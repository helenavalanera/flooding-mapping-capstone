"""Prepara a camada E (GeoAI, fração construída estimada) para o mapa: uma imagem WebP com transparência, alinhada à projeção do mapa (Web Mercator), e o meta.json.

    PYTHONPATH=src .venv/bin/python tools/preparar_camada_geoai.py [saida]

Lê o raster COG do experimento (data/processed/geoai/fracao_construida_30m_*.tif, banda 1 = fração construída; não o altera) e o polígono do município, e escreve em
data/processed/geoai_web/ (fora do Git): ``fracao_construida.webp`` e ``meta.json``. A camada é EXPERIMENTAL e independente das dimensões A a D: não entra em nenhum cálculo.
A Profill foi a referência e a fonte dos rótulos; não há validação independente contra verdade de campo; a transferência para outras áreas não foi testada. A imagem mostra a
fração construída (Edificação + Vias Pavimentadas da Profill) em cinco classes, com as células de 30 m como o modelo as estimou, e deixa transparente o que fica fora do município.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
BORDAS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]                       # fração construída: classes de 0,2 (zero fica transparente)
CORES = ["#dfe5ea", "#aab6c1", "#76879a", "#46586b", "#1f2d3d"]   # cinza-ardósia, claro a escuro: distinto das cores de A a D e do azul da água
RESOLUCAO_DESTINO_M = 35.0                                     # em unidades do Web Mercator, cerca de 30 m no chão em Porto Alegre


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def classes(fracao: np.ndarray) -> np.ndarray:
    """Índice da classe (1 a 5) de cada fração; 0 = sem cor (zero ou sem dado). Bordas superiores fechadas."""
    f = np.round(fracao.astype("float64"), 6)                  # 0,2 em float32 é um pouco maior que 0,2: arredonda para a borda valer
    c = np.digitize(f, BORDAS[1:-1], right=True) + 1
    return np.where(np.isfinite(f) & (f > 0), c, 0).astype(np.uint8)


def colorir(cls: np.ndarray, dentro: np.ndarray) -> np.ndarray:
    """RGBA: cada classe na sua cor, transparente onde não há classe ou fora do município."""
    rgba = np.zeros(cls.shape + (4,), dtype=np.uint8)
    for k, cor in enumerate(CORES, start=1):
        m = (cls == k) & dentro
        rgba[m] = [int(cor[i:i + 2], 16) for i in (1, 3, 5)] + [235]
    return rgba


def resultados() -> dict:
    """Os números do experimento, lidos do relatório (nada é digitado à mão)."""
    r = json.loads((RAIZ / "reports/qa/geoai_resultados.json").read_text(encoding="utf-8"))
    prim = r["primario"]["modelo"]
    return {"modelo": prim, "mae_blocos_3km": round(r["P1_blocos"][prim]["bootstrap_por_blocos"]["mae"]["valor"], 3), "mae_quadrante_externo": round(r["P2_quadrantes"][prim]["bootstrap_por_blocos"]["mae"]["valor"], 3),
            "bairros_com_erro_de_area_ate_10pct": round(r["primario"]["erro_de_area_por_bairro"]["fracao_dentro_do_limite"], 3), "fonte": "reports/qa/geoai_resultados.json"}


def preparar(tif: Path, municipio: Path, saida: Path) -> dict:
    import geopandas as gpd
    import rasterio
    from PIL import Image
    from pyproj import Transformer
    from rasterio.features import rasterize
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    saida.mkdir(parents=True, exist_ok=True)
    with rasterio.open(tif) as s:
        origem = s.read(1).astype("float32")
        crs_origem, transf_origem, nodata, tags, bandas = s.crs, s.transform, s.nodata, s.tags(), list(s.descriptions)
        trans, larg, alt = calculate_default_transform(s.crs, "EPSG:3857", s.width, s.height, *s.bounds, resolution=RESOLUCAO_DESTINO_M)
    destino = np.full((alt, larg), np.nan, dtype="float32")
    reproject(origem, destino, src_transform=transf_origem, src_crs=crs_origem, dst_transform=trans, dst_crs="EPSG:3857", src_nodata=nodata, dst_nodata=np.nan, resampling=Resampling.nearest)
    poligono = gpd.read_parquet(municipio).to_crs("EPSG:3857").geometry.union_all()
    dentro = rasterize([(poligono, 1)], out_shape=(alt, larg), transform=trans, fill=0, dtype="uint8").astype(bool)
    cls = classes(destino)
    img = Image.fromarray(colorir(cls, dentro), "RGBA")
    arq = saida / "fracao_construida.webp"
    img.save(arq, "WEBP", lossless=True, quality=100, method=6)
    esq, topo, dire, base = trans.c, trans.f, trans.c + trans.a * larg, trans.f + trans.e * alt
    tr = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    pts = [tr.transform(x, y) for x, y in ((esq, topo), (dire, topo), (dire, base), (esq, base))]
    valores = origem[np.isfinite(origem)]
    dentro_origem_pct = [round(100 * float(((cls == k) & dentro).sum() / max(1, ((cls > 0) & dentro).sum())), 1) for k in range(1, 6)]
    meta = {"versao": 1, "natureza": "EXPERIMENTAL: estimativa de fração construída por célula de 30 m (Edificação + Vias Pavimentadas da Profill), independente das dimensões A a D",
            "experimento": tags.get("experimento"), "fonte_da_imagem": tags.get("fonte_da_imagem"), "periodo": tags.get("periodo"), "modelo": tags.get("modelo"), "referencia": tags.get("referencia"),
            "arquivo": "fracao_construida.webp", "sha256_da_imagem": sha256(arq), "bytes": arq.stat().st_size, "largura_px": larg, "altura_px": alt,
            "coordenadas": [[round(lon, 6), round(lat, 6)] for lon, lat in pts], "projecao_da_imagem": "EPSG:3857 (cantos em graus, no sentido horário a partir do noroeste)",
            "origem": {"arquivo": tif.name, "sha256": sha256(tif), "crs": str(crs_origem), "resolucao_m": 30.0, "bandas": bandas, "celulas_validas": int(valores.size), "media_da_fracao": round(float(valores.mean()), 4)},
            "classes": [{"de": BORDAS[k], "ate": BORDAS[k + 1], "cor": CORES[k]} for k in range(5)], "celulas_por_classe_no_municipio_pct": dentro_origem_pct,
            "recorte": "células fora do polígono do município ficam transparentes", "opacidade_inicial": 0.85,
            "resultados": resultados(),
            "limitacoes": ["A Profill foi a referência e a fonte dos rótulos.", "Não há validação independente contra verdade de campo.", "A transferência para outras áreas não foi testada.",
                           "Não representa impermeabilidade medida, coeficiente de escoamento, vazão nem ocorrência de alagamento.", "Não entra no cálculo das dimensões A, B, C e D."]}
    (saida / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def main() -> None:
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data/processed/geoai_web"
    tifs = sorted((RAIZ / "data/processed/geoai").glob("fracao_construida_30m_*.tif"))
    if not tifs:
        raise SystemExit("raster do experimento não encontrado em data/processed/geoai")
    m = preparar(tifs[-1], RAIZ / "data/processed/municipality.parquet", saida)
    print(json.dumps({k: m[k] for k in ("experimento", "bytes", "largura_px", "altura_px", "coordenadas", "celulas_por_classe_no_municipio_pct")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
