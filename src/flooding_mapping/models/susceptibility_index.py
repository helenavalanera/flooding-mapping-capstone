"""Explainable physical susceptibility index for the DAER road segments.

This is an *index*, not a model and not a probability. It ranks segments by how low they sit
and how close they are to water, three terrain facts with explicit equal weights:

    baixa_altitude    = -z(elevation)               (low ground)
    baixa_cota_local  = -z(elevation - 1 km mean)    (a local depression)
    perto_da_agua     = -z(log(1 + distance to the nearest OSM waterway))

``z`` is a robust z-score (median and MAD, clipped at +-3) over the whole state network. The
index is the mean of the components, shown as a percentile (100 = most susceptible). Nothing
is fitted, so nothing can overfit the 16-ish labelled segments we have, and nothing here
supports reading the number as a flood probability: there are not enough segment-level
labels to validate it. It is compared with the plain "lowest elevation first" rule so the
reader can see what the extra terrain facts add, if anything.
"""

from __future__ import annotations

import argparse
import json
import subprocess

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from ..config import load_config, resolve
from ..geospatial import relief as relief_module
from ..ingestion import s2id

COMPONENTS = ["baixa_altitude", "baixa_cota_local", "perto_da_agua"]
WATER_TAGS = "w/waterway=river,stream,canal,drain,ditch"


def robust_z(values: pd.Series, clip: float = 3.0) -> pd.Series:
    median = values.median()
    scale = 1.4826 * (values - median).abs().median()
    return ((values - median) / (scale if scale > 0 else values.std())).clip(-clip, clip)


def distance_to_water(midpoints: gpd.GeoSeries, waterways: gpd.GeoDataFrame) -> pd.Series:
    """Metres to the nearest waterway (both in the same metric CRS)."""
    from shapely import STRtree

    tree = STRtree(waterways.geometry.values)
    _, dist = tree.query_nearest(midpoints.values, return_distance=True, all_matches=False)  # one answer per point
    return pd.Series(dist, index=midpoints.index)


def build_index(features: pd.DataFrame) -> pd.DataFrame:
    """Components, the index and its percentile (NaN where the terrain is unknown)."""
    out = features.copy()
    out["baixa_altitude"] = -robust_z(features["elev"])
    out["baixa_cota_local"] = -robust_z(features["rel_elev_500"])
    out["perto_da_agua"] = -robust_z(np.log1p(features["dist_agua_m"]))
    out["indice"] = out[COMPONENTS].mean(axis=1, skipna=False)
    out["percentil"] = out["indice"].rank(pct=True) * 100
    out["percentil_regra_elevacao"] = (-features["elev"]).rank(pct=True) * 100
    return out


def compare_on_labelled(index: pd.DataFrame, labelled_ids: list[str]) -> dict:
    """Where the segments of known blockages fall under the index and under the elevation rule."""
    rows = index.loc[index.index.intersection(labelled_ids)].dropna(subset=["percentil"])
    if rows.empty:
        return {"segmentos_rotulados": 0}
    describe = lambda s: {"mediana": round(float(s.median()), 1), "no_top_20pct": round(float((s >= 80).mean()), 3)}  # noqa: E731
    return {"segmentos_rotulados": len(rows), "indice": describe(rows["percentil"]),
            "regra_so_elevacao": describe(rows["percentil_regra_elevacao"]),
            "aviso": "poucos segmentos rotulados: descritivo, sem valor estatístico"}


