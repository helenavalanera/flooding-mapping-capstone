"""Hourly rain for the city: the recent past and the next 72 h, from one forecast model.

One series for the whole city. The model grid is about 10 km, so the rain is the same for every
street: it says *when* it rains, not *where* in the city. That is a stated limit of the risk
baseline. The hours up to now come from the forecast model's own recent analysis (the best
"observed" rain available without gauges); the later ones are forecast.

A failed download never blocks the service: the last good series is served and flagged ``obsoleta``.
"""

from __future__ import annotations

import threading
import time
import urllib.request
from collections.abc import Callable

import pandas as pd

from .ingestion.forecast import FORECAST_URL
from .ingestion.weather import TIMEZONE, request

PAST_DAYS = 5      # covers the 24 h window and the 72 h before it for any hour from now back to -24 h
FORECAST_DAYS = 3
TIMEOUT_S = 10


class ChuvaIndisponivel(RuntimeError):
    """No rain series, not even an old one."""


def baixar(lat: float, lon: float, opener: Callable = urllib.request.urlopen) -> tuple[pd.Series, dict]:
    """Hourly precipitation (mm in the hour ending at each stamp), local time without zone."""
    params = {"latitude": lat, "longitude": lon, "hourly": "precipitation", "past_days": PAST_DAYS,
              "forecast_days": FORECAST_DAYS, "timezone": TIMEZONE}
    payload, _ = request(FORECAST_URL, params, lambda req, timeout: opener(req, timeout=TIMEOUT_S))
    hourly = payload["hourly"]
    series = pd.Series(hourly["precipitation"], index=pd.to_datetime(hourly["time"]), dtype="float64", name="mm")
    if series.empty or series.isna().all():
        raise ValueError("resposta sem chuva horária")
    meta = {"fonte": FORECAST_URL, "emitido_em_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "primeira_hora": str(series.index.min()), "ultima_hora": str(series.index.max()),
            "resolucao_espacial": "uma série para a cidade inteira (grade do modelo de cerca de 10 km)"}
    return series, meta


class ChuvaHoraria:
    """Cached hourly rain with a time-to-live; keeps serving the last good series on failure."""

    def __init__(self, lat: float, lon: float, ttl_s: float = 1800, fonte: Callable = baixar,
                 relogio: Callable[[], float] = time.monotonic):
        self.lat, self.lon, self.ttl_s, self._fonte, self._relogio = lat, lon, ttl_s, fonte, relogio
        self._valor: tuple[pd.Series, dict] | None = None
        self._em = 0.0
        self._lock = threading.Lock()

    def obter(self) -> tuple[pd.Series, dict]:
        with self._lock:
            if self._valor is None or self._relogio() - self._em > self.ttl_s:
                try:
                    self._valor, self._em = self._fonte(self.lat, self.lon), self._relogio()
                except Exception as erro:  # network, HTTP, malformed answer: keep the last good one
                    if self._valor is None:
                        raise ChuvaIndisponivel(f"sem chuva horária: {type(erro).__name__}") from erro
                    serie, meta = self._valor
                    self._valor = (serie, {**meta, "obsoleta": True, "motivo_obsolescencia": type(erro).__name__})
                    self._em = self._relogio() - self.ttl_s + 60  # retry in about a minute
            return self._valor
