import io
import json
import urllib.error

import pytest

from flooding_mapping import chuva_horaria as ch


class Resposta(io.BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_com(horas=72, mm=0.5):
    chamadas = []

    def opener(req, timeout):
        chamadas.append((req.full_url, timeout))
        tempos = [f"2026-11-09T{h % 24:02d}:00" if h < 24 else f"2026-11-{9 + h // 24:02d}T{h % 24:02d}:00" for h in range(horas)]
        return Resposta(json.dumps({"hourly": {"time": tempos, "precipitation": [mm] * horas}}).encode())
    opener.chamadas = chamadas
    return opener


def test_download_asks_for_hourly_rain_with_a_short_timeout_and_no_credentials():
    opener = opener_com()
    serie, meta = ch.baixar(-30.03, -51.22, opener)
    url, timeout = opener.chamadas[0]
    assert "hourly=precipitation" in url and "past_days=5" in url and "forecast_days=3" in url
    assert timeout == ch.TIMEOUT_S <= 15 and "key" not in url.lower()
    assert len(serie) == 72 and serie.index.is_monotonic_increasing and meta["resolucao_espacial"]


def test_an_empty_answer_is_an_error_not_a_dry_forecast():
    def vazio(req, timeout):
        return Resposta(json.dumps({"hourly": {"time": ["2026-11-09T00:00"], "precipitation": [None]}}).encode())
    with pytest.raises(ValueError):
        ch.baixar(0, 0, vazio)


def test_a_failed_refresh_serves_the_last_good_series_flagged_as_stale():
    tempo = {"t": 0.0}
    estado = {"falha": False}

    def fonte(lat, lon):
        if estado["falha"]:
            raise urllib.error.URLError("sem rede")
        return ch.baixar(lat, lon, opener_com())
    c = ch.ChuvaHoraria(-30, -51, ttl_s=100, fonte=fonte, relogio=lambda: tempo["t"])
    serie, meta = c.obter()
    assert "obsoleta" not in meta
    estado["falha"], tempo["t"] = True, 500.0
    serie2, meta2 = c.obter()
    assert meta2["obsoleta"] is True and meta2["motivo_obsolescencia"] == "URLError" and len(serie2) == len(serie)


def test_with_no_series_at_all_the_failure_is_explicit():
    def fonte(lat, lon):
        raise urllib.error.URLError("sem rede")
    with pytest.raises(ch.ChuvaIndisponivel):
        ch.ChuvaHoraria(0, 0, fonte=fonte).obter()


def test_the_series_is_cached_within_the_ttl():
    n = {"v": 0}

    def fonte(lat, lon):
        n["v"] += 1
        return ch.baixar(lat, lon, opener_com())
    c = ch.ChuvaHoraria(0, 0, ttl_s=100, fonte=fonte, relogio=lambda: 1.0)
    c.obter(), c.obter(), c.obter()
    assert n["v"] == 1
