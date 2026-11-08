import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, box

from flooding_mapping.scenarios import (
    geocode_events,
    intersection_point,
    load_events,
    nearest_to_landmark,
    segment_between,
    street_midpoint,
)

CRS = "EPSG:31982"
# A "+" junction at node 2 (x=1000, y=1000) plus a separate street far away.
NODES = gpd.GeoDataFrame(
    {"id": [1, 2, 3, 4, 5, 6, 7]},
    geometry=[Point(0, 1000), Point(1000, 1000), Point(2000, 1000), Point(1000, 0),
              Point(1000, 2000), Point(5000, 5000), Point(6000, 5000)],
    crs=CRS,
)
EDGES = gpd.GeoDataFrame(
    {"name": ["Rua A", "Rua A", "Rua B", "Rua B", "Rua C"],
     "u": [1, 2, 4, 2, 6], "v": [2, 3, 2, 5, 7]},
    geometry=[LineString([(0, 1000), (1000, 1000)]), LineString([(1000, 1000), (2000, 1000)]),
              LineString([(1000, 0), (1000, 1000)]), LineString([(1000, 1000), (1000, 2000)]),
              LineString([(5000, 5000), (6000, 5000)])],
    crs=CRS,
)


def test_intersection_of_named_streets():
    point = intersection_point(EDGES, NODES, "Rua A", "Rua B", CRS)
    assert (point.x, point.y) == (1000, 1000)
    assert intersection_point(EDGES, NODES, "Rua A", "Rua C", CRS) is None
    # Alternative names separated by '|' are accepted.
    assert intersection_point(EDGES, NODES, "Rua X|Rua A", "Rua B", CRS) is not None


def test_street_midpoint_and_landmark_limit():
    assert street_midpoint(EDGES, "Rua A", CRS).equals(Point(1000, 1000))
    landmark = box(5400, 5100, 5600, 5200)
    near = nearest_to_landmark(EDGES, "Rua C", landmark, CRS)
    assert near.y == 5000 and 5400 <= near.x <= 5600
    assert near.distance(landmark) == pytest.approx(100)
    assert nearest_to_landmark(EDGES, "Rua C", box(5400, 6000, 5600, 6100), CRS) is None


def test_geocode_events_keeps_pending_and_unresolved_empty():
    events = pd.DataFrame({
        "event_id": ["e1", "e2", "e3"],
        "geocode_method": ["osm_intersection", "osm_intersection", "pendente"],
        "osm_street_a": ["Rua A", "Rua A", ""], "osm_street_b": ["Rua B", "Rua C", ""],
        "latitude": [None] * 3, "longitude": [None] * 3,
    })
    result = geocode_events(events, EDGES, NODES, {}, CRS).set_index("event_id")
    assert result.loc["e1", "geocode_detail"] == "ok"
    assert pd.notna(result.loc["e1", "latitude"])
    assert result.loc["e2", "geocode_detail"] == "não geocodificado"
    assert pd.isna(result.loc["e2", "latitude"])
    assert result.loc["e3", "geocode_detail"] == "pendente"


def test_load_events_rejects_duplicates_and_bad_confidence(tmp_path):
    base = {"event_id": "e1", "event_date": "2025-06-18", "event_type": "t", "source_name": "s",
            "source_url": "https://x", "latitude": "", "longitude": "", "confidence": "alta",
            "description": "", "verification_status": "v"}
    path = tmp_path / "events.csv"
    pd.DataFrame([base, base]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="Duplicated"):
        load_events(path)
    pd.DataFrame([{**base, "confidence": "certeza"}]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="confidence"):
        load_events(path)


def test_segment_between_two_cross_streets():
    nodes = gpd.GeoDataFrame(
        {"id": [1, 2, 3, 4, 5, 6]},
        geometry=[Point(0, 0), Point(1000, 0), Point(2000, 0), Point(0, 500), Point(2000, 500),
                  Point(1000, 500)],
        crs=CRS,
    )
    edges = gpd.GeoDataFrame(
        {"name": ["Main", "Main", "West", "East"], "u": [1, 2, 1, 3], "v": [2, 3, 4, 5]},
        geometry=[LineString([(0, 0), (1000, 0)]), LineString([(1000, 0), (2000, 0)]),
                  LineString([(0, 0), (0, 500)]), LineString([(2000, 0), (2000, 500)])],
        crs=CRS,
    )
    assert segment_between(edges, nodes, "Main", "West;East", CRS).equals(Point(1000, 0))
    assert segment_between(edges, nodes, "Main", "West;Nowhere", CRS) is None
