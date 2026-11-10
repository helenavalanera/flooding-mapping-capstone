import json

import pytest
import requests

from flooding_mapping.linguagem import explicar, ferramentas, gemini
from flooding_mapping.linguagem.gemini import Gemini, LinguagemIndisponivel

# ---------------------------------------------------------------- contratos das ferramentas


@pytest.mark.parametrize("nome, args, trecho", [
    ("drop_table", {}, "desconhecida"),
    ("analyze_route_risk", {"rota": "habitual", "analise_id": "outra"}, "não permitidos"),   # the provider cannot pick the analysis
    ("analyze_route_risk", {}, "falta"),
    ("analyze_route_risk", {"rota": "../../etc"}, "use um de"),
    ("get_weather_forecast", {"horas": 500}, "fora do intervalo"),
    ("get_weather_forecast", {"horas": "12"}, "inteiro"),
    ("get_weather_forecast", {"horas": True}, "inteiro"),
    ("get_weather_forecast", {"horas": 1.5}, "inteiro"),
    ("calculate_alternative_routes", {"aversao": 11}, "fora do intervalo"),
    ("calculate_alternative_routes", {"aversao": "alta"}, "número"),
    ("get_nearby_incidents", "SELECT * FROM x", "objeto"),
])
def test_calls_outside_the_closed_schema_are_refused(nome, args, trecho):
    with pytest.raises(ferramentas.FerramentaInvalida, match=trecho):
        ferramentas.validar(nome, args)


def test_valid_calls_pass_and_integers_are_normalised():
    assert ferramentas.validar("get_weather_forecast", {"horas": 12.0}) == {"horas": 12}
    assert ferramentas.validar("get_weather_forecast", None) == {}
    assert ferramentas.validar("analyze_route_risk", {"rota": "alternativa"}) == {"rota": "alternativa"}


def test_the_five_operations_of_the_contract_exist_and_declare_no_free_text_or_identifier_arguments():
    nomes = {d["name"] for d in ferramentas.DECLARACOES}
    assert nomes == {"get_weather_forecast", "analyze_route_risk", "calculate_alternative_routes", "get_nearby_incidents",
                     "get_risk_explanation"}
    for d in ferramentas.DECLARACOES:
        for regra in d["parameters"]["properties"].values():
            assert regra["type"] != "string" or "enum" in regra  # strings only from a closed list


def test_a_huge_result_is_replaced_not_forwarded():
    manip = {"get_weather_forecast": lambda **kw: {"x": "a" * 10_000}}
    assert "erro" in ferramentas.executar("get_weather_forecast", {}, manip)


# ---------------------------------------------------------------- cliente do provedor


class Resp:
    def __init__(self, status=200, corpo=None, texto=""):
        self.status_code, self._corpo, self.text = status, corpo, texto or json.dumps(corpo or {})

    def json(self):
        if self._corpo is None:
            raise ValueError("json")
        return self._corpo


def texto(t):
    return Resp(200, {"candidates": [{"content": {"parts": [{"text": t}]}}]})


def chamada(nome, args):
    return Resp(200, {"candidates": [{"content": {"parts": [{"functionCall": {"name": nome, "args": args}}]}}]})


class Http:
    def __init__(self, *respostas):
        self.respostas, self.pedidos = list(respostas), []

    def post(self, url, json=None, timeout=None, headers=None):
        self.pedidos.append({"url": url, "json": json, "timeout": timeout, "headers": headers})
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def cliente(*respostas, chave="CHAVE-SECRETA"):
    http = Http(*respostas)
    return Gemini(chave, "modelo-x", http=http), http


def test_the_key_goes_in_a_header_never_in_the_url_or_the_body():
    c, http = cliente(texto("ok"))
    assert c.gerar("sis", "pergunta") == "ok"
    p = http.pedidos[0]
    assert p["headers"] == {"x-goog-api-key": "CHAVE-SECRETA"}
    assert "CHAVE" not in p["url"] and "CHAVE" not in json.dumps(p["json"]) and p["timeout"] <= 20


def test_the_model_can_ask_for_operations_and_gets_validated_structured_answers():
    c, http = cliente(chamada("analyze_route_risk", {"rota": "habitual"}), texto("Explicação final."))
    visto = []
    saida = c.gerar("sis", "p", executar=lambda n, a: visto.append((n, a)) or {"km": 1}, declaracoes=ferramentas.DECLARACOES)
    assert saida == "Explicação final." and visto == [("analyze_route_risk", {"rota": "habitual"})]
    segunda = http.pedidos[1]["json"]["contents"]
    assert segunda[-1]["parts"][0]["functionResponse"]["response"] == {"resultado": {"km": 1}}


def test_an_invalid_operation_asked_by_the_model_returns_an_error_to_it_and_runs_nothing():
    def executar(n, a):
        return ferramentas.executar(n, a, {})
    c, http = cliente(chamada("run_sql", {"q": "drop"}), texto("certo"))
    assert c.gerar("s", "p", executar=executar, declaracoes=ferramentas.DECLARACOES) == "certo"
    resposta = http.pedidos[1]["json"]["contents"][-1]["parts"][0]["functionResponse"]["response"]["resultado"]
    assert "desconhecida" in resposta["erro"]


