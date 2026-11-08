import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiLineString

from flooding_mapping.geospatial.segments import as_line, segment


def trechos(lines, km_final, km_inicio=0.0):
    """Stretches drawn in EPSG:5880 (metres), so lengths are exact in the test."""
    return gpd.GeoDataFrame(
        {"objectid": list(range(1, len(lines) + 1)), "codigo_sre": [f"{i:03d}ERS0010" for i in range(len(lines))],
         "nome": "ERS-1", "rede": "RODOVIAS ESTADUAIS", "km_inicio": km_inicio, "km_final": km_final},
        geometry=lines, crs="EPSG:5880")


def test_a_10_km_stretch_gives_ten_one_km_pieces_with_consecutive_km():
    out = segment(trechos([LineString([(0, 0), (10000, 0)])], km_final=10.0))
    assert len(out) == 10
    assert out["comprimento_m"].round().eq(1000).all()
    assert out["km_ini"].round(6).tolist() == [float(i) for i in range(10)]
    assert out["km_fim"].iloc[-1] == pytest.approx(10.0)
    assert out["segmento_id"].iloc[3] == "1-003" and (out["n_segmentos"] == 10).all()


def test_pieces_follow_the_line_in_order():
    out = segment(trechos([LineString([(0, 0), (4000, 0)])], km_final=4.0, km_inicio=100.0))
    assert out["km_ini"].iloc[0] == 100.0 and out.geometry.iloc[0].coords[0] == (0.0, 0.0)
    assert out.geometry.iloc[-1].coords[-1] == pytest.approx((4000.0, 0.0))


def test_short_stretch_stays_whole_and_pieces_cover_the_stretch():
    out = segment(trechos([LineString([(0, 0), (1400, 0)])], km_final=1.4))
    assert len(out) == 1 and out["comprimento_m"].iloc[0] == pytest.approx(1400)
    long = segment(trechos([LineString([(0, 0), (2600, 0)])], km_final=2.6))
    assert len(long) == 3 and long["comprimento_m"].sum() == pytest.approx(2600)
    assert 750 < long["comprimento_m"].min() and long["comprimento_m"].max() < 1500


def test_ratio_between_vector_and_nominal_length_is_recorded():
    out = segment(trechos([LineString([(0, 0), (11000, 0)])], km_final=10.0))
    assert out["razao_vetor_nominal"].iloc[0] == pytest.approx(1.1)


def test_a_contiguous_multipart_line_is_merged_and_a_broken_one_is_an_error():
    joined = MultiLineString([[(0, 0), (500, 0)], [(500, 0), (1000, 0)]])
    assert as_line(joined).length == 1000
    broken = MultiLineString([[(0, 0), (500, 0)], [(900, 0), (1000, 0)]])
    with pytest.raises(ValueError, match="single line"):
        as_line(broken)
