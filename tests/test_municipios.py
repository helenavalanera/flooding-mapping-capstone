import geopandas as gpd
from shapely.geometry import Polygon

from flooding_mapping.ingestion.municipios import build


def tract(x0, y0, cd, name, pop):
    box = Polygon([(x0, y0), (x0 + 1, y0), (x0 + 1, y0 + 1), (x0, y0 + 1)])
    return {"CD_MUN": cd, "NM_MUN": name, "NM_RGI": "R", "NM_RGINT": "RI",
            "AREA_KM2": 10.0, "v0001": pop, "geometry": box}


def test_tracts_are_dissolved_by_municipality_and_lagoons_dropped(tmp_path):
    rows = [
        tract(-52, -30, "4300001", "A", 100),
        tract(-51, -30, "4300001", "A", 50),  # second tract of the same municipality
        tract(-52, -32, "4300002", "B", 7),
        tract(-53, -32, "0", "lagoa", 0),  # water body, not a municipality
    ]
    path = tmp_path / "t.gpkg"
    gpd.GeoDataFrame(rows, crs="EPSG:4674").to_file(path, driver="GPKG")

    towns = build(path)

    assert list(towns["ibge"]) == ["4300001", "4300002"]
    a = towns.set_index("ibge").loc["4300001"]
    assert a["populacao"] == 150 and a["area_km2"] == 20.0
    assert towns.geometry.iloc[0].contains(gpd.points_from_xy([a["lon"]], [a["lat"]])[0])
    assert a["densidade_hab_km2"] == 7.5
