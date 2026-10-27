import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

from flooding_mapping.susceptibility import (
    alert,
    event_ranks,
    label_segments,
    percentile_rank,
    terrain_rasters,
)

CRS = "EPSG:31982"


def test_percentile_rank_and_random_expectation():
    assert percentile_rank(np.array([3.0, 1.0, 2.0])).tolist() == pytest.approx([1, 1 / 3, 2 / 3])
    rng = np.random.default_rng(0)
    table = pd.DataFrame({"event_id": [f"e{i}" if i < 2000 else None for i in range(20000)]})
    table["event_anchor"] = table["event_id"].notna()
    table["positive"] = table["event_anchor"]
    ranks = event_ranks(table, rng.random(len(table)))
    assert len(ranks) == 2000
    assert ranks.median() == pytest.approx(0.5, abs=0.03)


def test_label_segments_marks_positives_and_one_anchor_per_event():
    table = gpd.GeoDataFrame({"segment_id": list("abcd")},
                             geometry=[Point(0, 0), Point(30, 0), Point(500, 0), Point(10, 0)],
                             crs=CRS)
    point = gpd.GeoSeries([Point(9, 0)], crs=CRS).to_crs("EPSG:4326").iloc[0]
    events = pd.DataFrame({"event_id": ["e1"], "event_date": ["2025-06-18"],
                           "latitude": [point.y], "longitude": [point.x]})
    labelled = label_segments(table, events, radius_m=50).set_index("segment_id")
    assert labelled["positive"].tolist() == [True, True, False, True]
    assert labelled["event_anchor"].sum() == 1 and labelled.loc["d", "event_anchor"]
    assert labelled.loc["a", "event_year"] == 2025


def test_terrain_rasters_relative_elevation_finds_depression():
    dem = np.full((41, 41), 10.0, dtype="float32")
    dem[20, 20] = 5.0
    rasters = terrain_rasters(dem)
    assert rasters["rel_elev_250"][20, 20] < 0
    assert rasters["slope"][0, 0] == pytest.approx(0)


def test_alert_respects_rain_threshold_and_percentile():
    config = {"susceptibility": {"alerta_chuva_mm_h": 30, "alerta_percentil": 0.9,
                                 "alerta_raio_m": 50}}
    scores = gpd.GeoDataFrame({"segment_id": ["s1", "s2"], "percentile": [0.95, 0.5]},
                              geometry=[LineString([(0, 0), (100, 0)]),
                                        LineString([(0, 1000), (100, 1000)])], crs=CRS)
    routes = gpd.GeoDataFrame({"route_short_name": ["R1", "R2"]},
                              geometry=[LineString([(50, -20), (50, 20)]),
                                        LineString([(50, 980), (50, 1020)])], crs=CRS)
    destinations = gpd.GeoDataFrame({"dest_id": ["d1"], "name": ["H"], "category": ["hospital"]},
                                    geometry=[Point(50, 30)], crs=CRS)
    assert alert(scores, 10, config, routes, destinations) == {"rain_mm_h": 10, "triggered": False}
    result = alert(scores, 45, config, routes, destinations)
    assert result["triggered"] and result["segments"] == 1
    assert result["routes"] == ["R1"]
    assert [d["dest_id"] for d in result["destinations"]] == ["d1"]
