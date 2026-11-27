"""Gera static/data/resultados_poa.json: os resultados executivos do dashboard, calculados dos dados reais (ver src/flooding_mapping/resultados.py).

    PYTHONPATH=src .venv/bin/python tools/gerar_resultados.py
"""
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from flooding_mapping import resultados  # noqa: E402


def main() -> None:
    t0 = time.time()
    r = resultados.gerar(RAIZ)
    destino = RAIZ / "src/flooding_mapping/app/static/data/resultados_poa.json"
    destino.write_text(json.dumps(r, ensure_ascii=False, separators=(",", ":"), default=float))
    print(f"gravado: {destino} ({destino.stat().st_size / 1e3:.0f} KB, {time.time() - t0:.0f} s); achados verificados: " +
          ", ".join(f"{a['id']}={'sim' if a['verificada'] else 'não'}" for d in r["dimensoes"].values() for a in d["achados"]) )


if __name__ == "__main__":
    main()
