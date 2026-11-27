"""Manifesto de publicação dos dados derivados: lista cada arquivo servido pela aplicação (tiles e fragmentos das camadas de escoamento e de drenagem)
com tamanho e SHA-256, e identifica o conjunto de dados por uma versão que muda quando qualquer arquivo muda. Só lê as pastas de origem.

O manifesto serve a três usos: (1) conferir uma cópia publicada contra o que foi gerado (`--verificar`); (2) fixar, na configuração da página, o hash do
meta.json de cada camada (a página recusa dados que não correspondam); (3) reverter para uma versão anterior sabendo exatamente o que ela continha.

    python tools/gerar_manifesto_publicacao.py [--fase3 DIR] [--drenagem DIR] [--saida ARQ]
    python tools/gerar_manifesto_publicacao.py --verificar MANIFESTO --fase3 DIR --drenagem DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FORMATO = 1


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def listar(pasta: Path) -> dict[str, dict]:
    return {p.relative_to(pasta).as_posix(): {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in sorted(pasta.rglob("*")) if p.is_file()}


def montar(fase3: Path, drenagem: Path) -> dict:
    camadas, resumo = {}, hashlib.sha256()
    for nome, pasta in (("fase3", fase3), ("drenagem", drenagem)):
        arquivos = listar(pasta)
        meta = json.loads((pasta / "meta.json").read_text())
        camadas[nome] = {"versao_da_camada": meta["versao"], "meta_sha256": arquivos["meta.json"]["sha256"], "arquivos": len(arquivos), "bytes": sum(a["bytes"] for a in arquivos.values()), "conteudo": arquivos}
        for rel, a in arquivos.items():
            resumo.update(f"{nome}/{rel}:{a['sha256']}\n".encode())
    topo = resumo.hexdigest()
    return {"formato": FORMATO, "versao_dos_dados": "d-" + topo[:12], "sha256_do_conjunto": topo, "camadas": camadas,
            "observacao": "A versão dos dados é derivada do conteúdo: se qualquer tile ou fragmento mudar, a versão muda. Os Parquets de origem não são publicados; seus hashes estão nos meta.json."}


def verificar(manifesto: dict, fase3: Path, drenagem: Path) -> list[str]:
    erros = []
    for nome, pasta in (("fase3", fase3), ("drenagem", drenagem)):
        esperado = manifesto["camadas"][nome]["conteudo"]
        real = {p.relative_to(pasta).as_posix() for p in pasta.rglob("*") if p.is_file()}
        erros += [f"{nome}: ausente {r}" for r in sorted(set(esperado) - real)] + [f"{nome}: a mais {r}" for r in sorted(real - set(esperado))]
        for rel, a in esperado.items():
            if rel in real and sha256(pasta / rel) != a["sha256"]:
                erros.append(f"{nome}: hash diferente em {rel}")
    return erros


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fase3", type=Path, default=RAIZ / "data/processed/fase3_web")
    ap.add_argument("--drenagem", type=Path, default=RAIZ / "data/processed/drenagem_web")
    ap.add_argument("--saida", type=Path, default=None, help="padrão: data/processed/publicacao/manifesto_<versao>.json")
    ap.add_argument("--verificar", type=Path, default=None)
    a = ap.parse_args()
    if a.verificar:
        erros = verificar(json.loads(a.verificar.read_text()), a.fase3, a.drenagem)
        print("\n".join(erros[:50]) or "conjunto idêntico ao manifesto")
        return 1 if erros else 0
    m = montar(a.fase3, a.drenagem)
    saida = a.saida or RAIZ / "data/processed/publicacao" / f"manifesto_{m['versao_dos_dados']}.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(m, ensure_ascii=False, indent=1))
    print(json.dumps({k: m[k] for k in ("versao_dos_dados", "sha256_do_conjunto")} | {n: {"arquivos": c["arquivos"], "mb": round(c["bytes"] / 1e6, 1), "meta_sha256": c["meta_sha256"]} for n, c in m["camadas"].items()}, ensure_ascii=False, indent=1))
    print("gravado:", saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
