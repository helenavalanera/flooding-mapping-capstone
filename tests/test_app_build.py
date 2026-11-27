"""Montagem do site estático de Porto Alegre (flooding_mapping.app.build): só a interface atual, sem modelo, previsão, rodovias nem bloqueios.

Os testes da montagem de duas escalas (Rio Grande do Sul), arquivada, estão em ``tests/arquivo/test_site_estadual.py`` (ignorados).
"""
import json
import re

import pytest

from flooding_mapping.app import build

# Arquivos carregados pelo painel ativo. Ficam de fora da varredura de termos: ``logic.js``, biblioteca de funções puras compartilhada com o PWA arquivado, que traz
# rótulos de rodovia e S2iD em funções que o painel atual não chama; e ``mapa-base.js``, cujo comentário diz que o mapa-base é um recorte do OpenStreetMap que cobre
# o estado inteiro (arquivo rs.pmtiles), usado só como fundo visual.
ARQUIVOS_DO_PAINEL = ("painel.js", "territorio.js", "mapa.js", "mapa2d.js", "resultados.js", "simulador.js", "fase3.js", "fase3-dados.js", "drenagem.js", "config-dados.js", "data/territorio_poa.json")
TERMOS_ESTADUAIS = re.compile(r"DAER|S2iD|CPRv|rodovi|bloqueio|munic[ií]pio|Rio Grande do Sul|estadual|estaduais|previs[aã]o de 72|ocorr[eê]ncias reportadas", re.I)


def make_site(tmp_path, **camadas):
    out = tmp_path / "site"
    return out, build.build_site(out, **camadas)


def test_site_has_the_page_the_data_and_no_jekyll_marker(tmp_path):
    out, published = make_site(tmp_path)
    for name in ("index.html", "painel.html", "inicio/index.html", "mapa2d.js", "logic.js", "style.css", ".nojekyll", "data/resultados_poa.json", "data/territorio_poa.json"):
        assert (out / name).exists(), name
    assert published == {"territorio": "poa", "cabecalhos": True}


def test_the_site_ships_nothing_from_the_state_front(tmp_path):
    out, _ = make_site(tmp_path)
    for ausente in ("previsao_72h.json", "bloqueios.json", "data/rodovias.geojson", "data/municipios.geojson", "data/cobertura_rs.json", "data/impacto_rs.json", "data/ocorrencias.json",
                    "data/territorios.json", "pwa", "sw.js", "sw-mapa.js", "manifest.webmanifest", "instalar.js", "inicio/aplicativo.html", "painel-estadual", "site_estadual.py"):
        assert not (out / ausente).exists(), ausente
    assert not list(out.rglob("*.parquet")) and not list(out.rglob("*.joblib")) and not list(out.rglob("*.geojson"))


def test_the_active_panel_has_no_state_territory_forecast_mobility_or_occurrence_front(tmp_path):
    out, _ = make_site(tmp_path)
    html = (out / "painel.html").read_text()
    for aba in ("geral", "previsao", "mobilidade", "ocorrencias"):
        assert f'data-aba="{aba}"' not in html and f'id="vista-{aba}"' not in html, aba
    assert re.findall(r'data-aba="(\w+)"', html) == ["resultados", "mapa", "simulador", "proveniencia"]
    assert 'data-territorio=' not in html and 'id="territorios"' not in html and 'id="modo"' not in html
    for nome in ARQUIVOS_DO_PAINEL:
        texto = (out / nome).read_text(encoding="utf-8")
        achados = sorted({m.group(0) for m in TERMOS_ESTADUAIS.finditer(texto)})
        # "município" e "estadual" só podem aparecer para dizer que o recorte estadual está arquivado
        assert not achados or all(a.lower() in ("estadual", "rio grande do sul") for a in achados) and "arquivad" in texto, (nome, achados)
    assert TERMOS_ESTADUAIS.search(html) is None


def test_every_file_the_page_loads_exists_in_the_site(tmp_path):
    out, _ = make_site(tmp_path)
    html = (out / "painel.html").read_text()      # a raiz (index.html) é a porta de entrada; o painel é painel.html
    local = [m for m in re.findall(r'(?:src|href)="([^"]+)"', html) if not m.startswith(("http", "data:", "inicio/", "#"))]
    assert {"style.css", "logic.js", "mapa.js", "mapa2d.js", "painel.js", "territorio.js", "config-dados.js", "mapa-base.js", "icone-192.png"} <= set(local) and all((out / m).exists() for m in local)
    assert local.index("config-dados.js") < local.index("mapa-base.js")      # o mapa-base lê onde está o arquivo do mapa em config-dados.js
    assert "app.js" not in local
    assert 'fetch("data/territorio_poa.json"' in (out / "territorio.js").read_text()


