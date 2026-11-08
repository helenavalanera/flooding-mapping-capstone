"""Train / validation / test splits that keep episodes and time order intact.

The temporal split is the primary protocol: train up to 2022, validate on 2023-2024 (where the
biggest episodes are), test on 2025 onwards, which is touched once. The last ``PURGE_DAYS`` of
each earlier period are dropped so an episode that straddles a boundary cannot sit on both
sides. A rolling origin (train on the past, test on one year) shows how stable the result is
over time, and a spatial hold-out trains on four fifths of the municipalities and tests on the
rest, in the test period, so both place and time are unseen.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

TRAIN_END = pd.Timestamp("2022-12-31")
VAL_START, VAL_END = pd.Timestamp("2023-01-01"), pd.Timestamp("2024-12-31")
TEST_START = pd.Timestamp("2025-01-01")
PURGE_DAYS = 7
SPATIAL_BLOCKS = 5


def temporal(frame: pd.DataFrame, purge: int = PURGE_DAYS) -> dict[str, np.ndarray]:
    """Boolean masks ``train``, ``val`` and ``test`` (rows after a record are never used)."""
    day, usable = frame["data"], ~frame["excluido"].to_numpy()
    cut = pd.Timedelta(days=purge)
    return {"train": ((day <= TRAIN_END - cut) & usable).to_numpy(),
            "val": ((day >= VAL_START) & (day <= VAL_END - cut) & usable).to_numpy(),
            "test": ((day >= TEST_START) & usable).to_numpy()}


def rolling_origin(frame: pd.DataFrame, years: range, purge: int = PURGE_DAYS):
    """Yield (year, train mask, test mask): train on days before the year, test on the year."""
    day, usable = frame["data"], ~frame["excluido"].to_numpy()
    for year in years:
        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year, month=12, day=31)
        yield (year, ((day <= start - pd.Timedelta(days=purge + 1)) & usable).to_numpy(),
               ((day >= start) & (day <= end) & usable).to_numpy())


def spatial_blocks(towns: pd.DataFrame, k: int = SPATIAL_BLOCKS, seed: int = 20261108) -> pd.Series:
    """Contiguous regions: k-means on latitude and longitude (ibge -> block number)."""
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(towns[["lat", "lon"]])
    return pd.Series(km.labels_, index=towns["ibge"].to_numpy(), name="bloco")


def spatial_holdout(frame: pd.DataFrame, blocks: pd.Series, held_out: int, purge: int = PURGE_DAYS):
    """Train on other regions before 2023; test on the held-out region from 2025 on."""
    masks = temporal(frame, purge)
    in_block = frame["ibge"].map(blocks).eq(held_out).to_numpy()
    before = (frame["data"] <= TRAIN_END - pd.Timedelta(days=purge)).to_numpy()
    usable = ~frame["excluido"].to_numpy()
    return before & ~in_block & usable, masks["test"] & in_block
