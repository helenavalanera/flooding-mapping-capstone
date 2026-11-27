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
    # só a página do painel pode ser enquadrada, e só pela mesma origem (página "No celular"); todo o resto continua com 'none'
    assert "frame-ancestors 'self'" in r.headers["Content-Security-Policy"] and r.headers["X-Content-Type-Options"] == "nosniff"
    for caminho in ("/inicio/", "/resultados.js"):
        o = requests.get(base + caminho)
        assert o.status_code == 200 and "frame-ancestors 'none'" in o.headers["Content-Security-Policy"], caminho
    # só a origem vai a outros domínios: o OpenStreetMap exige um Referer nos tiles, e o caminho da página nunca vaza
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
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


@pytest.fixture
def com_pwa_arquivado(monkeypatch):
    """O PWA arquivado (app/arquivo/) só é servido por opt-in (FM_ARQUIVO_PWA=1); os testes do app de rotas o ligam assim."""
    monkeypatch.setattr(srv, "RAIZES", tuple(r for r in srv.RAIZES if r != srv.ARQUIVO) + (srv.ARQUIVO,))


def test_the_archived_pwa_and_the_install_files_are_not_served_by_default(api):
    base, _, _ = api()
    for caminho in ("/pwa/", "/pwa/pwa.js", "/sw.js", "/sw-mapa.js", "/manifest.webmanifest", "/instalar.js", "/inicio/aplicativo.html"):
        assert requests.get(base + caminho).status_code == 404, caminho


def test_only_the_service_worker_may_connect_to_the_map_library_cdn(api, com_pwa_arquivado):
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


def test_a_directory_without_the_trailing_slash_redirects_so_relative_paths_keep_working(api, com_pwa_arquivado):
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


# ---- download verificado da tabela de ruas (hospedagem construída a partir do Git, sem data/)
class _RespostaFalsa:
    def __init__(self, conteudo: bytes):
        self.conteudo = conteudo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        for i in range(0, len(self.conteudo), n):
            yield self.conteudo[i:i + n]


def _com_resposta(monkeypatch, conteudo: bytes):
    import requests

    monkeypatch.setattr(requests, "get", lambda *a, **k: _RespostaFalsa(conteudo))


def test_the_street_table_is_downloaded_only_with_a_matching_hash(tmp_path, monkeypatch):
    import hashlib

    dados = b"tabela-de-ruas" * 1000
    _com_resposta(monkeypatch, dados)
    alvo = tmp_path / "dados" / "rede.parquet"
    srv.baixar_rede("https://exemplo.test/rede.parquet", hashlib.sha256(dados).hexdigest(), alvo)
    assert alvo.read_bytes() == dados and not list(alvo.parent.glob("*.parte"))


def test_a_download_with_the_wrong_hash_is_discarded(tmp_path, monkeypatch):
    _com_resposta(monkeypatch, b"outro conteudo")
    alvo = tmp_path / "rede.parquet"
    with pytest.raises(SystemExit, match="não confere"):
        srv.baixar_rede("https://exemplo.test/rede.parquet", "0" * 64, alvo)
    assert not alvo.exists() and not list(tmp_path.glob("*.parte"))


@pytest.mark.parametrize("url, sha, trecho", [
    ("https://exemplo.test/x", "", "SHA-256"), ("https://exemplo.test/x", "abc", "SHA-256"),
    ("http://exemplo.test/x", "0" * 64, "https"), ("ftp://exemplo.test/x", "0" * 64, "https")])
def test_the_download_refuses_a_missing_hash_and_a_non_https_address(tmp_path, monkeypatch, url, sha, trecho):
    _com_resposta(monkeypatch, b"x")
    with pytest.raises(SystemExit, match=trecho):
        srv.baixar_rede(url, sha, tmp_path / "rede.parquet")
    assert not (tmp_path / "rede.parquet").exists()


