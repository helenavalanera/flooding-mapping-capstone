import math

import networkx as nx
import pandas as pd
import pytest

from flooding_mapping.robustness import (
    build_graph,
    efficiency,
    lcc_share,
    relative_efficiency,
    remove_segments,
    sample_pairs,
)

# Square 1-2-3-4 plus a parallel duplicate 1-2 and a one-way 4->5.
SEGMENTS = pd.DataFrame({
    "segment_id": ["a:1:2", "b:2:3", "c:3:4", "d:4:1", "e:1:2", "f:4:5"],
    "u": [1, 2, 3, 4, 1, 4], "v": [2, 3, 4, 1, 2, 5],
    "length_m": [100.0, 100.0, 100.0, 100.0, 150.0, 50.0],
    "oneway": ["no", "no", "no", "no", "no", "yes"],
    "walk": True, "drive": True,
})


def test_graph_types_and_oneway():
    walk, drive = build_graph(SEGMENTS, "walk"), build_graph(SEGMENTS, "drive")
    assert not walk.is_directed() and drive.is_directed()
    assert drive.has_edge(4, 5) and not drive.has_edge(5, 4)
    assert walk[1][2]["length"] == 100 and len(walk[1][2]["ids"]) == 2


def test_no_blocking_gives_relative_efficiency_one():
    graph = build_graph(SEGMENTS, "walk")
    pairs = sample_pairs(list(graph.nodes), 3, 2, seed=1)
    e0 = efficiency(graph, pairs)
    es = efficiency(remove_segments(graph, set()), pairs)
    assert e0 > 0 and relative_efficiency(es, e0) == 1


def test_parallel_segment_removed_individually_and_disconnection():
    graph = build_graph(SEGMENTS, "walk")
    after = remove_segments(graph, {"a:1:2"})
    assert after[1][2]["length"] == 150                       # duplicate e:1:2 remains
    cut = remove_segments(graph, {"f:4:5"})
    assert lcc_share(cut) == pytest.approx(4 / 5)
    assert efficiency(cut, [(1, 5)]) == 0                      # no path contributes 0


def test_sampling_is_reproducible_and_edge_cases():
    nodes = list(range(100))
    assert sample_pairs(nodes, 5, 3, 7) == sample_pairs(nodes, 5, 3, 7)
    assert sample_pairs(nodes, 5, 3, 7) != sample_pairs(nodes, 5, 3, 8)
    assert all(a != b for a, b in sample_pairs(nodes, 5, 3, 7))
    assert math.isnan(efficiency(nx.Graph(), []))
    assert math.isnan(lcc_share(nx.Graph()))
    assert math.isnan(relative_efficiency(0.5, 0.0))
