"""Gemini over its public REST API: one implementation of the language provider.

The rest of the system only knows ``gerar`` and ``LinguagemIndisponivel``; replacing the provider
means writing another class with the same two things. The key travels in a header (never in the URL),
is read from the environment and never logged. Errors are mapped to a short code so that no response
body, URL or key can leak into a message.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import requests

from . import ferramentas

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT_S = 15
MAX_RODADAS = 3
MAX_SAIDA_TOKENS = 600


class LinguagemIndisponivel(RuntimeError):
    """The provider cannot answer. ``codigo`` is one of the keys of ``MENSAGENS``."""

    def __init__(self, codigo: str):
        super().__init__(MENSAGENS.get(codigo, codigo))
        self.codigo = codigo


MENSAGENS = {
    "nao_configurado": "provedor de linguagem não configurado",
    "autenticacao": "chave do provedor de linguagem recusada",
    "limite": "limite de requisições do provedor de linguagem atingido",
    "limite_local": "limite local de consultas ao provedor de linguagem atingido",
    "tempo_esgotado": "o provedor de linguagem não respondeu a tempo",
    "indisponivel": "provedor de linguagem indisponível",
    "resposta_invalida": "resposta do provedor de linguagem inválida",
}


class Gemini:
    def __init__(self, chave: str, modelo: str, http=requests, timeout: float = TIMEOUT_S):
        if not chave or not modelo:
            raise LinguagemIndisponivel("nao_configurado")
        self._chave, self.modelo, self._http, self._timeout = chave, modelo, http, timeout

    def _chamar(self, corpo: dict) -> dict:
        try:
            resposta = self._http.post(f"{BASE}/{self.modelo}:generateContent", json=corpo, timeout=self._timeout,
                                       headers={"x-goog-api-key": self._chave})
        except requests.Timeout:
            raise LinguagemIndisponivel("tempo_esgotado") from None
        except requests.RequestException:
            raise LinguagemIndisponivel("indisponivel") from None
        if resposta.status_code in (401, 403) or (resposta.status_code == 400 and "API key" in resposta.text[:400]):
            raise LinguagemIndisponivel("autenticacao")
        if resposta.status_code == 429:
            raise LinguagemIndisponivel("limite")
        if resposta.status_code >= 500:
            raise LinguagemIndisponivel("indisponivel")
        if resposta.status_code != 200:
            raise LinguagemIndisponivel("resposta_invalida")
        try:
            return resposta.json()
        except ValueError:
            raise LinguagemIndisponivel("resposta_invalida") from None

    @staticmethod
    def _partes(dados: dict) -> list[dict]:
        try:
            partes = dados["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            raise LinguagemIndisponivel("resposta_invalida") from None
        if not isinstance(partes, list):
            raise LinguagemIndisponivel("resposta_invalida")
        return partes

    def gerar(self, sistema: str, pergunta: str, executar: Callable[[str, object], dict] | None = None,
              declaracoes: list[dict] | None = None) -> str:
        """Text answer; the model may ask for the declared operations, at most ``MAX_RODADAS`` rounds."""
        conversa = [{"role": "user", "parts": [{"text": pergunta}]}]
        corpo = {"systemInstruction": {"parts": [{"text": sistema}]},
                 "generationConfig": {"temperature": 0.2, "maxOutputTokens": MAX_SAIDA_TOKENS}}
        if declaracoes:
            corpo["tools"] = [{"functionDeclarations": declaracoes}]
        for _ in range(MAX_RODADAS + 1):
            partes = self._partes(self._chamar({**corpo, "contents": conversa}))
            chamadas = [p["functionCall"] for p in partes if isinstance(p, dict) and "functionCall" in p]
            if not chamadas:
                texto = "".join(p.get("text", "") for p in partes if isinstance(p, dict)).strip()
                if not texto:
                    raise LinguagemIndisponivel("resposta_invalida")
                return texto
            if executar is None:
                raise LinguagemIndisponivel("resposta_invalida")
            respostas = []
            for chamada in chamadas[:3]:
                try:
                    resultado = executar(chamada.get("name"), chamada.get("args"))
                except ferramentas.FerramentaInvalida as erro:
                    resultado = {"erro": str(erro)}
                respostas.append({"functionResponse": {"name": str(chamada.get("name"))[:60], "response": {"resultado": resultado}}})
            conversa += [{"role": "model", "parts": partes}, {"role": "user", "parts": respostas}]
        raise LinguagemIndisponivel("resposta_invalida")  # kept asking for operations: give up

    def estruturar(self, sistema: str, texto: str, esquema: dict) -> dict:
        """One call, no operations, answer forced into ``esquema`` (a JSON schema)."""
        corpo = {"systemInstruction": {"parts": [{"text": sistema}]},
                 "contents": [{"role": "user", "parts": [{"text": texto}]}],
                 "generationConfig": {"temperature": 0, "maxOutputTokens": 300, "responseMimeType": "application/json",
                                      "responseSchema": esquema}}
        partes = self._partes(self._chamar(corpo))
        try:
            dados = json.loads("".join(p.get("text", "") for p in partes if isinstance(p, dict)))
        except ValueError:
            raise LinguagemIndisponivel("resposta_invalida") from None
        if not isinstance(dados, dict):
            raise LinguagemIndisponivel("resposta_invalida")
        return dados


def do_ambiente(env) -> Gemini | None:
    """The configured provider, or ``None`` when the key or the model is missing."""
    chave, modelo = (env.get("GEMINI_API_KEY") or "").strip(), (env.get("GEMINI_MODEL") or "").strip()
    return Gemini(chave, modelo) if chave and modelo else None
