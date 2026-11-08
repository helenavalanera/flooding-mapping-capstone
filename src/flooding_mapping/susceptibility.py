"""Prototype susceptibility of road segments to reported water-accumulation blockages.

Target: a road segment lies within ``raio_positivo_m`` of a blockage reported by
EPTC (positive); all other segments are *unlabelled*, not negative — absence of
a report does not prove absence of water. The model therefore ranks segments by
how similar their terrain is to reported locations; it does not predict real
flooding, and it inherits the reporting bias of the events.

Features are physical only (Copernicus DEM, OSM waterways); road class is left
out because it mostly encodes where EPTC tends to report.
"""

import argparse
import json
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject
from scipy import ndimage
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .config import load_config, resolve

BASE_FEATURES = ["elev", "rel_elev_250", "rel_elev_500", "slope", "dist_water", "height_above_water"]
# Drainage features: flow paths and wetness from the DEM, density of OSM drainage lines.
FEATURES = BASE_FEATURES + ["log_flow_acc", "twi", "drainage_density_250"]
FEATURES_VERSION = 2
WATERWAYS = {"stream", "canal", "drain", "river", "ditch"}


def build_dem(tiles: list, area: gpd.GeoDataFrame, crs: str, margin_m: float = 1000,
              resolution: float = 30) -> tuple[np.ndarray, rasterio.Affine]:
    """Mosaic DEM tiles over ``area`` (+margin) reprojected to ``crs``."""
    bounds = area.to_crs(crs).buffer(margin_m).to_crs("EPSG:4326").total_bounds
    sources = [rasterio.open(t) for t in tiles]
    try:
        mosaic, transform = merge(sources, bounds=tuple(bounds))
        src_crs = sources[0].crs
    finally:
        for source in sources:
            source.close()
    height, width = mosaic.shape[1:]
    dst_transform, dst_w, dst_h = calculate_default_transform(
        src_crs, crs, width, height, *bounds, resolution=resolution)
    dem = np.full((dst_h, dst_w), np.nan, dtype="float32")
    reproject(mosaic[0].astype("float32"), dem, src_transform=transform, src_crs=src_crs,
              dst_transform=dst_transform, dst_crs=crs, resampling=Resampling.bilinear,
              dst_nodata=np.nan)
    return dem, dst_transform


def fill_depressions(dem: np.ndarray, epsilon: float = 1e-4) -> np.ndarray:
    """Priority-flood depression filling (with a tiny gradient so flats drain).

    Cells on the raster edge or next to NaN are outlets.
    """
    import heapq

    rows, cols = dem.shape
    filled = np.where(np.isnan(dem), -np.inf, dem).astype("float64")
    done = np.zeros(dem.shape, bool)
    heap = []
    nan = np.isnan(dem)
    edge = np.zeros(dem.shape, bool)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    edge |= ndimage.binary_dilation(nan) & ~nan
    for r, c in zip(*np.nonzero(edge & ~nan)):
        heapq.heappush(heap, (filled[r, c], r, c))
        done[r, c] = True
    done |= nan
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    while heap:
        z, r, c = heapq.heappop(heap)
        for dr, dc in offsets:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not done[nr, nc]:
                done[nr, nc] = True
                filled[nr, nc] = max(filled[nr, nc], z + epsilon)
                heapq.heappush(heap, (filled[nr, nc], nr, nc))
    filled[nan] = np.nan
    return filled


