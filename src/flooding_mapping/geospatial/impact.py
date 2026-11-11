"""Simulated impact of closing each ~1 km segment of the DAER state road network.

What is simulated (and what is not)
    The network is a graph: segment ends closer than ``SNAP_M`` are one node. Closing one
    segment at a time gives, exactly:

    * ``ponte``: the segment is a bridge of the graph, so its loss splits the network.
      ``pop_isolada`` is the population of the smaller side (a municipality's population is spread over
      the network nodes inside its boundary);
    * otherwise ``desvio_km``: the extra distance between the segment's two ends by the
      best alternative route.

    ``vdm`` is the stretch's average daily traffic. Where it exists, ``veiculos_km_dia``
    (vdm x desvio_km) weights the detour by traffic. A missing VDM stays missing (NaN) and is
    never read as zero traffic: rankings are given with and without the weight, on the
    segments that have it, and the coverage is reported.

Limits that matter
    This is a *simulated* impact on a coarse network: municipal and local roads are mostly
    absent from the layer, so many "bridges" are not real isolation, only the lack of a mapped
    alternative. It says where the mapped network is fragile, not what happens on the ground.
    Planned roads and the duplicated geometry of coincident roads are excluded.
"""

from __future__ import annotations

import argparse
import json

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from ..config import load_config, resolve

SNAP_M = 30.0
ATTACH_KM = 15.0
DETOUR_CAP_KM = 300.0
OUTPUT = "data/interim/impacto_rs.parquet"


