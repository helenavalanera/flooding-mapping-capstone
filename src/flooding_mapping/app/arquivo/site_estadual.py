"""ARQUIVADO (frente estadual): montagem do site estático de duas escalas, com previsão de 72 h, bloqueios de rodovias e modelo.

Preservado sem alteração de lógica, para consulta histórica; não é executado pela versão atual, que é restrita a Porto Alegre (ver ``flooding_mapping.app.build``).
Para reexecutar seria preciso restaurar o painel estadual (``app/arquivo/painel-estadual/``) e os dados arquivados (``data/raw/arquivo_estadual/``).

Original: Assemble the static site: live rainfall + the trained model + live blockages + static layers.

Everything published is a static file: the page only reads JSON. Python, the model and the
network calls run here, in the environment that builds the site (a scheduled workflow), and no
credential ever reaches the output. The blockages and the rainfall are fetched at build time;
if the blockage source does not answer, the site is built without that layer and says so.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ...collector import fetch as fetch_blockages
from ...geospatial.matching import match_records
from ...ingestion import forecast as forecast_source
from ...inference import forecast as inference
from ..layers import BUILD_DATA, STATIC_DATA

STATIC = Path(__file__).parents[1] / "static"
ASSETS = ("index.html", "painel.js", "territorio.js", "fase3-dados.js", "fase3.js", "drenagem.js", "resultados.js", "simulador.js", "mapa.js", "mapa2d.js", "mapa-base.js", "logic.js", "style.css", "config-dados.js", "icone-192.png", "icone-512.png")
ENTRADA = Path(__file__).parents[1] / "entrada"   # raiz da versão estática: leva à landing (ou ao painel, quando o endereço pede)
# O PWA de rotas e a aplicação instalável estão arquivados em app/arquivo/ e não entram no site.
SOURCE_BLOCKAGES = "CPRv BM, bloqueios ativos (api pública), consulta no momento da publicação"


def blockages_payload(payload: dict, segments: gpd.GeoDataFrame, impact: pd.DataFrame) -> dict:
    """Active blockages with their match to a segment and the simulated impact of that segment."""
    records = payload["bloqueios"]
    matches = match_records(records, segments).set_index("id") if records else pd.DataFrame()
    impact = impact.set_index("segmento_id")
    rows = []
    for record in records:
        match = matches.loc[record["id"]] if record["id"] in matches.index else None
        row = {"id": record["id"], "rodovia": record["rodovia"], "municipio": record.get("municipio"),
               "km": record["km"], "km_fim": record.get("km_fim"), "tipo": record.get("tipo"),
               "desde": record.get("data"), "informacoes": record.get("informacoes"),
               "climatico": record.get("climatico"), "lat": record.get("lat"), "lng": record.get("lng")}
        if match is not None:
            row["casamento"] = {"status": match["status"], "tipo_bloqueio": match["tipo_bloqueio"],
                                "codigo_sre": match["codigo_sre"], "segmentos": int(match["n_segmentos"]),
                                "dist_coord_m": None if pd.isna(match["dist_coord_m"]) else float(match["dist_coord_m"])}
            main = match["segmento_principal"]
            if main in impact.index:
                i = impact.loc[main]
                row["impacto"] = {"natureza": "simulado", "ponte": bool(i["ponte"]),
                                  "pop_isolada": float(i["pop_isolada"]),
                                  "desvio_km": None if pd.isna(i["desvio_km"]) else float(i["desvio_km"]),
                                  "vdm": None if pd.isna(i["vdm"]) else float(i["vdm"])}
        rows.append(row)
    return {"fonte": SOURCE_BLOCKAGES, "natureza": "observação (bloqueio ativo informado pelo órgão)",
            "coletado_em_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "atualizado_pela_fonte": payload.get("atualizado"), "total": len(rows), "bloqueios": rows}


def check_card(artifact: dict, card: dict) -> None:
    """The site may only be built with the model its model card documents."""
    documented = card["artefato"]["versao"]
    if artifact["versao"] != documented:
        raise SystemExit(f"model {artifact['versao']} is not the one the card documents ({documented})")


def copiar_interface(out: Path) -> None:
    """A interface estática, sem nada que dependa de rede, de modelo ou de dado derivado: o que vai para o Pages.

    A raiz (``index.html``) é a porta de entrada, que leva à landing; o painel é ``painel.html``. Os dados derivados (fase3/, drenagem/) e o mapa-base
    ficam de fora: são publicados à parte (R2) ou acrescentados por ``build_site``.
    """
    (out / "data").mkdir(parents=True)
    for name in ASSETS:
        shutil.copy(STATIC / name, out / name)
    (out / "index.html").rename(out / "painel.html")   # o painel passa a ser painel.html; a raiz leva à landing
    shutil.copy(ENTRADA / "index.html", out / "index.html")
    shutil.copy(ENTRADA / "entrada.js", out / "entrada.js")
    shutil.copytree(STATIC / "inicio", out / "inicio")   # landing page: links to the panel are relative, so it works under a repository path on Pages
    shutil.copytree(STATIC / "vendor", out / "vendor")   # basemap libraries, styles and label fonts (the .pmtiles itself is served at /mapa/rs.pmtiles)
    for path in STATIC_DATA.glob("*"):
        shutil.copy(path, out / "data" / path.name)


def build_site(out: Path, artifact: dict, card: dict, series: pd.DataFrame, meta: dict,
               blockages: dict | None, segments: gpd.GeoDataFrame, impact: pd.DataFrame, fase3: Path | None = None, drenagem: Path | None = None) -> dict:
    """Write the site into ``out`` and return what was published."""
    towns, grid = artifact["municipios"], artifact["grade"]
    issue_day = pd.Timestamp(meta["ultima_data"]) - pd.Timedelta(days=forecast_source.FORECAST_DAYS - 1)
    estimates, missing = inference.estimate(artifact, series, towns, grid, issue_day, forecast_source.FORECAST_DAYS)
    forecast = inference.payload(estimates, missing, towns, artifact, card, meta, issue_day)

    shutil.rmtree(out, ignore_errors=True)
    copiar_interface(out)
    (out / "previsao_72h.json").write_text(json.dumps(forecast, ensure_ascii=False, separators=(",", ":")))
    published = {"previsao": True, "municipios": len(forecast["municipios"]), "sem_dados": len(missing)}
    if blockages is not None:
        (out / "bloqueios.json").write_text(json.dumps(
            blockages_payload(blockages, segments, impact), ensure_ascii=False, separators=(",", ":"), default=str))
        published["bloqueios"] = len(blockages["bloqueios"])
    if fase3 is not None:   # opt-in (--fase3): tiles and detail of the Phase 3 layer, derived data that never goes to Git
        shutil.copytree(fase3, out / "fase3")
        published["fase3"] = True
    if drenagem is not None:   # opt-in (--drenagem): the drainage inventory layer, also derived data outside Git
        shutil.copytree(drenagem, out / "drenagem")
        published["drenagem"] = True
    (out / ".nojekyll").write_text("")
    return published


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the static state interface")
    parser.add_argument("--model", required=True, type=Path, help="modelo.joblib (kept outside git)")
    parser.add_argument("--card", required=True, type=Path, help="reports/ml/gatilho_<rotulo>.json")
    parser.add_argument("--out", type=Path, default=Path("site"))
    parser.add_argument("--drenagem", type=Path, default=None, help="data/processed/drenagem_web (tools/preparar_camada_drenagem.py): publishes the drainage inventory layer with the site")
    parser.add_argument("--fase3", type=Path, default=None, help="data/processed/fase3_web (tools/preparar_camada_fase3.py): publishes the Phase 3 layer with the site")
    args = parser.parse_args()
    artifact = inference.load_artifact(args.model)
    card = json.loads(args.card.read_text())
    check_card(artifact, card)
    series, meta = forecast_source.operational(artifact["municipios"])
    try:
        blockages = fetch_blockages()
    except Exception as exc:  # noqa: BLE001 - the layer is optional; say why without leaking anything
        print(f"bloqueios indisponíveis: {type(exc).__name__}")
        blockages = None
    segments = gpd.read_parquet(BUILD_DATA / "segmentos_indice.parquet")
    impact = pd.read_parquet(BUILD_DATA / "impacto_segmentos.parquet")
    print(json.dumps(build_site(args.out, artifact, card, series, meta, blockages, segments, impact, args.fase3, args.drenagem), ensure_ascii=False))


if __name__ == "__main__":
    main()
