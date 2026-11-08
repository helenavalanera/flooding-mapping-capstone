"""Events, interdiction zones and candidate network edges."""

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPoint
from shapely.ops import linemerge, nearest_points

from .config import load_config, resolve
from .ingest import read_csv
from .validate import require_columns

EVENT_COLUMNS = (
    "event_id", "event_date", "event_type", "source_name", "source_url", "latitude",
    "longitude", "confidence", "description", "verification_status",
)
SCENARIO_COLUMNS = (
    "scenario_id", "event_id", "radius_m", "network_type", "affected_edge_ids",
    "validation_status", "validated_by", "validation_date", "notes",
)
CONFIDENCE = {"alta", "media", "baixa"}
# Maximum spread of shared nodes for one intersection (dual carriageways).
MAX_INTERSECTION_SPREAD_M = 150
# Maximum distance between a street and the landmark it is said to be near.
MAX_LANDMARK_DISTANCE_M = 300


def load_events(path: str | Path) -> pd.DataFrame:
    """Load and validate the events table."""
    events = read_csv(path)
    require_columns(events, EVENT_COLUMNS)
    if not events["event_id"].is_unique:
        raise ValueError("Duplicated event_id in events table")
    pd.to_datetime(events["event_date"], format="%Y-%m-%d")
    if not events["confidence"].isin(CONFIDENCE).all():
        raise ValueError(f"confidence must be one of {sorted(CONFIDENCE)}")
    if events["source_url"].isna().any():
        raise ValueError("Every event needs a source_url")
    return events


def load_scenarios(path: str | Path) -> pd.DataFrame:
    """Load and validate the versioned scenario table."""
    scenarios = read_csv(path)
    require_columns(scenarios, SCENARIO_COLUMNS)
    return scenarios


def _streets(edges: gpd.GeoDataFrame, names: str) -> gpd.GeoDataFrame:
    """Edges whose OSM name is one of the '|'-separated ``names``."""
    return edges[edges["name"].isin(names.split("|"))]


def intersection_point(edges, nodes, street_a: str, street_b: str, crs: str):
    """Centroid of the nodes shared by two named streets, or None.

    Returns None when the streets do not meet or their shared nodes are
    farther apart than MAX_INTERSECTION_SPREAD_M (ambiguous match).
    """
    a, b = _streets(edges, street_a), _streets(edges, street_b)
    shared = (set(a["u"]) | set(a["v"])) & (set(b["u"]) | set(b["v"]))
    if not shared:
        return None
    points = nodes[nodes["id"].isin(shared)].to_crs(crs)
    hull = MultiPoint(list(points.geometry))
    if hull.minimum_rotated_rectangle.length / 2 > MAX_INTERSECTION_SPREAD_M:
        return None
    return hull.centroid


def segment_between(edges, nodes, street: str, ends: str, crs: str):
    """Point of ``street`` closest to the middle of its intersections with the
    two ';'-separated cross streets in ``ends``, or None if either is missing."""
    first, second = ends.split(";")
    a = intersection_point(edges, nodes, street, first, crs)
    b = intersection_point(edges, nodes, street, second, crs)
    if a is None or b is None:
        return None
    line = _streets(edges, street).to_crs(crs).union_all()
    middle = MultiPoint([a, b]).centroid
    return nearest_points(line, middle)[0]


def street_midpoint(edges, street: str, crs: str):
    """Midpoint along the longest merged part of a named street."""
    lines = linemerge(_streets(edges, street).to_crs(crs).union_all())
    parts = getattr(lines, "geoms", [lines])
    longest = max(parts, key=lambda part: part.length)
    return longest.interpolate(0.5, normalized=True)


def nearest_to_landmark(edges, street: str, landmark, crs: str):
    """Point of a named street closest to a landmark geometry (in ``crs``),
    or None when the street is farther than MAX_LANDMARK_DISTANCE_M."""
    line = _streets(edges, street).to_crs(crs).union_all()
    if line.distance(landmark) > MAX_LANDMARK_DISTANCE_M:
        return None
    return nearest_points(line, landmark)[0]


