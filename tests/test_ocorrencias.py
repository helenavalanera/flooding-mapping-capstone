from datetime import timedelta

import pytest

from flooding_mapping import ocorrencias as oc

PONTO = {"lon": -51.22, "lat": -30.03}


def test_a_user_report_is_always_reported_with_low_reliability():
    store = oc.Ocorrencias()
    # the caller cannot promote a report by sending other fields
    r = store.relato({**PONTO, "tipo": "alagamento_via", "situacao": "confirmada", "confiabilidade": "alta",
                      "impacto_circulacao": "interdicao"})
    assert (r["situacao"], r["confiabilidade"], r["fonte"]) == ("reportada", "baixa", "usuario")
    assert r["historico"][0]["para"] == "reportada"


def test_a_report_never_closes_a_segment_only_a_confirmation_does():
    store = oc.Ocorrencias()
    r = store.relato({**PONTO, "impacto_circulacao": "interdicao"})
    assert store.interdicoes(72) == []
    with pytest.raises(ValueError, match="evidência"):
        store.mudar_situacao(r["id"], "confirmada", por="operador", evidencia="ok")
    store.mudar_situacao(r["id"], "confirmada", por="operador", evidencia="Equipe da EPTC no local, via fechada")
    assert [i["id"] for i in store.interdicoes(72)] == [r["id"]]


def test_transitions_are_kept_and_a_discarded_record_is_final():
    store = oc.Ocorrencias()
    r = store.relato(PONTO)
    store.mudar_situacao(r["id"], "descartada", por="operador", evidencia="Foto mostra via seca")
    assert [h["para"] for h in store.obter(r["id"])["historico"]] == ["reportada", "descartada"]
    with pytest.raises(ValueError, match="transição"):
        store.mudar_situacao(r["id"], "confirmada", por="operador", evidencia="tentando reabrir o caso")
    assert store.ativas(72) == [] and store.interdicoes(72) == []


@pytest.mark.parametrize("dados, trecho", [
    ({"lon": 10, "lat": 10}, "fora do Rio Grande do Sul"),
    ({"lon": "x", "lat": 1}, "lon e lat"),
    ({**PONTO, "tipo": "ufo"}, "tipo"),
    ({**PONTO, "descricao": "a" * 281}, "280"),
    ({**PONTO, "inicio": "2026-11-01T10:00", "fim": "2026-11-01T09:00"}, "fim anterior"),
    ({**PONTO, "segmento_ids": ["x"] * 51}, "segmento_ids"),
    ({**PONTO, "data_hora": "ontem"}, "inválida"),
])
def test_invalid_input_is_rejected_with_a_reason(dados, trecho):
    with pytest.raises(ValueError, match=trecho):
        oc.validar(dados)


def test_control_characters_are_removed_from_free_text():
    assert oc.validar({**PONTO, "descricao": "rua\x00 alagada\n<b>"})["descricao"] == "rua  alagada <b>"


def test_naive_times_are_read_as_brasilia_time():
    assert oc.validar({**PONTO, "data_hora": "2026-11-01T12:00"})["data_hora"] == "2026-11-01T15:00:00Z"


def test_records_survive_a_restart_and_expire_by_retention(tmp_path):
    path = tmp_path / "operacional" / "ocorrencias.jsonl"
    store = oc.Ocorrencias(path)
    novo = store.relato(PONTO)
    velho = store.relato({**PONTO, "data_hora": (oc.agora() - timedelta(days=200)).isoformat()})
    store.mudar_situacao(novo["id"], "confirmada", por="operador", evidencia="Confirmado pela guarda municipal")
    reloaded = oc.Ocorrencias(path)
    assert reloaded.obter(novo["id"])["situacao"] == "confirmada"  # latest line wins
    assert reloaded.expirar(90) == 1 and reloaded.obter(velho["id"]) is None
    assert oc.Ocorrencias(path).obter(velho["id"]) is None


def test_a_record_stays_active_for_its_validity_window_only():
    store = oc.Ocorrencias()
    recente = store.relato({**PONTO, "data_hora": (oc.agora() - timedelta(hours=10)).isoformat()})
    antiga = store.relato({**PONTO, "data_hora": (oc.agora() - timedelta(hours=100)).isoformat()})
    ids = {r["id"] for r in store.ativas(72)}
    assert recente["id"] in ids and antiga["id"] not in ids


def test_no_personal_fields_are_stored():
    r = oc.Ocorrencias().relato({**PONTO, "ip": "1.2.3.4", "usuario": "ana", "endereco": "Rua X"})
    assert not {"ip", "usuario", "endereco"} & set(r)


