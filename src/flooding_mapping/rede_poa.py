"""Builds the street table the routing service loads: OSM segments + terrain index + street names.

Reads ``data/interim`` (segments of the OSM clip, terrain features) and writes
``data/processed/rede_poa.parquet`` (not versioned, like every derived dataset). The service only
needs numpy, pandas and scipy to use it. Segments without terrain features keep a missing
percentile: they have no risk estimate, which is different from low risk.
"""

from __future__ import annotations

import argparse
import json

import geopandas as gpd
import numpy as np
import osmium
import pandas as pd
import shapely

from .config import load_config, resolve
from .risco_trecho import COMPONENTES, indice_fisico
from .rotas import Rede

OUTPUT = "data/processed/rede_poa.parquet"
TERRENO = ["elev", "rel_elev_250", "slope", "height_above_water", "log_flow_acc"]


SERVICOS_NAO_PUBLICOS = {"parking_aisle", "driveway", "drive-through", "emergency_access"}   # not streets a car goes through to somewhere else
ROTATORIAS = {"roundabout", "circular"}
LIBERA_PEDESTRE = {"yes", "designated", "permissive"}


def atributos_das_vias(pbf) -> dict[int, dict]:
    """OSM way id -> the tags the routing needs and the segment table does not carry (name, junction, service)."""
    vias = {}
    for obj in osmium.FileProcessor(str(pbf), osmium.osm.WAY):
        if obj.tags.get("highway"):
            vias[obj.id] = {"nome": obj.tags.get("name"), "junction": obj.tags.get("junction"), "service": obj.tags.get("service")}
    return vias


def construir(segmentos: gpd.GeoDataFrame, terreno: pd.DataFrame, vias: dict[int, dict]) -> pd.DataFrame:
    """One row per segment: graph columns, endpoints in lon/lat, terrain percentile and its parts.

    Three rules the raw segment table does not apply, all from OSM conventions:
    * a roundabout is one-way even when the tag is missing;
    * a parking aisle, driveway, drive-through or emergency access is not a street a car crosses to go elsewhere;
    * a private or closed way is not open to pedestrians either, unless it says so for foot."""
    lonlat = segmentos.geometry.to_crs("EPSG:4326")
    inicio, fim = shapely.get_point(lonlat.values, 0), shapely.get_point(lonlat.values, -1)
    tabela = pd.DataFrame({
        "segmento_id": segmentos["segment_id"].to_numpy(), "u": segmentos["u"].to_numpy(), "v": segmentos["v"].to_numpy(),
        "comprimento_m": segmentos["length_m"].to_numpy(), "highway": segmentos["highway"].to_numpy(),
        "oneway": segmentos["oneway"].to_numpy(), "drive": segmentos["drive"].to_numpy(), "walk": segmentos["walk"].to_numpy(),
        "lon0": shapely.get_x(inicio), "lat0": shapely.get_y(inicio), "lon1": shapely.get_x(fim), "lat1": shapely.get_y(fim),
        "nome": segmentos["way_id"].map(lambda w: (vias.get(w) or {}).get("nome")).to_numpy()})
    junction = segmentos["way_id"].map(lambda w: (vias.get(w) or {}).get("junction"))
    servico = segmentos["way_id"].map(lambda w: (vias.get(w) or {}).get("service"))
    tabela.loc[junction.isin(ROTATORIAS).to_numpy() & tabela["oneway"].isin(["no"]).to_numpy(), "oneway"] = "yes"
    tabela["drive"] = tabela["drive"].to_numpy() & ~servico.isin(SERVICOS_NAO_PUBLICOS).to_numpy()
    fechada = segmentos["access"].isin(["no", "private"]) & ~segmentos["foot"].isin(LIBERA_PEDESTRE)
    tabela["walk"] = tabela["walk"].to_numpy() & ~fechada.to_numpy()
    indice = indice_fisico(terreno.set_index("segment_id")[TERRENO])
    extras = indice[["percentil"] + COMPONENTES].join(terreno.set_index("segment_id")[TERRENO])
    return tabela.join(extras.astype("float32"), on="segmento_id")


