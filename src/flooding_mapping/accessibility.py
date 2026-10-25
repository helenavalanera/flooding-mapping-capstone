"""Accessibility metrics for flood scenarios."""

import pandas as pd


def classify_accessibility(
    frame: pd.DataFrame,
    travel_time_column: str = "travel_time_minutes",
    threshold_minutes: float = 30,
) -> pd.DataFrame:
    """Add a boolean accessibility flag based on travel time."""
    if travel_time_column not in frame:
        raise ValueError(f"Missing travel-time column: {travel_time_column}")
    result = frame.copy()
    result["is_accessible"] = (
        result[travel_time_column] <= threshold_minutes
    )
    return result

