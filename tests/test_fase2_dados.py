"""Fase 2: inventário de drenagem, uso do solo (Profill 2022) e estrutura de geração de escoamento. Tudo com dados SINTÉTICOS (nenhum teste usa serviço online).

O caso do uso do solo é desenhado com coordenadas múltiplas de 3 m (o passo da pintura), então sobreposição, lacuna e área fora do município têm valor exato conhecido de antemão.
"""
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely

from flooding_mapping import escoamento

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import auditar_drenagem_poa as aud  # noqa: E402
import processar_drenagem_poa as dren  # noqa: E402
import processar_uso_solo_poa as solo  # noqa: E402


# =====================================================================  escoamento: unidades, métodos e distinção entre fundamento e hipótese
def test_generation_formula_units_are_millimetres_square_metres_and_cubic_metres():
    assert escoamento.volume_gerado_m3(1, 1, 1) == pytest.approx(0.001)          # 1 mm sobre 1 m² é 1 litro
    assert escoamento.volume_gerado_m3(30, 1000, 0.5) == pytest.approx(15.0)     # 30 mm x 1000 m² x 0,5 = 15 m³
    assert escoamento.volume_gerado_m3(10, 5, 0.0) == 0.0
    v = escoamento.volume_gerado_m3(np.array([10, 30, 60]), 100.0, 0.8)
    assert v.tolist() == pytest.approx([0.8, 2.4, 4.8])                           # linear em P
    assert escoamento.volume_gerado_m3(30, 2000, 0.4) == pytest.approx(2 * escoamento.volume_gerado_m3(30, 1000, 0.4))   # linear em A


@pytest.mark.parametrize("p,a,c", [(-1, 10, 0.5), (10, -1, 0.5), (10, 10, 1.2), (10, 10, -0.1), (float("nan"), 10, 0.5), (10, float("inf"), 0.5), (10, 10, float("nan"))])
def test_generation_refuses_values_that_break_the_units_or_the_coefficient_range(p, a, c):
    with pytest.raises(ValueError):
        escoamento.volume_gerado_m3(p, a, c)


def test_method_one_has_only_referenced_classes_and_never_fills_the_rest():
    m1 = escoamento.carregar_metodo1()
    assert set(m1.classe_original) == {"Edificação", "Vias Pavimentadas"}
    assert m1.referencia.str.contains("TxDOT").all() and m1.valor_citado.notna().all()
    areas = {"Edificação": 1000.0, "Vias Pavimentadas": 2000.0, "Campo": 5000.0, "Vegetação Nativa": 7000.0, "Corpo Hídrico": 400.0, "Área Úmida": 100.0}
    r = escoamento.geracao_metodo1(areas, 30)
    assert r["volume_m3"]["min"] == pytest.approx(30 * (1000 * 0.75 + 2000 * 0.70) / 1000) and r["volume_m3"]["max"] == pytest.approx(30 * (1000 * 0.95 + 2000 * 0.95) / 1000)
    assert r["area_coberta_m2"] == 3000 and r["area_nao_coberta_pelo_metodo_m2"] == 12000 and r["area_fora_do_calculo_m2"] == 500
    assert set(r["classes_nao_cobertas"]) == {"Campo", "Vegetação Nativa"}               # nada de preencher o que a referência não cobre
    assert "não é volume retido" in r["aviso"] and r["metodo"] == 1


