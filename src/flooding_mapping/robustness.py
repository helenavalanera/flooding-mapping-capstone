"""Network robustness: sampled global efficiency and connected components."""

import argparse
import json
import time

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import shapely

from .config import load_config, resolve

FORWARD_ONEWAY = {"yes", "true", "1"}


def weighted_mean(
    frame: pd.DataFrame, value_column: str, weight_column: str = "weight"
) -> float:
    """Calculate a weighted mean, rejecting an empty or zero-weight input."""
    if frame.empty:
        raise ValueError("Cannot calculate a weighted mean from an empty frame")
    weights = frame[weight_column]
    if weights.sum() == 0:
        raise ValueError("Scenario weights must not sum to zero")
    return float((frame[value_column] * weights).sum() / weights.sum())


def build_graph(segments: pd.DataFrame, network: str) -> nx.Graph:
    """Graph of one network from the segment table.

    ``walk`` gives an undirected graph; ``drive`` a directed graph that
    respects ``oneway``. Each edge keeps ``ids`` ({segment_id: length}) so
    parallel segments are removed individually; ``length`` is the minimum.
    """
    usable = segments[segments[network]]
    graph = nx.Graph() if network == "walk" else nx.DiGraph()
    for row in usable[["segment_id", "u", "v", "length_m", "oneway"]].itertuples(index=False):
        if network == "walk":
            arcs = [(row.u, row.v)]
        elif row.oneway in FORWARD_ONEWAY:
            arcs = [(row.u, row.v)]
        elif row.oneway == "-1":
            arcs = [(row.v, row.u)]
        else:
            arcs = [(row.u, row.v), (row.v, row.u)]
        for a, b in arcs:
            if graph.has_edge(a, b):
                graph[a][b]["ids"][row.segment_id] = row.length_m
            else:
                graph.add_edge(a, b, ids={row.segment_id: row.length_m})
            graph[a][b]["length"] = min(graph[a][b]["ids"].values())
    return graph


def remove_segments(graph: nx.Graph, segment_ids: set[str]) -> nx.Graph:
    """Copy of ``graph`` without the given segments (edges emptied are removed)."""
    result = graph.copy()
    for a, b, data in graph.edges(data=True):
        hit = segment_ids & data["ids"].keys()
        if not hit:
            continue
        remaining = {k: v for k, v in data["ids"].items() if k not in hit}
        if remaining:
            result[a][b]["ids"] = remaining
            result[a][b]["length"] = min(remaining.values())
        else:
            result.remove_edge(a, b)
    return result


def largest_component(graph: nx.Graph) -> set:
    """Nodes of the largest (weakly, if directed) connected component."""
    if graph.number_of_nodes() == 0:
        return set()
    components = (nx.weakly_connected_components(graph) if graph.is_directed()
                  else nx.connected_components(graph))
    return max(components, key=len)


def lcc_share(graph: nx.Graph) -> float:
    """Share of nodes in the largest (weakly) connected component; NaN if empty."""
    if graph.number_of_nodes() == 0:
        return float("nan")
    return len(largest_component(graph)) / graph.number_of_nodes()


def sample_pairs(nodes: list, n_sources: int, targets_per_source: int, seed: int) -> list[tuple]:
    """Reproducible origin-destination node pairs (no self pairs)."""
    nodes = sorted(nodes)
    if len(nodes) < 2:
        return []
    rng = np.random.default_rng(seed)
    pairs = []
    for source in rng.choice(nodes, size=min(n_sources, len(nodes)), replace=False):
        candidates = [n for n in rng.choice(nodes, size=targets_per_source + 1, replace=False)
                      if n != source][:targets_per_source]
        pairs += [(source, target) for target in candidates]
    return pairs


def efficiency(graph: nx.Graph, pairs: list[tuple]) -> float:
    """Mean of 1/d over pairs, d = length-weighted shortest path; unreachable
    pairs (or nodes missing from the graph) contribute 0. NaN without pairs."""
    if not pairs:
        return float("nan")
    total = 0.0
    by_source: dict = {}
    for source, target in pairs:
        by_source.setdefault(source, []).append(target)
    for source, targets in by_source.items():
        if source not in graph:
            continue
        distances = nx.single_source_dijkstra_path_length(graph, source, weight="length")
        total += sum(1 / distances[t] for t in targets if t in distances and distances[t] > 0)
    return total / len(pairs)


