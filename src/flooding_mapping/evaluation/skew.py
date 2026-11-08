"""How much the model loses when it is fed forecasts instead of the reanalysis it learned from.

The model is trained on reanalysis rainfall but used on forecasts. Open-Meteo archives real
forecasts (rain predicted ``lead`` days earlier) only from mid-2024, which covers the whole
test period, so the same tested model is scored twice on the same municipality-days: once
with the reanalysis features and once with features built from the forecast series. The
difference is the cost of the substitution; the agreement of the two rainfall series says
where it comes from. Forecast series use the forecast for every day of the window, which is
harsher than operation (where the past days are analysis), so the loss is an upper bound.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import weather as feat
from . import metrics

EVENT_MM = 30.0


def compare_series(reanalysis: pd.DataFrame, forecast: pd.DataFrame) -> dict:
    """Daily rainfall agreement over the days and municipalities both series have."""
    ibges = reanalysis.columns.intersection(forecast.columns)
    days = reanalysis.index.intersection(forecast.index)
    a = reanalysis.loc[days, ibges].to_numpy(float).ravel()
    b = forecast.loc[days, ibges].to_numpy(float).ravel()
    ok = ~np.isnan(a) & ~np.isnan(b)
    a, b = a[ok], b[ok]
    heavy_a, heavy_b = a >= EVENT_MM, b >= EVENT_MM
    return {"dias_x_municipios": int(ok.sum()), "vies_medio_mm": round(float((b - a).mean()), 3),
            "erro_absoluto_medio_mm": round(float(np.abs(b - a).mean()), 3),
            "correlacao": round(float(np.corrcoef(a, b)[0, 1]), 4),
            f"dias_ge_{EVENT_MM:g}mm_reanalise": int(heavy_a.sum()),
            f"acerto_dias_ge_{EVENT_MM:g}mm": round(float((heavy_a & heavy_b).sum() / max(heavy_a.sum(), 1)), 3),
            f"falso_alarme_dias_ge_{EVENT_MM:g}mm": round(float((~heavy_a & heavy_b).sum() / max(heavy_b.sum(), 1)), 3)}


def score(artifact: dict, series: pd.DataFrame) -> pd.DataFrame:
    """(ibge, data, score) for every day with a complete window."""
    frame = feat.build(series, artifact["municipios"], artifact["grade"], artifact["quantis"])
    raw = artifact["modelo"].predict_proba(frame[artifact["colunas"]].to_numpy("float32"))[:, 1]
    return pd.DataFrame({"ibge": frame["ibge"], "data": frame["data"], "score": raw})


def rescored_metrics(labelled: pd.DataFrame, scores: pd.DataFrame, thresholds: dict) -> dict:
    """Ranking and event recall of ``scores`` on the labelled rows they cover."""
    rows = labelled.merge(scores, on=["ibge", "data"], how="inner")
    rows = rows[~rows["excluido"]].reset_index(drop=True)
    result = {"linhas": len(rows), "positivos": int(rows["y"].sum()), **metrics.ranking(rows["y"].to_numpy(), rows["score"].to_numpy())}
    result["orcamentos"] = {name: {**metrics.at_threshold(rows["y"].to_numpy(), rows["score"].to_numpy(), t),
                                   **metrics.event_recall(rows, rows["score"].to_numpy(), t)}
                            for name, t in thresholds.items()}
    return result


def evaluate(artifact: dict, labelled: pd.DataFrame, reanalysis: pd.DataFrame,
             forecasts: dict[int, pd.DataFrame], since: str = "2025-01-01") -> dict:
    """Test-period metrics with reanalysis features and with each forecast lead."""
    labelled = labelled[labelled["data"] >= since][["ibge", "data", "y", "excluido"]]
    base = score(artifact, reanalysis)
    out = {"reanalise": rescored_metrics(labelled, base, artifact["limiares"])}
    covered = None
    for lead, series in forecasts.items():
        scored = score(artifact, series)
        keys = scored[["ibge", "data"]].merge(base[["ibge", "data"]], on=["ibge", "data"])
        covered = keys if covered is None else covered.merge(keys, on=["ibge", "data"])
        out[f"previsao_{lead}d_antes"] = {
            "chuva": compare_series(reanalysis.loc[series.index.intersection(reanalysis.index)], series),
            **rescored_metrics(labelled, scored, artifact["limiares"])}
    if covered is not None:  # the reanalysis row of the table above, on exactly the days every lead covers
        out["reanalise_nos_mesmos_dias"] = rescored_metrics(labelled, base.merge(covered, on=["ibge", "data"]), artifact["limiares"])
    return out


def main() -> None:
    import argparse
    import json
    from datetime import date, timedelta

    import joblib

    from ..config import resolve
    from ..ingestion import forecast as forecast_source
    from ..ingestion import weather as rain_source

    parser = argparse.ArgumentParser(description="Forecast-versus-reanalysis skew of the trigger model")
    parser.add_argument("--label", default="estrito")
    parser.add_argument("--leads", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--since", default="2025-01-01")
    args = parser.parse_args()
    path = next(resolve("artifacts/models").glob(f"gatilho-{args.label}-*/modelo_teste.joblib"))
    artifact = joblib.load(path)
    labelled = pd.read_parquet(resolve(f"data/processed/gatilho_{args.label}.parquet"), columns=["ibge", "data", "y", "excluido"])
    reanalysis = feat.wide(rain_source.load())
    start = date.fromisoformat(args.since) - timedelta(days=35)
    end = reanalysis.index.max().date()
    towns = artifact["municipios"]
    forecasts = {lead: forecast_source.archived(towns, start, end, lead, resolve("data/raw/weather/previous_runs"))
                 for lead in args.leads}
    result = {"modelo_testado_ate": artifact["treinado_ate"], "periodo": [args.since, str(end)],
              "nota": "chuva prevista com 'lead' dias de antecedência para todos os dias da janela (limite superior da perda)",
              **evaluate(artifact, labelled, reanalysis, forecasts, args.since)}
    out = resolve(f"reports/ml/skew_{args.label}.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n")
    for name, block in result.items():
        if isinstance(block, dict) and "pr_auc" in block:
            top = block["orcamentos"]["alertas_2pct"]
            print(f"{name:26} PR-AUC {block['pr_auc']:.4f}  ROC {block['roc_auc']:.3f}  eventos@2% {top['eventos_detectados']}/{top['eventos']}")


if __name__ == "__main__":
    main()
