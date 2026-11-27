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
