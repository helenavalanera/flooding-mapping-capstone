"""Preparation and normalization of analysis inputs."""

import pandas as pd


def drop_empty_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy without rows that contain no values."""
    return frame.dropna(how="all").reset_index(drop=True)

