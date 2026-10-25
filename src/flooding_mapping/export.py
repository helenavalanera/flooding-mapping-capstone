"""Export helpers for analysis outputs."""

from pathlib import Path

import pandas as pd


def write_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    """Write a table, creating its parent directory when needed."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    return destination

