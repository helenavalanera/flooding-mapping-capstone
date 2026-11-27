"""HTTP layer: JSON API for both interfaces plus the static files, on the standard library only.

    python -m flooding_mapping.servidor            # http://127.0.0.1:8000  (painel de análise; o PWA de rotas está arquivado em app/arquivo/, ver FM_ARQUIVO_PWA)

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
import gzip
import ipaddress
import json
import os
import secrets
import signal
import sys
import threading
import time
from collections import defaultdict, deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd

from . import ocorrencias as oc
from . import rotas as rt
from .chuva_horaria import ChuvaHoraria, ChuvaIndisponivel
from .config import ROOT, load_config, resolve
from .linguagem import gemini
from .linguagem.explicar import Explicador
from .servico import Servico

STATIC = Path(__file__).parent / "app" / "static"
# Source files win; the build folder only supplies what the pipeline generates (state forecast, layers).
RAIZES = (STATIC, ROOT / "site")
ARQUIVO = Path(__file__).parent / "app" / "arquivo"   # frente futura (monitoramento em tempo real: PWA de rotas): só é servida com FM_ARQUIVO_PWA=1
MAX_CORPO = 8 * 1024
MAPA_ROTA = "/mapa/rs.pmtiles"   # basemap (Protomaps, vector tiles of RS) served from our own disk; the app never calls a third-party tile server
MAPA_ARQUIVO = ROOT / "data" / "raw" / "basemap" / "rs.pmtiles"
CACHE_DERIVADOS = "public, max-age=3600, must-revalidate"   # tiles e fragmentos dos derivados; a publicação usa caminhos com hash e "immutable" (docs/r2_cache.md)
FASE3_ROTA = "/fase3/"   # tiles e fragmentos da Fase 3 (derivados, fora do Git): tools/preparar_camada_fase3.py escreve em data/processed/fase3_web
FASE3_RAIZ = ROOT / "data" / "processed" / "fase3_web"
FASE3_TIPOS = (".pbf", ".json", ".webp")
GEOAI_ROTA = "/geoai/"   # camada E (GeoAI, experimental): tools/preparar_camada_geoai.py escreve em data/processed/geoai_web
GEOAI_RAIZ = ROOT / "data" / "processed" / "geoai_web"
DRENAGEM_ROTA = "/drenagem/"   # inventário de drenagem (Fase 2) para o mapa: tools/preparar_camada_drenagem.py escreve em data/processed/drenagem_web
DRENAGEM_RAIZ = ROOT / "data" / "processed" / "drenagem_web"
MAPA_RESPOSTA_MAX = 8 * 1024 * 1024   # one answer never carries more than this, however open the requested range is
MAX_MAPA_BYTES = 600 * 1024 * 1024
LIMITES_POR_MIN = {"/api/rotas": 20, "/api/explicacao": 10, "/api/relatos": 10, "/api/assistente": 10, "/api/avisos": 30}
LIMITE_APOIO_POR_MIN = 20
LIMITE_LEITURA_POR_MIN = 240   # GET on the API: enough for a dashboard, not for scraping
FALHAS_DE_CREDENCIAL_POR_MIN = 8
TOKEN_MINIMO = 24          # shorter operator tokens are refused at start: they are easy to guess
TEMPO_DE_CONEXAO_S = 20    # a client that stalls does not hold a thread forever
LENTO_MS = 5000
CSP = ("default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
       "img-src 'self' data: blob: https://cdnjs.cloudflare.com https://s3.amazonaws.com; "
       "connect-src 'self' https://s3.amazonaws.com; worker-src 'self' blob:; child-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'")
# The service worker downloads the map library from the CDN to keep a copy for offline use; only its own script gets that permission.
CSP_SW = CSP.replace("connect-src 'self'", "connect-src 'self' https://cdnjs.cloudflare.com")
# Só a página do painel pode ser exibida dentro de uma página da MESMA origem (a página "No celular" mostra a interface real em 390 px). Nenhuma outra origem a enquadra.
CSP_PAINEL = CSP.replace("frame-ancestors 'none'", "frame-ancestors 'self'")
TIPOS = {".pbf": "application/x-protobuf", ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json", ".geojson": "application/json", ".webmanifest": "application/manifest+json",
         ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


def validar_token(token: str) -> str:
    """The operator token from the environment, or a clear refusal when it is too short to protect anything."""
    token = (token or "").strip()
    if token and len(token) < TOKEN_MINIMO:
        raise SystemExit(f"OPERADOR_TOKEN com {len(token)} caracteres: use ao menos {TOKEN_MINIMO}. "
                         f"Gere um com: python -m flooding_mapping.servidor --gerar-token")
    return token


def proxies_confiaveis(texto: str) -> list:
    """Addresses or networks (comma separated) whose forwarding headers may be believed."""
    try:
        return [ipaddress.ip_network(p.strip(), strict=False) for p in (texto or "").split(",") if p.strip()]
    except ValueError as erro:
        raise SystemExit(f"PROXIES_CONFIAVEIS inválido: {erro}") from None


def ip_do_cliente(par: str, encaminhado: str | None, confiaveis: list) -> str:
    """The client address for rate limiting.

    The forwarding header is believed only when the direct peer is a configured trusted proxy; the chain is then read from
    the right, skipping trusted proxies, and the first other address is the client. With no trusted proxy configured, or a
    peer that is not one, the header is ignored: anyone can write it, and trusting it would let a client pick its own limit."""
    def confiavel(ip: str) -> bool:
        try:
            return any(ipaddress.ip_address(ip) in rede for rede in confiaveis)
        except ValueError:
            return False
    if not confiaveis or not confiavel(par) or not encaminhado:
        return par
    for ip in reversed([p.strip() for p in encaminhado.split(",") if p.strip()]):
        if not confiavel(ip):
            return ip
    return par


class Metricas:
    """Counters and latency of the last requests, in memory and without any personal data (route groups only)."""

    def __init__(self, janela: int = 500):
        self._lock = threading.Lock()
        self._ultimas: deque = deque(maxlen=janela)
        self.total = 0
        self.erros_5xx = 0
        self.iniciado = time.time()

    def registrar(self, grupo: str, status: int, ms: float) -> None:
        with self._lock:
            self._ultimas.append((grupo, status, ms))
            self.total += 1
            self.erros_5xx += status >= 500

    def resumo(self) -> dict:
        with self._lock:
            ms = sorted(m for _, _, m in self._ultimas)
        p95 = ms[min(len(ms) - 1, int(0.95 * len(ms)))] if ms else None
        return {"requisicoes": self.total, "erros_5xx": self.erros_5xx, "ultimas": len(ms), "latencia_p95_ms": None if p95 is None else round(p95),
                "ativo_ha_s": round(time.time() - self.iniciado)}


class MuitasTentativas(Exception):
    """Too many failed credential attempts (HTTP 429)."""


class Limitador:
    """At most ``max_n`` hits per ``janela_s`` per key, in memory only."""

    def __init__(self, janela_s: float = 60, relogio=time.monotonic):
        self.janela_s, self._relogio, self._lock = janela_s, relogio, threading.Lock()
        self._hits: dict[tuple, deque] = defaultdict(deque)

    def bloqueado(self, chave: tuple, max_n: int) -> bool:
        """True when ``chave`` already used its ``max_n`` hits in the window (does not count a new one)."""
        agora = self._relogio()
        with self._lock:
            fila = self._hits.get(chave)
            while fila and agora - fila[0] > self.janela_s:
                fila.popleft()
            return bool(fila) and len(fila) >= max_n

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


def criar_handler(servico_real: Servico, cors_origem: str = "", limitador: Limitador | None = None, confiaveis: list | None = None,
                  metricas: Metricas | None = None, servico_demo: Servico | None = None):
    limitador = limitador or Limitador()
    confiaveis = confiaveis or []
    metricas = metricas or Metricas()

    class Handler(BaseHTTPRequestHandler):
        def _sv(self) -> Servico:
            """The real service, or the isolated demonstration one when the visitor chose it (cookie ``fm_modo=demo``, set by the page's switch)."""
            if servico_demo is not None and "fm_modo=demo" in (self.headers.get("Cookie") or ""):
                return servico_demo
            return servico_real

        server_version = "FloodingMapping"
        sys_version = ""
        timeout = TEMPO_DE_CONEXAO_S

        def _cliente(self) -> str:
            return ip_do_cliente(self.client_address[0], self.headers.get("X-Forwarded-For"), confiaveis)

        def log_message(self, *args):  # no access log: it would carry places and times of people
            pass

        # -------------------------------------------------------------- respostas
        def _cabecalhos(self, tipo: str, tamanho: int, api: bool, csp: str = CSP, cache: str | None = None) -> None:
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(tamanho))
            self.send_header("X-Content-Type-Options", "nosniff")
            # Só a origem (nunca o caminho) vai a outros domínios. "no-referrer" fazia o navegador omitir o Referer nos mapas-base, e a política
            # de uso dos tiles do OpenStreetMap exige um Referer válido. Dentro do próprio servidor o Referer completo continua indo.
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
            self.send_header("Cache-Control", cache or ("no-store" if api else "no-cache"))
            if not api:
                self.send_header("Content-Security-Policy", csp)
            if cors_origem:
                self.send_header("Access-Control-Allow-Origin", cors_origem)
                self.send_header("Vary", "Origin")

        def _json(self, dados, status=HTTPStatus.OK) -> None:
            self._enviar(json.dumps(dados, ensure_ascii=False, default=str, allow_nan=False).encode(), status)

        def _enviar(self, corpo: bytes, status=HTTPStatus.OK) -> None:
            self._status = int(status)
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
            inicio, self._status = time.monotonic(), 0
            try:
                self._despachar_interno(metodo)
            finally:
                caminho = urlparse(self.path).path
                if caminho.startswith("/api/"):   # route group only: ids and query strings can carry places and times
                    grupo = "/".join(caminho.split("/")[:3]) + ("/{id}" if caminho.count("/") > 2 else "")
                    ms = (time.monotonic() - inicio) * 1000
                    metricas.registrar(metodo + " " + grupo, self._status, ms)
                    if ms > LENTO_MS:
                        print(f"lento: {metodo} {grupo} {ms:.0f} ms", file=sys.stderr)

        def _despachar_interno(self, metodo: str) -> None:
            url = urlparse(self.path)
            if not url.path.startswith("/api/"):
                return self._estatico(url.path) if metodo == "GET" else self._erro(HTTPStatus.METHOD_NOT_ALLOWED, "método não permitido")
            apoio = metodo == "POST" and url.path.startswith("/api/ocorrencias/") and url.path.endswith("/apoio")
            maximo = LIMITE_APOIO_POR_MIN if apoio else LIMITES_POR_MIN.get(url.path) if metodo == "POST" else (LIMITE_LEITURA_POR_MIN if metodo == "GET" else None)
            if maximo and not limitador.permite((metodo, "apoio" if apoio else url.path if metodo == "POST" else "leitura", self._cliente()), maximo):
                return self._erro(HTTPStatus.TOO_MANY_REQUESTS, "muitas requisições; tente em instantes")
            try:
                resultado = self._api(metodo, url.path, {k: v[-1] for k, v in parse_qs(url.query).items()})
            except MuitasTentativas as erro:
                return self._erro(HTTPStatus.TOO_MANY_REQUESTS, str(erro))
            except PermissionError as erro:
                return self._erro(HTTPStatus.FORBIDDEN, str(erro))
            except (ValueError, rt.ForaDaRede, rt.SemRota) as erro:
                return self._erro(HTTPStatus.UNPROCESSABLE_ENTITY, str(erro))
            except KeyError:
                return self._erro(HTTPStatus.NOT_FOUND, "não encontrado (ou expirado)")
            except ChuvaIndisponivel as erro:   # never old rain as if it were current: say it is down and when it last worked
                return self._json({"erro": str(erro), "ultima_atualizacao": erro.ultima_atualizacao}, HTTPStatus.SERVICE_UNAVAILABLE)
            except Exception as erro:  # never leak the request or a trace
                print(f"erro interno: {type(erro).__name__}", file=sys.stderr)
                return self._erro(HTTPStatus.INTERNAL_SERVER_ERROR, "erro interno")
            try:  # strict JSON: a NaN is a server bug (500), not a client mistake, and never reaches a client
                corpo = json.dumps(resultado, ensure_ascii=False, default=str, allow_nan=False).encode()
            except (ValueError, TypeError) as erro:
                print(f"erro interno ao serializar: {type(erro).__name__}", file=sys.stderr)
                return self._erro(HTTPStatus.INTERNAL_SERVER_ERROR, "erro interno")
            self._enviar(corpo)

        def _credencial_valida(self) -> bool:
            token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            return self._sv().autorizado(token)

        def _lista_completa(self) -> bool:
            """An operator asking for the full list goes through the same brute-force protection."""
            self._operador()
            return True

        def _operador(self) -> None:
            """Authorises an operator action. Wrong credentials are counted per client and blocked after a few tries,
            so the token cannot be guessed by brute force."""
            if not self._sv().token_operador:
                raise PermissionError("confirmação de ocorrências desativada (OPERADOR_TOKEN não definido)")
            chave = ("falha-operador", self._cliente())
            if limitador.bloqueado(chave, FALHAS_DE_CREDENCIAL_POR_MIN):
                raise MuitasTentativas("muitas tentativas com credencial inválida; aguarde um minuto")
            if not self._credencial_valida():
                limitador.permite(chave, FALHAS_DE_CREDENCIAL_POR_MIN)
                raise PermissionError("não autorizado")

        def _api(self, metodo: str, caminho: str, consulta: dict):
            if metodo == "GET":
                if caminho == "/api/saude":
                    saude = {**self._sv().saude(), "metricas": metricas.resumo(), "modo": "demonstracao" if self._sv() is servico_demo else "real",
                             "demonstracao_disponivel": servico_demo is not None}
                    if self._sv().token_operador and self.headers.get("Authorization") and self._credencial_valida():
                        # only for the operator: how this request reached the server, to find the proxy address to trust
                        saude["diagnostico_de_origem"] = {"conexao_direta": self.client_address[0], "encaminhado": self.headers.get("X-Forwarded-For"),
                                                         "cliente_considerado": self._cliente(), "proxies_confiaveis": len(confiaveis)}
                    return saude
                if caminho == "/api/visao-geral":
                    return self._sv().visao_geral()
                if caminho == "/api/previsao":
                    return self._sv().previsao(int(consulta.get("horas", 48)))
                if caminho == "/api/risco":
                    return self._sv().risco_mapa(float(consulta.get("h", 0)))
                if caminho == "/api/trecho":
                    return self._sv().trecho(consulta.get("id", ""))
                if caminho == "/api/ocorrencias":
                    completo = bool(self.headers.get("Authorization")) and self._sv().token_operador != "" and self._lista_completa()
                    return self._sv().listar_ocorrencias(consulta.get("situacao"), completo)
                if caminho == "/api/bolsoes":
                    return self._sv().bolsoes(float(consulta.get("h", 0)))
                if caminho == "/api/territorio":
                    return self._sv().territorio_geo()
                if caminho == "/api/bairros":
                    return self._sv().bairros(float(consulta.get("h", 0)))
                if caminho == "/api/pois":
                    return self._sv().lista_de_pois()
                if caminho == "/api/areas-sugeridas":
                    return self._sv().areas_sugeridas()
                if caminho == "/api/aprendizado":
                    return self._sv().aprendizado_status()
                if caminho == "/api/proveniencia":
                    return self._sv().proveniencia()
                if caminho == "/api/territorios":
                    return self._sv().territorios()
            if metodo == "POST":
                if caminho == "/api/rotas":
                    return self._sv().rotas(self._corpo())
                if caminho == "/api/explicacao":
                    dados = self._corpo()
                    return self._sv().explicacao(str(dados.get("analise_id", "")), bool(dados.get("contextualizar")))
                if caminho == "/api/assistente":
                    return self._sv().assistente(self._corpo())
                if caminho == "/api/relatos":
                    return self._sv().relato(self._corpo())
                if caminho == "/api/avisos":
                    return self._sv().avisos(self._corpo())
                if caminho.startswith("/api/ocorrencias/") and caminho.endswith("/apoio") and caminho.count("/") == 4:
                    return self._sv().apoiar(caminho.split("/")[3], self._corpo())
                if caminho.startswith("/api/ocorrencias/") and caminho.count("/") == 3:
                    self._operador()
                    return self._sv().mudar_situacao(caminho.rsplit("/", 1)[1], self._corpo())
            if metodo == "DELETE" and caminho.startswith("/api/analises/") and caminho.count("/") == 3:
                return {"apagada": self._sv().apagar_analise(caminho.rsplit("/", 1)[1])}
            raise KeyError(caminho)

        # -------------------------------------------------------------- arquivos estáticos
        def _mapa(self) -> None:
            """The basemap archive, answering HTTP ``Range`` (PMTiles reads only the bytes it needs, so a phone never downloads the whole file)."""
            arquivo = MAPA_ARQUIVO
            if not arquivo.is_file():
                return self._erro(HTTPStatus.NOT_FOUND, "mapa-base indisponível")
            total = arquivo.stat().st_size
            etag = f'"{arquivo.stat().st_mtime_ns:x}-{total:x}"'
            pedido = (self.headers.get("Range") or "").strip()
            inicio, fim, parcial = 0, min(total, MAPA_RESPOSTA_MAX) - 1, False
            if pedido:
                m = __import__("re").fullmatch(r"bytes=(\d*)-(\d*)", pedido)
                if not m or not (m.group(1) or m.group(2)):
                    return self._erro(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "intervalo inválido")
                if m.group(1):
                    inicio = int(m.group(1))
                    fim = int(m.group(2)) if m.group(2) else total - 1
                else:   # suffix: the last N bytes
                    inicio, fim = max(0, total - int(m.group(2))), total - 1
                if inicio >= total or fim < inicio:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{total}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                fim = min(fim, total - 1, inicio + MAPA_RESPOSTA_MAX - 1)
                parcial = True
            tamanho = fim - inicio + 1
            self._status = int(HTTPStatus.PARTIAL_CONTENT if parcial else HTTPStatus.OK)
            self.send_response(self._status)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(tamanho))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("X-Content-Type-Options", "nosniff")
            if parcial:
                self.send_header("Content-Range", f"bytes {inicio}-{fim}/{total}")
            if cors_origem:
                self.send_header("Access-Control-Allow-Origin", cors_origem)
                self.send_header("Vary", "Origin")
            self.end_headers()
            with arquivo.open("rb") as f:
                f.seek(inicio)
                restante = tamanho
                while restante > 0:
                    bloco = f.read(min(1 << 20, restante))
                    if not bloco:
                        break
                    self.wfile.write(bloco)
                    restante -= len(bloco)

        def _estatico(self, caminho: str) -> None:
            # (O redirecionamento de celulares ao aplicativo do cidadão foi arquivado com o PWA: app/arquivo/README.md.)
            if caminho == MAPA_ROTA:
                return self._mapa()
            if caminho.startswith(FASE3_ROTA):
                return self._fase3(unquote(caminho))
            if caminho.startswith(DRENAGEM_ROTA):
                return self._fase3(unquote(caminho), DRENAGEM_ROTA, DRENAGEM_RAIZ)
            if caminho.startswith(GEOAI_ROTA):
                return self._fase3(unquote(caminho), GEOAI_ROTA, GEOAI_RAIZ)
            caminho = unquote(caminho)   # the map library asks for "Noto%20Sans%20Regular"; the containment check below still applies to the decoded path
            if "\x00" in caminho:
                return self._erro(HTTPStatus.NOT_FOUND, "não encontrado")
            relativo = caminho.lstrip("/") or "index.html"
            for raiz in RAIZES:
                alvo = (raiz / relativo).resolve()
                if alvo.is_dir():
                    if not caminho.endswith("/") and alvo.is_relative_to(raiz.resolve()):   # relative links need the trailing slash
                        self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                        self.send_header("Location", caminho + "/")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    alvo = alvo / "index.html"
                if alvo.is_file() and alvo.is_relative_to(raiz.resolve()) and alvo.suffix in TIPOS:
                    corpo = alvo.read_bytes()
                    self.send_response(HTTPStatus.OK)
                    politica = CSP_SW if alvo.name == "sw.js" else CSP_PAINEL if alvo == raiz.resolve() / "index.html" else CSP
                    self._cabecalhos(TIPOS[alvo.suffix], len(corpo), False, politica)
                    self.end_headers()
                    self.wfile.write(corpo)
                    return
            self._erro(HTTPStatus.NOT_FOUND, "não encontrado")

        def _fase3(self, caminho: str, rota: str = FASE3_ROTA, pasta: Path | None = None) -> None:
            """Só leitura de arquivos já gerados, só ``.pbf``/``.json``, e nunca fora da pasta da camada (Fase 3 ou drenagem)."""
            raiz = (pasta or FASE3_RAIZ).resolve()
            alvo = (raiz / caminho[len(rota):]).resolve()
            if "\x00" in caminho or not alvo.is_relative_to(raiz) or alvo.suffix not in FASE3_TIPOS:
                return self._erro(HTTPStatus.NOT_FOUND, "não encontrado")
            if not alvo.is_file():
                if alvo.suffix == ".pbf" and alvo.relative_to(raiz).parts[:1] == ("tiles",):   # tile sem trechos: vazio, não erro (o mapa pede tudo o que a tela cobre)
                    self.send_response(HTTPStatus.NO_CONTENT)
                    self._cabecalhos(TIPOS[".pbf"], 0, False)
                    self.end_headers()
                    return
                return self._erro(HTTPStatus.NOT_FOUND, "não encontrado")
            corpo = alvo.read_bytes()
            # Como o CDN faria na publicação: tiles e fragmentos são imutáveis por versão (ETag + cache do navegador por uma hora, revalidando), vão comprimidos
            # (os tiles .pbf encolhem cerca de 3,7 vezes com gzip) e o meta.json, que decide qual versão vale, é sempre revalidado.
            etag = f'"{alvo.stat().st_mtime_ns:x}-{len(corpo):x}"'
            imutavel = alvo.name != "meta.json"
            if imutavel and self.headers.get("If-None-Match") == etag:
                self.send_response(HTTPStatus.NOT_MODIFIED)
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", CACHE_DERIVADOS)
                self.end_headers()
                return
            gz = len(corpo) > 512 and "gzip" in (self.headers.get("Accept-Encoding") or "")
            if gz:
                corpo = gzip.compress(corpo, 5)
            self.send_response(HTTPStatus.OK)
            self._cabecalhos(TIPOS[alvo.suffix], len(corpo), False, cache=CACHE_DERIVADOS if imutavel else None)
            if imutavel:
                self.send_header("ETag", etag)
            if gz:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding" if not cors_origem else "Origin, Accept-Encoding")
            self.end_headers()
            self.wfile.write(corpo)

    return Handler


