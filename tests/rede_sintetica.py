"""Small street graphs and rain series for the risk and routing tests."""

import numpy as np
import pandas as pd

from flooding_mapping.config import load_config
from flooding_mapping.risco_trecho import pesos, tabela_de_chuva
from flooding_mapping.rotas import Rede

CFG = load_config()
PR, PR_ROTA = CFG["risco_trecho"], CFG["roteamento"]
LON0, LAT0 = -51.22, -30.03


def aresta(sid, u, v, de, para, metros=1000.0, pct=50.0, highway="primary", oneway="no", drive=True, walk=True, nome=None):
    return {"segmento_id": sid, "u": u, "v": v, "comprimento_m": metros, "highway": highway, "oneway": oneway,
            "drive": drive, "walk": walk, "lon0": LON0 + de[0], "lat0": LAT0 + de[1], "lon1": LON0 + para[0],
            "lat1": LAT0 + para[1], "percentil": pct, "nome": nome or sid}


def tres_caminhos(pct_curto=95.0, pct_medio=50.0, pct_longo=5.0, metros=1000.0):
    """O -> D by a short (2 segments), a medium (3) and a long (4) path with no segment in common."""
    O, D = (0.0, 0.0), (0.03, 0.0)
    pontos = {"s1": (0.015, 0.004), "m1": (0.01, 0.01), "m2": (0.02, 0.01), "l1": (0.005, -0.012),
              "l2": (0.012, -0.014), "l3": (0.02, -0.012)}
    nos = {"O": O, "D": D, **pontos}
    cadeias = {"S": (["O", "s1", "D"], pct_curto), "M": (["O", "m1", "m2", "D"], pct_medio),
               "L": (["O", "l1", "l2", "l3", "D"], pct_longo)}
    rows, ids = [], {n: i for i, n in enumerate(nos)}
    for nome, (cadeia, pct) in cadeias.items():
        for k, (a, b) in enumerate(zip(cadeia, cadeia[1:])):
            rows.append(aresta(f"{nome}{k}", ids[a], ids[b], nos[a], nos[b], metros, pct))
    return pd.DataFrame(rows)


def rede(arestas: pd.DataFrame) -> Rede:
    return Rede(arestas, PR_ROTA)


def chuva(inicio="2026-11-09 12:00", mm_h=15.0, horas=4):
    """Hourly rain: four dry days, then ``horas`` hours at ``mm_h`` from ``inicio`` (local time)."""
    indice = pd.date_range("2026-11-03 00:00", "2026-11-12 00:00", freq="h")
    serie = pd.Series(0.0, index=indice)
    serie[pd.Timestamp(inicio):pd.Timestamp(inicio) + pd.Timedelta(hours=horas - 1)] = mm_h
    return serie


def tabela(**kw):
    return tabela_de_chuva(chuva(**kw), PR)


def sem_risco(r: Rede, ocorrencias=()):
    return pesos(r.pct, r, list(ocorrencias), PR)


O, D = (LON0, LAT0), (LON0 + 0.03, LAT0)
