import http.client
import json
import sys
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


def test_a_serialisation_failure_answers_500_instead_of_dropping_the_connection(api):
    base, servico, _ = api()
    servico.saude = lambda: {"valor": float("nan")}   # strict JSON refuses NaN
    r = requests.get(base + "/api/saude")
    assert r.status_code == 500 and r.json() == {"erro": "erro interno"}


def test_generated_files_come_from_the_build_folder_but_source_files_win(api, tmp_path, monkeypatch):
    fonte, build = tmp_path / "fonte", tmp_path / "build"
    for pasta in (fonte, build):
        pasta.mkdir()
    (fonte / "index.html").write_text("<p>da fonte</p>")
    (build / "index.html").write_text("<p>antigo do build</p>")
    (build / "previsao_72h.json").write_text('{"gerado": true}')
    (tmp_path / "segredo.json").write_text('{"segredo": 1}')
    monkeypatch.setattr(srv, "RAIZES", (fonte, build))
    base, _, _ = api()
    assert requests.get(base + "/").text == "<p>da fonte</p>"
    assert requests.get(base + "/previsao_72h.json").json() == {"gerado": True}
    assert requests.get(base + "/nao-existe.json").status_code == 404
    host, port = base.removeprefix("http://").split(":")
    c = http.client.HTTPConnection(host, int(port))
    c.request("GET", "/../segredo.json")           # a sibling of both roots must stay out of reach
    assert c.getresponse().status == 404


def test_only_the_service_worker_may_connect_to_the_map_library_cdn(api):
    base, _, _ = api()
    pagina = requests.get(base + "/pwa/").headers["Content-Security-Policy"]
    sw = requests.get(base + "/pwa/sw.js").headers["Content-Security-Policy"]
    assert "cdnjs" not in pagina.split("connect-src")[1].split(";")[0] and "cdnjs" in sw.split("connect-src")[1].split(";")[0]
    assert requests.get(base + "/pwa/manifest.webmanifest").headers["Content-Type"].startswith("application/manifest+json")


def test_guessing_the_operator_credential_is_blocked_after_a_few_failures(api):
    base, servico, _ = api(token="credencial-correta")
    rel = requests.post(base + "/api/relatos", json={"texto": "x", "lon": O[0], "lat": O[1]}).json()
    corpo = {"situacao": "confirmada", "evidencia": "Guarda municipal no local, via interditada"}
    codigos = [requests.post(base + f"/api/ocorrencias/{rel['id']}", json=corpo, headers={"Authorization": f"Bearer chute{i}"}).status_code
               for i in range(srv.FALHAS_DE_CREDENCIAL_POR_MIN + 4)]
    assert codigos[:srv.FALHAS_DE_CREDENCIAL_POR_MIN] == [403] * srv.FALHAS_DE_CREDENCIAL_POR_MIN and set(codigos[srv.FALHAS_DE_CREDENCIAL_POR_MIN:]) == {429}
    certa = requests.post(base + f"/api/ocorrencias/{rel['id']}", json=corpo, headers={"Authorization": "Bearer credencial-correta"})
    assert certa.status_code == 429 and servico.store.obter(rel["id"])["situacao"] == "reportada"   # locked out: even the right one waits


def test_the_public_list_hides_free_text_and_only_an_operator_sees_it(api):
    base, _, _ = api(token="op")
    requests.post(base + "/api/relatos", json={"texto": "rua alagada, falar com Maria 51 99999-0000", "lon": O[0], "lat": O[1]})
    publica = requests.get(base + "/api/ocorrencias").json()
    assert publica["texto_livre_incluido"] is False and all("descricao" not in r for r in publica["ocorrencias"]) and "99999" not in json.dumps(publica)
    completa = requests.get(base + "/api/ocorrencias", headers={"Authorization": "Bearer op"}).json()
    assert completa["texto_livre_incluido"] is True and any("descricao" in r for r in completa["ocorrencias"])
    assert requests.get(base + "/api/ocorrencias", headers={"Authorization": "Bearer errado"}).status_code == 403


def test_read_requests_are_limited_per_client(api, monkeypatch):
    monkeypatch.setattr(srv, "LIMITE_LEITURA_POR_MIN", 5)
    base, _, _ = api()
    codigos = [requests.get(base + "/api/saude").status_code for _ in range(7)]
    assert codigos == [200] * 5 + [429] * 2


def test_a_directory_without_the_trailing_slash_redirects_so_relative_paths_keep_working(api):
    base, _, _ = api()
    r = requests.get(base + "/pwa", allow_redirects=False)
    assert r.status_code == 301 and r.headers["Location"] == "/pwa/"
    assert requests.get(base + "/pwa").status_code == 200 and requests.get(base + "/pwa").url.endswith("/pwa/")
    assert requests.get(base + "/pwa/pwa.js").status_code == 200


