import numpy as np
import pandas as pd
import pytest
from rede_sintetica import D, O, PR, PR_ROTA, aresta, chuva, rede, sem_risco, tabela, tabela_de_chuva, tres_caminhos

from flooding_mapping import rotas
from flooding_mapping.risco_trecho import fator_em
from flooding_mapping.rotas import Analise, ForaDaRede, SemRota

SAIDA = pd.Timestamp("2026-11-09 11:50")
AGORA = pd.Timestamp("2026-11-09 08:00")


def analise(r, modo="carro", saida=SAIDA, tab=None, bloqueada=None, risco=None):
    return Analise(r, modo, O, D, saida, tabela() if tab is None else tab, risco or sem_risco(r),
                   np.zeros(r.n, bool) if bloqueada is None else bloqueada, AGORA)


def ids(r, rota):
    return [str(r.ids[e]) for e in rota["arestas"]]


def test_without_rain_the_fastest_route_is_the_habitual_one_and_nothing_is_penalised():
    r = rede(tres_caminhos())
    out = analise(r, tab=tabela(mm_h=0)).comparar()
    assert ids(r, out["habitual"]) == ["S0", "S1"]
    assert out["habitual"]["exposicao_km_risco"] == 0 and "menor_exposicao" not in out


def test_in_a_storm_the_lowest_exposure_route_avoids_the_susceptible_streets_at_a_time_cost():
    r = rede(tres_caminhos())
    out = analise(r).comparar()
    hab, menor = out["habitual"], out["menor_exposicao"]
    assert ids(r, hab) == ["S0", "S1"]                   # fastest, but on the most susceptible streets
    assert menor["exposicao_km_risco"] < hab["exposicao_km_risco"] and menor["tempo_s"] > hab["tempo_s"]
    assert hab["trechos_de_risco"] and hab["trechos_de_risco"][0]["classe"] == "alto"


def test_exposure_uses_the_passage_time_not_the_departure_time():
    # four 2 km segments on foot (25 min each); the storm starts 70 min after departure
    df = pd.DataFrame([aresta(f"P{k}", k, k + 1, (0.0, 0.0), (0.0, 0.0), 2000.0, 95.0) for k in range(4)])
    for k in range(4):
        df.loc[k, ["lon0", "lon1"]] = [-51.22 + 0.02 * k, -51.22 + 0.02 * (k + 1)]
    r = rede(df)
    tab = tabela_de_chuva(chuva("2026-11-09 11:00", 15.0, 3), PR)
    saida = pd.Timestamp("2026-11-09 09:50")  # the departure factor is zero
    a = Analise(r, "pe", (-51.22, -30.03), (-51.22 + 0.08, -30.03), saida, tab, sem_risco(r), np.zeros(r.n, bool), AGORA)
    rota = a.caminho(0.0)
    assert fator_em(tab, saida) == 0.0
    assert rota["exposicao_km_risco"] > 0                      # only the later segments meet the storm
    cedo = Analise(r, "pe", (-51.22, -30.03), (-51.22 + 0.08, -30.03), pd.Timestamp("2026-11-08 09:50"), tab, sem_risco(r),
                   np.zeros(r.n, bool), AGORA).caminho(0.0)
    assert cedo["exposicao_km_risco"] == 0


def test_a_confirmed_closure_removes_the_segment_but_a_forecast_risk_never_does():
    r = rede(tres_caminhos())
    fechada = np.zeros(r.n, bool)
    fechada[r.indices(["S1"])] = True
    out = analise(r, bloqueada=fechada, tab=tabela(mm_h=0)).comparar()
    assert "S1" not in sum((ids(r, x) for x in out.values()), [])
    assert ids(r, out["habitual"]) == ["M0", "M1", "M2"]
    # one road only, in a storm, at maximum aversion: the route is still found (risk is a cost, not a block)
    unico = rede(tres_caminhos().iloc[:2])
    rota = analise(unico).caminho(10.0)
    assert ids(unico, rota) == ["S0", "S1"] and rota["exposicao_km_risco"] > 0


def test_with_every_path_closed_there_is_no_route_and_it_says_so():
    r = rede(tres_caminhos())
    fechada = np.zeros(r.n, bool)
    fechada[r.indices(["S0", "M0", "L0"])] = True
    with pytest.raises(SemRota):
        analise(r, bloqueada=fechada).comparar()


