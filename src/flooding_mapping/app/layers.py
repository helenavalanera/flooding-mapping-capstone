"""Static layers of the state interface, derived once from the data and kept small.

Municipal boundaries, the road network, the S2iD occurrences and a lightweight segment index
are produced here from ``data/interim`` (which is not versioned) and written under
``app/static/data`` (published) and ``app/data`` (used only when the site is built, to match
live blockages to segments). Geometry is simplified for the web; analysis never reads these
files.
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ..config import resolve
from ..ingestion import s2id

HERE = Path(__file__).parent
STATIC_DATA = HERE / "static" / "data"
BUILD_DATA = HERE / "data"
TOWN_TOLERANCE_DEG = 0.005   # about 550 m
ROAD_TOLERANCE_DEG = 0.001   # about 110 m
SEGMENT_TOLERANCE_M = 50.0
RECENT_DAYS = 90


def _write_geojson(frame: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frame.to_json(drop_id=True, na="null", show_bbox=False))


def municipalities(towns: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    layer = towns[["ibge", "nome", "populacao", "regiao_imediata", "geometry"]].copy()
    layer["populacao"] = layer["populacao"].astype(int)
    layer["geometry"] = layer.geometry.simplify(TOWN_TOLERANCE_DEG, preserve_topology=True)
    return layer


def roads(trechos: gpd.GeoDataFrame, stretches: pd.DataFrame) -> gpd.GeoDataFrame:
    """Built stretches with the simulated impact and the traffic, for the map."""
    built = trechos[~trechos["situacao_fisica"].str.upper().eq("PLANEJADA")]
    keep = ["codigo_sre", "nome", "rede", "vdm", "km_inicio", "km_final", "geometry"]
    layer = built[["objectid"] + keep].merge(
        stretches[["objectid", "ponte", "pop_isolada", "desvio_km"]], on="objectid", how="left")
    layer["desvio_km"] = layer["desvio_km"].where(layer["desvio_km"].map(lambda v: pd.notna(v) and v < 1e9))
    layer["ponte"] = layer["ponte"].fillna(False).astype(bool)
    layer["geometry"] = layer.geometry.simplify(ROAD_TOLERANCE_DEG, preserve_topology=True)
    return gpd.GeoDataFrame(layer.drop(columns="objectid"), geometry="geometry", crs=trechos.crs)


def segment_index(segments: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Segments with simplified geometry: enough to match a blockage to a segment by position."""
    index = segments[["segmento_id", "objectid", "codigo_sre", "nome", "km_ini", "km_fim", "geometry"]].copy()
    index["geometry"] = index.geometry.simplify(SEGMENT_TOLERANCE_M)
    return index


def occurrences(records: pd.DataFrame, towns: pd.DataFrame, codes: tuple[int, ...] = s2id.HYDRO_BROAD) -> dict:
    """Hydrological S2iD records of the last ``RECENT_DAYS`` days before the latest export."""
    cutoff = records["data_evento"].max()
    recent = records[records["cobrade"].isin(codes) & (records["data_evento"] >= cutoff - timedelta(days=RECENT_DAYS))]
    names = towns.set_index("ibge")["nome"]
    rows = [{"ibge": r.ibge, "nome": names.get(r.ibge, r.ibge), "data": str(r.data_evento.date()),
             "tipo": r.cobrade_nome, "cobrade": int(r.cobrade), "status": r.status}
            for r in recent.sort_values("data_evento", ascending=False).itertuples()]
    return {"fonte": "S2iD/MIDR, Relatório Gerencial - Danos Informados (exportação manual)",
            "natureza": "ocorrência registrada (observação), com atraso e viés de notificação",
            "ate": str(cutoff.date()), "janela_dias": RECENT_DAYS, "registros": rows}


def main() -> None:
    argparse.ArgumentParser(description="Build the static layers of the state interface").parse_args()
    towns = gpd.read_parquet(resolve("data/interim/municipios.parquet"))
    trechos = gpd.read_parquet(resolve("data/interim/daer_trechos.parquet"))
    segments = gpd.read_parquet(resolve("data/interim/daer_segmentos.parquet"))
    impact = pd.read_parquet(resolve("data/interim/impacto_rs.parquet"))
    from ..geospatial import impact as impact_module

    stretches = impact_module.by_stretch(impact, trechos.drop(columns="geometry"))
    _write_geojson(municipalities(towns), STATIC_DATA / "municipios.geojson")
    _write_geojson(roads(trechos, stretches), STATIC_DATA / "rodovias.geojson")
    BUILD_DATA.mkdir(parents=True, exist_ok=True)
    segment_index(segments).to_parquet(BUILD_DATA / "segmentos_indice.parquet")
    impact[["segmento_id", "ponte", "pop_isolada", "desvio_km", "vdm", "veiculos_km_dia"]].replace(
        [float("inf")], [None]).to_parquet(BUILD_DATA / "impacto_segmentos.parquet")
    (STATIC_DATA / "ocorrencias.json").write_text(json.dumps(
        occurrences(pd.read_parquet(resolve("data/interim/s2id_rs.parquet")), towns), ensure_ascii=False))
    (STATIC_DATA / "impacto_rs.json").write_text(resolve("outputs/web/impacto_rs.json").read_text())
    for path in sorted(list(STATIC_DATA.glob("*")) + list(BUILD_DATA.glob("*"))):
        print(f"{path.relative_to(HERE)}: {path.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
