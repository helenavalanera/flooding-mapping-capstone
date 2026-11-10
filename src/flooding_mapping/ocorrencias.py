"""Georeferenced occurrences: reported, confirmed or discarded, with source and reliability.

An occurrence is an *observation* about circulation (a flooded street, a closed road). It is
never produced by a forecast and never inferred from a municipal record: S2iD rows are decrees
without geometry and do not enter here.

Rules that the rest of the system relies on
    * A user report is always stored as ``reportada`` with ``confiabilidade`` ``baixa``; the
      caller cannot choose otherwise.
    * Only ``mudar_situacao`` moves a record, always with a written evidence and an author, and
      every move is kept in ``historico``. A discarded record is final.
    * Only a ``confirmada`` record with ``impacto_circulacao == "interdicao"`` closes a segment
      for routing. A report, however alarming, only raises the estimated risk.
    * The store keeps no user identifier, address or device information.
"""

from __future__ import annotations

import json
import math
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TIPOS = ("alagamento_via", "bloqueio_via", "deslizamento", "queda_de_arvore", "outro")
SEVERIDADES = ("baixa", "media", "alta", "desconhecida")
IMPACTOS = ("nenhum", "parcial", "interdicao", "desconhecido")
SITUACOES = ("reportada", "confirmada", "descartada")
CONFIABILIDADES = ("baixa", "media", "alta")
RS_BOX = (-58.0, -34.0, -48.0, -27.0)  # lon_min, lat_min, lon_max, lat_max
MAX_TEXT = 280
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def agora() -> datetime:
    return datetime.now(timezone.utc)


def _instante(value, campo: str) -> str | None:
    """ISO instant in UTC; a time without zone is read as Brasilia time."""
    if value in (None, ""):
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{campo}: data/hora inválida") from None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=LOCAL_TZ)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _escolha(value, opcoes: tuple, campo: str, padrao: str) -> str:
    value = padrao if value in (None, "") else value
    if value not in opcoes:
        raise ValueError(f"{campo}: use um de {', '.join(opcoes)}")
    return value


def _texto(value, campo: str, limite: int) -> str:
    text = _CONTROL.sub(" ", str(value or "")).strip()
    if len(text) > limite:
        raise ValueError(f"{campo}: no máximo {limite} caracteres")
    return text


