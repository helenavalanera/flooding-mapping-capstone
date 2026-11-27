"""Distribuição das saídas da Fase 3 para a aplicação (Fase 4): preparação, sem recalcular nada.

Os Parquets de ``data/processed/fase3/`` continuam sendo a fonte de referência. Este módulo só lê esses arquivos e escreve, em
``data/processed/fase3_web/`` (derivado, fora do Git, como todo dado processado), duas coisas que o navegador consegue consumir:

* ``tiles/{z}/{x}/{y}.pbf``: tiles vetoriais com a geometria real dos trechos e, por trecho, **só** um número de ordem (``n``) e
  **classes visuais** inteiras (0 a 6). Nenhum valor físico viaja nos tiles.
* ``detalhe/NNNN.json``: fragmentos (1.024 trechos cada) com os valores do painel, em m² de área equivalente (``aeq``), exatamente
  como estão nos Parquets (9 algarismos significativos). O volume de uma chuva de referência é ``P x aeq / 1000``, uma operação
  linear que o teste confere contra ``trechos_nivel2_cenarios.parquet`` (a saída do motor).
* ``meta.json``: precipitações das execuções, pacotes, cortes das classes, contagens e hashes das entradas.

Ausência é ausência: valor ``NaN`` vira ``null`` no fragmento e **nenhuma classe** no tile (o trecho é pintado como "sem dados"),
nunca zero. Zero é a classe ``0``, distinta. As classes são por quantis dos trechos com valor positivo, então valem para qualquer
chuva (a escala é linear): só a legenda em m³ muda com a precipitação.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

TAMANHO_DO_FRAGMENTO = 1024
ZOOM_MINIMO, ZOOM_MAXIMO = 13, 15   # abaixo de 13 os tiles passam de 1,9 MB e perdem milhares de trechos curtos: a camada só desenha de perto
QUANTIS_DAS_CLASSES = (0.20, 0.40, 0.60, 0.80, 0.95)      # cortes entre as classes 1..6 dos valores positivos
CORTES_DA_COBERTURA = (0.25, 0.50, 0.75)                   # fração da área a montante: classes 1..4 (0 = exatamente zero)
CORTES_DO_POSTO_TOPOGRAFICO = (85.0, 92.0, 97.0)           # posto (0 a 100) entre os trechos com dados: classes 1..4
PACOTES = {"m1": "metodo1", "li": "limites_fisicos", "an": "referencia_analoga"}   # chave curta (tile) -> nome no Parquet de cenários
COLUNA_AEQ = {"m1": "aeq_m1", "li": "aeq_limites", "an": "aeq_analoga"}
LIMITES = ("min", "max")
GRANDEZAS = {"l": "local", "c": "contrib"}                 # l: volume potencial gerado (local); c: contribuição potencial associada ao trecho
COLUNAS_DE_COBERTURA = {"cb_m1": "fracao_montante_coberta_m1", "cb_li": "fracao_montante_com_valor_limites", "cb_an": "fracao_montante_com_valor_analoga"}

# Ordem das colunas de cada fragmento (o navegador lê por nome, via ``colunas`` do próprio fragmento).
COLUNAS_DO_DETALHE = (["id", "nome", "via", "n_cel", "n_cheg"]
                      + [f"{g}_{p}_{b}" for g in GRANDEZAS for p in PACOTES for b in LIMITES]
                      + ["area_montante_m2", "f_m1", "f_li", "f_an", "f_an_sem", "f_fora", "f_sem_classe", "topo_altura_max_m", "topo_altura_media_m", "topo_posto"])


class CamadaInvalida(Exception):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def arredonda(v: float) -> float | None:
    """9 algarismos significativos (erro relativo < 1e-9, abaixo da precisão do que o painel mostra); NaN vira ausência."""
    return None if v is None or not np.isfinite(v) else float(f"{float(v):.9g}")


def carregar(fase3: Path, segmentos: Path, rede: Path) -> pd.DataFrame:
    """Une as tabelas por ``segmento_id`` e ordena por identificador: a posição é o número ``n`` do trecho. Não calcula nada."""
    base = pd.read_parquet(fase3 / "trechos_contribuicao_base.parquet")
    topo = pd.read_parquet(fase3 / "trechos_nivel1_propensao_topografica.parquet").drop(columns=["n_celulas_com_dados"])
    nomes = pd.read_parquet(rede, columns=["segmento_id", "nome", "highway"])
    geo = gpd.read_parquet(segmentos, columns=["segment_id", "geometry"]).rename(columns={"segment_id": "segmento_id"})
    for nome, t in (("base", base), ("topografia", topo), ("rede", nomes), ("geometria", geo)):
        if not t["segmento_id"].is_unique:
            raise CamadaInvalida(f"identificadores repetidos em {nome}")
    tabela = base.merge(topo, on="segmento_id", how="left", validate="1:1").merge(nomes, on="segmento_id", how="left", validate="1:1")
    if len(tabela) != len(base) or tabela["altura_de_preenchimento_max_m"].isna().sum() != base["local_aeq_m1_max_m2"].isna().sum():
        raise CamadaInvalida("a união das tabelas mudou o número de trechos ou criou ausências")
    ausentes_na_geometria = set(tabela["segmento_id"]) - set(geo["segmento_id"])
    if ausentes_na_geometria:
        raise CamadaInvalida(f"{len(ausentes_na_geometria)} trechos sem geometria")
    tabela = tabela.sort_values("segmento_id", kind="mergesort").reset_index(drop=True)
    geometria = geo.set_index("segmento_id")["geometry"].reindex(tabela["segmento_id"]).to_numpy()
    return gpd.GeoDataFrame(tabela, geometry=geometria, crs=geo.crs)


def cortes_por_quantis(valores: pd.Series) -> list[float]:
    positivos = valores[valores > 0].dropna()
    if positivos.empty:
        return []
    return [float(np.quantile(positivos, q)) for q in QUANTIS_DAS_CLASSES]


def classe_por_cortes(valores: pd.Series, cortes: list[float]) -> pd.Series:
    """Ausente -> <NA> (sem classe); zero -> 0; positivo -> 1 + número de cortes que o valor alcança."""
    v = valores.to_numpy(dtype=float)
    saida = np.where(v > 0, 1 + np.searchsorted(np.asarray(cortes), v, side="right"), 0)
    return pd.Series(pd.array(np.where(np.isnan(v), -1, saida), dtype="Int8")).mask(np.isnan(v))


def classe_da_fracao(fracao: pd.Series) -> pd.Series:
    v = fracao.to_numpy(dtype=float)
    saida = np.where(v > 0, 1 + np.searchsorted(np.asarray(CORTES_DA_COBERTURA), v, side="left"), 0)
    return pd.Series(pd.array(np.where(np.isnan(v), -1, saida), dtype="Int8")).mask(np.isnan(v))


def classes_visuais(tabela: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Classes inteiras por trecho e os cortes (em m² de área equivalente) que as definem."""
    classes, cortes = {}, {}
    for g, grandeza in GRANDEZAS.items():
        for p, coluna in COLUNA_AEQ.items():
            for b in LIMITES:
                nome = f"{grandeza}_{coluna}_{b}_m2"
                chave = f"{g}_{p}_{b}"
                cortes[chave] = cortes_por_quantis(tabela[nome])
                classes[chave] = classe_por_cortes(tabela[nome], cortes[chave])
    for chave, coluna in COLUNAS_DE_COBERTURA.items():
        classes[chave] = classe_da_fracao(tabela[coluna])
    altura, posto = tabela["altura_de_preenchimento_max_m"], tabela["propensao_topografica_percentil"]
    com_altura = altura > 0
    tp = np.where(altura.isna(), -1, np.where(com_altura, 1 + np.searchsorted(np.asarray(CORTES_DO_POSTO_TOPOGRAFICO), posto.fillna(0).to_numpy(), side="right"), 0))
    classes["tp"] = pd.Series(pd.array(tp, dtype="Int8")).mask(altura.isna().to_numpy())
    return pd.DataFrame(classes), cortes


