"""Composição temporal e atributos por célula de 30 m.

A composição é a mediana, por pixel de 10 m, das cenas válidas (SCL, com folga em volta de nuvem e sombra). Os atributos são calculados em 10 m e
agregados à grade do projeto pela média dos pixels de cada célula: cada célula de 30 m recebe exatamente 3 x 3 pixels, sem reamostrar a grade de
elevação. O processamento é por faixas de linhas de células, para caber em 8 GB de RAM.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from . import imagens as im

log = logging.getLogger(__name__)
BANDAS = ["blue", "green", "red", "nir", "swir16", "swir22"]
INDICES = ["ndvi", "ndbi", "mndwi", "bsi"]
TEMPORAIS = ["ndvi_p10", "ndvi_p90", "mndwi_p90"]
INTRA = ["ndvi_dp", "brilho_dp"]   # desvio padrão entre os 9 pixels da célula: indicador de mistura, não de classe
CONJUNTOS = {"S1_bandas": BANDAS, "S2_indices": BANDAS + INDICES, "S3_temporais": BANDAS + INDICES + TEMPORAIS, "S4_intra_celula": BANDAS + INDICES + TEMPORAIS + INTRA}
NOMES = BANDAS + INDICES + TEMPORAIS + INTRA + ["n_cenas"]


def razao(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(a - b) / (a + b) com NaN onde a soma não é positiva."""
    s = a + b
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(s > 0, (a - b) / s, np.nan).astype("float32")


