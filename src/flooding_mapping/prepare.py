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


def make_grid(area: gpd.GeoDataFrame, spacing_m: float) -> gpd.GeoDataFrame:
    """Square cells of ``spacing_m`` covering ``area`` (metric CRS).

    Cells are clipped to the area, so together they tile it exactly. Each
    cell gets a stable id from its lower-left corner and an origin point:
    the cell centroid when it lies inside the area, otherwise a point on the
    clipped cell.
    """
    xmin, ymin, xmax, ymax = area.total_bounds
    x0 = np.floor(xmin / spacing_m) * spacing_m
    y0 = np.floor(ymin / spacing_m) * spacing_m
    xs = np.arange(x0, xmax, spacing_m)
    ys = np.arange(y0, ymax, spacing_m)
    cells = gpd.GeoDataFrame(
        {"origin_id": [f"g{int(x)}_{int(y)}" for x in xs for y in ys]},
        geometry=[box(x, y, x + spacing_m, y + spacing_m) for x in xs for y in ys],
        crs=area.crs,
    )
    territory = area.union_all()
    cells["geometry"] = cells.intersection(territory)
    cells = cells[~cells.is_empty & (cells.area > 0)].reset_index(drop=True)
    centroids = cells.centroid
    inside = centroids.within(territory)
    cells["origin"] = centroids.where(inside, cells.representative_point())
    cells["centroid_inside"] = inside
    return cells


def allocate_population(cells: gpd.GeoDataFrame, tracts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Allocate tract population to cells assuming uniform density per tract."""
    tracts = tracts[["CD_SETOR", "population", "geometry"]].copy()
    tracts["tract_area"] = tracts.area
    pieces = gpd.overlay(cells[["origin_id", "geometry"]], tracts, how="intersection",
                         keep_geom_type=True)
    pieces["population"] = pieces["population"] * pieces.area / pieces["tract_area"]
    totals = pieces.groupby("origin_id")["population"].sum()
    result = cells.copy()
    result["population"] = result["origin_id"].map(totals).fillna(0.0)
    return result


def origins(config: dict) -> gpd.GeoDataFrame:
    """Build origin points with allocated population from the configuration."""
    tracts = load_tracts(resolve(config["sources"]["ibge_setores"]["destino"]),
                         CD_MUN_POA, config["crs_metric"])
    cells = make_grid(municipality_polygon(tracts), config["grid"]["espacamento_m"])
    cells = allocate_population(cells, tracts)
    cells["has_population"] = cells["population"] > 0
    return gpd.GeoDataFrame(
        cells[["origin_id", "population", "has_population", "centroid_inside"]],
        geometry=cells["origin"], crs=cells.crs,
    )
