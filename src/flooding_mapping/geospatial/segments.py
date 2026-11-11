"""Analytical segments of about 1 km along each official DAER stretch.

Each stretch is cut into ``n = max(1, round(length / 1 km))`` pieces of equal length, so
pieces measure between about 0.67 and 1.5 km (a stretch under 1.5 km stays whole). Every
piece keeps ``objectid`` (the unique stretch id) and ``codigo_sre``.

Kilometre marks are interpolated linearly: the piece that starts at fraction ``f`` of the
line gets ``km_inicio + f * (km_final - km_inicio)``. This assumes the line runs from
``km_inicio`` to ``km_final``, which holds for every stretch in the August 2026 layer
(no reversed line), and that the vector length matches the nominal extent. Where it does
not (``razao_vetor_nominal`` far from 1), the km of a piece is only approximate; the
matching step uses the blockage coordinates as a second check.
"""

from __future__ import annotations

import argparse

import geopandas as gpd
import pandas as pd
from shapely.ops import linemerge, substring

from ..config import load_config, resolve

OUTPUT = "data/interim/daer_segmentos.parquet"
KEEP = ["objectid", "codigo_sre", "nome", "rede", "km_inicio", "km_final"]


def as_line(geometry):
    """A single LineString; a multipart stretch that does not merge is an explicit error."""
    line = linemerge(geometry) if geometry.geom_type == "MultiLineString" else geometry
    if line.geom_type != "LineString":
        raise ValueError(f"Stretch geometry is not a single line: {geometry.geom_type}")
    return line


def segment(trechos: gpd.GeoDataFrame, target_km: float = 1.0,
            crs: str = "EPSG:5880") -> gpd.GeoDataFrame:
    """Cut every stretch into pieces of about ``target_km``; lengths are measured in ``crs``."""
    metric = trechos.to_crs(crs)
    rows = []
    for stretch in metric.itertuples():
        line = as_line(stretch.geometry)
        n = max(1, round(line.length / (target_km * 1000)))
        km0, km1 = stretch.km_inicio, stretch.km_final
        nominal = stretch.km_final - stretch.km_inicio
        ratio = line.length / 1000 / nominal if nominal > 0 else float("nan")
        for i in range(n):
            piece = substring(line, i / n, (i + 1) / n, normalized=True)
            rows.append({
                **{c: getattr(stretch, c) for c in KEEP},
                "segmento_id": f"{stretch.objectid}-{i:03d}", "ordem": i, "n_segmentos": n,
                "km_ini": km0 + (km1 - km0) * i / n, "km_fim": km0 + (km1 - km0) * (i + 1) / n,
                "comprimento_m": piece.length, "razao_vetor_nominal": ratio, "geometry": piece,
            })
    return gpd.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs=crs)


def main() -> None:
    argparse.ArgumentParser(description="Segment the DAER stretches").parse_args()
    daer = load_config()["daer"]
    trechos = gpd.read_parquet(resolve("data/interim/daer_trechos.parquet"))
    segments = segment(trechos, daer["segmento_km"], daer["crs_metrico"])
    out = resolve(OUTPUT)
    segments.to_parquet(out)
    km = segments["comprimento_m"] / 1000
    print(f"{len(trechos)} trechos -> {len(segments)} segmentos; comprimento mediano "
          f"{km.median():.2f} km (mín {km.min():.2f}, máx {km.max():.2f}); "
          f"extensão total {km.sum():,.0f} km -> {OUTPUT}")


if __name__ == "__main__":
    main()
