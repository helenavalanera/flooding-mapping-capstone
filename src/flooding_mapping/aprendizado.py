"""Learning from what the community confirms: a ranking of street segments to *verify first*.

The labels are segments next to a record that an operator confirmed or enough people backed (``Ocorrencias.rotuladas``).
Everything else is *unlabeled*, not negative: no record of flooding is not evidence of dry streets (positive-unlabeled
learning). The features are the five terrain facts of ``risco_trecho.indice_fisico``; the model is a class-weighted logistic
regression, so every weight can be read.

The model replaces the terrain rule only when it earns it. Out-of-fold PR-AUC is measured with whole spatial blocks held out
(a street never helps predict its neighbour), against the rule's own PR-AUC on the same segments, and the model is adopted only
when it beats the rule by ``margem_ap``. With too few labels, or without that gain, the rule stays and the status says so.
The result is a rank (0-1, 1 = verify first), not a probability of flooding, and it inherits the bias of who reports.
"""

from __future__ import annotations

import hashlib

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupKFold

from .risco_trecho import COMPONENTES
from .rotas import Rede


def rotulos(rede: Rede, ocorrencias: list[dict], raio_m: float) -> np.ndarray:
    """Boolean per segment: next to a record that counts as observed."""
    y = np.zeros(rede.n, bool)
    for r in ocorrencias:
        idx = rede.indices(r["segmento_ids"]) if r["segmento_ids"] else rede.proximos(r["lon"], r["lat"], raio_m)
        y[idx] = True
    return y


def assinatura(ocorrencias: list[dict]) -> str:
    """Stable fingerprint of the label set: the model is retrained only when it changes."""
    return hashlib.sha1("|".join(sorted(f"{r['id']}:{r['situacao']}:{len(r.get('apoios', []))}" for r in ocorrencias)).encode()).hexdigest()[:12]


def _blocos(rede: Rede, lado_m: float) -> np.ndarray:
    meio = (rede._p0 + rede._p1) / 2
    return (np.floor(meio[:, 0] / lado_m) * 100003 + np.floor(meio[:, 1] / lado_m)).astype(np.int64)


def _rank(valores: np.ndarray) -> np.ndarray:
    """0-1 rank (1 = highest) keeping NaN where there is no value."""
    out = np.full(len(valores), np.nan)
    ok = ~np.isnan(valores)
    out[ok] = (np.argsort(np.argsort(valores[ok])) + 1) / ok.sum()
    return out


def treinar(rede: Rede, ocorrencias: list[dict], p: dict) -> dict:
    """Status plus ``rank``: per-segment score (0-1) from the model if adopted, else from the terrain rule."""
    regra = np.where(np.isnan(rede.pct), np.nan, rede.pct / 100.0)
    base = {"assinatura": assinatura(ocorrencias), "n_ocorrencias": len(ocorrencias), "fonte": "regra de terreno",
            "adotado": False, "rank": regra, "ap_modelo": None, "ap_regra": None, "pesos": None}
    if not all(c in rede.arestas.columns for c in COMPONENTES):
        return {**base, "n_positivos": 0, "motivo": "a tabela de ruas carregada não traz os componentes de terreno: a regra segue valendo"}
    y = rotulos(rede, ocorrencias, p["raio_rotulo_m"]) if ocorrencias else np.zeros(rede.n, bool)
    X = rede.arestas[COMPONENTES].to_numpy(float)
    ok = ~np.isnan(X).any(axis=1)
    positivos = int((y & ok).sum())
    base["n_positivos"] = positivos
    if len(ocorrencias) < p["min_ocorrencias"] or positivos < p["min_positivos"]:
        return {**base, "motivo": f"poucos rótulos confirmados ({len(ocorrencias)} ocorrências, {positivos} trechos): a regra de terreno segue valendo; "
                                  f"o modelo só é treinado com {p['min_ocorrencias']} ocorrências e {p['min_positivos']} trechos"}
    blocos = _blocos(rede, p["bloco_m"])
    com_positivo = np.unique(blocos[ok & y])
    dobras = min(p["dobras"], len(com_positivo))
    if dobras < 2:
        return {**base, "motivo": "rótulos concentrados em um bloco espacial: sem como validar; a regra segue valendo"}
    Xo, yo, go, ro = X[ok], y[ok], blocos[ok], regra[ok]
    oof = np.zeros(len(yo))
    for treino, teste in GroupKFold(n_splits=dobras).split(Xo, yo, go):
        if yo[treino].sum() == 0 or yo[teste].sum() == 0:
            oof[teste] = ro[teste]
            continue
        m = LogisticRegression(class_weight="balanced", max_iter=300).fit(Xo[treino], yo[treino])
        oof[teste] = m.predict_proba(Xo[teste])[:, 1]
    ap_modelo, ap_regra = float(average_precision_score(yo, oof)), float(average_precision_score(yo, ro))
    base.update(ap_modelo=round(ap_modelo, 4), ap_regra=round(ap_regra, 4))
    if ap_modelo < ap_regra * (1 + p["margem_ap"]):
        return {**base, "motivo": f"o modelo (PR-AUC {ap_modelo:.3f}) não superou a regra de terreno ({ap_regra:.3f}) por {p['margem_ap']:.0%} em blocos espaciais: a regra segue valendo"}
    final = LogisticRegression(class_weight="balanced", max_iter=300).fit(Xo, yo)
    pontuacao = np.full(rede.n, np.nan)
    pontuacao[ok] = final.predict_proba(Xo)[:, 1]
    return {**base, "adotado": True, "fonte": "modelo aprendido com confirmações da comunidade", "rank": _rank(pontuacao),
            "pesos": {c: round(float(w), 3) for c, w in zip(COMPONENTES, final.coef_[0])},
            "motivo": f"o modelo (PR-AUC {ap_modelo:.3f}) superou a regra de terreno ({ap_regra:.3f}) em blocos espaciais"}


def sugeridas(rede: Rede, rank: np.ndarray, fracao: float) -> np.ndarray:
    """Positions of the segments to verify first: the top ``fracao`` of the network by rank."""
    validos = np.flatnonzero(~np.isnan(rank))
    n = max(1, int(len(validos) * fracao))
    return validos[np.argsort(-rank[validos])][:n]