def fragmentos(tabela: pd.DataFrame) -> list[dict]:
    """Os valores do painel, por trecho, na ordem de ``n``. ``null`` onde o Parquet não tem valor."""
    t = tabela
    colunas = {"id": t["segmento_id"], "nome": t["nome"], "via": t["highway"], "n_cel": t["n_celulas_com_dados"], "n_cheg": t["n_celulas_de_chegada"]}
    for g, grandeza in GRANDEZAS.items():
        for p, coluna in COLUNA_AEQ.items():
            for b in LIMITES:
                colunas[f"{g}_{p}_{b}"] = t[f"{grandeza}_{coluna}_{b}_m2"]
    colunas.update({"area_montante_m2": t["area_montante_m2"], "f_m1": t["fracao_montante_coberta_m1"], "f_li": t["fracao_montante_com_valor_limites"],
                    "f_an": t["fracao_montante_com_valor_analoga"], "f_an_sem": t["fracao_montante_sem_valor_analoga"], "f_fora": t["fracao_montante_fora_do_calculo"],
                    "f_sem_classe": t["fracao_montante_sem_classe"], "topo_altura_max_m": t["altura_de_preenchimento_max_m"],
                    "topo_altura_media_m": t["altura_de_preenchimento_media_m"], "topo_posto": t["propensao_topografica_percentil"]})
    assert tuple(colunas) == tuple(COLUNAS_DO_DETALHE)
    linhas = []
    for i in range(len(t)):
        linha = []
        for k, serie in colunas.items():
            v = serie.iloc[i]
            if k in ("id", "nome", "via"):
                linha.append(None if pd.isna(v) else str(v))
            elif k in ("n_cel", "n_cheg"):
                linha.append(int(v))
            else:
                linha.append(arredonda(v))
        linhas.append(linha)
    return [{"colunas": list(COLUNAS_DO_DETALHE), "primeiro_n": i, "linhas": linhas[i:i + TAMANHO_DO_FRAGMENTO]} for i in range(0, len(linhas), TAMANHO_DO_FRAGMENTO)]


