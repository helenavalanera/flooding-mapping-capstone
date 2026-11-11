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
