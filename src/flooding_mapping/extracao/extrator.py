"""Documents in, candidate events out. Nothing leaves here as a label: every candidate is ``pendente`` until a person reviews it."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone

from ..linguagem.gemini import LinguagemIndisponivel
from .esquema import ESQUEMA, MAX_TEXTO, SISTEMA, VERSAO, validar_evento

TIPOS_DE_FONTE = ("boletim", "noticia", "relato")


@dataclass(frozen=True)
class Fonte:
    """Where texts come from. ``permitida`` is a decision of the author (licence and terms of use), recorded, never assumed."""
    id: str
    nome: str
    tipo: str
    licenca: str
    permitida: bool
    url: str = ""

    def __post_init__(self):
        if self.tipo not in TIPOS_DE_FONTE:
            raise ValueError(f"tipo de fonte inválido: {self.tipo}")


@dataclass(frozen=True)
class Documento:
    fonte_id: str
    texto: str
    url: str = ""
    publicado_em: date | None = None

    @property
    def id(self) -> str:
        return hashlib.sha256(f"{self.fonte_id}\n{self.url}\n{self.texto}".encode()).hexdigest()[:16]


class OrcamentoEsgotado(RuntimeError):
    """The daily limit of model calls was reached; the remaining documents wait for the next run."""


def extrair(doc: Documento, provedor, fonte: Fonte | None = None, max_saida: int = 1500) -> dict:
    """``{"candidatos": [...], "rejeitados": [{"motivo", "evento"}], "cortado": bool}`` for one document.

    A source that is not marked ``permitida`` is refused before any call. The model failing is raised as ``LinguagemIndisponivel``: the caller
    decides to retry, never to guess."""
    if fonte is not None and not fonte.permitida:
        raise PermissionError(f"fonte não autorizada para extração: {fonte.id}")
    texto = doc.texto[:MAX_TEXTO]
    contexto = f"Data de publicação: {doc.publicado_em.isoformat()}\n\n" if doc.publicado_em else ""
    bruto = provedor.estruturar(SISTEMA, contexto + texto, ESQUEMA, max_saida=max_saida)
    eventos = bruto.get("eventos")
    if not isinstance(eventos, list):
        raise LinguagemIndisponivel("resposta_invalida")
    candidatos, rejeitados = [], []
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    modelo = getattr(provedor, "modelo", "desconhecido")
    for n, item in enumerate(eventos[:20]):
        ev, motivo = validar_evento(item, texto, doc.publicado_em)
        if ev is None:
            rejeitados.append({"motivo": motivo, "evento": item if isinstance(item, dict) else None})
            continue
        candidatos.append({"id": f"{doc.id}-{n}", "doc_id": doc.id, "fonte_id": doc.fonte_id, "url": doc.url,
                           "publicado_em": doc.publicado_em.isoformat() if doc.publicado_em else "", "evento": ev,
                           "status": "pendente", "extraido_em": agora, "versao": VERSAO, "modelo": modelo})
    return {"candidatos": candidatos, "rejeitados": rejeitados, "cortado": len(doc.texto) > MAX_TEXTO}
