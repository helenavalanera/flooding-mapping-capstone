import json

import pandas as pd
import pytest
from rede_sintetica import PR

from flooding_mapping import auditoria_risco as au


def rede():
    return pd.DataFrame({"comprimento_m": [1000.0, 1000.0, 2000.0, 500.0], "percentil": [99.0, None, 90.0, None],
                         "drive": [True, True, False, False], "walk": [True, True, True, False]})


def test_coverage_is_by_length_and_a_footway_without_index_counts_as_uncovered():
    c = au.cobertura(rede())
    assert c["dirigivel"] == {"km": 2.0, "fracao_com_indice": 0.5}
    assert c["somente_a_pe"] == {"km": 2.0, "fracao_com_indice": 1.0} and c["nenhum_modal"]["fracao_com_indice"] == 0.0
    assert c["caminhavel"]["fracao_com_indice"] == pytest.approx(3 / 4)


def test_flagged_share_grows_with_the_rain_factor_and_ignores_segments_without_index():
    r = pd.DataFrame({"comprimento_m": [1000.0] * 4, "percentil": [100.0, 95.0, 50.0, None]})
    f = au.fracao_sinalizada(r, PR)
    assert f["0.4"]["alto"] == 0 and f["1.0"]["alto"] > 0 and f["1.0"]["atencao"] + f["1.0"]["alto"] >= f["0.4"]["atencao"]
    assert f["1.0"]["alto"] + f["1.0"]["atencao"] <= 2 / 3 + 1e-3   # the missing segment is not in the denominator; the mid one is never flagged


def test_the_event_check_reads_hourly_rain_and_reports_both_factors():
    def buscar(url, params):
        dias = pd.date_range(params["start_date"], pd.Timestamp(params["end_date"]) + pd.Timedelta(hours=23), freq="h")
        chuva = [20.0 if d.date().isoformat() == params["end_date"] and 10 <= d.hour <= 12 else 0.0 for d in dias]
        return {"hourly": {"time": [d.strftime("%Y-%m-%dT%H:%M") for d in dias], "precipitation": chuva}}, {}
    linhas = au.fator_nos_eventos(PR, buscar)
    assert [x["data"] for x in linhas] == list(au.EVENTOS) and all(x["fator_com_recuo"] <= x["fator_sem_recuo"] for x in linhas)
    tarde = next(x for x in linhas if x["hora_do_reporte"] == 21)   # reported 9 h after the rain stopped
    assert tarde["horas_secas_antes_do_reporte"] == 9 and tarde["fator_com_recuo"] == 0.0 and tarde["fator_sem_recuo"] > 0
    json.dumps(linhas)
