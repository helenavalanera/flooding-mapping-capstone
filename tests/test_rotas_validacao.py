"""Validation of the routing engine against controlled scenarios and reference paths.

These tests show that the arithmetic, the mode rules and the closures behave as specified. They do not say the routes are
good or safe for a real trip: that depends on a street network that has no pavements, turn restrictions or traffic.
"""

import networkx as nx
import numpy as np
import pandas as pd
import pytest
from rede_sintetica import LAT0, LON0, PR, PR_ROTA, aresta, chuva, rede, sem_risco, tabela, tres_caminhos

from flooding_mapping import auditoria_rotas as au
from flooding_mapping.rotas import Analise, ForaDaRede, SemRota

SAIDA, AGORA = pd.Timestamp("2026-11-09 11:50"), pd.Timestamp("2026-11-09 08:00")
KMH = lambda v: v / 3.6  # noqa: E731


def an(r, modo="carro", o=None, d=None, tab=None, bloqueada=None):
    n = r.n_nos
    o = o or (r.no_lon[0], r.no_lat[0])
    d = d or (r.no_lon[n - 1], r.no_lat[n - 1])
    return Analise(r, modo, o, d, SAIDA, tabela(mm_h=0) if tab is None else tab, sem_risco(r), np.zeros(r.n, bool) if bloqueada is None else bloqueada, AGORA)


def linha(n=3, metros=1000.0, **kw):
    """A straight street of ``n`` segments, node 0 at the west end."""
    return rede(pd.DataFrame([aresta(f"R{i}", i, i + 1, (0.01 * i, 0.0), (0.01 * (i + 1), 0.0), metros, **kw) for i in range(n)]))


# ------------------------------------------------------------------ duração e distância
@pytest.mark.parametrize("highway, kmh", [("primary", 40), ("residential", 25), ("motorway", 80), ("service", 15), ("tertiary", 30)])
def test_travel_time_is_length_over_the_speed_of_the_road_class(highway, kmh):
    r = linha(3, 1000.0, highway=highway)
    rota = an(r).caminho(0.0)
    assert rota["distancia_km"] == pytest.approx(3.0) and rota["tempo_s"] == pytest.approx(3000 / KMH(kmh))


def test_a_pedestrian_walks_at_the_same_pace_on_every_class_and_slower_than_any_car():
    for highway in ("primary", "residential", "service"):
        r = linha(2, 1000.0, highway=highway)
        assert an(r, "pe").caminho(0.0)["tempo_s"] == pytest.approx(2000 / KMH(PR_ROTA["pe_kmh"]))
        assert an(r, "pe").caminho(0.0)["tempo_s"] > an(r, "carro").caminho(0.0)["tempo_s"]


def test_the_arrival_is_the_departure_plus_the_travel_time():
    rota = an(linha(2, 1000.0, highway="primary")).caminho(0.0)
    assert pd.Timestamp(rota["chegada"]) == SAIDA + pd.Timedelta(seconds=rota["tempo_s"])


# ------------------------------------------------------------------ carro e caminhada
def test_a_car_obeys_one_way_streets_and_a_pedestrian_does_not():
    df = pd.DataFrame([aresta("A", 0, 1, (0.0, 0.0), (0.01, 0.0), oneway="yes"), aresta("B", 1, 2, (0.01, 0.0), (0.02, 0.0)), aresta("C", 2, 0, (0.02, 0.0), (0.0, 0.0), 5000.0)])
    r = rede(df)
    contra = lambda modo: an(r, modo, (r.no_lon[1], r.no_lat[1]), (r.no_lon[0], r.no_lat[0])).caminho(0.0)   # against the one-way
    assert [str(r.ids[e]) for e in contra("pe")["arestas"]] == ["A"]
    assert "A" not in [str(r.ids[e]) for e in contra("carro")["arestas"]]
    assert contra("carro")["distancia_km"] > contra("pe")["distancia_km"]


def test_each_mode_only_uses_what_it_is_allowed_to():
    df = tres_caminhos()
    df.loc[df["segmento_id"].str.startswith("S"), "walk"] = False           # the short way is closed to pedestrians
    df.loc[df["segmento_id"].str.startswith("M"), "drive"] = False          # the medium way is closed to cars
    r = rede(df)
    a_pe, de_carro = an(r, "pe", (LON0, LAT0), (LON0 + 0.03, LAT0)).caminho(0.0), an(r, "carro", (LON0, LAT0), (LON0 + 0.03, LAT0)).caminho(0.0)
    assert not {"S0", "S1"} & {str(r.ids[e]) for e in a_pe["arestas"]} and not {"M0", "M1", "M2"} & {str(r.ids[e]) for e in de_carro["arestas"]}


