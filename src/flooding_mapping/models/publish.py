"""Move the trained model to and from R2, kept out of git, checking its hash every time.

The model card in the repository records the SHA-256 of the artifact it describes. Upload
refuses a file that does not match its card, and download refuses an object that does not
match it either, so the site can only ever be built with the model that was validated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..r2 import OpBudget, R2Store

POINTER = "modelos/_atual.json"


def _card(path: Path) -> dict:
    return json.loads(path.read_text())["artefato"]


def upload(store, artifact: Path, card: Path) -> dict:
    """Store the artifact under its version and point ``_atual`` at it."""
    recorded = _card(card)
    data = artifact.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != recorded["sha256"]:
        raise ValueError(f"artifact hash {digest[:12]} does not match the model card {recorded['sha256'][:12]}")
    store.put_bytes(f"modelos/{recorded['versao']}/modelo.joblib", data, "application/octet-stream")
    pointer = {"versao": recorded["versao"], "sha256": digest,
               "enviado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    store.put_json(POINTER, pointer)
    return pointer


def download(store, card: Path, destination: Path) -> Path:
    """Fetch the version the card documents; fail if the object is absent or altered."""
    recorded = _card(card)
    pointer = store.get_json(POINTER)
    if not pointer or pointer["versao"] != recorded["versao"]:
        raise RuntimeError(f"R2 holds model {pointer and pointer['versao']}, the card documents {recorded['versao']}")
    data = store.get_bytes(f"modelos/{recorded['versao']}/modelo.joblib")
    if data is None:
        raise RuntimeError("model object missing in R2")
    if hashlib.sha256(data).hexdigest() != recorded["sha256"]:
        raise RuntimeError("model object does not match the hash in the model card")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish or fetch the trained model (R2)")
    sub = parser.add_subparsers(dest="command", required=True)
    up = sub.add_parser("upload")
    up.add_argument("--model", type=Path, required=True)
    up.add_argument("--card", type=Path, required=True)
    down = sub.add_parser("download")
    down.add_argument("--card", type=Path, required=True)
    down.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    store = R2Store.from_env(OpBudget(max_class_a=5, max_class_b=4))
    if args.command == "upload":
        print(json.dumps(upload(store, args.model, args.card)))
    else:
        print(f"modelo verificado -> {download(store, args.card, args.out)}")


if __name__ == "__main__":
    main()
