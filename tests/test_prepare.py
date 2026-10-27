import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon, box

from flooding_mapping.prepare import allocate_population, make_grid, normalize_destinations

CRS = "EPSG:31982"


@pytest.fixture
def tracts():
    # Two tracts side by side; an L-shaped territory so some cells are clipped.
    return gpd.GeoDataFrame(
        {"CD_SETOR": ["A", "B"], "population": [1000, 300]},
        geometry=[box(0, 0, 1500, 2000),
                  Polygon([(1500, 0), (2500, 0), (2500, 700), (1500, 700)])],
        crs=CRS,
    )


def test_grid_tiles_area_with_stable_ids_and_inner_points(tracts):
    area = gpd.GeoDataFrame(geometry=[tracts.union_all()], crs=CRS)
    cells = make_grid(area, 1000)
    assert cells["origin_id"].is_unique
    assert cells.area.sum() == pytest.approx(area.area.iloc[0])
    assert gpd.GeoSeries(cells["origin"], crs=CRS).within(area.union_all()).all()
    assert make_grid(area, 1000)["origin_id"].tolist() == cells["origin_id"].tolist()
    assert "g0_0" in set(cells["origin_id"])


def test_population_is_conserved(tracts):
    area = gpd.GeoDataFrame(geometry=[tracts.union_all()], crs=CRS)
    allocated = allocate_population(make_grid(area, 1000), tracts)
    assert allocated["population"].sum() == pytest.approx(1300)
    # Cell g0_0 lies fully inside tract A (3,0 km²): 1/3 of its population.
    g00 = allocated.set_index("origin_id").loc["g0_0", "population"]
    assert g00 == pytest.approx(1000 / 3)


def test_destinations_flag_node_polygon_duplicates_and_clip_to_area():
    area = gpd.GeoDataFrame(geometry=[box(0, 0, 1000, 1000)], crs=CRS)
    pois = gpd.GeoDataFrame(
        {
            "id": [1, 2, 3, 4],
            "osm_type": ["node", "way", "node", "node"],
            "name": ["Hospital X", "hospital x ", "Hospital X", "Clínica Y"],
            "amenity": ["hospital", "hospital", "hospital", "clinic"],
        },
        geometry=[Point(510, 510), box(450, 450, 550, 550), Point(900, 100), Point(2000, 2000)],
        crs=CRS,
    )
    table = normalize_destinations(pois, area).set_index("dest_id")
    assert set(table.index) == {"w2", "n1", "n3"}  # n4 is outside the area
    assert table.loc["n1", "duplicate"]
    assert not table.loc["w2", "duplicate"] and not table.loc["n3", "duplicate"]
    assert table.loc["w2"].geometry.within(box(450, 450, 550, 550))