def test_a_write_cut_short_does_not_stop_the_service_from_starting(tmp_path):
    caminho = tmp_path / "o.jsonl"
    store = oc.Ocorrencias(caminho)
    bom = store.relato(PONTO)
    with caminho.open("a") as f:
        f.write('{"id": "x", "situa')                    # power lost in the middle of a line
        f.write("\nlixo que não é json\n")
    de_novo = oc.Ocorrencias(caminho)
    assert de_novo.obter(bom["id"]) is not None and de_novo.linhas_invalidas == 2
    de_novo.relato(PONTO)                                 # and it keeps working after the damaged lines
    assert len(oc.Ocorrencias(caminho).listar()) == 2


def test_retention_rewrites_the_file_aside_and_leaves_no_temporary_file(tmp_path):
    caminho = tmp_path / "o.jsonl"
    store = oc.Ocorrencias(caminho)
    store.relato({**PONTO, "data_hora": (oc.agora() - timedelta(days=200)).isoformat()})
    novo = store.relato(PONTO)
    assert store.expirar(90) == 1 and [p.name for p in tmp_path.iterdir()] == ["o.jsonl"]
    assert [r["id"] for r in oc.Ocorrencias(caminho).listar()] == [novo["id"]]


def test_the_operator_declares_the_impact_when_reviewing_and_only_then_can_a_report_close_a_segment():
    store = oc.Ocorrencias()
    r = store.relato(PONTO)                                                     # a report never says "interdicao" by itself
    assert r["impacto_circulacao"] == "desconhecido"
    store.mudar_situacao(r["id"], "confirmada", por="operador", evidencia="Guarda municipal no local, via fechada")
    assert store.interdicoes(72) == []                                         # confirmed, but nobody said it is a closure
    r2 = store.relato(PONTO)
    c = store.mudar_situacao(r2["id"], "confirmada", por="operador", evidencia="Guarda municipal no local, via fechada", impacto="interdicao", severidade="alta")
    assert [i["id"] for i in store.interdicoes(72)] == [r2["id"]] and c["impacto_circulacao"] == "interdicao" and c["severidade"] == "alta"
    assert c["historico"][-1]["campos"] == {"impacto_circulacao": "interdicao", "severidade": "alta"}      # the decision is on the record
    with pytest.raises(ValueError, match="impacto_circulacao"):
        store.mudar_situacao(store.relato(PONTO)["id"], "confirmada", por="operador", evidencia="Guarda municipal no local, via fechada", impacto="bloqueado")


def _relato(store):
    return store.relato({"lon": -51.2, "lat": -30.0, "tipo": "alagamento_via"})


def test_community_backing_counts_each_anonymous_key_once_and_stores_only_hashes():
    store = oc.Ocorrencias()
    r = _relato(store)
    reg, novo = store.apoiar(r["id"], "chave-do-aparelho-1", "ainda", "sal", 2)
    assert novo and reg["confiabilidade"] == "baixa" and len(reg["apoios"]) == 1
    assert "chave-do-aparelho-1" not in str(reg)
    assert store.apoiar(r["id"], "chave-do-aparelho-1", "ainda", "sal", 2)[1] is False           # the same key does not count twice
    reg, _ = store.apoiar(r["id"], "chave-do-aparelho-2", "ainda", "sal", 2)
    assert reg["confiabilidade"] == "media" and reg["situacao"] == "reportada"                  # backing raises reliability, never the status
    assert oc.Ocorrencias.interdicoes(store, 72) == []                                         # and never closes a street


def test_the_same_key_on_two_records_leaves_two_unlinkable_hashes_and_dried_votes_close_the_validity():
    store = oc.Ocorrencias()
    a, b = _relato(store), _relato(store)
    ha = store.apoiar(a["id"], "mesma-chave-aleatoria", "ainda", "sal")[0]["apoios"][0]
    hb = store.apoiar(b["id"], "mesma-chave-aleatoria", "ainda", "sal")[0]["apoios"][0]
    assert ha != hb
    store.apoiar(a["id"], "outra-chave-aleatoria-1", "secou", "sal", 2)
    reg, _ = store.apoiar(a["id"], "outra-chave-aleatoria-2", "secou", "sal", 2)
    assert reg["fim"] and reg["situacao"] == "reportada"


def test_backing_rejects_bad_input_and_discarded_records_and_labels_need_enough_people():
    store = oc.Ocorrencias()
    r = _relato(store)
    for args in (("curta", "ainda"), ("chave-valida-123", "talvez")):
        try:
            store.apoiar(r["id"], args[0], args[1], "sal")
            raise AssertionError("deveria recusar")
        except ValueError:
            pass
    assert store.rotuladas(2) == []                                                            # an unbacked report is not a label
    store.apoiar(r["id"], "chave-valida-0001", "ainda", "sal")
    store.apoiar(r["id"], "chave-valida-0002", "ainda", "sal")
    assert [x["id"] for x in store.rotuladas(2)] == [r["id"]]
    store.mudar_situacao(r["id"], "descartada", por="op", evidencia="verificado: não há alagamento")
    assert store.rotuladas(2) == []
    try:
        store.apoiar(r["id"], "chave-valida-0003", "ainda", "sal")
        raise AssertionError("deveria recusar")
    except ValueError:
        pass
