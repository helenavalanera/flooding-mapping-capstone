"""HTTP layer: JSON API for both interfaces plus the static files, on the standard library only.

    python -m flooding_mapping.servidor            # http://127.0.0.1:8000  (dashboard)  /pwa/  (mobility PWA)

Choices that matter
    * Binds to 127.0.0.1 by default; publishing it is a deliberate act (``--host``).
    * No access log and no request bodies in any log: origins, destinations and reports are personal.
    * Confirming or discarding an occurrence needs ``OPERADOR_TOKEN``; unset, those routes are off.
    * Bodies are limited to 8 KB; every user-facing route has an in-memory rate limit per client
      (the address is only a dictionary key for the window, never stored or logged).
    * Errors answer with a short message, never a stack trace or the request.

shortcut: one process with threads and a single routing engine in Python: a few simultaneous users.
Upgrade to a worker pool (or a compiled router) when concurrent analyses become the bottleneck.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import defaultdict, deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from . import ocorrencias as oc
from . import rotas as rt
from .chuva_horaria import ChuvaHoraria, ChuvaIndisponivel
from .config import ROOT, load_config, resolve
from .linguagem import gemini
from .linguagem.explicar import Explicador
from .servico import Servico

STATIC = Path(__file__).parent / "app" / "static"
MAX_CORPO = 8 * 1024
LIMITES_POR_MIN = {"/api/rotas": 20, "/api/explicacao": 10, "/api/relatos": 10}
CSP = ("default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
       "img-src 'self' data: https://tile.openstreetmap.org https://cdnjs.cloudflare.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json", ".geojson": "application/json", ".webmanifest": "application/manifest+json",
         ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


class Limitador:
    """At most ``max_n`` hits per ``janela_s`` per key, in memory only."""

    def __init__(self, janela_s: float = 60, relogio=time.monotonic):
        self.janela_s, self._relogio, self._lock = janela_s, relogio, threading.Lock()
        self._hits: dict[tuple, deque] = defaultdict(deque)

    def permite(self, chave: tuple, max_n: int) -> bool:
        agora = self._relogio()
        with self._lock:
            fila = self._hits[chave]
            while fila and agora - fila[0] > self.janela_s:
                fila.popleft()
            if len(fila) >= max_n:
                return False
            fila.append(agora)
            if len(self._hits) > 5000:  # forget idle keys
                for k in [k for k, v in self._hits.items() if not v or agora - v[-1] > self.janela_s]:
                    del self._hits[k]
            return True


def ler_env(caminho: Path, env=os.environ) -> None:
    """Load ``KEY=VALUE`` lines of a ``.env`` file without overriding the real environment."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, _, valor = linha.partition("=")
            env.setdefault(chave.strip(), valor.strip().strip("\"'"))


