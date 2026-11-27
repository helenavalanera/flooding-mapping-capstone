"""Rótulos por célula (Profill 2022), blocos espaciais, dobras e referências auxiliares (OSM, bairros).

A Profill é interpretação visual de ortoimagem de 30 cm (2018 a 2021): referência cartográfica de alta resolução, não verdade de campo. A classe mista
"Jardins, Passeios ou Áreas semi urbanizadas" não tem fração impermeável conhecida; fica fora das frações e vira estrato nas métricas.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

GRUPOS = ["construido", "vegetacao", "solo_exposto", "agua"]


def alvos_da_profill(grade_parquet: Path, classes_json: Path, grade: dict, rotulos: dict) -> dict[str, np.ndarray]:
    """Frações dos quatro grupos sobre a área classificada em grupo não misto, por célula.

    Devolve rasters (linhas, colunas): ``frac_<grupo>``, ``nao_mista_m2``, ``jardins_frac`` (parte da célula em classe mista) e ``valida`` (célula usável).
    """
    codigos = json.loads(classes_json.read_text())["codigos"]
    g = pd.read_parquet(grade_parquet)
    desconhecidas = {c for k in (*GRUPOS, "misto_excluido") for c in rotulos[k]} - set(codigos)
    if desconhecidas:
        raise ValueError(f"classes inexistentes na Profill: {sorted(desconhecidas)}")
    col = lambda nome: f"area_m2__{codigos[nome]:02d}"  # noqa: E731
    area_grupo = {k: sum(g[col(c)].to_numpy("float64") for c in rotulos[k]) for k in GRUPOS}
    nao_mista = sum(area_grupo.values())
    mista = sum(g[col(c)].to_numpy("float64") for c in rotulos["misto_excluido"])
    celula_m2 = grade["celula_m"] ** 2
    shape = (grade["linhas"], grade["colunas"])
    r, c = g["linha"].to_numpy(), g["coluna"].to_numpy()

    def raster(v: np.ndarray, vazio: float = np.nan) -> np.ndarray:
        a = np.full(shape, vazio, dtype="float32")
        a[r, c] = v
        return a

    out = {f"frac_{k}": raster(np.where(nao_mista > 0, area_grupo[k] / np.where(nao_mista > 0, nao_mista, 1), np.nan)) for k in GRUPOS}
    out["nao_mista_m2"], out["jardins_frac"] = raster(nao_mista), raster(mista / celula_m2)
    out["edificacao_m2"], out["construido_m2"] = raster(g[col("Edificação")].to_numpy("float64")), raster(area_grupo["construido"])
    out["valida"] = np.isfinite(out["nao_mista_m2"]) & (np.nan_to_num(out["nao_mista_m2"]) >= rotulos["celula_minima_nao_mista_m2"])
    return out


def identificador_de_blocos(shape: tuple[int, int], bloco: int) -> np.ndarray:
    """Raster com o número do bloco (bloco x bloco células) de cada célula."""
    lin, col = np.indices(shape)
    n_col = -(-shape[1] // bloco)
    return (lin // bloco) * n_col + (col // bloco)


def dobras_por_blocos(blocos: np.ndarray, valida: np.ndarray, estrato: np.ndarray, k: int, semente: int, minimo_de_celulas: int = 200) -> tuple[np.ndarray, dict]:
    """Atribui cada bloco com dado a uma de ``k`` dobras, equilibrando o estrato (fração construída média do bloco) entre elas.

    Blocos com menos de ``minimo_de_celulas`` células válidas ficam de fora (-1): são bordas do município. Devolve o raster de dobras e o registro dos blocos.
    """
    ids = np.unique(blocos[valida])
    n = np.array([int((valida & (blocos == b)).sum()) for b in ids])
    media = np.array([float(np.nanmean(estrato[valida & (blocos == b)])) for b in ids])
    usados = n >= minimo_de_celulas
    rng = np.random.default_rng(semente)
    ordem = np.argsort(media[usados])
    ids_u = ids[usados][ordem]
    dobra_do_bloco = {}
    for i in range(0, len(ids_u), k):                 # a cada k blocos de fração parecida, um para cada dobra, em ordem aleatória
        grupo = ids_u[i:i + k]
        for b, d in zip(grupo, rng.permutation(k)[:len(grupo)]):
            dobra_do_bloco[int(b)] = int(d)
    dobras = np.full(blocos.shape, -1, dtype="int16")
    for b, d in dobra_do_bloco.items():
        dobras[blocos == b] = d
    dobras[~valida] = -1
    registro = {"blocos_com_celula_valida": int(len(ids)), "blocos_usados": int(usados.sum()), "blocos_excluidos_por_poucas_celulas": [int(b) for b in ids[~usados]],
                "celulas_por_dobra": {int(d): int((dobras == d).sum()) for d in range(k)}}
    return dobras, registro


def mascara_de_treino(teste: np.ndarray, valida: np.ndarray, buffer_celulas: int) -> np.ndarray:
    """Células válidas a mais de ``buffer_celulas`` de qualquer célula de teste (evita autocorrelação na borda do bloco)."""
    perto = ndimage.binary_dilation(teste, iterations=buffer_celulas) if buffer_celulas else teste
    return valida & ~perto


def fracao_de_edificacoes_osm(pbf: Path, grade: dict, crs: str, municipio) -> np.ndarray:
    """Fração da célula coberta por edificações do OpenStreetMap (pintura a 3 m). Não é independente da Profill: serve de verificação cruzada, não de verdade."""
    import geopandas as gpd
    from pyrosm import OSM
    from rasterio import features
    from rasterio.transform import from_origin
    b = OSM(str(pbf)).get_buildings()
    b = b[b.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(crs)
    b = gpd.clip(b, municipio)
    sub = 10
    t = from_origin(grade["origem_x"], grade["origem_y"], grade["celula_m"] / sub, grade["celula_m"] / sub)
    r = features.rasterize([(g, 1) for g in b.geometry], out_shape=(grade["linhas"] * sub, grade["colunas"] * sub), transform=t, fill=0, dtype="uint8")
    return r.reshape(grade["linhas"], sub, grade["colunas"], sub).mean(axis=(1, 3)).astype("float32")


def bairro_de_cada_celula(territorio_json: Path, grade: dict, crs: str) -> tuple[np.ndarray, list[str]]:
    """Raster com o índice do bairro (pelo centro da célula); -1 fora de qualquer bairro."""
    import geopandas as gpd
    from rasterio import features
    from rasterio.transform import from_origin
    from shapely.geometry import shape
    bairros = json.loads(territorio_json.read_text())["bairros"]
    g = gpd.GeoDataFrame({"nome": [b["nome"] for b in bairros]}, geometry=[shape(b["geom"]) for b in bairros], crs=4326).to_crs(crs)
    g = g.dissolve(by="nome", as_index=False)
    t = from_origin(grade["origem_x"], grade["origem_y"], grade["celula_m"], grade["celula_m"])
    r = features.rasterize([(geom, i) for i, geom in enumerate(g.geometry)], out_shape=(grade["linhas"], grade["colunas"]), transform=t, fill=-1, dtype="int32")
    return r, list(g["nome"])
