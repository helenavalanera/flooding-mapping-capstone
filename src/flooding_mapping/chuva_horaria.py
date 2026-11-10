"""Hourly rain for the city: the recent past and the next 72 h, from one forecast model.

What the numbers are
    * hours up to now: the forecast model's own recent analysis. It is the best "observed" rain available without gauges,
      but it is NOT a gauge measurement;
    * hours after now: the model's forecast;
    * one series for the whole city (grid of about 10 km): it says *when* it rains, not *where* in the city.

What is guaranteed
    * the unit is checked (mm) and the time zone is local (America/Sao_Paulo, no daylight saving since 2019);
    * every answer carries when it was downloaded and its age; a failed refresh serves the last good series flagged as
      stale, but only up to ``VALIDADE_MAX_S``: older than that it is *unavailable*, never presented as current, and the error
      says when the last good download was.
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
TTL_S = 1800            # refresh every 30 min
VALIDADE_MAX_S = 6 * 3600   # a series older than this is not served: after 6 h without an update the forecast is too old to act on
ESCOPO = "estimativa regional: uma série para a cidade inteira (grade de cerca de 10 km), não medição neste trecho"
PASSADO = "análise do modelo de previsão (não é medição de pluviômetro)"


class ChuvaIndisponivel(RuntimeError):
    """No usable rain series. ``ultima_atualizacao`` is when the last good one was downloaded, if there ever was one."""

    def __init__(self, mensagem: str, ultima_atualizacao: str | None = None):
        super().__init__(mensagem)
        self.ultima_atualizacao = ultima_atualizacao


def baixar(lat: float, lon: float, opener: Callable = urllib.request.urlopen) -> tuple[pd.Series, dict]:
    """Hourly precipitation (mm in the hour ending at each stamp), local time without zone."""
    params = {"latitude": lat, "longitude": lon, "hourly": "precipitation", "past_days": PAST_DAYS,
              "forecast_days": FORECAST_DAYS, "timezone": TIMEZONE}
    payload, _ = request(FORECAST_URL, params, lambda req, timeout: opener(req, timeout=TIMEOUT_S))
    unidade = (payload.get("hourly_units") or {}).get("precipitation")
    if unidade != "mm":   # a different unit would silently scale every risk estimate
        raise ValueError(f"unidade de chuva inesperada: {unidade!r}")
    hourly = payload["hourly"]
    series = pd.Series(hourly["precipitation"], index=pd.to_datetime(hourly["time"]), dtype="float64", name="mm")
    if series.empty or series.isna().all():
        raise ValueError("resposta sem chuva horária")
    if payload.get("timezone") not in (None, TIMEZONE):
        raise ValueError(f"fuso inesperado: {payload.get('timezone')!r}")
    meta = {"fonte": FORECAST_URL, "emitido_em_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "primeira_hora": str(series.index.min()), "ultima_hora": str(series.index.max()), "unidade": "mm", "fuso": TIMEZONE,
            "resolucao_temporal": "horária", "resolucao_espacial": ESCOPO, "horas_passadas": PASSADO, "horas_futuras": "previsão do modelo"}
    return series, meta


class ChuvaHoraria:
    """Cached hourly rain with an explicit validity: fresh, stale (flagged) or unavailable (never silently old)."""

    def __init__(self, lat: float, lon: float, ttl_s: float = TTL_S, fonte: Callable = baixar,
                 relogio: Callable[[], float] = time.monotonic, validade_max_s: float = VALIDADE_MAX_S):
        self.lat, self.lon, self.ttl_s, self.validade_max_s, self._fonte, self._relogio = lat, lon, ttl_s, validade_max_s, fonte, relogio
        self._valor: tuple[pd.Series, dict] | None = None
        self._baixado_em = 0.0     # when the last GOOD series came in
        self._tentar_apos = 0.0    # not before this instant (a failure is retried in about a minute)
        self._lock = threading.Lock()

    def obter(self) -> tuple[pd.Series, dict]:
        with self._lock:
            agora = self._relogio()
            if self._valor is None or (agora - self._baixado_em > self.ttl_s and agora >= self._tentar_apos):
                try:
                    self._valor, self._baixado_em = self._fonte(self.lat, self.lon), agora
                except Exception as erro:  # network, HTTP, malformed answer, wrong unit
                    self._tentar_apos = agora + 60
                    if self._valor is None:
                        raise ChuvaIndisponivel(f"sem dados de chuva ({type(erro).__name__})") from erro
                    self._falha = type(erro).__name__
            serie, meta = self._valor
            idade = agora - self._baixado_em
            if idade > self.validade_max_s:
                raise ChuvaIndisponivel(f"dados de chuva desatualizados (última atualização há {round(idade / 3600, 1)} h)", meta["emitido_em_utc"])
            vencido = idade > self.ttl_s
            return serie, {**meta, "idade_min": round(idade / 60), "obsoleta": vencido,
                           **({"motivo_obsolescencia": getattr(self, "_falha", "desconhecido")} if vencido else {})}
