"""Coverage of the territories: where there is data, how complete it is, and what each region may offer.

Three things kept apart (see ``config/territorios.yaml``):

    capacidades   what the product enables in a region: declared once, in the configuration
    cobertura     where data exists, in numbers computed here from the real tables
    qualidade     completeness, currency and reliability, with the method that produced each number

Nothing here is estimated or typed by hand: every fraction is a length (km) or a count taken from the
tables the pipelines already produce, and a region without data is reported as such, never as zero.

    python -m flooding_mapping.cobertura   ->   app/static/data/{territorios,cobertura_rs}.json
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .config import load_config, resolve

if TYPE_CHECKING:   # geopandas is needed only to BUILD the state coverage; the server imports this module and stays light
    import geopandas as gpd

ESTADOS = ("disponivel", "parcial", "indisponivel")
CLASSES = ("disponivel", "parcial", "insuficiente")
ROTULOS = {"disponivel": "Dados disponíveis", "parcial": "Cobertura parcial", "insuficiente": "Dados insuficientes"}
METODO = ("Cobertura calculada pelo comprimento (km) dos segmentos da malha DAER (segmentos de cerca de 1 km, sem os trechos planejados): "
          "fração com índice físico, fração com VDM e contagens. Cada segmento é atribuído ao município que contém o seu ponto médio. "
          "A classe depende de quatro dimensões: malha DAER, índice físico "
          "(fração do km), tráfego VDM (fração do km) e registros hidrológicos do S2iD (só para municípios). 'Dados disponíveis' exige que todas "
          "atendam o mínimo configurado; 'dados insuficientes' é a região sem malha nem registros S2iD (só há meteorologia); as demais são "
          "'cobertura parcial'. Rodovias não têm dimensão S2iD. A classe descreve a existência de dados, não a validade de nenhuma análise.")


NOMES = {"malha": "malha rodoviária DAER", "indice_fisico": "índice físico", "vdm": "tráfego (VDM)", "ocorrencias_s2id": "registros hidrológicos do S2iD"}


def classificar(km: float, km_indice: float, km_vdm: float, s2id_total: int | None, minimos: dict) -> dict:
    """Which dimensions a region meets and the resulting class.

    ``s2id_total`` is ``None`` for a highway (the S2iD is municipal). The class is ``disponivel`` only when every
    dimension meets its minimum, ``insuficiente`` when there is neither a mapped network nor an S2iD record,
    and ``parcial`` otherwise."""
    dims = {"malha": km > 0,
            "indice_fisico": km > 0 and km_indice / km >= minimos["indice_fisico_minimo"],
            "vdm": km > 0 and km_vdm / km >= minimos["vdm_minimo"]}
    if s2id_total is not None:
        dims["ocorrencias_s2id"] = s2id_total > 0
    if all(dims.values()):
        classe, motivo = "disponivel", "Todas as dimensões atendem o mínimo configurado."
    elif not dims["malha"] and not dims.get("ocorrencias_s2id", False):
        classe, motivo = "insuficiente", "Sem malha rodoviária DAER nem registros hidrológicos do S2iD: só há meteorologia."
    else:
        classe = "parcial"
        faltam = []
        for nome, ok in dims.items():
            if ok:
                continue
            if nome == "vdm" and km > 0:
                faltam.append(f"tráfego (VDM) em {km_vdm / km:.0%} do km")
            elif nome == "indice_fisico" and km > 0:
                faltam.append(f"índice físico em {km_indice / km:.0%} do km")
            else:
                faltam.append(NOMES[nome])
        motivo = "Sem: " + "; ".join(faltam) + "."
    return {"classe": classe, "classe_rotulo": ROTULOS[classe], "motivo": motivo, "dimensoes": dims}


def municipio_do_segmento(segmentos: gpd.GeoDataFrame, towns: gpd.GeoDataFrame) -> pd.Series:
    """Municipality (ibge) whose polygon contains the midpoint of each segment; ``segmento_id`` -> ibge."""
    import geopandas as gpd

    meio = segmentos.set_index("segmento_id").geometry.interpolate(0.5, normalized=True)
    pontos = gpd.GeoDataFrame(index=meio.index, geometry=meio.values, crs=segmentos.crs).to_crs(towns.crs)
    dentro = gpd.sjoin(pontos, towns[["ibge", "geometry"]], predicate="within")
    return dentro[~dentro.index.duplicated()]["ibge"]


def _agrega(frame: pd.DataFrame, minimos: dict, s2id_total: int | None = None) -> dict:
    km = float(frame["km"].sum())
    km_indice = float(frame.loc[frame["tem_indice"], "km"].sum())
    km_vdm = float(frame.loc[frame["vdm"].notna(), "km"].sum())
    return {"segmentos": int(len(frame)), "km": round(km, 1), "km_com_indice_fisico": round(km_indice, 1), "km_com_vdm": round(km_vdm, 1),
            "pontes": int(frame["ponte"].sum()), **classificar(km, km_indice, km_vdm, s2id_total, minimos)}


def tabela_de_segmentos(segmentos: gpd.GeoDataFrame, trechos: pd.DataFrame, indice_ids: set, impacto: pd.DataFrame, towns: gpd.GeoDataFrame) -> pd.DataFrame:
    """One row per DAER segment with what is known about it (index, traffic, bridge) and where it lies."""
    t = trechos.drop_duplicates("objectid").set_index("objectid")[["vdm", "nome", "rede", "situacao_fisica"]]
    base = pd.DataFrame({"segmento_id": segmentos["segmento_id"].to_numpy(), "objectid": segmentos["objectid"].to_numpy(),
                         "km": segmentos["comprimento_m"].to_numpy() / 1000, "codigo_sre": segmentos["codigo_sre"].to_numpy()})
    base = base.join(t, on="objectid")
    base = base[~base["situacao_fisica"].fillna("").str.upper().eq("PLANEJADA")].copy()
    base["tem_indice"] = base["segmento_id"].isin(indice_ids)
    base["ponte"] = base["segmento_id"].map(impacto.set_index("segmento_id")["ponte"]).fillna(False).astype(bool)
    base["ibge"] = base["segmento_id"].map(municipio_do_segmento(segmentos, towns))
    return base


def por_municipio(tabela: pd.DataFrame, towns: pd.DataFrame, records: pd.DataFrame, minimos: dict, ate: pd.Timestamp) -> dict:
    """Coverage and context of every municipality, including those with no mapped road (reported as insufficient)."""
    from .ingestion import s2id

    hidro = records[records["cobrade"].isin(s2id.HYDRO_BROAD)]
    total = hidro.groupby("ibge").size()
    recente = hidro[hidro["data_evento"] >= ate - pd.Timedelta(days=90)].groupby("ibge").size()
    grupos = {i: g for i, g in tabela.dropna(subset=["ibge"]).groupby("ibge")}
    saida = {}
    for ibge in towns["ibge"]:
        n = int(total.get(ibge, 0))
        info = _agrega(grupos.get(ibge, tabela.iloc[0:0]), minimos, n)
        saida[ibge] = {**info, "s2id_hidrologicos_2017_2026": n, "s2id_hidrologicos_90_dias": int(recente.get(ibge, 0))}
    return saida


def por_rodovia(tabela: pd.DataFrame, minimos: dict) -> dict:
    """Coverage of every highway (grouped by name), with the municipalities it crosses."""
    saida = {}
    for nome, g in tabela.dropna(subset=["nome"]).groupby("nome"):
        saida[nome] = {**_agrega(g, minimos), "rede": g["rede"].mode().iat[0], "municipios_atravessados": int(g["ibge"].nunique()),
                       "trechos": int(g["objectid"].nunique())}
    return saida


def resumo(municipios: dict, rodovias: dict, tabela: pd.DataFrame) -> dict:
    """State totals: the numbers a reader needs to judge how much of the state the analysis reaches."""
    classes = pd.Series([m["classe"] for m in municipios.values()]).value_counts()
    km = float(tabela["km"].sum())
    return {"municipios": len(municipios), "municipios_por_classe": {c: int(classes.get(c, 0)) for c in CLASSES},
            "segmentos": int(len(tabela)), "km": round(km, 1),
            "fracao_km_com_indice_fisico": round(float(tabela.loc[tabela["tem_indice"], "km"].sum() / km), 3),
            "fracao_km_com_vdm": round(float(tabela.loc[tabela["vdm"].notna(), "km"].sum() / km), 3),
            "rodovias": len(rodovias), "rodovias_por_classe": {c: sum(1 for r in rodovias.values() if r["classe"] == c) for c in CLASSES}}


def cobertura_poa(rede: pd.DataFrame) -> dict:
    """Share of the street length (km) with a terrain index, by kind of way."""
    km = rede["comprimento_m"] / 1000
    tem = rede["percentil"].notna()

    def parte(mask) -> dict:
        total = float(km[mask].sum())
        return {"km": round(total, 1), "fracao_com_indice": round(float(km[mask & tem].sum() / total), 3) if total else None}
    return {"dirigivel": parte(rede["drive"]), "caminhavel": parte(rede["walk"]),
            "somente_a_pe": parte(rede["walk"] & ~rede["drive"]), "nenhum_modal": parte(~rede["walk"] & ~rede["drive"]),
            "segmentos": int(len(rede)), "fonte": "OpenStreetMap; índice físico por segmento (Copernicus DEM GLO-30)"}


def validar_capacidades(config: dict) -> None:
    """The configuration may not over-claim: a known state per capability, a reason when unavailable,
    and no street-level risk presented as available."""
    for nome, t in config["territorios"].items():
        for cap, c in t["capacidades"].items():
            if c["estado"] not in ESTADOS:
                raise ValueError(f"{nome}.{cap}: estado inválido {c['estado']!r}")
            if c["estado"] == "indisponivel" and not c.get("motivo"):
                raise ValueError(f"{nome}.{cap}: capacidade indisponível precisa de motivo")
            if cap == "risco_por_trecho" and c["estado"] == "disponivel":
                raise ValueError(f"{nome}.risco_por_trecho não pode ser 'disponivel': não há validação em nível de via")


def montar(config: dict, resumo_rs: dict | None, poa: dict | None, gerado_em: str | None = None) -> dict:
    """The ``territorios.json`` the interfaces read: capabilities, coverage summaries and the method."""
    validar_capacidades(config)
    territorios = {}
    for nome, t in config["territorios"].items():
        territorios[nome] = {**t, "cobertura": resumo_rs if nome == "rs" else poa}
    return {"gerado_em": gerado_em or date.today().isoformat(), "metodo_de_cobertura": METODO, "rotulos_de_classe": ROTULOS,
            "minimos": config["classificacao"], "territorios": territorios}


def main() -> None:
    import geopandas as gpd

    argparse.ArgumentParser(description="Cobertura dos territórios (RS e Porto Alegre)").parse_args()
    config = {**load_config(), **yaml_territorios()}
    minimos = config["classificacao"]
    segmentos = gpd.read_parquet(resolve("data/interim/daer_segmentos.parquet"))
    trechos = gpd.read_parquet(resolve("data/interim/daer_trechos.parquet")).drop(columns="geometry")
    towns = gpd.read_parquet(resolve("data/interim/municipios.parquet"))
    indice = pd.read_parquet(resolve("data/interim/indice_fisico_segmentos.parquet"))
    impacto = pd.read_parquet(resolve("data/interim/impacto_rs.parquet"))
    records = pd.read_parquet(resolve("data/interim/s2id_rs.parquet"))
    tabela = tabela_de_segmentos(segmentos, trechos, set(indice.index), impacto, towns)
    municipios = por_municipio(tabela, towns, records, minimos, records["data_evento"].max())
    rodovias = por_rodovia(tabela, minimos)
    resumo_rs = resumo(municipios, rodovias, tabela)
    rede_poa = resolve("data/processed/rede_poa.parquet")
    poa = cobertura_poa(pd.read_parquet(rede_poa, columns=["comprimento_m", "percentil", "drive", "walk"])) if rede_poa.exists() else None
    saida = resolve("src/flooding_mapping/app/static/data")
    (saida / "territorios.json").write_text(json.dumps(montar(config, resumo_rs, poa), ensure_ascii=False, separators=(",", ":")))
    (saida / "cobertura_rs.json").write_text(json.dumps(
        {"metodo": METODO, "estado": resumo_rs, "municipios": municipios, "rodovias": rodovias}, ensure_ascii=False, separators=(",", ":")))
    print(json.dumps(resumo_rs, ensure_ascii=False))


def yaml_territorios() -> dict:
    import yaml

    with open(resolve("config/territorios.yaml"), encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


if __name__ == "__main__":
    main()
