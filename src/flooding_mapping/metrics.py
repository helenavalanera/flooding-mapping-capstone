"""Mobility loss indicators: A0, A_s, absolute loss L and relative loss P."""

import pandas as pd

VALUE = "reachable_weight"  # population reachable within the time limit


def relative_loss(a0: pd.Series, a_s: pd.Series) -> pd.Series:
    """P = (A0 - A_s) / A0, missing (NaN) when A0 is 0 or missing."""
    a0 = a0.astype("Float64")
    a_s = a_s.astype("Float64")
    return ((a0 - a_s) / a0.where(a0 > 0)).astype(float)


def losses(baseline: pd.DataFrame, scenario: pd.DataFrame, value: str = VALUE) -> pd.DataFrame:
    """Per origin and mode: A0, A_s, L = A0 - A_s and P.

    Both tables come from accessibility runs (``origin_id``, ``mode``,
    ``value``, ``status``). Indicators are only computed where both runs have
    status ``ok``; elsewhere they are missing.
    """
    keys = ["origin_id", "mode"]
    merged = baseline[keys + [value, "status"]].merge(
        scenario[keys + ["scenario_id", value, "status"]],
        on=keys, suffixes=("_0", "_s"), validate="one_to_one",
    )
    valid = (merged["status_0"] == "ok") & (merged["status_s"] == "ok")
    merged["A0"] = merged[f"{value}_0"].where(valid).astype(float)
    merged["A_s"] = merged[f"{value}_s"].where(valid).astype(float)
    merged["L"] = merged["A0"] - merged["A_s"]
    merged["P"] = relative_loss(merged["A0"], merged["A_s"])
    return merged[["scenario_id", "origin_id", "mode", "A0", "A_s", "L", "P"]]


def mobility_lost(table: pd.DataFrame, population: pd.Series, local_share: float = 0.10) -> pd.DataFrame:
    """Per scenario and mode, from a ``losses`` table.

    ``mobility_lost`` = 1 - sum(pop * A_s) / sum(pop * A0): share of all
    person-to-person reach lost in the city. Local instability: largest P of
    any origin, and population of origins losing at least ``local_share``.
    """
    data = table.dropna(subset=["L"]).assign(pop=lambda f: f["origin_id"].map(population).fillna(0))
    rows = []
    for (scenario_id, mode), group in data.groupby(["scenario_id", "mode"]):
        before, after = (group["pop"] * group["A0"]).sum(), (group["pop"] * group["A_s"]).sum()
        hit = group[group["L"] > 0]
        rows.append({
            "scenario_id": scenario_id, "mode": mode,
            "mobility_lost": 1 - after / before if before > 0 else float("nan"),
            "origins_with_loss": int(len(hit)),
            "population_with_loss": float(hit["pop"].sum()),
            "max_origin_loss": float(group["P"].max()) if group["P"].notna().any() else 0.0,
            "population_losing_10pct": float(group.loc[group["P"] >= local_share, "pop"].sum()),
        })
    return pd.DataFrame(rows)
