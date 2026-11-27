"""Dados SINTÉTICOS de teste: nada aqui vem de uma base real nem imita os pontos da Prefeitura.

A grade e os pontos alagados são gerados de uma semente fixa, com um sinal plantado (o alagamento depende de UM componente do terreno), numa região fora do
Brasil (perto de lon 0, lat 0). Servem para provar que o processamento funciona num clone limpo, sem os dados de terceiros que ficam fora do Git
(``flooding_mapping.dados_restritos``). Não são observações, não entram em nenhum resultado oficial e não alteram nenhuma métrica documentada.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from flooding_mapping.risco_trecho import COMPONENTES

CAMADA = "sintetico_nao_real"


def grade_com_sinal(n: int = 90, semente: int = 1) -> pd.DataFrame:
    """Grade de n x n trechos curtos com componentes de terreno aleatórios e um posto composto."""
    rng = np.random.default_rng(semente)
    k = np.arange(n * n)
    g = pd.DataFrame({"lon0": (k % n) * 0.006, "lat0": (k // n) * 0.006})
    g["lon1"], g["lat1"] = g.lon0 + 0.0005, g.lat0
    for c in COMPONENTES:
        g[c] = rng.normal(size=len(g))
    g["percentil"] = g[COMPONENTES].mean(axis=1).rank(pct=True) * 100
    return g


def pontos_alagados(g: pd.DataFrame) -> pd.DataFrame:
    """Pontos 'alagados' sintéticos: os trechos em que o primeiro componente passa de 2,4 desvios, no formato do arquivo real (camada, lon, lat)."""
    alvo = g.index[g[COMPONENTES[0]] > 2.4]
    return pd.DataFrame({"camada": CAMADA, "lon": (g.lon0[alvo] + 0.00025).round(6).to_numpy(), "lat": g.lat0[alvo].round(6).to_numpy()})
