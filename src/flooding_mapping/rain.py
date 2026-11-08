"""Rain at reported blockages (calibration of the alert thresholds).

Uses Open-Meteo's historical-forecast archive — the same model family the
dashboard reads live — at each geocoded event, in the 24 h before the hour of
the official report. Without rainy days *without* blockages, the result is a
lower bound (the least rain that has coincided with reported blockages), not a
probability.
"""

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

from .config import load_config, resolve

ARCHIVE = "https://historical-forecast-api.open-meteo.com/v1/forecast"
# Reanalysis archive (daily totals) used for how often each rain level happens.
REANALYSIS = "https://archive-api.open-meteo.com/v1/archive"
TIMEZONE = "America/Sao_Paulo"
# Hour of the official list each event comes from (see source_name in events.csv).
REPORT_HOUR = {"2025-06-18": 21, "2022-03-06": 17, "2021-09-08": 7, "2019-09-17": 18}
# A date whose modelled 24 h rain is below this, despite an official blockage
# report, is treated as a storm the model missed and left out of the thresholds.
MISSED_BELOW_24H_MM = 10


def fetch_hourly(lats: list[float], lons: list[float], start: str, end: str) -> list[pd.Series]:
    """Hourly precipitation (mm) per location from the archive."""
    query = urllib.parse.urlencode({
        "latitude": ",".join(f"{v:.4f}" for v in lats),
        "longitude": ",".join(f"{v:.4f}" for v in lons),
        "start_date": start, "end_date": end, "hourly": "precipitation", "timezone": TIMEZONE,
    })
    with urllib.request.urlopen(f"{ARCHIVE}?{query}", timeout=60) as response:
        payload = json.load(response)
    payload = payload if isinstance(payload, list) else [payload]
    return [pd.Series(item["hourly"]["precipitation"], index=pd.to_datetime(item["hourly"]["time"]),
                      dtype=float) for item in payload]


def window_stats(series: pd.Series, report: datetime) -> dict:
    """Max hourly rain and 24 h total in the 24 h up to the report hour."""
    window = series[(series.index > report - timedelta(hours=24)) & (series.index <= report)]
    if window.isna().all() or window.empty:
        return {"max_1h_mm": None, "total_24h_mm": None, "hours": int(window.notna().sum())}
    return {"max_1h_mm": round(float(window.max()), 1), "total_24h_mm": round(float(window.sum()), 1),
            "hours": int(window.notna().sum())}


def calibrate(events: pd.DataFrame) -> dict:
    """Rain statistics per geocoded event and lower-bound thresholds."""
    located = events.dropna(subset=["latitude", "longitude"])
    rows, queries = [], []
    for date, group in located.groupby("event_date"):
        report = datetime.fromisoformat(date) + timedelta(hours=REPORT_HOUR.get(date, 23))
        start = (report - timedelta(days=1)).date().isoformat()
        try:
            series = fetch_hourly(group["latitude"].tolist(), group["longitude"].tolist(),
                                  start, date)
        except Exception as error:  # archive may not cover older dates
            rows += [{"event_id": e, "event_date": date, "error": str(error)} for e in group["event_id"]]
            continue
        queries.append({"event_date": date, "start": start, "end": date, "points": len(group)})
        for event_id, values in zip(group["event_id"], series):
            rows.append({"event_id": event_id, "event_date": date,
                         "report_hour": report.hour, **window_stats(values, report)})
    table = pd.DataFrame(rows)
    valid = table.dropna(subset=["max_1h_mm"]) if "max_1h_mm" in table else table.iloc[0:0]
    per_date = valid.groupby("event_date").agg(max_1h_mm=("max_1h_mm", "max"),
                                               total_24h_mm=("total_24h_mm", "max"))
    per_date["captured"] = per_date["total_24h_mm"] >= MISSED_BELOW_24H_MM
    missed = per_date.index[~per_date["captured"]].tolist()
    per_date_all, per_date = per_date, per_date[per_date["captured"]]
    thresholds = {
        "medio_max_1h_mm": float(per_date["max_1h_mm"].min()) if len(per_date) else None,
        "medio_total_24h_mm": float(per_date["total_24h_mm"].min()) if len(per_date) else None,
        "alto_max_1h_mm": float(per_date["max_1h_mm"].median()) if len(per_date) else None,
        "alto_total_24h_mm": float(per_date["total_24h_mm"].median()) if len(per_date) else None,
    }
    return {
        "source": ARCHIVE, "timezone": TIMEZONE,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "queries": queries, "per_date": per_date_all.reset_index().to_dict(orient="records"),
        "missed_by_model": missed, "missed_rule_24h_mm": MISSED_BELOW_24H_MM,
        "events": table.where(table.notna(), None).to_dict(orient="records"),
        "thresholds": thresholds,
        "note": ("Limite inferior: menor chuva (por data) que coincidiu com bloqueios informados "
                 "(nível médio) e mediana entre datas (nível alto), excluindo datas em que o "
                 "modelo não capturou a chuva. Dado modelado; não é probabilidade nem substitui "
                 "pluviômetro; temporais curtos podem não aparecer na previsão."),
    }


def daily_rain(lat: float, lon: float, start: str, end: str) -> pd.Series:
    """Daily precipitation totals (mm) from the reanalysis archive."""
    query = urllib.parse.urlencode({"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
                                    "start_date": start, "end_date": end,
                                    "daily": "precipitation_sum", "timezone": TIMEZONE})
    with urllib.request.urlopen(f"{REANALYSIS}?{query}", timeout=120) as response:
        payload = json.load(response)
    return pd.Series(payload["daily"]["precipitation_sum"],
                     index=pd.to_datetime(payload["daily"]["time"]), dtype=float).dropna()


def frequency(daily: pd.Series, thresholds: list[float]) -> list[dict]:
    """Days per year with at least each threshold (mean, min, max over full years)."""
    rows = []
    for threshold in thresholds:
        per_year = (daily >= threshold).groupby(daily.index.year).sum()
        rows.append({"threshold_mm": threshold, "days_per_year_mean": round(float(per_year.mean()), 1),
                     "days_per_year_min": int(per_year.min()), "days_per_year_max": int(per_year.max())})
    return rows


def main() -> None:
    argparse.ArgumentParser(description="Calibra limiares de chuva com o arquivo do Open-Meteo").parse_args()
    from .scenarios import load_events

    config = load_config()
    events = load_events(resolve(config["paths"]["events"]) / "events.csv")
    result = calibrate(events)
    path = resolve(config["paths"]["qa"]) / "rain_calibration.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n",
                    encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("per_date", "thresholds")}, indent=2, ensure_ascii=False))
    # How often these rains happen (reanalysis, city centre, full years).
    daily = daily_rain(-30.05, -51.18, "2015-01-01", "2024-12-31")
    steps = sorted({*config["mobility"]["chuva_24h_mm"], result["thresholds"]["medio_total_24h_mm"],
                    result["thresholds"]["alto_total_24h_mm"]})
    freq = {"source": REANALYSIS, "point": [-30.05, -51.18], "period": "2015-2024",
            "annual_mean_mm": round(float(daily.groupby(daily.index.year).sum().mean())),
            "note": "Totais por dia de calendário de reanálise (modelada), não pluviômetro.",
            "frequency": frequency(daily, steps)}
    (resolve(config["paths"]["qa"]) / "rain_frequency.json").write_text(
        json.dumps(freq, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(freq["frequency"], ensure_ascii=False))
    errors = [e for e in result["events"] if e.get("error")]
    if errors:
        print("datas sem dados:", sorted({e["event_date"] for e in errors}))


if __name__ == "__main__":
    main()
