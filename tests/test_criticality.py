import math

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString

from flooding_mapping.criticality import (cut_off_nodes, drop_segment, recommendation,
                                          restore_segment, screen_segment, screening_score,
                                          spaced_top)


def line_with_loop():
    """a-b-c-d in a line, plus a parallel route b-e-c (so b-c has a detour) and a spur d-f."""
    graph = nx.Graph()
    for sid, a, b, length in [("ab", "a", "b", 100), ("bc", "b", "c", 100), ("cd", "c", "d", 100),
                              ("be", "b", "e", 150), ("ec", "e", "c", 150), ("df", "d", "f", 50)]:
        graph.add_edge(a, b, ids={sid: length}, length=length)
    return graph


def test_drop_and_restore_leave_the_graph_unchanged():
    graph = line_with_loop()
    before = nx.to_dict_of_dicts(graph)
    saved = drop_segment(graph, "bc", "b", "c")
    assert not graph.has_edge("b", "c")
    restore_segment(graph, saved)
    assert nx.to_dict_of_dicts(graph) == before


def test_detour_ratio_and_no_cut_when_a_parallel_route_exists():
    result = screen_segment(line_with_loop(), "bc", "b", "c", 100, seed=1)
    assert result["detour_ratio"] == 3.0          # b-e-c is 300 m for a 100 m segment
    assert result["cut_off_nodes"] == 0
    assert result["efficiency_lost"] > 0


def test_bridge_cuts_off_the_small_side():
    graph = line_with_loop()
    result = screen_segment(graph, "df", "d", "f", 50, seed=1)
    assert math.isinf(result["detour_ratio"])
    assert result["cut_off_nodes"] == 1            # only the spur node f
    drop_segment(graph, "df", "d", "f")
    assert cut_off_nodes(graph, "d", "f") == 1


def test_screening_score_weights_large_cut_off_above_efficiency_loss():
    table = pd.DataFrame({"segment_id": ["x", "x", "y", "y"],
                          "network": ["drive", "walk"] * 2,
                          "efficiency_lost": [0.02, 0.05, 0.4, 0.3],
                          "cut_off_nodes": [0, 60, 0, 0]})
    score = screening_score(table)
    assert score["x"] > score["y"]
    dead_end = pd.DataFrame({"segment_id": ["d", "y"], "network": ["walk", "walk"],
                             "efficiency_lost": [0.0, 0.4], "cut_off_nodes": [1, 0]})
    scores = screening_score(dead_end)
    assert scores["d"] < scores["y"]       # a one-node dead end does not outrank a real loss


def test_recommendation_is_rule_based():
    row = pd.Series({"cut_off_nodes": 4, "detour_ratio": math.inf, "suscetibilidade_percentil": 0.97})
    text = recommendation(row)
    assert "isola 4 cruzamentos" in text and "5% mais altas" in text
    quiet = pd.Series({"cut_off_nodes": 0, "detour_ratio": 1.2, "suscetibilidade_percentil": 0.5})
    assert recommendation(quiet).startswith("Sem característica")


def test_spaced_top_skips_neighbouring_segments():
    segments = gpd.GeoDataFrame(
        {"segment_id": ["a", "b", "c"]},
        geometry=[LineString([(0, 0), (10, 0)]), LineString([(100, 0), (110, 0)]),
                  LineString([(2000, 0), (2010, 0)])], crs="EPSG:31982")
    order = pd.Series([3.0, 2.0, 1.0], index=["a", "b", "c"])
    assert spaced_top(order, segments, 2, 500) == ["a", "c"]
