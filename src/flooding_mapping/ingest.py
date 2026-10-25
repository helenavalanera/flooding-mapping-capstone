"""Input data ingestion helpers."""

from pathlib import Path

import pandas as pd


def read_csv(path: str | Path) -> pd.DataFrame:
    """Read a CSV file and fail clearly when it is unavailable."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"CSV input not found: {source}")
    return pd.read_csv(source)

