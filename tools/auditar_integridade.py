"""Auditoria de integridade dos dados derivados que a aplicação consome. Só lê: não gera nem sobrescreve nada.

Confere (1) os hashes dos Parquets da Fase 3 e da drenagem contra os registrados nos metadados das camadas e no relatório de execução; (2) que os fragmentos
de detalhe cobrem todos os trechos, sem lacuna nem sobra; (3) que os tiles existem dentro da faixa de zoom declarada e não estão vazios onde há dados;
(4) que cada indicador executivo tem os campos de rastreabilidade e que a data de geração dos resultados é posterior aos Parquets de origem.

    python tools/auditar_integridade.py [--json saida.json]      (código de saída 1 se alguma verificação falhar)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAMPOS_INDICADOR = ("id", "dimensao", "titulo", "valor", "unidade", "formula", "fonte", "cenario", "metodo", "cobertura", "limitacoes")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def verificar(raiz: Path = RAIZ) -> list[dict]:
    r: list[dict] = []

    def ok(nome: str, passou: bool, detalhe: str = "") -> None:
        r.append({"verificacao": nome, "ok": bool(passou), "detalhe": detalhe})

    f3, web = raiz / "data/processed/fase3", raiz / "data/processed/fase3_web"
    if (web / "meta.json").exists():
        meta = json.loads((web / "meta.json").read_text())
        rel = json.loads((f3 / "relatorio_execucao.json").read_text()) if (f3 / "relatorio_execucao.json").exists() else {}
        for nome, esperado in meta["entradas_sha256"].items():
            real = sha256(f3 / nome) if (f3 / nome).exists() else "ausente"
            ok(f"fase3: hash de {nome} igual ao registrado na camada", real == esperado, real[:12])
        ok("fase3: nenhum arquivo de saída ficou fora do hash", set(meta["entradas_sha256"]) == {p.name for p in f3.glob("*.parquet")}, ", ".join(sorted(p.name for p in f3.glob("*.parquet"))))
        n_frag = len(list((web / "detalhe").glob("*.json")))
        esperado = -(-meta["trechos"] // meta["tamanho_do_fragmento"])
        ok("fase3: número de fragmentos cobre todos os trechos", n_frag == esperado, f"{n_frag} de {esperado}")
        linhas = 0
        for k in range(n_frag):
            fr = json.loads((web / "detalhe" / f"{k:04d}.json").read_text())
            if fr["primeiro_n"] != linhas:
                ok(f"fase3: fragmento {k} contínuo", False, f"começa em {fr['primeiro_n']}, esperado {linhas}")
                break
            linhas += len(fr["linhas"])
        else:
            ok("fase3: fragmentos contíguos e somam o total de trechos", linhas == meta["trechos"], f"{linhas} de {meta['trechos']}")
        ok("fase3: trechos com e sem dados somam o total", meta["trechos_com_dados"] + meta["trechos_sem_dados"] == meta["trechos"])
        tiles = list((web / "tiles").rglob("*.pbf"))
        zs = {int(p.relative_to(web / "tiles").parts[0]) for p in tiles}
        ok("fase3: tiles dentro da faixa de zoom declarada", bool(tiles) and min(zs) >= meta["zoom"][0] and max(zs) <= meta["zoom"][1], f"{len(tiles)} tiles, zoom {sorted(zs)}")
        ok("fase3: há tiles com conteúdo em cada nível de zoom declarado", all(any(t.stat().st_size > 100 for t in tiles if t.relative_to(web / "tiles").parts[0] == str(z)) for z in range(meta["zoom"][0], meta["zoom"][1] + 1)))
        if rel:
            ok("fase3: hashes do relatório de execução iguais aos do disco", all(sha256(raiz / a["path"]) == a["sha256"] for a in rel.get("arquivos", []) if isinstance(a, dict) and "path" in a and (raiz / a["path"]).exists()) if rel.get("arquivos") else True)
    else:
        ok("fase3: camada derivada presente", False, "data/processed/fase3_web/meta.json ausente")

    dren, dweb = raiz / "data/processed/drenagem", raiz / "data/processed/drenagem_web"
    if (dweb / "meta.json").exists():
        dm = json.loads((dweb / "meta.json").read_text())
        bad = [n for n, h in dm["entradas_sha256"].items() if (dren / n).exists() and sha256(dren / n) != h]
        faltam = [n for n in dm["entradas_sha256"] if not (dren / n).exists()]
        ok("drenagem: hashes dos Parquets iguais aos registrados na camada", not bad and not faltam, f"divergentes: {bad}; ausentes: {faltam}")
        for cam in ("rede", "pocos", "bocas", "bombas"):
            d = dweb / "detalhe" / cam
            if d.exists():
                ok(f"drenagem: fragmentos de {cam} contíguos", all(json.loads(p.read_text())["primeiro_n"] == i * dm["tamanho_do_fragmento"] for i, p in enumerate(sorted(d.glob("*.json")))), f"{len(list(d.glob('*.json')))} fragmentos")
    else:
        ok("drenagem: camada derivada presente", False, "data/processed/drenagem_web/meta.json ausente")

    res = raiz / "src/flooding_mapping/app/static/data/resultados_poa.json"
    if res.exists():
        d = json.loads(res.read_text())
        faltam = [(i["id"], c) for i in d["indicadores"] for c in CAMPOS_INDICADOR if i.get(c) in (None, "")]
        ok("resultados: os indicadores têm todos os campos de rastreabilidade", not faltam and len(d["indicadores"]) == 13, f"{len(d['indicadores'])} indicadores; faltam {faltam}")
        ok("resultados: todos os achados têm título decidido pela verificação", all(a.get("verificada") is not None for dim in d["dimensoes"].values() for a in dim["achados"]))
        if (f3 / "trechos_nivel2_cenarios.parquet").exists():
            ok("resultados: gerados depois dos Parquets de origem", res.stat().st_mtime >= (f3 / "trechos_nivel2_cenarios.parquet").stat().st_mtime, "")
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args()
    r = verificar()
    for x in r:
        print(("OK    " if x["ok"] else "FALHA ") + x["verificacao"] + (f"  [{x['detalhe']}]" if x["detalhe"] else ""))
    if a.json:
        a.json.write_text(json.dumps(r, ensure_ascii=False, indent=1))
    falhas = [x for x in r if not x["ok"]]
    print(f"\n{len(r) - len(falhas)} verificações ok, {len(falhas)} falhas")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
