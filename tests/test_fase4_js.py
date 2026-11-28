"""Fase 4: lógica e textos da camada de escoamento potencial (fase3-dados.js e o painel do trecho de fase3.js), em Node, sem navegador."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).parent.parent / "src/flooding_mapping/app/static"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not installed")

PRELUDIO = f"""
const D = require({json.dumps(str(STATIC / "fase3-dados.js"))});
global.window = {{ Fase3Dados: D, Logic: require({json.dumps(str(STATIC / "logic.js"))}) }};
global.document = {{ getElementById: () => null, activeElement: null }};
global.location = {{ href: "http://x/y/" }};
global.fetch = () => Promise.reject(new Error("sem rede"));
require({json.dumps(str(STATIC / "config-dados.js"))});
require({json.dumps(str(STATIC / "fase3.js"))});
const F = window.Fase3;
F.meta = {{ precipitacoes_mm: [10, 30, 60], zoom: [13, 15], trechos: 176836, tamanho_do_fragmento: 1024 }};
const LINHA = {{ id: "a:b:c", nome: "Rua Exemplo", via: "residential", n_cel: 4, n_cheg: 2,
  l_m1_min: 100, l_m1_max: 200, l_li_min: 0, l_li_max: 800, l_an_min: 50, l_an_max: 400,
  c_m1_min: 1000, c_m1_max: 2000, c_li_min: 0, c_li_max: 9000, c_an_min: 500, c_an_max: 4000,
  area_montante_m2: 12600, f_m1: 0.3, f_li: 0.5, f_an: 0.4, f_an_sem: 0.1, f_fora: 0, f_sem_classe: 0,
  topo_altura_max_m: 0, topo_altura_media_m: 0, topo_posto: 38.79 }};
