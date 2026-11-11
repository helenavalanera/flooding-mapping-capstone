"""Sensitivity of the street-risk baseline to controlled changes of its inputs.

They check that the implementation is coherent (monotonic where it should be, bounded, no invented zeros). They are not an
empirical validation: that is what ``auditoria_risco`` confronts with documented events, and it shows a low sensitivity.
"""

import numpy as np
import pandas as pd
import pytest
from rede_sintetica import LAT0, LON0, PR, chuva, rede, sem_risco, tabela, tres_caminhos

from flooding_mapping import risco_trecho as rt
from flooding_mapping.rotas import Analise

T = lambda s: pd.Timestamp(f"2026-11-09 {s}")  # noqa: E731


def fator(serie, hora):
    return rt.tabela_de_chuva(serie, PR).loc[T(hora), "fator"]


def test_without_rain_the_factor_is_zero_everywhere_and_no_street_is_flagged():
    t = rt.tabela_de_chuva(chuva(mm_h=0), PR).dropna(subset=["fator"])
    assert (t["fator"] == 0).all()
    assert set(rt.classe(np.array([0.0, 0.0]), PR)) == {"baixo"}


def test_a_rain_in_the_past_and_the_same_rain_in_the_future_weigh_the_same():
    s = chuva("2026-11-09 12:00", 15.0, 3)
    assert fator(s, "13:00") == fator(s, "13:00")                           # the baseline reads hours, not their origin...
    assert rt.natureza(T("13:00"), T("14:00")) == "observado" and rt.natureza(T("13:00"), T("12:00")) == "previsto"   # ...and the label says which one it is


def test_the_factor_never_decreases_when_the_rain_gets_more_intense_and_stays_in_zero_one():
    anteriores = -1.0
    for mm in np.arange(0, 80, 2.5):
        f = fator(chuva("2026-11-09 12:00", float(mm), 3), "14:00")
        assert 0 <= f <= 1 and f >= anteriores
        anteriores = f
    assert fator(chuva("2026-11-09 12:00", 60.0, 3), "14:00") == 1.0


def test_the_same_total_is_worse_when_it_falls_in_one_hour_than_when_it_is_spread_out():
    rajada = chuva("2026-11-09 12:00", 30.0, 1)                              # 30 mm in 1 h
    espalhada = chuva("2026-11-09 12:00", 5.0, 6)                            # 30 mm in 6 h
    pico = lambda serie: rt.tabela_de_chuva(serie, PR)["fator"].max()        # each scenario at its worst hour
    assert pico(rajada) > pico(espalhada) and pico(rajada) == 1.0


def test_a_longer_dry_spell_lowers_the_factor_until_it_reaches_zero():
    s = chuva("2026-11-09 12:00", 20.0, 2)
    seq = [fator(s, h) for h in ("13:00", "14:00", "16:00", "18:00", "19:00", "22:00")]
    assert all(a >= b for a, b in zip(seq, seq[1:])) and seq[-1] == 0.0


def test_wet_antecedent_conditions_never_lower_the_factor():
    seca = chuva("2026-11-09 12:00", 10.0, 1)
    molhada = chuva("2026-11-09 12:00", 10.0, 1)
    molhada[T("2026-11-06 06:00").strftime("%Y-%m-%d %H:%M"):"2026-11-08 06:00"] = 1.0
    assert fator(molhada, "12:00") >= fator(seca, "12:00")


def test_a_more_susceptible_street_never_scores_lower_and_below_the_cutoff_it_scores_zero():
    pct = np.linspace(0, 100, 101)
    peso = np.clip((pct - PR["corte_fisico"]) / (100 - PR["corte_fisico"]), 0, 1)
    assert (np.diff(peso) >= 0).all() and (peso[pct <= PR["corte_fisico"]] == 0).all() and peso[-1] == 1
    escores = 0.8 * peso
    assert (np.diff(escores) >= 0).all() and (rt.classe(escores[pct <= PR["corte_fisico"]], PR) == "baixo").all()


def test_a_street_without_terrain_data_is_never_scored_zero():
    r = rede(tres_caminhos())
    pct = np.array(r.pct, copy=True)
    pct[0] = np.nan
    peso = rt.pesos(pct, r, [], PR)["peso"]
    assert np.isnan(peso[0]) and rt.classe(0.8 * peso, PR)[0] is None


def test_raising_a_cutoff_flags_less_of_the_network_never_more():
    pct = np.linspace(0, 100, 5001)
    def marcado(corte, atencao):
        peso = np.clip((pct - corte) / (100 - corte), 0, 1)
        return (peso >= atencao).mean()
    assert marcado(90, 0.25) <= marcado(85, 0.25) <= marcado(70, 0.25) <= marcado(0, 0.25)
    assert marcado(85, 0.5) <= marcado(85, 0.25) <= marcado(85, 0.1)


def test_a_longer_recession_keeps_the_factor_high_for_longer_never_lower():
    s = chuva("2026-11-09 12:00", 20.0, 2)
    curto = rt.tabela_de_chuva(s, {**PR, "recuo_h": 3}).loc[T("16:00"), "fator"]
    longo = rt.tabela_de_chuva(s, {**PR, "recuo_h": 12}).loc[T("16:00"), "fator"]
    assert longo >= curto


def test_the_same_street_is_exposed_during_the_storm_and_not_after_it():
    r = rede(tres_caminhos())
    def exposicao(saida):
        a = Analise(r, "carro", (LON0, LAT0), (LON0 + 0.03, LAT0), pd.Timestamp(saida), tabela(), sem_risco(r), np.zeros(r.n, bool), T("08:00"))
        return a.caminho(0.0)["exposicao_km_risco"]
    assert exposicao("2026-11-09 11:55") > 0 and exposicao("2026-11-09 13:00") > 0 and exposicao("2026-11-09 23:00") == 0 == exposicao("2026-11-09 05:00")


def test_the_forecast_path_without_rain_data_has_no_class_at_all_and_no_zero():
    sem = pd.DataFrame({"fator": np.nan}, index=pd.date_range("2026-11-09", periods=48, freq="h"))
    assert np.isnan(rt.fator_em(sem, T("12:00")))
    assert rt.classe(np.array([np.nan]), PR)[0] is None
