"""Terrain at the road segments from Copernicus DEM GLO-30 (30 m), tile by tile.

For each point: elevation, elevation minus the mean of the surrounding ~1 km square
(``rel_elev_500``: negative means the point sits in a local low) and slope. Tiles are 1 degree
squares; each is read once, its neighbourhood mean is computed on the whole tile, and it is
dropped, so the whole state never has to fit in memory. Windows that cross a tile edge are
clipped at that edge (a small error within 500 m of a tile border). Tiles over open sea do not
exist and are skipped.
"""

from __future__ import annotations

import math
import urllib.error
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol
from scipy.ndimage import uniform_filter

from ..ingest import download

TILE_URL = "https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"
WINDOW_PX = 33          # about 1 km at 30 m: the mean covers +-500 m
CELL_M = 30.0


def tile_name(lat: int, lon: int) -> str:
    """Copernicus tile named by its lower-left corner, e.g. S30_00_W052_00."""
    return (f"Copernicus_DSM_COG_10_{'S' if lat < 0 else 'N'}{abs(lat):02d}_00_"
            f"{'W' if lon < 0 else 'E'}{abs(lon):03d}_00_DEM")


def needed_tiles(lon: np.ndarray, lat: np.ndarray) -> list[tuple[int, int]]:
    return sorted({(math.floor(y), math.floor(x)) for x, y in zip(lon, lat)})


def ensure_tiles(tiles: list[tuple[int, int]], root: Path, manifest: Path) -> dict[tuple[int, int], Path]:
    """Download the missing tiles (recording provenance); tiles that do not exist are skipped."""
    found = {}
    for lat, lon in tiles:
        name = tile_name(lat, lon)
        try:
            entry = download(TILE_URL.format(name=name), root / f"{name}.tif", manifest, timeout=300)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                continue
            raise
        found[(lat, lon)] = root / f"{name}.tif"
    return found


def tile_relief(path: Path, lon: np.ndarray, lat: np.ndarray) -> pd.DataFrame:
    """Elevation, local relief and slope at the given points, all inside one tile."""
    with rasterio.open(path) as src:
        dem = src.read(1).astype("float32")
        nodata = src.nodata
        transform = src.transform
    if nodata is not None:
        dem[dem == nodata] = np.nan
    rows, cols = rowcol(transform, lon, lat)
    rows = np.clip(rows, 0, dem.shape[0] - 1)
    cols = np.clip(cols, 0, dem.shape[1] - 1)
    filled = np.where(np.isnan(dem), np.nanmean(dem), dem)
    mean = uniform_filter(filled, size=WINDOW_PX, mode="nearest")
    dy, dx = np.gradient(filled, CELL_M)
    slope = np.degrees(np.arctan(np.hypot(dx, dy)))
    elevation = dem[rows, cols]
    return pd.DataFrame({"elev": elevation, "rel_elev_500": elevation - mean[rows, cols], "slope": slope[rows, cols]})


def relief(points_lonlat: pd.DataFrame, root: Path, manifest: Path) -> pd.DataFrame:
    """Relief features for points with ``lon`` and ``lat`` columns (index kept); NaN where no tile."""
    lon, lat = points_lonlat["lon"].to_numpy(), points_lonlat["lat"].to_numpy()
    tiles = ensure_tiles(needed_tiles(lon, lat), root, manifest)
    out = pd.DataFrame(np.nan, index=points_lonlat.index, columns=["elev", "rel_elev_500", "slope"])
    key_lat, key_lon = np.floor(lat).astype(int), np.floor(lon).astype(int)
    for (tile_lat, tile_lon), path in tiles.items():
        inside = (key_lat == tile_lat) & (key_lon == tile_lon)
        out.loc[inside] = tile_relief(path, lon[inside], lat[inside]).to_numpy()
    return out
