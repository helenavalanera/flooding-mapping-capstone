"""Referências bibliográficas, declaração de reuso de dados abertos e nomenclatura: o registro único, as citações e o texto publicado.

Não verificam endereços na rede (isso foi feito à mão e consta em `conferido` de cada entrada), só a coerência interna.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import gerar_referencias as g  # noqa: E402

LANDING = RAIZ / "src/flooding_mapping/app/static/inicio/index.html"
TEMPLATE = RAIZ / "tools/landing/estudo.template.html"
FRASE = ("O estudo utiliza dados geoespaciais públicos, provenientes de bases governamentais e iniciativas de dados abertos, reutilizados para fins de pesquisa, "
         "análise e desenvolvimento de produtos geoespaciais. As fontes originais são referenciadas na documentação técnica.")
CATEGORIAS = ["Dados geoespaciais e bases territoriais", "Dados de uso e cobertura do solo", "Dados de relevo e modelos digitais de elevação", "Dados de drenagem e infraestrutura urbana",
              "Dados meteorológicos e precipitação", "Bases históricas e registros de eventos", "Dados de referência e validação", "Métodos e referenciais científicos",
              "Modelos de inteligência artificial e GeoAI", "Bibliotecas, ferramentas e tecnologias", "Mapas-base, serviços cartográficos e provedores"]


@pytest.fixture(scope="module")
def refs():
    return g.carregar()


def test_the_registry_is_complete_and_unique(refs):
    assert len({r["id"] for r in refs}) == len(refs)
    assert len({r["cit"] for r in refs}) == len(refs), "duas referências com a mesma chave de citação"
    for r in refs:
        assert all(r.get(k) not in (None, "") for k in ("id", "cat", "uso", "tipo", "autor", "titulo", "ano", "licenca", "nota", "conferido")), r["id"]
        assert r["cat"] in g.CATEGORIAS and r["uso"] in g.USO and r["tipo"] in g.TIPOS, r["id"]


def test_the_eleven_categories_have_the_required_names_in_order():
    assert [g.CATEGORIAS[i] for i in range(1, 12)] == CATEGORIAS


def test_every_reference_has_a_locator_or_says_it_has_none(refs):
    for r in refs:
        assert r.get("url") or r.get("doi") or "sem endereço" in (r["nota"] + r["conferido"]).lower() or r["id"] == "events2025", r["id"]


def test_no_licence_is_asserted_for_third_party_data_without_evidence(refs):
    # Fontes da Prefeitura e do DAER: a licença não foi confirmada e a tabela precisa dizer isso.
    for i in ("profill2022", "geopoa_drenagem", "daer_rodovias"):
        r = next(x for x in refs if x["id"] == i)
        assert re.search(r"n[ãa]o confirmada|a confirmar", r["licenca"], re.I), i
    # Nenhum dado de terceiros recebe MIT; MIT só aparece onde o próprio pacote a declara (bibliotecas, categoria 10) ou em ressalva.
    for r in refs:
        if r["tipo"] in ("dataset",) or r["cat"] in (1, 2, 3, 4, 5, 6, 7):
            assert not re.search(r"\bMIT\b", r["licenca"]), r["id"]


def test_tools_not_executed_are_marked_and_kept_apart(refs):
    por_id = {r["id"]: r for r in refs}
    assert por_id["szwarcman2024"]["uso"] == "avaliada"
    assert por_id["cloudflare_pages"]["uso"] == "planejada" and por_id["cloudflare_r2"]["uso"] == "planejada"
    assert not any("streamlit" in (r["id"] + r["titulo"]).lower() for r in refs), "Streamlit nunca foi usado"
    md = g.documento_md(refs)
    corpo, _, avaliadas = md.partition("## Tecnologias avaliadas, não utilizadas, e planejadas")
    for r in refs:
        if r["uso"] in g.SEPARADAS:
            assert r["titulo"] in avaliadas and r["titulo"] not in corpo, r["id"]


def test_every_citation_marker_in_the_template_resolves_to_a_reference(refs):
    ids = {r["id"] for r in refs}
    usados = {i.strip() for m in re.findall(r"\{\{cite:([a-z0-9_,\s]+)\}\}", TEMPLATE.read_text(encoding="utf-8")) for i in m.split(",")}
    assert usados and usados <= ids, usados - ids


def test_a_citation_marker_that_matches_nothing_fails_loudly(refs):
    with pytest.raises(Exception):
        g.substituir_citacoes("texto {{cite:nao_existe}}", refs)


def test_the_landing_has_the_references_section_and_navigation_link():
    t = LANDING.read_text(encoding="utf-8")
    assert '<h2 id="h-ref" class="titulo">Referências bibliográficas</h2>' in t
    assert re.search(r'<ol class="ancoras">.*?href="#referencias">Referências</a>.*?</ol>', t, re.S)
    for nome in CATEGORIAS:
        assert nome in t, nome
    assert "Tecnologias avaliadas, não utilizadas, e planejadas" in t


def test_every_reference_cited_in_the_landing_exists_and_every_used_reference_is_listed():
    t = LANDING.read_text(encoding="utf-8")
    alvos = set(re.findall(r'class="cit"[^>]*href="#([^"]+)"', t)) | set(re.findall(r'href="#([^"]+)"[^>]*class="cit"', t))
    ids = set(re.findall(r'<li id="([^"]+)"', t))
    assert alvos and alvos <= ids, alvos - ids
    for chave in ("profill2022", "copernicus_dem", "osm_geofabrik", "hersbach2020", "openmeteo_software", "breiman2001", "alphaearth_dataset", "roberts2017", "drusch2012"):
        assert any(chave in i for i in ids), chave


def test_the_open_data_statement_is_verbatim_with_its_caveat_on_landing_readme_and_docs():
    for caminho in (LANDING, RAIZ / "README.md", RAIZ / "docs/inventario_fontes.md", RAIZ / "docs/metodologia.md"):
        t = re.sub(r"\s+", " ", caminho.read_text(encoding="utf-8"))
        assert FRASE in t, caminho.name
    landing = re.sub(r"<[^>]+>", "", LANDING.read_text(encoding="utf-8"))
    assert "não afirma que todas as bases" in landing and "licença MIT vale para o código" in landing


def test_geoai_is_presented_as_experimental_without_overclaims():
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", LANDING.read_text(encoding="utf-8")))
    ini = t.index("GeoAI: estimar a parte construída")
    sec = t[ini:t.index("De onde vêm os dados", ini)]
    for frase in ("não prevê alagamentos", "Concordância com a Profill não é validação independente em campo", "empatou com o Random Forest", "não é publicado", "solo exposto"):
        assert frase in sec, frase
    assert not re.search(r"supera o Random Forest|valida(do|ção) em campo\b(?! )", sec.replace("não é validação independente em campo", ""))


def test_the_published_text_avoids_the_terms_the_glossary_forbids():
    t = re.sub(r"<[^>]+>", " ", LANDING.read_text(encoding="utf-8"))
    t = re.sub(r"\s+", " ", t)
    for m in re.finditer(r"tempo real", t, re.I):
        assert "não um serviço em" in t[max(0, m.start() - 20):m.start()], t[max(0, m.start() - 60):m.end() + 20]
    # "vazão" só na negação ou como capacidade da drenagem
    for m in re.finditer(r"vaz[ãa]o", t, re.I):
        ctx = t[max(0, m.start() - 60):m.end() + 40].lower()
        assert re.search(r"n[ãa]o|capacidade|sem ", ctx), ctx


@pytest.mark.parametrize("doc", ["referencias_bibliograficas", "inventario_fontes", "glossario", "metodologia"])
def test_the_four_documents_exist_and_are_linked_from_the_readme(doc):
    assert (RAIZ / "docs" / f"{doc}.md").stat().st_size > 2000
    assert f"docs/{doc}.md" in (RAIZ / "README.md").read_text(encoding="utf-8")


def test_the_generated_reference_document_is_up_to_date(refs):
    assert (RAIZ / "docs/referencias_bibliograficas.md").read_text(encoding="utf-8") == g.documento_md(refs), "rode tools/gerar_referencias.py"
