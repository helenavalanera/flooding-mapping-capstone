import numpy as np
import pandas as pd

from flooding_mapping.evaluation import report


def frame(n=6000, seed=0):
    """Days of 10 municipalities; the model and the rule both see the same signal, on different scales."""
    rng = np.random.default_rng(seed)
    days = pd.date_range("2025-01-01", periods=n // 10)
    test = pd.DataFrame({"ibge": np.repeat([f"43{i:05d}" for i in range(10)], len(days)), "data": np.tile(days, 10)})
    signal = rng.gamma(0.5, 10, len(test))
    test["y"] = (signal + rng.normal(0, 4, len(test)) > np.quantile(signal, 0.985)).astype(int)
    test["score"] = signal / 1000                       # a model whose scores live on a tiny scale
    test["regra_p3d"] = signal * 5
    test["regra_rel_p3d"] = signal + rng.normal(0, 8, len(test))   # a noisier rule
    test["logistica_chuva"] = signal + rng.normal(0, 2, len(test))
    return test


def test_equal_share_comparison_does_not_depend_on_the_scale_of_the_scores():
    test = frame()
    base = report.equal_share_events(test)
    rescaled = test.assign(score=test["score"] * 1e-4 + 7.0)       # same ranking, wildly different scale
    assert report.equal_share_events(rescaled)["score"] == base["score"]


def test_equal_share_gives_each_scorer_the_same_number_of_alert_days_and_counts_events():
    test = frame()
    out = report.equal_share_events(test, budgets=(0.02,))
    assert set(out) == set(report.SCORERS) and out["score"][0.02]["eventos"] > 5
    top = test["score"] >= np.quantile(test["score"], 0.98)
    assert abs(top.mean() - 0.02) < 0.002                          # the 2% budget really is 2% of the days
    assert out["regra_p3d"][0.02]["detectados"] == out["score"][0.02]["detectados"]   # same ranking, same events
    assert out["regra_rel_p3d"][0.02]["detectados"] <= out["score"][0.02]["detectados"]  # a noisier rule catches no more


def test_the_comparison_sentence_states_both_periods_and_refuses_to_declare_a_winner():
    test = frame()
    card = {"eventos_oof_no_orcamento_do_portao": {"modelo": 0.48, "regra_p3d": 0.57, "regra_rel_p3d": 0.59, "logistica_chuva": 0.47}}
    text = report.comparison_sentence(card, report.equal_share_events(test, budgets=(0.02,)))
    assert "mesmo número de dias em alerta no teste (2%)" in text and "a ordem foi a inversa" in text
    assert "59%" in text and "48%" in text and "não permitem afirmar" in text


def test_budget_labels_and_number_formats_use_the_brazilian_convention():
    assert report.budget_label("alertas_0.5pct") == "0,5% dos dias" and report.budget_label("alertas_2pct") == "2% dos dias"
    assert report.num(0.00561) == "0,0056" and report.pct(0.0095, 2) == "0,95%" and report.thousands(1768598) == "1.768.598"


def test_the_operational_sentence_reports_the_real_alert_share_not_the_nominal_budget():
    card = {"gatilho_operacional": {"desempenho_teste": {"orcamentos": {"alertas_2pct": {
        "dias_alerta_por_mil": 17.1, "eventos_detectados": 43, "eventos": 111, "recall_eventos": 0.387, "precisao": 0.0095}}}}}
    text = report.operational_sentence(card)
    assert "1,7% dos dias-município" in text and "43 dos 111" in text and "39%" in text
