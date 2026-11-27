"""Índice da documentação e pasta única de upload: nenhum documento sem entrada, índice atualizado, links que resolvem, manifesto com SHA-256 e nada de segredo nem ZIP."""
import hashlib
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import consolidar_documentacao as c  # noqa: E402


def test_every_document_has_exactly_one_entry_and_every_entry_points_to_a_file():
    existentes = {p.name for p in (RAIZ / "docs").glob("*.md") if p.name != "README.md"}
    assert existentes == set(c.CATALOGO), (existentes ^ set(c.CATALOGO))
    assert all(0 <= cat < len(c.CATEGORIAS) and fin.endswith((".", ")")) for cat, fin in c.CATALOGO.values())
    for n, _ in c.EXTRAS:
        assert (RAIZ / n).exists(), n


def test_the_committed_index_is_up_to_date_and_its_links_resolve():
    texto = (RAIZ / "docs/README.md").read_text(encoding="utf-8")
    assert texto == c.indice() + "\n", "rode tools/consolidar_documentacao.py --so-indice"
    for link in re.findall(r"\]\(([^)]+\.md)\)", texto):
        assert (RAIZ / "docs" / link).exists(), link
    assert "Histórico: frentes arquivadas" in texto and "geoai_camada_e.md" in texto and "recorte_municipal.md" in texto and "base_legal_dados.md" in texto


def test_the_upload_folder_is_one_folder_with_an_index_and_a_manifest_that_matches_the_files(tmp_path):
    r = c.pasta_unica(tmp_path / "pasta")
    pasta = tmp_path / "pasta"
    assert {p.name for p in pasta.iterdir()} == {"INDICE.md", "MANIFESTO.json", "documentos", "leia-me", "numeros-e-relatorios"}
    man = json.loads((pasta / "MANIFESTO.json").read_text())
    assert man["arquivos"] == r["arquivos"] == len(man["conteudo"]) and "MANIFESTO.json" not in man["conteudo"]
    for rel, info in man["conteudo"].items():
        assert hashlib.sha256((pasta / rel).read_bytes()).hexdigest() == info["sha256"], rel
    indice = (pasta / "INDICE.md").read_text(encoding="utf-8")
    for link in re.findall(r"\]\(([^)]+\.md)\)", indice):
        assert (pasta / link).exists(), link                                                                   # os links do índice valem dentro da pasta
    assert not list(pasta.rglob("*.zip")) and not list(pasta.rglob(".env*"))
    assert (pasta / "numeros-e-relatorios/qa/geoai_resultados.json").exists() and (pasta / "numeros-e-relatorios/dados-publicados/recorte_municipal_poa.json").exists()


def test_the_consolidator_does_not_upload_or_zip_anything():
    codigo = (RAIZ / "tools/consolidar_documentacao.py").read_text(encoding="utf-8").split('"""')[2]
    for proibido in ("make_archive", "zipfile", "requests", "boto3", "googleapiclient", "subprocess"):
        assert proibido not in codigo, proibido
