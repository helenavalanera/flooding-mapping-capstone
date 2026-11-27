"""Preparação dos derivados para o R2: gzip determinístico, cabeçalhos por tipo de objeto e conferência do conteúdo original. Não envia nada."""
import gzip
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import preparar_para_r2 as p  # noqa: E402


def camada(pasta: Path, nome: str) -> None:
    (pasta / "tiles" / "13" / "1").mkdir(parents=True)
    (pasta / "tiles" / "13" / "1" / "2.pbf").write_bytes(b"tile" * 2000)
    (pasta / "meta.json").write_text(json.dumps({"versao": 1, "nome": nome}))


def test_headers_make_tiles_immutable_and_gzip_but_keep_the_meta_revalidated_and_the_pmtiles_uncompressed():
    t, m, pm = p.cabecalhos_do_objeto("fase3/tiles/13/1/2.pbf", True), p.cabecalhos_do_objeto("fase3/meta.json", True), p.cabecalhos_do_objeto("mapa/poa.pmtiles", False)
    assert t["content_encoding"] == "gzip" and "immutable" in t["cache_control"] and t["content_type"] == "application/x-protobuf"
    assert "immutable" not in m["cache_control"] and "must-revalidate" in m["cache_control"]
    assert "content_encoding" not in pm and "immutable" in pm["cache_control"]
    assert "content_encoding" not in p.cabecalhos_do_objeto("fase3/tiles/13/1/2.pbf", False)


def test_the_staging_folder_is_versioned_deterministic_and_checks_against_the_original_content(tmp_path):
    f3, dr = tmp_path / "f3", tmp_path / "dr"
    camada(f3, "f3"), camada(dr, "dr")
    r = p.preparar(f3, dr, tmp_path / "out")
    assert r["versao_dos_dados"].startswith("d-") and r["bytes"] < r["bytes_originais"]
    raiz = tmp_path / "out" / r["versao_dos_dados"]
    info = json.loads((raiz / "cabecalhos.json").read_text())["objetos"]
    chave = "fase3/tiles/13/1/2.pbf"
    guardado = (raiz / chave).read_bytes()
    assert gzip.decompress(guardado) == b"tile" * 2000 and info[chave]["sha256_do_original"] == hashlib.sha256(b"tile" * 2000).hexdigest()
    assert info["fase3/meta.json"]["content_encoding"] == "gzip" and info[chave]["bytes"] == len(guardado)
    r2 = p.preparar(f3, dr, tmp_path / "out2")                                    # mesmo conteúdo, mesma versão e mesmos bytes comprimidos
    assert r2["versao_dos_dados"] == r["versao_dos_dados"] and (tmp_path / "out2" / r["versao_dos_dados"] / chave).read_bytes() == guardado


def test_the_tool_never_uploads_or_reads_credentials():
    codigo = (RAIZ / "tools/preparar_para_r2.py").read_text(encoding="utf-8")
    for proibido in ("boto3", "wrangler", "R2_SECRET", "R2_ACCESS", "requests", "environ", "token"):
        assert proibido not in codigo.split('"""')[2], proibido


def test_the_geoai_layer_goes_with_the_webp_uncompressed_and_the_meta_revalidated(tmp_path):
    f3, dr, ge = tmp_path / "f3", tmp_path / "dr", tmp_path / "ge"
    camada(f3, "f3"), camada(dr, "dr")
    ge.mkdir()
    (ge / "fracao_construida.webp").write_bytes(b"RIFF" + b"x" * 3000)
    (ge / "meta.json").write_text(json.dumps({"versao": 1}))
    r = p.preparar(f3, dr, tmp_path / "out", geoai=ge)
    sem = p.preparar(f3, dr, tmp_path / "out2")
    assert r["versao_dos_dados"] != sem["versao_dos_dados"]                                       # a camada E muda o conjunto e, portanto, a versão
    info = json.loads((tmp_path / "out" / r["versao_dos_dados"] / "cabecalhos.json").read_text())["objetos"]
    img, meta = info["geoai/fracao_construida.webp"], info["geoai/meta.json"]
    assert img["content_type"] == "image/webp" and "content_encoding" not in img and "immutable" in img["cache_control"]
    assert meta["content_encoding"] == "gzip" and "immutable" not in meta["cache_control"]