def usable(segments: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Built roads without duplicates: no planned roads, no coincident (double-counted) geometry."""
    planned = segments["situacao_fisica"].str.upper().eq("PLANEJADA")
    coincident = segments["soma_extensao"].fillna("SIM").str.upper().eq("NÃO") | segments["soma_extensao"].fillna("SIM").str.upper().eq("NAO")
    return segments[~planned & ~coincident].reset_index(drop=True)


def build_graph(segments: gpd.GeoDataFrame, snap_m: float = SNAP_M) -> tuple[nx.Graph, pd.DataFrame]:
    """Graph with one edge per segment; also the node coordinates."""
    ends = np.array([[g.coords[0], g.coords[-1]] for g in segments.geometry])
    flat = ends.reshape(-1, 2)
    parent = np.arange(len(flat))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in cKDTree(flat).query_pairs(snap_m):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    node = np.array([find(i) for i in range(len(flat))]).reshape(-1, 2)
    graph = nx.Graph()
    for (u, v), row in zip(node, segments.itertuples()):
        if u == v:
            continue  # a piece shorter than the snap distance cannot disconnect anything
        u, v = int(u), int(v)
        if graph.has_edge(u, v):
            graph[u][v]["sids"].append(row.segmento_id)  # a second road between the same two nodes
        else:
            graph.add_edge(u, v, length=float(row.comprimento_m) / 1000, sids=[row.segmento_id])
    coords = pd.DataFrame(flat, columns=["x", "y"]).assign(no=node.ravel()).groupby("no").mean()
    return graph, coords


def attach_population(graph: nx.Graph, coords: pd.DataFrame, towns: gpd.GeoDataFrame, crs: str):
    """Spread each municipality's population over the network nodes inside its boundary.

    Those nodes are its road accesses. Attaching all of it to the node closest to the town
    centre would hang a whole city on a dead-end spur (the layer has no urban streets), so
    one cut would "isolate" it. A municipality with no node inside falls back to the nearest
    node within ``ATTACH_KM``; one farther than that is not counted.
    """
    nodes = coords.loc[list(graph.nodes)]
    points = gpd.GeoDataFrame(index=nodes.index, geometry=gpd.points_from_xy(nodes["x"], nodes["y"]), crs=crs)
    inside = gpd.sjoin(points.to_crs(towns.crs), towns[["ibge", "geometry"]], predicate="within")
    inside = inside[~inside.index.duplicated()]
    pop = {n: [] for n in graph.nodes}
    counts = inside.groupby("ibge").size()
    mapped = set(counts.index)
    for node, ibge in inside["ibge"].items():
        row = towns.loc[towns["ibge"] == ibge].iloc[0]
        pop[int(node)].append((ibge, row["nome"], float(row["populacao"]) / counts[ibge]))
    fallback = towns[~towns["ibge"].isin(mapped)]
    tree = cKDTree(nodes[["x", "y"]].to_numpy())
    far = gpd.GeoSeries(gpd.points_from_xy(fallback["lon"], fallback["lat"]), crs="EPSG:4326").to_crs(crs)
    distance, index = tree.query(np.c_[far.x, far.y])
    attached_fallback = 0
    for ok, i, row in zip(distance <= ATTACH_KM * 1000, index, fallback.itertuples()):
        if ok:
            pop[int(nodes.index[i])].append((row.ibge, row.nome, float(row.populacao)))
            attached_fallback += 1
    total = float(towns["populacao"].sum())
    counted = sum(p for entries in pop.values() for _, _, p in entries)
    return pop, {"municipios_com_no_no_poligono": len(mapped), "municipios_pelo_no_mais_proximo": attached_fallback,
                 "municipios_fora_da_rede": len(towns) - len(mapped) - attached_fallback,
                 "populacao_ligada_a_rede": round(counted / total, 4)}


def bridge_isolation(graph: nx.Graph, pop: dict) -> dict:
    """For every bridge of the main component: population on its smaller side (linear time)."""
    main = max(nx.connected_components(graph), key=len)
    sub = graph.subgraph(main)
    weight = {n: sum(p for _, _, p in pop[n]) for n in main}
    root = next(iter(main))
    tree = nx.dfs_tree(sub, root)
    order = list(nx.dfs_postorder_nodes(tree, root))
    below = dict(weight)
    for child in order:
        for parent in tree.predecessors(child):
            below[parent] += below[child]
    total = below[root]
    bridges = {frozenset(e) for e in nx.bridges(sub) if len(sub[e[0]][e[1]]["sids"]) == 1}  # parallel roads are no bridge
    out = {}
    for parent, child in tree.edges:
        if frozenset((parent, child)) in bridges:
            out[frozenset((parent, child))] = (min(below[child], total - below[child]), child)
    return out


def detour_km(graph: nx.Graph, u: int, v: int) -> float:
    """Extra distance between the ends of edge (u, v) when the edge is closed."""
    attrs = graph[u][v]
    if len(attrs["sids"]) > 1:
        return 0.0  # another road joins the same two nodes
    graph.remove_edge(u, v)
    try:
        alternative = nx.shortest_path_length(graph, u, v, weight="length")
    except nx.NetworkXNoPath:
        alternative = float("inf")
    finally:
        graph.add_edge(u, v, **attrs)
    return min(alternative - attrs["length"], DETOUR_CAP_KM) if np.isfinite(alternative) else float("inf")


def simulate(segments: gpd.GeoDataFrame, towns: gpd.GeoDataFrame, crs: str) -> tuple[pd.DataFrame, dict]:
    """One row per segment with its simulated impact, and a summary of the network."""
    segments = usable(segments)
    graph, coords = build_graph(segments)
    pop, attachment = attach_population(graph, coords, towns, crs)
    main = max(nx.connected_components(graph), key=len)
    isolation = bridge_isolation(graph, pop)
    by_sid = {sid: (u, v) for u, v, d in graph.edges(data=True) for sid in d["sids"]}
    records = []
    for row in segments.itertuples():
        uv = by_sid.get(row.segmento_id)
        record = {"segmento_id": row.segmento_id, "objectid": row.objectid, "codigo_sre": row.codigo_sre,
                  "nome": row.nome, "comprimento_m": row.comprimento_m, "vdm": row.vdm,
                  "na_rede_principal": bool(uv and uv[0] in main), "ponte": False,
                  "pop_isolada": 0.0, "desvio_km": np.nan}
        if record["na_rede_principal"]:
            key = frozenset(uv)
            if key in isolation:
                record.update(ponte=True, pop_isolada=isolation[key][0], desvio_km=np.inf)
            else:
                record["desvio_km"] = detour_km(graph, *uv)
        records.append(record)
    table = pd.DataFrame(records)
    table["veiculos_km_dia"] = np.where(table["vdm"].notna() & np.isfinite(table["desvio_km"]),
                                        table["vdm"] * table["desvio_km"], np.nan)
    summary = {
        "segmentos": len(table), "km": round(float(table["comprimento_m"].sum() / 1000)),
        "nos": graph.number_of_nodes(), "componentes": nx.number_connected_components(graph),
        "nos_rede_principal": len(main), "pontes": int(table["ponte"].sum()),
        **attachment,
        "cobertura_vdm_segmentos": round(float(table["vdm"].notna().mean()), 3),
        "cobertura_vdm_km": round(float(table.loc[table["vdm"].notna(), "comprimento_m"].sum() / table["comprimento_m"].sum()), 3),
    }
    return table, summary


def by_stretch(table: pd.DataFrame, trechos: pd.DataFrame) -> pd.DataFrame:
    """One row per official stretch: the worst of its segments, with the stretch's identity."""
    worst = table.groupby("objectid").agg(
        segmentos=("segmento_id", "size"), ponte=("ponte", "max"), pop_isolada=("pop_isolada", "max"),
        desvio_km=("desvio_km", lambda s: s.replace(np.inf, np.nan).max()),
        veiculos_km_dia=("veiculos_km_dia", "max"), vdm=("vdm", "first"), comprimento_km=("comprimento_m", lambda s: s.sum() / 1000))
    keys = trechos.drop_duplicates("objectid").set_index("objectid")[["codigo_sre", "nome", "km_inicio", "km_final", "local_inicio", "local_final"]]
    return worst.join(keys).reset_index()


def summary_for_app(table: pd.DataFrame, trechos: pd.DataFrame, segments: gpd.GeoDataFrame,
                    towns: gpd.GeoDataFrame, top: int = 15) -> dict:
    """Rankings with and without traffic weighting, municipal summaries and coverage."""
    stretches = by_stretch(table, trechos)
    keep = ["codigo_sre", "nome", "km_inicio", "km_final", "local_inicio", "local_final", "vdm"]
    fmt = lambda frame, extra: [{**{k: (None if pd.isna(r[k]) else r[k]) for k in keep + extra}} for _, r in frame.iterrows()]  # noqa: E731
    bridges = stretches[stretches["ponte"]].nlargest(top, "pop_isolada")
    weighted = stretches[stretches["veiculos_km_dia"].notna()].nlargest(top, "veiculos_km_dia")
    detour = stretches[~stretches["ponte"] & stretches["desvio_km"].notna()].nlargest(top, "desvio_km")
    covered = stretches[stretches["veiculos_km_dia"].notna()]
    rho = covered["desvio_km"].corr(covered["veiculos_km_dia"], method="spearman")
    overlap = len(set(covered.nlargest(50, "desvio_km")["objectid"]) & set(covered.nlargest(50, "veiculos_km_dia")["objectid"]))
    middle = segments.set_index("segmento_id").geometry.interpolate(0.5, normalized=True)
    points = gpd.GeoDataFrame(index=middle.index, geometry=middle.values, crs=segments.crs).to_crs(towns.crs)
    town_of = gpd.sjoin(points, towns[["ibge", "geometry"]], predicate="within")
    town_of = town_of[~town_of.index.duplicated()]["ibge"]
    joined = table.set_index("segmento_id").join(town_of)
    joined["km"] = joined["comprimento_m"] / 1000
    municipalities = {}
    for ibge, group in joined.dropna(subset=["ibge"]).groupby("ibge"):
        worst = group.loc[group["pop_isolada"].idxmax()] if group["ponte"].any() else None
        municipalities[ibge] = {
            "km_rede": round(float(group["km"].sum()), 1),
            "km_com_vdm": round(float(group.loc[group["vdm"].notna(), "km"].sum()), 1),
            "segmentos_ponte": int(group["ponte"].sum()),
            "maior_pop_isolada": int(group["pop_isolada"].max()),
            "trecho_critico": None if worst is None else f"{worst['nome']} ({worst['codigo_sre']})"}
    return {
        "natureza": "impacto SIMULADO do fechamento de cada segmento de 1 km na malha mapeada do DAER; "
                    "não é ocorrência observada nem previsão",
        "criterios": {"ponte": "o fechamento divide a rede; pop_isolada = população do lado menor",
                      "desvio_km": "distância extra entre as pontas do segmento pela melhor rota alternativa (teto de 300 km)",
                      "veiculos_km_dia": "VDM x desvio_km; só onde há VDM"},
        "limites": ["Estradas municipais e urbanas estão ausentes da camada: muitas 'pontes' são falta de "
                    "alternativa mapeada, não isolamento real.",
                    "VDM existe em cerca de 38% dos segmentos; VDM ausente não é tráfego zero e esses "
                    "segmentos ficam fora do ranking ponderado."],
        "cobertura": {"segmentos": len(table), "com_vdm": int(table["vdm"].notna().sum()),
                      "fracao_com_vdm": round(float(table["vdm"].notna().mean()), 3)},
        "com_x_sem_peso_do_vdm": {"trechos_com_vdm_e_desvio": len(covered), "spearman_desvio_x_ponderado": round(float(rho), 3),
                                  "sobreposicao_top50": overlap},
        "ranking_pontes_populacao_isolada": fmt(bridges, ["pop_isolada"]),
        "ranking_desvio_sem_vdm": fmt(detour, ["desvio_km"]),
        "ranking_veiculos_km_dia_com_vdm": fmt(weighted, ["desvio_km", "veiculos_km_dia"]),
        "municipios": municipalities}


def main() -> None:
    argparse.ArgumentParser(description="Simulated closure impact on the DAER network").parse_args()
    config = load_config()
    segments = gpd.read_parquet(resolve("data/interim/daer_segmentos.parquet")).drop(columns=["rede"])
    trechos = gpd.read_parquet(resolve("data/interim/daer_trechos.parquet"))
    attrs = trechos.drop(columns="geometry")
    segments = segments.merge(attrs[["objectid", "situacao_fisica", "soma_extensao", "vdm"]], on="objectid", how="left")
    towns = gpd.read_parquet(resolve("data/interim/municipios.parquet"))
    table, summary = simulate(segments, towns, config["daer"]["crs_metrico"])
    table.to_parquet(resolve(OUTPUT))
    usable_segments = segments[segments["segmento_id"].isin(table["segmento_id"])]
    app = summary_for_app(table, attrs, usable_segments, towns)
    app["rede"] = summary
    for target in ("outputs/web/impacto_rs.json", "reports/qa/impacto_rs.json"):
        out = resolve(target)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(app if "web" in target else {k: v for k, v in app.items() if k != "municipios"},
                                  indent=1, ensure_ascii=False, default=lambda o: None if pd.isna(o) else float(o)) + "\n")
    print(json.dumps(summary, ensure_ascii=False))
    print("com x sem VDM:", app["com_x_sem_peso_do_vdm"])


if __name__ == "__main__":
    main()
