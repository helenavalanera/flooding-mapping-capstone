"""Envia ao Cloudflare R2 os objetos preparados por tools/preparar_para_r2.py, com os cabeçalhos certos. NÃO roda sozinho em produção: por padrão é só um ensaio (--dry-run).

    PYTHONPATH=src .venv/bin/python tools/enviar_para_r2.py DIR_PREPARADO [--enviar] [--cors ORIGEM ...] [--prefixo d-<hash>]

As credenciais vêm só das variáveis de ambiente do SEU terminal (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET), nunca de argumento, arquivo do repositório nem chat.
Precisa de ``boto3`` (``pip install boto3``, importado só ao enviar). Usa o bucket que existe (R2_BUCKET); não cria bucket nem domínio: o domínio público e a regra de cache da Cloudflare
se configuram no painel. Cada objeto sobe com Content-Type, Content-Encoding e Cache-Control do ``cabecalhos.json``; objetos existentes só são pulados quando tamanho, SHA-256, Content-Type, Content-Encoding e Cache-Control coincidem
(caminho com hash: o mesmo caminho é o mesmo conteúdo). ``--cors`` aplica a política de CORS com ``Range`` para as origens dadas. Ao fim, confere cada objeto por HeadObject.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REQUIRED_ENV = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")


def plano(pasta: Path, prefixo: str | None = None) -> list[dict]:
    """Os objetos a enviar: chave no bucket (com o prefixo d-<hash>), arquivo, cabeçalhos e tamanho."""
    info = json.loads((pasta / "cabecalhos.json").read_text(encoding="utf-8"))
    prefixo = prefixo or pasta.name
    itens = []
    for chave, h in sorted(info["objetos"].items()):
        arq = pasta / chave
        if not arq.is_file() or arq.stat().st_size != h["bytes"]:
            raise SystemExit(f"{chave}: arquivo ausente ou com tamanho diferente do cabecalhos.json")
        itens.append({"chave": f"{prefixo}/{chave}", "arquivo": arq, "bytes": h["bytes"], "sha256": hashlib.sha256(arq.read_bytes()).hexdigest(), "content_type": h["content_type"], "content_encoding": h.get("content_encoding"), "cache_control": h["cache_control"]})
    return itens


def validar_local(pasta: Path, esperado: dict | None = None) -> dict:
    """Confere, sem rede, a pasta preparada: versão (nome da pasta), quantidade e tamanho de objetos e o SHA-256 do conteúdo ORIGINAL de cada um (descomprimindo o gzip). Erros ficam em ``erros``."""
    info = json.loads((pasta / "cabecalhos.json").read_text(encoding="utf-8"))
    erros, total = [], 0
    for chave, h in info["objetos"].items():
        arq = pasta / chave
        if not arq.is_file():
            erros.append(f"{chave}: ausente")
            continue
        corpo = arq.read_bytes()
        total += len(corpo)
        try:
            original = gzip.decompress(corpo) if h.get("content_encoding") == "gzip" else corpo
        except (OSError, EOFError):
            erros.append(f"{chave}: gzip corrompido")
            continue
        if len(corpo) != h["bytes"] or len(original) != h["bytes_originais"] or hashlib.sha256(original).hexdigest() != h["sha256_do_original"]:
            erros.append(f"{chave}: tamanho ou SHA-256 diferente do cabecalhos.json")
    r = {"versao": pasta.name, "objetos": len(info["objetos"]), "bytes": total, "mb": round(total / 1e6, 1), "resumo_confere": info["resumo"]["objetos"] == len(info["objetos"]) and info["resumo"]["bytes"] == total, "erros": erros}
    for k, v in (esperado or {}).items():
        if r.get(k) != v:
            erros.append(f"{k}: esperado {v!r}, encontrado {r.get(k)!r}")
    return r


def politica_cors(origens: list[str]) -> dict:
    for o in origens:
        if not o.startswith("https://") or o.count("/") != 2:
            raise SystemExit(f"origem de CORS deve ser uma origem https sem caminho: {o!r}")
    return {"CORSRules": [{"AllowedOrigins": origens, "AllowedMethods": ["GET", "HEAD"], "AllowedHeaders": ["Range", "If-Range", "If-None-Match"],
                           "ExposeHeaders": ["Content-Range", "Content-Length", "ETag", "Accept-Ranges"], "MaxAgeSeconds": 86400}]}


def cliente_do_ambiente(env=os.environ):
    faltam = [v for v in REQUIRED_ENV if not env.get(v)]
    if faltam:
        raise SystemExit("faltam variáveis de ambiente no seu terminal: " + ", ".join(faltam) + " (as credenciais não são lidas de argumento nem de arquivo)")
    import boto3   # só aqui: o resto do pacote e os testes não precisam dele
    from botocore.config import Config

    return boto3.client("s3", endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com", aws_access_key_id=env["R2_ACCESS_KEY_ID"], aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
                        region_name="auto", config=Config(retries={"max_attempts": 3, "mode": "standard"})), env["R2_BUCKET"]


def enviar(cliente, bucket: str, itens: list[dict], simultaneos: int = 8) -> dict:
    def um(it):
        try:
            existente = cliente.head_object(Bucket=bucket, Key=it["chave"])
            if (
                existente["ContentLength"] == it["bytes"]
                and existente.get("Metadata", {}).get("sha256") == it["sha256"]
                and existente.get("ContentType") == it["content_type"]
                and existente.get("ContentEncoding") == it["content_encoding"]
                and existente.get("CacheControl") == it["cache_control"]
            ):
                return "pulado"
        except Exception as e:   # 404: ainda não existe
            if getattr(e, "response", {}).get("Error", {}).get("Code") not in ("404", "NoSuchKey", "NotFound"):
                raise
        extra = {"ContentEncoding": it["content_encoding"]} if it["content_encoding"] else {}
        cliente.put_object(Bucket=bucket, Key=it["chave"], Body=it["arquivo"].read_bytes(), ContentType=it["content_type"], CacheControl=it["cache_control"], Metadata={"sha256": it["sha256"]}, **extra)
        return "enviado"
    with ThreadPoolExecutor(simultaneos) as ex:
        res = list(ex.map(um, itens))
    return {"enviados": res.count("enviado"), "pulados": res.count("pulado")}


def conferir(cliente, bucket: str, itens: list[dict]) -> list[str]:
    erros = []
    for it in itens:
        h = cliente.head_object(Bucket=bucket, Key=it["chave"])
        if (h["ContentLength"] != it["bytes"] or h.get("Metadata", {}).get("sha256") != it["sha256"] or h.get("CacheControl") != it["cache_control"] or h.get("ContentType") != it["content_type"] or h.get("ContentEncoding") != it["content_encoding"]):
            erros.append(it["chave"])
    return erros


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pasta", type=Path)
    ap.add_argument("--enviar", action="store_true", help="envia de verdade (sem isto é só um ensaio)")
    ap.add_argument("--cors", nargs="*", default=None, help="origens https do site (por exemplo https://flooding-mapping-capstone.pages.dev)")
    ap.add_argument("--prefixo", default=None)
    ap.add_argument("--validar", action="store_true", help="só confere a pasta preparada (versão, quantidade, tamanho, SHA-256), sem rede nem credencial")
    ap.add_argument("--esperar-versao", default=None)
    ap.add_argument("--esperar-objetos", type=int, default=None)
    a = ap.parse_args()
    if a.validar:
        esperado = {k: v for k, v in (("versao", a.esperar_versao), ("objetos", a.esperar_objetos)) if v is not None}
        r = validar_local(a.pasta, esperado)
        print(json.dumps({k: v for k, v in r.items() if k != "erros"} | {"erros": r["erros"][:10], "n_erros": len(r["erros"])}, ensure_ascii=False, indent=1))
        sys.exit(1 if r["erros"] or not r["resumo_confere"] else 0)
    itens = plano(a.pasta, a.prefixo)
    total = sum(i["bytes"] for i in itens)
    print(json.dumps({"objetos": len(itens), "mb": round(total / 1e6, 1), "prefixo": itens[0]["chave"].split("/")[0], "exemplo": {k: str(v) for k, v in itens[0].items() if k != "arquivo"}}, ensure_ascii=False, indent=1))
    if a.cors is not None:
        print("política de CORS:", json.dumps(politica_cors(a.cors), ensure_ascii=False))
    if not a.enviar:
        print("ENSAIO: nada foi enviado. Rode de novo com --enviar, com as variáveis R2_* no seu terminal.")
        return
    cliente, bucket = cliente_do_ambiente()
    if a.cors:
        cliente.put_bucket_cors(Bucket=bucket, CORSConfiguration=politica_cors(a.cors))
    print(enviar(cliente, bucket, itens))
    erros = conferir(cliente, bucket, itens)
    print("conferência:", "todos os objetos conferem" if not erros else f"{len(erros)} com cabeçalho ou tamanho diferente: {erros[:5]}")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
