"""Simulador de cenários de cálculo: cada número vem da saída do motor, a ordem dos trechos é estável e a linguagem não promete o que o modelo não calcula."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "src/flooding_mapping/app/static"
F3 = ROOT / "data/processed/fase3"
RES = STATIC / "data/resultados_poa.json"
node = shutil.which("node")


def run(expr, P=30):
    pre = f"""
global.window = {{ Logic: require({json.dumps(str(STATIC / "logic.js"))}), scrollY: 0 }};
global.document = {{ getElementById: () => null }};
require({json.dumps(str(STATIC / "resultados.js"))}); require({json.dumps(str(STATIC / "simulador.js"))});
const R = window.Resultados, S = window.Simulador, D = JSON.parse(require("fs").readFileSync({json.dumps(str(RES))}, "utf8")); R.dados = D; R.P = {P};
"""
    r = subprocess.run([node, "-e", pre + f"console.log(JSON.stringify({expr}))"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout)


@pytest.mark.skipif(node is None, reason="node not installed")
@pytest.mark.parametrize("P", [10, 20, 30])
def test_bands_partition_the_streets_with_data(P):
    faixas = run(f"S.faixas(D.cenarios, {P})", P)
    total = json.loads(RES.read_text())["cenarios"]["dados"][str(P)]["trechos_com_dados"]
    assert sum(n for _, n in faixas) == total and all(n >= 0 for _, n in faixas)


@pytest.mark.skipif(node is None, reason="node not installed")
def test_more_rain_moves_streets_out_of_the_lowest_band():
    baixo = [run(f"S.faixas(D.cenarios, {P})")[0][1] for P in (10, 20, 30)]
    assert baixo[0] > baixo[1] > baixo[2]


@pytest.mark.skipif(node is None, reason="node not installed")
def test_the_page_renders_for_every_scenario_with_the_declared_limits():
    for P in (10, 20, 30):
        h = run("S.corpo(D)", P)
        assert "Simulador de cenários de cálculo" in h and f"{P} mm" in h
        assert "Não é um simulador hidráulico" in h and "não calcula profundidade, extensão ou duração" in h
        assert "uniforme e sem distribuição no tempo" in h and "dois dias não equivale a uma chuva de 24 horas" in h
        assert "não se somam" in h and "não some os valores entre trechos" in h
        assert "Série diária modelada (reanálise ERA5, Open-Meteo), não pluviômetros" in h
        assert "Trechos sem dados ficam fora da contagem e não valem zero" in h
        assert f"escoamento=1&p={P}" in h
        assert ("percentil 75 dos totais por evento" in h and "Não é a média histórica" in h) == (P == 30)
        assert "undefined" not in h and "NaN" not in h and "null" not in h


@pytest.mark.skipif(node is None, reason="node not installed")
def test_the_simulator_never_claims_what_the_model_does_not_compute():
    texto = re.sub(r"<[^>]+>", " ", run("S.corpo(D)"))
    for frase in re.split(r"(?<=[.!?])\s+", texto):
        if re.search(r"previs[ãa]o de alagamento|alagamento (previsto|confirmado)|rota segura|vaz[ãa]o m[ée]dia|profundidade de \d", frase, re.I):
            assert re.search(r"\bn[ãa]o\b|nem\b", frase, re.I), frase


@pytest.mark.skipif(node is None, reason="node not installed")
def test_the_territorial_comparison_uses_only_neighbourhoods_with_enough_streets_and_scales_linearly():
    d = json.loads(RES.read_text())
    bs = run("S.bairros(D)")
    assert bs and all(b["suficiente"] for b in bs) and len(bs) < len(d["bairros"])
    v = [run(f"S.contribuicaoMediana({json.dumps(bs[0])}, {P})") for P in (10, 20, 30)]
    assert v[2] == pytest.approx(3 * v[0], rel=1e-9) and v[1] == pytest.approx(2 * v[0], rel=1e-9)


@pytest.mark.skipif(not (F3 / "trechos_nivel2_cenarios.parquet").exists(), reason="dados da Fase 3 ausentes")
def test_simulator_numbers_equal_the_engine_output_and_keep_the_order_of_the_streets():
    import pandas as pd
    d = json.loads(RES.read_text())["cenarios"]["dados"]
    n2 = pd.read_parquet(F3 / "trechos_nivel2_cenarios.parquet")
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from manchas_base import Quadro, carregar_rede
    q = Quadro(carregar_rede())
    n2 = n2[n2["segmento_id"].isin(set(q.ids[q.no_municipio()]))]                         # recorte municipal (docs/recorte_municipal.md): os resultados valem para as ruas dentro de Porto Alegre
    pivot = n2[n2["pacote"] == "metodo1"].pivot(index="segmento_id", columns="p_mm", values="contrib_potencial_max_m3").dropna()
    for P in (10, 20, 30):
        col = pivot[float(P)]
        for lim, n in d[str(P)]["trechos_com_contribuicao_acima_de_m3"].items():
            assert int((col >= float(lim)).sum()) == n, (P, lim)
        assert len(col) == d[str(P)]["trechos_com_dados"]
        assert float(col.quantile(.99)) == pytest.approx(d[str(P)]["por_trecho_m1_max_m3"]["contribuicao"]["p99"], rel=1e-6)
    assert (pivot[30.0] / pivot[10.0].where(pivot[10.0] > 0)).dropna().sub(3).abs().max() < 1e-9
    assert (pivot[20.0] / pivot[10.0].where(pivot[10.0] > 0)).dropna().sub(2).abs().max() < 1e-9
    assert (pivot[10.0].rank() == pivot[30.0].rank()).all() and (pivot[20.0].rank() == pivot[30.0].rank()).all()
