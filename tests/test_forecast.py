import json
import urllib.parse
from datetime import date

import pandas as pd

from flooding_mapping.ingestion import forecast


class FakeResponse:
    def __init__(self, body):
        self._body, self.headers = json.dumps(body).encode(), {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def towns(n):
    return pd.DataFrame({"ibge": [f"43{i:05d}" for i in range(n)], "lat": [-30.0] * n, "lon": [-51.0] * n})


def operational_api(calls):
    def opener(request, timeout):
        query = dict(urllib.parse.parse_qsl(request.full_url.split("?")[1]))
        calls.append(query)
        n = len(query["latitude"].split(","))
        days = pd.date_range("2026-09-29", periods=43).strftime("%Y-%m-%d").tolist()
        return FakeResponse([{"daily": {"time": days, "precipitation_sum": [float(k)] * 43}} for k in range(n)])
    return opener


def test_operational_series_is_fetched_in_batches_and_reports_its_window():
    calls = []
    series, meta = forecast.operational(towns(120), opener=operational_api(calls), sleep=lambda _: None)
    assert len(calls) == 3 and calls[0]["past_days"] == "40" and calls[0]["forecast_days"] == "3"
    assert series.shape == (43, 120) and series.index[0] == pd.Timestamp("2026-09-29")
    assert meta["ultima_data"] == "2026-11-10" and meta["dias_previstos"] == 3 and meta["municipios_sem_dado"] == []


def test_a_municipality_with_a_missing_day_is_reported():
    def opener(request, timeout):
        days = pd.date_range("2026-09-29", periods=43).strftime("%Y-%m-%d").tolist()
        values = [1.0] * 43
        values[-1] = None
        return FakeResponse([{"daily": {"time": days, "precipitation_sum": values}}])
    _, meta = forecast.operational(towns(1), opener=opener, sleep=lambda _: None)
    assert meta["municipios_sem_dado"] == ["4300000"]


def test_archived_forecast_sums_hours_to_days_and_caches(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        hours = pd.date_range("2025-06-01", periods=24 * 3, freq="h").strftime("%Y-%m-%dT%H:%M").tolist()
        values = [1.0] * 48 + [None] * 24  # the third day is incomplete
        return FakeResponse([{"hourly": {"time": hours, "precipitation_previous_day1": values}}])

    args = (towns(1), date(2025, 6, 1), date(2025, 6, 3), 1, tmp_path)
    first = forecast.archived(*args, opener=opener, sleep=lambda _: None)
    again = forecast.archived(*args, opener=opener, sleep=lambda _: None)
    assert first.iloc[0, 0] == 24.0 and first.iloc[1, 0] == 24.0 and pd.isna(first.iloc[2, 0])
    assert len(calls) == 1 and again.equals(first)  # second call came from the cache
