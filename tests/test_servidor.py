import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest
import requests
from rede_sintetica import D, O
from test_servico import SAIDA, Provedor, montar

from flooding_mapping import servidor as srv


@pytest.fixture
def api():
    """A live server on a free port; ``abrir(provedor, token, cors)`` builds the service behind it."""
    abertos = []

    def abrir(provedor=None, token="", cors="", store=None, **kw):
        servico, rede = montar(provedor=provedor, token=token, store=store, **kw)
        servidor = ThreadingHTTPServer(("127.0.0.1", 0), srv.criar_handler(servico, cors, srv.Limitador()))
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        abertos.append(servidor)
        base = f"http://127.0.0.1:{servidor.server_address[1]}"
        return base, servico, rede
    yield abrir
    for s in abertos:
        s.shutdown()


CORPO = {"origem": {"lon": O[0], "lat": O[1]}, "destino": {"lon": D[0], "lat": D[1]}, "modal": "carro", "saida": SAIDA}


def test_health_overview_forecast_map_and_provenance_answer_strict_json(api):
    base, _, _ = api()
    for caminho in ("/api/saude", "/api/visao-geral", "/api/previsao?horas=6", "/api/risco?h=2", "/api/proveniencia", "/api/ocorrencias"):
        r = requests.get(base + caminho)
        assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store", caminho
        json.loads(r.text, parse_constant=lambda c: pytest.fail(f"{c} em {caminho}"))  # no NaN/Infinity in the answers


def test_a_route_request_returns_three_routes_and_a_deterministic_alert(api):
    base, _, _ = api()
    r = requests.post(base + "/api/rotas", json=CORPO).json()
    assert set(r["rotas"]) == {"habitual", "menor_exposicao", "alternativa"} and r["alerta"]["texto"]
    assert requests.delete(base + f"/api/analises/{r['analise_id']}").json() == {"apagada": True}
    assert requests.post(base + "/api/explicacao", json={"analise_id": r["analise_id"]}).status_code == 404


def test_the_server_works_without_a_language_provider(api):
    base, _, _ = api(provedor=None)
    a = requests.post(base + "/api/rotas", json=CORPO).json()
    e = requests.post(base + "/api/explicacao", json={"analise_id": a["analise_id"], "contextualizar": True}).json()
    assert e["origem"] == "deterministico" and e["motivo"] == "nao_configurado" and e["texto"]
    assert requests.get(base + "/api/saude").json()["provedor_de_linguagem"] is False


def test_bad_input_gets_a_clear_422_and_unknown_routes_a_404(api):
    base, _, _ = api()
    assert requests.post(base + "/api/rotas", json={**CORPO, "modal": "foguete"}).status_code == 422
    assert requests.post(base + "/api/rotas", data="isto não é json").status_code == 422
    assert requests.post(base + "/api/rotas", data=json.dumps([1, 2])).status_code == 422
    assert requests.post(base + "/api/rotas", data=b"x" * (srv.MAX_CORPO + 1)).status_code == 422
    assert requests.get(base + "/api/nada").status_code == 404
    assert requests.get(base + "/api/trecho?id=inexistente").status_code == 404


def test_confirming_an_occurrence_needs_the_operator_token(api):
    base, servico, rede = api()  # no token configured: the route is off
    rel = requests.post(base + "/api/relatos", json={"texto": "rua alagada", "lon": O[0], "lat": O[1]}).json()
    assert rel["situacao"] == "reportada"
    corpo = {"situacao": "confirmada", "evidencia": "Guarda municipal no local, via interditada"}
    assert requests.post(base + f"/api/ocorrencias/{rel['id']}", json=corpo).status_code == 403
    base, servico, rede = api(token="segredo-do-operador")
    rel = requests.post(base + "/api/relatos", json={"texto": "rua alagada", "lon": O[0], "lat": O[1]}).json()
    assert requests.post(base + f"/api/ocorrencias/{rel['id']}", json=corpo).status_code == 403
    errado = requests.post(base + f"/api/ocorrencias/{rel['id']}", json=corpo, headers={"Authorization": "Bearer outro"})
    assert errado.status_code == 403
    ok = requests.post(base + f"/api/ocorrencias/{rel['id']}", json=corpo, headers={"Authorization": "Bearer segredo-do-operador"})
    assert ok.status_code == 200 and ok.json()["situacao"] == "confirmada"
    assert "segredo-do-operador" not in ok.text and "segredo-do-operador" not in requests.get(base + "/api/saude").text


