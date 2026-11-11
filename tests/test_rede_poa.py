import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from flooding_mapping import rede_poa

CRS = "EPSG:31982"


def test_the_street_table_has_lon_lat_endpoints_names_and_a_missing_index_where_there_is_no_terrain():
    linhas = [LineString([(500000, 6670000), (500100, 6670000)]), LineString([(500100, 6670000), (500100, 6670150)])]
    seg = gpd.GeoDataFrame({"segment_id": ["10:1:2", "11:2:3"], "way_id": [10, 11], "u": [1, 2], "v": [2, 3],
                            "length_m": [100.0, 150.0], "highway": ["primary", "residential"], "oneway": ["no", "yes"],
                            "drive": [True, True], "walk": [True, False], "access": [None, None], "foot": [None, None]}, geometry=linhas, crs=CRS)
    terreno = pd.DataFrame({"segment_id": ["10:1:2", "x:0:0", "y:0:0"], "elev": [3.0, 20.0, 60.0],
                            "rel_elev_250": [-1.0, 0.0, 4.0], "slope": [0.5, 3.0, 9.0],
                            "height_above_water": [1.0, 10.0, 40.0], "log_flow_acc": [5.0, 2.0, 1.0]})
    t = rede_poa.construir(seg, terreno, {10: {"nome": "Av. Ipiranga"}})
    assert list(t["nome"].fillna("")) == ["Av. Ipiranga", ""]
    assert t["lon0"].between(-52, -50).all() and t["lat0"].between(-31, -29).all() and (t["lon1"] > t["lon0"]).iloc[0]
    assert t["percentil"].notna().iloc[0] and np.isnan(t["percentil"].iloc[1])  # no terrain: no estimate, not zero
    assert {"drive", "walk", "oneway", "comprimento_m"} <= set(t.columns)


def test_the_descriptive_check_reports_where_documented_blockages_fall_and_its_own_limits():
    from rede_sintetica import LAT0, LON0, rede, tres_caminhos

    from flooding_mapping import rede_poa as rp

    df = tres_caminhos(pct_curto=95.0, pct_medio=50.0, pct_longo=5.0)
    df["elev"] = df["percentil"].rsub(100)  # high percentile = low ground
    # one event on the short (most susceptible) path
    eventos = pd.DataFrame({"latitude": [LAT0 + 0.002], "longitude": [LON0 + 0.0075], "event_date": ["2025-06-18"]})
    r = rede(df)
    out = rp.verificacao_descritiva(r, eventos, raio_m=100, n_nulo=50)
    assert out["eventos_com_segmento"] == 1 and out["indice_fisico"]["mediana"] == 95.0
    assert out["indice_fisico"]["mediana"] > out["mediana_geral_do_indice"]
    assert out["natureza"].startswith("descritivo") and len(out["limites"]) == 3
    assert rp.verificacao_descritiva(r, eventos.assign(latitude=[None]), n_nulo=5) == {"eventos_com_segmento": 0}


def _segmentos(linhas: list[dict]):
    base = {"highway": "residential", "oneway": "no", "drive": True, "walk": True, "access": None, "foot": None, "length_m": 100.0}
    geo = [LineString([(500000 + 200 * i, 6670000), (500100 + 200 * i, 6670000)]) for i in range(len(linhas))]
    d = pd.DataFrame([{**base, "segment_id": f"{i}:1:2", "way_id": i, "u": i * 2, "v": i * 2 + 1, **l} for i, l in enumerate(linhas)])
    return gpd.GeoDataFrame(d, geometry=geo, crs=CRS), pd.DataFrame({"segment_id": [], "elev": [], "rel_elev_250": [], "slope": [], "height_above_water": [], "log_flow_acc": []})


def test_osm_conventions_the_raw_table_misses_are_applied_to_the_street_table():
    seg, terreno = _segmentos([
        {},                                                   # 0: an ordinary street, left alone
        {"oneway": "no"},                                     # 1: a roundabout without the oneway tag (the table says "no")
        {"oneway": "yes"},                                    # 2: an explicit one-way, left alone
        {},                                                   # 3: a parking aisle
        {},                                                   # 4: a driveway
        {"drive": False, "access": "private"},                # 5: a private road (already closed to cars by the table)
        {"access": "private"},                                # 6: private, but the table still lets pedestrians in
        {"access": "private", "foot": "yes"},                 # 7: private to cars, open to people on foot
        {"access": "no", "foot": "designated"}])              # 8: closed in general, designated for foot
    vias = {1: {"junction": "roundabout"}, 3: {"service": "parking_aisle"}, 4: {"service": "driveway"}}
    t = rede_poa.construir(seg, terreno, vias).set_index("segmento_id")
    assert t.loc["1:1:2", "oneway"] == "yes" and t.loc["0:1:2", "oneway"] == "no" and t.loc["2:1:2", "oneway"] == "yes"
    assert not t.loc["3:1:2", "drive"] and not t.loc["4:1:2", "drive"] and t.loc["0:1:2", "drive"]
    assert t.loc["3:1:2", "walk"] and t.loc["4:1:2", "walk"]                          # a person can still walk through a parking lot
    assert t["walk"].tolist() == [True, True, True, True, True, False, False, True, True]   # private or closed ways shut to pedestrians, unless foot says yes