def test_plain_http_is_accepted_only_for_loopback(tmp_path, monkeypatch):
    import hashlib

    _com_resposta(monkeypatch, b"ok")
    srv.baixar_rede("http://127.0.0.1:9/x", hashlib.sha256(b"ok").hexdigest(), tmp_path / "r.parquet")
    assert (tmp_path / "r.parquet").read_bytes() == b"ok"


def test_the_download_has_a_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "MAX_REDE_BYTES", 10)
    _com_resposta(monkeypatch, b"x" * 100)
    with pytest.raises(SystemExit, match="limite"):
        srv.baixar_rede("https://exemplo.test/x", "0" * 64, tmp_path / "r.parquet")
    assert not (tmp_path / "r.parquet").exists()


# ---- celular: o painel abre normalmente (o redirecionamento ao app do cidadão foi arquivado com o PWA)
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
DESKTOP = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


@pytest.mark.parametrize("ua", [IPHONE, ANDROID])
def test_a_phone_is_no_longer_redirected_to_the_archived_citizen_app(api, ua):
    base, _, _ = api()
    r = requests.get(base + "/", headers={"User-Agent": ua}, allow_redirects=False)
    assert r.status_code == 200 and "Location" not in r.headers and "Vary" not in r.headers
    assert requests.get(base + "/index.html", headers={"User-Agent": ua}, allow_redirects=False).status_code == 200


def test_the_panel_stays_for_desktops_and_can_be_forced_on_a_phone(api):
    base, _, _ = api()
    assert requests.get(base + "/", headers={"User-Agent": DESKTOP}, allow_redirects=False).status_code == 200
    assert requests.get(base + "/?painel=1", headers={"User-Agent": IPHONE}, allow_redirects=False).status_code == 200


def test_the_api_opens_normally_on_a_phone_and_the_archived_app_does_only_with_the_opt_in(api, com_pwa_arquivado):
    base, _, _ = api()
    assert requests.get(base + "/pwa/", headers={"User-Agent": IPHONE}, allow_redirects=False).status_code == 200
    assert requests.get(base + "/api/saude", headers={"User-Agent": IPHONE}, allow_redirects=False).status_code == 200


# ---- modo de demonstração: um segundo serviço, isolado, escolhido por cookie
TOKEN_REAL = "token-do-servico-real-com-mais-de-24-caracteres"
TOKEN_DEMO = "demo-operador-com-mais-de-24-caracteres"


@pytest.fixture
def dois():
    """A real service and an isolated demonstration one behind the same server."""
    real, _ = montar(token=TOKEN_REAL)
    demo, _ = montar(token=TOKEN_DEMO)
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), srv.criar_handler(real, "", srv.Limitador(), servico_demo=demo))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()


DEMO = {"Cookie": "fm_modo=demo"}


def test_the_switch_cookie_picks_the_service_and_health_says_which(dois):
    real = requests.get(dois + "/api/saude").json()
    demo = requests.get(dois + "/api/saude", headers=DEMO).json()
    assert real["modo"] == "real" and demo["modo"] == "demonstracao" and real["demonstracao_disponivel"] is True
    assert requests.get(dois + "/api/saude", headers={"Cookie": "fm_modo=real"}).json()["modo"] == "real"
    assert requests.get(dois + "/api/saude", headers={"Cookie": "outro=1; fm_modo=demo"}).json()["modo"] == "demonstracao"


def test_demonstration_records_never_reach_the_real_service_and_the_other_way_round(dois):
    rid = requests.post(dois + "/api/relatos", json={"texto": "alagada (demonstração)", "lon": O[0], "lat": O[1]}, headers=DEMO).json()["id"]
    assert rid in [o["id"] for o in requests.get(dois + "/api/ocorrencias", headers=DEMO).json()["ocorrencias"]]
    assert requests.get(dois + "/api/ocorrencias").json()["total"] == 0
    requests.post(dois + "/api/relatos", json={"texto": "alagada (real)", "lon": D[0], "lat": D[1]})
    assert requests.get(dois + "/api/ocorrencias", headers=DEMO).json()["total"] == 1


