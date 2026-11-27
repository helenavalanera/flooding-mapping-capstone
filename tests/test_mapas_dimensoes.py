"""Mapas de manchas das dimensões A, B e D: números, imagens, legendas em unidade própria e lacunas. Só resultados que já existem; nada de índice composto."""
import json
import re
import sys
from pathlib import Path

import pytest
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ST = RAIZ / "src/flooding_mapping/app/static"
J = json.loads((ST / "data/mapa_dimensoes_poa.json").read_text(encoding="utf-8"))
FASE3 = RAIZ / "data/processed/fase3/trechos_nivel2_cenarios.parquet"
DIMS = [d for d in "ABDE" if d in J]


def lum(c):
    return sum(int(c[i:i + 2], 16) * w for i, w in ((1, .299), (3, .587), (5, .114)))


@pytest.mark.parametrize("d", DIMS)
def test_each_image_is_a_light_webp_with_the_recorded_size_and_a_darker_scale_for_higher_values(d):
    im = J[d]["imagem"]
    f = ST / "inicio" / im["arquivo"]
    assert Image.open(f).format == "WEBP" and Image.open(f).size == (im["largura_px"], im["altura_px"]) and f.stat().st_size == im["bytes"] < 400_000
    cores = [x["cor"] for x in J[d]["faixas"]]
    assert [lum(c) for c in cores] == sorted((lum(c) for c in cores), reverse=True) and len(set(cores)) == len(cores)


def test_the_four_maps_use_distinct_palettes_and_the_same_framing():
    paletas = [tuple(x["cor"] for x in J[d]["faixas"]) for d in DIMS] + [tuple(x["cor"] for x in json.loads((ST / "data/mapa_manchas_poa.json").read_text(encoding="utf-8"))["faixas_m"])]
    assert len(set(paletas)) == len(paletas) and not set.intersection(*map(set, paletas))
    tamanhos = {(J[d]["imagem"]["largura_px"], J[d]["imagem"]["altura_px"]) for d in DIMS} | {(1400, 1722)}
    assert len(tamanhos) == 1                                                                         # mesma grade e mesmo enquadramento: trocar de dimensão não desloca o mapa


@pytest.mark.parametrize("d", [x for x in "AB" if x in J])
def test_a_and_b_state_the_unit_the_gaps_and_the_numbers_add_up(d):
    r = J[d]
    assert r["trechos_total"] == 143149 and r["trechos_total"] + r["trechos_fora_do_municipio"] == r["trechos_na_malha"] == 176836 and r["trechos_com_dado"] + r["trechos_sem_dado"] == r["trechos_total"] and r["trechos_sem_dado"] == 68
    assert r["zero_com_hipotese_metodo2"] + r["zero_sem_classe_com_coeficiente_nem_hipotese"] == r["trechos_com_valor_zero"]            # zero separado de ausência de dado (68) e subdividido
    assert r["trechos_com_valor_positivo"] + r["trechos_com_valor_zero"] == r["trechos_com_dado"]
    assert sum(f["trechos"] for f in r["faixas"]) == r["trechos_com_valor_positivo"]
    assert "m³" in r["unidade"] and r["chuva_mm"] == 30 and all("m³" in f["rotulo"] for f in r["faixas"])
    assert r["mediana_m3"] < r["p90_m3"] < r["p99_m3"] and r["area_com_coeficiente_fundamentado_pct"] == 17.3
    assert all("construido_pct" in i for i in r["bairros"]["itens"])
    itens = r["bairros"]["itens"]
    assert len(itens) == 5 and [i["valor"] for i in itens] == sorted((i["valor"] for i in itens), reverse=True) and r["bairros"]["bairros_sem_estimativa"] == 2 and "200 trechos" in r["bairros"]["universo"]


def test_the_neighbourhood_figures_come_from_the_committed_results():
    res = json.loads((ST / "data/resultados_poa.json").read_text(encoding="utf-8"))["bairros"]
    nomes_ok = {b["nome"] for b in res if b["suficiente"]}
    for d in [x for x in "AB" if x in J]:
        assert {i["bairro"] for i in J[d]["bairros"]["itens"]} <= nomes_ok
    b = {x["nome"]: x for x in res}
    assert J["A"]["bairros"]["itens"][0]["valor"] == round(b[J["A"]["bairros"]["itens"][0]["bairro"]]["geracao_m1_max_aeq_por_ha"] * 0.03, 1)


