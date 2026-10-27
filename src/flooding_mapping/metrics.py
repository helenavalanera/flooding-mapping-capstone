"""Accessibility loss indicators."""

import pandas as pd


def relative_loss(a0: pd.Series, a_s: pd.Series) -> pd.Series:
    """P = (A0 - A_s) / A0, missing (NaN) when A0 is 0 or missing."""
    a0 = a0.astype("Float64")
    a_s = a_s.astype("Float64")
    return ((a0 - a_s) / a0.where(a0 > 0)).astype(float)


def losses(baseline: pd.DataFrame, scenario: pd.DataFrame) -> pd.DataFrame:
    """Per origin and mode: A0, A_s, L = A0 - A_s and P.

    Both tables come from accessibility runs (``origin_id``, ``mode``,
    ``n_destinations``, ``status``). Indicators are only computed where both
    runs have status ``ok``; elsewhere they are missing.
    """
    keys = ["origin_id", "mode"]
    merged = baseline[keys + ["n_destinations", "status"]].merge(
        scenario[keys + ["scenario_id", "n_destinations", "status"]],
        on=keys, suffixes=("_0", "_s"), validate="one_to_one",
    )
    valid = (merged["status_0"] == "ok") & (merged["status_s"] == "ok")
    merged["A0"] = merged["n_destinations_0"].where(valid).astype("Int64")
    merged["A_s"] = merged["n_destinations_s"].where(valid).astype("Int64")
    merged["L"] = merged["A0"] - merged["A_s"]
    merged["P"] = relative_loss(merged["A0"], merged["A_s"])
    return merged[["scenario_id", "origin_id", "mode", "A0", "A_s", "L", "P"]]


def summarize(table: pd.DataFrame, population: pd.Series | None = None) -> pd.DataFrame:
    """Per scenario and mode: origins with loss, total and maximum loss, mean P.

    ``population`` (indexed by origin_id) adds the population of origins with
    L > 0, an estimate under the uniform-density allocation.
    """
    data = table.copy()
    data["has_loss"] = data["L"] > 0
    grouped = data.groupby(["scenario_id", "mode"])
    summary = pd.DataFrame({
        "origins_valid": grouped["L"].count(),
        "origins_with_loss": grouped["has_loss"].sum(),
        "L_total": grouped["L"].sum(),
        "L_max": grouped["L"].max(),
        "P_mean_affected": data[data["has_loss"]].groupby(["scenario_id", "mode"])["P"].mean(),
    })
    if population is not None:
        data["population"] = data["origin_id"].map(population)
        summary["population_with_loss"] = (
            data[data["has_loss"]].groupby(["scenario_id", "mode"])["population"].sum())
    return summary.fillna({"origins_with_loss": 0}).reset_index()