def test_the_public_demonstration_credential_does_not_open_the_real_service(dois):
    rid = requests.post(dois + "/api/relatos", json={"texto": "alagada na rua", "lon": O[0], "lat": O[1]}).json()["id"]
    corpo = {"situacao": "confirmada", "confiabilidade": "alta", "impacto_circulacao": "interdicao", "evidencia": "confirmado em teste isolado"}
    assert requests.post(dois + "/api/ocorrencias/" + rid, json=corpo, headers={"Authorization": "Bearer " + TOKEN_DEMO}).status_code == 403
    assert requests.post(dois + "/api/ocorrencias/" + rid, json=corpo, headers={"Authorization": "Bearer " + TOKEN_REAL}).status_code == 200


def test_without_a_demonstration_service_the_cookie_changes_nothing(api):
    base, _, _ = api()
    saude = requests.get(base + "/api/saude", headers=DEMO).json()
    assert saude["modo"] == "real" and saude["demonstracao_disponivel"] is False


# ------------------------------------------------------------------ mapa-base (Protomaps, PMTiles lido por Range)
@pytest.fixture
def mapa(tmp_path, monkeypatch):
    arquivo = tmp_path / "rs.pmtiles"
    arquivo.write_bytes(bytes(range(256)) * 40)   # 10 240 bytes
    monkeypatch.setattr(srv, "MAPA_ARQUIVO", arquivo)
    return arquivo


def test_the_basemap_answers_byte_ranges_so_a_phone_never_downloads_the_whole_file(api, mapa):
    base, _, _ = api()
    todo = mapa.read_bytes()
    r = requests.get(base + "/mapa/rs.pmtiles", headers={"Range": "bytes=10-19"})
    assert r.status_code == 206 and r.content == todo[10:20]
    assert r.headers["Content-Range"] == f"bytes 10-19/{len(todo)}" and r.headers["Accept-Ranges"] == "bytes"
    assert requests.get(base + "/mapa/rs.pmtiles", headers={"Range": "bytes=-5"}).content == todo[-5:]       # suffix
    assert requests.get(base + "/mapa/rs.pmtiles", headers={"Range": f"bytes={len(todo) - 3}-"}).content == todo[-3:]   # open-ended
    inteiro = requests.get(base + "/mapa/rs.pmtiles")
    assert inteiro.status_code == 200 and inteiro.content == todo and "ETag" in inteiro.headers
    assert requests.get(base + "/mapa/rs.pmtiles?v=20261115", headers={"Range": "bytes=0-3"}).content == todo[:4]   # the version in the URL is only a cache key


def test_the_basemap_refuses_ranges_it_cannot_serve(api, mapa):
    base, _, _ = api()
    for pedido in ("bytes=99999-", "bytes=20-10", "bytes=-", "bytes=a-b", "items=0-9"):
        r = requests.get(base + "/mapa/rs.pmtiles", headers={"Range": pedido})
        assert r.status_code == 416, pedido
    assert requests.get(base + "/mapa/rs.pmtiles", headers={"Range": "bytes=99999-"}).headers["Content-Range"] == f"bytes */{mapa.stat().st_size}"


def test_one_basemap_answer_is_capped_however_open_the_range_is(api, mapa, monkeypatch):
    monkeypatch.setattr(srv, "MAPA_RESPOSTA_MAX", 100)
    base, _, _ = api()
    r = requests.get(base + "/mapa/rs.pmtiles", headers={"Range": "bytes=0-"})
    assert r.status_code == 206 and len(r.content) == 100 and r.headers["Content-Range"].startswith("bytes 0-99/")


def test_a_missing_basemap_is_a_404_not_a_crash(api, tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "MAPA_ARQUIVO", tmp_path / "nao_existe.pmtiles")
    base, _, _ = api()
    assert requests.get(base + "/mapa/rs.pmtiles").status_code == 404


def test_the_content_policy_no_longer_lets_pages_reach_third_party_tile_servers(api):
    base, _, _ = api()
    csp = requests.get(base + "/").headers["Content-Security-Policy"]
    assert "openstreetmap.org" not in csp and "carto" not in csp.lower()
    assert "connect-src 'self'" in csp


