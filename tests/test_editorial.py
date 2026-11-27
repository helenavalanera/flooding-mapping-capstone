"""Auditoria editorial: textos oficiais das dimensões A a D, cenários 10, 20 e 30 mm sem resquício do antigo, modo claro permanente, aviso de dados sintéticos e correspondência entre texto e dados."""
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ST = RAIZ / "src/flooding_mapping/app/static"
FASE3_META = RAIZ / "data/processed/fase3_web/meta.json"

A_D = {
    "A": "Quanto da chuva pode se transformar em água que escoa pela superfície (geração de escoamento superficial).",
    "B": "Para onde a água que escoa tende a convergir pelo território (concentração de escoamento superficial).",
    "C": "Onde o relevo apresenta condições mais favoráveis à retenção de água (propensão topográfica à retenção).",
    "D": "Onde estão localizados os dispositivos e as redes de drenagem cadastrados (infraestrutura de drenagem).",
}
PROPRIOS = [p for p in ST.rglob("*") if p.is_file() and p.suffix in {".js", ".css", ".html"} and "vendor" not in p.parts and not p.name.endswith(".min.js")]


def ler(p: str) -> str:
    return (ST / p).read_text(encoding="utf-8")


def test_the_four_dimensions_use_the_official_sentences_and_stay_independent():
    js = ler("mapa.js")
    bloco = js[js.index("var DIMENSOES = ["):js.index("M.DIMENSOES")]
    for letra, frase in A_D.items():
        assert frase in bloco, letra
    assert [m for m in re.findall(r'id: "([A-D])"', bloco)] == ["A", "B", "C", "D"]
    assert "índice" not in bloco.lower() or "sem índice" in js           # nenhuma dimensão vira nota composta
    assert not re.search(r"índice (composto|combinado|de risco)", js, re.I)


def test_the_methodological_detail_sits_in_a_secondary_disclosure_not_in_the_controls():
    js = ler("mapa.js")
    assert "<details class='dim-nota small'>" in js and "Como ler" in js


@pytest.mark.skipif(not FASE3_META.exists(), reason="camada da Fase 3 não gerada (data/processed fica fora do Git; tools/preparar_camada_fase3.py)")
def test_scenarios_are_10_20_30_everywhere_and_the_old_60_is_gone_from_the_interface():
    meta = json.loads(FASE3_META.read_text())
    res = json.loads((ST / "data/resultados_poa.json").read_text())
    land = json.loads((ST / "inicio/dados.json").read_text())
    assert meta["precipitacoes_mm"] == [10.0, 20.0, 30.0]
    assert sorted(res["cenarios"]["dados"]) == ["10", "20", "30"] and sorted(res["chuva"]["cenarios_na_distribuicao"]) == ["10", "20", "30"]
    assert land["cenarios"]["precipitacoes_mm"] == [10.0, 20.0, 30.0] and sorted(land["cenarios"]["totais_m3"]) == ["10", "20", "30"]
    assert res["precipitacao_de_referencia_mm"] == 30.0
    residuos = []
    for p in PROPRIOS:
        t = p.read_text(encoding="utf-8")
        for m in re.finditer(r"(?<![\d.,])60 ?mm|data-p=['\"]60['\"]|10, 30 e 60|10, 30 ou 60|\[10, 30, 60\]|\"60\": ?\{", t):
            residuos.append(f"{p.relative_to(ST)}: {t[max(0, m.start() - 30):m.end() + 10]!r}")
    assert not residuos, residuos


def test_the_reference_rain_is_described_as_the_75th_percentile_and_not_the_mean():
    res = json.loads((ST / "data/resultados_poa.json").read_text())
    c = res["chuva"]
    assert round(100 * c["cenarios_na_distribuicao"]["30"]["percentil_do_total_por_evento"]) == 75
    assert "percentil 75" in c["leitura_da_referencia"] and "Não é a média histórica" in c["leitura_da_referencia"]
    assert abs(c["total_por_evento_mm"]["p75"] - 29.9) < 0.15 and abs(c["total_por_evento_mm"]["media"] - 22.8) < 0.15
    assert "reanálise" in c["fonte"].lower() or "era5" in c["fonte"].lower()
    js = ler("mapa.js")
    assert "percentil 75" in js and "uniforme" in ler("simulador.js").lower() and "uniforme" in ler("fase3.js").lower()


