"""PWA arquivado (src/flooding_mapping/app/arquivo/): as peças guardadas continuam coerentes entre si (para a retomada da frente de monitoramento) e a aplicação atual não é instalável."""
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "src/flooding_mapping/app/static"
ARQ = ROOT / "src/flooding_mapping/app/arquivo"
PAINEL = ARQ / "pwa-painel"             # sw.js, manifest.webmanifest e instalar.js da aplicação de análise instalável
PAINEL_ESTADUAL = ARQ / "painel-estadual"   # snapshot do painel de duas escalas (territorios.json arquivado)
# Dados estaduais que o PWA arquivado pré-carregava e que saíram do Git (licença de DAER, IBGE e S2iD não confirmada); ficam só no disco local, em data/raw/arquivo_estadual/.
FORA_DO_GIT = {"data/cobertura_rs.json", "data/impacto_rs.json", "data/municipios.geojson", "data/rodovias.geojson", "data/ocorrencias.json"}
SW = (PAINEL / "sw.js").read_text()


def achar(rel):
    """Onde o arquivo estaria depois de restaurado: a interface atual, a raiz do arquivo ou a pasta do painel instalável."""
    for base in (STATIC, ARQ, PAINEL, PAINEL_ESTADUAL):
        if (base / rel).exists():
            return base / rel
    return None


def lista(nome):
    m = re.search(rf"var {nome} = \[(.*?)\];", SW, re.S)
    return re.findall(r'"([^"]+)"', m.group(1))


