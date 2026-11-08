"""Segment criticality: which single blocked segments cost the most mobility.

Two stages. The screen is on the street graph and cheap, so it covers every
candidate segment: detour ratio, local efficiency lost and nodes cut off from
the network. The simulation runs the top segments through the same r5py
pipeline as the rain scenarios and gives the mobility lost by mode.
"""

import argparse
import json
import math

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd

from .config import load_config, resolve
from .metrics import losses, mobility_lost
from .robustness import build_graph, efficiency

REGION_M = 3000        # street graph around the segment used for the local measures
PAIR_RADIUS_M = 1000   # origins and destinations of the local efficiency
CUT_CAP = 20000        # a side larger than this is the main network, not a cut-off part
MODE_NAMES = {"walk": "a pé", "transit": "ônibus", "car": "carro"}


def drop_segment(graph: nx.Graph, segment_id: str, u, v) -> list:
    """Remove one segment from the graph in place; returns what restore_segment needs."""
    saved = []
    for a, b in ((u, v), (v, u)):
        if graph.has_edge(a, b) and segment_id in graph[a][b]["ids"]:
            saved.append((a, b, dict(graph[a][b]["ids"]), graph[a][b]["length"]))
            ids = {k: x for k, x in graph[a][b]["ids"].items() if k != segment_id}
            if ids:
                graph[a][b]["ids"] = ids
                graph[a][b]["length"] = min(ids.values())
            else:
                graph.remove_edge(a, b)
    return saved


def restore_segment(graph: nx.Graph, saved: list) -> None:
    for a, b, ids, length in saved:
        graph.add_edge(a, b, ids=ids, length=length)


def cut_off_nodes(graph: nx.Graph, u, v, cap: int = CUT_CAP) -> int:
    """Nodes that lose the network when the (already removed) segment u-v is missing.

    Expands both ends in turn over undirected connectivity: if the searches meet
    (or one side exceeds ``cap``) nothing is cut off; if one side is exhausted
    first, its size is the cut-off part.
    """
    view = graph.to_undirected(as_view=True)
    seen = {u: {u}, v: {v}}
    frontier = {u: [u], v: [v]}
    while True:
        for end, other in ((u, v), (v, u)):
            if not frontier[end]:
                return len(seen[end])
            node = frontier[end].pop()
            for neighbour in view[node]:
                if neighbour in seen[other]:
                    return 0
                if neighbour not in seen[end]:
                    seen[end].add(neighbour)
                    frontier[end].append(neighbour)
            if len(seen[end]) > cap:
                return 0


def screen_segment(graph: nx.Graph, segment_id: str, u, v, length: float, seed: int,
                   n_sources: int = 12, targets_per_source: int = 6) -> dict | None:
    """Detour, local efficiency lost and cut-off nodes for removing one segment."""
    if u not in graph or v not in graph or not (graph.has_edge(u, v) or graph.has_edge(v, u)):
        return None
    undirected = graph.to_undirected(as_view=True)
    near = nx.single_source_dijkstra_path_length(undirected, u, cutoff=REGION_M, weight="length")
    region = graph.subgraph(near)
    pool = sorted(n for n, d in near.items() if d <= PAIR_RADIUS_M)
    rng = np.random.default_rng(seed)
    pairs = []
    if len(pool) >= 2:
        for source in rng.choice(pool, size=min(n_sources, len(pool)), replace=False):
            targets = [t for t in rng.choice(pool, size=min(targets_per_source + 1, len(pool)),
                                             replace=False) if t != source][:targets_per_source]
            pairs += [(source, t) for t in targets]
    e0 = efficiency(region, pairs)
    saved = drop_segment(graph, segment_id, u, v)
    try:
        es = efficiency(region, pairs)
        try:
            detour = nx.shortest_path_length(region, u, v, weight="length") / max(length, 1.0)
        except nx.NetworkXNoPath:
            try:
                detour = nx.shortest_path_length(region, v, u, weight="length") / max(length, 1.0)
            except nx.NetworkXNoPath:
                detour = math.inf
        cut = cut_off_nodes(graph, u, v) if not math.isfinite(detour) else 0
    finally:
        restore_segment(graph, saved)
    return {"efficiency_lost": 1 - es / e0 if e0 and e0 > 0 else float("nan"),
            "detour_ratio": detour, "cut_off_nodes": cut, "pairs": len(pairs)}


