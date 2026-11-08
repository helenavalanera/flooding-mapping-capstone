"""Input data ingestion with provenance tracking."""

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import load_config, resolve

CHUNK_SIZE = 1 << 20


def read_csv(path: str | Path) -> pd.DataFrame:
    """Read a CSV file and fail clearly when it is unavailable."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"CSV input not found: {source}")
    return pd.read_csv(source)


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_integrity(path: str | Path) -> None:
    """Fail when a ZIP or OSM PBF file is corrupted or truncated."""
    path = Path(path)
    if path.stat().st_size == 0:
        raise ValueError(f"Empty file: {path}")
    if path.suffix == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                bad = archive.testzip()
        except zipfile.BadZipFile as error:
            raise ValueError(f"Corrupted ZIP: {path}") from error
        if bad is not None:
            raise ValueError(f"Corrupted member {bad} in {path}")
    elif path.suffix == ".pbf":
        with open(path, "rb") as handle:
            if b"OSMHeader" not in handle.read(64):
                raise ValueError(f"Not an OSM PBF file: {path}")


def load_manifest(path: str | Path) -> dict:
    """Read the provenance manifest, creating an empty structure if absent."""
    path = Path(path)
    if not path.is_file():
        return {"sources": []}
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest.get("sources"), list):
        raise ValueError(f"Manifest without a 'sources' list: {path}")
    return manifest


def register(manifest_path: str | Path, entry: dict) -> bool:
    """Append an entry unless the same path and hash are already recorded.

    Returns True when the manifest was changed.
    """
    manifest = load_manifest(manifest_path)
    for existing in manifest["sources"]:
        if (existing.get("path"), existing.get("sha256")) == (
            entry["path"],
            entry["sha256"],
        ):
            return False
    manifest["sources"].append(entry)
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, manifest_path)
    return True


def download(
    url: str,
    destination: str | Path,
    manifest_path: str | Path,
    source_date: str | None = None,
    force: bool = False,
    timeout: float = 60,
) -> dict:
    """Download a file atomically and record its provenance.

    An existing destination is reused (and registered if missing from the
    manifest) unless ``force`` is set. Partial downloads never replace the
    destination: data is streamed to a temporary file, checked against the
    declared Content-Length and the format integrity, then moved into place.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    http: dict = {}

    if destination.exists() and not force:
        check_integrity(destination)
        status = "existing"
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "flooding-mapping"})
        # The ".part<ext>" suffix keeps the format visible to check_integrity.
        handle, temporary = tempfile.mkstemp(
            dir=destination.parent, suffix=".part" + destination.suffix
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response, os.fdopen(
                handle, "wb"
            ) as output:
                expected = response.headers.get("Content-Length")
                http = {
                    "final_url": response.geturl(),
                    "last_modified": response.headers.get("Last-Modified"),
                    "content_length": int(expected) if expected else None,
                }
                for chunk in iter(lambda: response.read(CHUNK_SIZE), b""):
                    output.write(chunk)
            received = os.path.getsize(temporary)
            if expected is not None and received != int(expected):
                raise IOError(f"Incomplete download: {received} of {expected} bytes")
            check_integrity(temporary)
            os.replace(temporary, destination)
        except BaseException:
            if os.path.exists(temporary):
                os.remove(temporary)
            raise
        status = "downloaded"

    try:
        relative = destination.resolve().relative_to(resolve("."))
    except ValueError:
        relative = destination
    entry = {
        "url": url,
        "path": str(relative),
        "downloaded_at_utc": datetime.fromtimestamp(
            destination.stat().st_mtime, tz=timezone.utc
        ).isoformat(timespec="seconds"),
        "sha256": sha256_file(destination),
        "size_bytes": destination.stat().st_size,
        "source_reference_date": source_date,
        **http,
    }
    entry["registered"] = register(manifest_path, entry)
    entry["status"] = status
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa uma fonte declarada em config/analysis.yaml")
    parser.add_argument("source", help="chave em sources (ex.: gtfs, osm)")
    parser.add_argument("--source-date", default=None, help="data de referência da fonte")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config = load_config()
    source = config["sources"].get(args.source)
    if not source:
        raise SystemExit(f"Fonte sem URL verificada em config: {args.source}")
    entry = download(
        source["url"],
        resolve(source["destino"]),
        resolve(config["paths"]["manifest"]),
        source_date=args.source_date,
        force=args.force,
    )
    print(json.dumps(entry, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