def test_a_model_that_never_stops_asking_for_operations_is_cut_off():
    c, _ = cliente(*[chamada("get_weather_forecast", {})] * 10)
    with pytest.raises(LinguagemIndisponivel) as erro:
        c.gerar("s", "p", executar=lambda n, a: {}, declaracoes=ferramentas.DECLARACOES)
    assert erro.value.codigo == "resposta_invalida"


@pytest.mark.parametrize("resposta, codigo", [
    (Resp(401), "autenticacao"), (Resp(403), "autenticacao"),
    (Resp(400, texto="API key not valid. Please pass a valid API key."), "autenticacao"),
    (Resp(429), "limite"), (Resp(500), "indisponivel"), (Resp(503), "indisponivel"),
    (Resp(404), "resposta_invalida"), (Resp(200, None), "resposta_invalida"),
    (Resp(200, {"candidates": []}), "resposta_invalida"), (Resp(200, {"candidates": [{"content": {"parts": [{"text": ""}]}}]}), "resposta_invalida"),
    (requests.Timeout(), "tempo_esgotado"), (requests.ConnectionError("dns"), "indisponivel"),
])
def test_every_provider_failure_becomes_a_short_code(resposta, codigo):
    c, _ = cliente(resposta)
    with pytest.raises(LinguagemIndisponivel) as erro:
        c.gerar("s", "p")
    assert erro.value.codigo == codigo and "CHAVE" not in str(erro.value)


def test_without_key_or_model_the_provider_is_not_configured():
    assert gemini.do_ambiente({}) is None and gemini.do_ambiente({"GEMINI_API_KEY": "k"}) is None
    assert gemini.do_ambiente({"GEMINI_API_KEY": "k", "GEMINI_MODEL": "m"}).modelo == "m"
    with pytest.raises(LinguagemIndisponivel):
        Gemini("", "m")


def test_structured_answers_must_be_a_json_object():
    c, _ = cliente(texto('{"tipo": "alagamento_via"}'))
    assert c.estruturar("s", "t", explicar.ESQUEMA_RELATO) == {"tipo": "alagamento_via"}
    c, _ = cliente(texto("não é json"))
    with pytest.raises(LinguagemIndisponivel):
        c.estruturar("s", "t", explicar.ESQUEMA_RELATO)
    c, _ = cliente(texto("[1, 2]"))
    with pytest.raises(LinguagemIndisponivel):
        c.estruturar("s", "t", explicar.ESQUEMA_RELATO)


# ---------------------------------------------------------------- alertas e explicação


def rota(tempo_min, exposicao, km_att=0.0, km_alto=0.0, trechos=(), pico=None):
    return {"arestas": [1], "coordenadas": [[-51.2, -30.0]], "tempo_s": tempo_min * 60.0, "distancia_km": 10.0,
            "exposicao_km_risco": exposicao, "km_atencao_ou_alto": km_att, "km_alto": km_alto, "km_sem_estimativa": 0.5,
            "instante_do_pico": pico, "trechos_de_risco": list(trechos), "chegada": "2026-11-09 18:00:00"}


def trecho(nome="Av. Beira-Rio", ocorrencia=None, peso=0.9, classe="alto"):
    return {"nome": nome, "classe": classe, "km": 0.8, "inicio": "2026-11-09 17:40:00", "fim": "2026-11-09 17:50:00",
            "escore": 0.7, "peso": peso, "ocorrencia": ocorrencia, "segmentos": ["1:2:3"], "fator": 0.8}


CASO = {"habitual": rota(32, 4.0, 3.0, 1.0, [trecho()], "2026-11-09 17:45:00"), "menor_exposicao": rota(38, 1.0, 0.5),
        "alternativa": rota(35, 2.5, 1.5, 0, [trecho("Rua X", classe="atencao")])}
METEO = {"total_na_janela_mm": 18.0}


def test_the_deterministic_alert_follows_the_documented_wording_and_never_calls_a_route_safe():
    a = explicar.alerta(CASO, METEO)
    assert a["nivel"] == "alto" and "maior exposição estimada" in a["texto"] and "menor exposição estimada" in a["texto"]
    assert "6 min" in a["texto"] and "Você escolhe" in a["texto"] and "Av. Beira-Rio" in a["texto"]
    assert not explicar.PROIBIDAS.search(a["texto"]) and a["motivos"]


def test_with_no_exposure_the_alert_says_estimate_not_guarantee():
    seco = {"habitual": rota(20, 0.0)}
    a = explicar.alerta(seco, {"total_na_janela_mm": 0.0})
    assert a["nivel"] == "sem_risco_estimado" and "garantia" in a["texto"] and not explicar.PROIBIDAS.search(a["texto"])
    assert "mas não identificamos" in explicar.alerta(seco, {"total_na_janela_mm": 12.0})["texto"]


def test_when_no_better_route_exists_the_alert_says_so():
    a = explicar.alerta({"habitual": CASO["habitual"]}, METEO)
    assert "Não encontramos alternativa" in a["texto"]


