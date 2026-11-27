"""Mapa de manchas da propensão topográfica à retenção: números, imagem e fontes. Só dimensão C, sem Profill, bairros nem alagamentos registrados."""
import json
import re
import sys
from pathlib import Path

import pytest
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ST = RAIZ / "src/flooding_mapping/app/static"
J = json.loads((ST / "data/mapa_manchas_poa.json").read_text(encoding="utf-8"))
IMG = ST / "inicio/img/estudo/mapa-propensao.webp"
PARQUET = RAIZ / "data/processed/fase3/trechos_nivel1_propensao_topografica.parquet"


def test_the_numbers_are_internally_consistent_and_use_only_streets_inside_the_municipality():
    assert J["trechos_na_malha"] == 176836 and J["trechos_total"] + J["trechos_fora_do_municipio"] == J["trechos_na_malha"] and J["trechos_total"] == 143149
    assert J["trechos_com_dado_de_relevo"] + J["trechos_sem_dado_de_relevo"] == J["trechos_total"] and J["trechos_sem_dado_de_relevo"] == 68
    assert J["cobertura_de_dado_pct"] == 99.95 and J["trechos_com_depressao"] == 31545 and J["trechos_com_depressao_pct"] == 22.0
    assert J["altura_mediana_m"] == 0.63 and J["altura_p99_m"] == 4.12
    assert "não é a profundidade da água" in J["variavel"]


def test_the_extreme_maximum_is_recorded_as_an_outlier_and_not_highlighted():
    assert J["altura_maxima_m"] > 8 and J["trechos_acima_de_8_m"] <= 10 and J["altura_p99_m"] < J["altura_maxima_m"] / 2
    html = (ST / "inicio/index.html").read_text(encoding="utf-8")
    assert str(J["altura_maxima_m"]).replace(".", ",") not in html            # o máximo é valor extremo, provável artefato do modelo de superfície


@pytest.mark.skipif(not PARQUET.exists(), reason="falta data/processed/fase3 (fora do Git)")
def test_the_numbers_are_recomputed_from_the_existing_results():
    sys.path.insert(0, str(RAIZ / "tools"))
    import pandas as pd

    from gerar_mapa_manchas import do_municipio, estatisticas
    from manchas_base import Quadro, carregar_rede
    e = estatisticas(do_municipio(Quadro(carregar_rede()), pd.read_parquet(PARQUET)))
    assert {k: J[k] for k in e} == e


def test_the_image_is_a_light_webp_with_the_recorded_size_and_a_legend_in_metres():
    im = Image.open(IMG)
    assert im.format == "WEBP" and im.size == (J["imagem"]["largura_px"], J["imagem"]["altura_px"]) and IMG.stat().st_size == J["imagem"]["bytes"]
    assert IMG.stat().st_size < 400_000                                                              # leve: o mapa aparece sem WebGL nem bibliotecas
    assert [(f["de"], f["ate"]) for f in J["faixas_m"]] == [(0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, None)]
    cores = [f["cor"] for f in J["faixas_m"]]
    lum = [sum(int(c[i:i + 2], 16) * w for i, w in ((1, .299), (3, .587), (5, .114))) for c in cores]
    assert lum == sorted(lum, reverse=True)                                                          # mais escuro = faixa mais profunda


def test_the_topographic_generator_keeps_to_dimension_c_and_does_not_use_the_profill_or_flood_records():
    fonte = (RAIZ / "tools/gerar_mapa_manchas.py").read_text(encoding="utf-8")
    codigo = re.sub(r'""".*?"""', "", fonte, count=1, flags=re.S)
    codigo = "\n".join(l for l in codigo.splitlines() if '"fontes":' not in l)                          # a frase que declara o que NÃO é usado
    for proibido in ("uso_solo", "profill", "alagamentos", "events.csv", "contrib_aeq", "acum_aeq", "nivel2"):
        assert proibido not in codigo.lower(), proibido
    assert "Copernicus" in J["fontes"] and "OpenStreetMap" in J["fontes"] and "não usa a Profill" in J["fontes"]
