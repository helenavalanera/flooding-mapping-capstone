"""Command line of the extraction pipeline (batch). Reads documents from a folder; never fetches anything from the web by itself.

    python -m flooding_mapping.extracao.cli extrair  PASTA_DE_DOCUMENTOS [--max-chamadas 50]
    python -m flooding_mapping.extracao.cli pendentes
    python -m flooding_mapping.extracao.cli revisar  ID aceitar|rejeitar|corrigir --por NOME [--campo chave=valor ...] [--nota TEXTO]
    python -m flooding_mapping.extracao.cli precisao ANOTACOES.jsonl
    python -m flooding_mapping.extracao.cli rotulos

A document is a JSON file: {"fonte_id", "texto", "url", "publicado_em"}. Sources and their permission: config/fontes_extracao.json.
Outputs (outside Git): data/operacional/extracao/fila.jsonl and rotulos.jsonl; the precision report goes to reports/qa/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from ..config import resolve
from ..linguagem import gemini
from . import precisao
from .extrator import Documento, Fonte, extrair
from .fila import Fila
from .geocodificador import Geocodificador

PASTA = Path(resolve("data/operacional/extracao"))
FONTES = Path(resolve("config/fontes_extracao.json"))


def carregar_fontes(caminho: Path = FONTES) -> dict[str, Fonte]:
    dados = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {"fontes": []}
    return {f["id"]: Fonte(f["id"], f["nome"], f["tipo"], f.get("licenca", ""), bool(f.get("permitida")), f.get("url", "")) for f in dados["fontes"]}


def _provedor():
    p = gemini.do_ambiente(os.environ)
    if p is None:
        raise SystemExit("Provedor de linguagem não configurado (GEMINI_API_KEY e GEMINI_MODEL).")
    return p


def cmd_extrair(args) -> int:
    fontes, fila = carregar_fontes(FONTES), Fila(PASTA / "fila.jsonl")
    arquivo_vistos = PASTA / "vistos.txt"   # every document sent to the model, also those that yielded no event: none is paid for twice
    vistos = set(arquivo_vistos.read_text().split()) if arquivo_vistos.exists() else set()
    provedor, chamadas, novos, pulados = _provedor(), 0, 0, {"sem_fonte_autorizada": 0, "ja_processado": 0}
    for arquivo in sorted(Path(args.pasta).glob("*.json")):
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        fonte = fontes.get(d.get("fonte_id"))
        if fonte is None or not fonte.permitida:
            pulados["sem_fonte_autorizada"] += 1
            continue
        doc = Documento(d["fonte_id"], d["texto"], d.get("url", ""), date.fromisoformat(d["publicado_em"]) if d.get("publicado_em") else None)
        if doc.id in vistos:
            pulados["ja_processado"] += 1
            continue
        if chamadas >= args.max_chamadas:
            print(f"Limite de {args.max_chamadas} chamadas atingido; o restante fica para a próxima rodada.", file=sys.stderr)
            break
        chamadas += 1
        novos += fila.adicionar(extrair(doc, provedor, fonte)["candidatos"])   # a model failure stops here, before the document is marked as seen
        PASTA.mkdir(parents=True, exist_ok=True)
        with arquivo_vistos.open("a") as f:
            f.write(doc.id + "\n")
    print(json.dumps({"chamadas": chamadas, "candidatos_novos": novos, **pulados}, ensure_ascii=False))
    return 0


def cmd_pendentes(_args) -> int:
    for c in Fila(PASTA / "fila.jsonl").listar("pendente"):
        e = c["evento"]
        print(f"{c['id']}  [{c['fonte_id']}] {e['tipo']} · {e['via'] or e['local_texto']} · {e['municipio']} · {e['data'] or 's/ data'}\n    “{e['trecho_fonte']}”\n    {c['url']}")
    return 0


def cmd_revisar(args) -> int:
    corrigido = dict(c.split("=", 1) for c in (args.campo or []))
    novo = Fila(PASTA / "fila.jsonl").revisar(args.id, args.acao, args.por, corrigido or None, args.nota or "")
    print(f"{novo['id']}: {novo['status']} por {novo['revisado_por']}")
    return 0


def cmd_precisao(args) -> int:
    relatorio = precisao.avaliar(precisao.carregar_anotacoes(args.anotacoes), _provedor())
    saida = Path(resolve("reports/qa"))
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "extracao_precisao.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    (saida / "extracao_precisao.md").write_text(precisao.em_markdown(relatorio), encoding="utf-8")
    print(precisao.em_markdown(relatorio))
    return 0


def cmd_rotulos(_args) -> int:
    import pandas as pd
    rede = Path(resolve("data/processed/rede_poa.parquet"))
    geo = Geocodificador(pd.read_parquet(rede)) if rede.exists() else None
    rotulos = Fila(PASTA / "fila.jsonl").exportar_rotulos(geo, {i: f.tipo for i, f in carregar_fontes(FONTES).items()})
    (PASTA / "rotulos.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rotulos), encoding="utf-8")
    print(f"{len(rotulos)} rótulos revisados em {PASTA / 'rotulos.jsonl'}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Extração de eventos a partir de texto, com revisão humana")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extrair"); e.add_argument("pasta"); e.add_argument("--max-chamadas", type=int, default=50); e.set_defaults(f=cmd_extrair)
    sub.add_parser("pendentes").set_defaults(f=cmd_pendentes)
    r = sub.add_parser("revisar"); r.add_argument("id"); r.add_argument("acao", choices=["aceitar", "rejeitar", "corrigir"]); r.add_argument("--por", required=True)
    r.add_argument("--campo", action="append"); r.add_argument("--nota"); r.set_defaults(f=cmd_revisar)
    a = sub.add_parser("precisao"); a.add_argument("anotacoes"); a.set_defaults(f=cmd_precisao)
    sub.add_parser("rotulos").set_defaults(f=cmd_rotulos)
    args = p.parse_args(argv)
    return args.f(args)


if __name__ == "__main__":
    raise SystemExit(main())
