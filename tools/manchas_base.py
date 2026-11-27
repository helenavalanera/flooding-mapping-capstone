"""Base comum dos mapas de manchas da landing (dimensões A, B, C e D): grade de 100 m, desenho e gravação em WebP.

Todos os mapas usam a MESMA grade, o mesmo enquadramento (EPSG:31982), as mesmas ruas e água do OpenStreetMap e, por cima das manchas, os limites dos 94 bairros,
para que alternar entre as dimensões mantenha cada lugar no mesmo ponto da imagem. Cada dimensão fornece só os valores por célula, as faixas da legenda e as cores.
A mancha é sempre o valor MÁXIMO (ou, na drenagem, a soma) do que cai na célula, sem suavização, para que a legenda continue verdadeira.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ESTATICO = RAIZ / "src/flooding_mapping/app/static"
IMG_DIR = ESTATICO / "inicio/img/estudo"
CELULA_M = 100
LARGURA_PX = 1400
FUNDO, AGUA, RUA, SEM_DADO, LIMITE, RUA_FORA = "#f4f6f7", "#cfe0ea", "#c3cbd0", "#8c99a1", "#7d8a93", "#e4e9ec"
FONTE_OSM = "Ruas e água: © colaboradores do OpenStreetMap · Limites de bairros: Prefeitura de Porto Alegre"


def carregar_rede() -> pd.DataFrame:
    return pd.read_parquet(RAIZ / "data/processed/rede_poa.parquet", columns=["segmento_id", "lon0", "lat0", "lon1", "lat1"])


def carregar_agua():
    try:
        import geopandas as gpd

        return gpd.read_parquet(RAIZ / "data/interim/water.parquet")
    except Exception as e:                                           # a água é só contexto: sem ela a imagem sai sem o fundo azul
        print("água indisponível:", type(e).__name__)
        return None


def carregar_bairros():
    """Limites dos bairros em EPSG:31982: lista de (nome, geometria)."""
    import json

    import geopandas as gpd
    from shapely.geometry import shape

    t = json.loads((RAIZ / "data/processed/territorio_poa.json").read_text(encoding="utf-8"))
    nomes = [b["nome"] for b in t["bairros"]]
    g = gpd.GeoSeries([shape(b["geom"]) for b in t["bairros"]], crs="EPSG:4326").to_crs("EPSG:31982")
    return list(zip(nomes, g))


def carregar_municipio():
    """Polígono do município de Porto Alegre em EPSG:31982 (o do pipeline: data/processed/municipality.parquet)."""
    import geopandas as gpd

    return gpd.read_parquet(RAIZ / "data/processed/municipality.parquet").to_crs("EPSG:31982").geometry.union_all()


class Quadro:
    """Projeção das ruas e grade comum a todos os mapas."""

    def __init__(self, rede: pd.DataFrame):
        from pyproj import Transformer

        tr = Transformer.from_crs("EPSG:4326", "EPSG:31982", always_xy=True)
        self.ids = rede["segmento_id"].to_numpy()
        self.x0, self.y0 = tr.transform(rede.lon0.to_numpy(), rede.lat0.to_numpy())
        self.x1, self.y1 = tr.transform(rede.lon1.to_numpy(), rede.lat1.to_numpy())
        self.xm, self.ym = (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2
        self.xmin, self.xmax = self.xm.min() - 400, self.xm.max() + 400
        self.ymin, self.ymax = self.ym.min() - 400, self.ym.max() + 400
        self.nx = int(np.ceil((self.xmax - self.xmin) / CELULA_M))
        self.ny = int(np.ceil((self.ymax - self.ymin) / CELULA_M))

    def no_municipio(self) -> np.ndarray:
        """Verdadeiro para o trecho cujo ponto médio cai DENTRO do município. A malha de ruas vem de uma caixa em volta de Porto Alegre e traz vias de cidades vizinhas."""
        import shapely

        if not hasattr(self, "_dentro"):
            self._dentro = shapely.contains(carregar_municipio(), shapely.points(self.xm, self.ym))
        return self._dentro

    def celula(self, x, y):
        return ((y - self.ymin) // CELULA_M).astype(int), ((x - self.xmin) // CELULA_M).astype(int)

    def valores_por_trecho(self, df: pd.DataFrame, coluna: str) -> np.ndarray:
        return pd.DataFrame({"segmento_id": self.ids}).merge(df[["segmento_id", coluna]], on="segmento_id", how="left")[coluna].to_numpy(dtype=float)

    def grade_maximo(self, h: np.ndarray) -> np.ndarray:
        """Máximo por célula entre os trechos com dado; célula sem trecho com dado fica vazia (NaN)."""
        tem = np.isfinite(h)
        iy, ix = self.celula(self.xm[tem], self.ym[tem])
        parcial, existe = np.zeros((self.ny, self.nx)), np.zeros((self.ny, self.nx), dtype=bool)
        np.maximum.at(parcial, (iy, ix), h[tem])
        existe[iy, ix] = True
        grade = np.full((self.ny, self.nx), np.nan)
        grade[existe] = parcial[existe]
        return grade


def desenhar(q: Quadro, grade: np.ndarray, bordas: list[float], cores: list[str], sem_dado: np.ndarray | None, agua, bairros, saida: Path, fonte_dado: str) -> tuple[int, int]:
    """Grava ``saida`` (WebP) com a grade colorida por faixas (``bordas`` com len(cores)+1 limites; só valores > 0 recebem cor)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from PIL import Image

    larg_in = LARGURA_PX / 200
    fig, ax = plt.subplots(figsize=(larg_in, larg_in * (q.ymax - q.ymin) / (q.xmax - q.xmin)), dpi=200)
    fig.patch.set_facecolor(FUNDO)
    ax.set_facecolor(FUNDO)
    if agua is not None:
        for g in agua.to_crs("EPSG:31982").geometry:
            for poly in getattr(g, "geoms", [g]):
                if poly.geom_type == "Polygon":
                    px, py = poly.exterior.xy
                    ax.fill(px, py, color=AGUA, lw=0, zorder=1)
    seg = lambda m: np.stack([np.c_[q.x0[m], q.y0[m]], np.c_[q.x1[m], q.y1[m]]], axis=1)
    dentro = q.no_municipio()                                          # vias de fora do município: só contexto, bem claras, sem análise
    ax.add_collection(LineCollection(seg(~dentro), colors=RUA_FORA, linewidths=0.2, zorder=2))
    ax.add_collection(LineCollection(seg(dentro), colors=RUA, linewidths=0.25, zorder=2))
    if sem_dado is not None and (sem_dado & dentro).any():
        ax.add_collection(LineCollection(seg(sem_dado & dentro), colors=SEM_DADO, linewidths=0.5, linestyles=(0, (2, 2)), zorder=3))
    acima = np.ma.masked_where(~(grade > 0), grade)
    ax.imshow(acima, extent=(q.xmin, q.xmax, q.ymin, q.ymax), origin="lower", cmap=ListedColormap(cores), norm=BoundaryNorm([*bordas[:-1], 1e12], len(cores)), interpolation="nearest", zorder=4, alpha=0.95)
    if bairros:
        linhas = []
        for _, g in bairros:
            for poly in getattr(g, "geoms", [g]):
                linhas.append(np.c_[poly.exterior.xy])
        ax.add_collection(LineCollection(linhas, colors=LIMITE, linewidths=0.3, zorder=5, alpha=0.8))
    ax.set_xlim(q.xmin, q.xmax)
    ax.set_ylim(q.ymin, q.ymax)
    ax.set_aspect("equal")
    ax.axis("off")
    dx, dy = q.xmax - q.xmin, q.ymax - q.ymin
    bx, by = q.xmin + 0.04 * dx, q.ymin + 0.05 * dy
    ax.plot([bx, bx + 5000], [by, by], color="#1b2630", lw=2.4, solid_capstyle="butt", zorder=6)
    ax.text(bx + 2500, by + 350, "5 km", ha="center", va="bottom", fontsize=7, color="#1b2630", zorder=6)
    nxp, nyp = q.xmax - 0.05 * dx, q.ymax - 0.06 * dy
    ax.annotate("", xy=(nxp, nyp), xytext=(nxp, nyp - 2600), arrowprops=dict(arrowstyle="-|>", color="#1b2630", lw=1.4), zorder=6)
    ax.text(nxp, nyp + 250, "N", ha="center", va="bottom", fontsize=8, color="#1b2630", fontweight="bold", zorder=6)
    ax.text(q.xmax - 0.01 * dx, q.ymin + 0.012 * dy, f"{fonte_dado} · {FONTE_OSM}", ha="right", va="bottom", fontsize=4.6, color="#4a5963", zorder=6)
    fig.subplots_adjust(0, 0, 1, 1)
    tmp = saida.with_suffix(".tmp.png")
    fig.savefig(tmp, dpi=200, facecolor=FUNDO)
    plt.close(fig)
    im = Image.open(tmp).convert("RGB")
    im.save(saida, "WEBP", quality=82, method=6)
    tmp.unlink()
    return im.size
