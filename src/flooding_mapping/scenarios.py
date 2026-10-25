"""Scenario loading and selection."""

from pathlib import Path

import pandas as pd

from .ingest import read_csv
from .validate import require_columns


def load_scenarios(path: str | Path) -> pd.DataFrame:
    """Load and validate the versioned scenario table."""
    scenarios = read_csv(path)
    require_columns(scenarios, ("scenario_id", "event_id", "weight"))
    return scenarios

