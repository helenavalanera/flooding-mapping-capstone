"""Landing científica: números rastreáveis às fontes, geração reproduzível, afirmações dentro do que o estudo demonstra, links e acessibilidade básica."""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
INICIO = RAIZ / "src/flooding_mapping/app/static/inicio"
sys.path.insert(0, str(RAIZ / "tools"))
real = pytest.mark.skipif(not ((RAIZ / "reports/qa/fase3_execucao.json").exists() and (RAIZ / "data/processed/fase3_web/meta.json").exists() and (RAIZ / "data/processed/drenagem_web/meta.json").exists()),
                          reason="relatórios e dados derivados do estudo não disponíveis neste ambiente")


class Coleta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs, self.imgs, self.scripts, self.h1, self.num, self.recursos = set(), [], [], [], 0, [], []

    def handle_starttag(self, tag, a):
        a = dict(a)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a":
            self.hrefs.append(a.get("href", ""))
        if tag == "img":
            self.imgs.append(a)
        if tag == "script":
            self.scripts.append(a)
        if tag == "h1":
            self.h1 += 1
        if tag == "article" and "data-chave" in a:
            self.num.append(a)
        if tag in ("link", "script", "img") and (a.get("src") or a.get("href", "")).startswith(("http://", "https://")):
            self.recursos.append(a.get("src") or a.get("href"))


@pytest.fixture(scope="module")
def pagina():
    c = Coleta()
    texto = (INICIO / "index.html").read_text(encoding="utf-8")
    c.feed(texto)
    return texto, c


def test_the_page_is_structurally_sound_and_loads_nothing_from_outside(pagina):
    texto, c = pagina
    assert texto.lstrip().startswith("<!doctype html>") and '<html lang="pt-BR">' in texto and c.h1 == 1
    assert not c.recursos, c.recursos                                                   # sem fontes, scripts ou imagens de terceiros
    assert all(s.get("src") or s.get("type") == "application/json" for s in c.scripts)    # nenhum script em linha: a CSP do servidor só permite o próprio site
    assert not re.search(r"\{\{[A-Z_]+\}\}", texto)


def test_the_eight_sections_exist_in_order_and_every_anchor_resolves(pagina):
    texto, c = pagina
    ordem = ["hero", "problema", "dimensoes", "resultados", "numeros", "metodologia", "interpretacao", "fontes", "sobre"]
    pos = [texto.index(f'id="{i}"') for i in ordem]
    assert pos == sorted(pos)
    internos = [h[1:] for h in c.hrefs if h.startswith("#") and len(h) > 1]
    assert internos and all(i in c.ids for i in internos), [i for i in internos if i not in c.ids]
    assert re.findall(r'<p class="sec-num"><span>(\d\d)</span> ([^<]*)', texto) == [("01", "O problema"), ("02", "As dimensões"), ("03", "Resultados"), ("04", "Indicadores municipais"), ("05", "Metodologia"), ("06", "Interpretação"), ("07", "Fontes e documentação"), ("08", "Sobre o projeto")]
    assert re.findall(r'<ol class="ancoras">(.*?)</ol>', texto, re.S)[0].count("<a ") == 8          # problema, dimensões, resultados, números, metodologia, interpretação, fontes e sobre


def test_relative_links_and_images_point_to_files_that_exist(pagina):
    _, c = pagina
    for h in c.hrefs:
        if h.startswith(("http", "#", "mailto:")):
            continue
        alvo = (INICIO / h.split("?")[0].split("#")[0]).resolve()
        if h.startswith("../"):
            assert alvo.exists() or h.startswith(("../?", "../pwa/")), h                  # o painel e o PWA são rotas do servidor, não arquivos desta pasta
        else:
            assert alvo.exists(), h
    for i in c.imgs:
        assert (INICIO / i["src"]).exists() and i.get("alt", "").strip(), i               # toda imagem existe e tem descrição
        assert i.get("width") and i.get("height"), i["src"]                                 # dimensões para o layout não saltar quando a imagem carrega