def validar(dados: dict) -> dict:
    """Normalized record from untrusted input; raises ``ValueError`` with a user-readable reason."""
    if not isinstance(dados, dict):
        raise ValueError("registro inválido")
    try:
        lon, lat = float(dados["lon"]), float(dados["lat"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("localização: informe lon e lat numéricos") from None
    if not (math.isfinite(lon) and math.isfinite(lat)) or not (
            RS_BOX[0] <= lon <= RS_BOX[2] and RS_BOX[1] <= lat <= RS_BOX[3]):
        raise ValueError("localização fora do Rio Grande do Sul")
    ids = dados.get("segmento_ids") or []
    if not isinstance(ids, list) or len(ids) > 50 or not all(isinstance(i, str) and len(i) < 64 for i in ids):
        raise ValueError("segmento_ids: lista de até 50 identificadores")
    inicio, fim = _instante(dados.get("inicio"), "inicio"), _instante(dados.get("fim"), "fim")
    if inicio and fim and fim < inicio:
        raise ValueError("fim anterior ao início")
    return {
        "tipo": _escolha(dados.get("tipo"), TIPOS, "tipo", "outro"),
        "lon": round(lon, 6), "lat": round(lat, 6), "segmento_ids": ids,
        "data_hora": _instante(dados.get("data_hora"), "data_hora") or agora().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inicio": inicio, "fim": fim,
        "severidade": _escolha(dados.get("severidade"), SEVERIDADES, "severidade", "desconhecida"),
        "impacto_circulacao": _escolha(dados.get("impacto_circulacao"), IMPACTOS, "impacto_circulacao", "desconhecido"),
        "descricao": _texto(dados.get("descricao"), "descricao", MAX_TEXT),
    }


class Ocorrencias:
    """Occurrence store: memory, or an append-only JSON-lines file (latest line per id wins)."""

    def __init__(self, caminho: str | Path | None = None):
        self.caminho = Path(caminho) if caminho else None
        self._registros: dict[str, dict] = {}
        self._lock = threading.Lock()
        self.linhas_invalidas = 0   # a write cut short (power loss) must not stop the service from starting
        if self.caminho and self.caminho.exists():
            for linha in self.caminho.read_text(encoding="utf-8", errors="replace").splitlines():
                if not linha.strip():
                    continue
                try:
                    registro = json.loads(linha)
                    self._registros[registro["id"]] = registro
                except (ValueError, KeyError, TypeError):
                    self.linhas_invalidas += 1

    def _gravar(self, registro: dict) -> None:
        if self.caminho:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with self.caminho.open("a", encoding="utf-8") as arquivo:
                arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
                arquivo.flush()
                os.fsync(arquivo.fileno())

    def registrar(self, dados: dict, fonte: str, origem: str, situacao: str = "reportada",
                  confiabilidade: str = "baixa", evidencia: str = "") -> dict:
        """Add a validated record. ``origem`` states how it was produced (traceability)."""
        base = validar(dados)
        fonte = _texto(fonte, "fonte", 40)
        if not fonte:
            raise ValueError("fonte obrigatória")
        situacao = _escolha(situacao, SITUACOES, "situacao", "reportada")
        if situacao == "confirmada" and len(_texto(evidencia, "evidencia", MAX_TEXT)) < 10:
            raise ValueError("confirmação exige evidência escrita")
        agora_iso = agora().strftime("%Y-%m-%dT%H:%M:%SZ")
        registro = {"id": secrets.token_hex(6), "fonte": fonte, "origem": _texto(origem, "origem", 120),
                    **base, "situacao": situacao,
                    "confiabilidade": _escolha(confiabilidade, CONFIABILIDADES, "confiabilidade", "baixa"),
                    "criado_em": agora_iso, "atualizado_em": agora_iso,
                    "historico": [{"em": agora_iso, "de": None, "para": situacao, "por": fonte,
                                   "evidencia": _texto(evidencia, "evidencia", MAX_TEXT)}]}
        with self._lock:
            self._registros[registro["id"]] = registro
            self._gravar(registro)
        return registro

    def relato(self, dados: dict, origem: str = "relato do usuário") -> dict:
        """A user report: always ``reportada`` and ``baixa``, whatever the caller sends."""
        return self.registrar(dados, fonte="usuario", origem=origem, situacao="reportada", confiabilidade="baixa")

    def mudar_situacao(self, id_: str, nova: str, por: str, evidencia: str,
                       confiabilidade: str | None = None) -> dict:
        nova = _escolha(nova, SITUACOES, "situacao", "")
        evidencia = _texto(evidencia, "evidencia", MAX_TEXT)
        if len(evidencia) < 10:
            raise ValueError("a mudança de situação exige evidência escrita")
        with self._lock:
            registro = self._registros.get(id_)
            if registro is None:
                raise KeyError(id_)
            atual = registro["situacao"]
            if atual == "descartada" or nova == atual or (atual == "confirmada" and nova == "reportada"):
                raise ValueError(f"transição inválida: {atual} -> {nova}")
            agora_iso = agora().strftime("%Y-%m-%dT%H:%M:%SZ")
            registro = {**registro, "situacao": nova, "atualizado_em": agora_iso,
                        "confiabilidade": _escolha(confiabilidade, CONFIABILIDADES, "confiabilidade", registro["confiabilidade"]),
                        "historico": registro["historico"] + [
                            {"em": agora_iso, "de": atual, "para": nova, "por": _texto(por, "por", 40), "evidencia": evidencia}]}
            self._registros[id_] = registro
            self._gravar(registro)
        return registro

    def obter(self, id_: str) -> dict | None:
        return self._registros.get(id_)

    def listar(self, situacao: str | None = None, desde: datetime | None = None) -> list[dict]:
        with self._lock:
            itens = list(self._registros.values())
        if situacao:
            itens = [r for r in itens if r["situacao"] == situacao]
        if desde:
            corte = desde.strftime("%Y-%m-%dT%H:%M:%SZ")
            itens = [r for r in itens if r["data_hora"] >= corte]
        return sorted(itens, key=lambda r: r["data_hora"], reverse=True)

    def ativas(self, validade_h: float, em: datetime | None = None) -> list[dict]:
        """Records that still count: not discarded, and not older than ``validade_h`` (or inside start-end)."""
        em = em or agora()
        out = []
        for r in self.listar():
            if r["situacao"] == "descartada":
                continue
            fim = r["fim"] and datetime.fromisoformat(r["fim"].replace("Z", "+00:00"))
            inicio = datetime.fromisoformat((r["inicio"] or r["data_hora"]).replace("Z", "+00:00"))
            limite = fim if fim else inicio + timedelta(hours=validade_h)
            if inicio - timedelta(hours=1) <= em <= limite:
                out.append(r)
        return out

    def interdicoes(self, validade_h: float, em: datetime | None = None) -> list[dict]:
        """Confirmed closures: the only records that make a segment unavailable for routing."""
        return [r for r in self.ativas(validade_h, em)
                if r["situacao"] == "confirmada" and r["impacto_circulacao"] == "interdicao"]

    def expirar(self, dias: int) -> int:
        """Drop records older than ``dias`` (retention); rewrites the file. Returns how many went."""
        corte = (agora() - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            velhos = [i for i, r in self._registros.items() if r["data_hora"] < corte]
            for i in velhos:
                del self._registros[i]
            if self.caminho and velhos:   # rewrite aside and swap, so a crash never leaves a half-written store
                temporario = self.caminho.with_suffix(".tmp")
                temporario.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in self._registros.values()), encoding="utf-8")
                os.replace(temporario, self.caminho)
        return len(velhos)