def test_territories_endpoint_serves_the_capabilities_and_the_live_coverage_of_porto_alegre(api):
    import yaml
    from flooding_mapping.config import ROOT
    base, servico, _ = api()
    assert requests.get(base + "/api/territorios").status_code == 404           # not configured: no invented answer
    servico.territorios_config = yaml.safe_load((ROOT / "config" / "territorios.yaml").read_text(encoding="utf-8"))
    t = requests.get(base + "/api/territorios").json()
    assert set(t["territorios"]) == {"rs", "poa"} and t["territorios"]["rs"]["cobertura"] is None
    assert t["territorios"]["poa"]["cobertura"]["dirigivel"]["km"] > 0 and t["territorios"]["rs"]["capacidades"]["rotas"]["estado"] == "indisponivel"


# ---------------------------------------------------------------- proxy, token, métricas e encerramento


@pytest.mark.parametrize("par, cabecalho, confiaveis, esperado", [
    ("203.0.113.9", "1.2.3.4", [], "203.0.113.9"),                              # no trusted proxy configured: header ignored
    ("203.0.113.9", "1.2.3.4", ["10.0.0.0/8"], "203.0.113.9"),                  # peer is not a trusted proxy: header ignored
    ("10.0.0.5", "1.2.3.4", ["10.0.0.0/8"], "1.2.3.4"),                         # trusted peer: believe the client address
    ("10.0.0.5", "9.9.9.9, 1.2.3.4", ["10.0.0.0/8"], "1.2.3.4"),                # a client cannot forge the left of the chain
    ("10.0.0.5", "1.2.3.4, 10.0.0.7", ["10.0.0.0/8"], "1.2.3.4"),               # trusted hops on the right are skipped
    ("10.0.0.5", None, ["10.0.0.0/8"], "10.0.0.5"), ("10.0.0.5", "lixo", ["10.0.0.0/8"], "lixo"),
])
def test_the_client_address_trusts_forwarding_headers_only_from_a_configured_proxy(par, cabecalho, confiaveis, esperado):
    assert srv.ip_do_cliente(par, cabecalho, srv.proxies_confiaveis(",".join(confiaveis))) == esperado


def test_a_forged_forwarding_header_does_not_buy_a_new_rate_limit(api):
    base, _, _ = api()   # no trusted proxy: every request is the same client whatever the header says
    codigos = [requests.post(base + "/api/rotas", json={}, headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code for i in range(22)]
    assert codigos[20:] == [429, 429]


def test_a_malformed_proxy_list_or_a_short_operator_token_stops_the_start():
    with pytest.raises(SystemExit, match="PROXIES_CONFIAVEIS"):
        srv.proxies_confiaveis("10.0.0.0/8, nao-e-ip")
    with pytest.raises(SystemExit, match="ao menos 24"):
        srv.validar_token("curto")
    assert srv.validar_token("") == "" and srv.validar_token("a" * 24) == "a" * 24


def test_health_carries_counters_without_personal_data(api):
    base, _, _ = api()
    requests.post(base + "/api/rotas", json=CORPO)
    requests.get(base + "/api/risco?h=1")
    saude = requests.get(base + "/api/saude").json()
    assert saude["metricas"]["requisicoes"] >= 2 and saude["metricas"]["erros_5xx"] == 0 and saude["metricas"]["latencia_p95_ms"] >= 0
    assert str(O[0]) not in json.dumps(saude)


def test_a_stalled_connection_does_not_hold_a_thread_forever():
    assert 0 < srv.TEMPO_DE_CONEXAO_S <= 30
    handler = srv.criar_handler(montar()[0])
    assert handler.timeout == srv.TEMPO_DE_CONEXAO_S


def test_the_generated_token_is_long_random_and_printed_not_stored(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["servidor", "--gerar-token"])
    srv.main()
    token = capsys.readouterr().out.strip()
    assert len(token) >= srv.TOKEN_MINIMO and srv.validar_token(token) == token


def test_assistant_endpoint_answers_and_is_rate_limited(api):
    from test_servico import COBERTURA, CAPACIDADES
    base, servico, _ = api()
    servico.cobertura_rs, servico.territorios_config = COBERTURA, CAPACIDADES
    r = requests.post(base + "/api/assistente", json={"tipo": "trecho", "id": "S0", "pergunta_id": "o_que_explica", "contextualizar": False})
    assert r.status_code == 200 and "fator de chuva" in r.json()["texto"] and len(r.json()["perguntas"]) == 3
    assert requests.post(base + "/api/assistente", json={"tipo": "trecho", "id": "nao-existe", "pergunta_id": "o_que_explica"}).status_code == 404
    assert requests.post(base + "/api/assistente", json={"tipo": "trecho", "id": "S0"}).status_code == 422
    codigos = [requests.post(base + "/api/assistente", json={}).status_code for _ in range(12)]
    assert codigos[-1] == 429


def test_the_api_answers_503_with_the_last_update_when_the_rain_data_is_down(api):
    from test_servico import sem_chuva
    servico, _ = sem_chuva()
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), srv.criar_handler(servico, "", srv.Limitador()))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{servidor.server_address[1]}"
    try:
        r = requests.get(base + "/api/previsao")
        assert r.status_code == 503 and r.json()["ultima_atualizacao"] == "2026-11-09T09:00:00Z" and "desatualizados" in r.json()["erro"]
        assert requests.get(base + "/api/saude").json()["status"] == "degradado"                       # the map and the segment detail do not depend on it
        assert requests.post(base + "/api/rotas", json=CORPO).json()["alerta"]["nivel"] == "sem_dados"
    finally:
        servidor.shutdown()