def test_the_hero_asks_the_question_and_never_claims_real_time_prediction(pagina):
    texto, _ = pagina
    assert "Dada uma chuva, onde a água tende a se acumular?" in texto and "Space Tech Bootcamp 2026" in texto and "Porto Alegre" in texto
    assert "Abrir o mapa" in texto and "Ver os resultados" in texto
    proibidos = json.loads(re.search(r"TERMOS_PROIBIDOS = (\[.*?\]);", (RAIZ / "src/flooding_mapping/app/static/fase3-dados.js").read_text(encoding="utf-8"), re.S).group(1).replace("\n", " "))
    visivel = re.sub(r"<script.*?</script>", "", texto, flags=re.S).lower()
    for t in proibidos:
        assert t not in visivel, t
    for t in ("previsão em tempo real", "prevê alagamentos", "alerta em tempo real"):
        for m in re.finditer(t, visivel):
            assert "não" in visivel[max(0, m.start() - 60):m.start()], t                      # só aparece negado


def test_the_negative_result_the_caveat_and_the_exploratory_nature_are_stated(pagina):
    texto, _ = pagina
    ressalva = ("Este estudo apresenta estimativas geoespaciais do escoamento superficial e das condições topográficas associadas à concentração e à retenção de água. Os resultados apoiam a análise territorial e o planejamento preventivo, "
                "mas não constituem previsão de alagamentos nem estimativa de profundidade ou duração da inundação.")
    assert texto.count(ressalva) == 2                                                          # no início e nos resultados
    for t in ("não mostrou ganho robusto", "Nem a física nem o aprendizado de máquina superaram a regra de terreno já em uso", "comparação exploratória", "cenários de cálculo", "Estimativa, não previsão"):
        assert t in texto, t


def test_the_dimensions_are_named_and_explained_in_plain_language_with_their_caveats(pagina):
    texto, _ = pagina
    for t in ("Geração potencial de escoamento", "Para onde a água pode escorrer?", "Contribuição acumulada", "Onde o escoamento que vem de outras áreas pode se concentrar?",
              "Retenção topográfica", "Onde o formato do terreno pode favorecer a retenção?", "Drenagem cadastrada", "Onde existe rede pluvial registrada?",
              "GeoAI experimental: fração construída estimada", "As camadas não formam um índice único", "Não é vazão (volume por tempo)",
              "Esse valor não é a profundidade real de um alagamento", "a ausência de registro não significa que não exista drenagem"):
        assert t in texto, t


@real
def test_every_number_card_matches_its_source_report(pagina):
    _, c = pagina
    assert len(c.num) == 12
    for a in c.num:
        rel, _, caminho = a["data-fonte"].partition(" · ")
        if "*" in caminho or "/" in caminho or "(" in rel:
            continue                                                                       # fontes compostas (várias camadas): conferidas no teste de geração
        d = json.loads((RAIZ / rel).read_text())
        for p in caminho.split("."):
            d = d[int(p)] if isinstance(d, list) else d[p]
        assert float(a["data-valor"]) == pytest.approx(float(d), rel=1e-12), a["data-chave"]
    grupos = re.findall(r'id="num-(\w+)"', (INICIO / "index.html").read_text())
    assert grupos == ["processamento", "metodologico", "validacao"]                         # os três tipos de número não se misturam


@real
def test_each_card_has_unit_definition_origin_context_and_limitation(pagina):
    texto, _ = pagina
    cartoes = re.findall(r'<article class="num".*?</article>', texto, re.S)
    assert len(cartoes) == 12
    for c in cartoes:
        for parte in ("class=\"unid\"", "<dt>Contexto</dt>", "<dt>Limitação</dt>", "<dt>O que é</dt>", "<dt>De onde vem</dt>"):
            assert parte in c
        assert re.search(r'class="unid">[^<]+<', c) and "<code>reports/qa/" in c or "<code>" in c


@real
def test_the_page_is_exactly_what_the_generator_produces_from_the_reports():
    import gerar_landing as g

    r = g.montar(figuras=False)
    assert r["html"] == (INICIO / "index.html").read_text(encoding="utf-8")
    dados = json.loads((INICIO / "dados.json").read_text())
    assert [n["chave"] for n in dados["numeros"]] == [n["chave"] for n in r["dados"]["numeros"]]
    assert dados["cenarios"]["precipitacoes_mm"] == [10.0, 20.0, 30.0]


