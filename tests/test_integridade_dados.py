"""Auditoria de integridade dos dados derivados (tools/auditar_integridade.py): hashes, fragmentos, tiles e rastreabilidade dos indicadores."""
import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
pytestmark = pytest.mark.skipif(not (RAIZ / "data/processed/fase3_web/meta.json").exists(), reason="camadas derivadas não geradas")


def test_every_integrity_check_passes_on_the_derived_data():
    spec = importlib.util.spec_from_file_location("auditar_integridade", RAIZ / "tools/auditar_integridade.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    r = m.verificar(RAIZ)
    assert len(r) >= 15
    assert [x for x in r if not x["ok"]] == []


def test_the_audit_detects_a_tampered_parquet(tmp_path):
    import shutil
    spec = importlib.util.spec_from_file_location("auditar_integridade2", RAIZ / "tools/auditar_integridade.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    base = tmp_path / "data/processed"
    shutil.copytree(RAIZ / "data/processed/fase3_web", base / "fase3_web", ignore=shutil.ignore_patterns("tiles"))
    (base / "fase3").mkdir()
    for p in (RAIZ / "data/processed/fase3").glob("trechos_nivel1*.parquet"):
        shutil.copy(p, base / "fase3" / p.name)
    (base / "fase3" / "trechos_nivel1_propensao_topografica.parquet").write_bytes(b"adulterado")
    falhas = [x["verificacao"] for x in m.verificar(tmp_path) if not x["ok"]]
    assert any("hash de trechos_nivel1_propensao_topografica.parquet" in f for f in falhas)
