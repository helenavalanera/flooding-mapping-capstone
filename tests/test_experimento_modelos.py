"""Experimento exploratório: regra de terreno vs. regressão logística, gradient boosting e MLP nos trechos alagados da Prefeitura.

O teste NÃO afirma que um modelo vence: afirma que o experimento é honesto (blocos separados, mesmas amostras, mesma exigência de ganho
da configuração) e registra o resultado. Precisa da tabela de ruas processada, que fica fora do Git: sem ela, é ignorado.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flooding_mapping.risco_trecho import COMPONENTES

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import experimento_modelos_alagamentos as exp  # noqa: E402

REDE = RAIZ / "data/processed/rede_poa.parquet"
from flooding_mapping.dados_restritos import ALAGAMENTOS_PMPA as COORDS, MOTIVO_AUSENTE  # noqa: E402   (dado de terceiros, fora do Git)


def test_a_planted_signal_is_found_and_leakage_is_impossible():
    """Synthetic grid where flooding depends on ONE terrain fact: the learned models must find it, the equal-weight rule must not."""
    rng = np.random.default_rng(1)
    n = 90
    k = np.arange(n * n)
    g = pd.DataFrame({"lon0": (k % n) * 0.006, "lat0": (k // n) * 0.006})
    g["lon1"], g["lat1"] = g.lon0 + 0.0005, g.lat0
    for c in COMPONENTES:
        g[c] = rng.normal(size=len(g))
    g["percentil"] = g[COMPONENTES].mean(axis=1).rank(pct=True) * 100
    alvo = g.index[g[COMPONENTES[0]] > 2.4]
    coords = pd.DataFrame({"lon": g.lon0[alvo] + 0.00025, "lat": g.lat0[alvo]})
    r = exp.rodar(g, coords, raio_m=50)
    assert r["blocos_separados_entre_treino_e_teste"]
    assert r["trechos_rotulados"] >= 30
    m = r["modelos"]
    assert m["regressao_logistica"]["precisao_media"] > 2 * m["regra_de_terreno"]["precisao_media"]
    assert m["gradient_boosting"]["precisao_media"] > m["regra_de_terreno"]["precisao_media"]


@pytest.mark.skipif(not REDE.exists() or not COORDS.exists(), reason="validação com dados reais: falta data/processed/rede_poa.parquet (fora do Git) ou " + MOTIVO_AUSENTE)
def test_exploratory_comparison_on_the_real_flooded_segments(tmp_path):
    coords = pd.read_csv(COORDS)
    assert list(coords.columns) == ["camada", "lon", "lat"]            # só coordenadas: nada de nome ou telefone
    rede = pd.read_parquet(REDE, columns=["lon0", "lat0", "lon1", "lat1", "percentil", *COMPONENTES])
    r = exp.rodar(rede, coords)
    assert r["blocos_separados_entre_treino_e_teste"]
    assert 90 <= r["trechos_rotulados"] <= 130                         # os ~105 trechos da Prefeitura
    m = r["modelos"]
    assert set(m) == {"regra_de_terreno", "regressao_logistica", "gradient_boosting", "mlp"}
    assert 0.60 <= m["regra_de_terreno"]["auc"] <= 0.75                # confere com reports/qa/terreno_alagamentos_pmpa.json (0,675)
    for nome, v in m.items():
        assert 0.0 <= v["auc"] <= 1.0 and v["precisao_media"] > 0
        lo, hi = v["intervalo_95_precisao_media"]
        assert lo <= hi
        if nome != "regra_de_terreno":
            # a decisão de adoção segue exatamente a regra da configuração, nunca um critério escolhido depois de ver o resultado
            assert v["adotaria"] == (v["precisao_media"] >= m["regra_de_terreno"]["precisao_media"] * (1 + r["margem_exigida"]))