def test_the_interface_is_light_only_with_no_dark_palette_or_theme_switch():
    for p in PROPRIOS:
        t = p.read_text(encoding="utf-8")
        assert "prefers-color-scheme" not in t, p.relative_to(ST)
        assert "data-theme" not in t and "prefers-color" not in t, p.relative_to(ST)
    assert "color-scheme:light" in ler("style.css")
    for pagina in ("index.html", "inicio/index.html", "inicio/celular.html"):
        assert '<meta name="color-scheme" content="light">' in ler(pagina), pagina
    arq = ST.parent / "arquivo"                         # as peças arquivadas também seguem o modo claro, para a retomada
    for pagina in ("pwa/index.html", "inicio/aplicativo.html"):
        assert '<meta name="color-scheme" content="light">' in (arq / pagina).read_text(encoding="utf-8"), pagina
    assert "prefers-color-scheme" not in (arq / "pwa" / "pwa.css").read_text(encoding="utf-8")
    base = ler("mapa-base.js")
    assert "function escuro() { return false; }" in base and "matchMedia" not in base
    assert "estilo-escuro" not in (arq / "pwa-painel" / "sw.js").read_text(encoding="utf-8")


def test_the_active_panel_has_no_demo_mode_and_the_synthetic_notice_stays_with_the_archived_panel():
    js, html = ler("painel.js"), ler("index.html")
    assert "Sobre os dados desta visualização" not in js and "Demonstração" not in html and "Dados reais" not in html and 'id="modo"' not in html
    assert "api(" not in js and 'fetch("api/' not in js       # o painel atual não chama a API do servidor: resultados, mapa e simulador vêm de arquivos estáticos
    # o aviso de dados sintéticos continua guardado no painel estadual arquivado, para a retomada
    arquivado = (ST.parent / "arquivo" / "painel-estadual" / "painel.js").read_text(encoding="utf-8")
    i = arquivado.index("Sobre os dados desta visualização")
    aviso = arquivado[i:arquivado.index('";', i)]
    assert "indicadores" in aviso and "metodologia do estudo" in aviso and "sintéticas" in aviso and "não representam registros reais" in aviso
    # a chuva sintética do servidor não alimenta os resultados: eles vêm de arquivos gerados dos Parquets e da série ERA5
    res = (RAIZ / "src/flooding_mapping/resultados.py").read_text(encoding="utf-8")
    assert "demonstracao" not in res and "sintetica" not in res.lower().replace("sintético", "")


def test_the_landing_states_the_narrative_the_scenarios_and_what_is_not_predicted():
    h = ler("inicio/index.html")
    assert "Como a chuva transforma o território?" in h
    assert "Da chuva à estimativa de áreas com maior propensão ao acúmulo de água." in h
    assert "cenários de 10, 20 e 30 mm" in h
    assert re.search(r"Não são previsão de alagamentos, de profundidade nem de duração da água", h)
    assert "planejamento preventivo" in h


@pytest.mark.parametrize("pagina", ["resultados.js", "simulador.js", "fase3.js", "mapa.js", "inicio/index.html"])
def test_no_text_promises_prediction_of_depth_extent_or_duration_without_denying_it(pagina):
    t = re.sub(r"\s+", " ", ler(pagina)).lower()
    for frase in ("prevê alagamento", "prevê a profundidade", "prevemos", "rota segura", "área segura", "garante", "vai alagar"):
        for m in re.finditer(re.escape(frase), t):
            assert "não" in t[max(0, m.start() - 80):m.start()], (pagina, frase)


def test_results_tab_sections_name_the_map_dimension_they_belong_to():
    t = ler("resultados.js")
    for rotulo in ("Dimensão A · Geração (urbanização)", "Dimensão A · Geração (vegetação)", "Dimensões B e C · Concentração e topografia", "Dimensão D · Drenagem"):
        assert rotulo in t
    assert "<p class='rs-tag'>Dimensão B</p>" not in t and "<p class='rs-tag'>Dimensão C</p>" not in t


