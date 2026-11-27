"""Servidor estático de teste: arquivos de uma pasta, HTTP Range e CORS, e nenhuma rota /api/. Faz o papel do Pages (a interface) e de um bucket (os dados) na topologia publicada.

    python tests/e2e/servidor_estatico.py PORTA PASTA
"""
import functools
import http.server
import os
import re
import sys


class Manipulador(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):   # sem registro de acessos
        pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Range")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def send_head(self):
        faixa = self.headers.get("Range")
        caminho = self.translate_path(self.path.split("?")[0])
        if not faixa or not os.path.isfile(caminho):
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)", faixa)
        tamanho = os.path.getsize(caminho)
        ini = int(m.group(1)) if m.group(1) else tamanho - int(m.group(2))
        fim = min(int(m.group(2)) if m.group(1) and m.group(2) else tamanho - 1, tamanho - 1)
        arquivo = open(caminho, "rb")
        arquivo.seek(ini)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(caminho))
        self.send_header("Content-Range", f"bytes {ini}-{fim}/{tamanho}")
        self.send_header("Content-Length", str(fim - ini + 1))
        self.end_headers()

        class Limitado:   # só o trecho pedido
            def __init__(self, f, n):
                self.f, self.n = f, n

            def read(self, k=-1):
                k = self.n if k < 0 else min(k, self.n)
                d = self.f.read(k)
                self.n -= len(d)
                return d

            def close(self):
                self.f.close()
        return Limitado(arquivo, fim - ini + 1)


if __name__ == "__main__":
    porta, pasta = int(sys.argv[1]), sys.argv[2]
    http.server.ThreadingHTTPServer(("127.0.0.1", porta), functools.partial(Manipulador, directory=pasta)).serve_forever()