def criar_handler(servico: Servico, cors_origem: str = "", limitador: Limitador | None = None):
    limitador = limitador or Limitador()

    class Handler(BaseHTTPRequestHandler):
        server_version = "FloodingMapping"
        sys_version = ""

        def log_message(self, *args):  # no access log: it would carry places and times of people
            pass

        # -------------------------------------------------------------- respostas
        def _cabecalhos(self, tipo: str, tamanho: int, api: bool) -> None:
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(tamanho))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
            self.send_header("Cache-Control", "no-store" if api else "no-cache")
            if not api:
                self.send_header("Content-Security-Policy", CSP)
            if cors_origem:
                self.send_header("Access-Control-Allow-Origin", cors_origem)
                self.send_header("Vary", "Origin")

        def _json(self, dados, status=HTTPStatus.OK) -> None:
            corpo = json.dumps(dados, ensure_ascii=False, default=str, allow_nan=False).encode()
            self.send_response(status)
            self._cabecalhos("application/json; charset=utf-8", len(corpo), True)
            self.end_headers()
            self.wfile.write(corpo)

        def _erro(self, status: HTTPStatus, mensagem: str) -> None:
            self._json({"erro": mensagem}, status)

        def _corpo(self) -> dict:
            try:
                tamanho = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ValueError("Content-Length inválido") from None
            if tamanho > MAX_CORPO:
                raise ValueError(f"corpo maior que {MAX_CORPO} bytes")
            if not tamanho:
                return {}
            try:
                dados = json.loads(self.rfile.read(tamanho))
            except ValueError:
                raise ValueError("JSON inválido") from None
            if not isinstance(dados, dict):
                raise ValueError("o corpo deve ser um objeto JSON")
            return dados

        # -------------------------------------------------------------- roteamento
        def do_OPTIONS(self):
            self.send_response(HTTPStatus.NO_CONTENT)
            if cors_origem:
                self.send_header("Access-Control-Allow-Origin", cors_origem)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            self._despachar("GET")

        def do_POST(self):
            self._despachar("POST")

        def do_DELETE(self):
            self._despachar("DELETE")

        def _despachar(self, metodo: str) -> None:
            url = urlparse(self.path)
            if not url.path.startswith("/api/"):
                return self._estatico(url.path) if metodo == "GET" else self._erro(HTTPStatus.METHOD_NOT_ALLOWED, "método não permitido")
            maximo = LIMITES_POR_MIN.get(url.path)
            if metodo == "POST" and maximo and not limitador.permite((url.path, self.client_address[0]), maximo):
                return self._erro(HTTPStatus.TOO_MANY_REQUESTS, "muitas requisições; tente em instantes")
            try:
                resultado = self._api(metodo, url.path, {k: v[-1] for k, v in parse_qs(url.query).items()})
            except PermissionError as erro:
                return self._erro(HTTPStatus.FORBIDDEN, str(erro))
            except (ValueError, rt.ForaDaRede, rt.SemRota) as erro:
                return self._erro(HTTPStatus.UNPROCESSABLE_ENTITY, str(erro))
            except KeyError:
                return self._erro(HTTPStatus.NOT_FOUND, "não encontrado (ou expirado)")
            except ChuvaIndisponivel:
                return self._erro(HTTPStatus.SERVICE_UNAVAILABLE, "sem dados de chuva no momento")
            except Exception as erro:  # never leak the request or a trace
                print(f"erro interno: {type(erro).__name__}", file=sys.stderr)
                return self._erro(HTTPStatus.INTERNAL_SERVER_ERROR, "erro interno")
            self._json(resultado)

        def _operador(self) -> None:
            if not servico.token_operador:
                raise PermissionError("confirmação de ocorrências desativada (OPERADOR_TOKEN não definido)")
            token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            if not servico.autorizado(token):
                raise PermissionError("não autorizado")

        def _api(self, metodo: str, caminho: str, consulta: dict):
            if metodo == "GET":
                if caminho == "/api/saude":
                    return servico.saude()
                if caminho == "/api/visao-geral":
                    return servico.visao_geral()
                if caminho == "/api/previsao":
                    return servico.previsao(int(consulta.get("horas", 48)))
                if caminho == "/api/risco":
                    return servico.risco_mapa(float(consulta.get("h", 0)))
                if caminho == "/api/trecho":
                    return servico.trecho(consulta.get("id", ""))
                if caminho == "/api/ocorrencias":
                    return servico.listar_ocorrencias(consulta.get("situacao"))
                if caminho == "/api/proveniencia":
                    return servico.proveniencia()
            if metodo == "POST":
                if caminho == "/api/rotas":
                    return servico.rotas(self._corpo())
                if caminho == "/api/explicacao":
                    dados = self._corpo()
                    return servico.explicacao(str(dados.get("analise_id", "")), bool(dados.get("contextualizar")))
                if caminho == "/api/relatos":
                    return servico.relato(self._corpo())
                if caminho.startswith("/api/ocorrencias/") and caminho.count("/") == 3:
                    self._operador()
                    return servico.mudar_situacao(caminho.rsplit("/", 1)[1], self._corpo())
            if metodo == "DELETE" and caminho.startswith("/api/analises/") and caminho.count("/") == 3:
                return {"apagada": servico.apagar_analise(caminho.rsplit("/", 1)[1])}
            raise KeyError(caminho)

        # -------------------------------------------------------------- arquivos estáticos
        def _estatico(self, caminho: str) -> None:
            relativo = caminho.lstrip("/") or "index.html"
            alvo = (STATIC / relativo).resolve()
            if alvo.is_dir():
                alvo = alvo / "index.html"
            if not alvo.is_file() or not alvo.is_relative_to(STATIC.resolve()) or alvo.suffix not in TIPOS:
                return self._erro(HTTPStatus.NOT_FOUND, "não encontrado")
            corpo = alvo.read_bytes()
            self.send_response(HTTPStatus.OK)
            self._cabecalhos(TIPOS[alvo.suffix], len(corpo), False)
            self.end_headers()
            self.wfile.write(corpo)

    return Handler


def montar(raiz: Path = ROOT, env=os.environ) -> tuple[Servico, str]:
    """The service wired from the repository's data and the environment; the CORS origin to use."""
    ler_env(raiz / ".env", env)
    config = load_config()
    destino = resolve("data/processed/rede_poa.parquet")
    if not destino.exists():
        raise SystemExit(f"Falta {destino.relative_to(ROOT)}. Gere com: python -m flooding_mapping.rede_poa")
    rede = rt.Rede(pd.read_parquet(destino), config["roteamento"])
    lat, lon = float(rede.no_lat.mean()), float(rede.no_lon.mean())
    servico = Servico(rede, ChuvaHoraria(lat, lon), oc.Ocorrencias(resolve("data/operacional/ocorrencias.jsonl")),
                      Explicador(gemini.do_ambiente(env)), config["risco_trecho"], token_operador=(env.get("OPERADOR_TOKEN") or "").strip(),
                      meta_dados={"rede": str(destino.relative_to(ROOT)), "gerada_em": time.strftime("%Y-%m-%d", time.localtime(destino.stat().st_mtime))})
    return servico, (env.get("CORS_ORIGEM") or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor do Flooding Mapping (dashboard, PWA e API)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    servico, cors = montar()
    servico.store.expirar(90)  # retention: reports and records older than 90 days are dropped at start
    servidor = ThreadingHTTPServer((args.host, args.port), criar_handler(servico, cors))
    print(f"http://{args.host}:{args.port}/  (PWA em /pwa/)  |  provedor de linguagem: "
          f"{'configurado' if servico.explicador.provedor else 'não configurado (textos determinísticos)'}  |  "
          f"confirmação de ocorrências: {'ativa' if servico.token_operador else 'desativada'}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