def geocode_events(events: pd.DataFrame, edges, nodes, landmarks: dict, crs: str) -> pd.DataFrame:
    """Fill latitude/longitude from the OSM names and method of each event.

    Events with method ``pendente`` or that cannot be resolved keep empty
    coordinates; ``geocode_detail`` explains the outcome.
    """
    result = events.copy()
    details = []
    for index, row in result.iterrows():
        method = row["geocode_method"]
        point = None
        if method == "osm_intersection":
            point = intersection_point(edges, nodes, row["osm_street_a"], row["osm_street_b"], crs)
        elif method == "osm_segment_between":
            point = segment_between(edges, nodes, row["osm_street_a"], row["osm_street_b"], crs)
        elif method == "osm_street_midpoint":
            point = street_midpoint(edges, row["osm_street_a"], crs)
        elif method == "osm_street_nearest_landmark" and row["osm_street_b"] in landmarks:
            point = nearest_to_landmark(edges, row["osm_street_a"], landmarks[row["osm_street_b"]], crs)
        if point is None:
            details.append("não geocodificado" if method != "pendente" else "pendente")
            result.loc[index, ["latitude", "longitude"]] = [None, None]
            continue
        lonlat = gpd.GeoSeries([point], crs=crs).to_crs("EPSG:4326").iloc[0]
        result.loc[index, ["latitude", "longitude"]] = [round(lonlat.y, 6), round(lonlat.x, 6)]
        details.append("ok")
    result["geocode_detail"] = details
    return result


def load_landmarks(osm, names: list[str], crs: str) -> dict:
    """Geometries (in ``crs``) of OSM features whose name is in ``names``."""
    if not names:
        return {}
    features = osm.get_data_by_custom_criteria(custom_filter={"name": names})
    if features is None or features.empty:
        return {}
    features = features.to_crs(crs)
    return {name: group.union_all() for name, group in features.groupby("name")}


def interdiction_zones(events: pd.DataFrame, radii: list[int], crs: str,
                       tolerance_m: float = 0) -> gpd.GeoDataFrame:
    """Circular search zones of each radius around geocoded events."""
    located = events.dropna(subset=["latitude", "longitude"])
    points = gpd.GeoSeries.from_xy(located["longitude"], located["latitude"], crs="EPSG:4326")
    points = points.to_crs(crs).set_axis(located["event_id"].to_numpy())
    zones = [{"event_id": event_id, "radius_m": radius, "geometry": point.buffer(radius + tolerance_m)}
             for radius in radii for event_id, point in points.items()]
    return gpd.GeoDataFrame(zones, geometry="geometry", crs=crs)


def candidate_segments(segments: gpd.GeoDataFrame, zone, network_type: str) -> gpd.GeoDataFrame:
    """Segments of the given network that intersect ``zone``."""
    usable = segments["drive"] if network_type == "driving" else segments["walk"] | segments["drive"]
    subset = segments[usable]
    return subset[subset.intersects(zone)]


def scenario_rows(events: pd.DataFrame, zones: gpd.GeoDataFrame, segments: gpd.GeoDataFrame,
                  network_type: str = "all") -> pd.DataFrame:
    """Candidate scenarios: one per total-blockage event and radius, plus one
    per date combining all of that date's total blockages."""
    total = events[events["event_type"] == "bloqueio_total_acumulo_agua"]
    zones = zones[zones["event_id"].isin(total["event_id"])]
    dates = total.set_index("event_id")["event_date"]
    rows = []
    for (event_id, radius), zone in zones.set_index(["event_id", "radius_m"]).geometry.items():
        ids = candidate_segments(segments, zone, network_type)["segment_id"]
        rows.append({"scenario_id": f"S-{event_id}-{radius}-{network_type}", "event_id": event_id,
                     "radius_m": radius, "network_type": network_type,
                     "affected_edge_ids": ";".join(sorted(ids)), "n_segments": len(ids),
                     "validation_status": "candidato", "validated_by": "", "validation_date": "",
                     "notes": "Segmentos que intersectam a zona (busca, não interdição comprovada)."})
    for date, group in zones.assign(date=zones["event_id"].map(dates)).groupby("date"):
        if group["event_id"].nunique() < 2:
            continue
        for radius, by_radius in group.groupby("radius_m"):
            ids = candidate_segments(segments, by_radius.union_all(), network_type)["segment_id"]
            tag = date.replace("-", "")
            rows.append({"scenario_id": f"S-D{tag}-{radius}-{network_type}",
                         "event_id": ";".join(sorted(by_radius["event_id"])), "radius_m": radius,
                         "network_type": network_type, "affected_edge_ids": ";".join(sorted(ids)),
                         "n_segments": len(ids), "validation_status": "candidato",
                         "validated_by": "", "validation_date": "",
                         "notes": f"Todos os bloqueios totais geocodificados de {date}, simultâneos."})
    return pd.DataFrame(rows)


