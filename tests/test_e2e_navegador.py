"""Browser tests (dashboard, PWA, service worker update) against the real street network with a synthetic storm.

They need a Chromium/Chrome and playwright-core, which are NOT project dependencies; point to them with

    PLAYWRIGHT_CORE=/caminho/para/node_modules/playwright-core CHROME_PATH=/caminho/do/chrome pytest tests/test_e2e_navegador.py

Without these, or without the generated street table and site folder, the tests are skipped.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).parent.parent
E2E = ROOT / "tests" / "e2e"
node = shutil.which("node")
FALTA = [c for c, ok in {
    "node": node, "PLAYWRIGHT_CORE": os.environ.get("PLAYWRIGHT_CORE"), "CHROME_PATH": os.environ.get("CHROME_PATH"),
    "data/processed/rede_poa.parquet": (ROOT / "data/processed/rede_poa.parquet").exists(), "site/previsao_72h.json": (ROOT / "site/previsao_72h.json").exists()}.items() if not ok]
pytestmark = pytest.mark.skipif(bool(FALTA), reason="faltam para os testes de navegador: " + ", ".join(FALTA))


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def subir(estaticos: Path | None = None, extra: tuple = ()):
    porta = porta_livre()
    cmd = [sys.executable, "-W", "ignore", str(E2E / "servidor_demo.py"), "--porta", str(porta)] + (["--estaticos", str(estaticos)] if estaticos else []) + list(extra)
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(90):
        try:
            if requests.get(f"http://127.0.0.1:{porta}/api/saude", timeout=1).status_code == 200:
                return proc, f"http://127.0.0.1:{porta}/"
        except requests.RequestException:
            time.sleep(1)
    proc.kill()
    raise RuntimeError("o servidor de demonstração não subiu: " + (proc.stderr.read().decode()[-400:] if proc.stderr else ""))


def rodar(script: str, base: str, **extra) -> subprocess.CompletedProcess:
    env = {**os.environ, "BASE_URL": base, **extra}
    return subprocess.run([node, str(E2E / script)], env=env, capture_output=True, text=True, timeout=900)   # WebGL por software: o painel leva ~8 min com o mapa-base vetorial


@pytest.fixture(scope="module")
def servidor():
    proc, base = subir()
    yield base
    proc.kill()


@pytest.fixture(scope="module")
def servidor_arquivo():
    """O mesmo servidor com o PWA arquivado (app/arquivo/) ligado: só os testes do app de rotas o usam; a aplicação atual roda sem ele."""
    proc, base = subir(extra=("--arquivo-pwa",))
    yield base
    proc.kill()


@pytest.mark.parametrize("script", ["dashboard.js", "sem_webgl.js"])
def test_the_interfaces_work_end_to_end_in_a_real_browser(servidor, script):
    r = rodar(script, servidor)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def test_the_archived_route_app_still_works_end_to_end_when_served_by_opt_in(servidor_arquivo):
    r = rodar("pwa.js", servidor_arquivo)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def test_the_current_application_is_not_a_pwa_and_the_archived_app_is_not_served(servidor):
    r = rodar("sem_pwa.js", servidor)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


@pytest.mark.skipif(not (ROOT / "data/processed/fase3_web/meta.json").exists(), reason="camada da Fase 3 não gerada (tools/preparar_camada_fase3.py)")
def test_the_phase_3_layer_works_end_to_end_in_a_real_browser(servidor):
    r = rodar("fase3.js", servidor)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


@pytest.mark.skipif(not (ROOT / "data/processed/drenagem_web/meta.json").exists(), reason="camada de drenagem não gerada (tools/preparar_camada_drenagem.py)")
def test_the_drainage_inventory_layer_works_end_to_end_in_a_real_browser(servidor):
    r = rodar("drenagem.js", servidor)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


@pytest.mark.skipif(not (ROOT / "data/processed/fase3_web/meta.json").exists(), reason="camada da Fase 3 não gerada (tools/preparar_camada_fase3.py)")
def test_the_scientific_landing_page_works_end_to_end_and_opens_the_map_as_asked(servidor):
    r = rodar("landing.js", servidor)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def test_the_results_tab_reads_as_an_executive_territorial_brief_in_a_real_browser(servidor):
    r = rodar("resultados.js", servidor)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def test_the_archived_service_worker_updates_and_drops_the_old_cache(tmp_path):
    copia = tmp_path / "arquivo"
    shutil.copytree(ROOT / "src/flooding_mapping/app/arquivo", copia)
    proc, base = subir(extra=("--arquivo", str(copia)))
    try:
        r = rodar("pwa_sw.js", base, STATIC_COPY=str(copia))
        assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    finally:
        proc.kill()


@pytest.mark.skipif(not (ROOT / "data/processed/fase3_web/meta.json").exists(), reason="camada da Fase 3 não gerada")
def test_the_phone_page_shows_the_real_interface_at_phone_width(servidor):
    r = rodar("celular.js", servidor)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


@pytest.mark.skipif(not (ROOT / "data/processed/fase3_web/meta.json").exists(), reason="camada da Fase 3 não gerada")
def test_data_urls_are_configurable_and_checked_by_hash_with_clear_failure_states(servidor):
    r = rodar("dados_config.js", servidor, META_FASE3=str(ROOT / "data/processed/fase3_web/meta.json"), CONFIG_JS=str(ROOT / "src/flooding_mapping/app/static/config-dados.js"))
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def test_the_interface_stays_light_when_the_system_asks_for_dark_mode(servidor):
    r = rodar("modo_claro.js", servidor)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


FALTAM_DADOS = [n for n, p in {"data/processed/fase3_web": ROOT / "data/processed/fase3_web/meta.json", "data/processed/drenagem_web": ROOT / "data/processed/drenagem_web/meta.json",
                               "data/raw/basemap/rs.pmtiles": ROOT / "data/raw/basemap/rs.pmtiles"}.items() if not p.exists()]


@pytest.mark.skipif(bool(FALTAM_DADOS), reason="faltam os dados derivados: " + ", ".join(FALTAM_DADOS))
def test_the_static_site_works_with_the_data_on_another_origin_like_pages_plus_a_bucket(tmp_path):
    """Topologia publicada: a interface numa origem (Pages) e tiles, fragmentos, drenagem e mapa-base noutra (bucket com CORS e Range). Sem API em nenhuma."""
    from flooding_mapping.app import build
    paginas, dados = tmp_path / "pages", tmp_path / "bucket"
    build.copiar_interface(paginas)
    (dados / "mapa").mkdir(parents=True)
    (dados / "fase3").symlink_to(ROOT / "data/processed/fase3_web")
    (dados / "drenagem").symlink_to(ROOT / "data/processed/drenagem_web")
    (dados / "mapa" / "rs.pmtiles").symlink_to(ROOT / "data/raw/basemap/rs.pmtiles")
    pa, pb = porta_livre(), porta_livre()
    config = (paginas / "config-dados.js").read_text()
    for antigo, novo in (('fase3: "fase3/"', f'fase3: "http://127.0.0.1:{pb}/fase3/"'), ('drenagem: "drenagem/"', f'drenagem: "http://127.0.0.1:{pb}/drenagem/"'), ('mapa: "/mapa/rs.pmtiles"', f'mapa: "http://127.0.0.1:{pb}/mapa/rs.pmtiles"')):
        assert antigo in config, antigo
        config = config.replace(antigo, novo)
    (paginas / "config-dados.js").write_text(config)
    procs = [subprocess.Popen([sys.executable, str(E2E / "servidor_estatico.py"), str(p), str(d)], cwd=ROOT) for p, d in ((pa, paginas), (pb, dados))]
    try:
        for p in (pa, pb):
            for _ in range(30):
                try:
                    requests.get(f"http://127.0.0.1:{p}/", timeout=1)
                    break
                except requests.RequestException:
                    time.sleep(0.5)
        r = rodar("estatico.js", f"http://127.0.0.1:{pa}/", PAGES=f"http://127.0.0.1:{pa}/", DADOS=f"http://127.0.0.1:{pb}/")
        assert r.returncode == 0, (r.stdout + r.stderr)[-1800:]
    finally:
        for proc in procs:
            proc.kill()
