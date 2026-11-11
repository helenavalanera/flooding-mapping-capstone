"""Metrics for a rare-event alert: ranking quality, alert budgets, events and calibration.

Accuracy is meaningless at a prevalence under 1%, so the headline is PR-AUC (ROC-AUC only as a
complement), plus precision, recall and F1 at explicit thresholds, the confusion matrix, the
share of real *events* caught (a run of positive days counts once) and how many alert days a
municipality would see per year. Negatives are unlabelled days, so precision is a lower bound.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def ranking(y: np.ndarray, score: np.ndarray) -> dict:
    return {"pr_auc": round(float(average_precision_score(y, score)), 4),
            "roc_auc": round(float(roc_auc_score(y, score)), 4),
            "prevalencia": round(float(np.mean(y)), 5)}


def at_threshold(y: np.ndarray, score: np.ndarray, threshold: float) -> dict:
    alert = score >= threshold
    tp, fp = int((alert & (y == 1)).sum()), int((alert & (y == 0)).sum())
    fn, tn = int((~alert & (y == 1)).sum()), int((~alert & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"limiar": float(threshold), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precisao": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "dias_alerta_por_mil": round(1000 * float(alert.mean()), 2)}


BUDGETS = (0.005, 0.02, 0.05)


def budget_thresholds(score: np.ndarray, budgets: tuple[float, ...] = BUDGETS) -> dict[str, float]:
    """Thresholds that would alert on the given share of days (0.5%, 2% and 5% by default).

    An alert budget is how a civil-defence agency actually decides how much warning it can
    handle, and it puts a model and a simple rule on the same footing: each gets the same
    number of alert days and is judged by the events it catches with them.
    """
    return {f"alertas_{budget * 100:g}pct": float(np.quantile(score, 1 - budget)) for budget in budgets}


def positive_runs(frame: pd.DataFrame) -> pd.Series:
    """Run id for each positive day: consecutive positive days of one municipality are one event."""
    ordered = frame.sort_values(["ibge", "data"])
    positive = ordered["y"].to_numpy() == 1
    town = ordered["ibge"].to_numpy()
    day = ordered["data"].to_numpy().astype("datetime64[D]")
    continues = (np.r_[False, positive[:-1]] & np.r_[False, town[1:] == town[:-1]]
                 & np.r_[False, np.diff(day).astype(int) == 1])
    runs = np.where(positive, np.cumsum(positive & ~continues), -1)
    return pd.Series(runs, index=ordered.index).reindex(frame.index)


def event_recall(frame: pd.DataFrame, score: np.ndarray, threshold: float) -> dict:
    """Share of real events (runs of positive days) with at least one alert day inside."""
    runs = positive_runs(frame)
    inside = runs[runs >= 0]
    hit = pd.Series(score[runs.to_numpy() >= 0] >= threshold, index=inside.index).groupby(inside).any()
    return {"eventos": int(len(hit)), "eventos_detectados": int(hit.sum()),
            "recall_eventos": round(float(hit.mean()), 4) if len(hit) else None}


def calibration(y: np.ndarray, probability: np.ndarray, bins: int = 10) -> dict:
    """Brier score and a reliability table over quantile bins of the predicted probability."""
    edges = np.unique(np.quantile(probability, np.linspace(0, 1, bins + 1)))
    index = np.clip(np.digitize(probability, edges[1:-1]), 0, len(edges) - 2)
    table = pd.DataFrame({"p": probability, "y": y, "bin": index}).groupby("bin").agg(
        previsto=("p", "mean"), observado=("y", "mean"), n=("y", "size"))
    return {"brier": round(float(brier_score_loss(y, probability)), 6),
            "brier_referencia_prevalencia": round(float(brier_score_loss(y, np.full(len(y), y.mean()))), 6),
            "confiabilidade": table.round(5).reset_index(drop=True).to_dict("records")}