def test_a_dead_end_spur_does_not_break_or_attract_the_route():
    df = pd.concat([tres_caminhos(), pd.DataFrame([aresta("X", 99, 98, (0.015, 0.004), (0.015, 0.02), 50.0)])], ignore_index=True)   # a stub off the short path
    r = rede(df)
    rota = an(r, "carro", (LON0, LAT0), (LON0 + 0.03, LAT0)).caminho(0.0)
    assert "X" not in [str(r.ids[e]) for e in rota["arestas"]]


# ------------------------------------------------------------------ conectividade e grafo incompleto
def test_a_point_on_an_island_with_no_way_to_the_network_is_refused_not_snapped_across_the_gap():
    df = pd.concat([tres_caminhos(), pd.DataFrame([aresta("I", 90, 91, (0.2, 0.2), (0.21, 0.2))])], ignore_index=True)    # an island 20 km away
    r = rede(df)
    with pytest.raises(ForaDaRede):
        Analise(r, "carro", (LON0 + 0.205, LAT0 + 0.2), (LON0 + 0.03, LAT0), SAIDA, tabela(), sem_risco(r), np.zeros(r.n, bool), AGORA)


def test_an_incomplete_graph_with_a_missing_link_has_no_route_and_says_so():
    df = pd.DataFrame([aresta("W0", 0, 1, (0.0, 0.0), (0.01, 0.0)), aresta("W1", 1, 0, (0.01, 0.0), (0.0, 0.0)),            # west part, both ways
                       aresta("E0", 5, 6, (0.05, 0.0), (0.06, 0.0)), aresta("E1", 6, 5, (0.06, 0.0), (0.05, 0.0))])          # east part, no link between
    r = rede(df)
    # the engine keeps only the largest strongly connected piece, so a point in the smaller piece is outside the usable network or unreachable
    with pytest.raises((ForaDaRede, SemRota, ValueError)):
        an(r, "carro", (LON0, LAT0), (LON0 + 0.055, LAT0)).comparar()


def test_segments_that_cannot_be_returned_from_are_left_out_of_the_usable_network():
    df = pd.DataFrame([aresta("A", 0, 1, (0.0, 0.0), (0.01, 0.0)), aresta("B", 1, 0, (0.01, 0.0), (0.0, 0.0)),
                       aresta("T", 1, 2, (0.01, 0.0), (0.02, 0.0), oneway="yes")])          # a one-way into a dead end: you enter and never leave
    usa = rede(df)._modo["carro"]["usa"]
    assert usa.tolist() == [True, True, False]
    c = au.conectividade(rede(df))
    assert c["carro"]["segmentos_isolados"] == 1 and c["carro"]["km_isolado"] == 1.0 and c["carro"]["fracao_alcancavel"] == pytest.approx(2 / 3, abs=1e-3)


# ------------------------------------------------------------------ alternativas, bloqueios e risco
def test_without_any_other_way_there_is_only_the_habitual_route_and_no_invented_alternative():
    r = linha(3, 1000.0)
    out = an(r, tab=tabela()).comparar()
    assert list(out) == ["habitual"]


def test_a_longer_alternative_is_offered_with_its_extra_time():
    r = rede(tres_caminhos())
    out = an(r, "carro", (LON0, LAT0), (LON0 + 0.03, LAT0), tab=tabela()).comparar()
    assert out["alternativa"]["distancia_km"] > out["habitual"]["distancia_km"] and out["alternativa"]["tempo_s"] > out["habitual"]["tempo_s"]


def test_a_confirmed_closure_blocks_both_modes_and_cannot_be_bought_back_with_a_higher_aversion():
    r = rede(tres_caminhos())
    fechada = np.zeros(r.n, bool)
    fechada[r.indices(["S1"])] = True
    for modo in ("carro", "pe"):
        a = an(r, modo, (LON0, LAT0), (LON0 + 0.03, LAT0), tab=tabela(mm_h=0), bloqueada=fechada)
        for aversao in (0.0, 1.0, 10.0):
            assert "S1" not in [str(r.ids[e]) for e in a.caminho(aversao)["arestas"]]


def test_a_forecast_risk_is_a_cost_never_a_wall_even_when_it_is_the_only_way():
    r = rede(tres_caminhos().iloc[:2])                                       # only the susceptible short path exists
    rota = an(r, "carro", (LON0, LAT0), (LON0 + 0.03, LAT0), tab=tabela()).caminho(10.0)
    assert [str(r.ids[e]) for e in rota["arestas"]] == ["S0", "S1"] and rota["exposicao_km_risco"] > 0


def test_a_segment_without_terrain_index_adds_no_penalty_and_is_reported_not_hidden():
    df = tres_caminhos()
    df.loc[df["segmento_id"].str.startswith("S"), "percentil"] = np.nan
    r = rede(df)
    rota = an(r, "carro", (LON0, LAT0), (LON0 + 0.03, LAT0), tab=tabela()).caminho(10.0)
    assert [str(r.ids[e]) for e in rota["arestas"]] == ["S0", "S1"] and rota["exposicao_km_risco"] == 0 and rota["km_sem_estimativa"] == pytest.approx(2.0)


