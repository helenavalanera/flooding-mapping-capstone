import json
import urllib.parse

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString

from flooding_mapping.ingestion import daer


class FakeResponse:
    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def layer_opener(total, lost=0):
    """An ArcGIS layer with ``total`` features; ``lost`` of them never come back."""
    def opener(request, timeout):
        query = dict(urllib.parse.parse_qsl(request.full_url.split("?")[1]))
        if query.get("returnCountOnly"):
            return FakeResponse({"count": total})
        start, size = int(query["resultOffset"]), int(query["resultRecordCount"])
        ids = list(range(1, total - lost + 1))[start:start + size]
        return FakeResponse({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": None, "properties": {"objectid": i}} for i in ids]})
    return opener


def test_features_are_fetched_page_by_page(monkeypatch):
    monkeypatch.setattr(daer, "PAGE", 3)
    collection = daer.fetch_features("http://layer", layer_opener(7))
    assert [f["properties"]["objectid"] for f in collection["features"]] == list(range(1, 8))
    assert collection["crs"]["properties"]["name"] == "EPSG:4674"


def test_a_short_layer_is_an_error_not_a_silent_gap(monkeypatch):
    monkeypatch.setattr(daer, "PAGE", 3)
    with pytest.raises(ValueError, match="of 7 expected"):
        daer.fetch_features("http://layer", layer_opener(7, lost=2))


def sheet(rows):
    base = {c: None for c in daer.SHEET_COLUMNS.values()}
    return pd.DataFrame([{**base, **r} for r in rows])


def roads(codes, gids=None):
    return gpd.GeoDataFrame(
        {"objectid": range(1, len(codes) + 1), "gid": gids or list(range(1, len(codes) + 1)),
         "codigo_sre": codes}, geometry=[LineString([(0, i), (1, i)]) for i in range(len(codes))], crs="EPSG:4674")


def test_exact_join_keeps_every_official_stretch_and_adds_attributes():
    merged, audit = daer.join(
        roads(["010ERS0010", "010ERS0020"]),
        sheet([{"codigo_sre": "010ERS0010", "gid_planilha": "1", "vdm": 5000.0},
               {"codigo_sre": "010ERS0020", "gid_planilha": "2", "vdm": None}]))
    assert len(merged) == 2 and list(merged["juncao"]) == ["codigo", "codigo"]
    assert merged["vdm"].iloc[0] == 5000 and pd.isna(merged["vdm"].iloc[1])  # missing stays missing
    assert audit["cobertura"]["vdm"] == 0.5 and audit["so_no_arcgis"] == [] and audit["so_na_planilha"] == []


def test_a_reclassified_stretch_is_joined_in_a_second_pass_and_reported():
    merged, audit = daer.join(
        roads(["030ERS0150", "040ERS0010"]),
        sheet([{"codigo_sre": "030MRS0150", "gid_planilha": "1", "vdm": 800.0},
               {"codigo_sre": "040ERS0010", "gid_planilha": "2", "vdm": 100.0}]))
    row = merged.set_index("codigo_sre").loc["030ERS0150"]
    assert row["juncao"].startswith("aproximada") and row["vdm"] == 800 and row["codigo_sre_planilha"] == "030MRS0150"
    assert audit["juncao_aproximada"] == ["030ERS0150"] and audit["so_na_planilha"] == []


def test_stretches_without_a_spreadsheet_row_are_listed_and_have_no_attributes():
    merged, audit = daer.join(roads(["050BRS9130"]), sheet([{"codigo_sre": "999ARS1005", "gid_planilha": "9"}]))
    assert merged["juncao"].iloc[0] == "sem planilha" and pd.isna(merged["vdm"].iloc[0])
    assert audit["so_no_arcgis"] == ["050BRS9130"] and audit["so_na_planilha"] == ["999ARS1005"]


def test_codes_repeated_in_the_layer_are_kept_and_reported():
    merged, audit = daer.join(
        roads(["118ERS0165", "118ERS0165"], gids=[1526, 1525]),
        sheet([{"codigo_sre": "118ERS0165", "gid_planilha": "1526"}]))
    assert len(merged) == 2 and merged["objectid"].is_unique
    assert audit["codigos_repetidos_arcgis"] == ["118ERS0165"] and audit["gid_divergente_em_codigo_exato"] == 1


def test_read_sheet_renames_columns_and_parses_numbers(monkeypatch):
    raw = pd.DataFrame([{c: "1" for c in daer.SHEET_COLUMNS} | {
        "CÓDIGO SRE NOVO": " 010ERS0010 ", "VDM": "56770", "IRI - Pista Direita (m/km) 2025": "-"}])
    monkeypatch.setattr(pd, "read_excel", lambda *a, **k: raw)
    out = daer.read_sheet("x.xls")
    assert out["codigo_sre"].iloc[0] == "010ERS0010" and out["vdm"].iloc[0] == 56770
    assert pd.isna(out["iri_2025"].iloc[0])  # a dash is "no measurement", not zero
    monkeypatch.setattr(pd, "read_excel", lambda *a, **k: raw.drop(columns=["VDM"]))
    with pytest.raises(ValueError, match="missing columns"):
        daer.read_sheet("x.xls")
