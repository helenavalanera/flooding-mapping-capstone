"""Rainfall and territorial features for the municipal trigger model.

Every rainfall feature of day ``d`` uses precipitation up to and including ``d`` and
nothing later, so the same function serves training (reanalysis) and operation (observed
past + forecast): at issue time the days after ``d`` simply do not exist yet. A window that
is not fully inside the series gives NaN rather than a partial sum.

Series are wide arrays (days x municipalities), the cheapest layout for rolling sums.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

RAIN_FEATURES = ["p0", "p_2d", "p_3d", "p_5d", "p_7d", "p_14d", "p_30d",
                 "ant_7d", "ant_30d", "max_7d", "wet_days_30d"]
SEASON_FEATURES = ["doy_sin", "doy_cos"]
TERRITORY_FEATURES = ["lat", "lon", "altitude_m", "log_area_km2", "log_populacao"]
RELATIVE_FEATURES = ["rel_p3d", "rel_p7d"]
REGIONAL_FEATURES = ["reg_p3d_mean", "reg_p3d_max", "reg_p7d_mean", "estado_frac_p3d_50"]
SEVERE_3D_MM = 50.0
WET_DAY_MM = 1.0


def wide(rain: pd.DataFrame, column: str = "precipitation_sum") -> pd.DataFrame:
    """Long (ibge, data, value) -> one row per day, one column per municipality, gap-free days."""
    table = rain.pivot(index="data", columns="ibge", values=column).sort_index()
    return table.reindex(pd.date_range(table.index.min(), table.index.max(), freq="D"))


def rolling_sum(values: np.ndarray, window: int, lag: int = 0) -> np.ndarray:
    """Sum of the ``window`` days ending ``lag`` days before each day; NaN until complete."""
    clean = np.nan_to_num(values, nan=0.0)
    missing = np.isnan(values).astype(np.int64)
    csum = np.vstack([np.zeros((1, values.shape[1])), np.cumsum(clean, axis=0)])
    cmiss = np.vstack([np.zeros((1, values.shape[1]), dtype=np.int64), np.cumsum(missing, axis=0)])
    out = np.full(values.shape, np.nan)
    n = len(values)
    for end in range(window + lag, n + 1):  # window covers days [end-window-lag, end-lag)
        stop, start = end - lag, end - lag - window
        total = csum[stop] - csum[start]
        total[(cmiss[stop] - cmiss[start]) > 0] = np.nan
        out[end - 1] = total
    return out


def rain_features(series: pd.DataFrame) -> dict[str, np.ndarray]:
    """Rainfall features per day and municipality, as arrays shaped like ``series``."""
    v = series.to_numpy(dtype=float)
    feats = {"p0": v.copy()}
    for days in (2, 3, 5, 7, 14, 30):
        feats[f"p_{days}d"] = rolling_sum(v, days)
    feats["ant_7d"] = rolling_sum(v, 7, lag=1)   # the 7 days *before* d
    feats["ant_30d"] = rolling_sum(v, 30, lag=1)
    peak = np.full(v.shape, np.nan)
    for end in range(7, len(v) + 1):
        window = v[end - 7:end]
        peak[end - 1] = np.where(np.isnan(window).any(axis=0), np.nan, window.max(axis=0))
    feats["max_7d"] = peak
    feats["wet_days_30d"] = rolling_sum(np.where(np.isnan(v), np.nan, (v >= WET_DAY_MM).astype(float)), 30)
    return feats


def seasonality(dates: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    angle = 2 * np.pi * (dates.dayofyear.to_numpy() - 1) / 365.25
    return {"doy_sin": np.sin(angle), "doy_cos": np.cos(angle)}


def local_quantiles(feats: dict[str, np.ndarray], dates: pd.DatetimeIndex, until: str,
                    q: float = 0.95) -> pd.DataFrame:
    """Per-municipality quantile of the 3- and 7-day totals over days up to ``until`` only.

    Uses rainfall alone (no labels), and only the past, so it can be fitted on the training
    period and applied to any later period or to municipalities unseen in training.
    """
    mask = dates <= pd.Timestamp(until)
    return pd.DataFrame({
        "q_p3d": np.nanquantile(feats["p_3d"][mask], q, axis=0),
        "q_p7d": np.nanquantile(feats["p_7d"][mask], q, axis=0)})


def relative_features(feats: dict[str, np.ndarray], quantiles: pd.DataFrame) -> dict[str, np.ndarray]:
    """Rainfall as a multiple of the municipality's own 95th-percentile total."""
    floor = 1.0  # mm; avoids dividing by ~0 in very dry series
    return {"rel_p3d": feats["p_3d"] / np.maximum(quantiles["q_p3d"].to_numpy(), floor),
            "rel_p7d": feats["p_7d"] / np.maximum(quantiles["q_p7d"].to_numpy(), floor)}