def test_method_two_scenarios_are_declared_hypotheses_and_independent_of_method_one():
    t = escoamento.carregar_cenarios()
    assert set(t.natureza_do_valor) <= escoamento.NATUREZAS
    assert not (set(t.classe_original[t.natureza_do_valor != "fora_do_calculo_de_escoamento"]) & set(escoamento.carregar_metodo1().classe_original))   # nenhum cenário redefine o Método 1
    areas = {"Edificação": 1000.0, "Campo": 5000.0, "Jardins, Passeios ou Áreas semi urbanizadas": 4000.0, "Vegetação Nativa": 7000.0, "Área Úmida": 100.0}
    inf, sup = escoamento.geracao_cenario(areas, 30, ["fisico_inferior"]), escoamento.geracao_cenario(areas, 30, ["fisico_superior"])
    assert inf["volume_m3"]["max"] == 0.0 and sup["volume_m3"]["min"] == pytest.approx(30 * (5000 + 4000 + 7000) / 1000)         # C=0 e C=1: limites físicos
    assert "Edificação" not in sup["por_classe"]                                                   # a classe do Método 1 fica de fora do cenário
    ana = escoamento.geracao_cenario(areas, 30, ["referencia_analoga", "referencia_analoga_jardins_f50"])
    assert ana["volume_m3"]["min"] == pytest.approx(30 * (5000 * 0.05 + 4000 * 0.40) / 1000) and ana["volume_m3"]["max"] == pytest.approx(30 * (5000 * 0.80 + 4000 * 0.65) / 1000)
    assert "Vegetação Nativa" in ana["classes_sem_valor_no_cenario"] and ana["area_sem_valor_no_cenario_m2"] == 7000    # sem referência: lacuna, não valor
    assert ana["hipoteses"] and ana["metodo"] == 2 and "não são medições" in ana["natureza"]
    with pytest.raises(ValueError):
        escoamento.geracao_cenario(areas, 30, ["referencia_analoga_jardins_f25", "referencia_analoga_jardins_f50"])   # duas hipóteses para a mesma classe
    with pytest.raises(ValueError):
        escoamento.geracao_cenario(areas, 30, ["nao_existe"])


def test_the_mixture_scenarios_follow_the_stated_formula_and_their_references():
    t = escoamento.carregar_cenarios()
    for pct in (25, 50, 75):
        f = pct / 100
        linha = t[t.cenario == f"referencia_analoga_jardins_f{pct}"].iloc[0]
        assert linha.c_min == pytest.approx(f * 0.75 + (1 - f) * 0.05) and linha.c_max == pytest.approx(f * 0.95 + (1 - f) * 0.35)
        assert linha.natureza_do_valor == "mistura_de_referencias_com_fracao_hipotetica" and "TxDOT" in linha.referencia and "NÃO consta na camada" in linha.hipotese_declarada


def test_every_class_of_the_land_use_layer_has_exactly_one_treatment_and_the_tables_agree():
    antiga = pd.read_csv(RAIZ / "config/uso_solo_profill_hidrologia.csv")
    classes = set(antiga.classe_original)
    assert len(classes) == 15
    m1, m2 = escoamento.carregar_metodo1(), escoamento.carregar_cenarios()
    fundamentadas, fora = set(m1.classe_original), set(m2[m2.natureza_do_valor == "fora_do_calculo_de_escoamento"].classe_original)
    com_cenario = set(m2[m2.natureza_do_valor != "fora_do_calculo_de_escoamento"].classe_original)
    assert fundamentadas | fora | com_cenario == classes and not (fundamentadas & fora) and not (fundamentadas & com_cenario)
    # a tabela de categorias e o Método 1 não podem divergir
    for r in antiga[antiga.tratamento_no_modelo == "faixa_fundamentada"].itertuples():
        linha = m1[m1.classe_original == r.classe_original].iloc[0]
        assert (linha.c_min, linha.c_max) == (r.coeficiente_min, r.coeficiente_max)
    assert set(antiga[antiga.tratamento_no_modelo == "fora_do_calculo_de_escoamento"].classe_original) == fora
    assert set(antiga[antiga.tratamento_no_modelo == "faixa_fundamentada"].classe_original) == fundamentadas


# =====================================================================  uso do solo: caso sintético com resposta exata
def anel(x0, y0, x1, y1):
    """Esri exterior ring: clockwise."""
    return [[x0, y0], [x0, y1], [x1, y1], [x1, y0], [x0, y0]]


def feicao(oid, classe, aneis, area=None):
    return {"a": {"objectid": oid, "classe": classe, "area_m2": area, "area_ha": None, "fitofision": " ", "estagio": " ", "regiao": "Centro/Norte"}, "g": {"rings": aneis}}


