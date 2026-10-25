"""Preparation of the study area, origins and destinations."""

import argparse
import json
import subprocess
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from .config import load_config, resolve

CD_MUN_POA = "4314902"
POPULATION_FIELD = "v0001"  # Censo 2022: total de pessoas


def drop_empty_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy without rows that contain no values."""
    return frame.dropna(how="all").reset_index(drop=True)


def load_tracts(path: str | Path, cd_mun: str, crs: str) -> gpd.GeoDataFrame:
    """Load census tracts of one municipality, one row per tract.

    The IBGE file stores multipart tracts as several rows with repeated
    attributes; they are dissolved so population is counted once.
    """
    tracts = gpd.read_file(path, where=f"CD_MUN = '{cd_mun}'")
    if tracts.empty:
        raise ValueError(f"No tracts for CD_MUN={cd_mun} in {path}")
    repeated = tracts.groupby("CD_SETOR")[POPULATION_FIELD].nunique()
    if (repeated > 1).any():
        raise ValueError("Multipart tract rows disagree on population")
    tracts = tracts.dissolve(by="CD_SETOR", aggfunc="first", as_index=False)
    tracts = tracts[["CD_SETOR", "SITUACAO", "CD_TIPO", POPULATION_FIELD, "geometry"]]
    tracts = tracts.rename(columns={POPULATION_FIELD: "population"}).to_crs(crs)
    tracts["geometry"] = tracts.geometry.make_valid()
    return tracts


def municipality_polygon(tracts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Union of all tracts: the municipal territory in the tracts' CRS."""
    return gpd.GeoDataFrame(geometry=[tracts.union_all()], crs=tracts.crs)


def clip_osm(
    source: str | Path,
    output: str | Path,
    area: gpd.GeoDataFrame,
    margin_m: float,
) -> dict:
    """Extract the OSM PBF around ``area`` (buffered by ``margin_m``).

    Uses osmium's default complete_ways strategy so ways crossing the
    boundary are kept whole.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    polygon_path = output.with_suffix(".clip.geojson")
    clip = area.buffer(margin_m).to_crs("EPSG:4326")
    polygon_path.write_text(clip.to_json(), encoding="utf-8")
    command = ["osmium", "extract", "--polygon", str(polygon_path), "--strategy",
               "complete_ways", "--set-bounds", "--overwrite", "-o", str(output), str(source)]
    started = time.perf_counter()
    subprocess.run(command, check=True, capture_output=True, text=True)
    return {
        "command": " ".join(command),
        "margin_m": margin_m,
        "seconds": round(time.perf_counter() - started, 1),
        "output_bytes": output.stat().st_size,
    }