def resumo_da_auditoria() -> dict | None:
    """The summary of the baseline audit against documented events, from the report in the repository (None if absent)."""
    arquivo = resolve("reports/ml/risco_trecho_auditoria.json")
    if not arquivo.exists():
        return None
    a = json.loads(arquivo.read_text())
    r, d = a["confronto_com_eventos_documentados"]["resumo"], a["dias_de_alerta_sem_registro"]
    return {"eventos_documentados": r["eventos_geocodificados"], "datas_distintas": r["datas_distintas"], "detectados_em_algum_horario_do_dia": r["detectados_em_alguma_hora_do_dia"],
            "detectados_na_hora_do_reporte": r["detectados_na_hora_do_reporte"], "nao_detectados": r["nao_detectados_no_dia"],
            "dias_avaliados": d["dias"], "dias_com_alguma_via_em_atencao": d["dias_com_alguma_via_em_atencao"], "dias_documentados": d["dias_documentados"], "leitura": d["leitura"]}


MAX_REDE_BYTES = 300 * 1024 * 1024
_CELULAR = __import__("re").compile(r"Mobi|Android|iPhone|iPad|iPod", __import__("re").I)


def e_celular(user_agent: str) -> bool:
    """Phones and tablets, by the User-Agent they announce (a desktop browser in a narrow window is not one). Sem uso desde o arquivamento do PWA; fica para a frente de monitoramento."""
    return bool(_CELULAR.search(user_agent or ""))