def blockage_count_fit(per_date: pd.DataFrame, events: pd.DataFrame) -> dict:
    """Linear fit of total blockages reported per date against 24 h rain.

    ``per_date`` comes from the rain calibration (event_date, total_24h_mm,
    captured); dates whose rain the model missed are left out.
    """
    import numpy as np

    totals = events[events["event_type"] == "bloqueio_total_acumulo_agua"].groupby("event_date").size()
    data = per_date.assign(blockages=per_date["event_date"].map(totals).fillna(0).astype(int))
    fit = data[data["captured"]]
    if len(fit) < 2:
        raise ValueError("At least two dates with captured rain are needed")
    slope, intercept = np.polyfit(fit["total_24h_mm"], fit["blockages"], 1)
    return {"intercept": float(intercept), "slope": float(slope), "dates": int(len(fit)),
            "points": fit[["event_date", "total_24h_mm", "blockages"]].to_dict(orient="records")}


def extra_points(fit: dict, rain_mm: float, factor: float = 1) -> int:
    """Number of extra blockages expected for ``rain_mm`` (never negative)."""
    return max(0, round(factor * (fit["intercept"] + fit["slope"] * rain_mm)))


def model_hotspots(scores: gpd.GeoDataFrame, n: int, exclude: gpd.GeoSeries,
                   min_distance_m: float) -> gpd.GeoDataFrame:
    """The ``n`` most susceptible segments, each at least ``min_distance_m``
    from the excluded points and from each other (greedy, by score)."""
    chosen = []
    taken = list(exclude.geometry) if len(exclude) else []
    for row in scores.sort_values("percentile", ascending=False).itertuples():
        if len(chosen) >= n:
            break
        if all(row.geometry.distance(g) >= min_distance_m for g in taken):
            chosen.append(row.Index)
            taken.append(row.geometry)
    return scores.loc[chosen]


def rain_scenario_rows(events: pd.DataFrame, segments: gpd.GeoDataFrame, scores: gpd.GeoDataFrame,
                       fit: dict, threshold_mm: float, config: dict) -> pd.DataFrame:
    """Closure sets along the rain scale.

    Below ``threshold_mm`` (least 24 h rain that ever coincided with a reported
    blockage) nothing closes. From it on, the documented total blockages close,
    plus ``extra_points`` model hotspots for the rain and precariousness factor.
    """
    params = config["mobility"]
    crs = config["crs_metric"]
    documented = events[(events["event_type"] == "bloqueio_total_acumulo_agua")].dropna(
        subset=["latitude", "longitude"])
    doc_points = gpd.GeoSeries.from_xy(documented["longitude"], documented["latitude"],
                                       crs="EPSG:4326").to_crs(crs)
    doc_zone = doc_points.buffer(params["raio_m"]).union_all()
    usable = segments[segments["walk"] | segments["drive"]]
    doc_ids = set(usable.loc[usable.intersects(doc_zone), "segment_id"])
    rows = []
    for factor in params["fatores_precariedade"]:
        for rain in params["chuva_24h_mm"]:
            if rain < threshold_mm:
                continue
            n = extra_points(fit, rain, factor)
            hotspots = model_hotspots(scores, n, doc_points, params["distancia_minima_m"])
            ids = set(doc_ids)
            if len(hotspots):
                zone = hotspots.geometry.buffer(params["raio_m"]).union_all()
                ids |= set(usable.loc[usable.intersects(zone), "segment_id"])
            rows.append({
                "scenario_id": f"S-C{rain:g}-F{factor:g}", "event_id": "documentados+modelo",
                "radius_m": params["raio_m"], "network_type": "all",
                "affected_edge_ids": ";".join(sorted(ids)),
                "validation_status": "hipotetico" if n else "candidato",
                "validated_by": "", "validation_date": "",
                "notes": (f"Chuva {rain:g} mm/24h, fator de precariedade {factor:g}: "
                          f"{len(doc_points)} pontos documentados + {n} pontos do modelo "
                          f"({', '.join(hotspots['segment_id']) or 'nenhum'})."),
                "rain_24h_mm": rain, "factor": factor, "extra_points": n,
            })
    return pd.DataFrame(rows)