# ------------------------------------------------------------------------------------------------ acessibilidade e mapa-base (Etapa 3)
def _luminancia(h):
    r, g, b = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4   # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contraste(a, b):
    la, lb = sorted([_luminancia(a), _luminancia(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_dimension_tags_keep_four_and_a_half_to_one_after_darkening_the_dimension_colour():
    cores = re.search(r"DIM_COR = \{(.*?)\}", ler("resultados.js"), re.S).group(1)
    dim = dict(re.findall(r'(\w+): ?"(#[0-9a-fA-F]{6})"', cores))
    assert set(dim) >= {"A", "B", "C", "D"}
    assert "color-mix(in srgb, var(--dim, var(--accent)) 68%, #000)" in ler("style.css")
    for k, h in dim.items():
        escura = "#" + "".join(f"{round(int(h.lstrip('#')[i:i + 2], 16) * 0.68):02x}" for i in (0, 2, 4))
        assert _contraste(escura, "#f3f7f9") >= 4.5, (k, h, escura)
    assert _contraste("#1b2630", "#dedbd1") >= 4.5          # a linha selecionada das tabelas usa a cor de texto principal


def test_landmarks_table_headers_and_regions_that_axe_flagged_are_fixed():
    html = ler("index.html")
    assert "<main id=\"conteudo\">" in html and html.count("</main>") == 1 and 'id="cores"' not in html
    for js in ("resultados.js", "simulador.js"):
        assert "<th scope='col'></th>" not in ler(js), js
    assert ".sr-only" in ler("style.css")
    assert "<aside" not in ler("inicio/index.html") and 'role="note"' in ler("inicio/index.html")
    assert 'setAttribute("tabindex", "0")' in ler("inicio/estudo.js")


def test_the_basemap_location_is_configurable_for_a_bucket_and_defaults_to_the_local_server():
    cfg, base, html = ler("config-dados.js"), ler("mapa-base.js"), ler("index.html")
    assert 'mapa: "/mapa/rs.pmtiles"' in cfg                                   # padrão: o servidor local, como antes
    assert "window.FM_DADOS.mapa" in base and '"/mapa/rs.pmtiles"' in base         # o mapa-base lê a configuração e mantém o padrão
    assert html.index('src="config-dados.js"') < html.index('src="mapa-base.js"')   # a configuração é carregada antes
    assert "https://" not in cfg.split("window.FM_DADOS = {")[1].split("base:")[0].replace("https://dados.exemplo.org", "")   # nenhuma URL de produção no padrão


def test_the_label_fonts_are_versionable_and_data_tiles_stay_ignored():
    import shutil
    import subprocess
    if not shutil.which("git"):
        return
    raiz = Path(__file__).resolve().parents[1]
    fontes = sorted((ST / "vendor/mapa/fontes").rglob("*.pbf"))
    assert fontes, "as fontes dos rótulos do mapa-base existem"
    ign = subprocess.run(["git", "check-ignore", *map(str, fontes)], cwd=raiz, capture_output=True, text=True)
    assert ign.returncode == 1 and ign.stdout == "", "fontes dos rótulos estão ignoradas pelo .gitignore (clone limpo sem rótulos): " + ign.stdout[:200]
    for dado in ("data/processed/fase3_web/tiles/13/1/1.pbf", "data/interim/qualquer.pbf"):
        assert subprocess.run(["git", "check-ignore", "-q", dado], cwd=raiz, capture_output=True).returncode == 0, dado
    assert sum(f.stat().st_size for f in fontes) < 2_000_000                       # só as fontes, nunca dado pesado


def test_the_experience_no_longer_suggests_operational_follow_up():
    for pagina in ("index.html", "painel.js"):
        t = ler(pagina)
        for frase in ("monitoramento regional", "mobilidade preventiva", "Operação urbana", "Inteligência territorial", "Instalar aplicativo"):
            assert frase not in t, (pagina, frase)
    assert "Estimativas de estudo, não previsão de alagamentos" in ler("index.html")