@pytest.mark.skipif(not FASE3.exists(), reason="falta data/processed/fase3 (fora do Git)")
def test_a_and_b_are_recomputed_from_the_phase_3_results():
    sys.path.insert(0, str(RAIZ / "tools"))
    from gerar_mapas_dimensoes import base_30mm
    from manchas_base import Quadro, carregar_rede
    q = Quadro(carregar_rede())
    d = base_30mm()
    d = d[d["segmento_id"].isin(set(q.ids[q.no_municipio()]))]
    for dim, col in (("A", "v_gerado_local_max_m3"), ("B", "contrib_potencial_max_m3")):
        v = d[col]
        assert (J[dim]["trechos_sem_dado"], J[dim]["trechos_com_valor_positivo"], J[dim]["trechos_com_valor_zero"]) == (int(v.isna().sum()), int((v > 0).sum()), int((v == 0).sum()))
        assert J[dim]["mediana_m3"] == round(float(v[v > 0].median()), 1)


def test_the_generator_makes_no_composite_index_and_no_ranking_across_dimensions():
    fonte = (RAIZ / "tools/gerar_mapas_dimensoes.py").read_text(encoding="utf-8")
    codigo = re.sub(r'""".*?"""', "", fonte, count=1, flags=re.S)
    for proibido in ("alagamentos", "events.csv", "indice_composto", "score", "risco"):
        assert proibido not in codigo.lower(), proibido
    assert "valores de dimensões diferentes não se comparam" in fonte


def test_d_is_a_record_of_the_registry_with_its_gaps_stated():
    r = J["D"]
    assert "metros de rede" in r["unidade"] and "não funcionamento" in r["natureza"] and sum(f["celulas"] for f in r["faixas"]) == r["celulas_com_rede"]
    assert r["rede_trechos"] == 135779 and r["rede_km"] == 2961 and r["bocas_de_lobo"] == 44761 and r["pocos_de_visita"] == 88860
    assert r["trechos_de_rua_em_celula_com_rede"] < r["trechos_de_rua_total"] == 143149 and r["trechos_de_rua_em_celula_com_rede_pct"] == 70.3     # ruas sem rede cadastrada: lacuna do cadastro, não prova de ausência
    assert r["campos_sem_preenchimento_pct"]["material"] > 90 and r["mediana_m_por_celula"] < r["p90_m_por_celula"]
    assert r["perto_de_boca_de_lobo_por_quintil_de_concentracao_pct"] == {"menor": 26, "maior": 73}
    assert len(r["bairros"]["itens"]) == 5 and r["bairros"]["bairros_sem_estimativa"] == 2


def test_d_gap_and_quintile_figures_come_from_the_municipal_cut():
    rec = json.loads((ST / "data/recorte_municipal_poa.json").read_text(encoding="utf-8"))["no_municipio"]["boca_de_lobo_ate_50m_por_quintil_de_contribuicao_pct"]
    assert J["D"]["perto_de_boca_de_lobo_por_quintil_de_concentracao_pct"] == {"menor": round(rec[0]), "maior": round(rec[-1])}


def test_d_numbers_match_the_committed_results():
    res = json.loads((ST / "data/resultados_poa.json").read_text(encoding="utf-8"))
    ind = {i["id"]: i["valor"] for i in res["indicadores"]}
    assert J["D"]["bocas_de_lobo"] == ind["D-pontos"]["bocas"] and J["D"]["rede_trechos"] == sum(v["trechos"] for v in ind["D-rede"].values())
    pb = res["dimensoes"]["D"]["dados"]["por_bairro"]
    assert all(round(pb[i["bairro"]]["rede_km_por_km2"], 1) == i["valor"] for i in J["D"]["bairros"]["itens"])


def test_e_is_experimental_independent_of_the_engine_and_states_its_limits_and_gaps():
    e = J["E"]
    assert "EXPERIMENTAL" in e["natureza"] and "independente das dimensões A a D" in e["natureza"] and "fração" in e["unidade"]
    assert sum(f["celulas_pct"] for f in e["faixas"]) == pytest.approx(100, abs=0.3) and len(e["faixas"]) == 5
    assert e["resultados"] == {"mae_blocos_3km": 0.049, "mae_quadrante_externo": 0.052, "bairros_dentro_do_limite_pct": 57.4}
    assert 0 < e["celulas_sem_rotulo_pct"] < 100 and e["celulas_no_municipio"] > 500000 and len(e["bairros"]["itens"]) == 5
    codigo = re.sub(r'""".*?"""', "", (RAIZ / "tools/gerar_mapas_dimensoes.py").read_text(encoding="utf-8"), count=1, flags=re.S)
    corpo_e = codigo.split("def dimensao_e")[1].split("\ndef main")[0]
    for proibido in ("fase3", "contrib", "nivel2", "trechos_nivel", "trechos_contrib"):
        assert proibido not in corpo_e, proibido                                                            # a camada E não lê o motor
