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
        return Resposta(json.dumps({"timezone": "America/Sao_Paulo", "hourly_units": {"precipitation": "mm"}, "hourly": {"time": tempos, "precipitation": [mm] * horas}}).encode())
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
    assert meta["obsoleta"] is False and meta["idade_min"] == 0
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


def fonte_que_cai(estado):
    def fonte(lat, lon):
        if estado["falha"]:
            raise urllib.error.URLError("sem rede")
        return ch.baixar(lat, lon, opener_com())
    return fonte


def test_a_series_older_than_the_validity_is_unavailable_and_says_when_it_was_last_updated():
    t, estado = {"v": 0.0}, {"falha": False}
    c = ch.ChuvaHoraria(0, 0, ttl_s=100, validade_max_s=3600, fonte=fonte_que_cai(estado), relogio=lambda: t["v"])
    _, meta0 = c.obter()
    estado["falha"], t["v"] = True, 1800.0                                  # stale but still inside the validity
    serie, meta = c.obter()
    assert meta["obsoleta"] is True and meta["idade_min"] == 30 and meta["emitido_em_utc"] == meta0["emitido_em_utc"] and len(serie) > 0
    t["v"] = 3601.0                                                         # past the validity: never presented as current
    with pytest.raises(ch.ChuvaIndisponivel) as erro:
        c.obter()
    assert erro.value.ultima_atualizacao == meta0["emitido_em_utc"] and "desatualizados" in str(erro.value)
    estado["falha"], t["v"] = False, 3700.0                                 # the service recovers: fresh again
    assert c.obter()[1]["obsoleta"] is False


def test_a_failed_refresh_is_not_retried_on_every_request():
    t, estado, tentativas = {"v": 0.0}, {"falha": False}, {"n": 0}
    base = fonte_que_cai(estado)

    def fonte(lat, lon):
        tentativas["n"] += 1
        return base(lat, lon)
    c = ch.ChuvaHoraria(0, 0, ttl_s=100, fonte=fonte, relogio=lambda: t["v"])
    c.obter()
    estado["falha"], t["v"] = True, 150.0
    for _ in range(5):
        c.obter()
    assert tentativas["n"] == 2                                             # the first download and one failed refresh, not six


def test_the_unit_and_the_time_zone_are_checked_before_the_series_is_used():
    def opener(unidade="mm", fuso="America/Sao_Paulo"):
        def f(req, timeout):
            return Resposta(json.dumps({"timezone": fuso, "hourly_units": {"precipitation": unidade},
                                        "hourly": {"time": ["2026-11-09T00:00"], "precipitation": [1.0]}}).encode())
        return f
    assert ch.baixar(0, 0, opener())[0].iloc[0] == 1.0
    with pytest.raises(ValueError, match="unidade"):
        ch.baixar(0, 0, opener(unidade="inch"))
    with pytest.raises(ValueError, match="fuso"):
        ch.baixar(0, 0, opener(fuso="UTC"))


def test_what_each_hour_is_stated_in_the_metadata():
    _, meta = ch.baixar(0, 0, opener_com())
    assert meta["unidade"] == "mm" and meta["fuso"] == "America/Sao_Paulo" and meta["resolucao_temporal"] == "horária"
    assert "não é medição de pluviômetro" in meta["horas_passadas"] and "previsão" in meta["horas_futuras"] and "não medição neste trecho" in meta["resolucao_espacial"]
