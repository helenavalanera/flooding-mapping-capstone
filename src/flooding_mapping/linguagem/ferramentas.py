"""Contracts of the operations the language provider may ask the backend to run.

The provider never touches routes, weather, incidents or the database: it asks for one of the
five operations below, the backend validates the call and answers with a small structured
result. Rules enforced here, not by the prompt:

* the schema is closed: an unknown operation, an unknown argument, a wrong type or a value out of
  range is refused;
* the analysis an operation works on is bound by the backend to the request that opened the
  session; the provider cannot name another one (``analise_id`` is not an argument);
* results carry aggregates and street names only: no coordinates, no origin or destination, no
  free text written by users, and never more than ``MAX_BYTES`` of JSON;
* nothing here can create, confirm or change an incident, or calculate a route that the backend has
  not already calculated for that analysis.
"""

from __future__ import annotations

import json
from collections.abc import Callable

MAX_BYTES = 4000
ROTAS = ["habitual", "menor_exposicao", "alternativa"]

DECLARACOES = [
    {"name": "get_weather_forecast",
     "description": "Chuva horária prevista (mm) para a cidade nas próximas horas, com o pico e os acumulados.",
     "parameters": {"type": "object", "properties": {"horas": {"type": "integer", "minimum": 1, "maximum": 48}}}},
    {"name": "analyze_route_risk",
     "description": "Resumo do risco estimado de uma rota da análise: tempo, km por classe, trechos e janelas de maior exposição.",
     "parameters": {"type": "object", "properties": {"rota": {"type": "string", "enum": ROTAS}}, "required": ["rota"]}},
    {"name": "calculate_alternative_routes",
     "description": "Compara as rotas já calculadas da análise (tempo e exposição estimada); opcionalmente recalcula com outra aversão ao risco.",
     "parameters": {"type": "object", "properties": {"aversao": {"type": "number", "minimum": 0, "maximum": 10}}}},
    {"name": "get_nearby_incidents",
     "description": "Ocorrências ativas ao longo de uma rota da análise: tipo, situação, confiabilidade e idade, sem texto livre.",
     "parameters": {"type": "object", "properties": {"rota": {"type": "string", "enum": ROTAS}}, "required": ["rota"]}},
    {"name": "get_risk_explanation",
     "description": "Fatores que compõem o risco estimado dos trechos mais expostos de uma rota e a metodologia com seus limites.",
     "parameters": {"type": "object", "properties": {"rota": {"type": "string", "enum": ROTAS}}, "required": ["rota"]}},
]
_SCHEMAS = {d["name"]: d["parameters"] for d in DECLARACOES}


class FerramentaInvalida(ValueError):
    """The provider asked for something the contract does not allow."""


def validar(nome: str, args: object) -> dict:
    """Arguments checked against the closed schema of ``nome``; raises ``FerramentaInvalida``."""
    esquema = _SCHEMAS.get(nome)
    if esquema is None:
        raise FerramentaInvalida(f"operação desconhecida: {str(nome)[:40]}")
    args = {} if args is None else args
    if not isinstance(args, dict):
        raise FerramentaInvalida("argumentos devem ser um objeto")
    extras = set(args) - set(esquema["properties"])
    if extras:
        raise FerramentaInvalida(f"argumentos não permitidos: {', '.join(sorted(map(str, extras)))[:60]}")
    for obrigatorio in esquema.get("required", []):
        if obrigatorio not in args:
            raise FerramentaInvalida(f"falta o argumento {obrigatorio}")
    for chave, valor in args.items():
        regra = esquema["properties"][chave]
        tipo = regra["type"]
        if tipo == "integer" and not (isinstance(valor, (int, float)) and not isinstance(valor, bool) and float(valor).is_integer()):
            raise FerramentaInvalida(f"{chave}: inteiro esperado")
        if tipo == "number" and (not isinstance(valor, (int, float)) or isinstance(valor, bool)):
            raise FerramentaInvalida(f"{chave}: número esperado")
        if tipo == "string" and not isinstance(valor, str):
            raise FerramentaInvalida(f"{chave}: texto esperado")
        if tipo in ("integer", "number") and not regra["minimum"] <= valor <= regra["maximum"]:
            raise FerramentaInvalida(f"{chave}: fora do intervalo {regra['minimum']}..{regra['maximum']}")
        if "enum" in regra and valor not in regra["enum"]:
            raise FerramentaInvalida(f"{chave}: use um de {', '.join(regra['enum'])}")
    return {k: (int(v) if _SCHEMAS[nome]["properties"][k]["type"] == "integer" else v) for k, v in args.items()}


def executar(nome: str, args: object, manipuladores: dict[str, Callable[..., dict]]) -> dict:
    """Run one validated operation; the answer is structured and never larger than ``MAX_BYTES``."""
    limpos = validar(nome, args)
    resposta = manipuladores[nome](**limpos)
    texto = json.dumps(resposta, ensure_ascii=False, default=str)
    if len(texto.encode()) > MAX_BYTES:
        resposta = {"erro": "resposta grande demais", "dica": "peça uma rota ou janela menor"}
    return resposta