def municipal_check(index: pd.DataFrame, towns_of_segment: pd.Series, records: pd.DataFrame, towns: pd.DataFrame) -> dict:
    """Do municipalities whose roads score higher declare more hydrological disasters per km?"""
    mean = index["percentil"].groupby(towns_of_segment.reindex(index.index)).mean()
    km = (index["comprimento_m"] / 1000).groupby(towns_of_segment.reindex(index.index)).sum()
    count = records[records["cobrade"].isin(s2id.HYDRO_STRICT)].groupby("ibge").size()
    frame = pd.DataFrame({"indice_medio": mean, "km": km}).join(count.rename("registros")).fillna({"registros": 0})
    frame = frame[frame["km"] > 0]
    rho = spearmanr(frame["indice_medio"], frame["registros"] / frame["km"])
    rho_elev = spearmanr(index["percentil_regra_elevacao"].groupby(towns_of_segment.reindex(index.index)).mean().reindex(frame.index),
                         frame["registros"] / frame["km"])
    return {"municipios": len(frame), "spearman_indice_x_registros_por_km": round(float(rho.statistic), 3),
            "spearman_so_elevacao_x_registros_por_km": round(float(rho_elev.statistic), 3),
            "aviso": "correlação com o número de registros municipais por km de rodovia; confundida pela chuva, "
                     "pela população e pelo hábito de notificar. Não valida o índice como probabilidade."}


def main() -> None:
    argparse.ArgumentParser(description="Physical susceptibility index of the DAER segments").parse_args()
    config = load_config()
    crs, manifest = config["daer"]["crs_metrico"], resolve(config["paths"]["manifest"])
    segments = gpd.read_parquet(resolve("data/interim/daer_segmentos.parquet"))
    trechos = gpd.read_parquet(resolve("data/interim/daer_trechos.parquet")).drop(columns="geometry")
    segments = segments.merge(trechos[["objectid", "situacao_fisica"]], on="objectid", how="left")
    segments = segments[~segments["situacao_fisica"].str.upper().eq("PLANEJADA")].set_index("segmento_id")
    mid = segments.geometry.interpolate(0.5, normalized=True)
    lonlat = gpd.GeoSeries(mid, crs=crs).to_crs("EPSG:4326")
    points = pd.DataFrame({"lon": lonlat.x, "lat": lonlat.y}, index=segments.index)

    terrain = relief_module.relief(points, resolve("data/raw/dem"), manifest)
    water_pbf = resolve("data/interim/waterways_sul.osm.pbf")
    subprocess.run(["osmium", "tags-filter", str(resolve(config["sources"]["osm"]["destino"])), WATER_TAGS,
                    "-o", str(water_pbf), "--overwrite"], check=True)
    from ..susceptibility import read_waterways

    waterways = read_waterways(water_pbf, crs)
    features = terrain.assign(dist_agua_m=distance_to_water(gpd.GeoSeries(mid.values, index=segments.index, crs=crs), waterways),
                              comprimento_m=segments["comprimento_m"], objectid=segments["objectid"])
    index = build_index(features)
    towns = gpd.read_parquet(resolve("data/interim/municipios.parquet"))
    inside = gpd.sjoin(gpd.GeoDataFrame(geometry=lonlat.values, index=segments.index, crs="EPSG:4326"),
                       towns[["ibge", "geometry"]], predicate="within")
    town_of = inside[~inside.index.duplicated()]["ibge"]
    matched = pd.read_parquet(resolve("data/interim/crbm_segmentos.parquet"))
    labelled = matched.loc[matched["status"].isin(["ok", "ok_sem_coordenada"]), "segmentos"].str.split(";").explode().tolist()
    report = {
        "natureza": "índice físico relativo, NÃO é probabilidade nem foi validado em nível de segmento",
        "componentes": COMPONENTS, "pesos": "iguais", "segmentos": int(len(index)),
        "sem_terreno": int(index["indice"].isna().sum()), "waterways_osm": int(len(waterways)),
        "correlacao_entre_componentes": index[COMPONENTS].corr().round(2).to_dict(),
        "segmentos_com_bloqueio_observado": compare_on_labelled(index, labelled),
        "verificacao_municipal_fraca": municipal_check(index, town_of, pd.read_parquet(resolve("data/interim/s2id_rs.parquet")), towns)}
    index.to_parquet(resolve("data/interim/indice_fisico_segmentos.parquet"))
    out = resolve("reports/ml/indice_suscetibilidade.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("segmentos", "sem_terreno", "waterways_osm")}),
          report["segmentos_com_bloqueio_observado"], report["verificacao_municipal_fraca"], sep="\n")


if __name__ == "__main__":
    main()
