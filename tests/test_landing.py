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


def test_the_five_sections_exist_in_order_and_every_anchor_resolves(pagina):
    texto, c = pagina
    ordem = ["hero", "apresentacao", "mapa", "cenarios", "resultados", "contato"]
    pos = [texto.index(f'id="{i}"') for i in ordem]
    assert pos == sorted(pos)
    internos = [h[1:] for h in c.hrefs if h.startswith("#") and len(h) > 1]
    assert internos and all(i in c.ids for i in internos), [i for i in internos if i not in c.ids]
    assert re.findall(r'<p class="sec-num"><span>(\d\d)</span> ([^<]*)', texto) == [("01", "Apresentação"), ("02", "Mapa"), ("03", "Simulador"), ("04", "Resultados"), ("05", "Contato")]
    assert re.findall(r'<ol class="ancoras">(.*?)</ol>', texto, re.S)[0].count("<a ") == 5          # só Apresentação, Mapa, Simulador, Resultados e Contato


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


def test_the_four_dimensions_are_named_and_explained_in_plain_language(pagina):
    texto, _ = pagina
    for t in ("Geração de escoamento", "água da chuva que não é absorvida pelo solo e escoa pela superfície", "Concentração do escoamento", "locais para onde a água da chuva tende a convergir",
              "Propensão topográfica à retenção", "áreas onde o relevo favorece o acúmulo de água", "Drenagem cadastrada", "rede de estruturas registradas para captar e conduzir a água da chuva",
              "acúmulo favorecido pelo relevo não é o mesmo que alagamento", "Não é vazão (volume por tempo)"):
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
