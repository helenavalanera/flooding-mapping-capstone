"""Recorte municipal: os números por trecho valem só para as ruas dentro de Porto Alegre, e o método reproduz o que já estava publicado quando o recorte é desligado."""
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
R = json.loads((RAIZ / "src/flooding_mapping/app/static/data/recorte_municipal_poa.json").read_text(encoding="utf-8"))
F3 = RAIZ / "reports/qa/fase3_execucao.json"


def test_the_cut_splits_the_street_network_and_removes_the_neighbouring_cities():
    assert R["trechos_na_malha"] == 176836 and R["trechos_no_municipio"] + R["trechos_fora_do_municipio"] == R["trechos_na_malha"]
    assert R["trechos_fora_do_municipio"] > 30000 and R["no_municipio"]["trechos"] == R["trechos_no_municipio"] == 143149
    n = R["no_municipio"]
    assert n["com_dados"] + n["sem_dado"] == n["trechos"] and n["preenchimento"]["zero"] + n["preenchimento"]["positivo"] == n["preenchimento"]["com_valor"]


@pytest.mark.skipif(not F3.exists(), reason="falta reports/qa/fase3_execucao.json")
def test_without_the_cut_the_method_reproduces_the_published_phase_3_numbers():
    d = json.loads(F3.read_text(encoding="utf-8"))["descricao"]
    s = R["sem_recorte"]
    assert s["com_dados"] == d["nivel1"]["trechos_com_valor"] and s["preenchimento"]["zero"] == d["nivel1"]["trechos_com_preenchimento_zero"]
    assert s["montante_coberta_m1_mediana"] == round(d["fracoes_a_montante_medianas"]["fracao_montante_coberta_m1"], 4)
    q = d["nivel2_p30"]["metodo1"]["contrib_potencial_max_m3"]
    assert [s["contrib_m1_max_30mm_m3"][k] for k in ("q50", "q90", "q99")] == [round(q[k], 1) for k in ("q50", "q90", "q99")]


def test_the_streets_outside_the_municipality_were_inflating_the_drainage_and_missing_data_figures():
    assert R["sem_recorte"]["sem_dado"] > 40 * R["no_municipio"]["sem_dado"]                      # quase todo "sem dado" era de fora
    antes, depois = R["sem_recorte"]["boca_de_lobo_ate_50m_por_quintil_de_contribuicao_pct"], R["no_municipio"]["boca_de_lobo_ate_50m_por_quintil_de_contribuicao_pct"]
    assert antes[0] < 5 < depois[0] and depois == sorted(depois)                                  # o quintil inferior parecia ter 2% de bocas de lobo por causa das vias de fora
