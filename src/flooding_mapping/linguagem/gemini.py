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
MAX_SAIDA_TOKENS = 1024   # models that think count their thinking against this limit: too small and the answer comes back empty


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
    "limite_de_tokens": "a resposta do provedor de linguagem foi cortada pelo limite de tokens",
}


class Gemini:
    def __init__(self, chave: str, modelo: str, http=requests, timeout: float = TIMEOUT_S, pensamento: str = "minimal"):
        if not chave or not modelo:
            raise LinguagemIndisponivel("nao_configurado")
        self._chave, self.modelo, self._http, self._timeout = chave, modelo, http, timeout
        self.pensamento = pensamento           # thinking level: explaining a computed result needs none, and thinking eats the output budget
        self._sem_config_de_pensamento = not pensamento
        self.ultimo_uso = self._uso_vazio()   # tokens of the last ``gerar``/``estruturar`` (all rounds), for cost and limits

    @staticmethod
    def _uso_vazio() -> dict:
        return {"chamadas": 0, "entrada": 0, "saida": 0, "pensamento": 0}

    def _somar_uso(self, dados: dict) -> None:
        meta = dados.get("usageMetadata") or {}
        self.ultimo_uso["chamadas"] += 1
        self.ultimo_uso["entrada"] += int(meta.get("promptTokenCount") or 0)
        self.ultimo_uso["saida"] += int(meta.get("candidatesTokenCount") or 0)
        self.ultimo_uso["pensamento"] += int(meta.get("thoughtsTokenCount") or 0)

    def _chamar(self, corpo: dict) -> dict:
        if not self._sem_config_de_pensamento:
            corpo = {**corpo, "generationConfig": {**corpo.get("generationConfig", {}), "thinkingConfig": {"thinkingLevel": self.pensamento}}}
        try:
            resposta = self._http.post(f"{BASE}/{self.modelo}:generateContent", json=corpo, timeout=self._timeout,
                                       headers={"x-goog-api-key": self._chave})
        except requests.Timeout:
            raise LinguagemIndisponivel("tempo_esgotado") from None
        except requests.RequestException:
            raise LinguagemIndisponivel("indisponivel") from None
        if resposta.status_code == 400 and not self._sem_config_de_pensamento and "thinking" in resposta.text[:600].lower():
            self._sem_config_de_pensamento = True   # this model family refuses the setting: ask once more without it, and stop sending it
            return self._chamar({**corpo, "generationConfig": {k: v for k, v in corpo["generationConfig"].items() if k != "thinkingConfig"}})
        if resposta.status_code in (401, 403) or (resposta.status_code == 400 and "API key" in resposta.text[:400]):
            raise LinguagemIndisponivel("autenticacao")
        if resposta.status_code == 429:
            raise LinguagemIndisponivel("limite")
        if resposta.status_code >= 500:
            raise LinguagemIndisponivel("indisponivel")
        if resposta.status_code != 200:
            raise LinguagemIndisponivel("resposta_invalida")
        try:
            dados = resposta.json()
        except ValueError:
            raise LinguagemIndisponivel("resposta_invalida") from None
        if isinstance(dados, dict):
            self._somar_uso(dados)
        return dados

    @staticmethod
    def _partes(dados: dict) -> list[dict]:
        try:
            candidato = dados["candidates"][0]
        except (KeyError, IndexError, TypeError):
            raise LinguagemIndisponivel("resposta_invalida") from None
        if candidato.get("finishReason") == "MAX_TOKENS":   # cut off, even if some text came: a half sentence is never shown
            raise LinguagemIndisponivel("limite_de_tokens")
        try:
            partes = candidato["content"]["parts"]
        except (KeyError, TypeError):
            raise LinguagemIndisponivel("resposta_invalida") from None
        if not isinstance(partes, list):
            raise LinguagemIndisponivel("resposta_invalida")
        return partes

    def gerar(self, sistema: str, pergunta: str, executar: Callable[[str, object], dict] | None = None,
              declaracoes: list[dict] | None = None) -> str:
        """Text answer; the model may ask for the declared operations, at most ``MAX_RODADAS`` rounds."""
        self.ultimo_uso = self._uso_vazio()
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
        self.ultimo_uso = self._uso_vazio()
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
    return Gemini(chave, modelo, pensamento=(env.get("GEMINI_PENSAMENTO") if env.get("GEMINI_PENSAMENTO") is not None else "minimal").strip()) if chave and modelo else None
