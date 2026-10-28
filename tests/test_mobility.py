import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point

from flooding_mapping.accessibility import count_accessible
from flooding_mapping.metrics import losses, mobility_lost
from flooding_mapping.scenarios import blockage_count_fit, extra_points, model_hotspots

CRS = "EPSG:31982"


def test_count_accessible_sums_population_of_reachable_destinations():
    times = pd.DataFrame({"from_id": ["a", "a", "a", "b"], "to_id": ["x", "y", "z", "x"],
                          "travel_time": [10, 30, 31, np.nan]})
    weights = pd.Series({"x": 100.0, "y": 50.0, "z": 7.0})
    result = count_accessible(times, pd.Series(["a", "b", "c"]), 30, unlinked_ids=["c"],
                              weights=weights).set_index("origin_id")
    assert result.loc["a", "reachable_weight"] == 150
    assert result.loc["b", "reachable_weight"] == 0
    assert np.isnan(result.loc["c", "reachable_weight"])


def test_blockage_fit_ignores_missed_dates_and_never_goes_negative():
    per_date = pd.DataFrame({"event_date": ["d1", "d2", "d3"], "total_24h_mm": [20.0, 60.0, 5.0],
                             "captured": [True, True, False]})
    events = pd.DataFrame({"event_date": ["d2"] * 4 + ["d3"] * 9,
                           "event_type": ["bloqueio_total_acumulo_agua"] * 13})
    fit = blockage_count_fit(per_date, events)
    assert fit["dates"] == 2
    assert fit["slope"] == pytest.approx(0.1)          # 0 at 20 mm, 4 at 60 mm
    assert extra_points(fit, 10) == 0
    assert extra_points(fit, 60) == 4
    assert extra_points(fit, 60, factor=3) == 12


def test_model_hotspots_respect_minimum_distance():
    scores = gpd.GeoDataFrame({"segment_id": list("abcd"), "percentile": [0.99, 0.98, 0.97, 0.5]},
                              geometry=[Point(0, 0), Point(100, 0), Point(1000, 0), Point(3000, 0)],
                              crs=CRS)
    exclude = gpd.GeoSeries([Point(0, 2000)], crs=CRS)
    chosen = model_hotspots(scores, 2, exclude, 500)
    assert chosen["segment_id"].tolist() == ["a", "c"]   # b is 100 m from a
    blocked = model_hotspots(scores, 1, gpd.GeoSeries([Point(0, 100)], crs=CRS), 500)
    assert blocked["segment_id"].tolist() == ["c"]       # a and b are near the documented point


def run(values, scenario=None):
    frame = pd.DataFrame({"origin_id": ["o1", "o2"], "mode": "car",
                          "reachable_weight": values, "status": "ok"})
    return frame.assign(scenario_id=scenario) if scenario else frame


def test_mobility_lost_is_population_weighted_with_local_instability():
    population = pd.Series({"o1": 10.0, "o2": 30.0})
    same = mobility_lost(losses(run([1000.0, 500.0]), run([1000.0, 500.0], "S")), population).iloc[0]
    assert same["mobility_lost"] == 0 and same["origins_with_loss"] == 0
    row = mobility_lost(losses(run([1000.0, 500.0]), run([1000.0, 250.0], "S")), population).iloc[0]
    # before = 10*1000 + 30*500 = 25000; after = 10*1000 + 30*250 = 17500
    assert row["mobility_lost"] == pytest.approx(0.3)
    assert row["origins_with_loss"] == 1 and row["population_with_loss"] == 30
    assert row["max_origin_loss"] == pytest.approx(0.5)
    assert row["population_losing_10pct"] == 30