def screen(segments: gpd.GeoDataFrame, candidates: pd.DataFrame, seed: int) -> pd.DataFrame:
    """One row per candidate and network with the cheap criticality measures."""
    rows = []
    by_id = segments.set_index("segment_id")
    for network in ("drive", "walk"):
        graph = build_graph(segments, network)
        for index, segment_id in enumerate(candidates["segment_id"]):
            row = by_id.loc[segment_id]
            if not row[network]:
                continue
            result = screen_segment(graph, segment_id, row["u"], row["v"], row["length_m"],
                                    seed + index)
            if result:
                rows.append({"segment_id": segment_id, "network": network, **result})
            if (index + 1) % 100 == 0:
                print(f"{network}: {index + 1}/{len(candidates)}", flush=True)
        print(network, "triagem concluída:", sum(r["network"] == network for r in rows))
    return pd.DataFrame(rows)


def screening_score(table: pd.DataFrame) -> pd.Series:
    """Per segment: largest efficiency lost over both networks plus a weight that grows with
    the size of the part cut off (log scale, 1 at 100 nodes), so dead ends do not dominate."""
    wide = table.pivot(index="segment_id", columns="network",
                       values=["efficiency_lost", "cut_off_nodes"])
    loss = wide["efficiency_lost"].fillna(0).clip(lower=0).max(axis=1)
    cut = wide["cut_off_nodes"].fillna(0).max(axis=1)
    return (loss + np.log1p(cut.clip(upper=100)) / np.log1p(100)).rename("screen_score")


def spaced_top(order: pd.Series, segments: gpd.GeoDataFrame, n: int, min_distance_m: float) -> list:
    """The first ``n`` segment ids of ``order`` that keep ``min_distance_m`` between midpoints."""
    centre = segments.drop_duplicates("segment_id").set_index("segment_id").geometry.centroid
    chosen = []
    for segment_id in order.index:
        point = centre[segment_id]
        if all(point.distance(centre[c]) >= min_distance_m for c in chosen):
            chosen.append(segment_id)
        if len(chosen) == n:
            break
    return chosen


def nearby_population(segments: gpd.GeoDataFrame, origins: gpd.GeoDataFrame, segment_ids,
                      radius_m: float) -> pd.Series:
    """Population of the origin cells whose centre lies within ``radius_m`` of each segment."""
    by_id = segments.drop_duplicates("segment_id").set_index("segment_id").geometry.centroid
    points = gpd.GeoDataFrame({"population": origins["population"].to_numpy()},
                              geometry=origins.geometry.centroid.to_crs(segments.crs).to_numpy(),
                              crs=segments.crs)
    tree = points.sindex
    totals = {}
    for segment_id in segment_ids:
        hit = tree.query(by_id[segment_id].buffer(radius_m), predicate="intersects")
        totals[segment_id] = float(points["population"].iloc[hit].sum())
    return pd.Series(totals, name="population_nearby")


def segment_names(pbf, segment_ids) -> dict:
    """OSM way names for the given segment ids."""
    import osmium

    wanted = {int(s.split(":")[0]) for s in segment_ids}
    return {way.id: way.tags.get("name") for way in osmium.FileProcessor(str(pbf), osmium.osm.WAY)
            if way.id in wanted and "name" in way.tags}


def recommendation(row: pd.Series) -> str:
    """Rule-based text for the segment sheet (no generated text)."""
    parts = []
    if row["cut_off_nodes"] > 0:
        parts.append(f"o bloqueio isola {int(row['cut_off_nodes'])} cruzamentos da rede")
    elif math.isfinite(row["detour_ratio"]) and row["detour_ratio"] >= 3:
        parts.append(f"o desvio mais curto é {row['detour_ratio']:.1f} vezes o trecho")
    if row["suscetibilidade_percentil"] >= 0.95:
        parts.append("a suscetibilidade a acúmulo de água está entre as 5% mais altas")
    if not parts:
        return "Sem característica estrutural que sugira prioridade; acompanhar."
    return "Priorizar inspeção da drenagem: " + "; ".join(parts) + "."