"""


def run(expressao):
    r = subprocess.run([node, "-e", PRELUDIO + f"console.log(JSON.stringify({expressao}))"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout)


def test_volume_conversion_is_p_times_area_over_1000_and_absence_stays_absence():
    assert run("D.volumeM3(1000, 30)") == 30 and run("D.volumeM3(0, 60)") == 0       # zero é zero
    assert run("D.volumeM3(null, 30)") is None and run("D.volumeM3(NaN, 30)") is None
    assert run("D.volumeM3(22546.35, 10)") == pytest.approx(225.4635, rel=1e-12)
    assert run("D.volumeM3(7, 60) / D.volumeM3(7, 30)") == pytest.approx(2.0, rel=1e-12)   # proporcionalidade exata


def test_formatting_changes_how_a_value_is_shown_never_the_value():
    assert run("D.formatar(null)") is None and run("D.formatar(0)") == "0"
    assert run("D.formatar(1234567)") == "1.230.000" and run("D.formatar(0.225)") == "0,225" and run("D.formatar(3.14159)") == "3,14"
    for v in (0.0123, 4.56, 98765.4, 2.5e7, 0.00099):
        t = run(f"D.formatar({v})")
        assert "e" not in t.lower() and abs(float(t.replace(".", "").replace(",", ".")) - v) / v < 0.006, (v, t)
    assert run("D.volume(null)") == "sem dados" and run("D.volume(0)") == "0 m³"          # ausente não aparece como 0 m³
    assert run("D.area(null)") == "sem dados" and run("D.area(900)") == "900 m²" and run("D.area(250000)") == "25 ha"
    assert run("D.pct(null)") == "sem dados" and run("D.pct(0)") == "0%" and run("D.pct(0.3)") == "30%" and run("D.pct(0.004)") == "<1%"


def test_interval_needs_both_ends_and_scales_with_the_rainfall():
    assert run("D.intervalo(1000, 2000, 30)")["min"] == 30 and run("D.intervalo(1000, 2000, 30)")["max"] == 60
    assert run("D.intervalo(null, 2000, 30)") is None and run("D.intervalo(1000, null, 30)") is None


def test_legend_ranges_follow_the_cuts_and_the_rainfall():
    cortes = [100, 200, 300, 400, 500]
    assert run(f"D.rotuloDaFaixa(D.faixaDaClasse({cortes}, 1, 30))") == "até 3 m³"
    assert run(f"D.rotuloDaFaixa(D.faixaDaClasse({cortes}, 3, 60))") == "12 a 18 m³"
    assert run(f"D.rotuloDaFaixa(D.faixaDaClasse({cortes}, 6, 10))") == "mais de 5 m³"


def test_map_colour_expression_has_a_distinct_colour_for_no_data_and_one_scale_per_quantity():
    e = run('D.expressaoDeCor("c_m1_max", D.PALETAS.c)')
    assert e[:2] == ["match", ["get", "c_m1_max"]] and e[-1] == run("D.COR_SEM_DADOS") and run("D.COR_SEM_DADOS") not in run("D.PALETAS.c")
    paletas = run("D.PALETAS")
    assert len({tuple(p[1:]) for p in paletas.values()}) == 4 and not set(paletas["c"][1:]) & set(paletas["l"][1:]) & set(paletas["tp"][1:])   # a mesma cor nunca vale duas grandezas
    assert run('D.propriedadeDoModo("c", "an", "min")') == "c_an_min" and run('D.propriedadeDoModo("tp", "an", "min")') == "tp" and run('D.propriedadeDoModo("cb", "li", "max")') == "cb_li"


def test_a_row_is_read_by_column_name_from_its_fragment():
    frag = {"colunas": ["id", "x"], "primeiro_n": 2048, "linhas": [["a", 1], ["b", None]]}
    assert run(f"D.linhaDoFragmento({json.dumps(frag)}, 2049)") == {"id": "b", "x": None}
    assert run(f"D.linhaDoFragmento({json.dumps(frag)}, 2050)") is None
    assert run("D.indiceDoFragmento(2049, 1024)") == 2 and run("D.nomeDoFragmento(2)") == "0002.json"


def painel(modo="c", pacote="m1", limite="max", p=30, linha="LINHA"):
    return run(f'(F.estado.modo = "{modo}", F.estado.pacote = "{pacote}", F.estado.limite = "{limite}", F.estado.p = {p}, F.corpoDoTrecho({linha}))')


def test_the_stretch_panel_shows_street_name_and_four_indicators_with_unit_and_keeps_explanations_secondary():
    h = painel()
    for rotulo in ("Geração", "Concentração", "Topografia", "Drenagem"):
        assert rotulo in h, rotulo
    assert h.count("sel-ind") >= 4 and h.count("<details") == 1 and "<code>a:b:c</code>" in h and "Rua Exemplo" in h and "sel-rua" in h
    assert "<span class='v'>30 a 60</span><span class='u'>m³</span>" in h and "<span class='v'>3 a 6</span><span class='u'>m³</span>" in h      # B: 2000 m² x 30 mm / 1000 = 60 m³; A idem
    assert "12.600 m²" in h and "30%" in h and "Não somar com outros trechos" in h                      # área e cobertura ficam no detalhe secundário
    for rotulo in ("Contribuição potencial estimada associada ao trecho", "Volume potencial gerado localmente", "Indicador topográfico de retenção"):
        assert rotulo in h.split("<details")[1], rotulo
    assert "title='Sem dado'>—</span>" in h and "Sem dado</span>" not in h and "estimados, não observados" in h                                  # D: nenhuma associação inventada entre trecho e drenagem
    assert "transportado" not in h.lower()                                  # a tela nunca apresenta (nem cita) volume efetivamente transportado como indicador


def test_the_panel_follows_the_selected_package_and_never_mixes_them():
    m1, an, li = painel(pacote="m1"), painel(pacote="an"), painel(pacote="li")
    assert "<span class='v'>30 a 60</span>" in m1 and "<span class='v'>15 a 120</span>" in an and "<span class='v'>0 a 270</span>" in li      # c_an 500..4000 e c_li 0..9000 x 30/1000
    assert "Método 1" in m1 and "Método 2" in an and "Limites físicos" in li and "limite matemático" in li and "limite matemático" not in m1
    assert "Método 2" not in m1


def test_the_rainfall_changes_the_volumes_by_the_same_factor():
    assert "<span class='v'>30 a 60</span>" in painel(p=30) and "<span class='v'>10 a 20</span>" in painel(p=10) and "<span class='v'>60 a 120</span>" in painel(p=60)


def test_a_stretch_without_data_says_so_and_does_not_show_zero():
    sem = '{"id": "x", "nome": null, "via": null, "n_cel": 0, "n_cheg": 0, "l_m1_max": null, "area_montante_m2": null, "topo_altura_max_m": null}'
    h = painel(linha=sem)
    assert h.count("title='Sem dado'>—</span>") == 4 and "que não é zero" in h and "0 m³" not in h and "Trecho sem nome" in h


def test_zero_is_shown_as_zero_and_is_not_confused_with_no_data():
    zero = run('(F.estado.pacote = "m1", F.corpoDoTrecho(Object.assign({}, LINHA, { l_m1_min: 0, l_m1_max: 0, c_m1_min: 0, c_m1_max: 0 })))')
    assert "<span class='v'>0</span><span class='u'>m³" in zero and zero.count("title='Sem dado'>—</span>") == 1         # só a drenagem segue sem dado


def test_a_low_coverage_marks_the_interval_as_partial_without_showing_percentages():
    assert "m³ · parcial" not in painel()                                                       # f_m1 = 30%: acima do limiar de 25%
    baixa = run('(F.estado.pacote = "m1", F.corpoDoTrecho(Object.assign({}, LINHA, { f_m1: 0.1 })))')
    assert "m³ · parcial" in baixa and "parcial: o intervalo considera só uma parte da área" in baixa
    alta = run('(F.estado.pacote = "m1", F.corpoDoTrecho(Object.assign({}, LINHA, { f_m1: 0.9 })))')
    assert "m³ · parcial" not in alta


def test_the_topographic_indicator_is_a_rank_never_a_depth_or_volume():
    com = run('(F.estado.pacote = "m1", F.corpoDoTrecho(Object.assign({}, LINHA, { topo_altura_max_m: 4.2, topo_posto: 91.5 })))')
    assert "posto 91,5</span><span class='u'>de 100" in com and "não é profundidade" in com.lower() and "grandeza do modelo" in com
    assert "<span class='v'>Sem depressão</span><span class='u'>no modelo" in painel()          # altura zero: não vira posto nem profundidade


def test_every_user_visible_text_avoids_forbidden_words():
    textos = json.dumps(run("F.textos()"), ensure_ascii=False).lower()
    saidas = " ".join(painel(modo, p, l, ch).lower() for modo in ("c", "tp") for p in ("m1", "an", "li") for l in ("min", "max") for ch in (10, 60))
    legendas = " ".join(run(f'(F.meta.cortes_das_classes_aeq_m2 = {{c_m1_max: [1,2,3,4,5], c_an_min: [], l_li_max: [1,2,3,4,5]}}, F.meta.cortes_do_posto_topografico = [85,92,97], F.estado.modo = "{m}", F.estado.pacote = "{pk}", F.estado.limite = "{lm}", F.legenda())').lower()
                        for m, pk, lm in (("c", "m1", "max"), ("c", "an", "min"), ("l", "li", "max"), ("tp", "m1", "max"), ("cb", "an", "max")))
    termos = run("D.TERMOS_PROIBIDOS")
    for termo in termos:
        for nome, texto in (("textos", textos), ("painéis", saidas), ("legendas", legendas)):
            assert termo not in texto, (termo, nome)
    assert len(run("F.textos().metodologia")) == 8                                               # as oito explicações pedidas


def test_legends_keep_one_scale_per_quantity_and_mark_no_data_apart_from_zero():
    base = '(F.meta.cortes_das_classes_aeq_m2 = {c_m1_max: [100,200,300,400,500], l_m1_max: [10,20,30,40,50]}, F.meta.cortes_do_posto_topografico = [85,92,97], '
    c = run(base + 'F.estado.modo = "c", F.estado.pacote = "m1", F.estado.limite = "max", F.estado.p = 30, F.legenda())')
    l = run(base + 'F.estado.modo = "l", F.estado.pacote = "m1", F.estado.limite = "max", F.estado.p = 30, F.legenda())')
    tp = run(base + 'F.estado.modo = "tp", F.legenda())')
    cb = run(base + 'F.estado.modo = "cb", F.estado.pacote = "an", F.legenda())')
    for h in (c, l, tp, cb):
        assert "Trecho sem dados disponíveis (não é valor zero)" in h and "dashed" in h
    assert "Contribuição potencial acumulada" in c and "Geração potencial local" in l and "Indicador topográfico de retenção" in tp and "Cobertura dos dados" in cb
    assert "até 3 m³" in c and "mais de 15 m³" in c and "até 0,3 m³" in l and "Zero (nada escoa neste limite)" in c
    assert "Sem preenchimento de depressão no modelo" in tp and "m³" not in tp and "Posto acima de 97" in tp
    assert "Método 2" in cb and "m³" not in cb
    assert "#253494" in c and "#253494" not in l and "#54278f" in l


def test_data_urls_are_relative_to_the_page_so_the_site_works_under_a_repository_path():
    for href, esperado in (("https://usuario.github.io/flooding-mapping/index.html", "https://usuario.github.io/flooding-mapping/fase3/"),
                           ("https://app.exemplo.com/", "https://app.exemplo.com/fase3/"), ("http://127.0.0.1:8766/?painel=1#mapa", "http://127.0.0.1:8766/fase3/")):
        assert run(f'(global.location.href = {json.dumps(href)}, F.base())') == esperado
    assert run('(global.location.href = "https://u.github.io/r/", F.urlTiles())') == "https://u.github.io/r/fase3/tiles/{z}/{x}/{y}.pbf"


def test_each_quantity_explains_itself_in_the_panel_and_local_generation_differs_from_accumulated_contribution():
    t = run("F.textos().modos")
    assert "soma o escoamento potencial de toda a área a montante" in t["c"] and "sem o que vem de cima" in t["l"] and "grau de confiança" in t["cb"]
    assert "Contribuição acumulada: soma" in t["c"] and "Geração local:" in t["l"]
