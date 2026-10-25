import pandas as pd
import pytest

from flooding_mapping.accessibility import classify_accessibility
from flooding_mapping.robustness import weighted_mean
from flooding_mapping.validate import require_columns


def test_classify_accessibility():
    result = classify_accessibility(
        pd.DataFrame({"travel_time_minutes": [10, 45]}), threshold_minutes=30
    )
    assert result["is_accessible"].tolist() == [True, False]


def test_weighted_mean():
    frame = pd.DataFrame({"value": [10, 20], "weight": [1, 3]})
    assert weighted_mean(frame, "value") == 17.5


def test_require_columns_reports_missing_columns():
    with pytest.raises(ValueError, match="Missing required columns"):
        require_columns(pd.DataFrame({"id": [1]}), ["id", "name"])