def escrever_geojson(tabela: gpd.GeoDataFrame, classes: pd.DataFrame, caminho: Path) -> None:
    """GeoJSON em WGS84 só para alimentar o gerador de tiles: ``n`` e classes inteiras; classe ausente = propriedade ausente."""
    lonlat = tabela.geometry.to_crs("EPSG:4326")
    with open(caminho, "w") as f:
        f.write('{"type":"FeatureCollection","features":[')
        for i in range(len(tabela)):
            props = {"n": i}
            for k in classes.columns:
                v = classes[k].iloc[i]
                if not pd.isna(v):
                    props[k] = int(v)
            geom = json.loads(shapely_geojson(lonlat.iloc[i]))
            f.write(("," if i else "") + json.dumps({"type": "Feature", "properties": props, "geometry": geom}, separators=(",", ":")))
        f.write("]}")


def shapely_geojson(geom) -> str:
    from shapely import set_precision, to_geojson

    return to_geojson(set_precision(geom, 1e-6))   # 0,1 m: abaixo da escala do mapa


def gerar_tiles(geojson: Path, saida: Path, camada: str = "trechos", zmin: int = ZOOM_MINIMO, zmax: int = ZOOM_MAXIMO) -> None:
    ogr = shutil.which("ogr2ogr")
    if ogr is None:
        raise CamadaInvalida("ogr2ogr (GDAL) não encontrado: ele gera os tiles vetoriais")
    shutil.rmtree(saida, ignore_errors=True)
    saida.parent.mkdir(parents=True, exist_ok=True)
    comando = [ogr, "-f", "MVT", str(saida), str(geojson), "-nln", camada, "-dsco", f"MINZOOM={zmin}", "-dsco", f"MAXZOOM={zmax}",
               "-dsco", "COMPRESS=NO", "-dsco", "MAX_SIZE=2000000", "-dsco", "MAX_FEATURES=200000", "-dsco", "SIMPLIFICATION=2", "-dsco", "SIMPLIFICATION_MAX_ZOOM=13"]
    r = subprocess.run(comando, capture_output=True, text=True)
    if r.returncode != 0:
        raise CamadaInvalida(f"ogr2ogr falhou: {r.stderr[-500:]}")
    if "Warning" in r.stderr:
        raise CamadaInvalida(f"o gerador de tiles avisou (possível descarte de feições): {r.stderr[-500:]}")