def export_web(config: dict, top: int = 20) -> None:
    """Small JSON/GeoJSON files for the interface: ranking, LCC by scenario, critical segments."""
    tables = resolve(config["paths"]["tables"])
    out = resolve("outputs/web")
    out.mkdir(parents=True, exist_ok=True)
    ranking = pd.read_csv(tables / "criticality_ranking.csv").head(top)
    keep = ["rank", "segment_id", "via", "highway", "population_nearby", "suscetibilidade_percentil",
            "efficiency_lost", "detour_ratio", "cut_off_nodes", "status", "recomendacao"]
    modes = [c[len("mobility_lost_"):] for c in ranking.columns
             if c.startswith("mobility_lost_") and c != "mobility_lost_sum"]
    ranking["modo_mais_afetado"] = ranking[[f"mobility_lost_{m}" for m in modes]].idxmax(axis=1).str[
        len("mobility_lost_"):].where(ranking["mobility_lost_sum"] > 0)
    keep += [f"mobility_lost_{m}" for m in modes] + [f"people_losing_10pct_{m}" for m in modes]
    records = ranking[keep + ["modo_mais_afetado"]].replace({float("inf"): None})
    (out / "ranking.json").write_text(
        json.dumps(records.where(records.notna(), None).to_dict(orient="records"),
                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    robust = pd.read_csv(tables / "robustness.csv")
    lcc = robust[robust["scenario_id"].str.startswith("S-C")][
        ["scenario_id", "network", "nodes", "LCC0", "LCCs", "LCC_ratio", "RE_global"]]
    (out / "lcc.json").write_text(json.dumps(lcc.round(6).to_dict(orient="records"), indent=2,
                                             ensure_ascii=False) + "\n", encoding="utf-8")

    from .network import load_or_build_segments

    interim = resolve(config["paths"]["interim"])
    segments = load_or_build_segments(interim / "poa.osm.pbf", interim / "segments.parquet",
                                      config["crs_metric"])
    chosen = segments[segments["segment_id"].isin(ranking["segment_id"])][["segment_id", "geometry"]]
    chosen = chosen.merge(ranking[["segment_id", "rank", "via"]], on="segment_id")
    chosen.to_crs("EPSG:4326").sort_values("rank").to_file(out / "critical_segments.geojson",
                                                          driver="GeoJSON")
    print("exportado em", out, [p.name for p in sorted(out.iterdir())])


def main() -> None:
    parser = argparse.ArgumentParser(description="Criticidade de trechos viários")
    sub = parser.add_subparsers(dest="command", required=True)
    s1 = sub.add_parser("screen", help="triagem em grafo dos trechos mais suscetíveis")
    s1.add_argument("--min-percentile", type=float, default=0.95)
    s1.add_argument("--limit", type=int, default=None, help="só os N mais suscetíveis (teste)")
    s2 = sub.add_parser("simulate", help="r5py nos K primeiros da triagem e ranking final")
    s2.add_argument("--top", type=int, default=20)
    s2.add_argument("--min-distance", type=float, default=500, help="metros entre trechos simulados")
    s2.add_argument("--population-radius", type=float, default=1500,
                    help="raio (m) da população exposta que pondera a triagem")
    s2.add_argument("--modes", nargs="+", default=None)
    sub.add_parser("export", help="ranking.json, lcc.json e critical_segments.geojson")
    args = parser.parse_args()

    from .network import load_or_build_segments

    config = load_config()
    if args.command == "export":
        export_web(config)
        return
    paths = config["paths"]
    tables, qa, interim = resolve(paths["tables"]), resolve(paths["qa"]), resolve(paths["interim"])
    segments = load_or_build_segments(interim / "poa.osm.pbf", interim / "segments.parquet",
                                      config["crs_metric"])
    scores = gpd.read_parquet(tables / "susceptibility.parquet")

    if args.command == "screen":
        candidates = scores[scores["percentile"] >= args.min_percentile].sort_values(
            "percentile", ascending=False)
        if args.limit:
            candidates = candidates.head(args.limit)
        table = screen(segments, candidates, config["robustness"]["semente"])
        table.to_parquet(tables / "criticality_screen.parquet", index=False)
        print(table.groupby("network")[["efficiency_lost", "cut_off_nodes"]].describe().T)
        return

    from .accessibility import BASELINE_TABLE, SCENARIO_DIR, run_baseline, run_scenarios
    from .scenarios import SCENARIO_COLUMNS, load_scenarios

    modes = args.modes or config["accessibility"]["modos"]
    screened = pd.read_parquet(tables / "criticality_screen.parquet")
    origins = gpd.read_parquet(resolve(paths["processed"]) / "origins.parquet")
    score = screening_score(screened)
    exposed = nearby_population(segments, origins, score.index, args.population_radius)
    # Structure times exposure: a cut-off dead end with nobody nearby costs no mobility.
    order = (score * exposed.reindex(score.index)).sort_values(ascending=False)
    top = spaced_top(order, segments, args.top, args.min_distance)

    path = resolve(paths["events"]) / "scenarios.csv"
    registry = load_scenarios(path)
    registry = registry[~registry["scenario_id"].str.startswith("S-K")]
    rows = pd.DataFrame([{
        "scenario_id": "S-K" + segment_id.replace(":", "_"), "event_id": "criticidade", "radius_m": 0,
        "network_type": "all", "affected_edge_ids": segment_id,
        "validation_status": "hipotetico", "validated_by": "", "validation_date": "",
        "notes": f"Bloqueio isolado do trecho {segment_id} (triagem de criticidade, posição {rank}).",
    } for rank, segment_id in enumerate(top, start=1)])
    pd.concat([registry, rows[list(SCENARIO_COLUMNS)]], ignore_index=True).to_csv(path, index=False)

    baseline_path = tables / BASELINE_TABLE
    baseline = pd.read_parquet(baseline_path) if baseline_path.exists() else run_baseline(config, modes)
    run_scenarios(config, rows["scenario_id"].tolist(), modes)

    population = origins.set_index("origin_id")["population"]
    result = []
    for row in rows.itertuples(index=False):
        scenario = pd.read_parquet(tables / SCENARIO_DIR / f"{row.scenario_id}.parquet")
        lost = mobility_lost(losses(baseline, scenario.assign(scenario_id=row.scenario_id)), population)
        wide = lost.set_index("mode")
        entry = {"segment_id": row.affected_edge_ids, "scenario_id": row.scenario_id}
        for mode in modes:
            entry[f"mobility_lost_{mode}"] = max(float(wide.loc[mode, "mobility_lost"]), 0.0)  # r5py noise ~1e-9
            entry[f"people_losing_10pct_{mode}"] = float(wide.loc[mode, "population_losing_10pct"])
            entry[f"max_origin_loss_{mode}"] = float(wide.loc[mode, "max_origin_loss"])
        result.append(entry)
    ranking = pd.DataFrame(result)
    ranking["mobility_lost_sum"] = ranking[[f"mobility_lost_{m}" for m in modes]].sum(axis=1)
    ranking = ranking.sort_values("mobility_lost_sum", ascending=False, kind="stable").reset_index(drop=True)
    ranking.insert(0, "rank", ranking.index + 1)

    by_id = segments.set_index("segment_id")
    names = segment_names(interim / "poa.osm.pbf", ranking["segment_id"])
    ranking["via"] = [names.get(int(s.split(":")[0]), "(sem nome no OSM)") for s in ranking["segment_id"]]
    ranking["highway"] = by_id.loc[ranking["segment_id"], "highway"].to_numpy()
    ranking["suscetibilidade_percentil"] = (scores.set_index("segment_id")
                                            .loc[ranking["segment_id"], "percentile"].to_numpy())
    drive = screened[screened["network"] == "drive"].set_index("segment_id")
    walk = screened[screened["network"] == "walk"].set_index("segment_id")
    for column in ("efficiency_lost", "detour_ratio", "cut_off_nodes"):
        ranking[column] = [max(float(drive[column].get(s, 0) or 0), float(walk[column].get(s, 0) or 0))
                           for s in ranking["segment_id"]]
    ranking["population_nearby"] = exposed.loc[ranking["segment_id"]].to_numpy()
    ranking["status"] = "candidato"
    ranking["recomendacao"] = ranking.apply(recommendation, axis=1)
    ranking.to_csv(tables / "criticality_ranking.csv", index=False)

    # Concentration for H3: share of the summed loss carried by the top segments.
    shares = (ranking["mobility_lost_sum"].cumsum() / ranking["mobility_lost_sum"].sum()).round(3)
    report = {"candidates_screened": int(screened["segment_id"].nunique()),
              "simulated": len(ranking), "modes": modes,
              "cumulative_share_of_simulated": shares.tolist(),
              "ranking": ranking.drop(columns=["recomendacao"]).round(5).to_dict(orient="records")}
    (qa / "criticality_run.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
    print(ranking[["rank", "via", "highway", *[f"mobility_lost_{m}" for m in modes]]].to_string(index=False))


if __name__ == "__main__":
    main()