def regional_features(feats: dict[str, np.ndarray], columns: pd.Index, region_of: pd.Series) -> dict[str, np.ndarray]:
    """Rain around each municipality on the same day: its immediate region and the whole state.

    A flood that reaches many municipalities at once is a different event from a local storm,
    and the forecast covers every municipality at issue time, so this is not look-ahead.
    """
    codes = pd.factorize(region_of.reindex(columns))[0]
    p3, p7 = feats["p_3d"], feats["p_7d"]
    out = {name: np.full(p3.shape, np.nan) for name in REGIONAL_FEATURES[:3]}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN days at the start of a series
        for code in np.unique(codes[codes >= 0]):
            idx = np.flatnonzero(codes == code)
            out["reg_p3d_mean"][:, idx] = np.nanmean(p3[:, idx], axis=1, keepdims=True)
            out["reg_p3d_max"][:, idx] = np.nanmax(p3[:, idx], axis=1, keepdims=True)
            out["reg_p7d_mean"][:, idx] = np.nanmean(p7[:, idx], axis=1, keepdims=True)
        severe = np.where(np.isnan(p3), np.nan, (p3 >= SEVERE_3D_MM).astype(float))
        out["estado_frac_p3d_50"] = np.repeat(np.nanmean(severe, axis=1, keepdims=True), p3.shape[1], axis=1)
    return out


def territory(towns: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    """Static municipal attributes, indexed by ``ibge``."""
    table = towns.set_index("ibge")[["lat", "lon", "area_km2", "populacao"]].join(
        grid.set_index("ibge")[["altitude_m"]])
    table["log_area_km2"] = np.log(table["area_km2"])
    table["log_populacao"] = np.log1p(table["populacao"])
    return table[TERRITORY_FEATURES]


def fit_quantiles(series: pd.DataFrame, until: str) -> pd.DataFrame:
    """Local rainfall quantiles from the days up to ``until`` (indexed by ``ibge``)."""
    quantiles = local_quantiles(rain_features(series), series.index, until)
    return quantiles.set_axis(series.columns)


def build(series: pd.DataFrame, towns: pd.DataFrame, grid: pd.DataFrame,
          quantiles: pd.DataFrame) -> pd.DataFrame:
    """One row per (ibge, data) with every feature; rows with an incomplete window are dropped.

    ``quantiles`` come from :func:`fit_quantiles` and are stored with the model, so training
    and operation compare rainfall with the same local climatology.
    """
    feats = rain_features(series)
    feats.update(relative_features(feats, quantiles.reindex(series.columns)))
    days, ibges = series.index, series.columns
    feats.update(regional_features(feats, ibges, towns.set_index("ibge")["regiao_imediata"]))
    frame = pd.DataFrame({name: arr.ravel().astype("float32") for name, arr in feats.items()})
    frame.insert(0, "data", np.repeat(days.to_numpy(), len(ibges)))
    frame.insert(0, "ibge", np.tile(ibges.to_numpy(), len(days)))
    for name, arr in seasonality(days).items():
        frame[name] = np.repeat(arr, len(ibges)).astype("float32")
    static = territory(towns, grid).reindex(ibges)
    for name in TERRITORY_FEATURES:
        frame[name] = np.tile(static[name].to_numpy(dtype="float32"), len(days))
    return frame.dropna(subset=RAIN_FEATURES + RELATIVE_FEATURES + REGIONAL_FEATURES).reset_index(drop=True)
