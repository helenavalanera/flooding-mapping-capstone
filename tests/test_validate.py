import zipfile
from datetime import date

import pandas as pd

from flooding_mapping.validate import (
    active_services,
    choose_reference_date,
    parse_gtfs_dates,
    service_coverage,
    validate_gtfs,
)

CALENDAR = pd.DataFrame({
    "service_id": ["WK", "SAT"],
    "monday": ["1", "0"], "tuesday": ["1", "0"], "wednesday": ["1", "0"],
    "thursday": ["1", "0"], "friday": ["1", "0"], "saturday": ["0", "1"],
    "sunday": ["0", "0"],
    "start_date": ["20250901", "20250901"],
    "end_date": ["20250930", "20250930"],
})
# 2025-09-09 (Tue): weekday service removed (holiday); 2025-10-05: extra-only service.
CALENDAR_DATES = pd.DataFrame({
    "service_id": ["WK", "EXTRA"],
    "date": ["20250909", "20251005"],
    "exception_type": ["2", "1"],
})
TRIPS = pd.DataFrame({"trip_id": ["t1", "t2", "t3", "t4"],
                      "service_id": ["WK", "WK", "SAT", "EXTRA"]})


def test_active_services_applies_exceptions():
    assert active_services(CALENDAR, CALENDAR_DATES, date(2025, 9, 10)) == {"WK"}
    assert active_services(CALENDAR, CALENDAR_DATES, date(2025, 9, 9)) == set()
    assert active_services(CALENDAR, CALENDAR_DATES, date(2025, 9, 6)) == {"SAT"}
    assert active_services(CALENDAR, CALENDAR_DATES, date(2025, 10, 5)) == {"EXTRA"}


def test_calendar_dates_only_feed():
    assert active_services(None, CALENDAR_DATES, date(2025, 10, 5)) == {"EXTRA"}


def test_coverage_extends_to_exception_dates_and_counts_trips():
    coverage = service_coverage(CALENDAR, CALENDAR_DATES, TRIPS).set_index("date")
    assert coverage.index.max() == date(2025, 10, 5)
    assert coverage.loc[date(2025, 9, 10), "n_trips"] == 2
    assert coverage.loc[date(2025, 9, 9), "n_trips"] == 0
    assert coverage.loc[date(2025, 10, 1), "n_trips"] == 0


def test_reference_date_avoids_holiday_and_respects_window():
    coverage = service_coverage(CALENDAR, CALENDAR_DATES, TRIPS)
    chosen = choose_reference_date(coverage, date(2025, 9, 8), date(2025, 9, 12))
    assert chosen in {date(2025, 9, 10), date(2025, 9, 11)}
    assert chosen != date(2025, 9, 9)
    assert choose_reference_date(coverage, date(2025, 10, 1), date(2025, 10, 5)) is None


def test_invalid_dates_become_nat():
    parsed = parse_gtfs_dates(pd.Series(["20250230", "2025-09-01", "20250901"]))
    assert parsed.isna().tolist() == [True, True, False]


def test_validate_gtfs_flags_expired_feed_and_broken_references(tmp_path):
    path = tmp_path / "feed.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("agency.txt", "agency_id,agency_name\nA,Agency\n")
        archive.writestr("routes.txt", "route_id,route_type\nR1,3\n")
        archive.writestr("stops.txt", "stop_id,stop_lat,stop_lon\nS1,-30.0,-51.2\n")
        archive.writestr("trips.txt", "route_id,service_id,trip_id\nR1,WK,t1\nR9,WK,t2\n")
        archive.writestr("stop_times.txt", "trip_id,stop_id\nt1,S1\nt2,S2\n")
        archive.writestr("calendar.txt", CALENDAR.to_csv(index=False))
    report = validate_gtfs(path, today=date(2026, 1, 1))
    assert report["missing_required"] == []
    assert report["expired"] is True
    assert report["effective"]["last_service_date"] == "2025-09-30"
    assert any("routes.txt" in issue for issue in report["issues"])
    assert any("stops.txt" in issue for issue in report["issues"])
