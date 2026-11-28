"""Verifica, pela URL PÚBLICA (sem credencial), os dados publicados no R2: metadados e hashes, integridade de objetos por amostragem, gzip, Range do PMTiles, CORS (com preflight e origem alheia),
cabeçalhos de cache e o que o CDN de fato devolve (cf-cache-status em duas leituras seguidas, sem presumir). Só faz GET, HEAD e OPTIONS.

    python tools/verificar_publicacao.py https://pub-xxxx.r2.dev [--versao d-b7f6f03555d9] [--origem https://flooding-mapping-capstone.pages.dev] [--pacote data/interim/r2_preparado/d-...] [--json]

Os hashes esperados vêm do resumo versionado do manifesto (docs/manifestos/) e, por amostragem de objetos, do cabecalhos.json do pacote preparado.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM_PADRAO = "https://flooding-mapping-capstone.pages.dev"


def eh_r2dev(base: str) -> bool:
    return base.split("//", 1)[-1].split("/", 1)[0].lower().endswith(".r2.dev")


def pedir(url: str, metodo: str = "GET", cabecalhos: dict | None = None, gzip_ok: bool = True) -> tuple[int, dict, bytes]:
    h = {"User-Agent": "flooding-mapping-verificador", **(cabecalhos or {})}
    if gzip_ok:
        h.setdefault("Accept-Encoding", "gzip")
    rq = urllib.request.Request(url, method=metodo, headers=h)
    try:
        with urllib.request.urlopen(rq, timeout=60) as r:
            return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


class Relatorio:
    def __init__(self):
        self.itens = []

    def ok(self, nome: str, condicao: bool, detalhe: str = ""):
        self.itens.append({"teste": nome, "resultado": "aprovado" if condicao else "REPROVADO", "detalhe": detalhe})
        return condicao

    def info(self, nome: str, detalhe: str):
        self.itens.append({"teste": nome, "resultado": "informativo", "detalhe": detalhe})


def decodificar(h: dict, corpo: bytes) -> bytes:
    return gzip.decompress(corpo) if h.get("content-encoding") == "gzip" else corpo


def verificar(base: str, versao: str, origem: str, pacote: Path | None = None, amostra: int = 6) -> Relatorio:
    r, raiz = Relatorio(), f"{base}/{versao}"
    man = json.loads((RAIZ / "docs/manifestos" / f"manifesto_{versao}.json").read_text(encoding="utf-8"))
    cab = json.loads((pacote / "cabecalhos.json").read_text(encoding="utf-8"))["objetos"] if pacote and (pacote / "cabecalhos.json").exists() else None
    # 1. metadados e hashes
    for camada in ("fase3", "drenagem"):
        st, h, corpo = pedir(f"{raiz}/{camada}/meta.json", cabecalhos={"Origin": origem})
        r.ok(f"{camada}/meta.json acessível", st == 200, f"HTTP {st}")
        if st == 200:
            sha = hashlib.sha256(decodificar(h, corpo)).hexdigest()
            r.ok(f"{camada}/meta.json confere com o hash do manifesto", sha == man["camadas"][camada]["meta_sha256"], f"{sha[:16]} contra {man['camadas'][camada]['meta_sha256'][:16]}")
            r.ok(f"{camada}/meta.json com gzip", h.get("content-encoding") == "gzip", h.get("content-encoding", "sem Content-Encoding"))
            r.ok(f"{camada}/meta.json revalidável (não immutable)", "immutable" not in h.get("cache-control", ""), h.get("cache-control", ""))
            r.ok(f"{camada}/meta.json com CORS para o site", h.get("access-control-allow-origin") == origem, h.get("access-control-allow-origin", "ausente"))
    # 2. PMTiles por faixas
    url_pm = f"{raiz}/{man['mapa']['arquivo']}"
    st, h, corpo = pedir(url_pm, "HEAD", {"Origin": origem}, gzip_ok=False)
    r.ok("PMTiles: tamanho confere com o manifesto", st == 200 and int(h.get("content-length", -1)) == man["mapa"]["bytes"], f"HTTP {st}, {h.get('content-length')} bytes")
    r.ok("PMTiles: Accept-Ranges bytes", h.get("accept-ranges") == "bytes", h.get("accept-ranges", "ausente"))
    st, h, corpo = pedir(url_pm, "GET", {"Range": "bytes=0-16383", "Origin": origem}, gzip_ok=False)
    r.ok("PMTiles: Range responde 206 com 16.384 bytes", st == 206 and len(corpo) == 16384, f"HTTP {st}, {len(corpo)} bytes")
    r.ok("PMTiles: Content-Range correto", h.get("content-range", "").startswith("bytes 0-16383/") and h["content-range"].endswith("/" + str(man["mapa"]["bytes"])), h.get("content-range", "ausente"))
    r.ok("PMTiles: ETag presente", bool(h.get("etag")), h.get("etag", "ausente"))
    r.ok("PMTiles: começa com a assinatura PMTiles", corpo[:7] == b"PMTiles", repr(corpo[:7]))
    r.ok("PMTiles: CORS para o site e Content-Range exposto", h.get("access-control-allow-origin") == origem and "content-range" in h.get("access-control-expose-headers", "").lower(), f"{h.get('access-control-allow-origin')} | {h.get('access-control-expose-headers')}")
    st, h2, _ = pedir(url_pm, "GET", {"Range": f"bytes={man['mapa']['bytes'] - 100}-{man['mapa']['bytes'] - 1}", "Origin": origem}, gzip_ok=False)
    r.ok("PMTiles: Range no fim do arquivo", st == 206 and h2.get("content-range", "").startswith(f"bytes {man['mapa']['bytes'] - 100}-"), f"HTTP {st}, {h2.get('content-range')}")
    # 3. CORS: preflight e origem alheia
    st, h, _ = pedir(url_pm, "OPTIONS", {"Origin": origem, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "range,if-range"}, gzip_ok=False)
    permitidos = h.get("access-control-allow-headers", "").lower()
    r.ok("CORS: preflight libera o site, GET e os cabeçalhos Range e If-Range", st in (200, 204) and h.get("access-control-allow-origin") == origem and "range" in permitidos and "if-range" in permitidos, f"HTTP {st} | {h.get('access-control-allow-origin')} | {permitidos} | {h.get('access-control-allow-methods')}")
    st, h, _ = pedir(f"{raiz}/fase3/meta.json", "GET", {"Origin": "https://outro-site.exemplo"})
    r.ok("CORS: origem alheia não é liberada", h.get("access-control-allow-origin") not in ("*", "https://outro-site.exemplo"), h.get("access-control-allow-origin", "ausente"))
    # 4. objetos por amostragem: gzip, cache imutável, integridade do conteúdo original
    if cab:
        chaves = [k for k in cab if "/tiles/" in k or "/detalhe/" in k]
        sorteio = random.Random(1).sample(chaves, min(amostra, len(chaves)))
        for k in sorteio:
            st, h, corpo = pedir(f"{raiz}/{k}", cabecalhos={"Origin": origem})
            exp = cab[k]
            conf = st == 200 and hashlib.sha256(decodificar(h, corpo)).hexdigest() == exp["sha256_do_original"]
            r.ok(f"objeto {k}: conteúdo original confere", conf, f"HTTP {st}")
            r.ok(f"objeto {k}: gzip e cache imutável", h.get("content-encoding") == "gzip" and "immutable" in h.get("cache-control", ""), f"{h.get('content-encoding')} | {h.get('cache-control')}")
        # 5. cache de borda, medido e não presumido
        if sorteio:
            k = sorteio[0]
            a = pedir(f"{raiz}/{k}")[1]
            b = pedir(f"{raiz}/{k}")[1]
            r.info("CDN: cf-cache-status na 1ª e na 2ª leitura do mesmo objeto", f"{a.get('cf-cache-status', 'ausente')} e {b.get('cf-cache-status', 'ausente')} (age: {b.get('age', 'ausente')})")
            if eh_r2dev(base) and b.get("cf-cache-status") != "HIT":
                r.info("CDN: sem cache de borda no endereço r2.dev (limitação conhecida, não defeito dos dados)", f"cf-cache-status {b.get('cf-cache-status', 'ausente')}: o endereço r2.dev é para uso fora de produção, tem limite de taxa e não passa pelas regras de cache da Cloudflare; para cache de borda use um domínio próprio ligado ao bucket, com regra de cache")
            else:
                r.ok("CDN: a 2ª leitura veio do cache de borda (HIT)", b.get("cf-cache-status") == "HIT", f"cf-cache-status {b.get('cf-cache-status', 'ausente')}: se não for HIT, a regra de cache do domínio ainda não cobre este caminho")
        st, h, _ = pedir(url_pm, "GET", {"Range": "bytes=0-16383"}, gzip_ok=False)
        st2, h2, _ = pedir(url_pm, "GET", {"Range": "bytes=0-16383"}, gzip_ok=False)
        r.info("CDN: cf-cache-status das faixas do PMTiles (1ª e 2ª leitura)", f"{h.get('cf-cache-status', 'ausente')} e {h2.get('cf-cache-status', 'ausente')}")
    # 6. a camada E não faz parte desta versão e não pode ser requisito
    st, _, _ = pedir(f"{raiz}/geoai/meta.json", "HEAD")
    r.info("camada E (GeoAI) nesta versão", f"HTTP {st} em geoai/meta.json ({'ausente, como previsto' if st == 404 else 'presente'})")
    return r


def verificar_geoai(base: str, prefixo: str, origem: str) -> Relatorio:
    """A camada E, no prefixo próprio (geoai-<hash>/): meta.json e imagem conferem com o manifesto, cabeçalhos de cache/gzip, CORS e a versão principal intacta."""
    r, raiz = Relatorio(), f"{base}/{prefixo}/geoai"
    man = json.loads((RAIZ / "docs/manifestos" / f"manifesto_{prefixo}.json").read_text(encoding="utf-8"))["geoai"]
    st, h, corpo = pedir(f"{raiz}/meta.json", "GET", {"Origin": origem})
    meta_b = decodificar(h, corpo) if st == 200 else b""
    r.ok("GeoAI meta.json: HTTP 200 e SHA-256 igual ao do manifesto", st == 200 and hashlib.sha256(meta_b).hexdigest() == man["meta_sha256"], f"HTTP {st}")
    r.ok("GeoAI meta.json: cache revalidável ou imutável, com CORS", "cache-control" in h and h.get("access-control-allow-origin") in (origem, "*"), f"{h.get('cache-control')} | ACAO {h.get('access-control-allow-origin')}")
    st, h, corpo = pedir(f"{raiz}/fracao_construida.webp", "GET", {"Origin": origem})
    img = decodificar(h, corpo) if st == 200 else b""
    r.ok("GeoAI imagem: HTTP 200, SHA-256 e tamanho iguais ao manifesto", st == 200 and hashlib.sha256(img).hexdigest() == man["imagem_sha256"] and len(img) == man["imagem_bytes"], f"HTTP {st}, {len(img)} bytes")
    r.ok("GeoAI imagem: tipo image/webp, cache imutável e CORS para o site", h.get("content-type") == "image/webp" and "immutable" in h.get("cache-control", "") and h.get("access-control-allow-origin") in (origem, "*"), f"{h.get('content-type')} | {h.get('cache-control')}")
    st, h, _ = pedir(f"{raiz}/fracao_construida.webp", "OPTIONS", {"Origin": origem, "Access-Control-Request-Method": "GET"})
    r.ok("GeoAI CORS: preflight libera a origem do site", st in (200, 204) and h.get("access-control-allow-origin") in (origem, "*"), f"HTTP {st}")
    st, _, _ = pedir(f"{base}/d-b7f6f03555d9/fase3/meta.json", "HEAD", {"Origin": origem})
    r.ok("versão principal continua no ar, intacta", st == 200, f"HTTP {st}")
    return r


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base", help="URL pública base do bucket, sem barra no fim")
    ap.add_argument("--versao", default="d-b7f6f03555d9")
    ap.add_argument("--origem", default=ORIGEM_PADRAO)
    ap.add_argument("--pacote", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--geoai-prefixo", default=None, help="verifica só a camada E, no prefixo próprio (por exemplo geoai-f11490d2ef1a)")
    a = ap.parse_args()
    r = verificar_geoai(a.base.rstrip("/"), a.geoai_prefixo, a.origem) if a.geoai_prefixo else verificar(a.base.rstrip("/"), a.versao, a.origem, a.pacote)
    if a.json:
        print(json.dumps(r.itens, ensure_ascii=False, indent=1))
    else:
        for i in r.itens:
            print(f"[{i['resultado']:>11}] {i['teste']}" + (f"  ({i['detalhe']})" if i["detalhe"] else ""))
    reprovados = [i for i in r.itens if i["resultado"] == "REPROVADO"]
    print(f"\n{len(r.itens) - len(reprovados)} sem reprovação, {len(reprovados)} reprovados")
    sys.exit(1 if reprovados else 0)


if __name__ == "__main__":
    main()
