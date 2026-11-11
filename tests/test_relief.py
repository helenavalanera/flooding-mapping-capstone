import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from flooding_mapping.geospatial import relief


def write_tile(path, dem, west=-52.0, north=-29.0, size=1 / 3600):
    with rasterio.open(path, "w", driver="GTiff", height=dem.shape[0], width=dem.shape[1], count=1,
                       dtype="float32", crs="EPSG:4326", transform=from_origin(west, north, size, size)) as dst:
        dst.write(dem.astype("float32"), 1)


def test_tile_names_follow_the_copernicus_convention_for_the_southwest():
    assert relief.tile_name(-30, -52) == "Copernicus_DSM_COG_10_S30_00_W052_00_DEM"
    assert relief.tile_name(-28, -50) == "Copernicus_DSM_COG_10_S28_00_W050_00_DEM"


def test_a_point_is_assigned_to_the_tile_whose_lower_left_corner_is_the_floor():
    # -29.5, -51.2 lies in the tile whose corner is (-30, -52): latitude -30..-29, longitude -52..-51
    assert relief.needed_tiles(np.array([-51.2, -51.9]), np.array([-29.5, -29.1])) == [(-30, -52)]
    assert relief.needed_tiles(np.array([-51.2, -53.5]), np.array([-29.5, -33.1])) == [(-34, -54), (-30, -52)]


def test_elevation_local_relief_and_slope_are_read_from_the_tile(tmp_path):
    n = 200
    y, x = np.mgrid[0:n, 0:n]
    dem = 100.0 + 0.0 * x
    dem[(abs(y - 100) < 6) & (abs(x - 100) < 6)] = 60.0        # a 40 m deep pit around (100, 100)
    dem[:, 150:] += np.arange(n - 150) * 3.0                    # a steep ramp on the right
    path = tmp_path / "t.tif"
    write_tile(path, dem)
    size = 1 / 3600
    lon = np.array([-52.0 + (100.5) * size, -52.0 + 30.5 * size, -52.0 + 180.5 * size])
    lat = np.array([-29.0 - 100.5 * size, -29.0 - 100.5 * size, -29.0 - 100.5 * size])
    out = relief.tile_relief(path, lon, lat)
    assert out["elev"].tolist() == [60.0, 100.0, 190.0]
    assert out["rel_elev_500"].iloc[0] < -10                    # inside the pit: far below its surroundings
    assert abs(out["rel_elev_500"].iloc[1]) < 1                 # flat ground
    assert out["slope"].iloc[1] == pytest.approx(0.0, abs=0.01)  # flat ground
    assert out["slope"].iloc[2] == pytest.approx(np.degrees(np.arctan(3 / 30)), abs=0.05)  # 3 m rise per 30 m cell


def test_relief_fills_nan_where_there_is_no_tile(tmp_path, monkeypatch):
    monkeypatch.setattr(relief, "ensure_tiles", lambda tiles, root, manifest: {})
    points = pd.DataFrame({"lon": [-51.0], "lat": [-33.9]}, index=["a"])
    out = relief.relief(points, tmp_path, tmp_path / "m.json")
    assert out.isna().all().all() and list(out.index) == ["a"]
