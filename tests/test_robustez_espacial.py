"""Robustez da validação espacial (exploratório): tamanho do bloco, origem da grade e leave-one-block-out.

Os testes verificam o método (a grade deslocada particiona de verdade, os pontos de estabilidade sinalizam, a retirada de blocos contabiliza os positivos, um sinal plantado
sobrevive e um nulo não vira ganho) e que o relatório real é rastreável ao experimento principal. A tabela real (fora do Git) é necessária só no último teste.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flooding_mapping.risco_trecho import COMPONENTES

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import experimento_modelos_alagamentos as exp  # noqa: E402
import experimento_sensibilidade_hidrologica as sens  # noqa: E402
import robustez_espacial_validacao as rob  # noqa: E402
from test_experimento_sensibilidade import COORDS, MOTIVO_AUSENTE, REDE, grade  # noqa: E402


def _amostra(alvo, seed=1, n=90):
    g, coords = grade(alvo, n=n, seed=seed)
    return sens.preparar(g, coords, raio_m=50)


def test_shifted_grid_is_a_real_partition_and_a_full_block_shift_changes_nothing():
    g = grade("fisica", n=60)[0]
    base = rob.blocos_deslocados(g, 1500)
    assert np.array_equal(base, exp.blocos(g))                                             # no shift = the original blocks
    metade = rob.blocos_deslocados(g, 1500, 0.5, 0.5)
    assert not np.array_equal(pd.factorize(base)[0], pd.factorize(metade)[0])              # half a block really moves the borders
    assert np.array_equal(pd.factorize(base)[0], pd.factorize(rob.blocos_deslocados(g, 1500, 1.0, 1.0))[0])   # a whole block is the same partition
    assert len(base) == len(metade)


def test_stability_points_flag_too_few_blocks_a_dominant_block_and_a_low_effective_number():
    bom = {"blocos_com_positivo": 50, "participacao_do_maior_bloco": 0.10, "numero_efetivo_de_blocos": 30.0}
    assert rob.estabilidade(bom) == {"adequada": True, "limitacoes": []}
    ruim = rob.estabilidade({"blocos_com_positivo": 8, "participacao_do_maior_bloco": 0.6, "numero_efetivo_de_blocos": 2.1})
    assert not ruim["adequada"] and len(ruim["limitacoes"]) == 3


def test_leave_one_block_out_accounts_for_every_positive_exactly_once():
    d = _amostra("fisica")
    lobo = rob.leave_one_block_out(d, semente=7)
    total = int(d["y"].sum())
    assert sum(b["positivos_removidos"] for b in lobo["por_bloco"]) == total
    assert all(b["positivos_removidos"] + b["positivos_restantes"] == total for b in lobo["por_bloco"])
    assert [t["blocos_removidos"] for t in lobo["remocao_dos_k_maiores_blocos"]] == [1, 2, 3]
    assert lobo["maior_bloco"]["positivos"] == max(b["positivos_removidos"] for b in lobo["por_bloco"])


def test_a_planted_signal_survives_removing_any_block_and_a_null_never_reaches_the_margin():
    sinal = rob.leave_one_block_out(_amostra("fisica"), semente=7)["resumo_por_modelo"]["B"]
    assert sinal["ganho_minimo"] > sens.MARGEM and sinal["blocos_que_invertem_o_sinal_do_ganho"] == 0
    nulo = rob.leave_one_block_out(_amostra("aleatorio", seed=5), semente=7)["resumo_por_modelo"]
    assert all(v["blocos_com_ganho_acima_da_margem"] == 0 for v in nulo.values())


def test_configurations_cover_the_four_sizes_and_four_origins_without_choosing_one():
    d = _amostra("fisica")
    cfgs = rob.por_configuracao(d, semente=7, replicas=100)
    assert len(cfgs) == 16 and {c["lado_m"] for c in cfgs} == set(rob.LADOS_M) and sum(c["original"] for c in cfgs) == 1
    # unsupervised scores (A, B, D1) do not depend on how the space is cut: only their intervals do
    for k in ("B", "D1u", "D1e"):
        assert len({c["modelos"][k]["ganho_sobre_a_regra"] for c in cfgs}) == 1
    assert all("blocos_totais" in c and "estabilidade" in c for c in cfgs)


@pytest.mark.skipif(not REDE.exists() or not COORDS.exists(), reason="validação com dados reais: falta data/processed/rede_poa.parquet (fora do Git) ou " + MOTIVO_AUSENTE)
def test_real_report_is_traceable_to_the_main_experiment_and_conclusion_follows_the_numbers():
    coords = pd.read_csv(COORDS)
    rede = pd.read_parquet(REDE, columns=["lon0", "lat0", "lon1", "lat1", "percentil", "slope", "log_flow_acc", *COMPONENTES])
    r = rob.rodar(rede, coords, replicas=200)
    principal = sens.rodar(rede, coords, replicas=200)
    orig = next(c for c in r["configuracoes"] if c["original"])
    assert r["amostra"]["trechos"] == principal["amostra"]["trechos"] and r["amostra"]["trechos_rotulados"] == principal["amostra"]["trechos_rotulados"]
    assert orig["distribuicao_dos_positivos"] == principal["amostra"]["distribuicao_espacial_dos_positivos_bloco_1500m"]
    m = principal["modelos"]
    assert orig["modelos"]["B"]["ganho_sobre_a_regra"] == m["B_fluxo_ajustado_pela_declividade"]["ganho_sobre_a_referencia"]
    assert orig["modelos"]["D2u"]["precisao_media"] == m["D2_componentes_mais_fisica"]["por_cenario_de_C"]["uniforme_0,50"]["precisao_media"]    # mesmas dobras e semente
    assert orig["modelos"]["D1e"]["precisao_media"] == m["D1_media_de_postos_regra_e_fisica"]["por_cenario_de_C"]["espacial_0,30-0,95"]["precisao_media"]
    assert r["leave_one_block_out"]["com_todos_os_blocos"]["B"]["ganho"] == pytest.approx(orig["modelos"]["B"]["ganho_sobre_a_regra"], abs=1e-4)
    nenhum = all(v["configuracoes_que_atendem_o_criterio"] == 0 for v in r["resumo_das_configuracoes"]["por_modelo"].values()) and \
        all(v["blocos_com_ganho_acima_da_margem"] == 0 for v in r["leave_one_block_out"]["resumo_por_modelo"].values())
    assert r["conclusao"]["conclusao_depende_da_divisao_espacial"] == (not nenhum)
    assert sum(not c["estabilidade"]["adequada"] for c in r["configuracoes"]) == len([c for c in r["configuracoes"] if c["estabilidade"]["limitacoes"]])
