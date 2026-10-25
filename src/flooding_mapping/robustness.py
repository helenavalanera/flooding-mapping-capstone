"""Robustness measures across scenarios."""

import pandas as pd


def weighted_mean(
    frame: pd.DataFrame, value_column: str, weight_column: str = "weight"
) -> float:
    """Calculate a weighted mean, rejecting an empty or zero-weight input."""
    if frame.empty:
        raise ValueError("Cannot calculate a weighted mean from an empty frame")
    weights = frame[weight_column]
    if weights.sum() == 0:
        raise ValueError("Scenario weights must not sum to zero")
    return float((frame[value_column] * weights).sum() / weights.sum())

