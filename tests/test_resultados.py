"""Resultados executivos (aba Resultados): indicadores rastreáveis, afirmações verificadas, nada somado entre trechos, linguagem dentro do que o estudo demonstra."""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flooding_mapping import resultados as r

RAIZ = Path(__file__).parent.parent
JSON = RAIZ / "src/flooding_mapping/app/static/data/resultados_poa.json"
real = pytest.mark.skipif(not ((RAIZ / "data/processed/fase3/celulas_30m.parquet").exists() and (RAIZ / "data/raw/weather/archive").exists() and (RAIZ / "data/processed/drenagem").exists()),
                          reason="dados derivados do estudo não disponíveis neste ambiente")


@pytest.fixture(scope="module")
def d():
    return json.loads(JSON.read_text())


# ------------------------------------------------------------------------------------------------ sintéticos
def test_events_are_runs_of_rainy_days_and_the_total_is_their_sum():
    s = pd.Series([0, 2, 3, 0, 0, 10, 0, 1, 0.5, 4], index=pd.date_range("2020-01-01", periods=10), dtype=float)
    ev = r.eventos(s)
    assert list(ev["total_mm"]) == [5.0, 10.0, 5.0] and list(ev["dias"]) == [2, 1, 1 + 0] or list(ev["total_mm"]) == [5.0, 10.0, 1.0, 4.0]
    assert float(ev["total_mm"].sum()) == float(s[s >= 1].sum())                              # nenhum milímetro some nem se repete


def test_a_claim_that_is_not_verified_falls_back_to_the_neutral_title():
    a = r.afirmacao("X", False, "Título conclusivo", "Título neutro", {}, "o", "e", "c", "r", "l")
    b = r.afirmacao("X", True, "Título conclusivo", "Título neutro", {}, "o", "e", "c", "r", "l")
    assert a["titulo"] == "Título neutro" and b["titulo"] == "Título conclusivo" and a["verificada"] is False


def test_an_indicator_without_traceability_fields_is_refused():
    with pytest.raises(ValueError, match="sem"):
        r.indicador(id="x", dimensao="A", titulo="t", valor=1, unidade="u")
    ok = r.indicador(id="x", dimensao="A", titulo="t", valor=1, unidade="u", formula="f", fonte="s", cenario="c", metodo="m", cobertura="k", limitacoes="l")
    assert set(ok) == {"id", "dimensao", "titulo", "valor", "unidade", "formula", "fonte", "cenario", "metodo", "cobertura", "limitacoes"}


def test_the_code_never_sums_a_contribution_or_a_local_value_across_stretches():
    codigo = (RAIZ / "src/flooding_mapping/resultados.py").read_text(encoding="utf-8")
    assert not re.search(r"(contrib_aeq|local_aeq)\w*\"\]\s*\.sum\(", codigo)                    # por trecho só quantis, razões e contagens
    assert "camada_drenagem" in codigo and "motor_acumulo" not in codigo                      # a drenagem é contexto: o motor não a importa e o resultado não o importa


# ------------------------------------------------------------------------------------------------ o arquivo gerado
def test_every_indicator_has_formula_unit_source_scenario_method_coverage_and_limitations(d):
    campos = ("id", "dimensao", "titulo", "valor", "unidade", "formula", "fonte", "cenario", "metodo", "cobertura", "limitacoes")
    ids = [i["id"] for i in d["indicadores"]]
    assert len(ids) == len(set(ids)) >= 12 and {i["dimensao"] for i in d["indicadores"]} == {"A", "B", "C", "D", "S"}
    for i in d["indicadores"]:
        assert all(i[c] not in (None, "") for c in campos), i["id"]


