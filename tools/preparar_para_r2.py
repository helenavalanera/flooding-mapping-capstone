"""Prepara, em disco, o que vai para o Cloudflare R2: os derivados com os cabeçalhos HTTP certos, e o mapa-base só de Porto Alegre. NÃO envia nada e não usa credencial.

    PYTHONPATH=src .venv/bin/python tools/preparar_para_r2.py [--saida DIR] [--mapa-poa] [--sem-compressao]

Lê data/processed/fase3_web e drenagem_web (não os altera) e escreve em ``DIR/<versão>/`` (padrão data/interim/r2_preparado, fora do Git):
- ``fase3/``, ``drenagem/`` e ``geoai/`` (camada E, experimental; a imagem WebP já é comprimida e vai como está): tiles .pbf e fragmentos .json já comprimidos com gzip (os tiles encolhem cerca de 3,7 vezes), para o R2 guardar o objeto com
  ``Content-Encoding: gzip`` e o CDN entregá-lo sem recomprimir (o R2 não comprime sozinho, e o CDN nem sempre comprime protobuf);
- ``mapa/poa.pmtiles`` (com ``--mapa-poa`` e o CLI ``pmtiles``): recorte do mapa-base do estado só para o município (cerca de 7 MB, em vez de 217 MB);
- ``cabecalhos.json``: para cada objeto, tipo, codificação, ``Cache-Control``, tamanho, tamanho original e SHA-256 do original, para o envio conferir e para o
  ``--verificar`` do manifesto continuar valendo (ele compara o conteúdo original, descomprimido).
A versão é a de ``gerar_manifesto_publicacao.py``: um caminho ``d-<hash>/`` novo a cada mudança, por isso os objetos podem ser ``immutable``. Passo a passo e comandos de
envio (sem segredos) em docs/r2_cache.md.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_manifesto_publicacao as manifesto  # noqa: E402

BBOX_POA = "-51.35,-30.30,-50.98,-29.90"                       # caixa em volta do município (EPSG:4326), com folga
IMUTAVEL = "public, max-age=31536000, immutable"
TIPOS = {".pbf": "application/x-protobuf", ".json": "application/json", ".pmtiles": "application/octet-stream", ".webp": "image/webp"}


def cabecalhos_do_objeto(chave: str, comprimido: bool) -> dict:
    """Tipo, codificação e cache de um objeto do bucket. O meta.json decide qual versão vale: nunca é ``immutable``."""
    nome = chave.rsplit("/", 1)[-1]
    h = {"content_type": TIPOS[Path(nome).suffix], "cache_control": "public, max-age=300, must-revalidate" if nome == "meta.json" else IMUTAVEL}
    if comprimido and Path(nome).suffix in (".pbf", ".json"):
        h["content_encoding"] = "gzip"
    return h


def preparar(fase3: Path, drenagem: Path, saida: Path, comprimir: bool = True, mapa_poa: bool = False, mapa_origem: Path | None = None, geoai: Path | None = None) -> dict:
    versao = manifesto.montar(fase3, drenagem, geoai)["versao_dos_dados"]
    raiz = saida / versao
    shutil.rmtree(raiz, ignore_errors=True)
    objetos = {}
    for nome, pasta in (("fase3", fase3), ("drenagem", drenagem), *((("geoai", geoai),) if geoai else ())):
        for p in sorted(pasta.rglob("*")):
            if not p.is_file():
                continue
            chave = f"{nome}/{p.relative_to(pasta).as_posix()}"
            original = p.read_bytes()
            h = cabecalhos_do_objeto(chave, comprimir)
            corpo = gzip.compress(original, 9, mtime=0) if h.get("content_encoding") == "gzip" else original   # mtime=0: o mesmo conteúdo dá sempre os mesmos bytes
            destino = raiz / chave
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(corpo)
            objetos[chave] = {**h, "bytes": len(corpo), "bytes_originais": len(original), "sha256_do_original": hashlib.sha256(original).hexdigest()}
    if mapa_poa:
        origem = mapa_origem or RAIZ / "data/raw/basemap/rs.pmtiles"
        if shutil.which("pmtiles") is None:
            raise SystemExit("o CLI pmtiles (go-pmtiles) não foi encontrado: ele extrai o recorte de Porto Alegre do mapa-base do estado")
        (raiz / "mapa").mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["pmtiles", "extract", str(origem), str(raiz / "mapa/poa.pmtiles"), f"--bbox={BBOX_POA}"], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("pmtiles extract falhou: " + r.stderr[-400:])
        dados = (raiz / "mapa/poa.pmtiles").read_bytes()
        objetos["mapa/poa.pmtiles"] = {**cabecalhos_do_objeto("mapa/poa.pmtiles", False), "bytes": len(dados), "bytes_originais": len(dados), "sha256_do_original": hashlib.sha256(dados).hexdigest()}
    resumo = {"versao_dos_dados": versao, "objetos": len(objetos), "bytes": sum(o["bytes"] for o in objetos.values()), "bytes_originais": sum(o["bytes_originais"] for o in objetos.values())}
    (raiz / "cabecalhos.json").write_text(json.dumps({"resumo": resumo, "objetos": objetos}, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumo


def preparar_geoai(geoai: Path, saida: Path, manifestos: Path | None = None) -> dict:
    """A camada E (GeoAI, experimental) num prefixo PRÓPRIO, ``geoai-<hash>/``, sem tocar a versão principal dos dados. O hash vem do conteúdo (meta.json e imagem). Escreve a pasta
    preparada (com cabecalhos.json, no mesmo formato) e, em ``manifestos``, o resumo versionado com os hashes que a página confere."""
    meta_b, img_b = (geoai / "meta.json").read_bytes(), (geoai / "fracao_construida.webp").read_bytes()
    meta = json.loads(meta_b)
    if hashlib.sha256(img_b).hexdigest() != meta["sha256_da_imagem"]:
        raise SystemExit("a imagem não corresponde ao sha256_da_imagem do meta.json: refaça tools/preparar_camada_geoai.py")
    prefixo = "geoai-" + hashlib.sha256(meta_b + img_b).hexdigest()[:12]
    raiz = saida / prefixo
    shutil.rmtree(raiz, ignore_errors=True)
    (raiz / "geoai").mkdir(parents=True)
    objetos = {}
    for nome, original in (("meta.json", meta_b), ("fracao_construida.webp", img_b)):
        chave = f"geoai/{nome}"
        h = cabecalhos_do_objeto(chave, True)
        corpo = gzip.compress(original, 9, mtime=0) if h.get("content_encoding") == "gzip" else original
        (raiz / chave).write_bytes(corpo)
        objetos[chave] = {**h, "bytes": len(corpo), "bytes_originais": len(original), "sha256_do_original": hashlib.sha256(original).hexdigest()}
    resumo = {"versao_dos_dados": prefixo, "objetos": len(objetos), "bytes": sum(o["bytes"] for o in objetos.values()), "bytes_originais": sum(o["bytes_originais"] for o in objetos.values())}
    (raiz / "cabecalhos.json").write_text(json.dumps({"resumo": resumo, "objetos": objetos}, ensure_ascii=False, indent=1), encoding="utf-8")
    if manifestos:
        man = {"formato": 1, "versao_dos_dados": prefixo, "camada": "geoai", "natureza": meta["natureza"], "experimento": meta["experimento"],
               "geoai": {"meta_sha256": objetos["geoai/meta.json"]["sha256_do_original"], "imagem": "geoai/fracao_construida.webp", "imagem_sha256": meta["sha256_da_imagem"], "imagem_bytes": len(img_b), "meta_bytes": len(meta_b),
                         "raster_de_origem_sha256": meta["origem"]["sha256"]},
               "objetos_no_bucket": len(objetos), "bytes_no_bucket": resumo["bytes"],
               "fontes_dos_hashes": ["data/processed/geoai_web/meta.json e fracao_construida.webp (tools/preparar_camada_geoai.py)", f"data/interim/r2_preparado/{prefixo}/cabecalhos.json (este script)", "data/processed/geoai/manifesto_" + meta["experimento"] + ".json (SHA-256 do COG de origem)"],
               "observacao": "Prefixo próprio da camada E: não faz parte da versão principal dos dados (d-b7f6f03555d9) e não a substitui. Camada experimental, sem validação independente."}
        (manifestos / f"manifesto_{prefixo}.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return resumo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fase3", type=Path, default=RAIZ / "data/processed/fase3_web")
    ap.add_argument("--drenagem", type=Path, default=RAIZ / "data/processed/drenagem_web")
    ap.add_argument("--saida", type=Path, default=RAIZ / "data/interim/r2_preparado")
    ap.add_argument("--geoai", type=Path, default=RAIZ / "data/processed/geoai_web", help="a camada E (experimental) entra se a pasta existir")
    ap.add_argument("--so-geoai", action="store_true", help="prepara só a camada E, num prefixo próprio geoai-<hash>, e grava o resumo do manifesto em docs/manifestos/")
    ap.add_argument("--mapa-poa", action="store_true")
    ap.add_argument("--sem-compressao", action="store_true")
    a = ap.parse_args()
    if a.so_geoai:
        r = preparar_geoai(a.geoai, a.saida, RAIZ / "docs/manifestos")
        print(json.dumps(r | {"saida": str(a.saida / r["versao_dos_dados"])}, ensure_ascii=False, indent=1))
        return
    r = preparar(a.fase3, a.drenagem, a.saida, not a.sem_compressao, a.mapa_poa, geoai=a.geoai if a.geoai.exists() else None)
    print(json.dumps(r | {"mb": round(r["bytes"] / 1e6, 1), "mb_originais": round(r["bytes_originais"] / 1e6, 1), "saida": str(a.saida / r["versao_dos_dados"])}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
