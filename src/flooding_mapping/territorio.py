"""Territory of Porto Alegre from the City's public maps: neighbourhoods, streams, pumping stations and informal settlements.

Streets are assigned to the neighbourhood that contains their midpoint, so the exposure estimate can be read by neighbourhood.
The settlement figures (IBGE 2010 subnormal agglomerates, per neighbourhood) are context for *who lives where the estimate is
high*; they are not part of the score. Nothing here is personal data.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from shapely.geometry import shape
from shapely.strtree import STRtree

from .config import resolve

ARQUIVO = "data/processed/territorio_poa.json"


def carregar(caminho=None) -> dict | None:
    """The prepared territory, or ``None`` when it was not built (the service then runs without these layers)."""
    arquivo = Path(caminho) if caminho else resolve(ARQUIVO)
    return json.loads(arquivo.read_text()) if arquivo.exists() else None


def vincular(rede, territorio: dict) -> np.ndarray:
    """Index of the neighbourhood of each street segment (-1 where no polygon contains its midpoint)."""
    from shapely import points

    formas = [shape(b["geom"]) for b in territorio["bairros"]]
    arvore = STRtree(formas)
    meio = points((rede.arestas.lon0.to_numpy() + rede.arestas.lon1.to_numpy()) / 2, (rede.arestas.lat0.to_numpy() + rede.arestas.lat1.to_numpy()) / 2)
    pontos, polis = arvore.query(meio, predicate="within")
    out = np.full(rede.n, -1, dtype=np.int32)
    out[pontos] = polis
    return out


def por_bairro(territorio: dict, bairro_do_trecho: np.ndarray, comprimento_m: np.ndarray, classes: np.ndarray) -> list[dict]:
    """One row per neighbourhood: kilometres of street in attention or high exposure and their share of the neighbourhood's streets."""
    saida = []
    for i, b in enumerate(territorio["bairros"]):
        no_bairro = bairro_do_trecho == i
        total = float(comprimento_m[no_bairro].sum())
        alto = float(comprimento_m[no_bairro & (classes == "alto")].sum())
        atencao = float(comprimento_m[no_bairro & (classes == "atencao")].sum())
        saida.append({"id": i, "nome": b["nome"], "geometria": b["geom"], "km_ruas": round(total / 1000, 1), "km_alto": round(alto / 1000, 2),
                      "km_atencao": round(atencao / 1000, 2), "parcela_exposta": round((alto + atencao) / total, 4) if total else None,
                      "aglomerados": b["aglomerados"], "pop_aglomerados": b["pop_aglomerados"], "domicilios_aglomerados": b["domicilios_aglomerados"]})
    return saida
