"""S2iD "Danos Informados" reports for Rio Grande do Sul as one table of disaster records.

The MIDR portal exports a semicolon CSV (ISO-8859-1) with four preamble lines before the
header. The ``Protocolo`` field (``RS-F-<IBGE>-<COBRADE>-<AAAAMMDD>``) carries the
municipality, the disaster type and a date. That date is the day the record was opened,
used here as the event date: in two Porto Alegre cases it coincided with the rainfall
peak, and it never falls after the registration date (checked on the 2017-2026 data).
It is *not* the day the damage started, so models must allow a tolerance window.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..config import load_config, resolve
from ..ingest import register_manual

PREAMBLE_LINES = 4
PROTOCOL = re.compile(r"^([A-Z]{2})-F-(\d{7})-(\d{5})-(\d{8})$")
PERIOD = re.compile(r"Data Inicial:\s*(\d{2}/\d{2}/\d{4})\s+Data Final:\s*(\d{2}/\d{2}/\d{4})")
RAW_DIR = "data/raw/s2id"
OUTPUT = "data/interim/s2id_rs.parquet"
ORIGIN = "S2iD/MIDR, Relatório Gerencial - Danos Informados (exportação manual, UF=RS)"

COLUMNS = {
    "Município": "municipio", "Registro": "data_registro", "Protocolo": "protocolo",
    "COBRADE": "cobrade_rotulo", "Status": "status", "População": "populacao",
    "DH_Desabrigados": "desabrigados", "DH_Desalojados": "desalojados",
    "DH_Outros Afetados": "outros_afetados",
    "DM_Obras de infraestrutura pública Danificadas": "obras_danificadas",
    "DM_Obras de infraestrutura pública Destruídas": "obras_destruidas",
    "DM_Obras de infraestrutura pública Valor": "obras_valor_rs",
}
NUMERIC = ["populacao", "desabrigados", "desalojados", "outros_afetados",
           "obras_danificadas", "obras_destruidas", "obras_valor_rs"]

# COBRADE: 12100 inundações, 12200 enxurradas, 12300 alagamentos (hidrológicos);
# 13214 tempestade local, chuvas intensas (ampla: inclui eventos que não são hídricos).
HYDRO_STRICT = (12100, 12200, 12300)
HYDRO_BROAD = HYDRO_STRICT + (13214,)


def read_report(path: str | Path) -> pd.DataFrame:
    """Parse one export; an export with no rows gives an empty table."""
    table = pd.read_csv(path, sep=";", encoding="latin-1", skiprows=PREAMBLE_LINES, dtype=str)
    missing = set(COLUMNS) - set(table.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    table = table.dropna(subset=["Protocolo"]).rename(columns=COLUMNS)[list(COLUMNS.values())]
    parts = table["protocolo"].str.extract(PROTOCOL)
    if parts[0].isna().any():
        bad = table.loc[parts[0].isna(), "protocolo"].head(3).tolist()
        raise ValueError(f"{path}: protocol outside the expected pattern, e.g. {bad}")
    table["uf"], table["ibge"] = parts[0], parts[1]
    table["cobrade"] = parts[2].astype(int)
    table["data_evento"] = pd.to_datetime(parts[3], format="%Y%m%d")
    table["data_registro"] = pd.to_datetime(table["data_registro"], format="%d/%m/%Y")
    table["cobrade_nome"] = table["cobrade_rotulo"].str.split(" - ", n=1).str[1]
    for column in NUMERIC:
        table[column] = pd.to_numeric(table[column], errors="coerce")
    return table.drop(columns="cobrade_rotulo")


def load(directory: str | Path | None = None) -> pd.DataFrame:
    """Every export in ``data/raw/s2id`` as one table, one row per ``protocolo``."""
    directory = Path(directory) if directory else resolve(RAW_DIR)
    files = sorted(directory.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No S2iD exports in {directory}")
    table = pd.concat([read_report(f) for f in files], ignore_index=True)
    return (table.drop_duplicates("protocolo").sort_values(["data_evento", "ibge"])
            .reset_index(drop=True))


def import_reports(sources: list[Path], destination: Path, manifest: Path) -> list[str]:
    """Copy manual exports into the raw folder, named by period, and record their hash."""
    imported = []
    for source in sources:
        header = source.read_text(encoding="latin-1").splitlines()[3]
        found = PERIOD.search(header)
        if not found:
            raise ValueError(f"{source}: period line not found")
        first, last = (datetime.strptime(d, "%d/%m/%Y").strftime("%Y%m%d") for d in found.groups())
        target = destination / f"danos_informados_{first}_{last}.csv"
        register_manual(source, target, manifest, ORIGIN, f"{first}/{last}")
        imported.append(target.name)
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(description="S2iD reports for RS")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import", help="copy manual exports into data/raw/s2id and register them")
    imp.add_argument("files", nargs="+", type=Path)
    sub.add_parser("build", help="consolidate the exports into data/interim/s2id_rs.parquet")
    args = parser.parse_args()
    config = load_config()
    if args.command == "import":
        names = import_reports(args.files, resolve(RAW_DIR), resolve(config["paths"]["manifest"]))
        print(f"{len(names)} arquivos importados:", *names, sep="\n  ")
        return
    table = load()
    out = resolve(OUTPUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(out)
    relevant = table[table["cobrade"].isin(HYDRO_BROAD)]
    print(f"{len(table)} registros, {table['ibge'].nunique()} municípios, "
          f"{table['data_evento'].min().date()} a {table['data_evento'].max().date()}; "
          f"hídricos (estrito/amplo): "
          f"{table['cobrade'].isin(HYDRO_STRICT).sum()}/{len(relevant)} -> {OUTPUT}")


if __name__ == "__main__":
    main()
