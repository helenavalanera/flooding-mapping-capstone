from datetime import datetime

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from flooding_mapping import rain
from flooding_mapping.dashboard import forecast_points


def test_window_stats_uses_24h_before_report():
    index = pd.date_range("2025-06-17 00:00", "2025-06-18 23:00", freq="h")
    series = pd.Series(0.0, index=index)
    series["2025-06-18 10:00"] = 8.0       # inside the window
    series["2025-06-18 22:00"] = 50.0      # after the report: ignored
    series["2025-06-17 20:00"] = 2.0       # 25 h before: ignored
    stats = rain.window_stats(series, datetime(2025, 6, 18, 21))
    assert stats == {"max_1h_mm": 8.0, "total_24h_mm": 8.0, "hours": 24}


def test_calibration_excludes_dates_the_model_missed(monkeypatch):
    def fake_fetch(lats, lons, start, end):
        index = pd.date_range(f"{start} 00:00", f"{end} 23:00", freq="h")
        wet = end == "2025-06-18"
        values = pd.Series(4.0 if wet else 0.1, index=index)
        return [values for _ in lats]

    monkeypatch.setattr(rain, "fetch_hourly", fake_fetch)
    events = pd.DataFrame({
        "event_id": ["a", "b"], "event_date": ["2025-06-18", "2022-03-06"],
        "latitude": [-30.0, -30.1], "longitude": [-51.2, -51.2],
    })
    result = rain.calibrate(events)
    assert result["missed_by_model"] == ["2022-03-06"]
    assert result["thresholds"]["medio_max_1h_mm"] == 4.0
    assert result["thresholds"]["medio_total_24h_mm"] == 96.0


def test_forecast_points_fall_inside_the_area():
    area = gpd.GeoDataFrame(geometry=[box(0, 0, 9000, 9000)], crs="EPSG:31982")
    points = forecast_points(area, n=3)
    assert len(points) == 9
    assert points.within(area.union_all()).all()