def hipoteses() -> dict:
    """Coeficientes e hipóteses exatamente como o motor os usa (``motor_acumulo.faixas_por_pacote``), para o painel mostrar a origem de cada intervalo."""
    from . import escoamento, motor_acumulo

    m1, m2 = escoamento.carregar_metodo1(), escoamento.carregar_cenarios()
    faixas = motor_acumulo.faixas_por_pacote(m1, m2)
    jardins = m2[m2.cenario.str.startswith("referencia_analoga_jardins_f")]
    return {
        "metodo1": [{"classe": r.classe_original, "c_min": float(r.c_min), "c_max": float(r.c_max), "grau_de_incerteza": r.grau_de_incerteza, "referencia": r.referencia} for r in m1.itertuples()],
        "limites_fisicos": {"c_min": 0.0, "c_max": 1.0, "classes": len(faixas["limites_fisicos"]), "natureza": "limite por definição, não é estimativa"},
        "referencia_analoga": [{"classe": c, "c_min": lo, "c_max": hi} for c, (lo, hi) in sorted(faixas["referencia_analoga"].items())],
        "jardins_e_passeios": {"classe": motor_acumulo.CLASSE_JARDINS, "envelope": [float(jardins.c_min.min()), float(jardins.c_max.max())],
                               "cenarios_de_fracao_de_piso": [{"fracao_de_piso": int(r.cenario.rsplit("_f", 1)[1]), "c_min": float(r.c_min), "c_max": float(r.c_max)} for r in jardins.itertuples()],
                               "hipotese": jardins.hipotese_declarada.iloc[0]},
        "fora_do_calculo": sorted(faixas["fora_do_calculo"]),
    }


def preencher_tiles_vazios(tiles: Path, limites: tuple[float, float, float, float], zmin: int = ZOOM_MINIMO, zmax: int = ZOOM_MAXIMO) -> int:
    """Tiles sem trechos (água, bordas) não existem; um 404 por tile polui o console. Dentro da caixa dos dados, o tile vazio é um arquivo vazio."""
    import math

    oeste, sul, leste, norte = limites
    criados = 0

    def xy(lon, lat, z):
        n = 2 ** z
        return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)

    for z in range(zmin, zmax + 1):
        x0, y1 = xy(oeste, sul, z)
        x1, y0 = xy(leste, norte, z)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                arq = tiles / str(z) / str(x) / f"{y}.pbf"
                if not arq.exists():
                    arq.parent.mkdir(parents=True, exist_ok=True)
                    arq.write_bytes(b"")
                    criados += 1
    return criados


def construir_meta(tabela: pd.DataFrame, cortes: dict, precipitacoes: list[float], entradas: dict[str, str]) -> dict:
    com_dados = tabela["local_aeq_m1_max_m2"].notna()
    return {
        "versao": 1, "unidade_de_apresentacao": "trecho viário", "unidade_computacional": "célula raster de 30 m",
        "trechos_menores_que_1_m": int((tabela.geometry.length.to_numpy() < 1.0).sum()),   # os de poucos decímetros colapsam a um ponto nos tiles
        "trechos": int(len(tabela)), "trechos_com_dados": int(com_dados.sum()), "trechos_sem_dados": int((~com_dados).sum()),
        "precipitacoes_mm": precipitacoes, "tamanho_do_fragmento": TAMANHO_DO_FRAGMENTO, "zoom": [ZOOM_MINIMO, ZOOM_MAXIMO],
        "pacotes": {k: v for k, v in PACOTES.items()}, "grandezas": GRANDEZAS, "limites": list(LIMITES),
        "cortes_das_classes_aeq_m2": cortes, "quantis_das_classes": list(QUANTIS_DAS_CLASSES),
        "cortes_da_cobertura": list(CORTES_DA_COBERTURA), "cortes_do_posto_topografico": list(CORTES_DO_POSTO_TOPOGRAFICO),
        "colunas_do_detalhe": list(COLUNAS_DO_DETALHE), "casas_significativas": 9, "hipoteses": hipoteses(),
        "entradas_sha256": entradas,
    }


