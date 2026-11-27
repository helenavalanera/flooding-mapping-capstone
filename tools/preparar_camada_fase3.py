"""Prepara as saídas da Fase 3 para a aplicação (Fase 4): tiles vetoriais, fragmentos de detalhe e meta.json.

    PYTHONPATH=src .venv/bin/python tools/preparar_camada_fase3.py [saida]

Lê data/processed/fase3/*.parquet (não os altera) e escreve em data/processed/fase3_web/ (fora do Git). Registra a saída no manifesto.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from flooding_mapping import camada_fase3 as c  # noqa: E402


def main() -> None:
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data/processed/fase3_web"
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        meta = c.preparar(RAIZ / "data/processed/fase3", RAIZ / "data/interim/segments.parquet", RAIZ / "data/processed/rede_poa.parquet", saida, Path(tmp))
    tamanho = lambda p: sum(f.stat().st_size for f in p.rglob("*") if f.is_file())  # noqa: E731
    resumo = {"saida": str(saida), "trechos": meta["trechos"], "com_dados": meta["trechos_com_dados"], "segundos": round(time.time() - t0, 1),
              "tiles_mb": round(tamanho(saida / "tiles") / 1e6, 2), "arquivos_de_tiles": sum(1 for _ in (saida / "tiles").rglob("*.pbf")),
              "detalhe_mb": round(tamanho(saida / "detalhe") / 1e6, 2), "fragmentos": sum(1 for _ in (saida / "detalhe").glob("*.json"))}
    print(json.dumps(resumo, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
