import geopandas as gpd
import pytest
from shapely.geometry import LineString

from flooding_mapping.geospatial.matching import match_records, normalize_road, summarize
from flooding_mapping.geospatial.segments import segment

KM = 1 / 111.19  # degrees of latitude per km, close enough for a synthetic road
LON = -51.0


def road(objectid, code, name, km0, km1, lon=LON, lat0=-30.0):
    """A straight north-south stretch drawn in degrees, 1.01 km of line per nominal km."""
    line = LineString([(lon, lat0), (lon, lat0 - (km1 - km0) * 1.01 * KM)])
    return {"objectid": objectid, "codigo_sre": code, "nome": name, "rede": "RODOVIAS ESTADUAIS",
            "km_inicio": km0, "km_final": km1, "geometry": line}


def segments(*roads):
    return segment(gpd.GeoDataFrame(list(roads), crs="EPSG:4326"))


def at_km(km, lon=LON):
    """Coordinates of the point at nominal ``km`` of the synthetic ERS-1 (km 0 at lat -30)."""
    return {"lat": -30.0 - km * 1.01 * KM, "lng": lon}


def rec(i=1, rodovia="ERS-1", km=5, km_fim=None, **where):
    return {"id": i, "municipio": "X", "rodovia": rodovia, "km": km, "km_fim": km_fim,
            **(where or at_km(km))}


SEGMENTS = segments(road(1, "001ERS0010", "ERS-1", 0, 11))


def match(*records, segs=SEGMENTS):
    return match_records(list(records), segs).set_index("id")


def test_point_blockage_picks_the_segment_closest_to_the_coordinates():
    row = match(rec(km=5)).loc[1]
    assert row["status"] == "ok" and row["tipo_bloqueio"] == "pontual"
    assert row["codigo_sre"] == "001ERS0010" and row["dist_coord_m"] < 600 and row["n_segmentos"] == 1
    assert row["concorda_coordenada"]


def test_interval_blockage_covers_every_overlapping_segment():
    row = match(rec(km=3, km_fim=6, **at_km(4.5))).loc[1]
    assert row["tipo_bloqueio"] == "intervalo" and row["n_segmentos"] == 3
    assert row["segmentos"].split(";") == ["1-003", "1-004", "1-005"]


def test_km_outside_every_stretch_is_reported_with_a_suggestion():
    row = match(rec(km=50, **at_km(5))).loc[1]
    assert row["status"] == "km_fora_da_faixa" and row["codigo_sre"] is None
    assert "1-0" in row["sugestao_segmento"]


def test_km_and_coordinates_that_disagree_are_flagged_not_trusted():
    row = match(rec(km=5, **at_km(9))).loc[1]
    assert row["status"] == "distante_da_coordenada" and row["dist_coord_m"] > 1000
    assert row["codigo_sre"] == "001ERS0010"  # kept as a suggestion


def test_unknown_road_is_accepted_only_when_the_point_lies_on_a_segment():
    near = match(rec(rodovia="XRS-9", km=2, **at_km(2))).loc[1]
    assert near["status"] == "apenas_coordenada" and near["codigo_sre"] == "001ERS0010"
    far = match(rec(rodovia="XRS-9", km=2, lat=-31.5, lng=-52.0)).loc[1]
    assert far["status"] == "rodovia_ausente" and far["n_segmentos"] == 0


def test_record_without_coordinates_matches_by_road_and_km():
    row = match(rec(km=5, lat=None, lng=None)).loc[1]
    assert row["status"] == "ok_sem_coordenada" and row["segmento_principal"] == "1-004"


def test_swapped_km_are_corrected_and_noted():
    row = match(rec(km=6, km_fim=3, **at_km(4.5))).loc[1]
    assert (row["km"], row["km_fim"]) == (3.0, 6) and "invertido" in row["observacao"]
    assert row["tipo_bloqueio"] == "intervalo"


def test_two_official_stretches_of_the_same_road_nearby_are_ambiguous():
    two = segments(road(1, "001ERS0010", "ERS-1", 0, 11), road(2, "001ERS0020", "ERS-1", 4, 8, lon=LON + 0.0004, lat0=-30.0 - 4 * KM))
    row = match(rec(km=5, **at_km(5)), segs=two).loc[1]
    assert row["status"] == "ambiguo" and row["n_trechos_candidatos"] == 2


def test_a_blockage_near_the_boundary_of_two_stretches_is_not_ambiguous():
    # Stretches A (km 0-5) and B (km 5-11) are contiguous; the point is on A, 400 m from B.
    contiguous = segments(road(1, "001ERS0010", "ERS-1", 0, 5), road(2, "001ERS0020", "ERS-1", 5, 11, lat0=-30.0 - 5 * 1.01 * KM))
    row = match(rec(km=5, **at_km(4.6)), segs=contiguous).loc[1]
    assert row["status"] == "ok" and row["codigo_sre"] == "001ERS0010" and row["n_trechos_candidatos"] == 2


def test_digitization_duplicates_with_the_same_code_are_not_ambiguous():
    twice = segments(road(1, "001ERS0010", "ERS-1", 0, 11), road(2, "001ERS0010", "ERS-1", 0, 11, lon=LON + 0.0005))
    assert match(rec(km=5), segs=twice).loc[1]["status"] == "ok"


@pytest.mark.parametrize("raw, expected", [("br 116", "BRS-116"), ("BR-290", "BRS-290"), ("ers401", "ERS-401"),
                                           ("VRS-863", "VRS-863"), ("RSC-287", "RSC-287"), (None, "")])
def test_road_names_are_normalized_to_the_daer_convention(raw, expected):
    assert normalize_road(raw) == expected


def test_summary_counts_coverage_and_lists_the_problems():
    table = match_records([rec(1), rec(2, km=50, **at_km(5)), rec(3, rodovia="XRS-9", lat=-31.5, lng=-52.0)], SEGMENTS)
    summary = summarize(table)
    assert summary["registros"] == 3 and summary["associados"] == 1
    assert summary["cobertura_associados"] == pytest.approx(0.333, abs=1e-3)
    assert summary["rodovias_sem_correspondencia"] == ["XRS-9"]
    assert {p["id"] for p in summary["problemas"]} == {2, 3}
