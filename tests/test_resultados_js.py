"""Aba Resultados (resultados.js) em Node: estrutura executiva, escala linear pela chuva, linguagem e ausência de valores quebrados."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).parent.parent / "src/flooding_mapping/app/static"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not installed")
PRELUDIO = f"""
global.window = {{ Logic: require({json.dumps(str(STATIC / "logic.js"))}), scrollY: 0 }};
global.document = {{ getElementById: () => null }};
require({json.dumps(str(STATIC / "resultados.js"))});
const R = window.Resultados, D = JSON.parse(require("fs").readFileSync({json.dumps(str(STATIC / "data/resultados_poa.json"))}, "utf8"));
R.dados = D; R.P = 30;
"""


def run(expr):
    r = subprocess.run([node, "-e", PRELUDIO + f"console.log(JSON.stringify({expr}))"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout)


def test_the_page_is_organised_as_the_executive_brief_asks():
    h = run("R.corpo(D)")
    for t in ("Dada uma precipitação de referência em Porto Alegre, quais contextos territoriais apresentam maior geração potencial de escoamento", "Que chuva o estudo usa como referência?", "Superfícies construídas e pavimentadas", "Vegetação e demais coberturas",
              "Concentração do escoamento e propensão topográfica à retenção", "Drenagem cadastrada", "Cenários de 10, 20 e 30 mm", "O que esses resultados significam para o território?", "Registro de indicadores e rastreabilidade"):
        assert t in h, t
    for rotulo in run("R.textos().rotulos"):
        assert h.count(rotulo) == 9, rotulo                                      # os nove achados respondem as cinco perguntas
    assert h.count("class='rs-achado'") == 9 and "<h3>Indicadores</h3>" not in h and "Análise geral" not in h


def test_every_title_is_the_one_the_data_verified():
    h = run("R.corpo(D)")
    for k in "ABCD":
        for a in run(f"D.dimensoes.{k}.achados"):
            assert a["titulo"] in h.replace("&amp;", "&") or a["titulo"].replace("'", "&#39;") in h, a["id"]
            assert a["verificada"], a["id"]                                       # hoje todos se verificaram; se algum deixar de valer, o título neutro entra pelo gerador


def test_the_rainfall_selector_rescales_by_p_times_aeq_over_1000():
    assert run("R.volume(1000, 30)") == 30 and run("R.volume(1000, 60)") == 60 and run("R.volume(null, 60)") is None and run("R.volume(0, 60)") == 0
    h30, h20 = run("R.corpo(D)"), run("(R.P = 20, R.corpo(D))")
    assert "Volume potencial por hectare, 30 mm" in h30 and "Volume potencial por hectare, 20 mm" in h20 and "Volume potencial por hectare, 20 mm" not in h30
    assert "<button type='button' data-p='20' aria-pressed='true'>" in h20 and "<button type='button' data-p='30' aria-pressed='true'>" in h30


def test_nothing_renders_as_a_broken_value_and_forbidden_wording_only_appears_negated():
    for p in (10, 20, 30):
        h = run(f"(R.P = {p}, R.corpo(D))")
        assert not re.search(r"NaN|undefined|\[object|>null<", h), p
        low = h.lower()
        for t in ("probabilidade de alagamento", "previsão de enchente", "profundidade da água", "volume retido", "rua alagada", "capacidade de retenção", "volume armazenável", "duração do alagamento"):
            for m in re.finditer(re.escape(t), low):
                assert "não" in low[max(0, m.start() - 90):m.start()] or "nem" in low[max(0, m.start() - 90):m.start()], (p, t)


def test_the_neighbourhood_ranking_changes_with_the_metric_and_lists_only_enough_data():
    a = run('(R.metricaBairro = "contribuicao", R.corpo(D))')
    b = run('(R.metricaBairro = "imperm", R.corpo(D))')
    assert a != b and a.count("trechos · cobertura M1") == 10 and "Bairros com ao menos 200 trechos com dados" in a
    nomes = run('D.bairros.filter(b => !b.suficiente).map(b => b.nome)')
    assert nomes and not any(n in a.split("os dez bairros")[1].split("Evidência")[0] for n in nomes)


def test_the_drainage_section_states_context_and_never_claims_function():
    h = run("R.corpo(D)").split("Dimensão D")[1].split("Cenários de 10")[0]
    assert "contexto" in h and "não indica capacidade de vazão" in h.lower().replace("&#39;", "'")
    assert not re.search(r"funcionando|\bem funcionamento|eficiente|entupid", h.lower())
