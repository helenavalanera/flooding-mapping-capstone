"""Indicator calculation and aggregation."""

import pandas as pd


def proportion_true(frame: pd.DataFrame, column: str) -> float:
    """Return the proportion of truthy values in a column."""
    if frame.empty:
        raise ValueError("Cannot calculate an indicator from an empty frame")
    if column not in frame:
        raise ValueError(f"Missing indicator column: {column}")
    return float(frame[column].mean())

