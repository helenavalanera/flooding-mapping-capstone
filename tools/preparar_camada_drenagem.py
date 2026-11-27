"""Prepara o inventário de drenagem (Fase 2) para a aplicação: tiles vetoriais, detalhe por registro e meta.json.

    PYTHONPATH=src .venv/bin/python tools/preparar_camada_drenagem.py [saida]

Lê data/processed/drenagem/ (não altera) e escreve em data/processed/drenagem_web/ (fora do Git). Camada contextual: não entra em nenhum cálculo.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from flooding_mapping import camada_drenagem as c  # noqa: E402


def main() -> None:
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data/processed/drenagem_web"
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        meta = c.preparar(RAIZ / "data/processed/drenagem", saida, Path(tmp))
    mb = lambda p: round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6, 2)  # noqa: E731
    print(json.dumps({"saida": str(saida), "segundos": round(time.time() - t0, 1), "tiles_mb": mb(saida / "tiles"), "detalhe_mb": mb(saida / "detalhe"),
                      "camadas": {k: {"registros": v["registros"], "tiles_vazios": v["tiles_vazios"]} for k, v in meta["camadas"].items()}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
