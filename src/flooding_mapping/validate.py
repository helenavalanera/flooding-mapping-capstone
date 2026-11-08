"""Validation of tabular inputs and GTFS service coverage."""

import argparse
import json
import zipfile
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from .config import load_config, resolve

REQUIRED_GTFS = ("agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    """Raise a useful error when required columns are missing."""
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")


def read_gtfs(path: str | Path, names: Iterable[str]) -> dict[str, pd.DataFrame]:
    """Read selected GTFS tables as strings; absent tables are omitted."""
    tables = {}
    with zipfile.ZipFile(path) as archive:
        members = set(archive.namelist())
        for name in names:
            if name in members:
                with archive.open(name) as handle:
                    tables[name] = pd.read_csv(
                        handle, dtype=str, keep_default_na=False, encoding="utf-8-sig"
                    )
    return tables


def parse_gtfs_dates(values: pd.Series) -> pd.Series:
    """Parse YYYYMMDD strings; invalid values become NaT."""
    return pd.to_datetime(values.str.strip(), format="%Y%m%d", errors="coerce")


def active_services(
    calendar: pd.DataFrame | None, calendar_dates: pd.DataFrame | None, day: date
) -> set[str]:
    """Return service_ids running on ``day`` (calendar plus exceptions)."""
    services: set[str] = set()
    stamp = pd.Timestamp(day)
    if calendar is not None and not calendar.empty:
        start = parse_gtfs_dates(calendar["start_date"])
        end = parse_gtfs_dates(calendar["end_date"])
        weekday = calendar[WEEKDAYS[day.weekday()]].str.strip() == "1"
        services |= set(calendar.loc[(start <= stamp) & (stamp <= end) & weekday, "service_id"])
    if calendar_dates is not None and not calendar_dates.empty:
        on_day = calendar_dates[parse_gtfs_dates(calendar_dates["date"]) == stamp]
        services |= set(on_day.loc[on_day["exception_type"].str.strip() == "1", "service_id"])
        services -= set(on_day.loc[on_day["exception_type"].str.strip() == "2", "service_id"])
    return services


def service_coverage(
    calendar: pd.DataFrame | None,
    calendar_dates: pd.DataFrame | None,
    trips: pd.DataFrame,
) -> pd.DataFrame:
    """Count active services and trips for every day spanned by the calendars."""
    bounds = []
    if calendar is not None and not calendar.empty:
        bounds += [parse_gtfs_dates(calendar["start_date"]).min(),
                   parse_gtfs_dates(calendar["end_date"]).max()]
    if calendar_dates is not None and not calendar_dates.empty:
        parsed = parse_gtfs_dates(calendar_dates["date"])
        bounds += [parsed.min(), parsed.max()]
    bounds = [b for b in bounds if pd.notna(b)]
    if not bounds:
        return pd.DataFrame(columns=["date", "weekday", "n_services", "n_trips"])

    trips_per_service = trips.groupby("service_id").size()
    rows = []
    day = min(bounds).date()
    while day <= max(bounds).date():
        services = active_services(calendar, calendar_dates, day)
        rows.append({
            "date": day,
            "weekday": WEEKDAYS[day.weekday()],
            "n_services": len(services),
            "n_trips": int(trips_per_service.reindex(list(services)).fillna(0).sum()),
        })
        day += timedelta(days=1)
    return pd.DataFrame(rows)


def choose_reference_date(
    coverage: pd.DataFrame, start: date | None = None, end: date | None = None
) -> date | None:
    """Pick a typical mid-week day inside [start, end].

    Typical means a Tue–Thu whose trip count equals the most frequent Tue–Thu
    count (avoiding holidays and reduced service). Among those, the day closest
    to the middle of the window is chosen, earliest on ties.
    """
    window = coverage
    if start is not None:
        window = window[window["date"] >= start]
    if end is not None:
        window = window[window["date"] <= end]
    midweek = window[window["weekday"].isin(["tuesday", "wednesday", "thursday"])
                     & (window["n_trips"] > 0)]
    if midweek.empty:
        return None
    typical = midweek.loc[midweek["n_trips"] == midweek["n_trips"].mode().max(), "date"]
    middle = typical.min() + (typical.max() - typical.min()) / 2
    distance = typical.map(lambda d: abs((d - middle).days))
    return typical[distance == distance.min()].min()


def referential_issues(tables: dict[str, pd.DataFrame]) -> list[str]:
    """Report broken foreign keys between the core GTFS tables."""
    checks = [
        ("trips.txt", "route_id", "routes.txt", "route_id"),
        ("stop_times.txt", "trip_id", "trips.txt", "trip_id"),
        ("stop_times.txt", "stop_id", "stops.txt", "stop_id"),
        ("trips.txt", "shape_id", "shapes.txt", "shape_id"),
    ]
    issues = []
    for child, key, parent, parent_key in checks:
        if child not in tables or parent not in tables or key not in tables[child]:
            continue
        values = tables[child][key]
        values = values[values != ""]
        missing = set(values) - set(tables[parent][parent_key])
        if missing:
            issues.append(f"{child}.{key}: {len(missing)} valores sem correspondência em {parent}")
    return issues


def validate_gtfs(path: str | Path, today: date | None = None) -> dict:
    """Validate a GTFS ZIP and summarise its effective service coverage."""
    today = today or date.today()
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        members = sorted(archive.namelist())
    report: dict = {
        "file": str(path),
        "zip_ok": bad_member is None,
        "files": members,
        "missing_required": [n for n in REQUIRED_GTFS if n not in members],
        "issues": [],
    }
    if "calendar.txt" not in members and "calendar_dates.txt" not in members:
        report["missing_required"].append("calendar.txt|calendar_dates.txt")

    tables = read_gtfs(path, ["calendar.txt", "calendar_dates.txt", "trips.txt", "stops.txt",
                              "routes.txt", "stop_times.txt", "feed_info.txt", "shapes.txt"])
    calendar = tables.get("calendar.txt")
    calendar_dates = tables.get("calendar_dates.txt")

    for name, columns in (("calendar.txt", ("start_date", "end_date")),
                          ("calendar_dates.txt", ("date",))):
        if name in tables:
            for column in columns:
                invalid = parse_gtfs_dates(tables[name][column]).isna().sum()
                if invalid:
                    report["issues"].append(f"{name}.{column}: {invalid} datas inválidas")

    stops = tables["stops.txt"]
    lat = pd.to_numeric(stops["stop_lat"], errors="coerce")
    lon = pd.to_numeric(stops["stop_lon"], errors="coerce")
    bad_coords = int((lat.isna() | lon.isna() | ~lat.between(-90, 90) | ~lon.between(-180, 180)
                      | ((lat == 0) & (lon == 0))).sum())
    if bad_coords:
        report["issues"].append(f"stops.txt: {bad_coords} paradas com coordenadas inválidas")
    report["issues"] += referential_issues(tables)

    trips = tables["trips.txt"]
    unknown_services = set(trips["service_id"]) - set(
        (calendar["service_id"] if calendar is not None else pd.Series(dtype=str)).tolist()
        + (calendar_dates["service_id"] if calendar_dates is not None else pd.Series(dtype=str)).tolist()
    )
    if unknown_services:
        report["issues"].append(f"trips.txt: {len(unknown_services)} service_id sem calendário")

    coverage = service_coverage(calendar, calendar_dates, trips)
    operating = coverage[coverage["n_trips"] > 0]
    declared = {}
    if calendar is not None:
        declared["calendar_start"] = str(parse_gtfs_dates(calendar["start_date"]).min().date())
        declared["calendar_end"] = str(parse_gtfs_dates(calendar["end_date"]).max().date())
    if "feed_info.txt" in tables:
        info = tables["feed_info.txt"].iloc[0]
        for field in ("feed_start_date", "feed_end_date", "feed_version"):
            if field in info:
                declared[field] = info[field]
    report["declared"] = declared

    first = operating["date"].min() if not operating.empty else None
    last = operating["date"].max() if not operating.empty else None
    days_without_service = coverage.loc[
        (coverage["n_trips"] == 0)
        & (coverage["date"] >= (first or date.max)) & (coverage["date"] <= (last or date.min)),
        "date"]
    window = [None, None]
    for i, field in enumerate(("feed_start_date", "feed_end_date")):
        parsed = parse_gtfs_dates(pd.Series([declared.get(field, "")])).iloc[0]
        if pd.notna(parsed):
            window[i] = parsed.date()
    if window[1] is not None and last is not None and window[1] != last:
        report["issues"].append(
            f"feed_end_date ({window[1]}) difere do último dia com viagens ({last})")
    if window[0] is not None and first is not None and window[0] != first:
        report["issues"].append(
            f"feed_start_date ({window[0]}) difere do primeiro dia com viagens ({first})")
    reference = choose_reference_date(coverage, *window)
    report["effective"] = {
        "first_service_date": str(first) if first else None,
        "last_service_date": str(last) if last else None,
        "days_with_service": int(len(operating)),
        "days_without_service_inside_range": [str(d) for d in days_without_service],
        "trips_per_weekday_median": coverage.groupby("weekday")["n_trips"].median().to_dict(),
        "reference_date": str(reference) if reference else None,
        "reference_trips": int(coverage.loc[coverage["date"] == reference, "n_trips"].iloc[0])
        if reference else None,
    }
    report["checked_on"] = str(today)
    report["expired"] = bool(last is None or last < today)
    report["counts"] = {name.removesuffix(".txt"): int(len(frame)) for name, frame in tables.items()}
    report["_coverage"] = coverage
    return report


def write_report(report: dict, directory: str | Path) -> tuple[Path, Path]:
    """Write the GTFS report as JSON and Markdown in ``directory``."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in report.items() if not k.startswith("_")}
    json_path = directory / "gtfs_validation.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    effective = report["effective"]
    lines = [
        "# Validação do GTFS",
        "",
        f"- Arquivo: `{report['file']}`",
        f"- Verificado em: {report['checked_on']}",
        f"- ZIP íntegro: {'sim' if report['zip_ok'] else 'NÃO'}",
        f"- Arquivos obrigatórios ausentes: {', '.join(report['missing_required']) or 'nenhum'}",
        "",
        "## Vigência declarada",
        "",
        *[f"- {k}: {v}" for k, v in report["declared"].items()],
        "",
        "## Cobertura efetiva (calendar.txt + calendar_dates.txt)",
        "",
        f"- Primeiro dia com viagens: {effective['first_service_date']}",
        f"- Último dia com viagens: {effective['last_service_date']}",
        f"- Dias com serviço: {effective['days_with_service']}",
        f"- Dias sem serviço dentro do intervalo: "
        f"{', '.join(effective['days_without_service_inside_range']) or 'nenhum'}",
        f"- Mediana de viagens por dia da semana: "
        + ", ".join(f"{k}={v:.0f}" for k, v in effective["trips_per_weekday_median"].items()),
        f"- Data de referência escolhida: {effective['reference_date']} "
        f"({effective['reference_trips']} viagens)",
        "",
        "## Situação",
        "",
        ("- **Feed vencido** em relação à data da verificação. Usar apenas como referência "
         "histórica; não representa garantidamente o serviço atual."
         if report["expired"] else "- Feed com serviço vigente na data da verificação."),
        "",
        "## Problemas encontrados",
        "",
        *([f"- {issue}" for issue in report["issues"]] or ["- nenhum"]),
        "",
        "## Contagens",
        "",
        *[f"- {k}: {v}" for k, v in report["counts"].items()],
        "",
    ]
    md_path = directory / "gtfs_validation.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida a vigência efetiva do GTFS")
    parser.add_argument("--gtfs", default=None)
    args = parser.parse_args()
    config = load_config()
    gtfs = args.gtfs or resolve(config["sources"]["gtfs"]["destino"])
    report = validate_gtfs(gtfs)
    for path in write_report(report, resolve(config["paths"]["qa"])):
        print(path)
    print(json.dumps(report["effective"], indent=2, ensure_ascii=False, default=str))
    print("issues:", report["issues"], "| expired:", report["expired"])


if __name__ == "__main__":
    main()