def flow_accumulation(filled: np.ndarray) -> np.ndarray:
    """D8 flow accumulation (number of upstream cells, including the cell)."""
    rows, cols = filled.shape
    z = np.where(np.isnan(filled), np.inf, filled)
    padded = np.pad(z, 1, constant_values=np.inf)
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    best_drop = np.zeros(z.shape)
    receiver = np.full(z.shape, -1, dtype=np.int64)
    index = np.arange(z.size).reshape(z.shape)
    for dr, dc in offsets:
        neighbour = padded[1 + dr:1 + dr + rows, 1 + dc:1 + dc + cols]
        drop = (z - neighbour) / np.hypot(dr, dc)
        better = np.isfinite(neighbour) & (drop > best_drop)
        best_drop[better] = drop[better]
        target = np.roll(np.roll(index, -dr, axis=0), -dc, axis=1)
        receiver[better] = target[better]
    accumulation = np.ones(z.size)
    flat_receiver = receiver.ravel()
    for cell in np.argsort(-z.ravel(), kind="stable"):
        if np.isfinite(z.flat[cell]) and flat_receiver[cell] >= 0:
            accumulation[flat_receiver[cell]] += accumulation[cell]
    result = accumulation.reshape(z.shape)
    result[np.isnan(filled)] = np.nan
    return result


def terrain_rasters(dem: np.ndarray, resolution: float = 30) -> dict[str, np.ndarray]:
    """Elevation, elevation relative to 250/500 m neighbourhood means, slope (deg)."""
    filled = np.where(np.isnan(dem), np.nanmean(dem), dem)
    rasters = {"elev": dem}
    for radius in (250, 500):
        size = int(2 * radius / resolution) + 1
        rasters[f"rel_elev_{radius}"] = dem - ndimage.uniform_filter(filled, size=size)
    dy, dx = np.gradient(filled, resolution)
    rasters["slope"] = np.degrees(np.arctan(np.hypot(dx, dy)))
    accumulation = flow_accumulation(fill_depressions(dem))
    # Flow paths are one cell wide: take the strongest path within 3 × 3 cells.
    rasters["log_flow_acc"] = ndimage.maximum_filter(np.log1p(np.nan_to_num(accumulation)), size=3)
    tan_slope = np.maximum(np.tan(np.radians(rasters["slope"])), 0.001)
    rasters["twi"] = np.log(np.nan_to_num(accumulation, nan=1.0) * resolution / tan_slope)
    return rasters


def drainage_density(waterways: gpd.GeoDataFrame, shape: tuple, transform,
                     radius_m: float = 250, resolution: float = 30) -> np.ndarray:
    """Share of raster cells within ``radius_m`` crossed by drainage lines."""
    from rasterio.features import rasterize

    lines = rasterize(((g, 1) for g in waterways.geometry), out_shape=shape, transform=transform,
                      fill=0, all_touched=True, dtype="uint8")
    size = int(2 * radius_m / resolution) + 1
    return ndimage.uniform_filter(lines.astype("float32"), size=size)


def sample(raster: np.ndarray, transform, points: gpd.GeoSeries) -> np.ndarray:
    """Raster values at points (NaN outside)."""
    rows, cols = rasterio.transform.rowcol(transform, points.x.to_numpy(), points.y.to_numpy())
    rows, cols = np.asarray(rows), np.asarray(cols)
    inside = (rows >= 0) & (rows < raster.shape[0]) & (cols >= 0) & (cols < raster.shape[1])
    values = np.full(len(points), np.nan)
    values[inside] = raster[rows[inside], cols[inside]]
    return values


def read_waterways(pbf, crs: str) -> gpd.GeoDataFrame:
    """OSM waterway lines (streams, canals, drains, rivers, ditches)."""
    import osmium
    from shapely.geometry import LineString

    rows = []
    for way in osmium.FileProcessor(str(pbf), osmium.osm.NODE | osmium.osm.WAY).with_locations():
        if way.is_way() and way.tags.get("waterway") in WATERWAYS:
            coords = [(n.lon, n.lat) for n in way.nodes if n.location.valid()]
            if len(coords) > 1:
                rows.append({"waterway": way.tags["waterway"], "geometry": LineString(coords)})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326").to_crs(crs)


