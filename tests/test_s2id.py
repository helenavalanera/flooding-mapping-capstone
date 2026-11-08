import json

import pandas as pd
import pytest

from flooding_mapping.ingestion import s2id

HEADER = ("UF;Município;Registro;Protocolo;COBRADE;Status;População;DH_Desabrigados;"
          "DH_Desalojados;DH_Outros Afetados;DM_Obras de infraestrutura pública Danificadas;"
          "DM_Obras de infraestrutura pública Destruídas;DM_Obras de infraestrutura pública Valor")


def export(rows, period="Data Inicial: 01/01/2023 Data Final: 01/01/2024 UF: RS"):
    preamble = ["Ministério da Integração e do Desenvolvimento Regional",
                "Secretaria Nacional de Proteção e Defesa Civil",
                "Relatório Gerencial - Danos Informados", period]
    return "\n".join(preamble + [HEADER] + rows) + "\n"


def row(ibge="4314902", cobrade="12200", day="20230615", registro="18/06/2023", nome="Enxurradas",
        valor="1500.5"):
    return (f"RS;Porto Alegre;{registro};RS-F-{ibge}-{cobrade}-{day};{cobrade} - {nome};"
            f"Reconhecido;1332845;0;10;20;3;0;{valor}")


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_bytes(text.encode("latin-1"))
    return path


def test_read_report_parses_protocol_dates_and_numbers(tmp_path):
    path = write(tmp_path, "a.csv", export([row()]))
    table = s2id.read_report(path)
    r = table.iloc[0]
    assert (r["ibge"], r["cobrade"], r["uf"]) == ("4314902", 12200, "RS")
    assert r["data_evento"] == pd.Timestamp("2023-06-15")
    assert r["data_registro"] == pd.Timestamp("2023-06-18")
    assert r["cobrade_nome"] == "Enxurradas" and r["obras_valor_rs"] == 1500.5
    assert r["data_registro"] >= r["data_evento"]


def test_load_merges_exports_and_drops_repeated_protocols(tmp_path):
    write(tmp_path, "a.csv", export([row(), row(day="20230616")]))
    write(tmp_path, "b.csv", export([row(day="20230616"), row(ibge="4300109", day="20230617")]))
    table = s2id.load(tmp_path)
    assert len(table) == 3 and table["ibge"].nunique() == 2
    assert table["data_evento"].is_monotonic_increasing


def test_empty_export_gives_an_empty_table(tmp_path):
    path = write(tmp_path, "empty.csv", export([], period="Data Inicial: 01/01/2023 Data Final: 01/01/2023 UF: RS"))
    assert s2id.read_report(path).empty


def test_protocol_outside_the_pattern_is_an_error(tmp_path):
    bad = row().replace("RS-F-4314902-12200-20230615", "RS-X-1")
    with pytest.raises(ValueError, match="protocol"):
        s2id.read_report(write(tmp_path, "bad.csv", export([bad])))


def test_hydrological_code_sets():
    assert set(s2id.HYDRO_STRICT) < set(s2id.HYDRO_BROAD)
    assert 13214 in s2id.HYDRO_BROAD and 13214 not in s2id.HYDRO_STRICT


def test_import_names_by_period_and_records_provenance(tmp_path):
    source = write(tmp_path, "download (3).csv", export([row()]))
    manifest = tmp_path / "manifest.json"
    names = s2id.import_reports([source], tmp_path / "raw", manifest)
    assert names == ["danos_informados_20230101_20240101.csv"]
    entry = json.loads(manifest.read_text())["sources"][0]
    assert entry["url"] is None and len(entry["sha256"]) == 64
    assert s2id.import_reports([source], tmp_path / "raw", manifest) == names  # idempotent
    assert len(json.loads(manifest.read_text())["sources"]) == 1