@pytest.fixture
def mundo(tmp_path):
    """Grid 600 x 600 m (20 x 20 cells of 30 m, blocks of 10 cells); municipality 600 x 450 m. Every coordinate is a multiple of 3 m."""
    feicoes = [
        feicao(1, "Edificação", [anel(30, 30, 60, 60)], 900.0),                                   # A
        feicao(2, "Vias Pavimentadas", [anel(0, 99, 600, 129)], 18000.0),                          # larga: vai para a partição "grandes"
        feicao(3, "Campo", [anel(300, 300, 600, 600)], 90000.0),                                   # grande; metade fora do município
        feicao(4, "Edificação", [anel(30, 30, 60, 60)], 900.0),                                    # duplicata exata de A
        feicao(5, "Solo Exposto", [[[201, 201], [231, 231], [231, 201], [201, 231], [201, 201]]]),  # laço (inválido)
        feicao(6, "Jardins, Passeios ou Áreas semi urbanizadas", [anel(36, 36, 66, 66)], 900.0),   # sobrepõe A em 24 x 24
        feicao(7, "Cultivo Irrigado", [anel(900, 900, 930, 930)], 900.0),                          # fora da grade
        feicao(8, "Corpo Hídrico", [anel(0, 300, 120, 330), [[30, 306], [60, 306], [60, 324], [30, 324], [30, 306]]], 1800.0),  # com buraco (anel anti-horário)
    ]
    raw = tmp_path / "raw"
    raw.mkdir()
    for k, lote in enumerate((feicoes[:4], feicoes[4:]), start=1):
        with gzip.GzipFile(filename="", mode="wb", fileobj=open(raw / f"parte_{k:04d}.jsonl.gz", "wb"), mtime=0) as gz:
            for f in lote:
                gz.write((json.dumps(f) + "\n").encode())
    return raw, solo.Grade(origem_x=0.0, origem_y=600.0, linhas=20, colunas=20, bloco=10, sub=10), shapely.box(0, 0, 600, 450)


def rodar(mundo, destino):
    raw, grade, _ = mundo
    municipio = shapely.box(0, 0, 600, 450)                                                  # a faixa de y = 450 a 600 fica fora do município
    est = solo.particionar(sorted(raw.glob("parte_*.jsonl.gz")), destino, grade)
    codigos = solo.codigos_das_classes(est["classes"])
    celulas, tot = solo.rasterizar(destino, grade, municipio, codigos)
    return est, codigos, celulas, tot


def test_polygon_builder_keeps_holes_and_clockwise_rings_are_exteriors():
    g = solo.poligono([anel(0, 0, 10, 10), [[2, 2], [8, 2], [8, 8], [2, 8], [2, 2]]])
    assert g.area == pytest.approx(100 - 36) and g.is_valid
    assert solo.poligono([[[0, 0], [1, 1]]]) is None                                        # anel degenerado: sem geometria útil


def test_every_polygon_is_accounted_for_and_the_bad_ones_are_reported(mundo, tmp_path):
    est, codigos, celulas, tot = rodar(mundo, tmp_path / "blocos")
    assert est["lidos"] == 8 and est["sem_geometria_util"] == 0 and sum(est["por_parte"].values()) == 8
    assert est["invalidos"] == 1 and "Self-intersection" in " ".join(est["motivos_de_invalidez"])
    assert est["duplicatas_exatas"] == 1 and est["fora_da_grade"] == 1 and est["grandes"] == 2
    assert est["classes"]["Edificação"]["poligonos"] == 1 and est["classes"]["Edificação"]["duplicatas_excluidas"] == 1            # a duplicata não entra na área
    assert est["classes"]["Edificação"]["area_m2_geometria"] == pytest.approx(900) and est["classes"]["Edificação"]["area_m2_duplicatas_excluidas"] == pytest.approx(900)
    assert est["classes"]["Solo Exposto"]["area_m2_geometria"] == pytest.approx(450) and est["classes"]["Solo Exposto"]["invalidos"] == 1   # área do polígono reparado
    assert est["classes"]["Corpo Hídrico"]["area_m2_geometria"] == pytest.approx(120 * 30 - 30 * 18)       # o buraco (anel anti-horário) é descontado
    assert set(est["classes"]) == {"Edificação", "Vias Pavimentadas", "Campo", "Solo Exposto", "Jardins, Passeios ou Áreas semi urbanizadas", "Cultivo Irrigado", "Corpo Hídrico"}
    assert (tmp_path / "blocos" / "grandes.parquet").exists() and len(list((tmp_path / "blocos").glob("bloco_*.parquet"))) >= 1


