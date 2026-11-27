"""O produto ativo é restrito a Porto Alegre, e o que saiu do escopo ou da publicação não volta sem querer.

Cobre: interface e landing sem frente estadual; frentes arquivadas guardadas (não apagadas) e não carregadas; dados e imagens de licença não confirmada fora da árvore versionada.
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "src/flooding_mapping/app"
STATIC = APP / "static"
ESTADUAL = re.compile(r"DAER|S2iD|CPRv|rodovi|bloqueio|munic[ií]pios|Rio Grande do Sul|estadual|estaduais", re.I)


def texto(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_the_landing_never_offers_a_state_front():
    h = texto(STATIC / "inicio/index.html")
    fora = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", h, flags=re.S)))
    achados = {m.group(0).lower() for m in ESTADUAL.finditer(fora)}
    assert achados == {"rio grande do sul"}, achados            # só o nome do estado ao situar Porto Alegre
    assert "Porto Alegre, Rio Grande do Sul" in fora


def test_the_published_static_folder_has_only_porto_alegre_data_and_no_state_layers():
    assert sorted(p.name for p in (STATIC / "data").iterdir()) == ["mapa_dimensoes_poa.json", "mapa_manchas_poa.json", "rankings_poa.json", "recorte_municipal_poa.json", "resultados_poa.json", "territorio_poa.json"]
    for nome in ("rodovias.geojson", "municipios.geojson", "cobertura_rs.json", "impacto_rs.json", "ocorrencias.json", "territorios.json"):
        assert not (STATIC / "data" / nome).exists(), nome
    assert not list(STATIC.rglob("*.geojson")) and not list(STATIC.rglob("*.parquet"))
    assert not (STATIC / "pwa").exists() and not (STATIC / "inicio/aplicativo.html").exists() and not (STATIC / "inicio/inicio.js").exists()


def test_the_archived_fronts_are_kept_and_the_active_interface_does_not_load_them():
    arq = APP / "arquivo"
    for rel in ("painel-estadual/painel.js", "painel-estadual/mapa.js", "painel-estadual/index.html", "site_estadual.py", "pwa/pwa.js", "inicio/aplicativo.html"):
        assert (arq / rel).is_file(), rel
    painel = texto(STATIC / "index.html")
    assert "arquivo" not in painel and "painel-estadual" not in painel
    for js in ("painel.js", "mapa.js", "mapa2d.js", "territorio.js"):
        assert "arquivo/painel-estadual" in texto(STATIC / js), js       # cada módulo diz onde está a versão de duas escalas
    assert (arq / "painel-estadual/painel.js").read_text(encoding="utf-8") != texto(STATIC / "painel.js")


def test_raw_third_party_data_and_unconfirmed_coordinates_are_not_in_the_versionable_tree():
    assert sorted(p.suffix for p in (STATIC / "inicio/img/estudo").iterdir()) == [".svg"] * 5 + [".webp"] * 5          # gráficos de números agregados e os cinco mapas de manchas, A a E (derivados, com atribuição)
    assert not list((RAIZ / "docs/figuras").glob("geoai_*.png"))                                              # derivam da Profill
    assert not (APP / "arquivo/inicio/img/painel-rs.png").exists()                                            # mostrava a malha do DAER
    assert not (RAIZ / "tests/dados/alagamentos_pmpa_coordenadas.csv").exists()                               # coordenadas da Prefeitura
    assert sorted(p.name for p in (RAIZ / "tests/dados").iterdir()) == ["LEIAME.md", "alagamentos_sinteticos.csv"]


def test_the_landing_gives_the_legal_basis_and_says_why_the_trecho_layers_are_pending():
    h = texto(STATIC / "inicio/index.html")
    assert "Decreto Municipal nº 20.315/2019" in h and "base_legal_dados.md" in h and "dependem da publicação dos arquivos derivados" in h
    assert "Figura não publicada" in texto(RAIZ / "docs/geoai_resultados.md")
    assert "mapas de trechos" in texto(RAIZ / "tools/gerar_landing.py") and "--mapas-locais" in texto(RAIZ / "tools/gerar_landing.py")


def test_the_scheduled_site_workflow_builds_the_porto_alegre_site_without_model_or_secrets():
    w = texto(RAIZ / ".github/workflows/publicar-site.yml")
    assert "app.build --out site" in w and "--model" not in w and "R2_" not in w and "schedule" not in w and "workflow_dispatch" in w