def dimensoes_png(p):
    b = p.read_bytes()
    assert b[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", b[16:24])


# ---------------------------------------------------------------- a aplicação atual não é um PWA
def test_the_current_application_is_not_installable_and_has_no_install_prompt():
    html = (STATIC / "index.html").read_text()
    assert 'rel="manifest"' not in html and 'id="instalar"' not in html and "instalar.js" not in html and "Instalar aplicativo" not in html
    assert "aviso-conexao" not in html and "aviso-versao" not in html and "pwa/" not in html
    assert not (STATIC / "manifest.webmanifest").exists() and not (STATIC / "sw.js").exists() and not (STATIC / "instalar.js").exists() and not (STATIC / "pwa").exists()
    assert not list(STATIC.rglob("*.webmanifest"))


def test_the_application_unregisters_the_old_service_worker_instead_of_registering_one():
    js = (STATIC / "painel.js").read_text()
    assert "limparServiceWorkerAntigo" in js and "r.unregister()" in js and 'indexOf("fm-app-") === 0' in js
    for f in STATIC.glob("*.js"):
        assert "serviceWorker.register" not in f.read_text(), f.name


def test_the_landing_no_longer_points_to_the_citizen_app_or_the_pwa():
    for f in (STATIC / "inicio").glob("*.html"):
        t = f.read_text()
        assert "../pwa/" not in t and "aplicativo.html" not in t and "Aplicativo (PWA)" not in t, f.name
    assert not (STATIC / "inicio" / "aplicativo.html").exists()


def test_the_archive_keeps_everything_that_left_the_current_experience():
    for rel in ("README.md", "sw-mapa.js", "pwa/index.html", "pwa/pwa.js", "pwa/dados.js", "pwa/avisos.js", "pwa/pwa.css", "pwa/sw.js", "pwa/manifest.webmanifest",
                "pwa/icon-192.png", "pwa/icon-512.png", "pwa-painel/sw.js", "pwa-painel/manifest.webmanifest", "pwa-painel/instalar.js", "inicio/aplicativo.html", "inicio/inicio.css", "inicio/inicio.js",
                "painel-estadual/index.html", "painel-estadual/painel.js", "painel-estadual/mapa.js", "painel-estadual/mapa2d.js", "painel-estadual/territorio.js", "painel-estadual/logic.js",
                "painel-estadual/style.css", "painel-estadual/territorios.yaml", "painel-estadual/data/territorios.json", "site_estadual.py"):
        assert (ARQ / rel).is_file(), rel
    texto = (ARQ / "README.md").read_text()
    assert "monitoramento em tempo real" in texto and "FM_ARQUIVO_PWA" in texto
    assert "data/raw/arquivo_estadual" in texto and "licença não confirmada" in texto      # o que saiu do Git e por quê


# ---------------------------------------------------------------- coerência das peças arquivadas
def test_manifest_is_installable_and_stays_inside_its_scope():
    m = json.loads((PAINEL / "manifest.webmanifest").read_text())
    assert m["display"] == "standalone" and m["lang"] == "pt-BR" and m["name"] and m["short_name"]
    assert m["scope"] == "./" and m["start_url"].startswith("./") and m["id"]
    tamanhos = set()
    for i in m["icons"]:
        w, h = dimensoes_png(ARQ / i["src"])
        assert f"{w}x{h}" == i["sizes"], i
        tamanhos.add(i["sizes"])
    assert {"192x192", "512x512"} <= tamanhos and "maskable" in {i["purpose"] for i in m["icons"]}


def test_every_precached_file_exists_so_the_install_cannot_fail():
    faltam = []
    for rel in lista("CASCA"):
        if not (achar(rel) or (rel.endswith("/") and achar(rel + "index.html")) or rel == "./" or rel in FORA_DO_GIT):
            faltam.append(rel)
    assert faltam == [], faltam


def test_precache_holds_only_the_light_interface_and_study_results():
    for rel in lista("CASCA"):
        assert not rel.startswith(("fase3/", "drenagem/", "api/", "mapa/")), rel
        p = achar(rel)
        if p is not None and p.is_file():
            assert p.stat().st_size < 3_000_000, f"{rel} é grande demais para a pré-carga"
    assert sum(achar(r).stat().st_size for r in lista("CASCA") if achar(r) is not None and achar(r).is_file()) < 6_000_000


def test_what_describes_now_or_weighs_tens_of_megabytes_is_never_stored():
    nunca = lista("NUNCA")
    assert {"api/", "previsao_72h.json", "bloqueios.json", "fase3/", "drenagem/"} <= set(nunca)
    assert re.search(r"if \(naoGuardar\(url\)[^\n]*\) return;", SW), "esses caminhos não passam pelo cache"


def test_cache_versions_do_not_delete_each_others_caches():
    assert re.search(r'var VERSAO = "fm-app-[^"]+"', SW)
    pwa = (ARQ / "pwa/sw.js").read_text()
    assert re.search(r'var VERSAO = "fm-pwa-[^"]+"', pwa)
    assert 'k.indexOf("fm-app-") === 0 && k !== VERSAO' in SW and 'indexOf("fm-pwa-") === 0 && k !== VERSAO' in pwa
    assert "fm-mapa-" not in SW.split("self.addEventListener(\"activate\"")[1].split("});")[0], "o cache do mapa-base é compartilhado e não é apagado por versão"
    assert 'importScripts("sw-mapa.js")' in SW and 'importScripts("../sw-mapa.js")' in pwa and "function mapaComCache" not in SW and "function mapaComCache" not in pwa


def test_saved_copy_is_marked_and_the_page_says_so():
    assert "X-FM-Copia-Salva" in SW and "X-FM-Copia-Salva" in (STATIC / "resultados.js").read_text()
    assert "cópia salva" in (STATIC / "resultados.js").read_text()


def test_offline_notice_does_not_promise_what_needs_the_network():
    js = (PAINEL / "instalar.js").read_text()
    t = re.search(r'TEXTO_OFFLINE = "([^"]+)"', js).group(1)
    for dep in ("escoamento", "drenagem", "previsão", "bloqueios", "ocorrências", "rotas"):
        assert dep in t.split("Dependem de conexão")[1]
    assert "última cópia salva" in t


def test_build_does_not_publish_the_archived_files():
    b = (STATIC.parent / "build.py").read_text()
    for f in ("sw.js", "sw-mapa.js", "manifest.webmanifest", "instalar.js"):
        assert f'"{f}"' not in b, f
    assert '"simulador.js"' in b and (STATIC / "simulador.js").exists()
    assert 'STATIC / "pwa"' not in b


def test_only_the_panel_page_may_be_framed_and_only_by_the_same_origin():
    from flooding_mapping import servidor
    assert "frame-ancestors 'none'" in servidor.CSP and "frame-ancestors 'none'" in servidor.CSP_SW
    assert "frame-ancestors 'self'" in servidor.CSP_PAINEL and servidor.CSP_PAINEL.replace("frame-ancestors 'self'", "frame-ancestors 'none'") == servidor.CSP
    fonte = (ROOT / "src/flooding_mapping/servidor.py").read_text()
    assert 'CSP_PAINEL if alvo == raiz.resolve() / "index.html"' in fonte
