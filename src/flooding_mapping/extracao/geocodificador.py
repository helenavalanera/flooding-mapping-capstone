"""Places a candidate on a street by name. Coarse on purpose: a street name is not a point.

Only the street table of Porto Alegre exists today, so only events in Porto Alegre can become street-level labels. Anything else keeps its
municipality and date (useful for the municipal trigger) and no coordinate. A name that matches many streets is *ambiguous* and gets no point.
"""

from __future__ import annotations

import re

import pandas as pd

from .esquema import normalizar

_PREFIXOS = re.compile(r"^(rua|r|avenida|av|travessa|tv|alameda|al|estrada|est|rodovia|rod|beco|largo|praca|pca|ponte|viaduto|elevada)\.?\s+")


def chave_da_via(nome: str) -> str:
    n = normalizar(nome)
    n = re.sub(r"\b(dos|das|do|da|de)\b", " ", n)
    return re.sub(r"\s+", " ", _PREFIXOS.sub("", re.sub(r"\s+", " ", n).strip())).strip()


class Geocodificador:
    """Index of the street table by normalized name; ``localizar`` returns the street's segments and a centre, or why it could not."""

    def __init__(self, rede: pd.DataFrame, municipio: str = "porto alegre"):
        self.municipio = normalizar(municipio)
        nomeadas = rede[rede["nome"].notna()].copy()
        nomeadas["_chave"] = nomeadas["nome"].map(chave_da_via)
        self._por_chave = {k: g for k, g in nomeadas.groupby("_chave") if k}

    def localizar(self, evento: dict) -> dict:
        mun = normalizar(evento.get("municipio", ""))
        if mun and mun != self.municipio:
            return {"precisao": "municipio", "motivo": "fora_da_rede_disponivel"}
        via = chave_da_via(evento.get("via") or "")
        if not via:
            return {"precisao": "municipio" if mun else "nenhuma", "motivo": "sem_via"}
        grupo = self._por_chave.get(via)
        if grupo is None:
            return {"precisao": "nenhuma", "motivo": "via_nao_encontrada"}
        lon = float(pd.concat([grupo["lon0"], grupo["lon1"]]).median())
        lat = float(pd.concat([grupo["lat0"], grupo["lat1"]]).median())
        extensao_m = float(grupo["comprimento_m"].sum())
        if extensao_m > 6000:   # a very long street (an avenue crossing the city) says little about where the water was
            return {"precisao": "via_extensa", "motivo": "via_longa_demais", "segmentos": int(len(grupo)), "extensao_m": round(extensao_m)}
        return {"precisao": "via", "lon": round(lon, 6), "lat": round(lat, 6), "segmentos": int(len(grupo)),
                "segmento_ids": [int(s) for s in grupo["segmento_id"].head(200)], "extensao_m": round(extensao_m)}
