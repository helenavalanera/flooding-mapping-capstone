"""Street segments from OSM and scenario-specific derived PBF files.

A segment is a pair of consecutive nodes of an OSM ``highway`` way, with id
``<way_id>:<u>:<v>``. Blocking works on segments, so only the part of a way
inside an interdiction zone is removed; the original PBF is never modified.
"""

from pathlib import Path

import geopandas as gpd
import osmium
import pandas as pd
from shapely.geometry import LineString

# Highway values usable by each network; everything else is excluded.
WALK_EXCLUDED = {"motorway", "motorway_link", "trunk", "trunk_link", "construction", "proposed"}
DRIVE_ALLOWED = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary",
    "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential", "living_street",
    "service", "road",
}
# New ids for split ways start here, far above current OSM way ids.
SPLIT_ID_OFFSET = 10**12


def segment_id(way_id: int, u: int, v: int) -> str:
    return f"{way_id}:{u}:{v}"


def read_segments(pbf: str | Path, crs: str) -> gpd.GeoDataFrame:
    """One row per consecutive node pair of every highway way."""
    rows = []
    processor = osmium.FileProcessor(str(pbf), osmium.osm.NODE | osmium.osm.WAY).with_locations()
    for way in processor:
        if not way.is_way():
            continue
        highway = way.tags.get("highway")
        if highway is None:
            continue
        refs = [(node.ref, node.lon, node.lat) for node in way.nodes if node.location.valid()]
        tags = {
            "highway": highway,
            "oneway": way.tags.get("oneway", "no"),
            "foot": way.tags.get("foot"),
            "access": way.tags.get("access"),
            "motor_vehicle": way.tags.get("motor_vehicle"),
        }
        for (u, x0, y0), (v, x1, y1) in zip(refs, refs[1:]):
            rows.append({"segment_id": segment_id(way.id, u, v), "way_id": way.id, "u": u, "v": v,
                         **tags, "geometry": LineString([(x0, y0), (x1, y1)])})
    segments = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326").to_crs(crs)
    segments["length_m"] = segments.length
    segments["walk"] = ~segments["highway"].isin(WALK_EXCLUDED) & (segments["foot"] != "no")
    no_car = segments["motor_vehicle"].isin(["no", "private"]) | segments["access"].isin(
        ["no", "private"])
    segments["drive"] = segments["highway"].isin(DRIVE_ALLOWED) & ~no_car
    return segments


def _runs(refs: list[int], blocked: set[tuple[int, int]]) -> tuple[list[list[int]], list[list[int]]]:
    """Split a node list into runs of free and of blocked consecutive pairs."""
    free, cut, current, current_blocked = [], [], [refs[0]], None
    for u, v in zip(refs, refs[1:]):
        is_blocked = (u, v) in blocked
        if current_blocked is None or is_blocked == current_blocked:
            current.append(v)
        else:
            (cut if current_blocked else free).append(current)
            current = [u, v]
        current_blocked = is_blocked
    (cut if current_blocked else free).append(current)
    return free, cut


def write_blocked_pbf(
    source: str | Path, output: str | Path, blocked_ids: set[str], network_type: str
) -> dict:
    """Write a copy of ``source`` without the blocked segments.

    ``network_type='all'`` drops blocked segments for every mode;
    ``'driving'`` keeps them but tags them ``motor_vehicle=no`` so only cars
    lose them. Affected ways are split: the first free run keeps the original
    id (relations still resolve), further runs get ids above SPLIT_ID_OFFSET.
    """
    if network_type not in {"all", "driving"}:
        raise ValueError(f"Unsupported network_type: {network_type}")
    by_way: dict[int, set[tuple[int, int]]] = {}
    for item in blocked_ids:
        way, u, v = (int(part) for part in item.split(":"))
        by_way.setdefault(way, set()).add((u, v))

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    next_id = SPLIT_ID_OFFSET
    stats = {"ways_split": 0, "segments_blocked": 0}
    with osmium.SimpleWriter(str(output)) as writer:
        for obj in osmium.FileProcessor(str(source)):
            if not (obj.is_way() and obj.id in by_way):
                writer.add(obj)
                continue
            refs = [node.ref for node in obj.nodes]
            blocked = by_way[obj.id] & set(zip(refs, refs[1:]))
            free, cut = _runs(refs, blocked)
            stats["ways_split"] += 1
            stats["segments_blocked"] += len(blocked)
            tags = dict(obj.tags)
            pieces = [(run, tags) for run in free]
            if network_type == "driving":
                pieces += [(run, {**tags, "motor_vehicle": "no", "motorcar": "no"}) for run in cut]
            for index, (run, run_tags) in enumerate(pieces):
                way_id = obj.id if index == 0 else next_id
                if index:
                    next_id += 1
                writer.add_way(obj.replace(id=way_id, nodes=run, tags=run_tags))
    return stats


def load_or_build_segments(pbf: str | Path, cache: str | Path, crs: str) -> gpd.GeoDataFrame:
    """Read the segment table from ``cache`` or build it from ``pbf``."""
    cache = Path(cache)
    if cache.exists() and cache.stat().st_mtime >= Path(pbf).stat().st_mtime:
        return gpd.read_parquet(cache)
    segments = read_segments(pbf, crs)
    cache.parent.mkdir(parents=True, exist_ok=True)
    segments.to_parquet(cache)
    return segments


def blocked_segments(segments: gpd.GeoDataFrame, ids: pd.Series | set) -> gpd.GeoDataFrame:
    return segments[segments["segment_id"].isin(set(ids))]
