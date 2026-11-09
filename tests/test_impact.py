import geopandas as gpd
import numpy as np
import pytest
from pyproj import Transformer
from shapely.geometry import LineString, Point

from flooding_mapping.geospatial import impact

CRS = "EPSG:5880"
# Test networks are drawn in metres around a real point of Rio Grande do Sul, so reprojection is valid.
X0, Y0 = Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform(-51.0, -30.0)


def seg(sid, a, b, vdm=np.nan, planned=False, coincident=False):
    line = LineString([(X0 + a[0], Y0 + a[1]), (X0 + b[0], Y0 + b[1])])
    return {"segmento_id": sid, "objectid": int(sid.split("-")[0]), "codigo_sre": sid, "nome": "ERS-1",
            "comprimento_m": line.length, "vdm": vdm, "geometry": line,
            "situacao_fisica": "PLANEJADA" if planned else "PAVIMENTADA",
            "soma_extensao": "NÃO" if coincident else "SIM"}


def network(rows):
    return gpd.GeoDataFrame(rows, crs=CRS)


def towns(*specs):
    """specs: (ibge, name, population, x, y) in metres around the test origin.

    Like the real table, the geometry is a polygon and the representative point lives in
    the ``lat``/``lon`` columns."""
    points = gpd.GeoSeries([Point(X0 + s[3], Y0 + s[4]) for s in specs], crs=CRS).to_crs("EPSG:4326")
    return gpd.GeoDataFrame(
        {"ibge": [s[0] for s in specs], "nome": [s[1] for s in specs], "populacao": [s[2] for s in specs],
         "lat": points.y, "lon": points.x},
        geometry=[p.buffer(0.01) for p in points], crs="EPSG:4326")


# A triangle A(0,0) B(10000,0) C(5000,8000) with a tail C -> D(5000,18000); a town at D and one at A.
TRIANGLE_AND_TAIL = [seg("1-0", (0, 0), (10000, 0), vdm=2000.0), seg("2-0", (10000, 0), (5000, 8000)),
                     seg("3-0", (5000, 8000), (0, 0)), seg("4-0", (5000, 8000), (5000, 18000), vdm=500.0)]
TOWNS = lambda: towns(("4300001", "Cidade A", 7000.0, 0, 0), ("4300002", "Cidade D", 300.0, 5000, 18000))  # noqa: E731


def test_the_tail_is_a_bridge_and_isolates_its_population_while_triangle_edges_are_not():
    table, summary = impact.simulate(network(TRIANGLE_AND_TAIL), TOWNS(), CRS)
    t = table.set_index("segmento_id")
    assert t.loc["4-0", "ponte"] and t.loc["4-0", "pop_isolada"] == 300.0     # smaller side: the tail town
    assert not t[["ponte"]].loc[["1-0", "2-0", "3-0"]].any().any()
    assert summary["pontes"] == 1 and summary["componentes"] == 1 and summary["populacao_ligada_a_rede"] == 1.0


def test_detour_is_the_extra_distance_around_the_triangle():
    table, _ = impact.simulate(network(TRIANGLE_AND_TAIL), TOWNS(), CRS)
    t = table.set_index("segmento_id")
    around = (np.hypot(5000, 8000) * 2) / 1000 - 10.0   # A->C->B instead of A->B directly
    assert t.loc["1-0", "desvio_km"] == pytest.approx(around, rel=1e-6)


def test_traffic_weighting_uses_vdm_only_where_it_exists_and_never_treats_missing_as_zero():
    table, _ = impact.simulate(network(TRIANGLE_AND_TAIL), TOWNS(), CRS)
    t = table.set_index("segmento_id")
    assert t.loc["1-0", "veiculos_km_dia"] == pytest.approx(2000.0 * t.loc["1-0", "desvio_km"])
    assert np.isnan(t.loc["2-0", "veiculos_km_dia"]) and np.isnan(t.loc["2-0", "vdm"])  # missing, not zero
    assert np.isnan(t.loc["4-0", "veiculos_km_dia"])  # a bridge has no finite detour to weight


def test_a_second_road_between_the_same_nodes_makes_both_roads_redundant():
    rows = [seg("1-0", (0, 0), (10000, 0)), seg("2-0", (0, 0), (10000, 0)), seg("3-0", (10000, 0), (10000, 9000))]
    table, _ = impact.simulate(network(rows), towns(("4300001", "A", 100.0, 0, 0), ("4300002", "B", 50.0, 10000, 9000)), CRS)
    t = table.set_index("segmento_id")
    assert not t.loc["1-0", "ponte"] and not t.loc["2-0", "ponte"] and t.loc["1-0", "desvio_km"] == 0.0
    assert t.loc["3-0", "ponte"]


def test_planned_roads_and_double_counted_geometry_are_left_out():
    rows = [seg("1-0", (0, 0), (5000, 0)), seg("2-0", (5000, 0), (9000, 0), planned=True),
            seg("3-0", (0, 0), (5000, 0), coincident=True)]
    assert list(impact.usable(network(rows))["segmento_id"]) == ["1-0"]


def test_endpoints_closer_than_the_snap_distance_are_one_junction():
    rows = [seg("1-0", (0, 0), (5000, 0)), seg("2-0", (5010, 0), (9000, 0))]   # 10 m apart
    graph, _ = impact.build_graph(network(rows))
    assert graph.number_of_nodes() == 3 and nx.number_connected_components(graph) == 1


def test_a_municipality_far_from_the_network_is_not_counted():
    table, summary = impact.simulate(network(TRIANGLE_AND_TAIL),
                                     towns(("4300001", "A", 100.0, 0, 0), ("4300009", "Longe", 900.0, 80000, 80000)), CRS)
    assert summary["municipios_fora_da_rede"] == 1 and summary["populacao_ligada_a_rede"] == pytest.approx(0.1)


def test_a_city_is_spread_over_its_road_accesses_so_one_spur_cannot_isolate_it_all():
    """The artefact seen on real data: all of a big city's people hung on one dead-end spur."""
    big = gpd.GeoDataFrame(
        {"ibge": ["4300001"], "nome": ["Capital"], "populacao": [1_000_000.0]},
        geometry=gpd.GeoSeries([Point(X0 + 4000, Y0 + 2000)], crs=CRS).to_crs("EPSG:4326").buffer(0.06), crs="EPSG:4326")
    center = gpd.GeoSeries([Point(X0 + 4000, Y0 + 2000)], crs=CRS).to_crs("EPSG:4326")
    big["lat"], big["lon"] = center.y.iloc[0], center.x.iloc[0]
    rows = [seg("1-0", (0, 0), (10000, 0)), seg("2-0", (10000, 0), (5000, 8000)), seg("3-0", (5000, 8000), (0, 0)),
            seg("4-0", (0, 0), (-3000, -3000))]  # a dead-end spur inside the municipality
    table, _ = impact.simulate(network(rows), big, CRS)
    spur = table.set_index("segmento_id").loc["4-0"]
    assert spur["ponte"] and spur["pop_isolada"] < 400_000  # one node of four, not the whole city


import networkx as nx  # noqa: E402  (used by the snapping test)
