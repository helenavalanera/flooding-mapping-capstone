import numpy as np
import pandas as pd

from flooding_mapping.accessibility import count_accessible

TIMES = pd.DataFrame({
    "from_id": ["a", "a", "a", "b", "b", "c"],
    "to_id": ["x", "y", "z", "x", "y", "x"],
    "travel_time": [10, 30, 31, np.nan, np.nan, 5],
})


def test_limit_is_inclusive_and_unreachable_counts_zero():
    result = count_accessible(TIMES, pd.Series(["a", "b"]), 30).set_index("origin_id")
    assert result.loc["a", "n_destinations"] == 2
    assert result.loc["b", "n_destinations"] == 0
    assert (result["status"] == "ok").all()


def test_missing_and_unlinked_origins_are_not_zero():
    result = count_accessible(TIMES, pd.Series(["a", "c", "d"]), 30, unlinked_ids=["c"])
    result = result.set_index("origin_id")
    assert result.loc["c", "status"] == "not_linked"
    assert pd.isna(result.loc["c", "n_destinations"])
    assert result.loc["d", "status"] == "missing"
    assert pd.isna(result.loc["d", "n_destinations"])