def test_each_finding_answers_the_five_questions_and_has_a_conclusive_title_only_if_verified(d):
    achados = [a for k in "ABCD" for a in d["dimensoes"][k]["achados"]] + d["cenarios"]["achados"]
    assert len(achados) == 9 and {a["id"] for a in achados} == {"A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "S1"}
    genericos = re.compile(r"^(indicadores|análise|resultados gerais|resultados)\b", re.I)
    for a in achados:
        assert all(len(a[c]) > 30 for c in ("observado", "estimado", "contexto", "relevancia", "limitacao")), a["id"]
        assert a["titulo"] == (a["titulo_conclusivo_se_verificada"] if a["verificada"] else a["titulo_neutro"]) and len(a["titulo"]) > 40 and not genericos.match(a["titulo"]), a["id"]
        assert not a["verificada"] or a["titulo"] == a["titulo_conclusivo_se_verificada"]


def test_the_executive_texts_stay_inside_what_was_calculated(d):
    texto = json.dumps(d, ensure_ascii=False).lower()
    proibidos = ("probabilidade de alagamento", "previsão de enchente", "profundidade prevista", "profundidade da água", "volume retido", "volume acumulado", "rua alagada", "ponto de alagamento confirmado", "capacidade de retenção", "volume armazenável", "duração do alagamento")
    for t in proibidos:
        for m in re.finditer(re.escape(t), texto):
            assert "não" in texto[max(0, m.start() - 80):m.start()] or "nem" in texto[max(0, m.start() - 80):m.start()], t            # só aparece negado
    for a in d["dimensoes"]["D"]["achados"]:
        for c in ("observado", "estimado", "contexto", "relevancia", "limitacao", "titulo"):
            assert not re.search(r"funcionando|\bem funcionamento|eficiente|entupid|obstruíd|conectad[oa]s? hidraulicamente", a[c].lower()), (a["id"], c)
    assert "não indica capacidade de vazão" in d["dimensoes"]["D"]["achados"][0]["limitacao"].lower()


def test_30_mm_is_documented_as_an_illustrative_scenario_and_never_as_the_historical_mean(d):
    c = d["chuva"]
    assert d["precipitacao_de_referencia_mm"] == 30 and "Não é a média histórica" in c["leitura_da_referencia"] and "ilustrativo" in c["leitura_da_referencia"]
    assert c["fonte"] and c["periodo"] and c["tratamento"] and "modelada" in c["natureza"] and c["total_por_evento_mm"]["media"] != 30
    assert set(c["cenarios_na_distribuicao"]) == {"10", "20", "30"}


def test_the_priority_contexts_are_hypotheses_ranked_without_summing_and_with_enough_stretches(d):
    s = d["sintese"]["contextos_prioritarios_hipoteses"]
    assert "nada somado entre trechos" in s["criterio"]
    for lista in ("por_contribuicao_mediana", "por_geracao_potencial_por_hectare_analogia", "por_parcela_no_decil_superior"):
        assert len(s[lista]) == 5 and all(b["suficiente"] and b["trechos_com_dados"] >= r.MINIMO_DE_TRECHOS_POR_BAIRRO for b in s[lista]), lista
    assert len(d["sintese"]["para_uma_analise_hidraulica"]) >= 5 and "trechos_sem_dados" in d["sintese"]["lacunas_de_dados"]


# ------------------------------------------------------------------------------------------------ contra os dados reais
@real
def test_the_rain_statistics_are_recomputed_from_the_cached_series(d):
    s = r.serie_diaria(RAIZ / "data/raw/weather/archive")
    ev = r.eventos(s)
    c = d["chuva"]
    assert c["dias"] == len(s) and c["eventos"] == len(ev) and c["total_por_evento_mm"]["p75"] == pytest.approx(float(np.quantile(ev["total_mm"], .75)))
    assert c["media_diaria_todos_os_dias_mm"] == pytest.approx(float(s.mean())) and c["media_por_dia_com_chuva_mm"] == pytest.approx(float(s[s >= 1].mean()))
    assert c["media_diaria_todos_os_dias_mm"] < c["total_por_evento_mm"]["media"]            # as médias medem coisas diferentes e não se confundem
    assert c["cenarios_na_distribuicao"]["30"]["percentil_do_total_por_evento"] == pytest.approx(float((ev["total_mm"] < 30).mean()))


@real
def test_the_package_totals_equal_the_cell_sums_the_engine_report_and_scale_linearly(d):
    cel = pd.read_parquet(RAIZ / "data/processed/fase3/celulas_30m.parquet")
    rel = json.loads((RAIZ / "reports/qa/fase3_execucao.json").read_text())["motor"]["totais_da_cidade_soma_das_celulas_m3"]
    t = d["cenarios"]["dados"]
    for p in ("10", "20", "30"):
        for pac, col, nome in (("metodo1", "aeq_m1", "metodo1"), ("analoga", "aeq_analoga", "referencia_analoga"), ("limites", "aeq_limites", "limites_fisicos")):
            for lim in ("min", "max"):
                esperado = float(cel[f"{col}_{lim}"].astype("float64").sum()) * float(p) / 1000
                assert t[p]["geracao_cidade_m3"][pac][lim] == pytest.approx(esperado, rel=1e-9)
                assert t[p]["geracao_cidade_m3"][pac][lim] == pytest.approx(rel[p][nome][f"{lim}_m3"], rel=1e-6)         # o mesmo que a execução do motor (as células são guardadas em float32)
    assert t["20"]["geracao_cidade_m3"]["metodo1"]["max"] == pytest.approx(2 * t["10"]["geracao_cidade_m3"]["metodo1"]["max"], rel=1e-12) and t["30"]["geracao_cidade_m3"]["metodo1"]["max"] == pytest.approx(3 * t["10"]["geracao_cidade_m3"]["metodo1"]["max"], rel=1e-12)
    assert t["10"]["trechos_com_contribuicao_acima_de_m3"]["1000"] <= t["20"]["trechos_com_contribuicao_acima_de_m3"]["1000"] <= t["30"]["trechos_com_contribuicao_acima_de_m3"]["1000"]


@real
def test_the_trecho_quantiles_and_counts_match_the_parquets(d):
    import sys
    sys.path.insert(0, str(RAIZ / "tools"))
    from manchas_base import Quadro, carregar_rede
    base = pd.read_parquet(RAIZ / "data/processed/fase3/trechos_contribuicao_base.parquet")
    q_ = Quadro(carregar_rede())
    base = base[base["segmento_id"].isin(set(q_.ids[q_.no_municipio()]))]                 # recorte municipal (docs/recorte_municipal.md)
    v = base["contrib_aeq_m1_max_m2"].dropna()
    q = d["dimensoes"]["C"]["dados"]["quantis_contribuicao_aeq"]
    assert q["p50"] == pytest.approx(float(v.median())) and q["p99"] == pytest.approx(float(v.quantile(.99)))
    assert sum(l["trechos"] for l in d["dimensoes"]["D"]["dados"]["por_quintil"]) == len(v) == 143081
    ev = d["dimensoes"]["C"]["achados"][0]["evidencia"]
    assert ev["razao_p99_p50"] == pytest.approx(float(v.quantile(.99) / v.median()))
    c1 = d["dimensoes"]["C"]["achados"][0]
    assert c1["verificada"] == (ev["razao_p99_p50"] >= 10)
    nao = d["dimensoes"]["C"]["dados"]
    assert nao["quantis_area_m2"]["p50"] == pytest.approx(float(base["area_montante_m2"].dropna().median()))


@real
def test_the_class_areas_and_the_uncertainty_shares_match_the_quality_report(d):
    uso = json.loads((RAIZ / "reports/qa/qualidade_uso_solo_fase2.json").read_text())["classes"]
    cl = d["dimensoes"]["B"]["dados"]["classes"]
    assert {c["classe"] for c in cl} == set(uso) and sum(c["area_km2"] for c in cl) == pytest.approx(sum(v["area_km2"] for v in uso.values()))
    assert sum(c["parcela_da_incerteza_da_analogia"] for c in cl) == pytest.approx(1.0)
    m1 = {c["classe"] for c in cl if c["metodo1"]}
    assert m1 == {"Edificação", "Vias Pavimentadas"}
    b1 = d["dimensoes"]["B"]["achados"][0]
    assert b1["evidencia"]["classe_dominante"] not in m1 and b1["verificada"]


@real
def test_the_imperviousness_bins_partition_the_classified_area_and_the_claim_matches_the_monotonicity(d):
    fx = d["dimensoes"]["A"]["dados"]["faixas"]
    grade = pd.read_parquet(RAIZ / "data/processed/uso_solo/uso_solo_grade30m.parquet", columns=["linha", "coluna", "area_classificada_m2"])
    celulas = pd.read_parquet(RAIZ / "data/processed/fase3/celulas_30m.parquet", columns=["linha", "coluna"])
    comum = grade.merge(celulas, on=["linha", "coluna"])
    assert sum(l["celulas"] for l in fx) == int((comum["area_classificada_m2"] > 0).sum())           # as faixas particionam as células classificadas
    assert sum(l["fracao_da_area_classificada"] for l in fx) == pytest.approx(1.0)
    a1 = d["dimensoes"]["A"]["achados"][0]
    mono = [fx[i]["c_efetivo_metodo1_max"] < fx[i + 1]["c_efetivo_metodo1_max"] for i in range(len(fx) - 1)]
    assert a1["verificada"] == all(mono) and a1["evidencia"]["crescimento_por_faixa"]["analoga_max"] is False       # a analogia não cobre classes impermeáveis e não é monotônica: o título não a inclui
    assert "Método 1" in a1["titulo"] and "analogia" not in a1["titulo"].lower() and "não prova a hipótese" in a1["limitacao"]


@real
def test_the_drainage_relation_is_described_as_found_and_the_title_follows_the_numbers(d):
    q = d["dimensoes"]["D"]["dados"]["por_quintil"]
    bs = [l["com_boca_de_lobo_ate_50m"] for l in q]
    sobe = all(bs[i] < bs[i + 1] for i in range(4)) and bs[-1] - bs[0] >= 0.05
    t = d["dimensoes"]["D"]["achados"][1]["titulo"]
    assert ("Há mais bocas de lobo" in t) == sobe and "capacidade" not in t.lower()
    cat = d["dimensoes"]["D"]["dados"]["rede_por_categoria"]
    assert sum(v["trechos"] for v in cat.values()) == 132986 + 2772 + 21