def test_the_whole_operator_flow_over_http_ends_with_the_route_avoiding_the_closed_segment_and_survives_a_restart(api, tmp_path):
    import pandas as pd
    from flooding_mapping import ocorrencias as oc
    from test_servico import montar as montar_servico
    arquivo = tmp_path / "ocorrencias.jsonl"
    base, servico, rede = api(token="credencial-do-operador-longa-o-bastante", store=oc.Ocorrencias(arquivo), mm_h=0.0)
    from flooding_mapping.chuva_horaria import ChuvaHoraria
    from flooding_mapping.risco_trecho import agora_local
    servico.relogio = agora_local                                                  # a report is stamped with the real clock: so is the service now
    agora = agora_local().floor("h")
    seca = pd.Series(0.0, index=pd.date_range(agora - pd.Timedelta(days=5), agora + pd.Timedelta(days=3), freq="h"))
    servico.chuva = ChuvaHoraria(0, 0, fonte=lambda a, b: (seca, {"fonte": "teste", "emitido_em_utc": "2026-01-01T00:00:00Z"}))
    CORPO = {"origem": {"lon": O[0], "lat": O[1]}, "destino": {"lon": D[0], "lat": D[1]}, "modal": "carro"}   # departs now
    antes = requests.post(base + "/api/rotas", json=CORPO).json()
    habitual = lambda a: [str(servico.rede.ids[e]) for e in servico._analise(a["analise_id"])[2]["habitual"]["arestas"]]
    assert habitual(antes) == ["S0", "S1"]
    i = rede.indices(["S1"])[0]
    rel = requests.post(base + "/api/relatos", json={"texto": "alagou", "lon": float(rede.no_lon[rede.u[i]]), "lat": float(rede.no_lat[rede.u[i]])}).json()
    assert rel["situacao"] == "reportada" and habitual(requests.post(base + "/api/rotas", json=CORPO).json()) == ["S0", "S1"]       # a report closes nothing
    corpo = {"situacao": "confirmada", "evidencia": "Guarda municipal no local, via fechada ao trânsito", "impacto_circulacao": "interdicao"}
    assert requests.post(base + f"/api/ocorrencias/{rel['id']}", json=corpo).status_code == 403                                      # the public cannot confirm
    assert requests.post(base + f"/api/ocorrencias/{rel['id']}", json=corpo, headers={"Authorization": "Bearer credencial-do-operador-longa-o-bastante"}).status_code == 200
    # the segment is named by the position of the report, which is on a node of S1 and so also touches S0: both are closed here
    depois = requests.post(base + "/api/rotas", json=CORPO).json()
    assert depois["interdicoes_consideradas"] >= 1 and "S1" not in habitual(depois)
    # a restart: a new store over the same file brings the confirmed record, with its history, and the closure keeps working
    reaberto = oc.Ocorrencias(arquivo)
    assert [r["situacao"] for r in reaberto.listar()] == ["confirmada"] and [h["para"] for h in reaberto.obter(rel["id"])["historico"]] == ["reportada", "confirmada"]
    assert [x["id"] for x in reaberto.interdicoes(72, pd.Timestamp(oc.agora()).to_pydatetime())] == [rel["id"]]


def test_the_operator_can_see_how_a_request_reached_the_server_to_find_the_proxy_address(api):
    base, _, _ = api(token="credencial-do-operador-longa-o-bastante")
    publico = requests.get(base + "/api/saude", headers={"X-Forwarded-For": "1.2.3.4"}).json()
    assert "diagnostico_de_origem" not in publico                                    # strangers do not learn it
    errado = requests.get(base + "/api/saude", headers={"Authorization": "Bearer errado"})
    assert errado.status_code == 200 and "diagnostico_de_origem" not in errado.json()
    d = requests.get(base + "/api/saude", headers={"Authorization": "Bearer credencial-do-operador-longa-o-bastante", "X-Forwarded-For": "1.2.3.4"}).json()["diagnostico_de_origem"]
    assert d["conexao_direta"] == "127.0.0.1" and d["encaminhado"] == "1.2.3.4" and d["cliente_considerado"] == "127.0.0.1" and d["proxies_confiaveis"] == 0