def test_the_site_ships_the_single_territory_with_only_the_layers_of_the_study(tmp_path):
    out, _ = make_site(tmp_path)
    territorios = json.loads((out / "data/territorio_poa.json").read_text())["territorios"]
    assert set(territorios) == {"poa"} and territorios["poa"]["nome"] == "Porto Alegre" and territorios["poa"]["escala"] == "municipal"
    camadas = {c for cap in territorios["poa"]["capacidades"].values() for c in cap["camadas"]}
    assert camadas == {"relevo", "escoamento_fase3", "drenagem_cadastro"}
    desenhadas = set(re.findall(r"^    (\w+): \{ rotulo:", (out / "mapa.js").read_text(), re.M))
    assert camadas == desenhadas        # toda camada prometida é desenhada, e nenhuma desenhada fica sem promessa


def test_derived_layers_are_published_only_when_asked(tmp_path):
    fase3, dren = tmp_path / "f3", tmp_path / "dr"
    for p in (fase3, dren):
        p.mkdir()
        (p / "meta.json").write_text("{}")
    out, published = make_site(tmp_path, fase3=fase3, drenagem=dren)
    assert published == {"territorio": "poa", "fase3": True, "drenagem": True, "cabecalhos": True} and (out / "fase3/meta.json").exists() and (out / "drenagem/meta.json").exists()


def test_nothing_secret_reaches_the_published_site(tmp_path):
    out, _ = make_site(tmp_path)
    pattern = re.compile(r"R2_[A-Z_]+|SECRET|access[_-]?key|api[_-]?key|token|cb1_[A-Za-z0-9_]{10,}", re.I)
    leaks = [p.name for p in out.rglob("*") if p.is_file() and p.suffix not in {".webp", ".png", ".woff2", ".pbf"} and pattern.search(p.read_text(errors="ignore"))]   # imagens são binárias: bytes ao acaso podem imitar um padrão
    assert leaks == []


def test_the_site_entry_is_the_landing_and_the_panel_keeps_its_links_and_the_pwa_is_not_shipped(tmp_path):
    out, _ = make_site(tmp_path)
    entrada, js = (out / "index.html").read_text(), (out / "entrada.js").read_text()
    assert 'src="entrada.js"' in entrada and 'href="inicio/"' in entrada and "painel.html" in entrada          # a raiz é só uma porta
    assert 'location.replace(abrePainel ? "painel.html" + location.search + location.hash : "inicio/")' in js   # sem pedido de painel, vai à landing
    assert "painel=" in js and "location.hash.length > 1" in js                                                   # links antigos (?painel=1 e #poa/mapa) seguem para o painel
    assert (out / "inicio" / "index.html").exists() and (out / "painel.html").exists() and (out / "icone-192.png").exists()
    assert 'rel="manifest"' not in (out / "painel.html").read_text()
    assert "../pwa/" not in (out / "inicio" / "index.html").read_text()


def test_the_archived_pwa_escapes_what_it_shows_and_never_watches_the_position():
    js = (build.STATIC.parent / "arquivo" / "pwa" / "pwa.js").read_text()    # PWA arquivado (app/arquivo/README.md)
    assert "geolocation.watchPosition" not in js and js.count("geolocation.getCurrentPosition") == 1   # one position, foreground only
    assert "Lg.esc" in js and js.count("esc(") > 30
    assert not re.search(r"(api[_-]?key|token|secret)", js + (build.STATIC.parent / "arquivo" / "pwa" / "dados.js").read_text(), re.I)


def test_the_map_library_is_pinned_with_an_integrity_hash_and_no_other_3d_engine_is_loaded():
    html = (build.STATIC / "index.html").read_text()
    tag = re.search(r'<script src="https://cdnjs\.cloudflare\.com/ajax/libs/maplibre-gl/(\d+\.\d+\.\d+)/maplibre-gl\.js"([^>]*)>', html)
    assert tag and re.fullmatch(r"\d+\.\d+\.\d+", tag.group(1)) and 'integrity="sha384-' in tag.group(2) and 'crossorigin="anonymous"' in tag.group(2)
    assert not re.search(r"three(\.min)?\.js|cesium|deck\.gl", html, re.I)


def test_free_text_from_the_data_is_escaped_by_the_page_not_trusted():
    js = (build.STATIC / "painel.js").read_text() + (build.STATIC / "mapa.js").read_text()
    assert "innerHTML" in js and js.count("Lg.esc(") > 8


