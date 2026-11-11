import json

import joblib
import numpy as np
import pandas as pd

from flooding_mapping.models import gatilho as model

TOWNS = [f"43{i:05d}" for i in range(14)]


def synthetic_inputs(seed=7):
    """Rain with real storms; each storm opens an S2iD-style record where it hit hardest."""
    rng = np.random.default_rng(seed)
    days = pd.date_range("2017-01-01", "2026-10-31", freq="D")
    rain = rng.gamma(0.35, 9.0, size=(len(days), len(TOWNS)))
    records = []
    for day in rng.choice(np.arange(60, len(days) - 5), size=150, replace=False):
        hit = rng.choice(len(TOWNS), size=rng.integers(1, 5), replace=False)
        rain[day:day + 2, hit] += rng.uniform(70, 160, size=(2, len(hit)))
        records += [{"ibge": TOWNS[t], "data_evento": days[day + 1], "cobrade": 12200} for t in hit]
    records += [{"ibge": TOWNS[0], "data_evento": days[400], "cobrade": 14110}]  # drought: never a label
    long = pd.DataFrame({"ibge": np.tile(TOWNS, len(days)), "data": np.repeat(days, len(TOWNS)),
                         "precipitation_sum": rain.ravel()})
    long.attrs["grade"] = pd.DataFrame({"ibge": TOWNS, "altitude_m": np.linspace(5, 800, len(TOWNS))})
    towns = pd.DataFrame({"ibge": TOWNS, "nome": [f"Cidade {i}" for i in range(len(TOWNS))], "lat": np.linspace(-33, -28, len(TOWNS)), "lon": np.linspace(-56, -50, len(TOWNS)),
                          "area_km2": 300.0, "populacao": np.linspace(2000, 90000, len(TOWNS)),
                          "regiao_imediata": ["R1", "R2"] * (len(TOWNS) // 2)})
    return long, towns, pd.DataFrame(records), long.attrs["grade"]


def test_training_rows_keep_all_positives_and_a_fixed_ratio_of_negatives():
    y = np.r_[np.ones(10), np.zeros(5000)].astype(int)
    frame = pd.DataFrame({"y": y})
    rows = model.training_rows(frame, np.ones(len(y), bool))
    assert y[rows].sum() == 10 and (y[rows] == 0).sum() == 10 * model.NEG_PER_POS
    assert np.array_equal(rows, model.training_rows(frame, np.ones(len(y), bool)))  # seeded


def test_the_simplest_family_within_the_tolerance_is_chosen_and_the_margin_is_relative():
    tuned = pd.DataFrame([
        {"familia": "logistica", "parametros": {"C": 1}, "pr_auc": 0.30},
        {"familia": "hgb", "parametros": {"learning_rate": 0.1}, "pr_auc": 0.31},
        {"familia": "rf", "parametros": {"min_samples_leaf": 20}, "pr_auc": 0.32}])
    clear = model.choose(tuned, baseline_best=0.20)
    assert clear["familia"] == "logistica" and clear["passa_margem_validacao"]
    assert not model.choose(tuned, baseline_best=0.30)["passa_margem_validacao"]
    # the tolerance is relative: at a PR-AUC near 0.02 a gap of 0.002 is a 10% difference
    tiny = pd.DataFrame([{"familia": "logistica", "parametros": {}, "pr_auc": 0.010},
                         {"familia": "rf", "parametros": {}, "pr_auc": 0.020}])
    assert model.choose(tiny, baseline_best=0.005)["familia"] == "rf"


def years(model_wins):
    rows = []
    for year, wins in zip(range(2020, 2025), model_wins):
        rows.append({"ano": year, "pr_auc_modelo": 0.02 if wins else 0.005, "pr_auc_regra_p3d": 0.01,
                     "pr_auc_regra_rel_p3d": 0.01, "pr_auc_logistica_chuva": 0.01})
    return rows


def test_validated_needs_all_three_independent_checks_and_names_the_failures():
    decision = {"familia": "hgb", "parametros": {}, "pr_auc_val": 0.03, "melhor_baseline_pr_auc_val": 0.02, "passa_margem_validacao": True}
    ok = model.validation_gate(decision, years([1, 1, 1, 0, 0]), {"modelo": 0.40, "regra_p3d": 0.35, "logistica_chuva": 0.30})
    assert ok["estado"].startswith("validado") and "passa_margem_validacao" not in ok
    assert all(v["passa"] for v in ok["criterios"].values())
    lost_events = model.validation_gate(decision, years([1, 1, 1, 0, 0]), {"modelo": 0.30, "logistica_chuva": 0.35})
    assert lost_events["estado"].startswith("experimental") and "eventos detectados fora da amostra" in lost_events["estado"]
    few_years = model.validation_gate(decision, years([1, 0, 0, 0, 0]), {"modelo": 0.40, "logistica_chuva": 0.30})
    assert "anos da janela móvel vencidos" in few_years["estado"]
    weak = model.validation_gate({**decision, "passa_margem_validacao": False}, years([1] * 5), {"modelo": 0.4, "x": 0.1})
    assert weak["estado"].startswith("experimental") and not weak["criterios"]["margem_pr_auc_na_validacao"]["passa"]


def test_full_protocol_on_synthetic_storms(tmp_path, monkeypatch):
    monkeypatch.setattr(model, "load_inputs", lambda: synthetic_inputs())
    monkeypatch.setattr(model, "resolve", lambda rel: tmp_path / rel)
    # make "resolve('.')" usable for the relative path shown in the card
    monkeypatch.setattr(model, "NEG_PER_POS", 20)
    card = model.run("estrito", quick=True)

    data = card["dataset"]
    assert data["municipios"] == len(TOWNS) and data["positivos"] > 100
    assert card["vazamento_episodios_entre_particoes"] <= 2  # only boundary-straddling episodes
    parts = card["particoes"]
    assert parts["train"]["periodo"][1] < parts["val"]["periodo"][0] < parts["val"]["periodo"][1] < parts["test"]["periodo"][0]

    test = card["teste_2025_em_diante"]
    assert test["modelo"]["pr_auc"] > 3 * test["modelo"]["prevalencia"]       # real signal found
    assert test["modelo"]["pr_auc"] > test["baselines"]["prior"]["pr_auc"]
    budgets = test["orcamentos_de_alerta"]
    assert set(budgets["modelo"]) == {"alertas_0.5pct", "alertas_2pct", "alertas_5pct"}
    assert {"regra_p3d", "logistica_chuva"} <= set(budgets) and "prior" not in budgets
    assert budgets["modelo"]["alertas_5pct"]["recall_eventos"] >= 0.7  # strong synthetic storms are caught
    assert budgets["modelo"]["alertas_2pct"]["dias_alerta_por_mil"] < 60
    assert {"brier", "confiabilidade"} <= set(test["calibracao"])
    assert card["decisao"]["familia"] in model.GRID and card["estabilidade_temporal_janela_movel"]
    assert card["chuva_em_torno_dos_registros"]["registros"] > 100       # the EDA is stored with the card
    assert card["importancia_por_permutacao_pr_auc"][0]["variavel"]

    saved = json.loads((tmp_path / "reports/ml/gatilho_estrito.json").read_text())
    assert saved["artefato"]["versionado_no_git"] is False and len(saved["artefato"]["sha256"]) == 64
    artifact = joblib.load(next((tmp_path / "artifacts/models").rglob("modelo.joblib")))
    operational = card["gatilho_operacional"]
    assert artifact["tipo"] == operational["tipo"] and artifact["colunas"] == operational["colunas"]
    if operational["tipo"] == "modelo":
        assert artifact["colunas"] == card["selecao_de_variaveis"]["variaveis"] and card["decisao"]["estado"].startswith("validado")
    else:  # no model passed the gate: a calibrated rainfall rule runs, and the card says why
        assert operational["regra"] in model.RULES and card["decisao"]["estado"].startswith("experimental")
        assert operational["motivo"] == card["decisao"]["estado"] and "experimental" in operational["estado"]
    assert operational["desempenho_teste"]["orcamentos"]["alertas_2pct"]["eventos"] > 0
    assert {"ibge", "nome", "lat", "lon", "populacao", "regiao_imediata"} <= set(artifact["municipios"].columns)
    assert list(artifact["grade"].columns) == ["ibge", "altitude_m"]
    assert artifact["treinado_ate"] >= "2026-10-01" and set(artifact["limiares"]) == set(budgets["modelo"])
    sample = np.zeros((2, len(artifact["colunas"])), dtype="float32")
    probability = artifact["calibrador"].predict(artifact["modelo"].predict_proba(sample)[:, 1])
    assert ((0 <= probability) & (probability <= 1)).all()


def test_label_set_changes_what_counts_as_positive():
    assert set(model.LABELS["estrito"]) < set(model.LABELS["amplo"])


def test_a_rule_scorer_ranks_by_its_column_and_nothing_is_fitted():
    import numpy as np

    from flooding_mapping.models.rules import RuleScorer

    scorer = RuleScorer(1)
    probability = scorer.predict_proba(np.array([[9.0, 2.0], [1.0, 40.0], [5.0, 7.0]]))
    assert probability.shape == (3, 2) and probability[:, 1].tolist() == [2.0, 40.0, 7.0]
    assert np.argsort(-probability[:, 1]).tolist() == [1, 2, 0]


def test_the_monotone_trees_never_lower_the_risk_when_rain_rises():
    import numpy as np

    cols = ["p0", "p_3d", "lat"]
    rng = np.random.default_rng(0)
    X = np.column_stack([rng.gamma(0.4, 8, 4000), rng.gamma(0.5, 20, 4000), rng.uniform(-33, -28, 4000)]).astype("float32")
    y = (X[:, 1] + rng.normal(0, 25, 4000) > 60).astype(int)
    hgb = model.make_model("hgb", {"learning_rate": 0.1, "max_depth": 5, "min_samples_leaf": 20}, cols).fit(X, y)
    low, high = X.copy(), X.copy()
    high[:, 1] += 50                                  # the same municipality-days with 50 mm more rain in 3 days
    assert (hgb.predict_proba(high)[:, 1] >= hgb.predict_proba(low)[:, 1] - 1e-9).all()
