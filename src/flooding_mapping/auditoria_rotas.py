"""Audit of the routing engine against the real street network of Porto Alegre.

    python -m flooding_mapping.auditoria_rotas      ->  reports/ml/rotas_auditoria.json

Three questions, none of which says the routes are safe or even well chosen for a real trip:
1. How much of the network can be used at all (the largest strongly connected piece of each mode)?
2. Which OSM attributes are available, and which does the engine use or leave out?
3. Does the engine find the same shortest time as an independent implementation (networkx) on the same arcs?
"""

from __future__ import annotations

import argparse
import collections
import json

import networkx as nx
import numpy as np
import pandas as pd

from .config import load_config, resolve
from .risco_trecho import pesos, tabela_de_chuva
from .rotas import MODOS, Analise, Rede


def conectividade(rede: Rede) -> dict:
    """Length that is allowed for the mode against the length that is actually reachable (largest strongly connected piece)."""
    a, saida = rede.arestas, {}
    for modo in MODOS:
        permitido = a["drive" if modo == "carro" else "walk"].to_numpy(bool)
        usa = rede._modo[modo]["usa"]
        km = rede.comp_m / 1000
        saida[modo] = {"km_permitido": round(float(km[permitido].sum()), 1), "km_alcancavel": round(float(km[usa].sum()), 1),
                       "km_isolado": round(float(km[permitido & ~usa].sum()), 1), "fracao_alcancavel": round(float(km[usa].sum() / km[permitido].sum()), 4),
                       "segmentos_isolados": int((permitido & ~usa).sum())}
    return saida


def grafo_de_referencia(rede: Rede, modo: str) -> nx.DiGraph:
    """The same arcs as the engine, in networkx, keeping the fastest of any parallel arcs."""
    m, g = rede._modo[modo], nx.DiGraph()
    de = np.repeat(np.arange(rede.n_nos), np.diff(m["indptr"]))
    for u, v, t in zip(de.tolist(), m["para"], m["tempo"]):
        if not g.has_edge(u, v) or g[u][v]["t"] > t:
            g.add_edge(u, v, t=t)
    return g


def conferir_com_referencia(rede: Rede, pr: dict, n: int = 100, semente: int = 20261110) -> dict:
    """Shortest travel time of the engine against networkx for random node pairs, per mode."""
    sorteio, saida = np.random.default_rng(semente), {}
    for modo in MODOS:
        ref, nos = grafo_de_referencia(rede, modo), rede._modo[modo]["nos"]
        dif, ruins, medidos = [], 0, 0
        tabela = pd.DataFrame({"fator": 0.0}, index=pd.date_range("2026-01-01", periods=5, freq="h"))
        risco = pesos(rede.pct, rede, [], pr)
        while medidos < n:
            o, d = (int(x) for x in sorteio.choice(nos, 2, replace=False))
            km = np.hypot((rede.no_lon[o] - rede.no_lon[d]) * rede._cos, rede.no_lat[o] - rede.no_lat[d]) * 111.32
            if not 1 <= km <= 15 or not nx.has_path(ref, o, d):
                continue
            esperado = nx.dijkstra_path_length(ref, o, d, weight="t")
            try:
                obtido = Analise(rede, modo, (rede.no_lon[o], rede.no_lat[o]), (rede.no_lon[d], rede.no_lat[d]), pd.Timestamp("2026-01-01 00:30"), tabela, risco,
                                 np.zeros(rede.n, bool), pd.Timestamp("2026-01-01 00:00")).caminho(0.0)["tempo_s"]
            except ValueError:
                continue
            dif.append(obtido - esperado)
            ruins += abs(obtido - esperado) > 1e-6 * max(esperado, 1)
            medidos += 1
        dif = np.array(dif)
        saida[modo] = {"pares": n, "pares_com_diferenca": int(ruins), "maior_diferenca_s": round(float(np.abs(dif).max()), 3), "maior_excesso_s": round(float(max(0.0, dif.max())), 3),
                       "mais_lento_que_a_referencia": int((dif > 1e-6).sum()), "mais_rapido_que_a_referencia": int((dif < -1e-6).sum())}
    return saida


def atributos_osm(pbf) -> dict:
    """What OSM says about the ways, to see what the engine can and cannot know."""
    import osmium
    c, total_pedestre = collections.Counter(), 0
    for o in osmium.FileProcessor(str(pbf), osmium.osm.WAY):
        t = o.tags
        if not t.get("highway"):
            continue
        c["vias"] += 1
        c["rotatorias"] += t.get("junction") in ("roundabout", "circular")
        c["rotatorias_sem_oneway"] += t.get("junction") in ("roundabout", "circular") and t.get("oneway") is None
        c["escadas"] += t.get("highway") == "steps"
        c["estacionamento_ou_garagem"] += t.get("service") in ("parking_aisle", "driveway")
        c["acesso_privado_ou_fechado"] += t.get("access") in ("private", "no")
        c["com_calcada_informada"] += t.get("sidewalk") is not None
        c["com_velocidade_maxima"] += t.get("maxspeed") is not None
    return dict(c)


def main() -> None:
    argparse.ArgumentParser(description="Auditoria do motor de roteamento").parse_args()
    config = load_config()
    rede = Rede(pd.read_parquet(resolve("data/processed/rede_poa.parquet")), config["roteamento"])
    relatorio = {
        "natureza": "auditoria do cálculo; não valida a segurança nem a qualidade real de nenhum deslocamento",
        "conectividade": conectividade(rede), "conferencia_com_networkx": conferir_com_referencia(rede, config["risco_trecho"]),
        "atributos_osm": atributos_osm(resolve("data/interim/poa.osm.pbf")),
        "o_motor_usa": ["geometria e comprimento dos segmentos", "sentido único (incluindo rotatórias sem a marca)", "acesso privado ou fechado (carro e pedestre)",
                        "serviços de estacionamento e garagem fora do carro", "classe da via para a velocidade de fluxo livre", "interdições confirmadas como bloqueio rígido",
                        "risco estimado no horário de passagem como penalidade"],
        "o_motor_nao_usa": ["velocidade máxima da via (limite legal não é velocidade de viagem)", "restrições de conversão (relações do OSM)", "semáforos e congestionamento",
                            "existência e condição de calçada", "inclinação para o tempo a pé", "passagens inferiores e túneis como pontos de alagamento", "ônibus"]}
    destino = resolve("reports/ml/rotas_auditoria.json")
    destino.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: relatorio[k] for k in ("conectividade", "conferencia_com_networkx")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