def verificacao_descritiva(rede: Rede, eventos: pd.DataFrame, raio_m: float = 50, n_nulo: int = 1000, semente: int = 20261110) -> dict:
    """Where the segments of documented water-accumulation blockages fall in the physical index.

    Descriptive only. The events are few (one point each, a handful of dates, several on the same
    day) and are the same ones used to anchor the rain levels, so this says nothing about rain. It
    asks one thing: do the streets next to documented blockages sit higher in the terrain index than
    streets in general, and higher than under the plain "lowest elevation first" rule?
    """
    a = rede.arestas
    com_indice = a["drive"].to_numpy(bool) & np.isfinite(rede.pct)
    elev = (-a["elev"]).rank(pct=True).to_numpy() * 100
    pontos = eventos.dropna(subset=["latitude", "longitude"])
    vizinhos = [[i for i in rede.proximos(p.longitude, p.latitude, raio_m) if com_indice[i]] for p in pontos.itertuples()]
    vizinhos = [v for v in vizinhos if v]
    if not vizinhos:
        return {"eventos_com_segmento": 0}
    por_evento = [float(np.max(rede.pct[v])) for v in vizinhos]
    segmentos = sorted({i for v in vizinhos for i in v})
    descreve = lambda x: {"mediana": round(float(np.nanmedian(x[segmentos])), 1), "no_terco_superior": round(float(np.nanmean(x[segmentos] >= 70)), 3)}  # noqa: E731
    sorteio = np.random.default_rng(semente)
    candidatos = np.flatnonzero(com_indice)
    meio = lambda i: ((a["lon0"].iat[i] + a["lon1"].iat[i]) / 2, (a["lat0"].iat[i] + a["lat1"].iat[i]) / 2)  # noqa: E731
    nulo = []
    for _ in range(n_nulo):
        escolhidos = sorteio.choice(candidatos, size=min(len(vizinhos), len(candidatos)), replace=False)
        nulo.append(np.median([np.max(rede.pct[[j for j in rede.proximos(*meio(i), raio_m) if com_indice[j]] or [i]]) for i in escolhidos]))
    return {
        "natureza": "descritivo; não valida o índice nem o risco por trecho",
        "eventos_com_segmento": len(vizinhos), "datas_distintas": int(pontos["event_date"].nunique()), "segmentos_proximos": len(segmentos),
        "raio_m": raio_m, "segmentos_com_indice": int(com_indice.sum()),
        "indice_fisico": descreve(rede.pct), "regra_so_cota_baixa": descreve(elev),
        "mediana_geral_do_indice": round(float(np.nanmedian(rede.pct[com_indice])), 1),
        "mediana_por_evento_do_maximo_no_entorno": round(float(np.median(por_evento)), 1),
        "mediana_em_sorteios_aleatorios": round(float(np.mean(nulo)), 1), "p95_dos_sorteios": round(float(np.percentile(nulo, 95)), 1),
        "limites": ["poucos eventos (um ponto cada) concentrados em poucas datas: as unidades não são independentes",
                    "os mesmos eventos ancoraram os níveis de chuva; esta checagem só olha o terreno",
                    "se a regra de cota baixa se sai igual, os demais fatores não mostram ganho"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Street table of Porto Alegre for the routing service")
    parser.add_argument("--verificar", action="store_true", help="checagem descritiva do índice físico contra eventos documentados")
    args = parser.parse_args()
    if args.verificar:
        rede = Rede(pd.read_parquet(resolve(OUTPUT)), load_config()["roteamento"])
        resultado = verificacao_descritiva(rede, pd.read_csv(resolve("data/events/events.csv")))
        alvo = resolve("reports/ml/risco_trecho_descritivo.json")
        alvo.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({k: v for k, v in resultado.items() if k != "limites"}, ensure_ascii=False))
        return
    segmentos = gpd.read_parquet(resolve("data/interim/segments.parquet"))
    terreno = pd.read_parquet(resolve("data/interim/susceptibility_features_v2.parquet"))
    tabela = construir(segmentos, terreno, atributos_das_vias(resolve("data/interim/poa.osm.pbf")))
    saida = resolve(OUTPUT)
    saida.parent.mkdir(parents=True, exist_ok=True)
    tabela.to_parquet(saida)
    resumo = {"segmentos": len(tabela), "com_indice_fisico": int(tabela["percentil"].notna().sum()),
              "dirigiveis": int(tabela["drive"].sum()), "caminhaveis": int(tabela["walk"].sum()),
              "com_nome": int(tabela["nome"].notna().sum()), "tamanho_mb": round(saida.stat().st_size / 1e6, 1)}
    print(json.dumps(resumo))


if __name__ == "__main__":
    main()
