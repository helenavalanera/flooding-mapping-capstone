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
                            "drive": [True, True], "walk": [True, False]}, geometry=linhas, crs=CRS)
    terreno = pd.DataFrame({"segment_id": ["10:1:2", "x:0:0", "y:0:0"], "elev": [3.0, 20.0, 60.0],
                            "rel_elev_250": [-1.0, 0.0, 4.0], "slope": [0.5, 3.0, 9.0],
                            "height_above_water": [1.0, 10.0, 40.0], "log_flow_acc": [5.0, 2.0, 1.0]})
    t = rede_poa.construir(seg, terreno, {10: "Av. Ipiranga"})
    assert list(t["nome"].fillna("")) == ["Av. Ipiranga", ""]
    assert t["lon0"].between(-52, -50).all() and t["lat0"].between(-31, -29).all() and (t["lon1"] > t["lon0"]).iloc[0]
    assert t["percentil"].notna().iloc[0] and np.isnan(t["percentil"].iloc[1])  # no terrain: no estimate, not zero
    assert {"drive", "walk", "oneway", "comprimento_m"} <= set(t.columns)
