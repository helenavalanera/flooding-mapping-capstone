"""RS municipalities (id, name, region, area, population, point) from the IBGE tract mesh.

The 2022 census tract mesh already ships in ``data/raw`` (see ``ingest.py``), so no new
download is needed. Tracts are dissolved by municipality; the two lagoon "tracts"
(``CD_MUN`` 0) are not municipalities and are dropped. The representative point lies
inside the polygon, unlike the centroid of a concave municipality.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd

from ..config import load_config, resolve

POPULATION_FIELD = "v0001"  # Censo 2022: total de pessoas (as in prepare.py)
FIELDS = ["CD_MUN", "NM_MUN", "NM_RGI", "NM_RGINT", "AREA_KM2", POPULATION_FIELD]
OUTPUT = "data/interim/municipios.parquet"


def build(tracts_path: str | Path) -> gpd.GeoDataFrame:
    """One row per municipality, in EPSG:4326, with a representative point."""
    tracts = gpd.read_file(tracts_path, columns=FIELDS)
    tracts = tracts[tracts["CD_MUN"].astype(str) != "0"].copy()
    tracts[POPULATION_FIELD] = tracts[POPULATION_FIELD].astype(float)
    towns = tracts.dissolve(
        by="CD_MUN",
        aggfunc={"NM_MUN": "first", "NM_RGI": "first", "NM_RGINT": "first",
                 "AREA_KM2": "sum", POPULATION_FIELD: "sum"},
    ).reset_index()
    towns = towns.rename(columns={
        "CD_MUN": "ibge", "NM_MUN": "nome", "NM_RGI": "regiao_imediata",
        "NM_RGINT": "regiao_intermediaria", "AREA_KM2": "area_km2",
        POPULATION_FIELD: "populacao"})
    towns["ibge"] = towns["ibge"].astype(str)
    towns = towns.to_crs("EPSG:4326")
    point = towns.geometry.representative_point()
    towns["lat"], towns["lon"] = point.y.round(5), point.x.round(5)
    towns["densidade_hab_km2"] = (towns["populacao"] / towns["area_km2"]).round(2)
    return towns.sort_values("ibge").reset_index(drop=True)


def main() -> None:
    argparse.ArgumentParser(description="Build the RS municipality table").parse_args()
    config = load_config()
    towns = build(resolve(config["sources"]["ibge_setores"]["destino"]))
    out = resolve(OUTPUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    towns.to_parquet(out)
    print(f"{len(towns)} municípios, {towns['populacao'].sum():,.0f} habitantes -> {OUTPUT}")


if __name__ == "__main__":
    main()