def relative_efficiency(e_s: float, e_0: float) -> float:
    """R_E = E_s / E_0; NaN when E_0 is not positive."""
    return e_s / e_0 if e_0 > 0 else float("nan")


def robustness_table(segments: gpd.GeoDataFrame, scenarios: pd.DataFrame, config: dict,
                     local_radius_m: float = 1000) -> pd.DataFrame:
    """Global and local efficiency and LCC share before/after each scenario."""
    seed = config["robustness"]["semente"]
    n_pairs = config["robustness"]["n_pares"]
    n_sources = max(1, n_pairs // 10)
    rows = []
    for network in ("walk", "drive"):
        started = time.perf_counter()
        graph = build_graph(segments, network)
        core = largest_component(graph)
        global_pairs = sample_pairs(list(core), n_sources, 10, seed)
        e0_global = efficiency(graph, global_pairs)
        lcc0 = lcc_share(graph)
        first = segments.drop_duplicates("u").set_index("u").geometry
        node_xy = gpd.GeoSeries(shapely.get_point(first.values, 0), index=first.index)
        base_seconds = round(time.perf_counter() - started, 1)
        for row in scenarios.itertuples(index=False):
            started = time.perf_counter()
            blocked = set(row.affected_edge_ids.split(";"))
            zone = segments[segments["segment_id"].isin(blocked)].union_all().buffer(local_radius_m)
            local_nodes = [n for n in core if n in node_xy.index and node_xy[n].intersects(zone)]
            local_pairs = sample_pairs(local_nodes, n_sources, 10, seed)
            after = remove_segments(graph, blocked)
            e0_local = efficiency(graph, local_pairs)
            es_global, es_local = efficiency(after, global_pairs), efficiency(after, local_pairs)
            rows.append({
                "scenario_id": row.scenario_id, "network": network,
                "directed": graph.is_directed(), "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(), "pairs_global": len(global_pairs),
                "pairs_local": len(local_pairs), "E0_global": e0_global, "Es_global": es_global,
                "RE_global": relative_efficiency(es_global, e0_global), "E0_local": e0_local,
                "Es_local": es_local, "RE_local": relative_efficiency(es_local, e0_local),
                "LCC0": lcc0, "LCCs": lcc_share(after),
                "seconds": round(time.perf_counter() - started, 1), "base_seconds": base_seconds,
            })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Robustez das redes de pedestres e viária")
    parser.add_argument("--scenarios", nargs="+", required=True)
    args = parser.parse_args()
    from .network import load_or_build_segments
    from .scenarios import load_scenarios

    config = load_config()
    interim = resolve(config["paths"]["interim"])
    segments = load_or_build_segments(interim / "poa.osm.pbf", interim / "segments.parquet",
                                      config["crs_metric"])
    scenarios = load_scenarios(resolve(config["paths"]["events"]) / "scenarios.csv")
    unknown = sorted(set(args.scenarios) - set(scenarios["scenario_id"]))
    if unknown:
        raise SystemExit(f"Cenários inexistentes em scenarios.csv: {unknown}")
    scenarios = scenarios[scenarios["scenario_id"].isin(args.scenarios)]
    table = robustness_table(segments, scenarios, config)
    tables = resolve(config["paths"]["tables"])
    tables.mkdir(parents=True, exist_ok=True)
    table.to_csv(tables / "robustness.csv", index=False)
    print(table.to_string(index=False))
    summary = table[["scenario_id", "network", "RE_global", "RE_local", "LCC0", "LCCs",
                     "seconds"]].to_dict(orient="records")
    (resolve(config["paths"]["qa"]) / "robustness_run.json").write_text(
        json.dumps({"seed": config["robustness"]["semente"],
                    "n_pairs": config["robustness"]["n_pares"], "results": summary},
                   indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
