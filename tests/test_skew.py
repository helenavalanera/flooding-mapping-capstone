import numpy as np
import pandas as pd

import test_inference as ti
from flooding_mapping.evaluation import skew


def inputs():
    tw = ti.towns()
    grid = pd.DataFrame({"ibge": ti.TOWNS, "altitude_m": [10.0, 300.0, 700.0]})
    history = ti.series(pd.date_range("2024-01-01", periods=700), seed=11)
    art = ti.artifact(history, tw, grid)
    art["municipios"], art["grade"] = tw, grid
    return art, history


def labelled_from(series):
    """Rows labelled by a rule on the true rain: the signal the model has to find."""
    p3 = series.rolling(3).sum().stack().rename("p3").reset_index()
    p3.columns = ["data", "ibge", "p3"]
    p3["y"] = (p3["p3"] > p3["p3"].quantile(0.97)).astype(int)
    p3["excluido"] = False
    return p3[["ibge", "data", "y", "excluido"]].dropna()


def test_series_agreement_is_perfect_for_identical_series_and_degrades_with_noise():
    _, rain = inputs()
    same = skew.compare_series(rain, rain)
    assert same["erro_absoluto_medio_mm"] == 0 and same["correlacao"] == 1.0
    noisy = rain * np.random.default_rng(1).uniform(0.2, 2.0, rain.shape)
    worse = skew.compare_series(rain, noisy)
    assert worse["erro_absoluto_medio_mm"] > 0 and worse["correlacao"] < 1.0


def test_scoring_forecast_features_never_beats_perfect_forecast_and_is_never_better_than_noise_free():
    art, rain = inputs()
    labelled = labelled_from(rain)
    perfect = skew.evaluate(art, labelled, rain, {1: rain}, since="2024-03-01")
    noisy_rain = rain * np.random.default_rng(2).uniform(0.1, 2.5, rain.shape)
    noisy = skew.evaluate(art, labelled, rain, {1: noisy_rain}, since="2024-03-01")
    assert perfect["previsao_1d_antes"]["pr_auc"] == perfect["reanalise"]["pr_auc"]
    assert noisy["previsao_1d_antes"]["pr_auc"] < perfect["reanalise"]["pr_auc"]
    assert noisy["previsao_1d_antes"]["chuva"]["correlacao"] < 1


def test_the_reanalysis_is_also_reported_on_exactly_the_days_the_forecasts_cover():
    art, rain = inputs()
    labelled = labelled_from(rain)
    short = rain.loc["2025-01-01":]  # a forecast archive that starts later
    out = skew.evaluate(art, labelled, rain, {1: short}, since="2024-03-01")
    assert out["reanalise_nos_mesmos_dias"]["linhas"] == out["previsao_1d_antes"]["linhas"] < out["reanalise"]["linhas"]
