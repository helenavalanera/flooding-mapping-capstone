"""Unsupervised typology of origins by baseline mobility and rain-scenario loss.

Descriptive only: k-means groups origins with similar access (A0) and
maximum relative loss across simulated scenarios. It does not predict
flooding or interdictions.
"""

import argparse
import json

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .config import load_config, resolve


def features(baseline: pd.DataFrame, losses: pd.DataFrame) -> pd.DataFrame:
    """One row per origin with valid values in every mode.

    Columns: ``log_A0_<mode>`` = log(1 + A0) and ``P_max_<mode>`` = maximum
    relative loss over scenarios (0 when A0 = 0, since nothing can be lost;
    negative values — small gains from R5 stop relinking — count as 0).
    """
    valid = baseline[baseline["status"] == "ok"]
    a0 = valid.pivot(index="origin_id", columns="mode", values="reachable_weight").astype(float)
    p = losses.assign(P=losses["P"].fillna(0).clip(lower=0)).groupby(["origin_id", "mode"])["P"].max()
    p_max = p.unstack("mode").reindex(index=a0.index, columns=a0.columns).fillna(0)
    table = pd.concat([np.log1p(a0).add_prefix("log_A0_"), p_max.add_prefix("P_max_")], axis=1)
    return table.dropna()


def choose_k(x: np.ndarray, k_values: range, seed: int,
             min_cluster_share: float = 0.02) -> tuple[int, dict]:
    """k with the highest silhouette among solutions whose smallest cluster
    holds at least ``min_cluster_share`` of the points (ties: smaller k).

    The size rule keeps typologies substantive instead of isolating outliers.
    """
    scores = {}
    for k in k_values:
        if k >= len(x):
            break
        labels = KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(x)
        if np.bincount(labels).min() < min_cluster_share * len(x):
            continue
        scores[k] = float(silhouette_score(x, labels))
    if not scores:
        raise ValueError("Not enough origins to cluster")
    best = max(scores, key=lambda k: (scores[k], -k))
    return best, scores


def typology(table: pd.DataFrame, seed: int, k_values: range = range(2, 7)) -> tuple[pd.DataFrame, dict]:
    """Cluster labels (ordered by mean car access, 0 = lowest) and diagnostics."""
    x = StandardScaler().fit_transform(table.to_numpy())
    k, scores = choose_k(x, k_values, seed)
    labels = KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(x)
    result = table.assign(cluster=labels)
    order = result.groupby("cluster")[table.columns[0]].mean().sort_values().index
    result["cluster"] = result["cluster"].map({old: new for new, old in enumerate(order)})
    return result, {"k": k, "silhouette": scores, "seed": seed}


def main() -> None:
    argparse.ArgumentParser(description="Tipologia k-means das origens").parse_args()
    config = load_config()
    tables = resolve(config["paths"]["tables"])
    baseline = pd.read_parquet(tables / "mobility_baseline.parquet")
    losses = pd.read_parquet(tables / "mobility_losses.parquet")
    table = features(baseline, losses)
    result, info = typology(table, config["robustness"]["semente"])
    origins = gpd.read_parquet(resolve(config["paths"]["processed"]) / "origins.parquet")
    result = result.join(origins.set_index("origin_id")["population"])
    result.reset_index().to_parquet(tables / "typology.parquet", index=False)
    profile = result.groupby("cluster").agg(
        origins=("population", "size"), population=("population", "sum"),
        **{c: (c, "mean") for c in table.columns})
    info["n_origins"] = len(result)
    info["profile"] = profile.round(3).reset_index().to_dict(orient="records")
    (resolve(config["paths"]["qa"]) / "typology_run.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=2, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
