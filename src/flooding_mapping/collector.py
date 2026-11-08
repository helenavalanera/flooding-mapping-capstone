"""Archive the active highway blockages published by CPRv BM (Rio Grande do Sul).

The public endpoint lists only the blockages active *now*; there is no history.
This collector turns it into one: it keeps the hash of each active blockage and
writes an object to R2 only when something changed, so a quiet hour costs one
read and no write.

Layout in the bucket::

    bloqueios/_estado.json                       last seen state (overwritten)
    bloqueios/AAAA/MM/DD/AAAAMMDDTHHMMSSZ.json   one change event

A change event holds the full records of new and changed blockages and only the
ids of removed ones (as text), so storage grows with the number of changes, not
with the number of polls. The event is written before the state: if the state
write fails, the next run logs the same changes again, so readers must treat a
repeated (id, record) as one.

A payload that is not the expected JSON (for example the firewall's rejection
page) aborts the run without touching the state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .r2 import BudgetExceeded, MemoryStore, OpBudget, R2Store, error_code

ENDPOINT = "https://bloqueios.cprvbm.rs.gov.br/api.php?c=publico:ativos"
USER_AGENT = (
    "flooding-mapping-capstone (pesquisa academica; "
    "+https://github.com/helenavalanera/flooding-mapping-capstone)"
)
STATE_KEY = "bloqueios/_estado.json"
STATE_VERSION = 1


def fetch(url: str = ENDPOINT, timeout: float = 20) -> dict[str, Any]:
    """Download and validate the active-blockage payload."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read())
    return validate(payload)


def validate(payload: Any) -> dict[str, Any]:
    """Fail on anything that is not the expected list of blockage records."""
    if not isinstance(payload, dict) or not isinstance(payload.get("bloqueios"), list):
        raise ValueError("Unexpected payload: missing 'bloqueios' list")
    ids = []
    for record in payload["bloqueios"]:
        if not isinstance(record, dict) or "id" not in record:
            raise ValueError("Unexpected payload: record without 'id'")
        ids.append(str(record["id"]))
    if len(ids) != len(set(ids)):
        raise ValueError("Unexpected payload: duplicated ids")
    return payload


def record_hash(record: dict[str, Any]) -> str:
    """Stable fingerprint of a record, independent of key order."""
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def diff(previous: dict[str, str], records: list[dict[str, Any]]) -> dict[str, list]:
    """Split the current records into new, changed and removed against the state."""
    current = {str(r["id"]): r for r in records}
    return {
        "novos": [r for i, r in current.items() if i not in previous],
        "alterados": [
            r for i, r in current.items() if i in previous and previous[i] != record_hash(r)
        ],
        "removidos": sorted(i for i in previous if i not in current),
    }


def snapshot_key(now: datetime) -> str:
    return f"bloqueios/{now:%Y/%m/%d}/{now:%Y%m%dT%H%M%SZ}.json"


def run(store: Any, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Compare the payload with the stored state and archive what changed."""
    state = store.get_json(STATE_KEY) or {"versao": STATE_VERSION, "ativos": {}}
    records = payload["bloqueios"]
    changes = diff(state["ativos"], records)
    summary = {"ativos": len(records), **{k: len(v) for k, v in changes.items()}, "acao": "nada"}
    if not any(changes.values()):
        return summary

    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    store.put_json(
        snapshot_key(now),
        {
            "versao": STATE_VERSION,
            "coletado_em": stamp,
            "fonte_atualizado": payload.get("atualizado"),
            "total_ativos": len(records),
            **changes,
        },
    )
    state["ativos"] = {str(r["id"]): record_hash(r) for r in records}
    state["atualizado_em"] = stamp
    store.put_json(STATE_KEY, state)
    summary["acao"] = "gravado"
    return summary


def main(argv: list[str] | None = None, fetcher: Callable[[], dict] = fetch) -> int:
    parser = argparse.ArgumentParser(description="Archive CPRv BM active blockages")
    parser.add_argument(
        "--dry-run", action="store_true", help="fetch and report; write nothing, needs no R2"
    )
    args = parser.parse_args(argv)
    try:
        payload = fetcher()
        store = MemoryStore(OpBudget()) if args.dry_run else R2Store.from_env(OpBudget())
        summary = run(store, payload, datetime.now(timezone.utc))
    except BudgetExceeded as exc:
        print(f"ORCAMENTO: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        # The log is public: show the error class and only text that is safe by
        # construction (our own messages, the R2 error code), never raw exceptions.
        detail = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else error_code(exc)
        print(f"FALHA: {type(exc).__name__} {detail}".strip(), file=sys.stderr)
        return 1
    action = "gravaria" if args.dry_run and summary["acao"] == "gravado" else summary["acao"]
    print(
        f"ativos={summary['ativos']} novos={summary['novos']} "
        f"alterados={summary['alterados']} removidos={summary['removidos']} "
        f"acao={action} classeA={store.budget.class_a} classeB={store.budget.class_b}"
        + (" (dry-run)" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