def indices(b: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {"ndvi": razao(b["nir"], b["red"]), "ndbi": razao(b["swir16"], b["nir"]), "mndwi": razao(b["green"], b["swir16"]),
            "bsi": razao(b["swir16"] + b["red"], b["nir"] + b["blue"])}


def celula_de_cada_pixel(origem: float, passo_px: float, n_px: int, origem_grade: float, celula: float, n_celulas: int, invertido: bool) -> np.ndarray:
    """Índice de célula de cada pixel (pelo centro do pixel) ao longo de um eixo; -1 fora da grade."""
    i = np.arange(n_px)
    centro = origem - (i + 0.5) * passo_px if invertido else origem + (i + 0.5) * passo_px
    c = np.floor(((origem_grade - centro) if invertido else (centro - origem_grade)) / celula).astype(int)
    c[(c < 0) | (c >= n_celulas)] = -1
    return c


def medias_por_celula(valores: np.ndarray, linha_celula: np.ndarray, coluna_celula: np.ndarray, n_linhas: int, n_colunas: int) -> tuple[np.ndarray, np.ndarray]:
    """Soma e contagem (ignorando NaN) dos pixels de cada célula. ``valores`` é (H, W); os índices de célula são por linha e por coluna de pixel."""
    ok = np.isfinite(valores)
    v = np.where(ok, valores, 0).astype("float64")
    li, co = linha_celula >= 0, coluna_celula >= 0
    v, ok = v[np.ix_(li, co)], ok[np.ix_(li, co)].astype("float64")
    lc, cc = linha_celula[li], coluna_celula[co]
    soma, cont = np.zeros((n_linhas, n_colunas)), np.zeros((n_linhas, n_colunas))
    # eixo das colunas
    ini_c = np.r_[0, np.flatnonzero(np.diff(cc)) + 1]
    sc, nc = np.add.reduceat(v, ini_c, axis=1), np.add.reduceat(ok, ini_c, axis=1)
    cols = cc[ini_c]
    ini_l = np.r_[0, np.flatnonzero(np.diff(lc)) + 1]
    sl, nl = np.add.reduceat(sc, ini_l, axis=0), np.add.reduceat(nc, ini_l, axis=0)
    soma[np.ix_(lc[ini_l], cols)], cont[np.ix_(lc[ini_l], cols)] = sl, nl
    return soma, cont


def compor_e_agregar(cache: Path, registros: list[dict], janela: im.Janela, transform_cena: list[float], grade: dict, deslocamento_crs: tuple[float, float], cfg_img: dict,
                     celulas_por_faixa: int = 40, minimo_de_cenas: int = 3) -> tuple[np.ndarray, dict]:
    """Devolve (atributos [linhas, colunas, n], resumo). Pixels com menos de ``minimo_de_cenas`` observações válidas ficam sem dado (NaN)."""
    n_l, n_c, cel = grade["linhas"], grade["colunas"], grade["celula_m"]
    ox = transform_cena[2] + janela.coluna * transform_cena[0]
    oy = transform_cena[5] - janela.linha * transform_cena[0]
    gx, gy = grade["origem_x"] + deslocamento_crs[0], grade["origem_y"] + deslocamento_crs[1]
    lin_cel = celula_de_cada_pixel(oy, transform_cena[0], janela.linhas, gy, cel, n_l, True)
    col_cel = celula_de_cada_pixel(ox, transform_cena[0], janela.colunas, gx, cel, n_c, False)
    dirs = [cache / r["id"] for r in registros]
    saida = np.full((n_l, n_c, len(NOMES)), np.nan, dtype="float32")
    pixels_com_dado = pixels_total = 0
    for r0 in range(0, n_l, celulas_por_faixa):
        r1 = min(r0 + celulas_por_faixa, n_l)
        px = np.flatnonzero((lin_cel >= r0) & (lin_cel < r1))
        if px.size == 0:
            continue
        a, b = int(px[0]), int(px[-1]) + 1
        pilha = {k: [] for k in BANDAS}
        for d, reg in zip(dirs, registros):
            scl = im.scl_10m(d, reg, (a, b))
            ok = im.pixels_validos(scl, cfg_img["scl_validas"], cfg_img["scl_nuvem_e_sombra"], cfg_img["dilatar_nuvem_px_20m"])
            for k in BANDAS:
                x = im.refletancia(d, reg, k, (a, b))
                x[~ok] = np.nan
                pilha[k].append(x)
        pilha = {k: np.stack(v) for k, v in pilha.items()}          # (T, H, W)
        n_obs = np.isfinite(pilha["red"]).sum(0)
        with np.errstate(all="ignore"):
            comp = {k: np.nanmedian(v, axis=0) for k, v in pilha.items()}
            ind = indices(comp)
            ndvi_t, mndwi_t = razao(pilha["nir"], pilha["red"]), razao(pilha["green"], pilha["swir16"])
            temp = {"ndvi_p10": np.nanpercentile(ndvi_t, 10, axis=0), "ndvi_p90": np.nanpercentile(ndvi_t, 90, axis=0), "mndwi_p90": np.nanpercentile(mndwi_t, 90, axis=0)}
        pouco = n_obs < minimo_de_cenas
        brilho = (comp["blue"] + comp["green"] + comp["red"]) / 3
        campos = {**comp, **ind, **temp}
        for campo in campos.values():
            campo[pouco] = np.nan
        pixels_com_dado += int((~pouco).sum())
        pixels_total += int(pouco.size)
        lc, cc = lin_cel[a:b], col_cel
        for k, nome in enumerate(BANDAS + INDICES + TEMPORAIS):
            s, n = medias_por_celula(campos[nome], lc, cc, n_l, n_c)
            sel = slice(r0, r1)
            with np.errstate(invalid="ignore", divide="ignore"):
                saida[sel, :, k] = np.where(n[sel] >= 5, s[sel] / n[sel], np.nan)         # ao menos 5 dos 9 pixels com dado
        for nome, v in (("ndvi_dp", ind["ndvi"]), ("brilho_dp", np.where(pouco, np.nan, brilho))):
            s1, n = medias_por_celula(v, lc, cc, n_l, n_c)
            s2, _ = medias_por_celula(np.square(v), lc, cc, n_l, n_c)
            with np.errstate(invalid="ignore", divide="ignore"):
                m = s1 / n
                dp = np.sqrt(np.maximum(s2 / n - m * m, 0))
            saida[r0:r1, :, NOMES.index(nome)] = np.where(n[r0:r1] >= 5, dp[r0:r1], np.nan)
        s, n = medias_por_celula(n_obs.astype("float32"), lc, cc, n_l, n_c)
        with np.errstate(invalid="ignore", divide="ignore"):
            saida[r0:r1, :, NOMES.index("n_cenas")] = np.where(n[r0:r1] > 0, s[r0:r1] / n[r0:r1], np.nan)
        log.info("faixa de células %d-%d de %d", r0, r1, n_l)
    return saida, {"pixels_de_10m_na_janela_com_dado_suficiente": pixels_com_dado, "pixels_de_10m_na_janela": pixels_total, "cenas": len(registros), "minimo_de_cenas_por_pixel": minimo_de_cenas,
                   "pixels_por_celula": "9 (3 x 3), mínimo de 5 com dado", "nomes_dos_atributos": NOMES}


def salvar(saida_dir: Path, atributos: np.ndarray, resumo: dict) -> Path:
    destino = saida_dir / "atributos_30m.npy"
    np.save(destino, atributos)
    (saida_dir / "atributos_30m.json").write_text(json.dumps(resumo, indent=1))
    return destino


NOMES_AEF = [f"A{i:02d}" for i in range(64)]


def agregar_embeddings(arquivo: Path, meta: dict, grade: dict, deslocamento_crs: tuple[float, float], celulas_por_faixa: int = 40) -> np.ndarray:
    """Média dos 3 x 3 embeddings de 10 m de cada célula (já sem a quantização int8). Devolve (linhas, colunas, 64); células com menos de 5 pixels com dado ficam NaN.

    A média de vetores unitários não tem norma 1; não é renormalizada porque o classificador não depende da escala.
    """
    n_l, n_c, cel = grade["linhas"], grade["colunas"], grade["celula_m"]
    gx, gy = grade["origem_x"] + deslocamento_crs[0], grade["origem_y"] + deslocamento_crs[1]
    lin_cel = celula_de_cada_pixel(meta["topo_y"], 10.0, meta["altura"], gy, cel, n_l, True)
    col_cel = celula_de_cada_pixel(meta["origem_x"], 10.0, meta["largura"], gx, cel, n_c, False)
    emb = np.load(arquivo, mmap_mode="r")
    saida = np.full((n_l, n_c, 64), np.nan, dtype="float32")
    for r0 in range(0, n_l, celulas_por_faixa):
        r1 = min(r0 + celulas_por_faixa, n_l)
        px = np.flatnonzero((lin_cel >= r0) & (lin_cel < r1))
        if px.size == 0:
            continue
        a, b = int(px[0]), int(px[-1]) + 1
        bloco = im.descontar_quantizacao(np.asarray(emb[a:b]))                     # (h, W, 64)
        for k in range(64):
            s, n = medias_por_celula(bloco[:, :, k], lin_cel[a:b], col_cel, n_l, n_c)
            with np.errstate(invalid="ignore", divide="ignore"):
                saida[r0:r1, :, k] = np.where(n[r0:r1] >= 5, s[r0:r1] / n[r0:r1], np.nan)
        log.info("embeddings: faixa de células %d-%d de %d", r0, r1, n_l)
    return saida