def test_without_rain_data_the_time_is_computed_and_no_exposure_is_invented():
    r = rede(tres_caminhos())
    sem_chuva = pd.DataFrame({"fator": np.nan, "chuva_hora_mm": np.nan}, index=pd.date_range("2026-11-08", periods=96, freq="h"))
    rota = an(r, "carro", (LON0, LAT0), (LON0 + 0.03, LAT0), tab=sem_chuva).caminho(1.0)
    assert rota["tempo_s"] > 0 and rota["exposicao_km_risco"] == 0 and rota["km_sem_estimativa"] == pytest.approx(rota["distancia_km"]) and rota["escore_maximo"] is None


def test_steps_are_reported_on_a_walk_so_that_walkable_is_not_read_as_accessible():
    df = tres_caminhos()
    df.loc[df["segmento_id"] == "S0", "highway"] = "steps"
    r = rede(df)
    rota = an(r, "pe", (LON0, LAT0), (LON0 + 0.03, LAT0), tab=tabela(mm_h=0)).caminho(0.0)
    assert "S0" in [str(r.ids[e]) for e in rota["arestas"]] and rota["km_escadas"] == pytest.approx(1.0)


def test_the_origin_and_the_destination_in_the_same_place_are_refused():
    r = linha(2)
    with pytest.raises(ValueError, match="mesmo ponto"):
        an(r, "carro", (r.no_lon[0], r.no_lat[0]), (r.no_lon[0], r.no_lat[0]))


# ------------------------------------------------------------------ reprodutibilidade e caminhos de referência
def test_the_same_request_gives_exactly_the_same_routes():
    r = rede(tres_caminhos())
    a = an(r, "carro", (LON0, LAT0), (LON0 + 0.03, LAT0), tab=tabela()).comparar()
    b = an(r, "carro", (LON0, LAT0), (LON0 + 0.03, LAT0), tab=tabela()).comparar()
    assert {k: v["arestas"] for k, v in a.items()} == {k: v["arestas"] for k, v in b.items()}
    assert {k: v["tempo_s"] for k, v in a.items()} == {k: v["tempo_s"] for k, v in b.items()}


@pytest.mark.parametrize("semente", [1, 2, 3])
def test_on_random_street_grids_the_engine_matches_an_independent_shortest_path(semente):
    sorteio = np.random.default_rng(semente)
    lado, linhas, idx = 6, [], lambda i, j: i * 6 + j
    for i in range(lado):
        for j in range(lado):
            for di, dj in ((0, 1), (1, 0)):
                if i + di < lado and j + dj < lado:
                    a, b = idx(i, j), idx(i + di, j + dj)
                    metros = float(sorteio.integers(100, 900))
                    hw = str(sorteio.choice(["primary", "residential", "tertiary", "service"]))
                    sentido = str(sorteio.choice(["no", "no", "yes"]))        # about a third are one-way
                    linhas.append(aresta(f"{a}-{b}", a, b, (0.004 * j, 0.004 * i), (0.004 * (j + dj), 0.004 * (i + di)), metros, 50.0, highway=hw, oneway=sentido))
                    if sentido == "yes" and sorteio.random() < 0.7:           # most one-ways have a return street so that the grid stays connected
                        linhas.append(aresta(f"{b}-{a}", b, a, (0.004 * (j + dj), 0.004 * (i + di)), (0.004 * j, 0.004 * i), metros * 1.3, 50.0, highway="residential"))
    r = rede(pd.DataFrame(linhas))
    ref = au.grafo_de_referencia(r, "carro")
    nos = r._modo["carro"]["nos"]
    feitos = 0
    while feitos < 25:
        o, d = (int(x) for x in sorteio.choice(nos, 2, replace=False))
        if not nx.has_path(ref, o, d):
            continue
        esperado = nx.dijkstra_path_length(ref, o, d, weight="t")
        obtido = Analise(r, "carro", (r.no_lon[o], r.no_lat[o]), (r.no_lon[d], r.no_lat[d]), SAIDA, tabela(mm_h=0), sem_risco(r), np.zeros(r.n, bool), AGORA).caminho(0.0)["tempo_s"]
        assert obtido == pytest.approx(esperado, rel=1e-9), (semente, o, d)
        feitos += 1


def test_the_audit_cross_check_reports_zero_difference_on_a_small_network():
    r = rede(tres_caminhos())
    out = au.conferir_com_referencia(r, PR, n=8)
    assert all(v["pares_com_diferenca"] == 0 and v["maior_diferenca_s"] == 0 for v in out.values())