def test_areas_overlap_gap_and_outside_municipality_have_the_exact_expected_values(mundo, tmp_path):
    est, codigos, celulas, tot = rodar(mundo, tmp_path / "blocos")
    # município: y de 0 a 450. União dentro dele: A+F = 900+900-576, via 18000, campo 300x150 = 45000 (a outra metade, y > 450, fica fora), laço 450, corpo hídrico com buraco
    agua = est["classes"]["Corpo Hídrico"]["area_m2_geometria"]
    assert agua == pytest.approx(120 * 30 - 30 * 18)                                          # 3600 - buraco de 540
    esperada_dentro = (900 + 900 - 576) + 18000 + 45000 + 450 + agua
    assert tot["classificada_dentro_do_municipio_m2"] == pytest.approx(esperada_dentro, abs=1e-6)
    assert tot["classificada_fora_do_municipio_m2"] == pytest.approx(45000, abs=1e-6)         # a metade do campo acima de y = 450
    assert tot["sobreposicao_m2"] == pytest.approx(576, abs=1e-6)                              # A e F; a duplicata não conta
    assert tot["area_do_municipio_m2"] == pytest.approx(600 * 450)
    assert tot["lacuna_dentro_do_municipio_m2"] == pytest.approx(600 * 450 - esperada_dentro, abs=1e-6)
    assert tot["classificada_dentro_do_municipio_m2"] + tot["lacuna_dentro_do_municipio_m2"] == pytest.approx(tot["area_do_municipio_m2"])


def test_gaps_are_checked_against_known_water_without_assuming_the_cause():
    celulas = pd.DataFrame({"x_centro": [15.0, 45.0, 75.0, 600.0], "y_centro": [15.0, 15.0, 15.0, 15.0], "area_lacuna_m2": [900.0, 900.0, 450.0, 0.0]})
    agua = gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 60, 30)], crs=solo.CRS)                 # cobre as duas primeiras células
    r = solo.lacunas_contra_agua(celulas, agua)
    assert r["lacuna_m2"] == 2250.0 and r["celulas_com_lacuna"] == 3                              # a célula sem lacuna não conta
    assert r["lacuna_sobre_agua_osm_m2"] == 1800.0 and r["fracao_da_lacuna_sobre_agua_osm"] == pytest.approx(0.8)
    assert r["lacuna_fora_da_agua_m2"] == 450.0 and r["fracao_da_lacuna_fora_da_agua_a_ate_100m_da_agua"] == 1.0           # a 15 m da borda
    assert "pendência" in r["leitura"] and solo.lacunas_contra_agua(celulas.iloc[3:], agua) == {"lacuna_m2": 0.0}


def test_class_areas_in_the_30m_cells_add_up_to_the_painted_class_totals(mundo, tmp_path):
    est, codigos, celulas, tot = rodar(mundo, tmp_path / "blocos")
    cols = [c for c in celulas.columns if c.startswith("area_m2__")]
    assert len(cols) == len(codigos) and set(cols) == {f"area_m2__{k:02d}" for k in codigos.values()}
    assert celulas[cols].to_numpy().sum() == pytest.approx(celulas["area_classificada_m2"].sum())
    assert (celulas["area_classificada_m2"] <= 900 + 1e-3).all()                                      # nenhuma célula tem mais que 900 m² classificados
    assert celulas[f"area_m2__{codigos['Edificação']:02d}"].sum() == pytest.approx(900 - 576)       # F (objectid maior) é pintada por cima de parte de A: o último vence
    assert celulas[f"area_m2__{codigos['Jardins, Passeios ou Áreas semi urbanizadas']:02d}"].sum() == pytest.approx(900)
    vias = celulas[f"area_m2__{codigos['Vias Pavimentadas']:02d}"].sum()
    assert vias == pytest.approx(18000) and est["classes"]["Vias Pavimentadas"]["area_m2_geometria"] == pytest.approx(18000)    # a partição "grandes" chegou a todos os blocos
    assert celulas[["linha", "coluna"]].duplicated().sum() == 0 and celulas["x_centro"].between(0, 600).all()
    assert (celulas["area_dentro_do_municipio_m2"] <= 900 + 1e-3).all()


