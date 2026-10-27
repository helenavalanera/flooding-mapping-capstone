import numpy as np
import pandas as pd

from flooding_mapping.clustering import features, typology


def test_features_use_max_loss_and_skip_invalid_origins():
    baseline = pd.DataFrame({
        "origin_id": ["a", "a", "b", "b", "c", "c"],
        "mode": ["walk", "car"] * 3,
        "n_destinations": [4, 100, 0, 50, None, None],
        "status": ["ok"] * 4 + ["not_linked"] * 2,
    })
    losses = pd.DataFrame({
        "origin_id": ["a", "a", "a", "b"], "mode": ["walk", "walk", "car", "walk"],
        "P": [0.25, 0.5, 0.1, np.nan],
    })
    table = features(baseline, losses)
    assert list(table.index) == ["a", "b"]
    assert table.loc["a", "P_max_walk"] == 0.5
    assert table.loc["b", "P_max_walk"] == 0          # A0 = 0: nothing to lose
    assert table.loc["b", "P_max_car"] == 0           # no scenario loss recorded
    assert table.loc["a", "log_A0_car"] == np.log1p(100)


def test_typology_is_reproducible_and_separates_groups():
    rng = np.random.default_rng(0)
    low = rng.normal(0, 0.1, size=(20, 2))
    high = rng.normal(5, 0.1, size=(20, 2))
    table = pd.DataFrame(np.vstack([low, high]), columns=["log_A0_car", "P_max_car"])
    first, info = typology(table, seed=1)
    second, _ = typology(table, seed=1)
    assert info["k"] == 2
    assert first["cluster"].tolist() == second["cluster"].tolist()
    assert (first["cluster"].iloc[:20] == 0).all() and (first["cluster"].iloc[20:] == 1).all()
