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


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocodifica eventos a partir dos nomes OSM")
    parser.parse_args()
    from pyrosm import OSM

    config = load_config()
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


if __name__ == "__main__":
    main()