def test_comparison_labels_rank_the_estimated_exposure():
    por = {c["rota"]: c for c in explicar.comparar(CASO)}
    assert por["menor_exposicao"]["rotulo"] == "menor exposição estimada" and por["menor_exposicao"]["acrescimo_min"] == 6
    assert por["habitual"]["rotulo"] == "maior exposição estimada" and por["alternativa"]["rotulo"] == "exposição estimada intermediária"
    assert por["menor_exposicao"]["reducao_exposicao_pct"] == 75


def test_what_the_provider_sees_has_no_coordinates_ids_or_endpoints():
    comp = explicar.comparar(CASO)
    resumo = explicar.resumo_rota(CASO["habitual"], "habitual", comp)
    texto_json = json.dumps(resumo, ensure_ascii=False)
    assert "-51.2" not in texto_json and "1:2:3" not in texto_json and "coordenadas" not in texto_json
    assert resumo["trechos_mais_expostos"][0]["nome"] == "Av. Beira-Rio" and len(resumo["trechos_mais_expostos"]) <= 5


class Provedor:
    def __init__(self, texto="Sua rota habitual tem maior exposição estimada; é uma estimativa sem validação.", erro=None):
        self.texto, self.erro, self.chamadas = texto, erro, 0

    def gerar(self, sistema, pergunta, executar=None, declaracoes=None):
        self.chamadas += 1
        if self.erro:
            raise self.erro
        return self.texto

    def estruturar(self, sistema, texto, esquema):
        self.chamadas += 1
        if self.erro:
            raise self.erro
        return {"tipo": "alagamento_via", "severidade": "alta", "impacto_circulacao": "interdicao", "descricao": "Rua alagada"}


def explica(exp):
    return exp.explicar({"habitual": {}}, explicar.alerta(CASO, METEO), lambda n, a: {}, ferramentas.DECLARACOES)


def test_without_a_provider_the_deterministic_text_is_returned():
    r = explica(explicar.Explicador(None))
    assert r["origem"] == "deterministico" and r["motivo"] == "nao_configurado" and r["texto"]


def test_the_provider_text_is_used_when_valid_and_cached_afterwards():
    p = Provedor()
    exp = explicar.Explicador(p)
    assert explica(exp)["origem"] == "provedor_de_linguagem"
    assert explica(exp)["motivo"] == "cache" and p.chamadas == 1


@pytest.mark.parametrize("codigo", ["autenticacao", "limite", "tempo_esgotado", "indisponivel", "resposta_invalida"])
def test_any_provider_failure_falls_back_to_the_deterministic_text(codigo):
    r = explica(explicar.Explicador(Provedor(erro=LinguagemIndisponivel(codigo))))
    assert r["origem"] == "deterministico" and r["motivo"] == codigo and "maior exposição estimada" in r["texto"]


@pytest.mark.parametrize("ruim", ["Esta rota é segura, pode ir.", "Sem risco nenhum.", "Garantimos que não alaga.", "x" * 1000, "  "])
def test_an_answer_that_breaks_the_rules_is_replaced(ruim):
    r = explica(explicar.Explicador(Provedor(texto=ruim)))
    assert r["origem"] == "deterministico" and r["motivo"] == "resposta_invalida"


def test_the_local_limit_protects_the_provider_quota():
    t = {"v": 0.0}
    exp = explicar.Explicador(Provedor(texto="a" * 5 + " estimativa"), limite_por_min=2, relogio=lambda: t["v"])
    for i in range(3):  # distinct questions so the cache does not hide the limit
        r = exp.explicar({"habitual": {"i": i}}, explicar.alerta(CASO, METEO), lambda n, a: {}, ferramentas.DECLARACOES)
    assert r["motivo"] == "limite_local" and r["origem"] == "deterministico"
    t["v"] = 61.0
    assert exp.explicar({"habitual": {"i": 9}}, explicar.alerta(CASO, METEO), lambda n, a: {}, ferramentas.DECLARACOES)["origem"] == "provedor_de_linguagem"


def test_a_report_is_structured_by_the_provider_but_stays_valid_when_it_fails():
    ok = explicar.Explicador(Provedor()).interpretar_relato("a rua tá alagada, ninguém passa")
    assert ok["interpretado"] and ok["tipo"] == "alagamento_via" and ok["impacto_circulacao"] == "interdicao"
    falhou = explicar.Explicador(Provedor(erro=LinguagemIndisponivel("limite"))).interpretar_relato("rua alagada")
    assert falhou == {"tipo": "outro", "severidade": "desconhecida", "impacto_circulacao": "desconhecido",
                      "descricao": "rua alagada", "interpretado": False}


def test_invented_fields_in_the_structured_answer_are_discarded():
    class Malicioso(Provedor):
        def estruturar(self, *a):
            return {"tipo": "ufo", "severidade": "extrema", "impacto_circulacao": "interdicao", "descricao": "ok", "situacao": "confirmada"}
    r = explicar.Explicador(Malicioso()).interpretar_relato("texto")
    assert r["tipo"] == "outro" and r["severidade"] == "desconhecida" and "situacao" not in r
