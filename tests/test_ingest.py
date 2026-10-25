import functools
import http.server
import json
import threading
import zipfile

import pytest

from flooding_mapping.ingest import download, load_manifest, register, sha256_file


@pytest.fixture
def server(tmp_path):
    """Serve tmp_path/www over HTTP on a random local port."""
    root = tmp_path / "www"
    root.mkdir()
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(root)
    )
    handler.log_message = lambda *args: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield root, f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def make_zip(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("stops.txt", "stop_id\n1\n")


def test_download_records_provenance_and_is_idempotent(server, tmp_path):
    root, base = server
    make_zip(root / "feed.zip")
    destination = tmp_path / "raw" / "feed.zip"
    manifest = tmp_path / "raw" / "manifest.json"

    first = download(f"{base}/feed.zip", destination, manifest, source_date="2025-09-25")
    assert first["status"] == "downloaded"
    assert first["sha256"] == sha256_file(root / "feed.zip")
    assert first["size_bytes"] == (root / "feed.zip").stat().st_size
    assert first["source_reference_date"] == "2025-09-25"

    second = download(f"{base}/feed.zip", destination, manifest)
    assert second["status"] == "existing"
    assert second["registered"] is False
    assert len(load_manifest(manifest)["sources"]) == 1
    assert not list(destination.parent.glob("*.part*"))


def test_download_rejects_corrupted_zip_without_leaving_files(server, tmp_path):
    root, base = server
    (root / "bad.zip").write_bytes(b"not a zip")
    destination = tmp_path / "raw" / "bad.zip"
    manifest = tmp_path / "raw" / "manifest.json"

    with pytest.raises(ValueError, match="Corrupted ZIP"):
        download(f"{base}/bad.zip", destination, manifest)
    assert not destination.exists()
    assert not list(destination.parent.glob("*"))


def test_download_fails_on_http_error(server, tmp_path):
    _, base = server
    with pytest.raises(Exception, match="404"):
        download(f"{base}/missing.zip", tmp_path / "x.zip", tmp_path / "m.json")
    assert not (tmp_path / "x.zip").exists()


def test_register_preserves_existing_entries(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sources": [{"path": "a", "sha256": "1"}], "notes": "n"}))
    assert register(manifest, {"path": "b", "sha256": "2"}) is True
    assert register(manifest, {"path": "b", "sha256": "2"}) is False
    content = load_manifest(manifest)
    assert [s["path"] for s in content["sources"]] == ["a", "b"]
    assert content["notes"] == "n"


def test_manifest_without_sources_list_is_rejected(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sources": "oops"}))
    with pytest.raises(ValueError):
        load_manifest(manifest)