def baixar_rede(url: str, sha256: str, destino: Path, variavel: str = "FM_REDE", nome: str = "a tabela de ruas", limite: int | None = None) -> None:
    """Fetches the street table when it is not on disk (a host built from Git has no ``data/``), and refuses it unless the hash matches.

    The hash is mandatory: the file is loaded into the process, so a swapped file must never be accepted. HTTPS only (plain HTTP is allowed
    for a loopback address, to test). The download goes to a temporary file and replaces the target atomically."""
    import hashlib

    import requests

    limite = limite or MAX_REDE_BYTES   # read at call time, so the default can be adjusted
    partes = urlparse(url)
    if partes.scheme != "https" and not (partes.scheme == "http" and partes.hostname in ("127.0.0.1", "localhost")):
        raise SystemExit(f"{variavel}_URL: use um endereço https")
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256.lower()):
        raise SystemExit(f"{variavel}_SHA256: informe o SHA-256 (64 caracteres hexadecimais) do arquivo; sem ele {nome} não é baixada")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".parte")
    h, total = hashlib.sha256(), 0
    try:
        with requests.get(url, stream=True, timeout=(10, 60)) as r:
            r.raise_for_status()
            with temporario.open("wb") as f:
                for bloco in r.iter_content(1 << 20):
                    total += len(bloco)
                    if total > limite:
                        raise SystemExit(f"{variavel}_URL: o arquivo excede o limite de {limite // (1024 * 1024)} MB")
                    h.update(bloco); f.write(bloco)
        if h.hexdigest() != sha256.lower():
            raise SystemExit(f"O arquivo baixado ({nome}) não confere com {variavel}_SHA256: arquivo descartado")
        os.replace(temporario, destino)
        print(f"{nome} baixada ({total / 1e6:.1f} MB) e verificada", file=sys.stderr, flush=True)
    except requests.RequestException as erro:
        raise SystemExit(f"Não foi possível baixar {nome}: {type(erro).__name__}") from None
    finally:
        temporario.unlink(missing_ok=True)


