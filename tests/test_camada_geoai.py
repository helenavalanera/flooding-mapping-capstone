"""Camada E (GeoAI, fração construída estimada): classes, cores, recorte, integridade do arquivo publicado e rótulo de experimental. Independente das dimensões A a D."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import preparar_camada_geoai as g  # noqa: E402

WEB = RAIZ / "data/processed/geoai_web"
real = pytest.mark.skipif(not (WEB / "meta.json").exists(), reason="falta data/processed/geoai_web (fora do Git)")


def test_classes_have_closed_upper_edges_and_zero_or_missing_get_no_colour():
    f = np.array([0.0, 0.0001, 0.2, 0.2001, 0.4, 0.6, 0.8, 0.9996, np.nan], dtype="float32")
    assert list(g.classes(f)) == [0, 1, 1, 2, 2, 3, 4, 5, 0]


def test_colours_follow_the_classes_and_the_outside_of_the_municipality_is_transparent():
    cls = np.array([[1, 5], [3, 0]], dtype=np.uint8)
    dentro = np.array([[True, True], [False, True]])
    rgba = g.colorir(cls, dentro)
    assert tuple(rgba[0, 0][:3]) == (0xdf, 0xe5, 0xea) and tuple(rgba[0, 1][:3]) == (0x1f, 0x2d, 0x3d) and rgba[0, 0][3] > 0
    assert rgba[1, 0][3] == 0 and rgba[1, 1][3] == 0                               # fora do município, ou sem classe: transparente


def test_the_palette_is_dark_for_high_fractions_and_distinct_from_the_other_layers():
    lum = [sum(int(c[i:i + 2], 16) * w for i, w in ((1, .299), (3, .587), (5, .114))) for c in g.CORES]
    assert lum == sorted(lum, reverse=True) and len(g.CORES) == len(g.BORDAS) - 1
    outras = {"#f7d6e6", "#5e0f45", "#dcd9f2", "#2d2166", "#f1d9a8", "#6a2a12", "#d4ecd9", "#0e5236"}
    assert not outras & set(g.CORES)


@real
def test_the_published_file_matches_its_meta_and_the_experiment_manifest():
    m = json.loads((WEB / "meta.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((WEB / m["arquivo"]).read_bytes()).hexdigest() == m["sha256_da_imagem"] and (WEB / m["arquivo"]).stat().st_size == m["bytes"] < 400_000
    man = json.loads((RAIZ / f"data/processed/geoai/manifesto_{m['experimento']}.json").read_text(encoding="utf-8"))
    assert m["origem"]["sha256"] == man["produto"]["sha256"] and m["origem"]["crs"] == man["sistema_de_referencia"] == "EPSG:31982" and m["origem"]["resolucao_m"] == man["resolucao_m"] == 30.0
    assert m["natureza"].startswith("EXPERIMENTAL") and any("validação independente" in x for x in m["limitacoes"]) and any("Profill foi a referência" in x for x in m["limitacoes"])


@real
def test_the_image_covers_porto_alegre_and_its_numbers_come_from_the_experiment_report():
    m = json.loads((WEB / "meta.json").read_text(encoding="utf-8"))
    lons, lats = [c[0] for c in m["coordenadas"]], [c[1] for c in m["coordenadas"]]
    assert -51.35 < min(lons) < -51.25 and -51.02 < max(lons) < -50.95 and -30.35 < min(lats) < -30.25 and -29.95 < max(lats) < -29.9      # a caixa do município
    assert abs(sum(m["celulas_por_classe_no_municipio_pct"]) - 100) < 0.5 and len(m["classes"]) == 5
    r = json.loads((RAIZ / "reports/qa/geoai_resultados.json").read_text(encoding="utf-8"))
    prim = r["primario"]["modelo"]
    assert m["resultados"]["mae_blocos_3km"] == round(r["P1_blocos"][prim]["bootstrap_por_blocos"]["mae"]["valor"], 3) == 0.049
    assert m["resultados"]["mae_quadrante_externo"] == 0.052 and m["resultados"]["bairros_com_erro_de_area_ate_10pct"] == 0.574
    from PIL import Image
    assert Image.open(WEB / m["arquivo"]).size == (m["largura_px"], m["altura_px"])


def test_the_layer_never_enters_the_engine():
    codigo = (RAIZ / "tools/preparar_camada_geoai.py").read_text(encoding="utf-8").split('"""')[2]
    for proibido in ("fase3", "contrib", "resultados_poa", "trechos_"):
        assert proibido not in codigo, proibido


# --------------------------------------------------------------------------------------------------------------- compatibilidade espacial com o mapa
TIF = next(iter(sorted((RAIZ / "data/processed/geoai").glob("fracao_construida_30m_*.tif"))), None)
real_tif = pytest.mark.skipif(TIF is None or not (WEB / "meta.json").exists(), reason="faltam data/processed/geoai e geoai_web (fora do Git)")


