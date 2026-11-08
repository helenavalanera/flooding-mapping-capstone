from datetime import datetime, timezone

import pytest

from flooding_mapping.collector import (
    STATE_KEY,
    diff,
    main,
    read_events,
    record_hash,
    records_from_events,
    run,
    snapshot_key,
    validate,
)
from flooding_mapping.r2 import MemoryStore

T0 = datetime(2026, 11, 8, 12, 7, 5, tzinfo=timezone.utc)
T1 = datetime(2026, 11, 8, 12, 37, 5, tzinfo=timezone.utc)


def rec(i, **extra):
    return {"id": i, "rodovia": "ERS-401", "tipo": "total", "informacoes": "ponte", **extra}


def payload(*records):
    return {"atualizado": "2026-11-08T12:00:00Z", "bloqueios": list(records)}


def events(store):
    return sorted(k for k in store.objects if k != STATE_KEY)


def clone(store):
    """A new store holding the same objects, with fresh operation counters."""
    copy = MemoryStore()
    copy.objects = dict(store.objects)
    return copy


def test_first_run_archives_everything_as_new():
    store = MemoryStore()
    summary = run(store, payload(rec(1), rec(2)), T0)
    assert summary["novos"] == 2 and summary["acao"] == "gravado"
    assert events(store) == [snapshot_key(T0)]
    assert (store.budget.class_a, store.budget.class_b) == (2, 1)


def test_unchanged_poll_costs_one_read_and_no_write():
    store = MemoryStore()
    run(store, payload(rec(1)), T0)
    quiet = clone(store)
    assert run(quiet, payload(rec(1)), T1)["acao"] == "nada"
    assert (quiet.budget.class_a, quiet.budget.class_b) == (0, 1)
    assert events(quiet) == [snapshot_key(T0)]


def test_changed_and_removed_records_are_logged():
    store = MemoryStore()
    run(store, payload(rec(1), rec(2)), T0)
    later = clone(store)
    summary = run(later, payload(rec(1, tipo="parcial"), rec(3)), T1)
    assert (summary["novos"], summary["alterados"], summary["removidos"]) == (1, 1, 1)
    event = later.get_json(snapshot_key(T1))
    assert [r["id"] for r in event["novos"]] == [3]
    assert [r["id"] for r in event["alterados"]] == [1]
    assert event["removidos"] == ["2"]  # ids of removed records are text


def test_event_stores_only_changes_not_the_whole_list():
    store = MemoryStore()
    run(store, payload(*[rec(i) for i in range(1, 51)]), T0)
    later = clone(store)
    run(later, payload(*[rec(i) for i in range(1, 51)], rec(99)), T1)
    event = later.get_json(snapshot_key(T1))
    assert event["total_ativos"] == 51 and len(event["novos"]) == 1


@pytest.mark.parametrize(
    "bad",
    [None, [], {}, {"bloqueios": "x"}, {"bloqueios": [{"sem_id": 1}]}, {"bloqueios": [rec(1), rec(1)]}],
)
def test_invalid_payload_is_rejected(bad):
    with pytest.raises(ValueError):
        validate(bad)


def test_main_dry_run_needs_no_credentials_and_says_it_would_write(capsys):
    code = main(["--dry-run"], fetcher=lambda: payload(rec(1), rec(2)))
    out = capsys.readouterr().out
    assert code == 0 and "novos=2" in out and "acao=gravaria" in out and "(dry-run)" in out


def test_main_shows_why_a_bad_payload_failed(capsys):
    def broken():
        return validate({"html": "Request Rejected"})

    assert main(["--dry-run"], fetcher=broken) == 1
    err = capsys.readouterr().err
    assert "FALHA: ValueError" in err and "bloqueios" in err


def test_main_names_the_missing_r2_variables_but_no_values(monkeypatch, capsys):
    for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(name, raising=False)
    assert main([], fetcher=lambda: payload(rec(1))) == 1
    assert "R2_BUCKET" in capsys.readouterr().err


def test_hash_ignores_key_order_and_diff_uses_it():
    a = {"id": 1, "x": 1, "y": 2}
    b = {"y": 2, "id": 1, "x": 1}
    assert record_hash(a) == record_hash(b)
    assert diff({"1": record_hash(a)}, [b]) == {"novos": [], "alterados": [], "removidos": []}


def test_history_is_replayed_into_one_row_per_blockage():
    store = MemoryStore()
    run(store, payload(rec(1), rec(2)), T0)
    run(store, payload(rec(1, tipo="parcial"), rec(3)), T1)  # 1 changes, 2 leaves, 3 arrives
    rows = {r["id"]: r for r in records_from_events(read_events(store))}
    assert set(rows) == {1, 2, 3}
    assert rows[1]["tipo"] == "parcial" and rows[1]["visto_primeira_vez"] == "2026-11-08T12:07:05Z"
    assert rows[1]["ultima_alteracao"] == "2026-11-08T12:37:05Z" and rows[1]["removido_em"] is None
    assert rows[2]["removido_em"] == "2026-11-08T12:37:05Z"
    assert rows[3]["visto_primeira_vez"] == "2026-11-08T12:37:05Z"


def test_reading_history_skips_the_state_object_and_counts_the_listing():
    store = MemoryStore()
    run(store, payload(rec(1)), T0)
    reader = clone(store)
    assert len(read_events(reader)) == 1
    assert (reader.budget.class_a, reader.budget.class_b) == (1, 1)
