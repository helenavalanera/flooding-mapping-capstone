"""Configuration loading."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "analysis.yaml"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    """Read the analysis YAML configuration."""
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve(relative: str | Path) -> Path:
    """Resolve a repository-relative path."""
    return ROOT / relative