def test_a_user_report_cannot_confirm_itself_through_the_api(api):
    base, servico, _ = api(token="t")
    rel = requests.post(base + "/api/relatos", json={"texto": "x", "lon": O[0], "lat": O[1], "situacao": "confirmada",
                                                      "confiabilidade": "alta"}).json()
    assert servico.store.obter(rel["id"])["situacao"] == "reportada" and servico.store.interdicoes(72) == []


def test_rate_limits_protect_the_expensive_routes(api):
    base, _, _ = api()
    codigos = [requests.post(base + "/api/rotas", json={}).status_code for _ in range(22)]
    assert codigos[:20] == [422] * 20 and codigos[20:] == [429, 429]


def test_internal_errors_do_not_leak_details(api, capsys):
    base, servico, _ = api()
    servico.saude = lambda: (_ for _ in ()).throw(RuntimeError("SEGREDO-INTERNO /home/usuario"))
    r = requests.get(base + "/api/saude")
    assert r.status_code == 500 and "SEGREDO" not in r.text and r.json() == {"erro": "erro interno"}


def test_requests_are_not_logged_so_places_never_reach_the_logs(api, capsys):
    base, _, _ = api()
    requests.post(base + "/api/rotas", json=CORPO)
    requests.get(base + "/api/risco?h=1")
    saida = capsys.readouterr()
    assert str(O[0]) not in saida.out + saida.err and "/api/" not in saida.out + saida.err


def test_static_files_are_served_with_security_headers_and_no_path_traversal(api):
    base, _, _ = api()
    r = requests.get(base + "/")
    assert r.status_code == 200 and "text/html" in r.headers["Content-Type"]
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"] and r.headers["X-Content-Type-Options"] == "nosniff"
    host, port = base.removeprefix("http://").split(":")
    for caminho in ("/../../config/analysis.yaml", "/..%2f..%2fconfig/analysis.yaml", "/%2e%2e/%2e%2e/.env", "/index.html/../../servidor.py"):
        c = http.client.HTTPConnection(host, int(port))
        c.request("GET", caminho)
        resposta = c.getresponse()
        assert resposta.status == 404, caminho
        assert b"OPERADOR_TOKEN" not in resposta.read()


def test_cors_is_off_unless_an_origin_is_configured(api):
    base, _, _ = api()
    assert "Access-Control-Allow-Origin" not in requests.get(base + "/api/saude").headers
    base, _, _ = api(cors="https://exemplo.github.io")
    assert requests.get(base + "/api/saude").headers["Access-Control-Allow-Origin"] == "https://exemplo.github.io"
    pre = requests.options(base + "/api/rotas")
    assert pre.status_code == 204 and "POST" in pre.headers["Access-Control-Allow-Methods"]


def test_the_env_file_fills_missing_variables_but_never_overrides_the_real_environment(tmp_path):
    arquivo = tmp_path / ".env"
    arquivo.write_text("# comentário\nGEMINI_API_KEY=abc\nGEMINI_MODEL=\"modelo-x\"\nOPERADOR_TOKEN=do-arquivo\nVAZIA=\n")
    env = {"OPERADOR_TOKEN": "do-ambiente"}
    srv.ler_env(arquivo, env)
    assert env["GEMINI_API_KEY"] == "abc" and env["GEMINI_MODEL"] == "modelo-x" and env["OPERADOR_TOKEN"] == "do-ambiente"
    srv.ler_env(tmp_path / "nao-existe", env)  # a missing file is fine
