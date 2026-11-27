"""Rankings e média mensal da landing: vêm de agregações dos resultados existentes, com cobertura e validade, e o que não foi publicado diz por quê."""
import json
import re
from pathlib import Path

ST = Path(__file__).resolve().parents[1] / "src/flooding_mapping/app/static"
R = json.loads((ST / "data/rankings_poa.json").read_text(encoding="utf-8"))
RES = json.loads((ST / "data/resultados_poa.json").read_text(encoding="utf-8"))
HTML = (ST / "inicio/index.html").read_text(encoding="utf-8")


def test_the_monthly_mean_is_by_calendar_month_with_its_source_and_period_and_is_not_per_event():
    m = R["media_mensal_de_chuva"]
    assert [x["mes"] for x in m["meses"]][0] == "janeiro" and len(m["meses"]) == 12 and all(x["anos"] >= 9 and x["media_mm"] > 0 for x in m["meses"])
    assert m["periodo_da_serie"] == RES["chuva"]["periodo"] and "ERA5" in m["fonte"] and "Não é chuva por evento" in m["o_que_e"]
    assert abs(m["media_dos_meses_mm"] - RES["chuva"]["media_mensal_mm"]) < 2          # o mesmo nível da média mensal dos resultados (esta só descarta o mês incompleto)
    assert "Média mensal não é chuva por evento" in HTML and "grafico-chuva-mensal.svg" in HTML


def test_the_top5_districts_are_the_five_highest_among_districts_with_enough_stretches_and_sorted():
    itens = R["top5_bairros"]["itens"]
    validos = {b["nome"]: b for b in RES["bairros"] if b["suficiente"]}
    assert len(itens) == 5 and all(i["bairro"] in validos for i in itens)
    valores = [i["parcela_com_propensao_topografica"] for i in itens]
    assert valores == sorted(valores, reverse=True)
    resto = max(b["parcela_com_preenchimento"] for n, b in validos.items() if n not in {i["bairro"] for i in itens})
    assert min(valores) >= round(resto, 3)
    for i in itens:
        assert i["bairro"] in HTML and i["trechos_com_dados"] == validos[i["bairro"]]["trechos_com_dados"]


def test_unpublished_rankings_state_why_and_the_page_does_not_claim_them():
    assert set(R["nao_publicados"]) == {"top10_trechos", "ranking_de_zonas"}
    assert "Profill" in R["nao_publicados"]["top10_trechos"] and "zonas" in R["nao_publicados"]["ranking_de_zonas"]
    assert "Ranking de ruas e trechos: não publicado" in HTML and "Ranking de zonas de Porto Alegre: não publicado" in HTML
    assert not re.search(r"<th scope='row'>(?:6|7|8|9|10)\. ", HTML)                    # nenhuma tabela de 10 itens