@real_tif
def test_the_image_covers_the_source_raster_and_sits_inside_the_basemap_bounds():
    import rasterio
    from pyproj import Transformer
    m = json.loads((WEB / "meta.json").read_text(encoding="utf-8"))
    with rasterio.open(TIF) as s:
        tr = Transformer.from_crs(s.crs, "EPSG:4326", always_xy=True)
        cantos = [tr.transform(x, y) for x, y in ((s.bounds.left, s.bounds.bottom), (s.bounds.right, s.bounds.bottom), (s.bounds.right, s.bounds.top), (s.bounds.left, s.bounds.top))]
    lons, lats = [c[0] for c in m["coordenadas"]], [c[1] for c in m["coordenadas"]]
    assert all(min(lons) - 1e-6 <= x <= max(lons) + 1e-6 and min(lats) - 1e-6 <= y <= max(lats) + 1e-6 for x, y in cantos)      # a imagem contém o raster inteiro
    assert max(lons) - max(c[0] for c in cantos) < 0.01 and min(c[0] for c in cantos) - min(lons) < 0.01 and max(lats) - max(c[1] for c in cantos) < 0.01      # e não passa muito dele
    sys.path.insert(0, str(RAIZ / "tools"))
    import preparar_para_r2 as r2
    w, s_, e, n = map(float, r2.BBOX_POA.split(","))                                                                              # caixa do mapa-base (poa.pmtiles)
    assert w <= min(lons) and max(lons) <= e and s_ <= min(lats) and max(lats) <= n, (w, s_, e, n)


@real_tif
def test_every_visible_pixel_of_the_web_image_has_the_class_of_the_source_cell_under_it():
    import rasterio
    from PIL import Image
    from pyproj import Transformer
    m = json.loads((WEB / "meta.json").read_text(encoding="utf-8"))
    img = np.array(Image.open(WEB / m["arquivo"]).convert("RGBA"))
    esq, topo, dire, base = [(m["coordenadas"][0][0], m["coordenadas"][0][1]), (m["coordenadas"][1][0], m["coordenadas"][1][1]), (m["coordenadas"][2][0], m["coordenadas"][2][1]), (m["coordenadas"][3][0], m["coordenadas"][3][1])][0] + (m["coordenadas"][2][0], m["coordenadas"][2][1])
    to3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x0, y0 = to3857.transform(m["coordenadas"][0][0], m["coordenadas"][0][1])
    x1, y1 = to3857.transform(m["coordenadas"][2][0], m["coordenadas"][2][1])
    h, w = img.shape[:2]
    rng = np.random.default_rng(7)
    ys, xs = np.nonzero(img[..., 3] > 0)
    escolha = rng.choice(len(ys), 3000, replace=False)
    to_src = Transformer.from_crs("EPSG:3857", "EPSG:31982", always_xy=True)
    cores = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (k["cor"] for k in m["classes"])]
    with rasterio.open(TIF) as s:
        dados = s.read(1)
        erradas = 0
        for k in escolha:
            y, x = ys[k], xs[k]
            X, Y = x0 + (x + 0.5) * (x1 - x0) / w, y0 - (y + 0.5) * (y0 - y1) / h
            sx, sy = to_src.transform(X, Y)
            lin, col = s.index(sx, sy)
            v = float(dados[lin, col])
            cls = int(np.digitize(round(v, 6), [0.2, 0.4, 0.6, 0.8], right=True))
            if v <= 0 or tuple(img[y, x, :3]) != cores[cls]:
                erradas += 1
    assert erradas / len(escolha) < 0.02, f"{erradas} de {len(escolha)} pixels fora da classe da célula de origem"                  # só as bordas da reamostragem podem discordar


@real_tif
def test_the_source_raster_is_aligned_with_independent_openstreetmap_data():
    import geopandas as gpd
    import rasterio
    from rasterio.features import rasterize
    with rasterio.open(TIF) as s:
        fr = s.read(1)
        agua = gpd.read_parquet(RAIZ / "data/interim/water.parquet").to_crs(s.crs)
        mascara = rasterize([(g, 1) for g in agua.geometry if g is not None and not g.is_empty], out_shape=fr.shape, transform=s.transform, fill=0, dtype="uint8").astype(bool)
    assert mascara.sum() > 100000 and fr[mascara].mean() < 0.05 < 0.15 < fr[~mascara].mean()                                      # quase nada construído sobre a água do OSM
    ed_arq = RAIZ / "data/processed/geoai/osm_edificacoes_30m.npy"
    if ed_arq.exists():
        ed = np.load(ed_arq)
        if ed.shape == fr.shape:
            ok = np.isfinite(ed) & np.isfinite(fr)
            corr = lambda a: float(np.corrcoef(fr[ok], a[ok])[0, 1])                                                                # noqa: E731
            assert corr(ed) > 0.5 and all(corr(np.roll(ed, d, (0, 1))) < corr(ed) for d in ((1, 0), (-1, 0), (0, 1), (0, -1)))    # a correlação com as edificações do OSM é máxima sem deslocamento
