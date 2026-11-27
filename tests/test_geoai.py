"""Fase 5 (GeoAI): testes das peças do pipeline com dados SINTÉTICOS pequenos.

Eles provam que o código faz o que diz (agregação 3 x 3, máscaras, rótulos, dobras sem vazamento, métricas com resposta exata). NÃO são evidência de
desempenho do modelo: os números do experimento vêm de ``tools/executar_geoai.py`` sobre as imagens e a Profill reais (docs/geoai_fase5.md).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flooding_mapping import config as cfgmod
from flooding_mapping.geoai import atributos as at
from flooding_mapping.geoai import avaliacao as av
from flooding_mapping.geoai import imagens as im
from flooding_mapping.geoai import modelos as md
from flooding_mapping.geoai import referencia as rf

RAIZ = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------------------------------------ imagens
def test_each_30m_cell_gets_exactly_nine_ten_meter_pixels_even_with_a_sub_pixel_offset():
    # tile com origem em x=1000, y=2000; a grade do projeto começa 0,92 m ao lado, como a real
    col = at.celula_de_cada_pixel(1000.0, 10.0, 12, 1000.92, 30.0, 4, invertido=False)
    lin = at.celula_de_cada_pixel(2000.0, 10.0, 12, 2000.92, 30.0, 4, invertido=True)
    assert col.tolist() == lin.tolist() == [0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3]
    valores = np.arange(144, dtype="float64").reshape(12, 12)
    soma, cont = at.medias_por_celula(valores, lin, col, 4, 4)
    assert (cont == 9).all() and soma[1, 2] / cont[1, 2] == pytest.approx(valores[3:6, 6:9].mean())


def test_cell_means_ignore_nan_and_skip_pixels_outside_the_grid():
    lin = np.array([-1, 0, 0, 0, 1, 1, 1])
    col = np.array([0, 0, 0, 1, 1, 1])
    v = np.ones((7, 6))
    v[1, 0] = np.nan
    v[0, :] = 999          # linha fora da grade
    soma, cont = at.medias_por_celula(v, lin, col, 2, 2)
    assert cont[0, 0] == 8 and soma[0, 0] == 8 and cont[1, 1] == 9 and soma.max() == 9


def test_spectral_ratio_is_nan_when_the_sum_is_not_positive():
    r = at.razao(np.array([1.0, 0.0, -1.0]), np.array([1.0, 0.0, 1.0]))
    assert r[0] == 0 and np.isnan(r[1]) and np.isnan(r[2])


def test_valid_pixels_exclude_clouds_shadows_and_a_margin_around_them():
    scl = np.full((9, 9), 4)
    scl[4, 4] = 9
    ok = im.pixels_validos(scl, [4, 5, 6], [2, 3, 8, 9, 10], dilatar=2)
    assert not ok[4, 4] and not ok[2, 4] and not ok[4, 6] and ok[0, 0] and ok[8, 8]
    assert not im.pixels_validos(np.array([[7, 0, 1, 11]]), [4, 5, 6], [3, 8, 9, 10], 0).any()


def test_scene_choice_respects_quality_the_total_and_a_per_year_cap():
    cenas = [{"id": f"{a}-{i}", "datetime": f"{a}-0{i + 1}-01T00:00:00Z", "valido_no_municipio": 0.99 - 0.01 * i - (0.001 if a == 2020 else 0)} for a in (2019, 2020, 2021) for i in range(8)]
    cenas.append({"id": "ruim", "datetime": "2019-12-01T00:00:00Z", "valido_no_municipio": 0.3})
    esc = im.escolher_cenas(cenas, 0.85, 9)
    assert len(esc) == 9 and "ruim" not in {c["id"] for c in esc}
    por_ano = pd.Series([c["datetime"][:4] for c in esc]).value_counts()
    assert por_ano.max() <= 3 and [c["datetime"] for c in esc] == sorted(c["datetime"] for c in esc)


def test_duplicate_reprocessings_keep_the_latest_generation():
    def item(i, g):
        return {"id": i, "properties": {"datetime": "2021-03-30T13:30:49Z", "s2:generation_time": g}}
    out = im.deduplicar([item("a", "2021-03-30"), item("b", "2023-05-18"), item("c", "2023-02-19")])
    assert [i["id"] for i in out] == ["b"]


def test_window_is_even_aligned_contains_the_grid_and_refuses_a_municipality_outside_the_tile():
    grade = {"origem_x": 500000.0, "origem_y": 6700000.0, "linhas": 100, "colunas": 100, "celula_m": 30.0}
    transf = [10.0, 0, 399960.0, 0, -10.0, 6800000.0]
    j = im.janela_do_municipio(grade, "EPSG:31982", "EPSG:31982", transf, (10980, 10980), 60.0)
    assert j.linha % 2 == 0 and j.coluna % 2 == 0 and j.linhas % 2 == 0 and j.colunas % 2 == 0
    assert 399960 + 10 * j.coluna <= 500000 - 60 and 399960 + 10 * (j.coluna + j.colunas) >= 503000 + 60 - 20
    with pytest.raises(ValueError, match="não cabe no tile"):
        im.janela_do_municipio(grade, "EPSG:31982", "EPSG:31982", [10.0, 0, 520000.0, 0, -10.0, 6800000.0], (10980, 10980), 60.0)


def test_reflectance_uses_the_scale_and_offset_of_each_scene_and_masks_nodata(tmp_path):
    reg = {"bandas": {"red": {"arquivo": "red.npy", "passo": 1, "escala": 0.0001, "deslocamento": -0.1, "nodata": 0}, "swir16": {"arquivo": "s.npy", "passo": 2, "escala": 0.0001, "deslocamento": 0.0, "nodata": 0}}}
    np.save(tmp_path / "red.npy", np.array([[0, 1100, 2100, 3100]], dtype="uint16"))
    np.save(tmp_path / "s.npy", np.array([[5000, 0]], dtype="uint16"))
    r = im.refletancia(tmp_path, reg, "red")
    assert np.isnan(r[0, 0]) and r[0, 1] == pytest.approx(0.01) and r[0, 3] == pytest.approx(0.21)
    s = im.refletancia(tmp_path, reg, "swir16")
    assert s.shape == (2, 4) and s[0, 0] == s[1, 1] == pytest.approx(0.5) and np.isnan(s[0, 2])
    assert im.refletancia(tmp_path, reg, "red", (0, 1)).shape == (1, 4)


def test_declared_radiometric_offset_is_kept_only_when_the_digital_numbers_contain_it():
    com = np.random.default_rng(0).integers(1000, 4000, 5000)          # DN com o +1000 (mínimo de reflectância ~0)
    sem = np.random.default_rng(0).integers(50, 3000, 5000)            # DN sem o +1000, como nas 30 cenas reais
    assert im.deslocamento_efetivo(com, 1e-4, -0.1) == -0.1
    assert im.deslocamento_efetivo(sem, 1e-4, -0.1) == 0.0
    assert im.deslocamento_efetivo(sem, 1e-4, 0.0) == 0.0


def test_calibration_writes_the_effective_offset_to_every_reflectance_band_and_reflectance_stays_non_negative(tmp_path):
    pasta = tmp_path / "c1"
    pasta.mkdir()
    rng = np.random.default_rng(1)
    for nome in ("blue", "red"):
        np.save(pasta / f"{nome}.npy", rng.integers(100, 3000, (64, 64)).astype("uint16"))
    np.save(pasta / "scl.npy", np.full((32, 32), 4, "uint8"))
    reg = {"id": "c1", "bandas": {n: {"arquivo": f"{n}.npy", "passo": 1, "escala": 1e-4, "deslocamento": -0.1, "nodata": 0} for n in ("blue", "red")} | {"scl": {"arquivo": "scl.npy", "passo": 2, "escala": None, "deslocamento": None, "nodata": None}}}
    out = im.calibrar_deslocamentos(tmp_path, [reg])[0]
    assert out["bandas"]["red"]["deslocamento_efetivo"] == 0.0 and "deslocamento_efetivo" not in out["bandas"]["scl"] and out["deslocamento_conferido"]["declarado"] == -0.1
    assert np.nanmin(im.refletancia(pasta, out, "red")) >= 0.0


# ------------------------------------------------------------------------------------------------ referência
def _grade_sintetica(tmp_path):
    codigos = {"Edificação": 5, "Vias Pavimentadas": 12, "Vegetação Nativa": 11, "Solo Exposto": 9, "Corpo Hídrico": 2, "Jardins, Passeios ou Áreas semi urbanizadas": 6}
    (tmp_path / "classes.json").write_text(json.dumps({"codigos": codigos}))
    cols = {f"area_m2__{i:02d}": [0.0, 0.0, 0.0] for i in range(1, 16)}
    cols["area_m2__05"], cols["area_m2__12"], cols["area_m2__11"] = [300.0, 0, 0], [0.0, 0, 0], [300.0, 0, 0]
    cols["area_m2__06"], cols["area_m2__09"], cols["area_m2__02"] = [300.0, 800, 0], [0.0, 0, 0], [0.0, 0, 900]
    g = pd.DataFrame({"linha": [0, 0, 1], "coluna": [0, 1, 0], **cols})
    g.to_parquet(tmp_path / "g.parquet")
    return {"linhas": 2, "colunas": 2, "celula_m": 30.0}


ROTULOS = {"construido": ["Edificação", "Vias Pavimentadas"], "vegetacao": ["Vegetação Nativa"], "solo_exposto": ["Solo Exposto"], "agua": ["Corpo Hídrico"],
           "misto_excluido": ["Jardins, Passeios ou Áreas semi urbanizadas"], "celula_minima_nao_mista_m2": 540}


def test_labels_are_fractions_of_the_non_mixed_area_and_the_mixed_class_is_left_out(tmp_path):
    grade = _grade_sintetica(tmp_path)
    a = rf.alvos_da_profill(tmp_path / "g.parquet", tmp_path / "classes.json", grade, ROTULOS)
    assert a["frac_construido"][0, 0] == pytest.approx(0.5) and a["frac_vegetacao"][0, 0] == pytest.approx(0.5)
    assert a["jardins_frac"][0, 0] == pytest.approx(300 / 900) and a["nao_mista_m2"][0, 0] == 600
    assert a["valida"][0, 0] and not a["valida"][0, 1]          # 0 m² não misto: fora; 800 m² só de classe mista: fora
    assert a["valida"][1, 0] and a["frac_agua"][1, 0] == 1.0 and not a["valida"][1, 1]   # a célula sem registro nem vira zero
    soma = sum(a[f"frac_{k}"][0, 0] for k in rf.GRUPOS)
    assert soma == pytest.approx(1.0)


def test_labels_refuse_a_class_name_that_does_not_exist_in_the_source(tmp_path):
    grade = _grade_sintetica(tmp_path)
    with pytest.raises(ValueError, match="inexistentes"):
        rf.alvos_da_profill(tmp_path / "g.parquet", tmp_path / "classes.json", grade, {**ROTULOS, "agua": ["Lago"]})


def test_each_block_belongs_to_one_fold_small_blocks_are_dropped_and_folds_are_balanced():
    blocos = rf.identificador_de_blocos((40, 40), 10)
    assert blocos.max() == 15 and len(np.unique(blocos)) == 16
    valida = np.ones((40, 40), bool)
    valida[:10, :10] = False
    valida[10, 10:] = True
    estrato = np.tile(np.linspace(0, 1, 40), (40, 1))
    d, reg = rf.dobras_por_blocos(blocos, valida, estrato, 4, 7, minimo_de_celulas=20)
    for b in np.unique(blocos[valida]):
        assert len(np.unique(d[blocos == b][valida[blocos == b]])) == 1
    assert (d[~valida] == -1).all() and set(np.unique(d[d >= 0])) <= {0, 1, 2, 3}
    d2, _ = rf.dobras_por_blocos(blocos, valida, estrato, 4, 7, minimo_de_celulas=20)
    assert np.array_equal(d, d2)                                    # reprodutível com a mesma semente
    assert max(reg["celulas_por_dobra"].values()) - min(reg["celulas_por_dobra"].values()) <= 300


def test_training_mask_keeps_a_buffer_away_from_test_cells():
    valida = np.ones((20, 20), bool)
    teste = np.zeros_like(valida)
    teste[:, :10] = True
    treino = rf.mascara_de_treino(teste, valida, 3)
    assert not treino[:, :10].any() and not treino[:, 10:13].any() and treino[:, 13:].all()


def test_quadrant_protocol_defines_four_regions():
    blocos = rf.identificador_de_blocos((40, 40), 10)
    d = np.zeros((40, 40), "int16")
    r = md.regioes_por_quadrante(blocos, d, 4)
    assert set(np.unique(r)) == {0, 1, 2, 3} and r[0, 0] == 0 and r[0, 39] == 1 and r[39, 0] == 2 and r[39, 39] == 3


# ------------------------------------------------------------------------------------------------ métricas
def test_fraction_errors_have_exact_values():
    e = av.erros_da_fracao(np.array([0.0, 0.5, 1.0]), np.array([0.1, 0.5, 0.7]))
    assert e["mae"] == pytest.approx(0.4 / 3) and e["vies"] == pytest.approx(-0.2 / 3) and e["rmse"] == pytest.approx(np.sqrt((0.01 + 0.09) / 3))


def test_confusion_matrix_f1_and_iou_match_a_hand_computation():
    ref, pred = np.array([0, 0, 0, 1, 1, 2]), np.array([0, 0, 1, 1, 1, 0])
    cm = av.matriz_de_confusao(ref, pred, 4)
    assert cm.tolist() == [[2, 1, 0, 0], [0, 2, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0]]
    m = av.f1_e_iou(cm)
    assert m["precisao"][0] == pytest.approx(2 / 3) and m["recall"][0] == pytest.approx(2 / 3) and m["f1"][1] == pytest.approx(0.8)
    assert m["iou"][0] == pytest.approx(0.5) and m["iou"][1] == pytest.approx(2 / 3) and np.isnan(m["f1"][3])
    assert m["f1"][2] == 0.0                                          # existe na referência e ninguém a acertou: 0, não ignorada
    assert m["macro_f1"] == pytest.approx((2 / 3 + 0.8 + 0.0) / 3)


def test_a_predictor_that_always_says_the_majority_class_does_not_get_a_high_macro_f1():
    ref = np.repeat([0, 1, 2, 3], [10, 80, 5, 5])
    cm = av.matriz_de_confusao(ref, np.ones_like(ref))
    m = av.f1_e_iou(cm)
    assert m["macro_f1"] < 0.25 and m["f1"][1] > 0.85 and m["f1"][0] == m["f1"][2] == m["f1"][3] == 0.0


def _par(n=600, erro=0.1, seed=0):
    rng = np.random.default_rng(seed)
    ref = rng.dirichlet([1, 1, 1, 1], n)
    pred = np.abs(ref + rng.normal(0, erro, ref.shape)); pred /= pred.sum(1, keepdims=True)
    return ref, pred, np.repeat(np.arange(30), n // 30)


def test_block_bootstrap_is_reproducible_brackets_the_point_estimate_and_widens_with_noise():
    ref, pred, bl = _par()
    ev = av.estatisticas_por_bloco(ref, pred, bl)
    a, b = av.bootstrap_por_blocos(ev, 200, 1), av.bootstrap_por_blocos(ev, 200, 1)
    assert a == b and a["mae"]["ic95"][0] <= a["mae"]["valor"] <= a["mae"]["ic95"][1]
    assert a["mae"]["valor"] == pytest.approx(av.erros_da_fracao(ref[:, 0], pred[:, 0])["mae"])
    ref2, pred2, bl2 = _par(erro=0.3)
    assert av.bootstrap_por_blocos(av.estatisticas_por_bloco(ref2, pred2, bl2), 200, 1)["mae"]["valor"] > a["mae"]["valor"]


def test_paired_difference_is_negative_when_the_first_model_is_better():
    ref, bom, bl = _par(erro=0.05)
    _, mau, _ = _par(erro=0.3, seed=0)
    d = av.diferenca_pareada(av.estatisticas_por_bloco(ref, bom, bl), av.estatisticas_por_bloco(ref, mau, bl), 200, 3)
    assert d["diferenca_mae"] < 0 and d["ic95"][1] < 0


def test_area_error_per_neighbourhood_uses_the_area_weighted_fraction():
    ref = np.array([[0.5, .5, 0, 0]] * 4)
    pred = np.array([[0.5, .5, 0, 0]] * 2 + [[0.6, .4, 0, 0]] * 2)
    r = av.erro_de_area_por_bairro(ref, pred, np.full(4, 900.0), np.array([0, 0, 1, 1]), ["A", "B"], 0.10, minimo_de_celulas=1)
    assert r["bairros_avaliados"] == 2 and r["fracao_dentro_do_limite"] == 0.5
    b = {x["bairro"]: x for x in r["bairros"]}
    assert b["A"]["erro_relativo"] == 0 and b["B"]["erro_relativo"] == pytest.approx(0.2)


# ------------------------------------------------------------------------------------------------ modelos
def _mundo(n=24):
    rng = np.random.default_rng(1)
    f = rng.random((n, n)).astype("float32")                       # sinal real: a fração construída é função do atributo "ndvi"
    atrib = np.full((n, n, len(at.NOMES)), np.nan, "float32")
    atrib[..., at.NOMES.index("ndvi")] = 1 - f + rng.normal(0, 0.02, (n, n))
    atrib[..., at.NOMES.index("ndbi")] = f + rng.normal(0, 0.02, (n, n))
    atrib[..., at.NOMES.index("mndwi")] = rng.normal(0, 0.1, (n, n))
    Y = np.stack([f, 1 - f, np.zeros_like(f), np.zeros_like(f)], -1)
    return atrib, Y


def test_spatial_cross_validation_predicts_every_cell_out_of_fold_and_beats_the_mean_when_there_is_signal():
    atrib, Y = _mundo()
    valida = np.ones((24, 24), bool)
    blocos = rf.identificador_de_blocos((24, 24), 6)
    dobras, _ = rf.dobras_por_blocos(blocos, valida, Y[..., 0], 4, 3, minimo_de_celulas=10)
    params = {"n_estimators": 20, "min_samples_leaf": 3, "max_features": 0.5, "n_jobs": 1, "amostras_de_treino": None}
    r = md.validar_espacialmente(atrib, Y, valida, dobras, ["ndvi", "ndbi", "mndwi"], 1, params, 5, "rf")
    m = md.validar_espacialmente(atrib, Y, valida, dobras, [], 1, params, 5, "media")
    ref = Y.reshape(-1, 4)[r["indices"]]
    assert len(r["indices"]) == int((dobras >= 0).sum()) and np.isfinite(r["pred"]).all() and np.allclose(r["pred"].sum(1), 1)
    assert av.erros_da_fracao(ref[:, 0], r["pred"][:, 0])["mae"] < 0.5 * av.erros_da_fracao(ref[:, 0], m["pred"][:, 0])["mae"]
    assert (r["sd"] >= 0).all()


def test_the_training_set_never_contains_the_test_fold():
    """Se uma célula do teste entrasse no treino, o RF a decoraria: com rótulo aleatório e atributo-identificador o erro seria ~0."""
    n = 24
    rng = np.random.default_rng(2)
    f = rng.random((n, n)).astype("float32")                       # rótulo puro ruído
    atrib = np.full((n, n, len(at.NOMES)), np.nan, "float32")
    atrib[..., at.NOMES.index("ndvi")] = np.arange(n * n).reshape(n, n)       # identificador único da célula
    Y = np.stack([f, 1 - f, np.zeros_like(f), np.zeros_like(f)], -1)
    valida = np.ones((n, n), bool)
    dobras, _ = rf.dobras_por_blocos(rf.identificador_de_blocos((n, n), 6), valida, f, 4, 1, minimo_de_celulas=10)
    params = {"n_estimators": 30, "min_samples_leaf": 1, "max_features": 1.0, "n_jobs": 1, "amostras_de_treino": None}
    r = md.validar_espacialmente(atrib, Y, valida, dobras, ["ndvi"], 1, params, 1, "rf")
    mae = av.erros_da_fracao(Y.reshape(-1, 4)[r["indices"]][:, 0], r["pred"][:, 0])["mae"]
    assert mae > 0.15                                              # ruído não é previsível; a base de comparação (aleatório) é ~0,33


def test_normalisation_returns_fractions_that_sum_to_one():
    p = md.normalizar(np.array([[0.5, 0.5, 0.5, 0.5], [-1, 0, 0, 0], [2, 1, 1, 0]]))
    assert np.allclose(p.sum(1), 1) and (p >= 0).all() and p[1].tolist() == [0.25] * 4


# ------------------------------------------------------------------------------------------------ configuração real
def test_config_class_names_exist_in_the_real_profill_dictionary_and_every_class_has_one_group():
    cfg = cfgmod.load_config(RAIZ / "config/geoai.yaml")
    f = RAIZ / "data/processed/uso_solo/classes_e_codigos.json"
    if not f.exists():
        pytest.skip("dados da Profill ausentes")
    codigos = set(json.loads(f.read_text())["codigos"])
    usados = [c for k in (*rf.GRUPOS, "misto_excluido") for c in cfg["rotulos"][k]]
    assert set(usados) == codigos and len(usados) == len(codigos)       # nenhuma classe esquecida nem repetida
    assert cfg["imagens"]["fim"] <= "2021-12-31" and cfg["imagens"]["inicio"] >= "2018-01-01"


# ------------------------------------------------------------------------------------------------ embeddings AlphaEarth
def test_alphaearth_dequantisation_follows_the_official_formula_and_masks_minus_128():
    v = np.array([127, -127, 0, 64, -128], dtype="int8")
    d = im.descontar_quantizacao(v)
    assert d[0] == pytest.approx((127 / 127.5) ** 2) and d[1] == pytest.approx(-((127 / 127.5) ** 2)) and d[2] == 0 and d[3] == pytest.approx((64 / 127.5) ** 2) and np.isnan(d[4])


def test_embedding_window_is_pasted_north_up_from_a_south_up_cog(tmp_path, monkeypatch):
    import rasterio
    from rasterio.transform import Affine
    # arquivo com o norte embaixo (pixel de altura positivo, como o bucket): o valor da banda 0 é o número da linha de baixo para cima
    ny, nx = 30, 40
    dados = np.zeros((64, ny, nx), dtype="int8")
    dados[0] = np.arange(ny, dtype="int8")[:, None]
    dados[1] = np.arange(nx, dtype="int8")[None, :]
    with rasterio.open(tmp_path / "a.tiff", "w", driver="GTiff", height=ny, width=nx, count=64, dtype="int8", crs="EPSG:32722", transform=Affine(10, 0, 1000, 0, 10, 5000), nodata=-128) as dst:
        dst.write(dados)
    monkeypatch.setattr(im, "AEF_BUCKET", str(tmp_path) + "/")
    # caixa que pega as linhas 5 a 25 do arquivo (y de 5050 a 5250) e as colunas 10 a 30 (x de 1100 a 1300)
    meta = im.baixar_embeddings(["a.tiff"], (1100, 5050, 1300, 5250), tmp_path / "saida.npy")
    out = np.load(tmp_path / "saida.npy")
    assert out.shape == (20, 20, 64) and meta["topo_y"] == 5250 and meta["origem_x"] == 1100
    assert out[0, 0, 0] == 24 and out[-1, 0, 0] == 5            # a primeira linha da saída é a mais ao norte
    assert out[0, 0, 1] == 10 and out[0, -1, 1] == 29
    assert not (out == -128).any()