def test_the_second_alternative_is_clearly_different_and_not_absurdly_longer():
    r = rede(tres_caminhos())
    out = analise(r).comparar()
    escolhidas = [out[k] for k in ("habitual", "menor_exposicao") if k in out]
    alt = out["alternativa"]
    assert all(rotas.compartilha(alt, e) <= PR_ROTA["compartilhamento_maximo"] for e in escolhidas)
    assert alt["tempo_s"] <= out["habitual"]["tempo_s"] * 1.5 + 600
    assert not any(alt["arestas"] == e["arestas"] for e in escolhidas)


def test_missing_terrain_data_adds_no_penalty_and_is_reported():
    df = tres_caminhos()
    df.loc[df["segmento_id"].str.startswith("S"), "percentil"] = np.nan
    r = rede(df)
    hab = analise(r).comparar()["habitual"]
    assert ids(r, hab) == ["S0", "S1"] and hab["exposicao_km_risco"] == 0
    assert hab["km_sem_estimativa"] == pytest.approx(2.0)


def test_one_way_streets_bind_cars_but_not_pedestrians():
    df = pd.DataFrame([aresta("A", 0, 1, (0.0, 0.0), (0.01, 0.0), oneway="yes"), aresta("B", 1, 2, (0.01, 0.0), (0.02, 0.0)),
                       aresta("C", 2, 0, (0.02, 0.0), (0.0, 0.0))])  # a loop; A only runs 0 -> 1
    r = rede(df)
    volta = lambda modo: Analise(r, modo, (-51.21, -30.03), (-51.22, -30.03), SAIDA, tabela(mm_h=0), sem_risco(r),  # noqa: E731
                                 np.zeros(r.n, bool), AGORA).caminho(0.0)
    assert ids(r, volta("pe")) == ["A"]
    assert "A" not in ids(r, volta("carro"))  # against the one way: the long way round


def test_points_far_from_any_street_are_refused():
    r = rede(tres_caminhos())
    with pytest.raises(ForaDaRede):
        Analise(r, "carro", (-50.0, -29.0), D, SAIDA, tabela(), sem_risco(r), np.zeros(r.n, bool), AGORA)


def test_pedestrians_cannot_use_car_only_streets():
    df = tres_caminhos()
    df.loc[df["segmento_id"].str.startswith("S"), "walk"] = False
    r = rede(df)
    assert "S0" not in ids(r, analise(r, "pe", tab=tabela(mm_h=0)).caminho(0.0))
    assert "S0" in ids(r, analise(r, "carro", tab=tabela(mm_h=0)).caminho(0.0))


def test_simulated_closure_impact_gives_the_detour_or_says_there_is_none():
    r = rede(tres_caminhos())
    desvio = rotas.impacto_fechamento(r, "carro", r.indices(["S0"])[0], raio_km=5.0)
    assert desvio["sem_alternativa_proxima"] is False and desvio["desvio_s"] > 0
    unico = rede(tres_caminhos().iloc[:2])
    assert rotas.impacto_fechamento(unico, "carro", 0)["sem_alternativa_proxima"] is True


def test_each_risk_stretch_carries_its_own_line_so_it_can_be_highlighted_on_the_route():
    r = rede(tres_caminhos())
    rota = analise(r).comparar()["habitual"]
    assert rota["trechos_de_risco"]
    t = rota["trechos_de_risco"][0]
    assert len(t["coordenadas"]) == len(t["segmentos"]) + 1                         # n consecutive segments = n + 1 nodes
    assert all(c in rota["coordenadas"] for c in t["coordenadas"]) and "i0" not in t and "i1" not in t
    assert t["coordenadas"][0] == rota["coordenadas"][0]                            # the whole short path is the stretch here


def test_the_best_route_is_found_even_when_it_goes_far_from_the_straight_line():
    # A: short detour next to the line but slow (residential); B: a fast road that bows out 4.4 km from the line. A search area
    # around the line would have kept A; the optimum is B.
    df = pd.DataFrame([
        aresta("A0", 0, 1, (0.0, 0.0), (0.01, 0.001), 8000.0, 50.0, highway="residential"), aresta("A1", 1, 2, (0.01, 0.001), (0.02, 0.0), 8000.0, 50.0, highway="residential"),
        aresta("B0", 0, 3, (0.0, 0.0), (0.01, 0.04), 4400.0, 50.0, highway="motorway"), aresta("B1", 3, 2, (0.01, 0.04), (0.02, 0.0), 4400.0, 50.0, highway="motorway")])
    r = rede(df)
    rota = Analise(r, "carro", (-51.22, -30.03), (-51.20, -30.03), SAIDA, tabela(mm_h=0), sem_risco(r), np.zeros(r.n, bool), AGORA).caminho(0.0)
    assert ids(r, rota) == ["B0", "B1"] and rota["tempo_s"] == pytest.approx(2 * 4400 / (80 / 3.6))