def test_the_page_policy_lets_the_map_work_and_nothing_more():
    from flooding_mapping import servidor
    csp = dict(p.strip().split(" ", 1) for p in servidor.CSP.split(";") if p.strip())
    assert "'self'" in csp["worker-src"] and "blob:" in csp["worker-src"]     # o mapa precisa de workers blob
    assert "https://s3.amazonaws.com" in csp["connect-src"]          # as tiles de elevação do relevo 3D
    assert "openstreetmap.org" not in servidor.CSP                  # o mapa-base é um arquivo nosso, nunca um servidor de tiles de terceiros
    assert "'unsafe-eval'" not in servidor.CSP and csp["frame-ancestors"] == "'none'" and csp["script-src"] == "'self' https://cdnjs.cloudflare.com"


def test_the_site_build_imports_nothing_from_the_archived_state_front():
    import ast
    modulos = {n.module or "" for n in ast.walk(ast.parse((build.STATIC.parent / "build.py").read_text())) if isinstance(n, ast.ImportFrom)}
    assert not {m for m in modulos if re.search(r"collector|ingestion|inference|geospatial|layers|arquivo", m)}, modulos


def test_the_pages_headers_file_repeats_the_server_policy_and_the_security_headers(tmp_path):
    from flooding_mapping import servidor
    out, _ = make_site(tmp_path)
    h = (out / "_headers").read_text(encoding="utf-8")
    assert build.CSP == servidor.CSP and build.CSP_ENQUADRAVEL == servidor.CSP_PAINEL            # a mesma política do servidor local
    assert h.startswith("/*\n") and f"Content-Security-Policy: {build.CSP}" in h
    for linha in ("X-Content-Type-Options: nosniff", "Referrer-Policy: strict-origin-when-cross-origin", "Permissions-Policy: geolocation=(), camera=(), microphone=()"):
        assert f"  {linha}" in h
    assert "'unsafe-eval'" not in h and "frame-ancestors 'none'" in h and "https://s3.amazonaws.com" in h        # relevo 3D; nenhum motor de avaliação dinâmica
    assert max(len(x) for x in h.splitlines()) < 2000 and h.count("\n/") < 100                            # limites do Pages: 2.000 caracteres por linha e 100 regras


def test_the_pages_headers_let_only_the_entry_and_the_panel_be_framed_by_the_same_origin_and_drop_the_general_policy_there(tmp_path):
    out, _ = make_site(tmp_path)
    blocos = {}
    for bloco in re.split(r"\n(?=/)", (out / "_headers").read_text(encoding="utf-8").strip()):
        rota, *regras = bloco.splitlines()
        blocos[rota] = [r.strip() for r in regras]
    for rota in ("/", "/index.html", "/painel.html"):
        assert blocos[rota][0] == "! Content-Security-Policy"                                            # sem isso o Pages somaria as duas políticas e o quadro seguiria bloqueado
        assert f"Content-Security-Policy: {build.CSP_ENQUADRAVEL}" in blocos[rota] and "frame-ancestors 'self'" in blocos[rota][1]
    assert "frame-ancestors 'none'" in " ".join(blocos["/*"]) and "/inicio/*" not in blocos
    assert blocos["/vendor/*"] == ["Cache-Control: public, max-age=86400"]


def test_the_r2_origin_is_added_only_to_connect_and_img_sources_and_only_when_it_is_a_plain_https_origin(tmp_path):
    r2 = "https://dados.exemplo.org"
    h = build.cabecalhos(r2)
    for linha in (l for l in h.splitlines() if "Content-Security-Policy:" in l):
        d = dict(p.strip().split(" ", 1) for p in linha.split("Content-Security-Policy:", 1)[1].split(";") if p.strip())
        assert r2 in d["connect-src"].split() and r2 in d["img-src"].split() and r2 not in d["script-src"] and r2 not in d["default-src"]
    assert r2 not in build.cabecalhos() and build.com_origem_do_r2(build.CSP, None) == build.CSP
    for ruim in ("http://dados.exemplo.org", "https://dados.exemplo.org/mapa", "dados.exemplo.org", "https://x.org; script-src *", "https://*.exemplo.org"):
        with pytest.raises(SystemExit, match="origem https sem caminho"):
            build.cabecalhos(ruim)
    out = tmp_path / "s"
    build.build_site(out, r2_origem=r2)
    assert r2 in (out / "_headers").read_text(encoding="utf-8")
