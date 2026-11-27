"""Experimento EXPLORATÓRIO: a regra de terreno contra três modelos aprendidos, nos trechos alagados registrados pela Prefeitura.

    python tools/experimento_modelos_alagamentos.py [saida.json]

Compara, com validação por blocos espaciais (uma rua nunca ajuda a prever a vizinha):
  regra (percentil do índice de terreno) | regressão logística | gradient boosting | MLP (rede neural)
As entradas são só os cinco fatos de terreno. Os rótulos são trechos a até 100 m de um registro de alagamento (2013-2014, só coordenadas);
todo o resto é "não rotulado", não "seco" (aprendizado com positivos e não rotulados). Mede terreno, não chuva.
Com ~100 trechos positivos o resultado é indicativo: serve para dizer se vale insistir, não para escolher um modelo de produção.
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from flooding_mapping.dados_restritos import ler_alagamentos  # noqa: E402
from flooding_mapping.risco_trecho import COMPONENTES

RAIZ = Path(__file__).resolve().parents[1]
MARGEM_AP = 0.10        # a mesma exigência de config/analysis.yaml (aprendizado.margem_ap): ganho relativo de PR-AUC para adotar
KX, KY = np.cos(np.radians(-30.05)) * 111320, 110574


def modelos(semente: int) -> dict:
    return {
        "regressao_logistica": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=300)),
        "gradient_boosting": lambda: HistGradientBoostingClassifier(max_depth=3, max_iter=100, learning_rate=0.1, random_state=semente),
        "mlp": lambda: make_pipeline(StandardScaler(), MLPClassifier((16, 8), alpha=1e-2, max_iter=200, early_stopping=False, random_state=semente)),
    }


def rotular(g: pd.DataFrame, coords: pd.DataFrame, raio_m: float = 100) -> np.ndarray:
    """Boolean per segment: the segment nearest to a record, when within ``raio_m``."""
    arvore = cKDTree(np.c_[(g.lon0 + g.lon1) / 2 * KX, (g.lat0 + g.lat1) / 2 * KY])
    d, i = arvore.query(np.c_[coords.lon * KX, coords.lat * KY], distance_upper_bound=raio_m)
    y = np.zeros(len(g), bool)
    y[i[d <= raio_m]] = True
    return y


def blocos(g: pd.DataFrame, lado_m: float = 1500) -> np.ndarray:
    x, y = (g.lon0 + g.lon1) / 2 * KX, (g.lat0 + g.lat1) / 2 * KY
    return (np.floor(x / lado_m) * 100003 + np.floor(y / lado_m)).to_numpy().astype(np.int64)


def amostra_treino(y: np.ndarray, rng, razao: int = 50, repetir: int = 5) -> np.ndarray:
    """Positives (repeated, so a small class is not drowned) plus a sample of the unlabeled; ranks do not depend on the sampling prior."""
    pos, neg = np.flatnonzero(y), np.flatnonzero(~y)
    sorteio = rng.choice(neg, size=min(len(neg), max(2000, razao * len(pos))), replace=False)
    return np.concatenate([np.tile(pos, repetir), sorteio])


def _medidas(y, escore, topo: float = 0.10) -> dict:
    corte = np.quantile(escore, 1 - topo)
    return {"auc": round(float(roc_auc_score(y, escore)), 3), "precisao_media": round(float(average_precision_score(y, escore)), 5),
            "positivos_no_topo_10pct": round(float((escore[y] >= corte).mean()), 3)}


def _intervalo(y, escore, rng, n=100) -> list:
    """Bootstrap over the positives (the negatives stay fixed): 95% interval of the average precision."""
    pos, neg = np.flatnonzero(y), np.flatnonzero(~y)
    aps = []
    for _ in range(n):
        idx = np.concatenate([rng.choice(pos, len(pos)), neg])
        aps.append(average_precision_score(y[idx], escore[idx]))
    return [round(float(v), 5) for v in np.percentile(aps, [2.5, 97.5])]


def rodar(rede: pd.DataFrame, coords: pd.DataFrame, semente: int = 7, dobras: int = 5, raio_m: float = 100) -> dict:
    """Out-of-fold scores of the rule and of each model on the same segments, folds made of whole spatial blocks."""
    ok = ~rede[COMPONENTES].isna().any(axis=1).to_numpy() & rede.percentil.notna().to_numpy()
    g = rede[ok].reset_index(drop=True)
    y, X, regra, grupos = rotular(g, coords, raio_m), g[COMPONENTES].to_numpy(float), g.percentil.to_numpy(float), blocos(g)
    com_positivo = np.unique(grupos[y])
    dobras = min(dobras, len(com_positivo))
    rng = np.random.default_rng(semente)
    oof = {nome: np.zeros(len(y)) for nome in modelos(semente)}
    separados = True
    for treino, teste in GroupKFold(n_splits=dobras).split(X, y, grupos):
        separados &= not set(grupos[treino]) & set(grupos[teste])
        if y[treino].sum() == 0 or y[teste].sum() == 0:
            for nome in oof:
                oof[nome][teste] = regra[teste]
            continue
        idx = treino[amostra_treino(y[treino], rng)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for nome, fabrica in modelos(semente).items():
                oof[nome][teste] = fabrica().fit(X[idx], y[idx]).predict_proba(X[teste])[:, 1]
    resultado = {"regra_de_terreno": {**_medidas(y, regra), "intervalo_95_precisao_media": _intervalo(y, regra, np.random.default_rng(semente))}}
    for nome, escore in oof.items():
        resultado[nome] = {**_medidas(y, escore), "intervalo_95_precisao_media": _intervalo(y, escore, np.random.default_rng(semente))}
    ap_regra = resultado["regra_de_terreno"]["precisao_media"]
    for nome in oof:
        ganho = resultado[nome]["precisao_media"] / ap_regra - 1
        resultado[nome]["ganho_sobre_a_regra"] = round(float(ganho), 3)
        resultado[nome]["adotaria"] = bool(ganho >= MARGEM_AP)
    return {"trechos": int(len(y)), "trechos_rotulados": int(y.sum()), "taxa_base": round(float(y.mean()), 5), "dobras": int(dobras),
            "blocos_separados_entre_treino_e_teste": bool(separados), "margem_exigida": MARGEM_AP, "modelos": resultado,
            "leitura": "exploratório: ~100 trechos positivos, rótulos de 2013-2014, só terreno (sem chuva). Um modelo só seria adotado com ganho "
                       f"de {MARGEM_AP:.0%} de PR-AUC sobre a regra em blocos espaciais; intervalos que se sobrepõem não sustentam diferença."}


if __name__ == "__main__":
    coords = ler_alagamentos()
    rede = pd.read_parquet(RAIZ / "data/processed/rede_poa.parquet", columns=["lon0", "lat0", "lon1", "lat1", "percentil", *COMPONENTES])
    r = rodar(rede, coords)
    saida = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "reports/qa/modelos_exploratorio_alagamentos.json")
    saida.write_text(json.dumps(r, ensure_ascii=False, indent=2))
    print(json.dumps(r["modelos"], ensure_ascii=False, indent=2))
