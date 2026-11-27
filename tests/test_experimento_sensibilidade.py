"""Experimento de sensibilidade hidrológica (exploratório): a física simplificada acrescenta informação ao índice atual?

Os testes verificam o MÉTODO (a ordem não depende de chuva uniforme, o volume é monótono, o bootstrap concorda com o sklearn, o critério de adoção não
é frouxo) e que o resultado real é registrado sem forçar adoção. Não afirmam que a física vence. Os testes da tabela real precisam de
data/processed/rede_poa.parquet (fora do Git) e são ignorados sem ela.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flooding_mapping.risco_trecho import COMPONENTES

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import experimento_modelos_alagamentos as anterior  # noqa: E402
import experimento_sensibilidade_hidrologica as sens  # noqa: E402

REDE = RAIZ / "data/processed/rede_poa.parquet"
from flooding_mapping.dados_restritos import ALAGAMENTOS_PMPA as COORDS, MOTIVO_AUSENTE  # noqa: E402   (dado de terceiros, fora do Git)
RELATORIO_ANTERIOR = RAIZ / "reports/qa/modelos_exploratorio_alagamentos.json"
RAPIDO = 300


def grade(alvo: str, n=90, seed=1):
    """n x n isolated segments with random terrain facts; ``alvo`` decides what the (planted) flooding follows."""
    rng = np.random.default_rng(seed)
    k = np.arange(n * n)
    corte = n // 3                                   # a dense corner (street density varies), the rest isolated segments
    pos = lambda i: np.where(i < corte, i * 0.0008, corte * 0.0008 + (i - corte) * 0.006)
    g = pd.DataFrame({"lon0": pos(k % n), "lat0": pos(k // n)})
    g["lon1"], g["lat1"] = g.lon0 + 0.0005, g.lat0
    for c in COMPONENTES:
        g[c] = rng.normal(size=len(g))
    g["percentil"] = g[COMPONENTES].mean(axis=1).rank(pct=True) * 100
    g["log_flow_acc"], g["slope"] = rng.uniform(0.7, 9, len(g)), rng.uniform(0.2, 12, len(g))
    b = sens.indice_umidade_topografica(g["log_flow_acc"], g["slope"])
    verdade = b if alvo == "fisica" else rng.normal(size=len(g))
    topo = g.index[verdade > np.quantile(verdade, 0.985)]
    return g, pd.DataFrame({"lon": g.lon0[topo] + 0.00025, "lat": g.lat0[topo]})


def test_physical_index_has_the_documented_form_and_units():
    # A = expm1(lfa)*900 m²: one cell (lfa = ln 2) is 900 m², a = A/30 = 30 m of flow width; on a 45° slope tanβ = 1, so B = ln 30
    assert sens.area_contribuinte_m2(np.log(2)) == pytest.approx(900.0)
    assert sens.indice_umidade_topografica(np.log(2), 45.0) == pytest.approx(np.log(30.0))
    # flatter ground and more upstream area raise B; the slope is floored so a flat cell does not blow up
    assert sens.indice_umidade_topografica(5, 1.0) > sens.indice_umidade_topografica(5, 8.0)
    assert sens.indice_umidade_topografica(7, 2.0) > sens.indice_umidade_topografica(4, 2.0)
    assert np.isfinite(sens.indice_umidade_topografica(5, 0.0))
    # C-score is B plus constants: ln(P*C*a/tanβ)
    b = sens.indice_umidade_topografica(5, 3.0)
    assert sens.escore_fisico(b, 0.5, 30) == pytest.approx(b + np.log(0.5) + np.log(0.03))


def test_uniform_rain_and_constant_c_scale_the_volume_but_never_reorder_the_streets():
    g, coords = grade("fisica")
    r = sens.rodar(g, coords, raio_m=50, replicas=RAPIDO)
    s = r["sensibilidade"]
    assert s["ordem_dos_trechos_independe_da_chuva_uniforme"]
    assert s["volume_cresce_com_a_chuva_em_todos_os_cenarios"] and s["volume_cresce_com_C_uniforme"]
    uniformes = [c for c in r["cenarios"] if c["coeficiente"].startswith("uniforme")]
    assert all(c["spearman_com_p30"] > 0.999999 for c in uniformes)
    # every uniform-C scenario ranks exactly like B: the same metrics
    por = r["modelos"]["C_com_coeficientes_de_escoamento"]["por_cenario_de_C"]
    ap_b = r["modelos"]["B_fluxo_ajustado_pela_declividade"]["precisao_media"]
    assert all(por[n]["precisao_media"] == ap_b for n in por if n.startswith("uniforme"))
    # a spatially varying C does change the order (that is the only way C can matter)
    assert s["spearman_de_B_com_cada_cenario_de_C"]["espacial_0,30-0,95"] < 0.999


def test_a_planted_physical_signal_is_found_and_reported_as_a_gain():
    g, coords = grade("fisica")
    r = sens.rodar(g, coords, raio_m=50, replicas=RAPIDO)
    assert r["amostra"]["trechos_rotulados"] >= 30
    b = r["modelos"]["B_fluxo_ajustado_pela_declividade"]
    assert b["ganho_sobre_a_referencia"] > 1.0 and b["atende_criterio"]
    assert b["ic95_ganho"][0] > 0


def test_with_flooding_unrelated_to_the_physics_nothing_is_adopted():
    """The criterion must not be loose: random labels give no adoptable formulation, and the verdict says so."""
    g, coords = grade("aleatorio", seed=5)
    r = sens.rodar(g, coords, raio_m=50, replicas=RAPIDO)
    assert not r["veredito"]["ha_evidencia_de_ganho_incremental"]
    assert "Não há evidência" in r["veredito"]["texto"]


def test_adoption_needs_both_the_margin_and_an_interval_above_zero():
    assert sens.atende(0.25, 0.05)
    assert not sens.atende(0.08, 0.04)          # positive but under the 10% margin
    assert not sens.atende(0.40, -0.02)         # large point gain with an interval that includes zero (uncertain)
    assert not sens.atende(0.10, 0.0)           # a bound at zero is not above zero


def test_bootstrap_is_paired_and_resamples_whole_spatial_blocks_together():
    rng = np.random.default_rng(3)
    y = rng.random(4000) < 0.03
    s = rng.normal(size=4000) + 0.8 * y
    # paired: an identical copy of the reference gets exactly the same resampled positives, so its gain is exactly zero with a zero-width interval
    r = sens.comparar(y, {"ref": s, "clone": s.copy()}, "ref", np.random.default_rng(1), 300)
    assert r["clone"]["ganho_sobre_a_referencia"] == 0 and r["clone"]["ic95_ganho"] == [0.0, 0.0]
    # blocks: positives in the same block always carry the same weight, and the interval is not narrower than resampling segments alone
    grupos = np.arange(4000) // 80
    t = s + rng.normal(scale=0.6, size=4000)
    por_trecho = sens.comparar(y, {"ref": s, "t": t}, "ref", np.random.default_rng(1), 1500)["t"]["ic95_ganho"]
    por_bloco = sens.comparar(y, {"ref": s, "t": t}, "ref", np.random.default_rng(1), 1500, grupos)["t"]["ic95_ganho"]
    assert por_bloco[1] - por_bloco[0] >= por_trecho[1] - por_trecho[0]
    _, inv = np.unique(grupos[y], return_inverse=True)
    pesos = np.random.default_rng(0).multinomial(inv.max() + 1, np.full(inv.max() + 1, 1 / (inv.max() + 1)), size=5)[:, inv]
    for w in pesos:
        assert all(len(set(w[inv == g])) == 1 for g in np.unique(inv))


def test_cluster_bootstrap_with_negatives_matches_a_brute_force_resampling():
    """The vectorised cluster bootstrap (blocks resampled with their negatives) must equal re-ranking the resampled data from scratch."""
    from sklearn.metrics import average_precision_score
    rng = np.random.default_rng(4)
    n = 600
    grupos = rng.integers(0, 12, n)
    y = rng.random(n) < 0.08
    s = rng.normal(size=n) + 1.0 * y
    _, bidx = np.unique(grupos, return_inverse=True)
    pre = sens._Pre(y, s, bidx)
    nb = bidx.max() + 1
    contagem = rng.multinomial(nb, np.full(nb, 1 / nb))
    ap, auc, _ = pre.medidas(contagem[bidx[y]], pre.acima @ contagem, pre.abaixo @ contagem, float(pre.n_neg_bloco @ contagem))
    # brute force: repeat each block's segments as many times as it was drawn, then rank everything again
    idx = np.repeat(np.arange(n), contagem[bidx])
    ref = average_precision_score(y[idx], s[idx])
    assert ap == pytest.approx(ref, rel=0.05)
    from sklearn.metrics import roc_auc_score
    assert auc == pytest.approx(roc_auc_score(y[idx], s[idx]), abs=0.01)


def test_the_distribution_of_positives_over_blocks_is_reported():
    d = sens.distribuicao_positivos(np.array([True] * 6 + [False] * 4), np.array([1, 1, 1, 1, 2, 3, 4, 4, 5, 5]))
    assert d["blocos_com_positivo"] == 3 and d["positivos_no_maior_bloco"] == 4 and d["participacao_do_maior_bloco"] == pytest.approx(0.667, abs=1e-3)
    assert 1 < d["numero_efetivo_de_blocos"] < 3


def test_bootstrap_handles_massive_score_ties_like_sklearn_and_its_interval_contains_the_estimate():
    """Regression: with most segments tied (zero fill height) the interval used to sit entirely above the point estimate and the criterion was met by artifact."""
    from sklearn.metrics import average_precision_score, roc_auc_score
    rng = np.random.default_rng(11)
    n = 20000
    y = rng.random(n) < 0.004
    s = np.where(rng.random(n) < 0.78, 0.0, rng.exponential(1.0, n) + 0.8 * y)            # 78% of the scores are exactly zero
    s[y & (rng.random(n) < 0.6)] = 0.0                                                    # and many positives are inside the tie
    ap, auc, _ = sens._Pre(y, s).medidas(np.ones(int(y.sum())))
    assert ap == pytest.approx(average_precision_score(y, s), rel=1e-9) and auc == pytest.approx(roc_auc_score(y, s), abs=1e-9)
    ref = rng.normal(size=n) + 0.5 * y
    r = sens.comparar(y, {"ref": ref, "empatado": s}, "ref", np.random.default_rng(3), 1000)["empatado"]
    lo, hi = r["ic95_precisao_media"]
    assert lo <= r["precisao_media"] <= hi                                                 # o intervalo contém a estimativa pontual
    glo, ghi = r["ic95_ganho"]
    assert glo <= r["ganho_sobre_a_referencia"] <= ghi


def test_fast_bootstrap_agrees_with_sklearn_on_the_point_estimate():
    rng = np.random.default_rng(0)
    y = rng.random(5000) < 0.02
    s = rng.normal(size=5000) + 1.2 * y
    ap, auc, topo = sens._Pre(y, s).medidas(np.ones(int(y.sum())))
    ref = anterior._medidas(y, s)
    assert ap == pytest.approx(ref["precisao_media"], rel=0.02)
    assert auc == pytest.approx(ref["auc"], abs=0.005)
    assert topo == pytest.approx(ref["positivos_no_topo_10pct"], abs=0.02)


def test_the_report_keeps_the_mandatory_limitations_and_the_markdown_follows_the_json():
    g, coords = grade("fisica", n=60)
    r = sens.rodar(g, coords, raio_m=50, replicas=100)
    texto = " ".join(r["limitacoes"])
    for obrigatorio in ("2013-2014", "horário nem precipitação", "DSM de 30 m", "capacidade da drenagem", "hipóteses de cenário"):
        assert obrigatorio in texto
    md = sens.relatorio_md(r)
    assert r["veredito"]["texto"] in md and "Equações e unidades" in md and "Limitações obrigatórias" in md
    assert "não prevê profundidade" in md.lower().replace("não altera o índice nem o modelo de produção, ", "")


@pytest.mark.skipif(not REDE.exists() or not COORDS.exists(), reason="validação com dados reais: falta data/processed/rede_poa.parquet (fora do Git) ou " + MOTIVO_AUSENTE)
def test_real_network_same_sample_as_before_data_untouched_and_no_forced_adoption():
    antes = hashlib.sha256(REDE.read_bytes()).hexdigest()
    coords = pd.read_csv(COORDS)
    rede = pd.read_parquet(REDE, columns=["lon0", "lat0", "lon1", "lat1", "percentil", "slope", "log_flow_acc", *COMPONENTES])
    r = sens.rodar(rede, coords, replicas=RAPIDO)
    assert hashlib.sha256(REDE.read_bytes()).hexdigest() == antes                      # dados originais intactos
    anterior_r = anterior.rodar(rede, coords)
    assert r["amostra"]["trechos"] == anterior_r["trechos"] and r["amostra"]["trechos_rotulados"] == anterior_r["trechos_rotulados"]
    a, a0 = r["modelos"]["A_regra_atual"], anterior_r["modelos"]["regra_de_terreno"]
    assert (a["auc"], a["precisao_media"], a["positivos_no_topo_10pct"]) == (a0["auc"], a0["precisao_media"], a0["positivos_no_topo_10pct"])   # mesma regra, mesma amostra
    assert r["sensibilidade"]["ordem_dos_trechos_independe_da_chuva_uniforme"] and r["sensibilidade"]["volume_cresce_com_a_chuva_em_todos_os_cenarios"]
    # the verdict must follow the criterion, never the other way round
    grupos = [r["modelos"]["B_fluxo_ajustado_pela_declividade"]["atende_criterio"], r["modelos"]["C_com_coeficientes_de_escoamento"]["atende_criterio_em_todos_os_cenarios"],
              r["modelos"]["D1_media_de_postos_regra_e_fisica"]["atende_criterio_em_todos_os_cenarios"], r["modelos"]["D2_componentes_mais_fisica"]["atende_criterio_em_todos_os_cenarios"]]
    assert r["veredito"]["ha_evidencia_de_ganho_incremental"] == any(grupos)
    for x in [r["modelos"]["B_fluxo_ajustado_pela_declividade"], *r["modelos"]["C_com_coeficientes_de_escoamento"]["por_cenario_de_C"].values()]:
        assert x["atende_criterio"] == (sens.atende(x["ganho_sobre_a_referencia"], x["ic95_ganho"][0]) and sens.atende(x["ganho_sobre_a_referencia"], x["ic95_ganho_por_blocos"][0])
                                       and sens.atende(x["ganho_sobre_a_referencia"], x["ic95_ganho_por_blocos_completo"][0]))
    json.dumps(r)                                                                      # serializável
