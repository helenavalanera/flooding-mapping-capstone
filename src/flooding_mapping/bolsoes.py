"""Pockets of estimated exposure: stretches flagged at the same hour, grouped into areas, with the places inside them.

Given the segments at ``atencao`` or ``alto`` (or any set of segments to look at), each one is widened by a buffer and
the overlapping buffers merge into one *pocket* (``bolsao``). For every pocket the output says how many kilometres of
street it holds, how strong the estimate is, and which points of interest (hospitals, schools, ...) lie inside it.

This is geometry and arithmetic over the risk estimate, not a second model: a pocket is exactly as reliable as the
estimate it groups (an unvalidated baseline) and a POI inside one is *possibly* affected, never "flooded".

    prioridade = escore_medio x (1 + ln(1 + soma dos pesos dos POIs))      (explicit and editorial; see ``pois.PESO``)
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import mapping
from shapely.strtree import STRtree

from . import pois as pois_mod
from .rotas import M_POR_GRAU, Rede

MAX_NOMES = 6


def _para_lonlat(rede: Rede, geometria):
    """Back from the local metric plane (equirectangular, as in ``Rede``) to lon/lat."""
    escala = np.array([rede._cos * M_POR_GRAU, M_POR_GRAU])
    return shapely.transform(geometria, lambda xy: xy / escala)


def formar(rede: Rede, indices, escore: np.ndarray, pois: pd.DataFrame | None = None, raio_m: float = 120.0,
           maximo: int = 25, simplificar_m: float = 15.0) -> list[dict]:
    """Pockets for the segments in ``indices`` (positions in the network), strongest priority first.

    ``escore`` is the per-segment value that ranks them (0-1; the hour's risk score, or a susceptibility rank).
    Each pocket: id, geometry (GeoJSON polygon, lon/lat), km, segment counts, the street names, the POIs inside.
    """
    indices = np.asarray(indices, dtype=int)
    if not len(indices):
        return []
    linhas = shapely.linestrings(np.stack([rede._p0[indices], rede._p1[indices]], axis=1))
    bufs = shapely.buffer(linhas, raio_m, quad_segs=3)
    uniao = shapely.union_all(bufs)
    poligonos = list(uniao.geoms) if uniao.geom_type == "MultiPolygon" else [uniao]
    arvore_linhas = STRtree(linhas)
    xy_pois, pois_tab = None, None
    if pois is not None and len(pois):
        pois_tab = pois.reset_index(drop=True)
        xy_pois = rede._xy(pois_tab["lon"], pois_tab["lat"])
        arvore_pois = STRtree(shapely.points(xy_pois))
    nomes_vias = rede.arestas["nome"].to_numpy(object)
    km = rede.comp_m / 1000
    saida = []
    for poligono in poligonos:
        dentro = indices[np.asarray(arvore_linhas.query(poligono, predicate="intersects"), dtype=int)]
        if not len(dentro):
            continue
        valores = escore[dentro]
        lista_pois, peso = [], 0.0
        if pois_tab is not None:
            achados = np.asarray(arvore_pois.query(poligono, predicate="contains"), dtype=int)
            sub = pois_tab.iloc[achados]
            lista_pois = [{"poi_id": r.poi_id, "nome": r.nome if isinstance(r.nome, str) and r.nome else None, "categoria": r.categoria, "tipo": r.tipo,
                           "lon": float(r.lon), "lat": float(r.lat)} for r in sub.itertuples()]
            peso = float(sum(pois_mod.PESO[p["categoria"]] for p in lista_pois))
        escore_medio = float(np.nanmean(valores))
        por_categoria = {}
        for p in lista_pois:
            por_categoria[p["categoria"]] = por_categoria.get(p["categoria"], 0) + 1
        nomes = pd.Series(nomes_vias[dentro]).dropna().value_counts().index.tolist()[:MAX_NOMES]
        geo = _para_lonlat(rede, shapely.simplify(poligono, simplificar_m))
        c = geo.centroid
        saida.append({
            "id": f"b{round(c.x * 1e4):d}_{round(c.y * 1e4):d}", "centro": [round(c.x, 5), round(c.y, 5)],
            "geometria": mapping(shapely.set_precision(geo, 1e-5)),
            "km": round(float(km[dentro].sum()), 2), "n_trechos": int(len(dentro)),
            "escore_medio": round(escore_medio, 3), "escore_maximo": round(float(np.nanmax(valores)), 3),
            "ruas": nomes, "pois_por_categoria": por_categoria, "n_pois": len(lista_pois),
            "pois": sorted(lista_pois, key=lambda p: (-pois_mod.PESO[p["categoria"]], p["nome"] or "~"))[:30],
            "prioridade": round(escore_medio * (1 + math.log1p(peso)), 3), "segmento_ids": [str(rede.ids[i]) for i in dentro[:200]]})
    saida.sort(key=lambda b: (-b["prioridade"], -b["km"]))
    return saida[:maximo]


def extensao(km: float) -> str:
    """Length in plain words: metres under a kilometre, one decimal above."""
    return f"{round(km * 1000 / 10) * 10:d} m" if km < 1 else f"{km:.1f} km".replace(".", ",")


def texto(b: dict, hora: str, natureza: str) -> str:
    """Deterministic sentence for a pocket, from its own numbers. Always an estimate, never "safe" or "flooded"."""
    ruas = ", ".join(b["ruas"][:3]) if b["ruas"] else "trechos sem nome no mapa"
    partes = [f"Área com {extensao(b['km'])} de vias em exposição estimada às {hora} ({natureza}): {ruas}."]
    if b["n_pois"]:
        cats = ", ".join(f"{n} de {pois_mod.ROTULOS[c]}" for c, n in sorted(b["pois_por_categoria"].items(), key=lambda kv: -pois_mod.PESO[kv[0]]))
        partes.append(f"Dentro dela há {b['n_pois']} pontos de interesse ({cats}) que podem ter o acesso afetado.")
    partes.append("É uma estimativa de um baseline sem validação em vias, não um alerta oficial.")
    return " ".join(partes)