def segment_features(segments: gpd.GeoDataFrame, rasters: dict, transform,
                     waterways: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Physical features at each segment midpoint."""
    mid = segments.geometry.interpolate(0.5, normalized=True)
    table = gpd.GeoDataFrame(segments[["segment_id"]].copy(), geometry=mid, crs=segments.crs)
    for name, raster in rasters.items():
        table[name] = sample(raster, transform, table.geometry)
    nearest = gpd.sjoin_nearest(table[["geometry"]], waterways[["geometry"]], how="left",
                                distance_col="dist_water")
    nearest = nearest[~nearest.index.duplicated()]
    table["dist_water"] = nearest["dist_water"]
    water_points = [waterways.geometry.loc[i].interpolate(waterways.geometry.loc[i].project(p))
                    for p, i in zip(table.geometry, nearest["index_right"])]
    water_elev = sample(rasters["elev"], transform, gpd.GeoSeries(water_points, crs=segments.crs))
    table["height_above_water"] = table["elev"] - water_elev
    return table


def label_segments(table: gpd.GeoDataFrame, events: pd.DataFrame, radius_m: float) -> gpd.GeoDataFrame:
    """Mark segments within ``radius_m`` of a geocoded event; keep the event id."""
    located = events.dropna(subset=["latitude", "longitude"])
    points = gpd.GeoDataFrame(
        located[["event_id", "event_date"]],
        geometry=gpd.points_from_xy(located["longitude"], located["latitude"]),
        crs="EPSG:4326").to_crs(table.crs)
    near = gpd.sjoin_nearest(table[["geometry"]], points, how="left", max_distance=radius_m,
                             distance_col="event_distance")
    near = near[~near.index.duplicated()]
    result = table.copy()
    result["event_id"] = near["event_id"]
    result["event_year"] = pd.to_datetime(near["event_date"]).dt.year
    result["positive"] = result["event_id"].notna()
    # The segment closest to each event point represents the event in evaluation.
    closest = near.dropna(subset=["event_id"]).groupby("event_id")["event_distance"].idxmin()
    result["event_anchor"] = result.index.isin(closest.to_numpy())
    return result


def percentile_rank(scores: np.ndarray) -> np.ndarray:
    """Share of segments with a score lower than or equal to each score."""
    order = scores.argsort().argsort()
    return (order + 1) / len(scores)


def event_ranks(table: pd.DataFrame, score: np.ndarray, mask: np.ndarray | None = None) -> pd.Series:
    """Per event, the percentile (within ``mask``) of the segment closest to it.

    One segment per event keeps a random score at an expected 0.5; taking the
    best of an event's many segments would inflate uncorrelated scores.
    """
    mask = np.ones(len(table), bool) if mask is None else mask
    pct = pd.Series(np.nan, index=table.index)
    pct[mask] = percentile_rank(score[mask])
    anchors = table.loc[mask & table["event_anchor"].to_numpy()]
    return pct[anchors.index].set_axis(anchors["event_id"].to_numpy())


def models(seed: int) -> dict:
    return {
        "logistic": make_pipeline(StandardScaler(), LogisticRegression(
            C=1.0, class_weight="balanced", max_iter=2000)),
        "random_forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=20, class_weight="balanced_subsample",
            random_state=seed, n_jobs=-1),
    }


def summarize_ranks(ranks: pd.Series) -> dict:
    return {"events": int(ranks.size), "median_percentile": round(float(ranks.median()), 3),
            "share_top10": round(float((ranks >= 0.90).mean()), 3),
            "share_top20": round(float((ranks >= 0.80).mean()), 3)}


def evaluate(table: pd.DataFrame, seed: int, block_m: float, features: list[str] = FEATURES) -> dict:
    """Spatial block CV and temporal hold-out (train < 2025, test 2025)."""
    x = table[features].to_numpy()
    y = table["positive"].to_numpy()
    blocks = (table.geometry.x // block_m).astype(int).astype(str) + "_" + (
        table.geometry.y // block_m).astype(int).astype(str)
    references = {"depressao_500m": -table["rel_elev_500"].to_numpy(),
                  "elevacao_baixa": -table["elev"].to_numpy(),
                  "aleatorio": np.random.default_rng(seed).random(len(table))}
    report = {"spatial_cv": {}, "temporal": {}}
    n_splits = min(5, table.loc[table["positive"], "event_id"].nunique())
    for name, model in models(seed).items():
        oof = np.zeros(len(table))
        for train, test in GroupKFold(n_splits=n_splits).split(x, y, blocks):
            model.fit(x[train], y[train])
            oof[test] = model.predict_proba(x[test])[:, 1]
        references[name] = oof
    for name, score in references.items():
        report["spatial_cv"][name] = {**summarize_ranks(event_ranks(table, score)),
                                      "auc_pu": round(float(roc_auc_score(y, score)), 3)}

    test_year = table["event_year"] == 2025
    train_mask = ~test_year.to_numpy()          # 2025 positives never seen in training
    for name, model in models(seed).items():
        model.fit(x[train_mask], y[train_mask])
        score = model.predict_proba(x)[:, 1]
        report["temporal"][name] = summarize_ranks(
            event_ranks(table, score, mask=~(table["positive"] & ~test_year).to_numpy())
            [lambda s: s.index.str.startswith("E2025")])
    for name in ("depressao_500m", "elevacao_baixa", "aleatorio"):
        report["temporal"][name] = summarize_ranks(
            event_ranks(table, references[name], mask=~(table["positive"] & ~test_year).to_numpy())
            [lambda s: s.index.str.startswith("E2025")])
    return report


def alert(scores: pd.DataFrame, rain_mm_h: float, config: dict, routes: gpd.GeoDataFrame) -> dict:
    """Deterministic operational alert for a forecast rain intensity.

    Below the (provisional) rain threshold nothing is flagged. Otherwise the
    segments above the configured susceptibility percentile are flagged, with
    the bus routes within ``alerta_raio_m`` of them.
    """
    params = config["susceptibility"]
    if rain_mm_h < params["alerta_chuva_mm_h"]:
        return {"rain_mm_h": rain_mm_h, "triggered": False}
    flagged = scores[scores["percentile"] >= params["alerta_percentil"]]
    zone = flagged.buffer(params["alerta_raio_m"]).union_all()
    hit_routes = routes[routes.intersects(zone)]
    return {
        "rain_mm_h": rain_mm_h, "triggered": True,
        "threshold_mm_h": params["alerta_chuva_mm_h"], "percentile": params["alerta_percentil"],
        "segments": int(len(flagged)),
        "routes": sorted(hit_routes["route_short_name"].astype(str).unique().tolist()),
    }


def gtfs_routes(gtfs_zip, crs: str) -> gpd.GeoDataFrame:
    """One geometry per route from shapes.txt (via trips.txt)."""
    from shapely.geometry import LineString, MultiLineString

    with zipfile.ZipFile(gtfs_zip) as archive:
        read = lambda name: pd.read_csv(archive.open(name), dtype=str)  # noqa: E731
        shapes, trips, routes = read("shapes.txt"), read("trips.txt"), read("routes.txt")
    shapes["seq"] = shapes["shape_pt_sequence"].astype(int)
    shapes = shapes.sort_values(["shape_id", "seq"])
    lines = {sid: LineString(zip(g["shape_pt_lon"].astype(float), g["shape_pt_lat"].astype(float)))
             for sid, g in shapes.groupby("shape_id") if len(g) > 1}
    pairs = trips[["route_id", "shape_id"]].drop_duplicates()
    pairs = pairs[pairs["shape_id"].isin(lines)]
    geoms = pairs.groupby("route_id")["shape_id"].apply(
        lambda ids: MultiLineString([lines[i] for i in ids]))
    result = gpd.GeoDataFrame(routes.set_index("route_id")[["route_short_name"]].join(
        geoms.rename("geometry"), how="inner"), geometry="geometry", crs="EPSG:4326")
    return result.to_crs(crs).reset_index()


def main() -> None:
    parser = argparse.ArgumentParser(description="Suscetibilidade de segmentos e alerta operacional")
    parser.add_argument("--alert-rain", type=float, default=None,
                        help="chuva prevista (mm/h) para gerar o alerta")
    args = parser.parse_args()
    from .network import load_or_build_segments
    from .scenarios import load_events

    config = load_config()
    crs, seed = config["crs_metric"], config["robustness"]["semente"]
    params = config["susceptibility"]
    interim, processed = resolve(config["paths"]["interim"]), resolve(config["paths"]["processed"])
    tables, qa = resolve(config["paths"]["tables"]), resolve(config["paths"]["qa"])
    area = gpd.read_parquet(processed / "municipality.parquet")

    features_path = interim / f"susceptibility_features_v{FEATURES_VERSION}.parquet"
    if features_path.exists():
        table = gpd.read_parquet(features_path)
    else:
        tiles = [resolve(config["sources"][k]["destino"]) for k in ("dem_s30", "dem_s31")]
        dem, transform = build_dem(tiles, area, crs)
        segments = load_or_build_segments(interim / "poa.osm.pbf", interim / "segments.parquet", crs)
        segments = segments[segments["drive"]]
        segments = segments[segments.geometry.interpolate(0.5, normalized=True).within(
            area.union_all())]
        waterways = read_waterways(interim / "poa.osm.pbf", crs)
        rasters = terrain_rasters(dem)
        rasters["drainage_density_250"] = drainage_density(waterways, dem.shape, transform)
        table = segment_features(segments, rasters, transform, waterways)
        table.to_parquet(features_path)
    events = load_events(resolve(config["paths"]["events"]) / "events.csv")
    table = label_segments(table, events, params["raio_positivo_m"]).dropna(subset=FEATURES)
    table = table.reset_index(drop=True)

    report = {"n_segments": int(len(table)), "n_positive_segments": int(table["positive"].sum()),
              "n_events": int(table.loc[table["positive"], "event_id"].nunique()),
              "features": FEATURES, "seed": seed,
              **evaluate(table, seed, params["bloco_validacao_m"])}
    # Same evaluation with the original features only, to show the gain.
    base = evaluate(table, seed, params["bloco_validacao_m"], BASE_FEATURES)
    report["ablation_base_features"] = {
        part: {m: base[part][m] for m in ("logistic", "random_forest")}
        for part in ("spatial_cv", "temporal")}

    final = models(seed)["logistic"].fit(table[FEATURES].to_numpy(), table["positive"].to_numpy())
    coefficients = dict(zip(FEATURES, final[-1].coef_[0].round(3).tolist()))
    report["logistic_coefficients_standardized"] = coefficients
    scores = table[["segment_id", "geometry"]].copy()
    scores["score"] = final.predict_proba(table[FEATURES].to_numpy())[:, 1]
    scores["pct_logistic"] = percentile_rank(scores["score"].to_numpy())
    scores["pct_elevacao_baixa"] = percentile_rank(-table["elev"].to_numpy())
    # The alert uses whichever scorer ranked the held-out 2025 events best.
    candidates = {"logistic": "pct_logistic", "elevacao_baixa": "pct_elevacao_baixa"}
    selected = max(candidates, key=lambda name: report["temporal"][name]["median_percentile"])
    scores["percentile"] = scores[candidates[selected]]
    report["selected_scorer"] = selected
    scores.to_parquet(tables / "susceptibility.parquet")

    if args.alert_rain is not None:
        routes = gtfs_routes(resolve(config["sources"]["gtfs"]["destino"]), crs)
        report["alert"] = alert(scores, args.alert_rain, config, routes)
    (qa / "susceptibility_run.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