def montar(raiz: Path = ROOT, env=os.environ) -> tuple[Servico, str]:
    """The service wired from the repository's data and the environment; the CORS origin to use.

    Paths can be moved to a persistent volume with ``FM_REDE`` (street table) and ``FM_OCORRENCIAS`` (occurrence file)."""
    ler_env(raiz / ".env", env)
    token = validar_token(env.get("OPERADOR_TOKEN"))
    if env.get("FM_SITE"):   # the generated site (state forecast and layers) on a persistent volume; source files still win
        global RAIZES
        RAIZES = (STATIC, Path(env["FM_SITE"]))
    if (env.get("FM_ARQUIVO_PWA") or "").strip().lower() in ("1", "true", "sim"):   # opt-in: o PWA arquivado volta a ser servido (testes e retomada da frente de monitoramento)
        RAIZES = tuple(r for r in RAIZES if r != ARQUIVO) + (ARQUIVO,)
    global MAPA_ARQUIVO, FASE3_RAIZ, DRENAGEM_RAIZ, GEOAI_RAIZ
    MAPA_ARQUIVO = Path(env.get("FM_MAPA") or MAPA_ARQUIVO)
    FASE3_RAIZ = Path(env.get("FM_FASE3") or FASE3_RAIZ)
    DRENAGEM_RAIZ = Path(env.get("FM_DRENAGEM") or DRENAGEM_RAIZ)
    GEOAI_RAIZ = Path(env.get("FM_GEOAI") or GEOAI_RAIZ)
    if not MAPA_ARQUIVO.exists() and env.get("FM_MAPA_URL"):   # a host built from Git has no data/: fetch the basemap once, verified
        baixar_rede(env["FM_MAPA_URL"], env.get("FM_MAPA_SHA256", ""), MAPA_ARQUIVO, "FM_MAPA", "o mapa-base", MAX_MAPA_BYTES)
    config = load_config()
    destino = Path(env.get("FM_REDE") or resolve("data/processed/rede_poa.parquet"))
    if not destino.exists() and env.get("FM_REDE_URL"):
        baixar_rede(env["FM_REDE_URL"], env.get("FM_REDE_SHA256", ""), destino)
    if not destino.exists():
        raise SystemExit(f"Falta a tabela de ruas ({destino}). Gere com: python -m flooding_mapping.rede_poa (ou aponte FM_REDE)")
    rede = rt.Rede(pd.read_parquet(destino), config["roteamento"])
    from . import pois as pois_mod

    pois = pois_mod.carregar(env.get("FM_POIS") or None)
    from . import territorio as territorio_mod

    territorio = territorio_mod.carregar(env.get("FM_TERRITORIO") or None)
    lat, lon = float(rede.no_lat.mean()), float(rede.no_lon.mean())
    from .cobertura import yaml_territorios

    arquivo = resolve("src/flooding_mapping/app/static/data/cobertura_rs.json")
    cobertura = json.loads(arquivo.read_text()) if arquivo.exists() else None
    servico = Servico(rede, ChuvaHoraria(lat, lon), oc.Ocorrencias(Path(env.get("FM_OCORRENCIAS") or resolve("data/operacional/ocorrencias.jsonl"))),
                      Explicador(gemini.do_ambiente(env)), config["risco_trecho"], token_operador=token,
                      territorios=yaml_territorios(), resumo_rs=cobertura["estado"] if cobertura else None, cobertura_rs=cobertura, validacao=resumo_da_auditoria(),
                      meta_dados={"rede": destino.name, "gerada_em": time.strftime("%Y-%m-%d", time.localtime(destino.stat().st_mtime))},
                      pois=pois, params_aprendizado=config.get("aprendizado"), territorio=territorio)
    return servico, (env.get("CORS_ORIGEM") or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor do Flooding Mapping (dashboard, PWA e API)")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--gerar-token", action="store_true", help="imprime um token de operador aleatório (não o grava em lugar nenhum)")
    args = parser.parse_args()
    if args.gerar_token:
        print(secrets.token_urlsafe(32))
        return
    servico, cors = montar()
    confiaveis = proxies_confiaveis(os.environ.get("PROXIES_CONFIAVEIS", ""))
    perdidos = servico.store.expirar(90)  # retention: reports and records older than 90 days are dropped at start
    demo = None
    if (os.environ.get("FM_DEMONSTRACAO") or "").strip().lower() in ("1", "true", "sim"):
        from .demonstracao import criar_servico_demo
        demo = criar_servico_demo(servico)
    servidor = ThreadingHTTPServer((args.host, args.port), criar_handler(servico, cors, confiaveis=confiaveis, servico_demo=demo))
    servidor.daemon_threads = True
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))   # a platform stop is a clean stop
    print(f"http://{args.host}:{args.port}/  |  provedor de linguagem: "
          f"{'configurado' if servico.explicador.provedor else 'não configurado (textos determinísticos)'}  |  "
          f"confirmação de ocorrências: {'ATIVA' if servico.token_operador else 'DESATIVADA (OPERADOR_TOKEN não definido)'}  |  "
          f"modo de demonstração: {'DISPONÍVEL (dados sintéticos, isolados)' if demo else 'desligado'}  |  "
          f"proxies confiáveis: {len(confiaveis)}  |  ocorrências: {len(servico.store.listar())} ({perdidos} expiradas, {servico.store.linhas_invalidas} linhas inválidas)", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
        print("servidor encerrado", flush=True)


if __name__ == "__main__":
    main()