def test_reprocessing_the_same_input_gives_identical_files(mundo, tmp_path):
    a = rodar(mundo, tmp_path / "a")[2]
    b = rodar(mundo, tmp_path / "b")[2]
    pd.testing.assert_frame_equal(a, b)
    fa, fb = tmp_path / "a.parquet", tmp_path / "b.parquet"
    a.to_parquet(fa, index=False, compression="zstd")
    b.to_parquet(fb, index=False, compression="zstd")
    assert hashlib.sha256(fa.read_bytes()).hexdigest() == hashlib.sha256(fb.read_bytes()).hexdigest()
    assert sorted(p.name for p in (tmp_path / "a").glob("*.parquet")) == sorted(p.name for p in (tmp_path / "b").glob("*.parquet"))
    for p in (tmp_path / "a").glob("*.parquet"):
        assert hashlib.sha256(p.read_bytes()).hexdigest() == hashlib.sha256((tmp_path / "b" / p.name).read_bytes()).hexdigest()


def test_the_grid_is_the_dem_grid_of_30m_and_is_not_finer(mundo):
    g = solo.grade_do_dem() if (RAIZ / "data/raw/dem").exists() and (RAIZ / "data/processed/municipality.parquet").exists() else mundo[1]
    assert g.celula == 30.0 and g.sub == 10                                              # 30 m como o Copernicus; os 3 m são só a pintura interna, não a resolução de saída
    assert g.transform.a == 30.0 and g.transform.e == -30.0


# =====================================================================  drenagem: inventário sem inferir capacidade nem conectividade
def test_standardising_keeps_original_values_and_only_adds_flags():
    df = pd.DataFrame({"OBJECTID": [1, 2, 3], "DIAMETRO": [300, 400, 300], "MATERIAL": ["CR", " ", None], "ALTITUDE_MONTANTE": [10.0, 283465.0, 0.0], "ALTITUDE_JUSANTE": [9.0, 8.0, 0.0],
                       "DECLIVIDADE": [0.01, -93539.0, None], "INSERCAOMONTANTE": [0.9, 0.0, 1.2], "ATIVO": ["1", " ", "1"], "DATAIMPLANTACAO": [1.1e12, -6.2e13, None]})
    out = dren._sinais(dren._padronizar(df, dren.CAMPOS_REDE))
    assert out["altitude_montante"].tolist()[:2] == [10.0, 283465.0]                          # o valor impossível NÃO é corrigido
    assert out["altitude_montante_fora_da_faixa_plausivel"].tolist() == [False, True, False]
    assert out["declividade_fora_da_faixa_plausivel"].tolist() == [False, True, False]
    assert out["insercao_montante_zero_possivel_ausencia"].tolist() == [False, True, False]
    assert out["material"].isna().tolist() == [False, True, True] and out["ativo_no_cadastro"].isna().tolist() == [False, True, False]   # branco vira nulo
    assert bool(out["data_implantacao_suspeita"].iloc[1]) and not bool(out["data_implantacao_suspeita"].iloc[0])


def test_duplicates_are_marked_not_deleted_and_reversed_lines_count_as_the_same_drawing():
    g = gpd.GeoSeries([shapely.LineString([(0, 0), (10, 0)]), shapely.LineString([(10, 0), (0, 0)]), shapely.LineString([(0, 0), (20, 0)])], crs=dren.CRS)
    ids = pd.Series([5, 6, 7])
    d = dren._duplicatas(g, ids)
    assert d.isna().tolist() == [True, False, True] and d.iloc[1] == 5                           # o 6 é a mesma linha do 5, invertida
    pts = gpd.GeoSeries([shapely.Point(1, 1), shapely.Point(1, 1.001), shapely.Point(3, 3)], crs=dren.CRS)
    assert dren._duplicatas(pts, pd.Series([1, 2, 3])).notna().tolist() == [False, True, False]   # diferença de 1 mm é a mesma posição (precisão de 1 cm)