@real
def test_the_scenario_data_come_from_the_engine_and_scale_linearly():
    d = json.loads((INICIO / "dados.json").read_text())["cenarios"]
    t = d["totais_m3"]
    for pacote in ("metodo1", "limites_fisicos", "referencia_analoga"):
        for lim in ("min_m3", "max_m3"):
            assert t["20"][pacote][lim] == pytest.approx(2 * t["10"][pacote][lim], rel=1e-9) and t["30"][pacote][lim] == pytest.approx(3 * t["10"][pacote][lim], rel=1e-9)
    assert t["30"]["limites_fisicos"]["min_m3"] == 0 and t["30"]["metodo1"]["max_m3"] > t["30"]["metodo1"]["min_m3"] > 0


def test_the_weight_of_the_page_is_proportionate():
    imagens = sum(p.stat().st_size for p in (INICIO / "img/estudo").glob("*") if p.is_file())
    assert imagens < 3_000_000 and (INICIO / "index.html").stat().st_size < 150_000
    assert (INICIO / "estudo.css").stat().st_size < 40_000 and (INICIO / "estudo.js").stat().st_size < 12_000
    assert not list((INICIO / "img/estudo").glob("*.tmp.png"))


def test_the_page_uses_the_municipal_cut_and_gives_each_card_one_denominator(pagina):
    texto, _ = pagina
    rec = json.loads((RAIZ / "src/flooding_mapping/app/static/data/recorte_municipal_poa.json").read_text(encoding="utf-8"))
    total = f"{rec['trechos_no_municipio']:,}".replace(",", ".")
    assert f"<dt>{total}</dt><dd>trechos de rua analisados em Porto Alegre" in texto and f"<b>{total}</b><span class=\"n-rot\">trechos analisados</span>" in texto and "176.836 trechos de rua" not in texto
    assert "cidades vizinhas" in texto                                                                        # a landing diz que as vias de fora ficam de fora
    for velho in ("2.919", "38.976 de", "98,3%", "57,0%", "2% dos trechos de menor"):
        assert velho not in texto, velho                                                                       # números da malha inteira, que incluía vias de fora


def test_zero_missing_data_and_missing_infrastructure_are_told_apart(pagina):
    texto, _ = pagina
    assert "Zero não é ausência de dado" in texto and "tracejados no mapa" in texto and "não prova que não exista" in texto
    assert "Não é a profundidade que a água atingiria" in texto and "mais de 0 até 0,5 m" in texto and "0,0 a 0,5 m" not in texto


def test_promises_about_the_interactive_map_follow_what_is_published(pagina):
    texto, _ = pagina
    cfg = (RAIZ / "src/flooding_mapping/app/static/config-dados.js").read_text(encoding="utf-8")
    publicado = 'fase3: "https://' in cfg
    assert ("Explore o mapa e compare chuvas" in texto) == publicado and ("Abrir o simulador no mapa" in texto) == publicado
    assert publicado or "dependem da publicação dos arquivos derivados, em preparação" in texto


def test_the_four_headline_numbers_are_the_current_ones_and_come_from_the_generated_data(pagina):
    texto, _ = pagina
    for esperado in ("<b>143.149</b>", "<b>22%</b>", "31.545 trechos apresentam depressões", "<b>70,3%</b>", "<b>49,8 m³</b>", "17,3%"):
        assert esperado in texto, esperado


def test_the_technology_section_names_only_what_the_pipeline_really_uses(pagina):
    texto, _ = pagina
    for usado in ("Copernicus DEM GLO-30", "AWS Terrain Tiles", "Profill 2022", "OpenStreetMap e Protomaps", "Open-Meteo", "Python", "MapLibre, Leaflet e PMTiles", "Rasterio", "GDAL (ogr2ogr)", "scikit-learn"):
        assert usado in texto, usado
    antes_do_geoai = texto.split("Sentinel-2 e AlphaEarth (só no GeoAI)")[0].split('id="metodologia"')[1]
    assert "Sentinel" not in antes_do_geoai and "AlphaEarth" not in antes_do_geoai                    # Sentinel-2 e AlphaEarth só aparecem contextualizados como GeoAI
    assert "não são fontes do motor principal" in texto.lower().replace("não são", "não são")
