"""Points of interest (POIs) of Porto Alegre from the OpenStreetMap clip: what a flood-prone stretch can cut people off from.

Reads ``data/interim/poa.osm.pbf`` and writes ``data/processed/pois_poa.parquet`` (not versioned, like every derived dataset):
one row per hospital, clinic, pharmacy, school, police or fire station, community centre, supermarket or transport terminal.
A POI is an *OpenStreetMap volunteer record*: it can be out of date or missing, and the category says what the place is
for, never that it is open, staffed or usable as a shelter.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import resolve

ENTRADA = "data/interim/poa.osm.pbf"
SAIDA = "data/processed/pois_poa.parquet"

# (tag, value) -> (categoria, tipo). Order matters only for the first match of an object.
CATEGORIAS = {
    ("amenity", "hospital"): ("saude", "hospital"), ("healthcare", "hospital"): ("saude", "hospital"),
    ("amenity", "clinic"): ("saude", "clínica"), ("healthcare", "clinic"): ("saude", "clínica"),
    ("amenity", "doctors"): ("saude", "consultório"), ("amenity", "pharmacy"): ("saude", "farmácia"),
    ("amenity", "school"): ("educacao", "escola"), ("amenity", "kindergarten"): ("educacao", "creche"),
    ("amenity", "college"): ("educacao", "faculdade"), ("amenity", "university"): ("educacao", "universidade"),
    ("amenity", "police"): ("seguranca", "polícia"), ("amenity", "fire_station"): ("seguranca", "bombeiros"),
    ("amenity", "community_centre"): ("comunidade", "centro comunitário"),
    ("shop", "supermarket"): ("abastecimento", "supermercado"), ("amenity", "marketplace"): ("abastecimento", "mercado"),
    ("amenity", "bus_station"): ("transporte", "terminal de ônibus"), ("amenity", "ferry_terminal"): ("transporte", "terminal fluvial"),
    ("railway", "station"): ("transporte", "estação de trem"), ("railway", "halt"): ("transporte", "estação de trem"),
}
# How much a place that people depend on weighs in the priority of an area (an explicit editorial choice, not a fit).
PESO = {"saude": 3.0, "seguranca": 3.0, "educacao": 2.0, "comunidade": 1.0, "abastecimento": 1.0, "transporte": 1.0}
ROTULOS = {"saude": "saúde", "seguranca": "segurança", "educacao": "educação", "comunidade": "comunidade",
           "abastecimento": "abastecimento", "transporte": "transporte"}


def _classificar(tags) -> tuple[str, str] | None:
    for (chave, valor), destino in CATEGORIAS.items():
        if tags.get(chave) == valor:
            return destino
    return None


def extrair(pbf) -> pd.DataFrame:
    """POIs of the clip: nodes at their position, ways (buildings) at the mean of their nodes."""
    import osmium

    linhas = []
    for obj in osmium.FileProcessor(str(pbf), osmium.osm.NODE | osmium.osm.WAY).with_locations():
        destino = _classificar(obj.tags)
        if destino is None:
            continue
        if isinstance(obj, osmium.osm.Node):
            if not obj.location.valid():
                continue
            lon, lat, prefixo = obj.location.lon, obj.location.lat, "n"
        else:
            pontos = [(n.lon, n.lat) for n in obj.nodes if n.location.valid()]
            if not pontos:
                continue
            lon, lat, prefixo = sum(p[0] for p in pontos) / len(pontos), sum(p[1] for p in pontos) / len(pontos), "w"
        linhas.append({"poi_id": f"{prefixo}{obj.id}", "nome": obj.tags.get("name"), "categoria": destino[0], "tipo": destino[1],
                       "lon": round(float(lon), 6), "lat": round(float(lat), 6)})
    pois = pd.DataFrame(linhas, columns=["poi_id", "nome", "categoria", "tipo", "lon", "lat"])
    return pois.drop_duplicates("poi_id").reset_index(drop=True)


def carregar(caminho=None) -> pd.DataFrame | None:
    """The built table, or ``None`` when it was not built (the service then runs without the POI layer)."""
    arquivo = Path(caminho) if caminho else resolve(SAIDA)
    if not arquivo.exists():
        return None
    return pd.read_parquet(arquivo)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pbf", default=ENTRADA)
    ap.add_argument("--saida", default=SAIDA)
    args = ap.parse_args()
    pois = extrair(resolve(args.pbf))
    destino = resolve(args.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pois.to_parquet(destino, index=False)
    print(f"{len(pois)} pontos de interesse -> {destino}")
    print(pois.groupby(["categoria", "tipo"]).size().to_string())


if __name__ == "__main__":
    main()
