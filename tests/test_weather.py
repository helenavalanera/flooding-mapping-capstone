import io
import json
import urllib.error
from datetime import date

import pandas as pd
import pytest

from flooding_mapping.ingestion import weather

TOWNS = pd.DataFrame({"ibge": [f"43{i:05d}" for i in range(45)],
                      "lat": [-30.0 - i / 100 for i in range(45)],
                      "lon": [-51.0 - i / 100 for i in range(45)]})


class FakeResponse:
    def __init__(self, body, headers=None):
        self._body, self.headers = body, headers or {"X-RateLimit-Cost": "5"}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def api(request, timeout):
    """Answer like Open-Meteo: one entry per requested location, one value per day."""
    query = dict(p.split("=") for p in request.full_url.split("?")[1].split("&"))
    n = len(query["latitude"].split(","))
    days = (date.fromisoformat(query["end_date"]) - date.fromisoformat(query["start_date"])).days + 1
    items = [{"latitude": 1.5, "longitude": 2.5, "elevation": 10.0,
              "daily": {"time": [], "precipitation_sum": [float(k)] * days}} for k in range(n)]
    return FakeResponse(json.dumps(items).encode())


def test_plan_covers_every_municipality_and_year_newest_first():
    chunks = weather.plan(list(TOWNS["ibge"]), date(2022, 1, 1), date(2023, 6, 30))
    assert [c["year"] for c in chunks] == [2023] * 3 + [2022] * 3  # 45 towns = 3 batches
    assert chunks[0]["end"] == date(2023, 6, 30) and chunks[3]["start"] == date(2022, 1, 1)
    assert sum(len(c["ibge"]) for c in chunks if c["year"] == 2023) == 45


def test_download_caches_chunks_and_resumes_without_repeating_requests(tmp_path):
    calls = []

    def counting(request, timeout):
        calls.append(request.full_url)
        return api(request, timeout)

    first = weather.download(TOWNS, date(2023, 1, 1), date(2023, 1, 10), root=tmp_path,
                             opener=counting, sleep=lambda _: None)
    again = weather.download(TOWNS, date(2023, 1, 1), date(2023, 1, 10), root=tmp_path,
                             opener=counting, sleep=lambda _: None)
    assert first["parou"] == "concluído" and first["baixados"] == 3
    assert again["baixados"] == 0 and again["ja_em_cache"] == 3
    assert len(calls) == 3

    table = weather.load(root=tmp_path)
    assert len(table) == 45 * 10 and table["data"].min() == pd.Timestamp("2023-01-01")
    assert table.attrs["grade"]["altitude_m"].iloc[0] == 10.0


def test_run_stops_before_exceeding_the_cost_budget(tmp_path):
    summary = weather.download(TOWNS, date(2023, 1, 1), date(2023, 1, 10), max_cost=8,
                               root=tmp_path, opener=api, sleep=lambda _: None)
    assert summary["parou"] == "orçamento da execução"
    assert summary["baixados"] == 1 and summary["restantes"] == 2


def limit_error(reason):
    return urllib.error.HTTPError("u", 429, "Too Many", {}, io.BytesIO(json.dumps({"reason": reason}).encode()))


def test_minute_limit_waits_and_retries(tmp_path):
    state = {"n": 0}
    slept = []

    def flaky(request, timeout):
        state["n"] += 1
        if state["n"] == 1:
            raise limit_error("Minutely API request limit exceeded")
        return api(request, timeout)

    summary = weather.download(TOWNS.head(5), date(2023, 1, 1), date(2023, 1, 3), root=tmp_path,
                               opener=flaky, sleep=slept.append)
    assert summary["parou"] == "concluído" and 65 in slept


def test_daily_limit_stops_the_run_and_keeps_what_was_cached(tmp_path):
    state = {"n": 0}

    def exhausted(request, timeout):
        state["n"] += 1
        if state["n"] == 2:
            raise limit_error("Daily API request limit exceeded")
        return api(request, timeout)

    summary = weather.download(TOWNS, date(2023, 1, 1), date(2023, 1, 3), root=tmp_path,
                               opener=exhausted, sleep=lambda _: None)
    assert summary["parou"] == "limite diário" and summary["baixados"] == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_other_http_errors_are_not_swallowed(tmp_path):
    def broken(request, timeout):
        raise urllib.error.HTTPError("u", 500, "boom", {}, io.BytesIO(b"{}"))

    with pytest.raises(urllib.error.HTTPError):
        weather.download(TOWNS.head(2), date(2023, 1, 1), date(2023, 1, 2), root=tmp_path,
                         opener=broken, sleep=lambda _: None)


def test_network_errors_are_retried_with_a_growing_wait_and_then_raised(tmp_path):
    state = {"n": 0}
    slept = []

    def flaky(request, timeout):
        state["n"] += 1
        if state["n"] <= 2:
            raise urllib.error.URLError("handshake timed out")
        return api(request, timeout)

    summary = weather.download(TOWNS.head(5), date(2023, 1, 1), date(2023, 1, 3), root=tmp_path,
                               opener=flaky, sleep=slept.append)
    assert summary["parou"] == "concluído" and slept[:2] == [30, 60]

    def down(request, timeout):
        raise urllib.error.URLError("unreachable")

    with pytest.raises(urllib.error.URLError):
        weather.download(TOWNS.head(5), date(2022, 1, 1), date(2022, 1, 3), root=tmp_path,
                         opener=down, sleep=lambda _: None)


def test_a_truncated_response_is_retried_like_any_network_error(tmp_path):
    state = {"n": 0}

    def cut_short(request, timeout):
        state["n"] += 1
        if state["n"] == 1:
            return FakeResponse(b'[{"latitude": 1.5, "daily": {"time": [')  # connection died mid-body
        return api(request, timeout)

    summary = weather.download(TOWNS.head(5), date(2023, 1, 1), date(2023, 1, 3), root=tmp_path,
                               opener=cut_short, sleep=lambda _: None)
    assert summary["parou"] == "concluído" and state["n"] == 2
