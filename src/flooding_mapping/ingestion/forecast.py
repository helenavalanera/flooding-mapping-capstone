"""Operational rainfall (observed past + 72 h forecast) and archived forecasts, per municipality.

``operational`` is what the live model consumes: the last ``PAST_DAYS`` days (the forecast
model's own recent analysis, the best available "observed" rain) followed by today and the
next two days. ``archived`` fetches forecasts as they were issued one or two days ahead
(Open-Meteo "previous runs"), which exist from mid-2024 and are the only honest way to measure
how much the model loses when it is fed forecasts instead of the reanalysis it was trained on.

Note: Open-Meteo's "historical forecast" endpoint returns the same series as the reanalysis
(0.00 mm/day difference on 2019-2026 samples), so it is *not* used as forecast evidence.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import urllib.request

import pandas as pd

from .weather import TIMEZONE, get

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
PAST_DAYS = 40  # the model needs 30 complete days of history
FORECAST_DAYS = 3  # today plus two more: 72 hours
BATCH = 50
ARCHIVED_FROM = date(2024, 6, 1)  # earlier dates return nothing for previous runs


def _coords(towns: pd.DataFrame) -> dict:
    return {"latitude": ",".join(map(str, towns["lat"])), "longitude": ",".join(map(str, towns["lon"]))}


def operational(towns: pd.DataFrame, opener: Callable = urllib.request.urlopen,
                sleep: Callable = time.sleep) -> tuple[pd.DataFrame, dict]:
    """Daily precipitation (days x ibge) for the past ``PAST_DAYS`` days and the next 72 h."""
    columns, issued = {}, datetime.now(timezone.utc)
    for start in range(0, len(towns), BATCH):
        part = towns.iloc[start:start + BATCH]
        payload, _ = get({**_coords(part), "daily": "precipitation_sum", "past_days": PAST_DAYS,
                          "forecast_days": FORECAST_DAYS, "timezone": TIMEZONE}, opener, sleep, FORECAST_URL)
        for ibge, item in zip(part["ibge"], payload if isinstance(payload, list) else [payload]):
            columns[ibge] = pd.Series(item["daily"]["precipitation_sum"],
                                      index=pd.to_datetime(item["daily"]["time"]), dtype="float64")
    series = pd.DataFrame(columns).sort_index()
    meta = {"fonte": FORECAST_URL, "emitido_em_utc": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dias_passados": PAST_DAYS, "dias_previstos": FORECAST_DAYS,
            "primeira_data": str(series.index.min().date()), "ultima_data": str(series.index.max().date()),
            "municipios_sem_dado": sorted(series.columns[series.isna().any()])}
    return series, meta


def archived(towns: pd.DataFrame, start: date, end: date, lead: int, root: Path,
             opener: Callable = urllib.request.urlopen, sleep: Callable = time.sleep) -> pd.DataFrame:
    """Daily rain forecast issued ``lead`` days ahead (1 or 2), days x ibge, cached on disk."""
    variable = f"precipitation_previous_day{lead}"
    root.mkdir(parents=True, exist_ok=True)
    pieces = []
    for first in range(0, len(towns), BATCH):
        part = towns.iloc[first:first + BATCH]
        cache = root / f"lead{lead}_{start}_{end}_{part['ibge'].iloc[0]}_{len(part)}.parquet"
        if not cache.exists():
            frames = {}
            day = start
            while day <= end:
                stop = min(end, day + timedelta(days=119))
                payload, _ = get({**_coords(part), "hourly": variable, "start_date": day.isoformat(),
                                  "end_date": stop.isoformat(), "timezone": TIMEZONE}, opener, sleep,
                                 PREVIOUS_RUNS_URL)
                for ibge, item in zip(part["ibge"], payload if isinstance(payload, list) else [payload]):
                    hourly = pd.Series(item["hourly"][variable], index=pd.to_datetime(item["hourly"]["time"]),
                                       dtype="float64")
                    frames.setdefault(ibge, []).append(hourly.groupby(hourly.index.normalize()).sum(min_count=24))
                day = stop + timedelta(days=1)
            pd.DataFrame({ibge: pd.concat(v) for ibge, v in frames.items()}).to_parquet(cache)
        pieces.append(pd.read_parquet(cache))
    return pd.concat(pieces, axis=1).sort_index()
