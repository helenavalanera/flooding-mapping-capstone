"""Fase 3: motor de contribuição potencial e indicador topográfico. Tudo com DEMs e áreas SINTÉTICOS, com respostas conhecidas de antemão.

Mundo padrão: grade de 10 x 10 células de 30 m, relevo inclinado para leste (cada linha é um caminho de escoamento independente, de 10 células, que sai pela borda leste).
Cada célula tem 300 m² de Edificação e 600 m² de Campo.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flooding_mapping import escoamento, fluxo, motor_acumulo as motor
from flooding_mapping import susceptibility as sus

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
CLASSES = {"Edificação": 1, "Campo": 2}
M1, M2 = escoamento.carregar_metodo1(), escoamento.carregar_cenarios()
GRADE = motor.GradeRaster(origem_x=0.0, origem_y=300.0, linhas=10, colunas=10, celula=30.0)
AEQ_M1_MIN, AEQ_M1_MAX = 300 * 0.75, 300 * 0.95                                  # por célula (m²): só a Edificação é do Método 1
AEQ_ANA_MIN, AEQ_ANA_MAX = 600 * 0.05, 600 * 0.80                                # Campo por analogia


def centro(linha, coluna):
    return GRADE.origem_x + (coluna + 0.5) * 30.0, GRADE.origem_y - (linha + 0.5) * 30.0


def dem_inclinado():
    return np.tile(100.0 - np.arange(10, dtype=float), (10, 1))


def celulas_padrao():
    lin, col = np.divmod(np.arange(100), 10)
    return pd.DataFrame({"linha": lin, "coluna": col, "area_m2__01": 300.0, "area_m2__02": 600.0})


def trechos(*segs):
    return pd.DataFrame({"segmento_id": [f"s{i}" for i in range(len(segs))], "x0": [s[0] for s in segs], "y0": [s[1] for s in segs], "x1": [s[2] for s in segs], "y1": [s[3] for s in segs]})


def rodar(dem=None, segs=None, **kw):
    segs = segs if segs is not None else [(*centro(3, 2), *centro(3, 6)), (*centro(0, 2), *centro(9, 2))]
    return motor.executar(dem_inclinado() if dem is None else dem, GRADE, celulas_padrao(), CLASSES, M1, M2, trechos(*segs), **kw)


# ---------------------------------------------------------------- núcleo de fluxo
def test_forest_accumulation_reproduces_the_projects_flow_accumulation_exactly():
    rng = np.random.default_rng(0)
    dem = (rng.normal(size=(40, 45)).cumsum(0).cumsum(1) * 0.05 + np.linspace(0, 10, 45)[None, :]).astype("float32")
    dem[5:8, 10:13] = np.nan
    f = sus.fill_depressions(dem)
    rec, val = fluxo.receptores_d8(f)
    arv = fluxo.ArvoreDeFluxo(rec, val)
    ref = sus.flow_accumulation(f).ravel()
    assert np.array_equal(arv.acumular(np.ones(dem.size))[val], ref[val])


def test_mass_is_conserved_for_random_weights_and_several_columns_at_once():
    rng = np.random.default_rng(1)
    dem = rng.normal(size=(30, 30)).cumsum(0).cumsum(1) * 0.1
    f = sus.fill_depressions(dem)
    arv = fluxo.ArvoreDeFluxo(*fluxo.receptores_d8(f))
    w = rng.random((dem.size, 4)) * 100
    c = arv.conservacao(w)
    assert c["erro_relativo_maximo"] < 1e-12 and len(arv.exutorios()) >= 1
    assert np.allclose(arv.acumular(w)[:, 2], arv.acumular(w[:, 2]))                     # as colunas não se misturam


def test_a_cell_downstream_of_another_is_its_ancestor_and_never_itself():
    f = sus.fill_depressions(dem_inclinado())
    arv = fluxo.ArvoreDeFluxo(*fluxo.receptores_d8(f))
    a, b = 3 * 10 + 2, 3 * 10 + 6                                                       # mesma linha: b está a jusante de a
    assert arv.eh_ancestral(np.array([b]), np.array([a]))[0] and not arv.eh_ancestral(np.array([a]), np.array([b]))[0]
    assert not arv.eh_ancestral(np.array([a]), np.array([a]))[0]
    assert not arv.eh_ancestral(np.array([4 * 10 + 6]), np.array([a]))[0]                # outra linha: caminho independente


# ---------------------------------------------------------------- regra de associação: sem dupla contagem
def test_a_segment_along_the_flow_counts_each_upstream_cell_once():
    r = rodar()
    b = r["base"].iloc[0]
    # pegada: colunas 2 a 6 da linha 3. Local = 5 células. Contribuição = acumulado da célula mais a jusante (coluna 6) = 7 células (0 a 6): a água de 0 e 1 vem de fora da pegada
    assert b["n_celulas_com_dados"] == 5 and b["n_celulas_de_chegada"] == 1
    assert b["local_aeq_m1_min_m2"] == pytest.approx(5 * AEQ_M1_MIN) and b["contrib_aeq_m1_min_m2"] == pytest.approx(7 * AEQ_M1_MIN)
    assert b["contrib_aeq_m1_min_m2"] != pytest.approx((3 + 4 + 5 + 6 + 7) * AEQ_M1_MIN)  # somar os acumulados contaria a mesma água cinco vezes


def test_a_segment_across_independent_flow_paths_adds_them_up():
    r = rodar()
    b = r["base"].iloc[1]
    assert b["n_celulas_com_dados"] == 10 and b["n_celulas_de_chegada"] == 10             # dez linhas, dez caminhos disjuntos
    assert b["local_aeq_m1_max_m2"] == pytest.approx(10 * AEQ_M1_MAX) and b["contrib_aeq_m1_max_m2"] == pytest.approx(10 * 3 * AEQ_M1_MAX)   # cada caminho traz 3 células (colunas 0 a 2)


def test_contribution_equals_the_generation_over_the_union_of_upstream_catchments_by_brute_force():
    rng = np.random.default_rng(7)
    L, C = 22, 26
    dem = rng.normal(size=(L, C)).cumsum(0).cumsum(1) * 0.08 + np.linspace(0, 6, C)[None, :]
    dem[4:6, 8:10] = np.nan
    grade = motor.GradeRaster(0.0, 30.0 * L, L, C, 30.0)
    f = sus.fill_depressions(dem)
    arv = fluxo.ArvoreDeFluxo(*fluxo.receptores_d8(f))
    w = rng.random(dem.size) * 50
    w[~arv.valida] = 0
    acc = arv.acumular(w)
    segs = []
    for _ in range(60):
        x0, x1 = rng.uniform(0, 30.0 * C, 2)
        y0, y1 = rng.uniform(0, 30.0 * L, 2)
        segs.append((x0, y0, x1, y1))
    s = np.array(segs)
    seg, cel = motor.pegada_dos_trechos(s[:, 0], s[:, 1], s[:, 2], s[:, 3], grade, 6.0)
    r = motor.associar_aos_trechos(arv, len(segs), seg, cel, w[:, None], acc[:, None])
    filhos = {}
    for c in np.flatnonzero(arv.valida):
        if arv.receptor[c] >= 0:
            filhos.setdefault(int(arv.receptor[c]), []).append(int(c))

    def montante(c):
        achados, pilha = set(), [int(c)]
        while pilha:
            v = pilha.pop()
            if v not in achados:
                achados.add(v)
                pilha += filhos.get(v, [])
        return achados
    for i in range(len(segs)):
        cels = [int(c) for c in cel[seg == i] if arv.valida[c]]
        if not cels:
            assert np.isnan(r["contribuicao"][i, 0])
            continue
        uniao = set().union(*(montante(c) for c in cels))
        assert r["contribuicao"][i, 0] == pytest.approx(sum(w[c] for c in uniao), rel=1e-9)         # a união das bacias, cada célula uma vez
        assert r["local"][i, 0] == pytest.approx(sum(w[c] for c in set(cels)))
        assert r["contribuicao"][i, 0] >= r["local"][i, 0] - 1e-9                                  # toda célula da pegada está na união das bacias das células de chegada


def test_the_footprint_is_the_set_of_cells_crossed_once_each_and_ignores_what_is_outside_the_grid():
    seg, cel = motor.pegada_dos_trechos([15.0, -500.0], [165.0, 165.0], [135.0, -400.0], [165.0, 165.0], GRADE, 6.0)
    assert sorted(cel[seg == 0].tolist()) == [4 * 10 + c for c in range(0, 5)]               # y = 165 cai na linha 4 (floor((300-165)/30)); x de 15 a 135: colunas 0 a 4
    assert (seg == 1).sum() == 0                                                              # fora da grade: nenhuma célula
    assert len(set(zip(seg.tolist(), cel.tolist()))) == len(seg)


# ---------------------------------------------------------------- três grandezas, unidades e métodos
def test_generated_contribution_and_transported_volumes_are_three_different_things():
    r = rodar()
    assert r["relatorio"]["nao_calculado"]["volume_efetivamente_transportado"].startswith("não calculado")
    assert not [c for c in r["nivel2"].columns if "transportado" in c]                           # a grandeza não calculada não vira coluna
    n2 = r["nivel2"]
    um = n2[(n2.segmento_id == "s0") & (n2.p_mm == 30) & (n2.pacote == "metodo1")].iloc[0]
    assert um.v_gerado_local_min_m3 < um.contrib_potencial_min_m3                                # a contribuição inclui a água de fora da pegada


def test_volumes_follow_p_times_a_times_c_over_1000_and_scale_linearly_with_rain():
    r = rodar(precipitacoes_mm=(10, 20, 30))
    n2 = r["nivel2"]
    v = lambda p: n2[(n2.segmento_id == "s0") & (n2.p_mm == p) & (n2.pacote == "metodo1")].iloc[0]
    # uma célula: 300 m² de edificação a C = 0,75 e 30 mm -> 30 x 300 x 0,75 / 1000 = 6,75 m³; cinco células na pegada
    assert v(30).v_gerado_local_min_m3 == pytest.approx(5 * 30 * 300 * 0.75 / 1000)
    assert v(20).contrib_potencial_max_m3 == pytest.approx(2 * v(10).contrib_potencial_max_m3) and v(30).contrib_potencial_max_m3 == pytest.approx(3 * v(10).contrib_potencial_max_m3)
    assert (n2.v_gerado_local_min_m3 <= n2.v_gerado_local_max_m3 + 1e-12).all() and (n2.contrib_potencial_min_m3 <= n2.contrib_potencial_max_m3 + 1e-12).all()
    assert set(n2.p_mm) == {10.0, 20.0, 30.0} and set(n2.pacote) == set(motor.PACOTES)


def test_physical_limits_and_analogy_packages_have_the_declared_values():
    r = rodar()
    b = r["base"].iloc[0]
    assert b["local_aeq_limites_min_m2"] == 0.0 and b["local_aeq_limites_max_m2"] == pytest.approx(5 * 600)       # C = 0 e C = 1 só no Campo (o Método 1 não é redefinido)
    assert b["local_aeq_analoga_min_m2"] == pytest.approx(5 * AEQ_ANA_MIN) and b["local_aeq_analoga_max_m2"] == pytest.approx(5 * AEQ_ANA_MAX)


def test_methods_are_independent_changing_a_scenario_never_changes_method_one():
    r1 = rodar()
    m2 = M2.copy()
    m2.loc[(m2.cenario == "referencia_analoga") & (m2.classe_original == "Campo"), ["c_min", "c_max"]] = [0.10, 0.30]
    r2 = motor.executar(dem_inclinado(), GRADE, celulas_padrao(), CLASSES, M1, m2, trechos((*centro(3, 2), *centro(3, 6)), (*centro(0, 2), *centro(9, 2))))
    for c in [c for c in r1["base"].columns if "_m1_" in c or c == "fracao_montante_coberta_m1"]:
        assert np.allclose(r1["base"][c], r2["base"][c], equal_nan=True), c
    assert not np.allclose(r1["base"]["contrib_aeq_analoga_max_m2"], r2["base"]["contrib_aeq_analoga_max_m2"])
    m2_ruim = pd.concat([M2, pd.DataFrame([{"cenario": "referencia_analoga", "classe_original": "Edificação", "c_min": 0.1, "c_max": 0.2, "natureza_do_valor": "referencia_externa_por_analogia",
                                            "referencia": "x", "hipotese_declarada": "x", "grau_de_incerteza": "alto"}])], ignore_index=True)
    with pytest.raises(ValueError):
        motor.faixas_por_pacote(M1, m2_ruim)                                                  # um cenário não pode redefinir uma classe do Método 1


def test_gardens_always_use_the_envelope_of_the_fraction_scenarios_never_a_central_value():
    f = motor.faixas_por_pacote(M1, M2)["referencia_analoga"][motor.CLASSE_JARDINS]
    fr = M2[M2.cenario.str.startswith("referencia_analoga_jardins_f")]
    assert f == (float(fr.c_min.min()), float(fr.c_max.max())) == (0.225, 0.8)
    assert f[0] < float(fr[fr.cenario.str.endswith("f50")].c_min.iloc[0]) and f[1] > float(fr[fr.cenario.str.endswith("f50")].c_max.iloc[0])    # nem o cenário do meio
    assert motor.CLASSE_JARDINS not in motor.faixas_por_pacote(M1, M2)["metodo1"]


def test_coverage_fractions_partition_the_upstream_area_and_show_the_uncovered_part():
    r = rodar()
    b = r["base"]
    soma = b.fracao_montante_coberta_m1 + b.fracao_montante_com_valor_analoga + b.fracao_montante_sem_valor_analoga + b.fracao_montante_fora_do_calculo + b.fracao_montante_sem_classe
    assert np.allclose(soma, 1.0)
    assert np.allclose(b.fracao_montante_coberta_m1, 300 / 900) and np.allclose(b.fracao_montante_com_valor_analoga, 600 / 900) and np.allclose(b.fracao_montante_sem_valor_analoga, 0.0)


def test_classes_without_any_value_in_a_package_are_reported_as_uncovered_not_filled():
    celulas = celulas_padrao().assign(**{"area_m2__03": 100.0, "area_m2__04": 50.0})
    celulas["area_m2__02"] = 450.0
    celulas["area_m2__01"] = 300.0                                                             # 300 + 450 + 100 + 50 = 900
    classes = {**CLASSES, "Vegetação Nativa": 3, "Corpo Hídrico": 4}
    r = motor.executar(dem_inclinado(), GRADE, celulas, classes, M1, M2, trechos((*centro(3, 2), *centro(3, 6))))
    b = r["base"].iloc[0]
    assert b.fracao_montante_sem_valor_analoga == pytest.approx(100 / 900)                       # Vegetação Nativa não tem valor por analogia: lacuna
    assert b.fracao_montante_fora_do_calculo == pytest.approx(50 / 900)                          # Corpo Hídrico fica fora do cálculo
    assert b.local_aeq_limites_max_m2 == pytest.approx(5 * (450 + 100))                          # os limites físicos cobrem a Vegetação Nativa (C = 1) e não o corpo hídrico


# ---------------------------------------------------------------- indicador topográfico e exutórios
def test_the_topographic_indicator_is_the_fill_height_and_is_not_called_volume_or_depth():
    dem = dem_inclinado()
    dem[3, 5] -= 4.0                                                                           # poço de 91 m cercado por 96 m (oeste) e 94 m (leste, a saída): o preenchimento sobe 3 m
    r = rodar(dem=dem, segs=[(*centro(3, 4), *centro(3, 6)), (*centro(8, 1), *centro(8, 3))])
    n1 = r["nivel1"]
    assert n1.altura_de_preenchimento_max_m.iloc[0] == pytest.approx(3.0, abs=1e-3) and n1.altura_de_preenchimento_max_m.iloc[1] < 0.01        # o segundo trecho está em encosta lisa
    assert n1.propensao_topografica_percentil.iloc[0] > n1.propensao_topografica_percentil.iloc[1]
    assert not [c for c in list(n1.columns) + list(r["nivel2"].columns) + list(r["base"].columns) if any(p in c.lower() for p in motor.PROIBIDAS_NAS_SAIDAS)]


def test_masked_water_cells_are_outlets_and_do_not_become_a_flooded_bowl():
    dem = dem_inclinado()
    dem[:, 7:] = 10.0                                                                          # "lago" baixo e plano na borda leste
    sem = rodar(dem=dem, segs=[(*centro(3, 5), *centro(3, 6))])
    mascara = np.zeros(dem.shape, bool)
    mascara[:, 7:] = True
    com = rodar(dem=dem, segs=[(*centro(3, 5), *centro(3, 6))], mascara_exutorio=mascara)
    assert com["relatorio"]["celulas_mascaradas_como_exutorio"] == 30
    assert com["nivel1"].altura_de_preenchimento_max_m.iloc[0] <= sem["nivel1"].altura_de_preenchimento_max_m.iloc[0]
    assert com["relatorio"]["conservacao_de_massa"]["erro_relativo_maximo"] < 1e-12


def test_conservation_and_determinism_hold_for_the_whole_run():
    a, b = rodar(), rodar()
    assert a["relatorio"]["conservacao_de_massa"]["erro_relativo_maximo"] < 1e-12
    pd.testing.assert_frame_equal(a["base"], b["base"])
    pd.testing.assert_frame_equal(a["nivel2"], b["nivel2"])
    pd.testing.assert_frame_equal(a["celulas"], b["celulas"])
    tot = a["relatorio"]["totais_da_cidade_soma_das_celulas_m3"]["30"]["metodo1"]
    assert tot["min_m3"] == pytest.approx(30 * 100 * AEQ_M1_MIN / 1000) and tot["max_m3"] == pytest.approx(30 * 100 * AEQ_M1_MAX / 1000)


def test_a_segment_outside_the_data_gets_missing_values_not_zeros():
    r = rodar(segs=[(-900.0, -900.0, -800.0, -800.0), (*centro(3, 2), *centro(3, 6))])
    assert r["base"].n_celulas_com_dados.tolist() == [0, 5]
    assert r["base"].iloc[0][["contrib_aeq_m1_max_m2", "local_aeq_m1_max_m2"]].isna().all() and r["nivel1"].altura_de_preenchimento_max_m.iloc[0] != 0
    assert np.isnan(r["nivel1"].altura_de_preenchimento_max_m.iloc[0])
    assert r["relatorio"]["trechos_com_pegada_valida"] == 1


def test_inputs_are_validated():
    with pytest.raises(ValueError):
        motor.executar(np.zeros((5, 5)), GRADE, celulas_padrao(), CLASSES, M1, M2, trechos((0, 0, 1, 1)))          # DEM com formato diferente da grade
    with pytest.raises(ValueError):
        fluxo.ArvoreDeFluxo(*fluxo.receptores_d8(sus.fill_depressions(dem_inclinado()))).acumular(np.ones(7))


# ---------------------------------------------------------------- executor: funções de apoio e integridade dos arquivos reais
def test_water_cells_become_outlets_only_where_the_land_use_layer_leaves_them_unclassified():
    import executar_fase3 as ex
    celulas = pd.DataFrame({"linha": [1, 2, 3], "coluna": [1, 2, 3], "x_centro": [45.0, 75.0, 105.0], "y_centro": [255.0, 225.0, 195.0], "area_lacuna_m2": [900.0, 449.0, 450.0]})
    m = ex.mascara_de_agua(celulas, GRADE, {"lacuna_minima_m2": 450, "exigir_agua_osm": False})
    assert m.sum() == 2 and m[1, 1] and m[3, 3] and not m[2, 2]                                  # 449 m² sem classe ainda é terra; 450 m² já é água


def test_segment_coordinates_are_projected_to_the_metric_grid_crs():
    import executar_fase3 as ex
    from pyproj import Transformer
    rede = pd.DataFrame({"segmento_id": ["a"], "lon0": [-51.2], "lat0": [-30.0], "lon1": [-51.199], "lat1": [-30.001]})
    t = ex.trechos_em_utm(rede)
    x, y = Transformer.from_crs(4326, 31982, always_xy=True).transform(-51.2, -30.0)
    assert t.x0.iloc[0] == pytest.approx(x) and t.y0.iloc[0] == pytest.approx(y) and 80 < np.hypot(t.x1 - t.x0, t.y1 - t.y0).iloc[0] < 180


PROC = RAIZ / "data/processed/fase3"


@pytest.mark.skipif(not (PROC / "relatorio_execucao.json").exists(), reason="Fase 3 ainda não executada (data/processed fica fora do Git)")
def test_real_outputs_are_consistent_conserve_mass_and_promise_nothing_beyond_the_method():
    rel = json.loads((PROC / "relatorio_execucao.json").read_text())
    assert rel["verificacoes_do_nucleo"]["acumulo_com_peso_1_identico_a_susceptibility_flow_accumulation"] is True
    assert rel["verificacoes_do_nucleo"]["conservacao_de_massa_erro_relativo_maximo"] < 1e-9
    base, n1, n2 = (pd.read_parquet(PROC / f"{n}.parquet") for n in ("trechos_contribuicao_base", "trechos_nivel1_propensao_topografica", "trechos_nivel2_cenarios"))
    assert len(base) == len(n1) == rel["motor"]["trechos"] and (base.segmento_id == n1.segmento_id).all() and base.segmento_id.is_unique
    for tab in (base, n1, n2, pd.read_parquet(PROC / "celulas_30m.parquet")):
        assert not [c for c in tab.columns if any(p in c.lower() for p in motor.PROIBIDAS_NAS_SAIDAS + ("transportado",))]
    ok = base.n_celulas_com_dados > 0
    soma = (base.fracao_montante_coberta_m1 + base.fracao_montante_com_valor_analoga + base.fracao_montante_sem_valor_analoga + base.fracao_montante_fora_do_calculo + base.fracao_montante_sem_classe)[ok]
    assert np.allclose(soma, 1.0, atol=1e-9)                                                     # a cobertura a montante particiona a área
    for rot in ("m1", "limites", "analoga"):
        assert (base[f"local_aeq_{rot}_min_m2"][ok] <= base[f"local_aeq_{rot}_max_m2"][ok] + 1e-9).all() and (base[f"contrib_aeq_{rot}_min_m2"][ok] <= base[f"contrib_aeq_{rot}_max_m2"][ok] + 1e-9).all()
        assert (base[f"contrib_aeq_{rot}_max_m2"][ok] >= base[f"local_aeq_{rot}_max_m2"][ok] - 1e-6).all()      # a contribuição inclui o volume local
    assert base.loc[~ok, [c for c in base.columns if c.startswith(("local_", "contrib_"))]].isna().all().all()    # sem dados: ausente, nunca zero
    # o volume é exatamente P x aeq / 1000 (linearidade em P e unidades)
    um = n2[(n2.p_mm == 30) & (n2.pacote == "metodo1")].set_index("segmento_id")
    esperado = 30 * base.set_index("segmento_id")["contrib_aeq_m1_max_m2"] / 1000
    assert np.allclose(um["contrib_potencial_max_m3"].reindex(esperado.index), esperado, equal_nan=True)
    assert set(n2.p_mm) == {10.0, 20.0, 30.0} and set(n2.pacote) == set(motor.PACOTES) and len(n2) == len(base) * 9
    # os pacotes não se somam: nenhuma coluna total entre Método 1 e cenários
    assert not [c for c in n2.columns if "total" in c or "soma" in c]
    assert rel["motor"]["nao_calculado"]["volume_efetivamente_transportado"].startswith("não calculado")
    cel = pd.read_parquet(PROC / "celulas_30m.parquet")
    assert (cel["altura_de_preenchimento_m"] >= -1e-9).all() and cel[["linha", "coluna"]].duplicated().sum() == 0
    ult = {s["path"]: s for s in json.loads((RAIZ / "data/raw/manifest.json").read_text())["sources"]}
    for nome, a in rel["arquivos"].items():
        assert ult[a["path"]]["sha256"] == a["sha256"]                                           # registrado no manifesto com o hash do arquivo


@pytest.mark.skipif(not (PROC / "relatorio_execucao.json").exists() or not (RAIZ / "reports/qa/fase3_execucao.json").exists(), reason="Fase 3 ainda não executada")
def test_the_results_report_is_generated_from_the_json_and_states_what_is_not_calculated():
    import gerar_relatorio_fase3 as g
    texto = g.gerar()
    for secao in ("Verificações do núcleo", "Trechos viários", "Total da cidade", "Indicador topográfico", "Comparação exploratória", "Não calculado", "Limitações"):
        assert secao in texto, secao
    assert "nan" not in texto.lower().replace("finan", "").replace("nancy", "") and "não são somáveis" in texto
    assert "efetivamente transportado" in texto and "limite superior" in texto