def test_geometric_evidence_is_labelled_as_evidence_and_never_becomes_a_connection():
    redes = gpd.GeoDataFrame({"id_origem": [1, 2, 3]}, geometry=[shapely.LineString([(0, 0), (10, 0)]), shapely.LineString([(10, 0), (20, 0)]), shapely.LineString([(500, 500), (510, 500)])], crs=dren.CRS)
    pocos = gpd.GeoDataFrame({"id_origem": [1]}, geometry=[shapely.Point(0, 0)], crs=dren.CRS)
    r = dren.evidencia_geometrica(redes.copy(), pocos)
    assert r["evidencia_geometrica_fim_coincide_com_outro_extremo"].tolist() == [True, False, False]
    assert r["evidencia_geometrica_inicio_perto_de_poco_de_visita"].tolist() == [True, False, False]
    assert r["evidencia_geometrica_ambos_extremos_ligados"].tolist() == [True, False, False]
    novas = [c for c in r.columns if c not in ("id_origem", "geometry")]
    assert all(c.startswith("evidencia_geometrica_") for c in novas)                              # nenhuma coluna chamada "conectado" ou "trecho"
    assert not any(("conect" in c and not c.startswith("evidencia")) or "trecho" in c for c in r.columns)


def test_manholes_and_inlets_get_a_distance_but_never_a_segment_id():
    rede = gpd.GeoDataFrame({"id_origem": [10, 11]}, geometry=[shapely.LineString([(0, 0), (100, 0)]), shapely.LineString([(0, 50), (100, 50)])], crs=dren.CRS)
    bocas = gpd.GeoDataFrame({"id_origem": [1, 2]}, geometry=[shapely.Point(40, 1.5), shapely.Point(40, 80)], crs=dren.CRS)
    d = dren.distancia_a_rede(bocas, rede)
    assert d.round(3).tolist() == [1.5, 30.0]
    bocas["distancia_geometrica_a_rede_pluvial_m"] = d
    assert not any("trecho" in c or "segmento" in c for c in bocas.columns)


def test_pumps_never_get_a_capacity_or_a_flow_and_the_project_comparison_is_reported(tmp_path, monkeypatch):
    raiz = tmp_path / "raw"
    raiz.mkdir()
    feicoes = [{"atributos": {"fid": i + 1, "name": n, "capacidade": " ", "local": " ", "f__rea_prot": " ", "f__rea_cont": " ", "se____o_re": " ", "configura_": " ", "endere__o": " ", "descri____": " "},
                "geometria": {"x": x, "y": y}} for i, (n, x, y) in enumerate([("CB-1", 480000.0, 6670000.0), ("CB-NOVA", 481000.0, 6671000.0)])]
    (raiz / "casas_de_bomba_ebap.json").write_text(json.dumps({"camada": "x", "campo_de_identificador": "fid", "campos": [], "feicoes": feicoes}))
    monkeypatch.setattr(aud, "RAW", raiz)
    para_deg = __import__("pyproj").Transformer.from_crs(31982, 4674, always_xy=True).transform
    lon, lat = para_deg(480010.0, 6670000.0)
    bombas = dren.construir_bombas([{"nome": "CB-1", "lon": lon, "lat": lat}, {"nome": "CB-SO-NO-PROJETO", "lon": lon, "lat": lat}])
    assert not bombas["capacidade_informada"].any() and bombas["capacidade_texto_original"].isna().all()
    assert not any(k in c.lower() for c in bombas.columns for k in ("vazao", "vazão", "potencia", "m3s", "operac"))        # nenhuma grandeza inventada
    assert bombas["nome_no_projeto"].tolist() == [True, False] and bombas.loc[0, "distancia_ao_registro_do_projeto"] == pytest.approx(10.0, abs=0.1)
    assert math.isnan(bombas.loc[1, "distancia_ao_registro_do_projeto"])


def test_operational_classification_is_preserved_and_the_unattended_networks_are_not_promoted():
    # as colunas originais de classificação continuam lá, com o que o cadastro disse; nenhuma coluna nova afirma operação
    nomes = {n for n, _, _ in dren.CAMPOS_REDE.values()}
    assert {"ativo_no_cadastro", "acesso", "enabled"} <= nomes
    assert set(dren.REDES) == {"rede_pluvial", "rede_pluvial_sem_acesso", "rede_pluvial_nao_interligada"}
    assert not any("operacional" in n or "funcional" in n for n in nomes)


