"""A configuração de produção contra a infraestrutura simulada: Pages com o _headers (CSP) e bucket do R2 (Range, gzip, CORS), no navegador. Precisa de Chrome e do pacote preparado."""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

RAIZ = Path(__file__).resolve().parents[1]
E2E = RAIZ / "tests/e2e"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(E2E))
VERSAO = "d-b7f6f03555d9"
PACOTE = RAIZ / "data/interim/r2_preparado" / VERSAO
FALTA = [c for c, ok in {"node": shutil.which("node"), "PLAYWRIGHT_CORE": os.environ.get("PLAYWRIGHT_CORE"), "CHROME_PATH": os.environ.get("CHROME_PATH"), f"pacote {VERSAO}": (PACOTE / "cabecalhos.json").exists()}.items() if not ok]
nav = pytest.mark.skipif(bool(FALTA), reason="faltam: " + ", ".join(FALTA))


def porta():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pub_local(tmp_path, r2_url, **extra):
    pub = json.loads((RAIZ / "config/publicacao.json").read_text(encoding="utf-8"))
    pub.update({"r2_url": r2_url, "versao": VERSAO, **extra})
    arq = tmp_path / "publicacao.json"
    arq.write_text(json.dumps(pub), encoding="utf-8")
    return arq


@nav
def test_the_production_configuration_works_in_a_real_browser_against_simulated_pages_and_r2(tmp_path):
    from flooding_mapping.app import build
    pa, pb = porta(), porta()
    origem_site, r2_url = f"http://127.0.0.1:{pa}", f"http://127.0.0.1:{pb}"
    pub = build.carregar_publicacao(pub_local(tmp_path, r2_url, geoai_publicada=False), local=True)
    site = tmp_path / "site"
    build.build_site(site, publicacao=pub)
    procs = [subprocess.Popen([sys.executable, str(E2E / "servidor_producao_simulado.py"), "pages", str(pa), str(site)]),
             subprocess.Popen([sys.executable, str(E2E / "servidor_producao_simulado.py"), "r2", str(pb), str(PACOTE), origem_site])]
    try:
        for p in (pa, pb):
            for _ in range(40):
                try:
                    requests.get(f"http://127.0.0.1:{p}/", timeout=1)
                    break
                except requests.RequestException:
                    time.sleep(0.25)
        r = subprocess.run(["node", str(E2E / "producao.js")], env={**os.environ, "PAGES": origem_site, "R2": r2_url, "VERSAO": VERSAO}, capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, (r.stdout + r.stderr)[-2500:]
        assert "producao ok" in r.stdout
    finally:
        for proc in procs:
            proc.kill()


@nav
def test_a_wrong_expected_hash_makes_the_page_refuse_the_data_instead_of_loading_them(tmp_path):
    from flooding_mapping.app import build
    pa, pb = porta(), porta()
    origem_site, r2_url = f"http://127.0.0.1:{pa}", f"http://127.0.0.1:{pb}"
    man = json.loads((RAIZ / "docs/manifestos" / f"manifesto_{VERSAO}.json").read_text(encoding="utf-8"))
    man["camadas"]["fase3"]["meta_sha256"] = "0" * 63 + "1"                                      # hash que não é o do meta.json publicado
    (tmp_path / "manifesto.json").write_text(json.dumps(man), encoding="utf-8")
    pub = build.carregar_publicacao(pub_local(tmp_path, r2_url, manifesto=str(tmp_path / "manifesto.json")), local=True)
    site = tmp_path / "site"
    build.build_site(site, publicacao=pub)
    procs = [subprocess.Popen([sys.executable, str(E2E / "servidor_producao_simulado.py"), "pages", str(pa), str(site)]),
             subprocess.Popen([sys.executable, str(E2E / "servidor_producao_simulado.py"), "r2", str(pb), str(PACOTE), origem_site])]
    try:
        for p in (pa, pb):
            for _ in range(40):
                try:
                    requests.get(f"http://127.0.0.1:{p}/", timeout=1)
                    break
                except requests.RequestException:
                    time.sleep(0.25)
        r = subprocess.run(["node", str(E2E / "producao_integridade.js")], env={**os.environ, "PAGES": origem_site, "R2": r2_url}, capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, (r.stdout + r.stderr)[-2000:]
    finally:
        for proc in procs:
            proc.kill()


def test_the_public_verifier_passes_against_the_simulated_r2_and_catches_a_missing_cors_and_a_wrong_hash(tmp_path):
    if not (PACOTE / "cabecalhos.json").exists():
        pytest.skip("falta o pacote preparado")
    import threading
    import servidor_producao_simulado as sim
    sys.path.insert(0, str(RAIZ / "tools"))
    import verificar_publicacao as v
    origem = "https://flooding-mapping-capstone.pages.dev"
    srv = sim.servidor_r2(0, PACOTE, origem)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        r = v.verificar(base, VERSAO, origem, PACOTE)
        reprovados = [i for i in r.itens if i["resultado"] == "REPROVADO" and not i["teste"].startswith("CDN")]
        assert reprovados == [], reprovados                                                       # o CDN real não existe no simulador: só ele pode ficar sem HIT
        assert any(i["teste"].startswith("PMTiles: Range responde 206") and i["resultado"] == "aprovado" for i in r.itens)
        assert any("camada E" in i["teste"] and "ausente, como previsto" in i["detalhe"] for i in r.itens)
        errado = v.verificar(base, VERSAO, "https://outro-site.exemplo", PACOTE)                    # origem que o bucket não libera
        assert any(i["resultado"] == "REPROVADO" and "CORS" in i["teste"] for i in errado.itens)
    finally:
        srv.shutdown()


def test_r2dev_addresses_are_reported_as_a_known_limitation_for_edge_caching_and_custom_domains_are_not():
    sys.path.insert(0, str(RAIZ / "tools"))
    import verificar_publicacao as v
    assert v.eh_r2dev("https://pub-66f5a12eb6834ef2b736fc85c89ca28c.r2.dev") and v.eh_r2dev("https://pub-x.r2.dev/")
    assert not v.eh_r2dev("https://dados.exemplo.org") and not v.eh_r2dev("https://r2.dev.exemplo.org") and not v.eh_r2dev("http://127.0.0.1:8000")


@nav
@pytest.mark.skipif(not (RAIZ / "data/interim/r2_preparado/geoai-f11490d2ef1a/cabecalhos.json").exists(), reason="falta o pacote geoai (tools/preparar_para_r2.py --so-geoai)")
def test_the_geoai_layer_loads_from_its_own_prefix_in_production_without_touching_the_main_version(tmp_path):
    """Com geoai_publicada ligado, a camada E vem de geoai-<hash>/ (hash do meta conferido pela página) e funciona junto com a versão principal; sem erros de CSP, CORS ou hash."""
    from flooding_mapping.app import build
    gpac = RAIZ / "data/interim/r2_preparado/geoai-f11490d2ef1a"
    pa, pb = porta(), porta()
    origem_site, r2_url = f"http://127.0.0.1:{pa}", f"http://127.0.0.1:{pb}"
    pub = build.carregar_publicacao(pub_local(tmp_path, r2_url, geoai_publicada=True), local=True)
    site = tmp_path / "site"
    build.build_site(site, publicacao=pub)
    procs = [subprocess.Popen([sys.executable, str(E2E / "servidor_producao_simulado.py"), "pages", str(pa), str(site)]),
             subprocess.Popen([sys.executable, str(E2E / "servidor_producao_simulado.py"), "r2", str(pb), str(PACOTE), origem_site, str(gpac)])]
    try:
        for p in (pa, pb):
            for _ in range(40):
                try:
                    requests.get(f"http://127.0.0.1:{p}/", timeout=1)
                    break
                except requests.RequestException:
                    time.sleep(0.25)
        r = subprocess.run(["node", str(E2E / "producao_geoai.js")], env={**os.environ, "PAGES": origem_site, "R2": r2_url, "VERSAO": VERSAO, "GEOAI": "geoai-f11490d2ef1a"}, capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, (r.stdout + r.stderr)[-2500:]
        assert "producao_geoai ok" in r.stdout
    finally:
        for proc in procs:
            proc.terminate()
