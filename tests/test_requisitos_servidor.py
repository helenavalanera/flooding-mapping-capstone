"""A imagem do servidor só instala requirements-servidor.txt: tudo o que o servidor importa ao iniciar precisa estar ali (direta ou transitivamente).

Antes deste teste, módulos novos importavam shapely e scikit-learn sem que o arquivo os listasse: o contêiner não subiria e nenhum teste acusava, porque o
ambiente de desenvolvimento tem tudo instalado.
"""
import json
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pytest

packaging = pytest.importorskip("packaging.requirements")

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "requirements-servidor.txt"


def _nome(n: str) -> str:
    return n.lower().replace("_", "-").replace(".", "-")


def _requisitos_diretos() -> set:
    linhas = [ln.split("#")[0].strip() for ln in ARQUIVO.read_text().splitlines()]
    return {_nome(packaging.Requirement(ln).name) for ln in linhas if ln}


def _fecho(diretos: set) -> set:
    visto, fila = set(), list(diretos)
    while fila:
        n = fila.pop()
        if n in visto:
            continue
        visto.add(n)
        try:
            for r in metadata.requires(n) or []:
                req = packaging.Requirement(r)
                if req.marker is None or not req.marker.evaluate({"extra": ""}):
                    if req.marker is not None:
                        continue
                fila.append(_nome(req.name))
        except metadata.PackageNotFoundError:
            pass
    return visto


def test_the_server_starts_in_an_environment_with_only_what_the_requirements_cover():
    """Simulates the image: every installed package that requirements-servidor.txt does not cover (even transitively) is made unimportable, then the server is imported.

    Optional imports guarded by try/except (psutil, for instance) are tolerated; a hard import of anything else fails here, as it would in the container.
    """
    cobertos = _fecho(_requisitos_diretos())
    bloqueados = sorted(m for m, ds in metadata.packages_distributions().items()
                        if m not in sys.stdlib_module_names and m != "flooding_mapping" and not any(_nome(d) in cobertos for d in ds))
    codigo = (
        "import sys\n"
        f"BLOQ = set({bloqueados!r})\n"
        "class Bloqueio:\n"
        "    def find_spec(self, nome, caminho=None, alvo=None):\n"
        "        if nome.split('.')[0] in BLOQ:\n"
        "            raise ModuleNotFoundError(f\"No module named '{nome}' (ausente da imagem)\", name=nome)\n"
        "sys.meta_path.insert(0, Bloqueio())\n"
        "import flooding_mapping.servidor\n"
        "print('ok')\n")
    saida = subprocess.run([sys.executable, "-W", "ignore", "-c", codigo], capture_output=True, text=True, cwd=RAIZ, env={"PYTHONPATH": str(RAIZ / "src"), "PATH": ""}, timeout=180)
    assert saida.returncode == 0 and saida.stdout.strip().endswith("ok"), f"o servidor não inicia só com requirements-servidor.txt: {saida.stderr[-600:]}"


def test_the_guard_really_detects_a_missing_requirement(tmp_path, monkeypatch):
    """Without shapely in the requirements the same simulation must fail: the test is not vacuous."""
    sem = tmp_path / "req.txt"
    sem.write_text("\n".join(ln for ln in ARQUIVO.read_text().splitlines() if "shapely" not in ln) + "\n")
    monkeypatch.setattr(sys.modules[__name__], "ARQUIVO", sem)
    with pytest.raises(AssertionError):
        test_the_server_starts_in_an_environment_with_only_what_the_requirements_cover()


def test_the_two_packages_that_broke_the_image_are_pinned():
    texto = ARQUIVO.read_text()
    for pacote in ("shapely==", "scikit-learn=="):
        assert pacote in texto