def test_processed_drainage_files_are_deterministic_and_registered_once(tmp_path):
    gdf = gpd.GeoDataFrame({"camada_origem": ["a", "a"], "id_origem": [2, 1], "valor": [1.5, 2.5], "valida": [True, True], "duplicata_exata_de": [np.nan, np.nan], "usar_no_inventario": [True, True]},
                           geometry=[shapely.Point(1, 1), shapely.Point(2, 2)], crs=dren.CRS)
    man = tmp_path / "manifest.json"
    e1 = dren.gravar(gdf, tmp_path / "x.parquet", {"inputs": []}, man)
    e2 = dren.gravar(gdf.copy(), tmp_path / "x.parquet", {"inputs": []}, man)
    assert e1["sha256"] == e2["sha256"] and e1["registered"] is True and e2["registered"] is False   # mesma entrada, mesmo arquivo, manifesto intacto
    assert len(json.loads(man.read_text())["sources"]) == 1
    lido = gpd.read_parquet(tmp_path / "x.parquet")
    assert str(lido.crs).endswith("31982") or lido.crs.to_epsg() == 31982
    assert lido["id_origem"].tolist() == [1, 2]                                                      # ordenado por identificador de origem


# =====================================================================  dados reais processados (quando existirem; fora do Git)
PROC = RAIZ / "data/processed"


@pytest.mark.skipif(not (PROC / "drenagem/qualidade_drenagem.json").exists(), reason="inventário de drenagem ainda não processado (data/processed fica fora do Git)")
def test_real_drainage_inventory_matches_the_raw_counts_and_promises_nothing():
    q = json.loads((PROC / "drenagem/qualidade_drenagem.json").read_text())
    for camada, x in q["rede_pluvial"].items():
        assert x["registros_processados"] + (x["rejeitados_na_coleta_sem_geometria"] or 0) + (x["rejeitados_na_coleta_coordenada_nao_finita"] or 0) == x["registros_na_fonte"], camada
        assert x["geometrias_invalidas"] == 0 or x["usados_no_inventario"] < x["registros_processados"]
    assert q["casas_de_bomba"]["colunas_sem_nenhum_preenchimento"] and "capacidade_texto_original" in q["casas_de_bomba"]["colunas_sem_nenhum_preenchimento"]
    assert q["casas_de_bomba_detalhe"]["capacidade_informada"] == 0
    gdf = gpd.read_parquet(PROC / "drenagem/rede_pluvial.parquet")
    assert gdf.crs.to_epsg() == 31982 and np.isfinite(shapely.get_coordinates(gdf.geometry.values)).all() and gdf.id_origem.notna().all()
    assert {"rede_pluvial", "rede_pluvial_sem_acesso", "rede_pluvial_nao_interligada"} == set(gdf.camada_origem)
    assert (gdf.loc[gdf.camada_origem == "rede_pluvial_nao_interligada", "ativo_no_cadastro"].fillna(0).astype(float) == 0).all()      # a original diz inativa: continua inativa
    assert not [c for c in gdf.columns if "vazao" in c or "capacidade" in c]


@pytest.mark.skipif(not (PROC / "uso_solo/qualidade_uso_solo.json").exists(), reason="uso do solo ainda não processado (data/processed fica fora do Git)")
def test_real_land_use_covers_the_city_with_traceable_areas_and_no_coefficient_applied():
    q = json.loads((PROC / "uso_solo/qualidade_uso_solo.json").read_text())
    assert q["poligonos_lidos"] == q["poligonos_processados"] + q["rejeitados_sem_geometria_util"]
    assert len(q["classes"]) == 15 and not q["classes_sem_nenhum_tratamento"] and not q["classes_inesperadas"]
    soma = sum(c["area_m2_geometria"] for c in q["classes"].values())
    assert soma == pytest.approx(q["area_classificada_pelos_poligonos_m2"]) and 0.9 < q["fracao_da_referencia_classificada"] <= 1.02
    assert q["grade"]["celula_m"] == 30.0
    cob = q["cobertura_dos_metodos"]
    assert cob["metodo1_area_m2"] + cob["fora_do_calculo_area_m2"] + cob["sem_coeficiente_fundamentado_area_m2"] == pytest.approx(q["area_classificada_pelos_poligonos_m2"])
    celulas = pd.read_parquet(PROC / "uso_solo/uso_solo_grade30m.parquet")
    assert len(celulas) == q["grade_de_saida"]["celulas"] and not any("coeficiente" in c or "volume" in c for c in celulas.columns)
    cols = list(q["grade_de_saida"]["colunas_de_area_por_classe"])
    assert celulas[cols].to_numpy().sum() == pytest.approx(celulas["area_classificada_m2"].sum(), rel=1e-4)
