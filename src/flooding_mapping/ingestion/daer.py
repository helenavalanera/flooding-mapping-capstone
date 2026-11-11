"""DAER state road network: ArcGIS geometry joined to the SRE spreadsheet by ``codigo_sre``.

The ArcGIS layer holds the line of each official stretch ("trecho"); the Sistema
Rodoviario Estadual spreadsheet, a manual download, holds the operational attributes
(daily traffic VDM, IRI roughness, paving year, urban area...). The official stretches
and every ArcGIS attribute are kept as published. The audit lists what exists on only one
side and the coverage of each added attribute: a missing VDM or IRI stays missing and is
never read as zero.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ..config import load_config, resolve
from ..ingest import register, register_manual, sha256_file

PAGE = 500  # a single query for all stretches makes the server answer 500
USER_AGENT = "flooding-mapping-capstone (pesquisa academica)"
ORIGIN = "DAER, Relatório do Sistema Rodoviário Estadual do RS (download manual)"
OUTPUT = "data/interim/daer_trechos.parquet"
AUDIT = "reports/qa/daer_ingestao.json"

SHEET_COLUMNS = {
    "CÓDIGO SRE NOVO": "codigo_sre", "TIPO DE TRECHO": "tipo_trecho",
    "SIGLA SITUAÇÃO FÍSICA": "sigla_situacao_fisica", "SIGLA REDE": "sigla_rede",
    "SOMA EXTENSÃO": "soma_extensao", "CIRCUNSCRIÇÃO ADMINISTRATIVA": "circunscricao",
    "SIGLA ADMINISTRAÇÃO": "sigla_administracao", "MUNICÍPIO": "municipio_unico",
    "ANTIGA TRAVESSIA URBANA": "antiga_travessia_urbana",
    "INSERIDO EM ÁREA URBANIZADA": "area_urbanizada",
    "LARGURA FAIXA DE DOMÍNIO (m)": "faixa_dominio_m", "VDM": "vdm",
    "IRI - Pista Direita (m/km) 2018": "iri_2018", "IRI - Pista Direita (m/km) 2022": "iri_2022",
    "IRI - Pista Direita (m/km) 2025": "iri_2025", "ANO PAVIMENTAÇÃO": "ano_pavimentacao",
    "SNV JURISDIÇÃO": "jurisdicao", "GID": "gid_planilha",
}
NUMERIC = ["faixa_dominio_m", "vdm", "iri_2018", "iri_2022", "iri_2025", "ano_pavimentacao"]
ADDED = ["vdm", "iri_2018", "iri_2022", "iri_2025", "ano_pavimentacao", "faixa_dominio_m"]


def get_json(url: str, params: dict, opener: Callable = urllib.request.urlopen) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=180) as response:
        return json.loads(response.read())


def fetch_features(layer: str, opener: Callable = urllib.request.urlopen) -> dict:
    """All features of the layer as one GeoJSON collection, fetched page by page."""
    query = f"{layer}/query"
    expected = get_json(query, {"where": "1=1", "returnCountOnly": "true", "f": "json"}, opener)["count"]
    features: list[dict] = []
    while len(features) < expected:
        page = get_json(query, {
            "where": "1=1", "outFields": "*", "outSR": "4674", "f": "geojson",
            "geometryPrecision": "6", "orderByFields": "objectid",
            "resultOffset": len(features), "resultRecordCount": PAGE}, opener)["features"]
        if not page:
            break
        features += page
    if len(features) != expected:
        raise ValueError(f"DAER layer: {len(features)} features received of {expected} expected")
    ids = [f["properties"]["objectid"] for f in features]
    if len(ids) != len(set(ids)):
        raise ValueError("DAER layer: repeated objectid across pages")
    return {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:4674"}},
            "features": features}


def download(layer: str, destination: Path, manifest: Path, opener: Callable = urllib.request.urlopen) -> dict:
    """Fetch the layer and save it atomically with its provenance."""
    collection = fetch_features(layer, opener)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".part")
    temporary.write_text(json.dumps(collection, separators=(",", ":")))
    os.replace(temporary, destination)
    entry = {
        "url": f"{layer}/query (paginado, {PAGE} por página, outSR=4674, f=geojson)",
        "path": str(destination.relative_to(resolve("."))) if destination.is_relative_to(resolve(".")) else str(destination),
        "downloaded_at_utc": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "sha256": sha256_file(destination), "size_bytes": destination.stat().st_size,
        "source_reference_date": None, "features": len(collection["features"]),
    }
    entry["registered"] = register(manifest, entry)
    return entry


def read_sheet(path: str | Path) -> pd.DataFrame:
    """The spreadsheet attributes, one row per stretch, with readable column names."""
    sheet = pd.read_excel(path, sheet_name="GERAL", engine="xlrd", dtype=str)
    missing = set(SHEET_COLUMNS) - set(sheet.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    sheet = sheet[list(SHEET_COLUMNS)].rename(columns=SHEET_COLUMNS)
    sheet["codigo_sre"] = sheet["codigo_sre"].str.strip()
    for column in NUMERIC:
        sheet[column] = pd.to_numeric(sheet[column], errors="coerce")
    return sheet


def loose_key(code: str) -> str:
    """Code without its type letter (4th character): E, M, A... changes when a stretch is reclassified."""
    return code[:3] + code[4:]


def join(roads: gpd.GeoDataFrame, sheet: pd.DataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    """Left join on ``codigo_sre`` (geometry side) and an audit of both sides.

    A stretch the spreadsheet only knows under another type letter (for example
    ``030ERS0150`` in the layer and ``030MRS0150`` in the spreadsheet, after a
    municipalization) is joined in a second pass when that match is unique.
    ``juncao`` says how each row was joined; ``objectid`` is the unique stretch id (a
    handful of codes appear twice in the layer, as alternative digitizations).
    """
    sheet = sheet.rename(columns={"codigo_sre": "codigo_sre_planilha"})
    duplicated = sorted(set(sheet.loc[sheet["codigo_sre_planilha"].duplicated(), "codigo_sre_planilha"]))
    sheet = sheet.drop_duplicates("codigo_sre_planilha")
    merged = roads.merge(sheet, left_on="codigo_sre", right_on="codigo_sre_planilha", how="left")
    merged["juncao"] = merged["gid_planilha"].notna().map({True: "codigo", False: "sem planilha"})

    unused = sheet[~sheet["codigo_sre_planilha"].isin(roads["codigo_sre"])].copy()
    unused["chave"] = unused["codigo_sre_planilha"].map(loose_key)
    unused = unused[~unused["chave"].duplicated(keep=False)].set_index("chave")
    need = merged["gid_planilha"].isna()
    keys = merged.loc[need, "codigo_sre"].map(loose_key)
    hit = keys.isin(unused.index) & ~keys.duplicated(keep=False)
    rows = merged.index[need][hit.values]
    for column in sheet.columns:
        merged.loc[rows, column] = unused.loc[keys[hit].values, column].values
    merged.loc[rows, "juncao"] = "aproximada (letra do tipo)"

    roads_codes = set(roads["codigo_sre"])
    sheet_codes = set(sheet["codigo_sre_planilha"]) - set(merged["codigo_sre_planilha"].dropna())
    exact = merged[merged["juncao"] == "codigo"]
    audit = {
        "trechos_arcgis": len(roads), "trechos_planilha": len(sheet) + len(duplicated),
        "codigos_repetidos_arcgis": sorted(set(roads.loc[roads["codigo_sre"].duplicated(), "codigo_sre"])),
        "codigos_repetidos_planilha": duplicated,
        "juncao": merged["juncao"].value_counts().to_dict(),
        "juncao_aproximada": sorted(merged.loc[merged["juncao"].str.startswith("aprox"), "codigo_sre"]),
        "so_no_arcgis": sorted(merged.loc[merged["juncao"] == "sem planilha", "codigo_sre"]),
        "so_na_planilha": sorted(sheet_codes - roads_codes),
        "gid_divergente_em_codigo_exato": int((exact["gid"].astype(str) != exact["gid_planilha"].astype(str)).sum()),
        "cobertura": {c: round(float(merged[c].notna().mean()), 3) for c in ADDED},
    }
    return merged, audit


def load(geojson: Path, sheet: Path) -> tuple[gpd.GeoDataFrame, dict]:
    return join(gpd.read_file(geojson), read_sheet(sheet))


def main() -> None:
    parser = argparse.ArgumentParser(description="DAER road network ingestion")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="fetch the ArcGIS layer into data/raw/daer")
    imp = sub.add_parser("import", help="copy the SRE spreadsheet into data/raw/daer")
    imp.add_argument("planilha", type=Path)
    sub.add_parser("build", help="join layer and spreadsheet into data/interim/daer_trechos.parquet")
    args = parser.parse_args()
    config = load_config()
    daer, manifest = config["daer"], resolve(config["paths"]["manifest"])
    if args.command == "download":
        entry = download(daer["camada_arcgis"], resolve(daer["geojson"]), manifest)
        print(f"{entry['features']} trechos, {entry['size_bytes'] / 1e6:.1f} MB -> {entry['path']}")
    elif args.command == "import":
        entry = register_manual(args.planilha, resolve(daer["planilha"]), manifest, ORIGIN)
        print(f"planilha registrada: {entry['path']} ({entry['size_bytes'] / 1e6:.1f} MB)")
    else:
        merged, audit = load(resolve(daer["geojson"]), resolve(daer["planilha"]))
        out = resolve(OUTPUT)
        out.parent.mkdir(parents=True, exist_ok=True)
        merged.to_parquet(out)
        resolve(AUDIT).write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in audit.items()},
                         ensure_ascii=False), f"-> {OUTPUT}")


if __name__ == "__main__":
    main()
