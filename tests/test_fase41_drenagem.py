"""Fase 4.1: o inventário de drenagem na aplicação preserva o cadastro da Fase 2 e fica fora do cálculo.

Sintéticos rodam sempre; os de integridade conferem os arquivos distribuídos contra os Parquets da Fase 2 e são ignorados se não existirem."""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flooding_mapping import camada_drenagem as d
from flooding_mapping import camada_fase3 as base

RAIZ = Path(__file__).parent.parent
PROC = RAIZ / "data/processed/drenagem"
WEB = RAIZ / "data/processed/drenagem_web"
STATIC = RAIZ / "src/flooding_mapping/app/static"
real = pytest.mark.skipif(not ((WEB / "meta.json").exists() and (PROC / "rede_pluvial.parquet").exists()), reason="camada de drenagem não gerada (tools/preparar_camada_drenagem.py)")


def test_the_origin_layer_is_the_only_source_of_the_category_and_unknown_ones_are_refused():
    t = pd.DataFrame({"camada_origem": ["rede_pluvial", "rede_pluvial_sem_acesso", "rede_pluvial_nao_interligada"], "usar_no_inventario": [True, True, False],
                      "diametro_fora_da_faixa_plausivel": [False, True, None], "data_implantacao_suspeita": [False, False, True]})
    c = d.classes(t, "rede")
    assert list(c["cat"]) == [0, 1, 2] and list(c["u"]) == [0, 0, 1] and list(c["s"]) == [0, 1, 1]
    with pytest.raises(ValueError, match="desconhecida"):
        d.classes(t.assign(camada_origem=["rede_pluvial", "outra", "rede_pluvial"]), "rede")


def test_values_keep_their_type_and_absence_is_null_never_zero():
    assert d._valor(np.nan) is None and d._valor(None) is None and d._valor(pd.NA) is None and d._valor(pd.NaT) is None
    assert d._valor(0) == 0 and d._valor(0.0) == 0.0 and d._valor(np.int64(7)) == 7 and d._valor(np.bool_(False)) is False
    assert d._valor(1234.5678901234) == pytest.approx(1234.56789, rel=1e-9) and d._valor("ViaPublica") == "ViaPublica"
    assert d._valor(pd.Timestamp("2020-01-02")).startswith("2020-01-02")


@pytest.fixture(scope="module")
def dados():
    meta = json.loads((WEB / "meta.json").read_text())
    return meta


@real
def test_counts_hashes_and_categories_match_the_phase_2_files(dados):
    meta = dados
    assert meta["entradas_sha256"] == {p.name: base.sha256(p) for p in sorted(PROC.glob("*")) if p.is_file()}
    esperado = {"rede": 135856, "pocos": 88899, "bocas": 44868, "bombas": 24}
    assert {k: v["registros"] for k, v in meta["camadas"].items()} == esperado
    assert meta["camadas"]["rede"]["por_categoria"] == {"rede_pluvial": 133060, "rede_pluvial_sem_acesso": 2775, "rede_pluvial_nao_interligada": 21}
    assert meta["camadas"]["rede"]["duplicados_fora_do_inventario"] == 77            # 135.856 - 135.779 usados


@real
@pytest.mark.parametrize("camada", ["rede", "pocos", "bocas", "bombas"])
def test_every_original_attribute_is_preserved_in_the_detail_in_the_index_order(dados, camada):
    original = d.carregar(PROC, camada)
    frags = [json.loads(p.read_text()) for p in sorted((WEB / "detalhe" / camada).glob("*.json"))]
    colunas = frags[0]["colunas"]
    assert colunas == [c for c in original.columns if c != "geometry"]          # nenhum atributo some nem muda de nome
    linhas = pd.DataFrame([l for f in frags for l in f["linhas"]], columns=colunas)
    assert len(linhas) == len(original) and all(f["primeiro_n"] == i * 1024 for i, f in enumerate(frags))
    for c in colunas:
        o, m = original[c], linhas[c]
        assert (o.isna().to_numpy() == m.isna().to_numpy()).all(), c           # nulo continua nulo
        if pd.api.types.is_float_dtype(o):
            ok = o.notna().to_numpy()
            assert np.all(np.abs(m[ok].astype(float).to_numpy() - o[ok].to_numpy()) <= 1e-8 * np.abs(o[ok].to_numpy())), c
        elif pd.api.types.is_bool_dtype(o):
            assert (o.to_numpy() == m.astype(bool).to_numpy()).all(), c
        elif pd.api.types.is_integer_dtype(o):
            assert (o.to_numpy() == m.to_numpy()).all(), c


@real
def test_tiles_have_the_features_and_classes_of_the_data_and_no_attributes(dados):
    ler = base.ler_tile
    for camada, (_, zmin, zmax) in d.CAMADAS.items():
        original = d.carregar(PROC, camada)
        cl = d.classes(original, camada)
        vistos = {}
        for f in (WEB / "tiles" / camada / str(zmax)).rglob("*.pbf"):
            for p in ler(f.read_bytes()):
                vistos[p["n"]] = p
        faltam = set(range(len(original))) - set(vistos)
        curtos = set(np.flatnonzero(original.geometry.length.to_numpy() < 1.0).tolist())
        assert faltam <= curtos and len(faltam) <= 100, (camada, len(faltam))
        for n in list(vistos)[::53]:
            assert vistos[n] == {"n": n, **{k: int(cl[k].iloc[n]) for k in cl.columns}}, (camada, n)      # só n e classes: nenhum atributo do cadastro nos tiles


@real
def test_the_distribution_sizes_are_proportionate():
    assert max(p.stat().st_size for p in (WEB / "detalhe").rglob("*.json")) < 400_000                      # um clique baixa < 400 KB
    assert max(p.stat().st_size for p in (WEB / "tiles").rglob("*.pbf")) < 400_000
    assert sum(1 for _ in WEB.rglob("*") if _.is_file()) < 20_000                                           # cabe nos limites de arquivos de hospedagem estática gratuita


def test_the_screen_never_claims_capacity_function_connectivity_or_efficiency_outside_the_disclaimers():
    js = (STATIC / "drenagem.js").read_text(encoding="utf-8")
    sem_avisos = re.sub(r"/\*.*?\*/", "", re.sub(r'aviso: ".*?",\n', "", js, flags=re.S), flags=re.S)   # fora o aviso e o comentário de cabeçalho, que negam essas afirmações
    for termo in ("capacidade de vazão", "funcionando", "em funcionamento", "eficiência", "conectividade", "entupid", "obstruíd", "alagada", "rua alagada"):
        assert termo not in sem_avisos.lower(), termo
    assert "não indica capacidade de vazão" in js.lower() and "não entra no cálculo de escoamento potencial" in js
    fase3 = (STATIC / "fase3.js").read_text(encoding="utf-8") + (STATIC / "fase3-dados.js").read_text(encoding="utf-8")
    assert "drenagem/" not in fase3 and "Drenagem." not in fase3 and "drenagem_web" not in fase3        # a camada da Fase 3 não lê a drenagem
    motor = (RAIZ / "src/flooding_mapping/motor_acumulo.py").read_text(encoding="utf-8")
    assert "camada_drenagem" not in motor and "drenagem_web" not in motor and "rede_pluvial" not in motor           # nada da drenagem entra no motor
