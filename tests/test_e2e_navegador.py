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


def subir(estaticos: Path | None = None):
    porta = porta_livre()
    cmd = [sys.executable, "-W", "ignore", str(E2E / "servidor_demo.py"), "--porta", str(porta)] + (["--estaticos", str(estaticos)] if estaticos else [])
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
    return subprocess.run([node, str(E2E / script)], env=env, capture_output=True, text=True, timeout=420)


@pytest.fixture(scope="module")
def servidor():
    proc, base = subir()
    yield base
    proc.kill()


@pytest.mark.parametrize("script", ["dashboard.js", "pwa.js", "sem_webgl.js", "jornada.js"])
def test_the_interfaces_work_end_to_end_in_a_real_browser(servidor, script):
    r = rodar(script, servidor)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def test_the_service_worker_updates_and_drops_the_old_cache(tmp_path):
    copia = tmp_path / "static"
    shutil.copytree(ROOT / "src/flooding_mapping/app/static", copia)
    proc, base = subir(copia)
    try:
        r = rodar("pwa_sw.js", base, STATIC_COPY=str(copia))
        assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    finally:
        proc.kill()
