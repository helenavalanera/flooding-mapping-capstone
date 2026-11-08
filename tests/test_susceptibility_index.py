import numpy as np
import pandas as pd
import pytest

from flooding_mapping.models import susceptibility_index as si


def features(n=200, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"elev": rng.uniform(5, 900, n), "rel_elev_500": rng.normal(0, 20, n),
                         "dist_agua_m": rng.uniform(10, 8000, n), "comprimento_m": 1000.0,
                         "objectid": range(n)}, index=[f"{i}-000" for i in range(n)])


def test_robust_z_ignores_outliers_and_is_clipped():
    values = pd.Series([10.0] * 50 + [11.0] * 50 + [1e9])
    z = si.robust_z(values)
    assert z.max() == 3.0 and abs(z.iloc[0]) < 3


def test_a_low_segment_beside_a_river_ranks_above_a_high_dry_one():
    f = pd.concat([features(), pd.DataFrame({"elev": [3.0, 950.0], "rel_elev_500": [-40.0, 40.0],
                                              "dist_agua_m": [5.0, 9000.0], "comprimento_m": 1000.0, "objectid": [998, 999]},
                                             index=["low-000", "high-000"])])
    out = si.build_index(f)
    assert out.loc["low-000", "percentil"] > 95 and out.loc["high-000", "percentil"] < 5
    assert out["percentil"].between(0, 100).all() and set(si.COMPONENTS) <= set(out.columns)


def test_unknown_terrain_gives_no_index_instead_of_a_made_up_one():
    f = features()
    f.loc[f.index[0], "elev"] = np.nan
    out = si.build_index(f)
    assert np.isnan(out.loc[f.index[0], "indice"]) and out["indice"].iloc[1:].notna().all()


def test_the_elevation_rule_is_reported_beside_the_index():
    out = si.build_index(features())
    lowest = out["elev"].idxmin()
    assert out.loc[lowest, "percentil_regra_elevacao"] == 100.0


def test_comparison_on_labelled_segments_is_descriptive_and_warns():
    out = si.build_index(features())
    ids = list(out.sort_values("percentil").index[-10:])
    result = si.compare_on_labelled(out, ids)
    assert result["segmentos_rotulados"] == 10 and result["indice"]["no_top_20pct"] == 1.0
    assert "sem valor estatístico" in result["aviso"]
    assert si.compare_on_labelled(out, ["nao-existe"]) == {"segmentos_rotulados": 0}


def test_distance_to_water_gives_one_distance_per_point_even_with_equidistant_waterways():
    import geopandas as gpd
    from shapely.geometry import LineString, Point

    waterways = gpd.GeoDataFrame(geometry=[LineString([(-100, 0), (-100, 50)]), LineString([(100, 0), (100, 50)])], crs="EPSG:5880")
    points = gpd.GeoSeries([Point(0, 10), Point(0, 20), Point(60, 5)], index=["a", "b", "c"], crs="EPSG:5880")
    out = si.distance_to_water(points, waterways)   # the first two are exactly 100 m from both waterways
    assert list(out.index) == ["a", "b", "c"] and out.tolist() == [100.0, 100.0, 40.0]