def preparar(fase3: Path, segmentos: Path, rede: Path, saida: Path, trabalho: Path) -> dict:
    tabela = carregar(fase3, segmentos, rede)
    classes, cortes = classes_visuais(tabela)
    cenarios = pd.read_parquet(fase3 / "trechos_nivel2_cenarios.parquet", columns=["p_mm"])
    precipitacoes = sorted(float(p) for p in cenarios["p_mm"].unique())
    entradas = {p.name: sha256(p) for p in sorted(fase3.glob("*.parquet"))}
    trabalho.mkdir(parents=True, exist_ok=True)
    geojson = trabalho / "trechos_fase3.geojson"
    escrever_geojson(tabela, classes, geojson)
    shutil.rmtree(saida, ignore_errors=True)
    (saida / "detalhe").mkdir(parents=True)
    gerar_tiles(geojson, saida / "tiles")
    tiles_vazios = preencher_tiles_vazios(saida / "tiles", tuple(float(v) for v in tabela.geometry.to_crs("EPSG:4326").total_bounds))
    for k, frag in enumerate(fragmentos(tabela)):
        (saida / "detalhe" / f"{k:04d}.json").write_text(json.dumps(frag, ensure_ascii=False, separators=(",", ":")))
    meta = construir_meta(tabela, cortes, precipitacoes, entradas)
    meta["tiles_vazios_dentro_da_caixa_dos_dados"] = tiles_vazios
    (saida / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


# ----------------------------------------------------------------------------------------------- leitura de tiles (verificação)
def _varint(b: bytes, i: int) -> tuple[int, int]:
    n = s = 0
    while True:
        x = b[i]
        i += 1
        n |= (x & 0x7F) << s
        if not x & 0x80:
            return n, i
        s += 7


def _campos(b: bytes):
    i = 0
    while i < len(b):
        chave, i = _varint(b, i)
        campo, tipo = chave >> 3, chave & 7
        if tipo == 0:
            v, i = _varint(b, i)
        elif tipo == 2:
            n, i = _varint(b, i)
            v, i = b[i:i + n], i + n
        elif tipo == 1:
            v, i = b[i:i + 8], i + 8
        elif tipo == 5:
            v, i = b[i:i + 4], i + 4
        else:
            raise CamadaInvalida(f"tipo de campo protobuf inesperado: {tipo}")
        yield campo, v


def ler_tile(dados: bytes) -> list[dict]:
    """Propriedades de cada feição de um tile MVT (leitor mínimo, sem dependências), para conferir o que foi distribuído."""
    saida = []
    for campo, camada in _campos(dados):
        if campo != 3:
            continue
        chaves, valores, feicoes = [], [], []
        for c, v in _campos(camada):
            if c == 3:
                chaves.append(v.decode())
            elif c == 4:
                for t, x in _campos(v):
                    valores.append({1: lambda y: y.decode(), 4: lambda y: y, 5: lambda y: y, 6: lambda y: (y >> 1) ^ -(y & 1), 7: bool}.get(t, lambda y: y)(x))
            elif c == 2:
                feicoes.append(v)
        for f in feicoes:
            tags = []
            for c, v in _campos(f):
                if c == 2:
                    j = 0
                    while j < len(v):
                        t, j = _varint(v, j)
                        tags.append(t)
            saida.append({chaves[tags[k]]: valores[tags[k + 1]] for k in range(0, len(tags), 2)})
    return saida
