import numpy as np
import pandas as pd

from flooding_mapping import aprendizado
from flooding_mapping.risco_trecho import COMPONENTES
from rede_sintetica import LAT0, LON0, PR_ROTA, aresta
from flooding_mapping.rotas import Rede

P = {"apoios_minimos": 2, "min_ocorrencias": 8, "min_positivos": 30, "raio_rotulo_m": 100, "bloco_m": 1500, "dobras": 5, "margem_ap": 0.1,
     "fracao_sugerida": 0.02, "raio_bolsao_m": 120, "raio_aviso_m": 150}


def grade(n=60, seed=3):
    """n x n isolated east-west segments, each 1 km apart, with five random terrain facts; the 'percentil' is the plain mean rank."""
    rng = np.random.default_rng(seed)
    linhas = []
    for k in range(n * n):
        x, y = (k % n) * 0.012, (k // n) * 0.012
        linhas.append({**aresta(f"g{k}", 2 * k, 2 * k + 1, (x, y), (x + 0.004, y)), **dict(zip(COMPONENTES, rng.normal(size=5)))})
    d = pd.DataFrame(linhas)
    d["percentil"] = d[COMPONENTES].mean(axis=1).rank(pct=True) * 100
    return d


def ocorrencias(d, ids):
    return [{"id": f"o{i}", "situacao": "confirmada", "segmento_ids": [s], "lon": 0, "lat": 0, "apoios": []} for i, s in enumerate(ids)]


def test_with_few_labels_the_terrain_rule_stays_and_the_status_says_why():
    r = Rede(grade(), PR_ROTA)
    res = aprendizado.treinar(r, ocorrencias(r.arestas, ["g1", "g2"]), P)
    assert not res["adotado"] and res["fonte"] == "regra de terreno" and "poucos rótulos" in res["motivo"]
    assert np.allclose(res["rank"], r.pct / 100.0)


def test_the_model_is_adopted_only_when_it_beats_the_rule_in_held_out_blocks():
    d = grade()
    r = Rede(d, PR_ROTA)
    verdade = d.index[d["baixa_altitude"] > 1.9]                  # the truth depends on ONE terrain fact, which the equal-weight rule dilutes
    res = aprendizado.treinar(r, ocorrencias(d, [d["segmento_id"][i] for i in verdade]), P)
    assert res["adotado"] and res["ap_modelo"] > res["ap_regra"] * 1.1
    assert res["pesos"]["baixa_altitude"] == max(res["pesos"].values())
    top = aprendizado.sugeridas(r, res["rank"], 0.02)
    assert len(top) == int(r.n * 0.02) and set(top) & set(verdade)


def test_labels_that_the_rule_already_explains_do_not_replace_it():
    d = grade()
    r = Rede(d, PR_ROTA)
    alvo = d.index[d["percentil"] > 97]
    res = aprendizado.treinar(r, ocorrencias(d, [d["segmento_id"][i] for i in alvo]), P)
    assert not res["adotado"] and "não superou" in res["motivo"]


def test_unlabeled_is_not_negative_and_missing_terrain_has_no_rank():
    d = grade(n=30)
    d.loc[:5, COMPONENTES] = np.nan
    d.loc[:5, "percentil"] = np.nan
    r = Rede(d, PR_ROTA)
    res = aprendizado.treinar(r, [], P)
    assert np.isnan(res["rank"][:6]).all() and not np.isnan(res["rank"][6:]).any()
    assert 0 not in aprendizado.sugeridas(r, res["rank"], 0.5)


def test_the_signature_changes_only_when_the_labels_change():
    a = [{"id": "x", "situacao": "reportada", "apoios": ["h1"]}]
    assert aprendizado.assinatura(a) == aprendizado.assinatura(list(a))
    assert aprendizado.assinatura(a) != aprendizado.assinatura([{**a[0], "apoios": ["h1", "h2"]}])
