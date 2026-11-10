"""Builds the street table the routing service loads: OSM segments + terrain index + street names.

Reads ``data/interim`` (segments of the OSM clip, terrain features) and writes
``data/processed/rede_poa.parquet`` (not versioned, like every derived dataset). The service only
needs numpy, pandas and scipy to use it. Segments without terrain features keep a missing
percentile: they have no risk estimate, which is different from low risk.
"""

from __future__ import annotations

import argparse
import json

import geopandas as gpd
import osmium
import pandas as pd
import shapely

from .config import load_config, resolve
from .risco_trecho import COMPONENTES, indice_fisico

OUTPUT = "data/processed/rede_poa.parquet"
TERRENO = ["elev", "rel_elev_250", "slope", "height_above_water", "log_flow_acc"]


def nomes_das_vias(pbf) -> dict[int, str]:
    """OSM way id -> street name, for the ways that have one."""
    nomes = {}
    for obj in osmium.FileProcessor(str(pbf), osmium.osm.WAY):
        if obj.tags.get("highway") and obj.tags.get("name"):
            nomes[obj.id] = obj.tags["name"]
    return nomes


def construir(segmentos: gpd.GeoDataFrame, terreno: pd.DataFrame, nomes: dict[int, str]) -> pd.DataFrame:
    """One row per segment: graph columns, endpoints in lon/lat, terrain percentile and its parts."""
    lonlat = segmentos.geometry.to_crs("EPSG:4326")
    inicio, fim = shapely.get_point(lonlat.values, 0), shapely.get_point(lonlat.values, -1)
    tabela = pd.DataFrame({
        "segmento_id": segmentos["segment_id"].to_numpy(), "u": segmentos["u"].to_numpy(), "v": segmentos["v"].to_numpy(),
        "comprimento_m": segmentos["length_m"].to_numpy(), "highway": segmentos["highway"].to_numpy(),
        "oneway": segmentos["oneway"].to_numpy(), "drive": segmentos["drive"].to_numpy(), "walk": segmentos["walk"].to_numpy(),
        "lon0": shapely.get_x(inicio), "lat0": shapely.get_y(inicio), "lon1": shapely.get_x(fim), "lat1": shapely.get_y(fim),
        "nome": segmentos["way_id"].map(nomes).to_numpy()})
    indice = indice_fisico(terreno.set_index("segment_id")[TERRENO])
    extras = indice[["percentil"] + COMPONENTES].join(terreno.set_index("segment_id")[TERRENO])
    return tabela.join(extras.astype("float32"), on="segmento_id")


def main() -> None:
    argparse.ArgumentParser(description="Street table of Porto Alegre for the routing service").parse_args()
    segmentos = gpd.read_parquet(resolve("data/interim/segments.parquet"))
    terreno = pd.read_parquet(resolve("data/interim/susceptibility_features_v2.parquet"))
    tabela = construir(segmentos, terreno, nomes_das_vias(resolve("data/interim/poa.osm.pbf")))
    saida = resolve(OUTPUT)
    saida.parent.mkdir(parents=True, exist_ok=True)
    tabela.to_parquet(saida)
    resumo = {"segmentos": len(tabela), "com_indice_fisico": int(tabela["percentil"].notna().sum()),
              "dirigiveis": int(tabela["drive"].sum()), "caminhaveis": int(tabela["walk"].sum()),
              "com_nome": int(tabela["nome"].notna().sum()), "tamanho_mb": round(saida.stat().st_size / 1e6, 1)}
    print(json.dumps(resumo))


if __name__ == "__main__":
    main()
