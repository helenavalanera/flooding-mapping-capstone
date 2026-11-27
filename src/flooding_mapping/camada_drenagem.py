"""Inventário de drenagem (Fase 2) para a aplicação: camada contextual, independente do cálculo de escoamento.

Lê ``data/processed/drenagem/*.parquet`` (que não são alterados) e escreve em ``data/processed/drenagem_web/``:

* ``tiles/<camada>/{z}/{x}/{y}.pbf``: geometria real, ``n`` (número de ordem) e poucas classes inteiras (categoria do cadastro, registro
  duplicado, sinalização de valor fora da faixa plausível). Nenhum atributo viaja nos tiles.
* ``detalhe/<camada>/NNNN.json``: **todos** os atributos originais do cadastro e os indicadores de qualidade, por registro, na ordem de ``n``.
  Nulo continua nulo (o painel diz "não informado"), nunca zero.
* ``meta.json``: contagens, colunas, unidades (do dicionário de campos, quando inferidas, marcadas assim) e SHA-256 das entradas.

O que a camada **não** diz: capacidade de vazão, funcionamento atual, conectividade hidráulica ou eficiência. As colunas ``evidencia_geometrica_*``
são coincidências de geometria medidas na Fase 2, não conexão hidráulica, e o painel as rotula assim.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from . import camada_fase3 as base

TAMANHO_DO_FRAGMENTO = 1024
# camada -> (arquivo, zoom mínimo dos tiles, zoom máximo)
CAMADAS = {"rede": ("rede_pluvial.parquet", 14, 15), "pocos": ("pocos_de_visita.parquet", 15, 15),
           "bocas": ("bocas_de_lobo.parquet", 15, 15), "bombas": ("casas_de_bomba.parquet", 14, 15)}
CATEGORIA_DA_REDE = {"rede_pluvial": 0, "rede_pluvial_sem_acesso": 1, "rede_pluvial_nao_interligada": 2}   # só o que o cadastro declara (camada de origem)
SINALIZACOES = ("fora_da_faixa_plausivel", "data_implantacao_suspeita")                                        # sufixos/nomes das colunas de qualidade que marcam valor suspeito


def carregar(pasta: Path, camada: str) -> gpd.GeoDataFrame:
    arquivo = CAMADAS[camada][0]
    d = gpd.read_parquet(pasta / arquivo)
    if d.geometry.isna().any() or d.geometry.is_empty.any():
        raise ValueError(f"{arquivo}: geometria ausente ou vazia")
    chaves = [c for c in ("camada_origem", "id_origem") if c in d.columns]
    d = d.reset_index(drop=True)
    d["_ordem"] = np.arange(len(d))
    d = d.sort_values(chaves + ["_ordem"], kind="mergesort").drop(columns="_ordem").reset_index(drop=True)   # n = posição: ordem estável e reproduzível
    return d


def sinalizada(d: pd.DataFrame) -> pd.Series:
    colunas = [c for c in d.columns if c.endswith("_fora_da_faixa_plausivel") or c == "data_implantacao_suspeita"]
    if not colunas:
        return pd.Series(False, index=d.index)
    return d[colunas].fillna(False).astype(bool).any(axis=1)


def classes(d: pd.DataFrame, camada: str) -> pd.DataFrame:
    """Classes inteiras dos tiles. ``u``: 1 = registro duplicado (fora do inventário). ``s``: 1 = algum valor fora da faixa plausível ou data suspeita."""
    c = pd.DataFrame(index=d.index)
    if camada == "rede":
        if not set(d["camada_origem"]) <= set(CATEGORIA_DA_REDE):
            raise ValueError(f"camada de origem desconhecida: {sorted(set(d['camada_origem']) - set(CATEGORIA_DA_REDE))}")
        c["cat"] = d["camada_origem"].map(CATEGORIA_DA_REDE).astype(int)
    c["u"] = (~d["usar_no_inventario"].astype(bool)).astype(int)
    c["s"] = sinalizada(d).astype(int)
    return c


def _valor(v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)) or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return float(f"{float(v):.9g}")
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return str(v) if not isinstance(v, (int, str)) else v


def fragmentos(d: gpd.GeoDataFrame) -> list[dict]:
    colunas = [c for c in d.columns if c != "geometry"]
    linhas = [[_valor(v) for v in r] for r in d[colunas].itertuples(index=False, name=None)]
    return [{"colunas": colunas, "primeiro_n": i, "linhas": linhas[i:i + TAMANHO_DO_FRAGMENTO]} for i in range(0, len(linhas), TAMANHO_DO_FRAGMENTO)]


def escrever_geojson(d: gpd.GeoDataFrame, cl: pd.DataFrame, caminho: Path) -> None:
    from shapely import set_precision, to_geojson

    lonlat = d.geometry.to_crs("EPSG:4326")
    with open(caminho, "w") as f:
        f.write('{"type":"FeatureCollection","features":[')
        cols = list(cl.columns)
        valores = cl.to_numpy()
        for i in range(len(d)):
            props = {"n": i, **{k: int(valores[i][j]) for j, k in enumerate(cols)}}
            f.write(("," if i else "") + '{"type":"Feature","properties":' + json.dumps(props, separators=(",", ":")) + ',"geometry":' + to_geojson(set_precision(lonlat.iloc[i], 1e-6)) + "}")
        f.write("]}")


def contagens(d: pd.DataFrame, cl: pd.DataFrame, camada: str) -> dict:
    o = {"registros": int(len(d)), "duplicados_fora_do_inventario": int(cl["u"].sum()), "com_valor_sinalizado": int(cl["s"].sum())}
    if camada == "rede":
        o["por_categoria"] = {k: int((cl["cat"] == v).sum()) for k, v in CATEGORIA_DA_REDE.items()}
    return o


def preparar(pasta: Path, saida: Path, trabalho: Path) -> dict:
    dicionario = json.loads((pasta / "dicionario_de_campos.json").read_text())
    qualidade = json.loads((pasta / "qualidade_drenagem.json").read_text())
    shutil.rmtree(saida, ignore_errors=True)
    meta = {"versao": 1, "natureza": "cadastro municipal: registro, não funcionamento", "tamanho_do_fragmento": TAMANHO_DO_FRAGMENTO,
            "entradas_sha256": {p.name: base.sha256(p) for p in sorted(pasta.glob("*")) if p.is_file()}, "camadas": {},
            "dicionario_de_campos": dicionario, "versao_do_processamento": qualidade.get("versao_do_processamento")}
    trabalho.mkdir(parents=True, exist_ok=True)
    for camada, (arquivo, zmin, zmax) in CAMADAS.items():
        d = carregar(pasta, camada)
        cl = classes(d, camada)
        geo = trabalho / f"{camada}.geojson"
        escrever_geojson(d, cl, geo)
        base.gerar_tiles(geo, saida / "tiles" / camada, camada, zmin, zmax)
        vazios = base.preencher_tiles_vazios(saida / "tiles" / camada, tuple(float(v) for v in d.geometry.to_crs("EPSG:4326").total_bounds), zmin, zmax)
        (saida / "detalhe" / camada).mkdir(parents=True)
        for k, frag in enumerate(fragmentos(d)):
            (saida / "detalhe" / camada / f"{k:04d}.json").write_text(json.dumps(frag, ensure_ascii=False, separators=(",", ":")))
        meta["camadas"][camada] = {"arquivo": arquivo, "zoom": [zmin, zmax], "colunas": [c for c in d.columns if c != "geometry"], "tiles_vazios": vazios, **contagens(d, cl, camada),
                                   "geometria": "linha" if camada == "rede" else "ponto"}
    (saida / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta
