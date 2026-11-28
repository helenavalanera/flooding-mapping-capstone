"""Simula, no computador, a infraestrutura de produção: o Cloudflare Pages (arquivos de uma pasta + as regras do _headers, inclusive a CSP) e o bucket do R2
(objetos de uma pasta preparada por tools/preparar_para_r2.py, com Content-Type, Content-Encoding e Cache-Control de cada um, HTTP Range e CORS só para a origem do site).

    python tests/e2e/servidor_producao_simulado.py pages PORTA PASTA
    python tests/e2e/servidor_producao_simulado.py r2 PORTA PASTA_PREPARADA ORIGEM_DO_SITE
"""
import fnmatch
import hashlib
import http.server
import json
import re
import sys
from pathlib import Path


def regras_do_headers(texto: str):
    """[(padrão, [("add"|"del", nome, valor)])] na ordem do arquivo _headers do Pages."""
    regras, atual = [], None
    for linha in texto.splitlines():
        if not linha.strip():
            continue
        if not linha.startswith((" ", "\t")):
            atual = (linha.strip(), []); regras.append(atual)
        elif atual is not None:
            h = linha.strip()
            if h.startswith("!"):
                atual[1].append(("del", h[1:].strip(), None))
            else:
                n, _, v = h.partition(":")
                atual[1].append(("add", n.strip(), v.strip()))
    return regras


def casa(padrao: str, caminho: str) -> bool:
    return fnmatch.fnmatchcase(caminho, padrao.replace("*", "*"))


class Pages(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

    def end_headers(self):
        caminho = self.path.split("?")[0]
        arq = Path(self.directory) / "_headers"
        cab = {}
        if arq.exists():
            for padrao, acoes in regras_do_headers(arq.read_text(encoding="utf-8")):
                if casa(padrao, caminho):
                    for tipo, n, v in acoes:
                        if tipo == "del": cab.pop(n.lower(), None)
                        else: cab[n.lower()] = (n, v) if n.lower() not in cab else (n, cab[n.lower()][1] + ", " + v)
        for n, v in cab.values():
            self.send_header(n, v)
        super().end_headers()

    def do_GET(self):   # a raiz leva à landing, como o Pages faz com index.html
        if self.path.split("?")[0] in ("/", ""):
            self.path = "/index.html" + (("?" + self.path.split("?", 1)[1]) if "?" in self.path else "")
        return super().do_GET()


class R2(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    protocol_version = "HTTP/1.1"

    def _cors(self):
        origem = self.headers.get("Origin")
        if origem == self.server.origem_permitida:
            self.send_header("Access-Control-Allow-Origin", origem)
            self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length, ETag, Accept-Ranges")
        self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        self.send_response(204); self._cors()
        if self.headers.get("Origin") == self.server.origem_permitida:
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD"); self.send_header("Access-Control-Allow-Headers", "Range, If-Range, If-None-Match"); self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0"); self.end_headers()

    def _servir(self, corpo_ao_fim: bool):
        chave = self.path.split("?")[0].lstrip("/")
        obj = self.server.objetos.get(chave)
        pasta, prefixo = self.server.pasta, self.server.prefixo
        outro = self.server.extras.get(chave.split("/", 1)[0])           # prefixo adicional (a camada E, geoai-<hash>/), servido do mesmo bucket simulado
        if outro:
            pasta, prefixo, obj = outro[0], chave.split("/", 1)[0], outro[1].get(chave)
        if obj is None:
            self.send_response(404); self._cors(); self.send_header("Content-Length", "0"); self.end_headers(); return
        dados = (pasta / chave[len(prefixo) + 1:]).read_bytes()
        etag = '"' + hashlib.md5(dados).hexdigest() + '"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304); self._cors(); self.send_header("ETag", etag); self.end_headers(); return
        faixa = re.match(r"bytes=(\d+)-(\d*)$", self.headers.get("Range") or "")
        if faixa and not obj.get("content_encoding"):
            ini = int(faixa.group(1)); fim = min(int(faixa.group(2)) if faixa.group(2) else len(dados) - 1, len(dados) - 1)
            if ini >= len(dados):
                self.send_response(416); self.send_header("Content-Range", f"bytes */{len(dados)}"); self._cors(); self.send_header("Content-Length", "0"); self.end_headers(); return
            corpo = dados[ini:fim + 1]; self.send_response(206); self.send_header("Content-Range", f"bytes {ini}-{fim}/{len(dados)}")
        else:
            corpo = dados; self.send_response(200)
        self._cors()
        self.send_header("Content-Type", obj["content_type"]); self.send_header("Cache-Control", obj["cache_control"]); self.send_header("ETag", etag); self.send_header("Accept-Ranges", "bytes")
        if obj.get("content_encoding"): self.send_header("Content-Encoding", obj["content_encoding"])
        self.send_header("Content-Length", str(len(corpo))); self.end_headers()
        if corpo_ao_fim: self.wfile.write(corpo)

    def do_GET(self): self._servir(True)
    def do_HEAD(self): self._servir(False)


def servidor_r2(porta: int, pasta: Path, origem_permitida: str, extras: tuple = ()):
    s = http.server.ThreadingHTTPServer(("127.0.0.1", porta), R2)
    s.pasta, s.prefixo, s.origem_permitida = pasta, pasta.name, origem_permitida
    s.extras = {Path(e).name: (Path(e), {f"{Path(e).name}/{k}": v for k, v in json.loads((Path(e) / "cabecalhos.json").read_text(encoding="utf-8"))["objetos"].items()}) for e in extras}
    s.objetos = {f"{pasta.name}/{k}": v for k, v in json.loads((pasta / "cabecalhos.json").read_text(encoding="utf-8"))["objetos"].items()}
    return s


def servidor_pages(porta: int, pasta: Path):
    import functools
    return http.server.ThreadingHTTPServer(("127.0.0.1", porta), functools.partial(Pages, directory=str(pasta)))


if __name__ == "__main__":
    modo, porta, pasta = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
    (servidor_r2(porta, pasta, sys.argv[4], tuple(sys.argv[5:])) if modo == "r2" else servidor_pages(porta, pasta)).serve_forever()
