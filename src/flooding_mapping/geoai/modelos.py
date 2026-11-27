"""Modelos do experimento: Random Forest (baseline tradicional) e dois controles simples. Mesmo protocolo para qualquer representação de entrada."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

from . import atributos as at
from .referencia import GRUPOS


def matriz(atributos: np.ndarray, nomes: list[str], mascara: np.ndarray, ordem: list[str] | None = None) -> np.ndarray:
    """(n_células, n_atributos) em float32 das células de ``mascara``, na ordem de ``nomes``; ``ordem`` nomeia o último eixo de ``atributos`` (padrão: ``at.NOMES``)."""
    idx = [(ordem or at.NOMES).index(n) for n in nomes]
    return atributos[mascara][:, idx].astype("float32")


def normalizar(p: np.ndarray) -> np.ndarray:
    """Frações em [0, 1] que somam 1 (a previsão de cada grupo é independente; a soma é imposta depois)."""
    p = np.clip(p, 0, None)
    s = p.sum(axis=1, keepdims=True)
    return np.where(s > 0, p / np.where(s > 0, s, 1), 1 / p.shape[1])


def ajustar_rf(X: np.ndarray, Y: np.ndarray, params: dict, semente: int, limite: int | None = None) -> RandomForestRegressor:
    """RF multissaída das quatro frações; ``limite`` subamostra o treino (reprodutível) para caber na memória."""
    if limite and len(X) > limite:
        sel = np.random.default_rng(semente).choice(len(X), limite, replace=False)
        X, Y = X[sel], Y[sel]
    rf = RandomForestRegressor(n_estimators=params["n_estimators"], min_samples_leaf=params["min_samples_leaf"], max_features=params["max_features"], n_jobs=params["n_jobs"], random_state=semente)
    return rf.fit(X, Y)


def prever_rf(rf: RandomForestRegressor, X: np.ndarray, lote: int = 60000) -> tuple[np.ndarray, np.ndarray]:
    """Frações previstas (normalizadas) e desvio entre as árvores da fração construída (indicador de incerteza do modelo, não intervalo de confiança)."""
    saida, desvio = [], []
    for i in range(0, len(X), lote):
        por_arvore = np.stack([e.predict(X[i:i + lote]) for e in rf.estimators_])      # (árvores, lote, 4)
        saida.append(por_arvore.mean(0))
        desvio.append(por_arvore[:, :, GRUPOS.index("construido")].std(0))
    return normalizar(np.concatenate(saida)), np.concatenate(desvio)


def ajustar_linear(X: np.ndarray, Y: np.ndarray) -> tuple[LinearRegression, np.ndarray]:
    """Controle ingênuo: regressão linear em poucos índices, com NaN trocado pela média do treino."""
    medias = np.nanmean(X, axis=0)
    return LinearRegression().fit(np.where(np.isnan(X), medias, X), Y), medias


def prever_linear(m: tuple[LinearRegression, np.ndarray], X: np.ndarray) -> np.ndarray:
    return normalizar(m[0].predict(np.where(np.isnan(X), m[1], X)))


def regioes_por_quadrante(blocos: np.ndarray, dobras_validas: np.ndarray, n_colunas_de_blocos: int) -> np.ndarray:
    """Protocolo mais duro: quatro quadrantes (norte/sul x oeste/leste, pela mediana dos blocos usados). Cada um é testado com o modelo treinado nos outros três."""
    usados = np.unique(blocos[dobras_validas >= 0])
    lin, col = usados // n_colunas_de_blocos, usados % n_colunas_de_blocos
    ml, mc = np.median(lin), np.median(col)
    regiao = {int(b): int(2 * (l > ml) + (c > mc)) for b, l, c in zip(usados, lin, col)}
    r = np.full(blocos.shape, -1, dtype="int16")
    for b, g in regiao.items():
        r[blocos == b] = g
    r[dobras_validas < 0] = -1
    return r


def validar_espacialmente(atributos: np.ndarray, alvos: np.ndarray, valida: np.ndarray, dobras: np.ndarray, nomes: list[str], buffer_celulas: int, params: dict, semente: int,
                          modelo: str = "rf", ordem: list[str] | None = None) -> dict:
    """Previsão fora da dobra para todas as células de ``valida`` com dobra >= 0.

    ``alvos`` é (linhas, colunas, 4). Para cada dobra, treina nas células válidas fora dela e fora do buffer e prevê as células da dobra.
    ``modelo``: ``rf`` (Random Forest), ``linear`` (controle com poucos índices) ou ``media`` (controle: fração média do treino).
    """
    from .referencia import mascara_de_treino
    dentro = valida & (dobras >= 0)
    flat = np.flatnonzero(dentro.ravel())
    pred, sd = np.full((len(flat), len(GRUPOS)), np.nan, dtype="float32"), np.full(len(flat), np.nan, dtype="float32")
    dobra_flat = dobras.ravel()[flat]
    for k in sorted(set(dobra_flat.tolist())):
        teste = dentro & (dobras == k)
        treino = mascara_de_treino(teste, dentro, buffer_celulas)
        Xtr, Ytr, Xte = matriz(atributos, nomes, treino, ordem), alvos[treino], matriz(atributos, nomes, teste, ordem)
        sel = dobra_flat == k
        if modelo == "rf":
            rf = ajustar_rf(Xtr, Ytr, params, semente + k, params.get("amostras_de_treino"))
            pred[sel], sd[sel] = prever_rf(rf, Xte)
        elif modelo == "linear":
            pred[sel] = prever_linear(ajustar_linear(Xtr, Ytr), Xte)
        elif modelo == "media":
            pred[sel] = np.tile(Ytr.mean(0), (int(sel.sum()), 1))
        else:
            raise ValueError(modelo)
    return {"indices": flat, "pred": pred, "sd": sd, "dobra": dobra_flat}