def test_the_basemap_download_is_verified_and_named_in_its_errors(tmp_path, monkeypatch):
    import hashlib
    _com_resposta(monkeypatch, b"mapa")
    alvo = tmp_path / "rs.pmtiles"
    srv.baixar_rede("https://exemplo.test/rs.pmtiles", hashlib.sha256(b"mapa").hexdigest(), alvo, "FM_MAPA", "o mapa-base", srv.MAX_MAPA_BYTES)
    assert alvo.read_bytes() == b"mapa"
    with pytest.raises(SystemExit, match="FM_MAPA_SHA256"):
        srv.baixar_rede("https://exemplo.test/rs.pmtiles", "0" * 64, tmp_path / "outro.pmtiles", "FM_MAPA", "o mapa-base", srv.MAX_MAPA_BYTES)


def test_encoded_paths_reach_the_label_fonts_but_never_leave_the_static_folder(api):
    base, _, _ = api()
    r = requests.get(base + "/vendor/mapa/fontes/Noto%20Sans%20Regular/0-255.pbf")   # how the map library spells the font stack
    assert r.status_code == 200 and len(r.content) > 1000
    host, port = base.removeprefix("http://").split(":")
    for caminho in ("/vendor/mapa/fontes/%2e%2e/%2e%2e/%2e%2e/servidor.py", "/vendor/%00/x", "/vendor/mapa/..%2f..%2f..%2fservidor.py", "/%252e%252e/%252e%252e/.env"):
        c = http.client.HTTPConnection(host, int(port))
        c.request("GET", caminho)
        resposta = c.getresponse()
        assert resposta.status == 404, caminho
        assert b"OPERADOR_TOKEN" not in resposta.read()


def test_the_citizen_routes_answer_strict_json_and_the_backing_flow_works_over_http(api):
    base, servico, _ = api()
    for caminho in ("/api/bolsoes?h=1", "/api/pois", "/api/areas-sugeridas", "/api/aprendizado", "/api/bairros?h=1", "/api/territorio"):
        r = requests.get(base + caminho)
        assert r.status_code == 200, caminho
        json.loads(r.text, parse_constant=lambda c: pytest.fail(f"{c} em {caminho}"))
    rel = requests.post(base + "/api/relatos", json={"lon": O[0], "lat": O[1], "tipo": "alagamento_via"}).json()
    ok = requests.post(base + f"/api/ocorrencias/{rel['id']}/apoio", json={"chave": "aparelho-aleatorio-123", "tipo": "ainda"})
    assert ok.status_code == 200 and ok.json()["contado"] and ok.json()["situacao"] == "reportada"
    assert requests.post(base + f"/api/ocorrencias/{rel['id']}/apoio", json={"chave": "x", "tipo": "ainda"}).status_code == 422
    assert requests.post(base + "/api/ocorrencias/inexistente/apoio", json={"chave": "aparelho-aleatorio-123", "tipo": "ainda"}).status_code == 404
    av = requests.post(base + "/api/avisos", json={"lugares": [{"nome": "Casa", "lon": O[0], "lat": O[1]}], "horas": 3})
    assert av.status_code == 200 and av.json()["lugares"][0]["nome"] == "Casa"
    assert requests.post(base + "/api/avisos", json={"lugares": []}).status_code == 422


def test_backing_does_not_need_the_operator_token_and_cannot_confirm(api):
    base, servico, _ = api(token="x" * 30)
    rel = requests.post(base + "/api/relatos", json={"lon": O[0], "lat": O[1]}).json()
    r = requests.post(base + f"/api/ocorrencias/{rel['id']}/apoio", json={"chave": "aparelho-aleatorio-9", "tipo": "ainda"})
    assert r.status_code == 200 and r.json()["situacao"] == "reportada"
    assert requests.post(base + f"/api/ocorrencias/{rel['id']}", json={"situacao": "confirmada", "evidencia": "tentativa sem token"}).status_code == 403
