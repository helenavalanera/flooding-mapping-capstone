import hashlib
import json

import pytest

from flooding_mapping.models import publish
from flooding_mapping.r2 import MemoryStore


def setup(tmp_path, payload=b"modelo-bytes", version="gatilho-estrito-20261108"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    model = tmp_path / "modelo.joblib"
    model.write_bytes(payload)
    card = tmp_path / "card.json"
    card.write_text(json.dumps({"artefato": {"versao": version, "sha256": hashlib.sha256(payload).hexdigest()}}))
    return model, card


def test_upload_then_download_returns_the_same_bytes(tmp_path):
    store = MemoryStore()
    model, card = setup(tmp_path)
    publish.upload(store, model, card)
    got = publish.download(store, card, tmp_path / "out" / "modelo.joblib")
    assert got.read_bytes() == b"modelo-bytes" and store.get_json(publish.POINTER)["versao"] == "gatilho-estrito-20261108"


def test_upload_refuses_a_file_that_is_not_the_one_the_card_describes(tmp_path):
    model, card = setup(tmp_path)
    model.write_bytes(b"outro-modelo")
    with pytest.raises(ValueError, match="does not match"):
        publish.upload(MemoryStore(), model, card)


def test_download_refuses_a_different_version_a_missing_object_and_an_altered_one(tmp_path):
    store = MemoryStore()
    model, card = setup(tmp_path)
    with pytest.raises(RuntimeError, match="documents"):
        publish.download(store, card, tmp_path / "x")              # nothing published yet
    publish.upload(store, model, card)
    _, old_card = setup(tmp_path / "antigo", b"v0", "gatilho-estrito-20260101")
    with pytest.raises(RuntimeError, match="documents gatilho-estrito-20260101"):
        publish.download(store, old_card, tmp_path / "x")          # R2 holds a newer version than the card
    store.objects["modelos/gatilho-estrito-20261108/modelo.joblib"] = b"adulterado"
    with pytest.raises(RuntimeError, match="does not match the hash"):
        publish.download(store, card, tmp_path / "x")
    assert not (tmp_path / "x").exists()                            # nothing is written on failure
