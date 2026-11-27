"""Manifesto de publicação: versão derivada do conteúdo, reprodutível, e capaz de acusar arquivo adulterado, ausente ou a mais."""
import importlib.util
import json
from pathlib import Path

RAIZ = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("manifesto", RAIZ / "tools/gerar_manifesto_publicacao.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def camada(base: Path, nome: str, conteudo: bytes = b"x"):
    d = base / nome
    (d / "tiles/13/1").mkdir(parents=True)
    (d / "tiles/13/1/2.pbf").write_bytes(conteudo)
    (d / "meta.json").write_text(json.dumps({"versao": 1}))
    return d


def test_version_is_derived_from_content_and_reproducible(tmp_path):
    f, d = camada(tmp_path, "f"), camada(tmp_path, "d")
    a, b = m.montar(f, d), m.montar(f, d)
    assert a == b and a["versao_dos_dados"].startswith("d-") and a["camadas"]["fase3"]["arquivos"] == 2
    (f / "tiles/13/1/2.pbf").write_bytes(b"outro")
    assert m.montar(f, d)["versao_dos_dados"] != a["versao_dos_dados"]


def test_verification_reports_tampered_missing_and_extra_files(tmp_path):
    f, d = camada(tmp_path, "f"), camada(tmp_path, "d")
    man = m.montar(f, d)
    assert m.verificar(man, f, d) == []
    (f / "tiles/13/1/2.pbf").write_bytes(b"adulterado")
    (d / "meta.json").unlink()
    (d / "tiles/extra.pbf").write_bytes(b"e")
    erros = m.verificar(man, f, d)
    assert any("hash diferente em tiles/13/1/2.pbf" in e for e in erros) and any("ausente meta.json" in e for e in erros) and any("a mais tiles/extra.pbf" in e for e in erros)


def test_real_manifest_matches_the_layer_metadata_when_data_exist():
    f, d = RAIZ / "data/processed/fase3_web", RAIZ / "data/processed/drenagem_web"
    if not (f / "meta.json").exists() or not (d / "meta.json").exists():
        return
    man = m.montar(f, d)
    assert man["camadas"]["fase3"]["arquivos"] == len([p for p in f.rglob("*") if p.is_file()])
    assert man["camadas"]["fase3"]["meta_sha256"] == m.sha256(f / "meta.json")
