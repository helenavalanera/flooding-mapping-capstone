import numpy as np
import pandas as pd
import pytest

from flooding_mapping.metrics import losses, relative_loss


def test_perda_relativa_sem_base():
    a0 = pd.Series([0, 4, 10])
    a_s = pd.Series([0, 2, 5])
    p = relative_loss(a0, a_s)
    assert np.isnan(p.iloc[0])
    assert p.iloc[1] == 0.5
    assert p.iloc[2] == 0.5


def run(values, statuses=None, scenario=None):
    frame = pd.DataFrame({"origin_id": ["a", "b", "c", "d"], "mode": "walk",
                          "reachable_weight": values, "status": statuses or ["ok"] * 4})
    if scenario:
        frame["scenario_id"] = scenario
    return frame


def test_losses_absolute_relative_and_invalid_origins():
    baseline = run([10.0, 0.0, 5.0, np.nan], ["ok", "ok", "ok", "not_linked"])
    scenario = run([6.0, 0.0, 5.0, np.nan], ["ok", "ok", "ok", "not_linked"], scenario="S1")
    table = losses(baseline, scenario).set_index("origin_id")
    assert table.loc["a", "L"] == 4 and table.loc["a", "P"] == pytest.approx(0.4)
    assert table.loc["b", "L"] == 0 and np.isnan(table.loc["b", "P"])   # A0 = 0
    assert table.loc["c", "L"] == 0 and table.loc["c", "P"] == 0
    assert pd.isna(table.loc["d", "L"])                                  # not linked


def test_losses_reject_duplicated_keys():
    baseline = run([1.0] * 4)
    scenario = pd.concat([run([1.0] * 4, scenario="S1")] * 2)
    with pytest.raises(pd.errors.MergeError):
        losses(baseline, scenario)