def review_map(event_id: str, events: pd.DataFrame, zones: gpd.GeoDataFrame,
               segments: gpd.GeoDataFrame, path: str | Path) -> None:
    """Zones and candidate segments of one event, for human review."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    own = zones[zones["event_id"] == event_id].sort_values("radius_m", ascending=False)
    extent = own.geometry.iloc[0].buffer(150)
    context = segments[segments.intersects(extent)]
    fig, ax = plt.subplots(figsize=(8, 8))
    context.plot(ax=ax, color="0.75", linewidth=0.8)
    colors = {150: "#fdae61", 100: "#f46d43", 50: "#a50026"}
    for radius, zone in own.set_index("radius_m").geometry.items():
        gpd.GeoSeries([zone], crs=zones.crs).boundary.plot(ax=ax, color=colors.get(radius, "k"),
                                                           linestyle="--", linewidth=1)
        candidate_segments(context, zone, "all").plot(ax=ax, color=colors.get(radius, "k"),
                                                      linewidth=2.5, label=f"candidatos {radius} m")
    for name, group in context[context.intersects(own.geometry.iloc[0])].groupby("name"):
        point = group.union_all().representative_point()
        ax.annotate(name, (point.x, point.y), fontsize=7, color="0.2")
    row = events.set_index("event_id").loc[event_id]
    ax.set_title(f"{event_id} — {row['location_text']} ({row['event_date']})", fontsize=9)
    ax.legend(fontsize=8, loc="lower right")
    ax.set_axis_off()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def geocode(config: dict) -> None:
    from pyrosm import OSM

    path = resolve(config["paths"]["events"]) / "events.csv"
    events = load_events(path)
    osm = OSM(str(resolve(config["paths"]["interim"]) / "poa.osm.pbf"))
    nodes, edges = osm.get_network(network_type="all", nodes=True)
    landmark_names = events.loc[events["geocode_method"] == "osm_street_nearest_landmark",
                                "osm_street_b"].dropna().unique().tolist()
    landmarks = load_landmarks(osm, landmark_names, config["crs_metric"])
    geocoded = geocode_events(events, edges, nodes, landmarks, config["crs_metric"])
    geocoded.drop(columns="geocode_detail").to_csv(path, index=False)
    print(geocoded[["event_id", "location_text", "latitude", "longitude", "geocode_detail"]]
          .to_string(index=False))


def candidates(config: dict, review: list[str]) -> None:
    from .network import load_or_build_segments

    interim = resolve(config["paths"]["interim"])
    segments = load_or_build_segments(interim / "poa.osm.pbf", interim / "segments.parquet",
                                      config["crs_metric"])
    names = _segment_names(interim / "poa.osm.pbf", segments)
    segments = segments.assign(name=segments["way_id"].map(names))
    events = load_events(resolve(config["paths"]["events"]) / "events.csv")
    zones = interdiction_zones(events, config["scenarios"]["raios_m"], config["crs_metric"],
                               config["scenarios"]["tolerancia_m"])
    rows = scenario_rows(events, zones, segments)
    path = resolve(config["paths"]["events"]) / "scenarios.csv"
    existing = load_scenarios(path)
    validated = existing[existing["validation_status"] != "candidato"]
    rows = rows[~rows["scenario_id"].isin(validated["scenario_id"])]
    pd.concat([validated, rows.drop(columns="n_segments")], ignore_index=True).to_csv(path, index=False)
    print(rows[["scenario_id", "n_segments"]].to_string(index=False))
    for event_id in review:
        review_map(event_id, events, zones, segments,
                   resolve(config["paths"]["maps"]) / f"review_{event_id}.png")


def _segment_names(pbf: Path, segments: gpd.GeoDataFrame) -> dict:
    """OSM way names (for map labels)."""
    import osmium

    wanted = set(segments["way_id"])
    return {way.id: way.tags.get("name") for way in osmium.FileProcessor(str(pbf), osmium.osm.WAY)
            if way.id in wanted and "name" in way.tags}


def main() -> None:
    parser = argparse.ArgumentParser(description="Eventos e cenários de interdição")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("geocode", help="geocodifica eventos a partir dos nomes OSM")
    cand = sub.add_parser("candidates", help="gera zonas, segmentos candidatos e mapas de revisão")
    cand.add_argument("--review", nargs="*", default=[], help="event_ids para mapa de revisão")
    args = parser.parse_args()
    config = load_config()
    if args.command == "geocode":
        geocode(config)
    else:
        candidates(config, args.review)


if __name__ == "__main__":
    main()
