"""Mapa de manchas da propensão topográfica à retenção (dimensão C), pré-renderizado em WebP para a landing.

    PYTHONPATH=src .venv/bin/python tools/gerar_mapa_manchas.py

Só reaproveita resultados que já existem (altura que o preenchimento de depressões soma ao relevo, por trecho de rua); nada reexecuta o motor.
Fontes do desenho: relevo Copernicus DEM GLO-30 (via o indicador por trecho), ruas e água do OpenStreetMap. NÃO usa a Profill (nem A nem B), os limites de bairros
da Prefeitura nem as coordenadas de alagamentos: por isso a imagem pode ser publicada com atribuição. Cada mancha é o MÁXIMO da altura entre os trechos que caem
em uma célula de 100 m; escuro = depressão mais profunda estimada, o que não é ocorrência nem risco de alagamento.
Escreve: static/inicio/img/estudo/mapa-propensao.webp e static/data/mapa_manchas_poa.json (números e faixas da legenda, usados pela landing e conferidos por teste).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ESTATICO = RAIZ / "src/flooding_mapping/app/static"
IMG = ESTATICO / "inicio/img/estudo/mapa-propensao.webp"
DADOS = ESTATICO / "data/mapa_manchas_poa.json"
CELULA_M = 100
FAIXAS_M = [0.0, 0.5, 1.0, 2.0, np.inf]                       # limites da legenda, em metros
CORES = ["#f1d9a8", "#dfa356", "#b3622a", "#6a2a12"]          # claro a escuro (tons de terra, como o indicador topográfico do mapa interativo)
LARGURA_PX = 1400
FUNDO, AGUA, RUA, SEM_DADO = "#f4f6f7", "#cfe0ea", "#c3cbd0", "#8c99a1"


def estatisticas(t: pd.DataFrame) -> dict:
    a = t["altura_de_preenchimento_max_m"]
    com_dado, pos = a.dropna(), a[a > 0]
    return {"trechos_total": int(len(t)), "trechos_com_dado_de_relevo": int(len(com_dado)), "trechos_sem_dado_de_relevo": int(a.isna().sum()),
            "cobertura_de_dado_pct": round(100 * len(com_dado) / len(t), 1), "trechos_com_depressao": int(len(pos)), "trechos_com_depressao_pct": round(100 * len(pos) / len(t), 1),
            "altura_mediana_m": round(float(pos.median()), 2), "altura_p90_m": round(float(pos.quantile(0.9)), 2), "altura_p99_m": round(float(pos.quantile(0.99)), 2),
            "altura_maxima_m": round(float(pos.max()), 2), "trechos_acima_de_8_m": int((pos > 8).sum())}


def desenhar(t: pd.DataFrame, rede: pd.DataFrame, agua) -> tuple[int, int]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from pyproj import Transformer

    tr = Transformer.from_crs("EPSG:4326", "EPSG:31982", always_xy=True)
    x0, y0 = tr.transform(rede.lon0.to_numpy(), rede.lat0.to_numpy())
    x1, y1 = tr.transform(rede.lon1.to_numpy(), rede.lat1.to_numpy())
    h = rede[["segmento_id"]].merge(t[["segmento_id", "altura_de_preenchimento_max_m"]], on="segmento_id", how="left")["altura_de_preenchimento_max_m"].to_numpy()
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    xmin, xmax, ymin, ymax = xm.min() - 400, xm.max() + 400, ym.min() - 400, ym.max() + 400
    nx, ny = int(np.ceil((xmax - xmin) / CELULA_M)), int(np.ceil((ymax - ymin) / CELULA_M))
    grade = np.full((ny, nx), np.nan)
    tem = np.isfinite(h)
    ix, iy = ((xm[tem] - xmin) // CELULA_M).astype(int), ((ym[tem] - ymin) // CELULA_M).astype(int)
    parcial = np.zeros((ny, nx))
    np.maximum.at(parcial, (iy, ix), h[tem])
    existe = np.zeros((ny, nx), dtype=bool)
    existe[iy, ix] = True
    grade[existe] = parcial[existe]                                  # máximo por célula; célula sem trecho com dado fica vazia
    acima = np.ma.masked_where(~(grade > 0), grade)                  # só as células com depressão ganham cor

    larg_in = LARGURA_PX / 200
    alt_in = larg_in * (ymax - ymin) / (xmax - xmin)
    fig, ax = plt.subplots(figsize=(larg_in, alt_in), dpi=200)
    fig.patch.set_facecolor(FUNDO)
    ax.set_facecolor(FUNDO)
    if agua is not None:
        for g in agua.to_crs("EPSG:31982").geometry:
            for poly in getattr(g, "geoms", [g]):
                if poly.geom_type == "Polygon":
                    px, py = poly.exterior.xy
                    ax.fill(px, py, color=AGUA, lw=0, zorder=1)
    ax.add_collection(LineCollection(np.stack([np.c_[x0, y0], np.c_[x1, y1]], axis=1), colors=RUA, linewidths=0.25, zorder=2))
    sd = ~tem
    ax.add_collection(LineCollection(np.stack([np.c_[x0[sd], y0[sd]], np.c_[x1[sd], y1[sd]]], axis=1), colors=SEM_DADO, linewidths=0.5, linestyles=(0, (2, 2)), zorder=3))
    cmap, norm = ListedColormap(CORES), BoundaryNorm([0.0, 0.5, 1.0, 2.0, 1e9], 4)
    ax.imshow(acima, extent=(xmin, xmax, ymin, ymax), origin="lower", cmap=cmap, norm=norm, interpolation="nearest", zorder=4, alpha=0.95)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.axis("off")
    # escala gráfica de 5 km (a projeção é métrica) e seta do norte
    bx, by = xmin + 0.04 * (xmax - xmin), ymin + 0.05 * (ymax - ymin)
    ax.plot([bx, bx + 5000], [by, by], color="#1b2630", lw=2.4, solid_capstyle="butt", zorder=6)
    ax.text(bx + 2500, by + 350, "5 km", ha="center", va="bottom", fontsize=7, color="#1b2630", zorder=6)
    nxp, nyp = xmax - 0.05 * (xmax - xmin), ymax - 0.06 * (ymax - ymin)
    ax.annotate("", xy=(nxp, nyp), xytext=(nxp, nyp - 2600), arrowprops=dict(arrowstyle="-|>", color="#1b2630", lw=1.4), zorder=6)
    ax.text(nxp, nyp + 250, "N", ha="center", va="bottom", fontsize=8, color="#1b2630", fontweight="bold", zorder=6)
    ax.text(xmax - 0.01 * (xmax - xmin), ymin + 0.012 * (ymax - ymin), "Relevo: Copernicus DEM GLO-30 · Ruas e água: © colaboradores do OpenStreetMap", ha="right", va="bottom", fontsize=5.2, color="#4a5963", zorder=6)
    fig.subplots_adjust(0, 0, 1, 1)
    tmp = IMG.with_suffix(".tmp.png")
    fig.savefig(tmp, dpi=200, facecolor=FUNDO)
    plt.close(fig)
    from PIL import Image

    im = Image.open(tmp).convert("RGB")
    im.save(IMG, "WEBP", quality=82, method=6)
    tmp.unlink()
    return im.size


def main() -> None:
    t = pd.read_parquet(RAIZ / "data/processed/fase3/trechos_nivel1_propensao_topografica.parquet")
    rede = pd.read_parquet(RAIZ / "data/processed/rede_poa.parquet", columns=["segmento_id", "lon0", "lat0", "lon1", "lat1"])
    agua = None
    try:
        import geopandas as gpd

        agua = gpd.read_parquet(RAIZ / "data/interim/water.parquet")
    except Exception as e:                                           # a água é só contexto: sem ela a imagem sai sem o fundo azul
        print("água indisponível:", type(e).__name__)
    w, h = desenhar(t, rede, agua)
    r = {"variavel": "altura que o preenchimento de depressões soma ao relevo (propensão topográfica à retenção, dimensão C), por trecho",
         "fontes": "Copernicus DEM GLO-30 (relevo) e OpenStreetMap (ruas e água). Não usa a Profill, os limites de bairros da Prefeitura nem registros de alagamento",
         "imagem": {"arquivo": "img/estudo/mapa-propensao.webp", "largura_px": w, "altura_px": h, "bytes": IMG.stat().st_size, "celula_m": CELULA_M, "agregacao": "máximo entre os trechos de cada célula"},
         "faixas_m": [{"de": 0.0, "ate": 0.5, "cor": CORES[0]}, {"de": 0.5, "ate": 1.0, "cor": CORES[1]}, {"de": 1.0, "ate": 2.0, "cor": CORES[2]}, {"de": 2.0, "ate": None, "cor": CORES[3]}],
         **estatisticas(t)}
    DADOS.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"gravado: {IMG.name} {w}x{h}, {IMG.stat().st_size / 1024:.0f} KB; {DADOS.name}")


if __name__ == "__main__":
    main()
