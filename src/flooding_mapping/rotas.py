"""Deterministic routing on the street graph, with the estimated risk at the time of passage.

    custo(trecho) = tempo + penalidade
    penalidade    = lambda x aversao x km x escore(t_passagem) x confiabilidade     (segundos)

``t_passagem`` is the estimated time at which the traveller is *on* the segment (departure plus
the travel time so far), not the departure time. ``escore`` comes from ``risco_trecho``.

* A confirmed closure removes the segment: it cannot be used, whatever the cost.
* A forecast risk is only a cost. It never blocks a segment.
* Missing terrain data adds no penalty, and the share of the route without estimate is reported.

Routes offered: the fastest (``habitual``), the one with the lowest estimated exposure and a
second, clearly different one. The words are "menor exposição estimada": no route is called safe.

Limits (MVP): free-flow speeds by road class, no congestion, signals or turn restrictions, and
no buses (no usable timetable). Each route is a best-cost path under a time-dependent penalty,
not an exact optimum of a time-dependent graph.
"""

from __future__ import annotations

import heapq
import math

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from .risco_trecho import classe, fator_em

MODOS = ("carro", "pe")
M_POR_GRAU = 111_320.0


class ForaDaRede(ValueError):
    """Origin or destination too far from any usable street."""


class SemRota(ValueError):
    """No path between two points (for example because of confirmed closures)."""


class Rede:
    """Street graph with per-mode directed arcs, built from one row per OSM segment."""

    COLUNAS = ["segmento_id", "u", "v", "comprimento_m", "highway", "oneway", "drive", "walk",
               "lon0", "lat0", "lon1", "lat1", "percentil", "nome"]

    def __init__(self, arestas: pd.DataFrame, params: dict):
        self.p = params
        a = arestas.reset_index(drop=True)
        a["nome"] = a["nome"].astype(object).where(a["nome"].notna(), None)  # an unnamed street is None, never NaN (not JSON)
        self.n = len(a)
        self.arestas = a
        self.ids = a["segmento_id"].to_numpy()
        self._por_id = {s: i for i, s in enumerate(self.ids)}
        nos, inverso = np.unique(np.concatenate([a["u"].to_numpy(), a["v"].to_numpy()]), return_inverse=True)
        self.u, self.v = inverso[:self.n], inverso[self.n:]
        self.n_nos = len(nos)
        self.no_lon = np.zeros(self.n_nos)
        self.no_lat = np.zeros(self.n_nos)
        self.no_lon[self.u], self.no_lat[self.u] = a["lon0"].to_numpy(), a["lat0"].to_numpy()
        self.no_lon[self.v], self.no_lat[self.v] = a["lon1"].to_numpy(), a["lat1"].to_numpy()
        self.comp_m = a["comprimento_m"].to_numpy(float)
        self.pct = a["percentil"].to_numpy(float)
        self.escada = a["highway"].eq("steps").to_numpy()   # walkable, but a person who cannot take stairs cannot use it
        self._cos = math.cos(math.radians(float(np.mean(self.no_lat))))
        self._p0, self._p1 = self._xy(a["lon0"], a["lat0"]), self._xy(a["lon1"], a["lat1"])
        self._arvore_arestas = cKDTree((self._p0 + self._p1) / 2)
        self._meio_comprimento = float(np.linalg.norm(self._p1 - self._p0, axis=1).max()) / 2
        self._modo = {m: self._arcos(m) for m in MODOS}

    def _xy(self, lon, lat) -> np.ndarray:
        return np.c_[np.asarray(lon, float) * self._cos * M_POR_GRAU, np.asarray(lat, float) * M_POR_GRAU]

    def _arcos(self, modo: str) -> dict:
        """CSR arcs of one mode, restricted to the largest strongly connected piece."""
        a = self.arestas
        if modo == "carro":
            ok = a["drive"].to_numpy(bool)
            velocidade = a["highway"].map(self.p["velocidade_kmh"]).fillna(self.p["velocidade_padrao_kmh"]).to_numpy(float)
            sentido = a["oneway"].fillna("no")
            frente = ok & ~sentido.eq("-1").to_numpy(bool)
            tras = ok & ~sentido.isin(["yes", "true", "1"]).to_numpy(bool)
        else:
            ok = a["walk"].to_numpy(bool)
            velocidade = np.full(self.n, self.p["pe_kmh"])
            frente = tras = ok
        tempo_aresta = self.comp_m / (velocidade / 3.6)
        e = np.arange(self.n)
        de = np.concatenate([self.u[frente], self.v[tras]])
        para = np.concatenate([self.v[frente], self.u[tras]])
        aresta = np.concatenate([e[frente], e[tras]])
        grafo = csr_matrix((np.ones(len(de)), (de, para)), shape=(self.n_nos, self.n_nos))
        _, rotulo = connected_components(grafo, directed=True, connection="strong")
        grande = np.bincount(rotulo[np.unique(np.concatenate([de, para]))]).argmax() if len(de) else -1
        mantem = (rotulo[de] == grande) & (rotulo[para] == grande)
        de, para, aresta = de[mantem], para[mantem], aresta[mantem]
        ordem = np.argsort(de, kind="stable")
        de, para, aresta = de[ordem], para[ordem], aresta[ordem]
        indptr = np.searchsorted(de, np.arange(self.n_nos + 1))
        nos = np.unique(de)
        return {"indptr": indptr.tolist(), "para": para.tolist(), "aresta": aresta.tolist(),
                "tempo": tempo_aresta[aresta].tolist(), "tempo_aresta": tempo_aresta,
                "nos": nos, "arvore": cKDTree(self._xy(self.no_lon[nos], self.no_lat[nos])),
                "usa": np.isin(e, aresta)}

    def indices(self, segmento_ids: list[str]) -> list[int]:
        return [self._por_id[s] for s in segmento_ids if s in self._por_id]

    def proximos(self, lon: float, lat: float, raio_m: float) -> list[int]:
        """Segments within ``raio_m`` of a point, by distance to the segment itself."""
        ponto = self._xy([lon], [lat])[0]
        candidatos = np.array(self._arvore_arestas.query_ball_point(ponto, raio_m + self._meio_comprimento), dtype=int)
        if not len(candidatos):
            return []
        a, b = self._p0[candidatos], self._p1[candidatos]
        ab = b - a
        t = np.clip(((ponto - a) * ab).sum(axis=1) / np.maximum((ab * ab).sum(axis=1), 1e-9), 0, 1)
        distancia = np.linalg.norm(a + ab * t[:, None] - ponto, axis=1)
        return candidatos[distancia <= raio_m].tolist()

    def no_mais_proximo(self, modo: str, lon: float, lat: float) -> int:
        m = self._modo[modo]
        dist, i = m["arvore"].query(self._xy([lon], [lat])[0])
        if dist > self.p["snap_maximo_m"]:
            raise ForaDaRede(f"nenhuma via para {'carro' if modo == 'carro' else 'pedestres'} a menos de {self.p['snap_maximo_m']} m")
        return int(m["nos"][i])


def _fatores_horarios(tabela: pd.DataFrame, saida: pd.Timestamp, horas: int = 12) -> list[float]:
    """Rain factor on an hourly grid from the departure hour; NaN becomes 0 (reported apart)."""
    base = saida.floor("h")
    grade = [fator_em(tabela, base + pd.Timedelta(hours=h)) for h in range(horas + 1)]
    return [0.0 if math.isnan(x) else x for x in grade]


def _dijkstra(rede: Rede, modo: str, origem: int, destino: int, saida_s: float, base_s: float, fatores: list[float],
              peso: list[float], confiab: list[float], bloqueada: np.ndarray, lam: float, reuso: dict,
              caixa: np.ndarray | None) -> tuple[list[int], list[float], list[int]] | None:
    """Best-cost path: segment indices, elapsed seconds at the start of each, and the nodes visited."""
    m = rede._modo[modo]
    indptr, para, aresta, tempo = m["indptr"], m["para"], m["aresta"], m["tempo"]
    comp_km = (rede.comp_m / 1000).tolist()
    bloq = bloqueada.tolist()
    melhor = {origem: 0.0}
    decorrido = {origem: 0.0}
    anterior: dict[int, tuple[int, int]] = {}
    fila = [(0.0, origem)]
    ultimo = len(fatores) - 1
    while fila:
        custo, no = heapq.heappop(fila)
        if custo > melhor[no]:
            continue
        if no == destino:
            break
        el = decorrido[no]
        for k in range(indptr[no], indptr[no + 1]):
            e = aresta[k]
            if bloq[e]:
                continue
            w = para[k]
            if caixa is not None and not caixa[w]:
                continue
            dt = tempo[k]
            pen = 0.0
            if lam:
                h = (saida_s - base_s + el + dt / 2) / 3600
                i = min(int(h), ultimo - 1) if h >= 0 else 0
                f = fatores[i] + (fatores[i + 1] - fatores[i]) * min(max(h - i, 0.0), 1.0)
                pen = lam * comp_km[e] * f * peso[e] * confiab[e]
            c = custo + dt * reuso.get(e, 1.0) + pen
            if c < melhor.get(w, math.inf):
                melhor[w] = c
                decorrido[w] = el + dt
                anterior[w] = (no, k)
                heapq.heappush(fila, (c, w))
    if destino not in anterior and origem != destino:
        return None
    arestas, inicios, nos, no = [], [], [destino], destino
    while no != origem:
        no, k = anterior[no]
        arestas.append(aresta[k])
        inicios.append(decorrido[no])
        nos.append(no)
    return arestas[::-1], inicios[::-1], nos[::-1]


class Analise:
    """Everything needed to compute and compare routes for one origin, destination and departure."""

    def __init__(self, rede: Rede, modo: str, origem: tuple[float, float], destino: tuple[float, float],
                 saida: pd.Timestamp, tabela_chuva: pd.DataFrame, risco: dict, bloqueada: np.ndarray, agora: pd.Timestamp):
        if modo not in MODOS:
            raise ValueError(f"modal: use um de {', '.join(MODOS)}")
        self.rede, self.modo, self.saida, self.tabela, self.risco, self.bloqueada, self.agora = (
            rede, modo, saida, tabela_chuva, risco, bloqueada, agora)
        self.no_o = rede.no_mais_proximo(modo, *origem)
        self.no_d = rede.no_mais_proximo(modo, *destino)
        if self.no_o == self.no_d:
            raise ValueError("origem e destino estão no mesmo ponto da rede")
        self.fatores = _fatores_horarios(tabela_chuva, saida)
        self.base_s = saida.floor("h").value / 1e9
        self.saida_s = saida.value / 1e9
        self.peso = np.nan_to_num(risco["peso"]).tolist()
        self.confiab = np.nan_to_num(risco["confiabilidade"]).tolist()

    def caminho(self, aversao: float = 0.0, reuso: dict | None = None) -> dict | None:
        """Best-cost path over the WHOLE graph. A search area around the straight line was tried and dropped: on a real pair it
        cut the optimal walk (it left the area by 3.2 km) and returned one 12 minutes slower, while a full search takes ~0.1 s."""
        achado = _dijkstra(self.rede, self.modo, self.no_o, self.no_d, self.saida_s, self.base_s, self.fatores, self.peso, self.confiab,
                           self.bloqueada, aversao * self.rede.p["penalidade_s_por_km_risco"], reuso or {}, None)
        return self.descrever(*achado) if achado else None

    def descrever(self, arestas: list[int], inicios: list[float], nos: list[int]) -> dict:
        """Metrics of a path: time, distance and exposure to the estimated risk at passage time."""
        r, p = self.rede, self.risco["parametros"]
        dur = r._modo[self.modo]["tempo_aresta"][arestas]
        ini = np.array(inicios)
        quando = self.saida + pd.to_timedelta(ini + dur / 2, unit="s")
        fator = np.array([fator_em(self.tabela, t) for t in quando])
        peso = self.risco["peso"][arestas]
        escore = fator * peso
        km = r.comp_m[arestas] / 1000
        cls = classe(escore, p)
        sem = np.isnan(escore)
        escore0 = np.nan_to_num(escore)
        trechos, atual = [], None
        for i, e in enumerate(arestas):
            if cls[i] in ("atencao", "alto"):
                if atual is None:
                    atual = {"segmentos": [], "km": 0.0, "inicio": quando[i], "classe": "atencao", "escore": 0.0, "i0": i}
                atual["i1"] = i
                atual["segmentos"].append(str(r.ids[e]))
                atual["km"] += km[i]
                atual["fim"] = quando[i]
                atual["escore"] = max(atual["escore"], float(escore[i]))
                atual["nome"] = atual.get("nome") or r.arestas["nome"].iat[e] or None
                atual["classe"] = "alto" if cls[i] == "alto" or atual["classe"] == "alto" else "atencao"
                atual["peso"] = max(atual.get("peso", 0.0), float(peso[i]))
                atual["fator"] = float(fator[i])
                atual["ocorrencia"] = atual.get("ocorrencia") or self.risco["ocorrencia"][e]
            elif atual:
                trechos.append(atual)
                atual = None
        if atual:
            trechos.append(atual)
        coords = [[float(r.no_lon[n]), float(r.no_lat[n])] for n in nos]
        for t in trechos:   # the stretch's own line: the nodes from the start of its first segment to the end of its last
            t["coordenadas"] = coords[t.pop("i0"): t.pop("i1") + 2]
        pico = int(np.nanargmax(escore)) if not sem.all() else None
        return {
            "arestas": [int(e) for e in arestas], "coordenadas": coords,
            "tempo_s": float(dur.sum()), "distancia_km": float(km.sum()),
            "exposicao_km_risco": float((km * escore0).sum()),
            "km_atencao_ou_alto": float(km[np.isin(cls, ["atencao", "alto"])].sum()),
            "km_alto": float(km[cls == "alto"].sum()),
            "km_sem_estimativa": float(km[sem].sum()), "km_escadas": float(km[r.escada[arestas]].sum()),
            "escore_maximo": None if pico is None else float(escore[pico]),
            "instante_do_pico": None if pico is None else str(quando[pico]),
            "trechos_de_risco": [{**t, "inicio": str(t["inicio"]), "fim": str(t["fim"]), "km": round(t["km"], 3)} for t in trechos],
            "chegada": str(self.saida + pd.Timedelta(seconds=float(dur.sum())))}

    def comparar(self) -> dict:
        """Fastest route, lowest estimated exposure and a clearly different second option."""
        p = self.rede.p
        habitual = self.caminho(0.0)
        if habitual is None:
            raise SemRota("não há caminho entre os pontos com as interdições confirmadas")
        candidatas = [habitual]
        for aversao in p["aversoes_candidatas"]:
            if (c := self.caminho(aversao)):
                candidatas.append(c)
        menor = min(candidatas, key=lambda c: (round(c["exposicao_km_risco"], 4), c["tempo_s"]))
        for base in (habitual, menor):
            if (c := self.caminho(1.0, {e: 3.0 for e in base["arestas"]})):
                candidatas.append(c)
        out = {"habitual": habitual}
        if menor["arestas"] != habitual["arestas"] and menor["exposicao_km_risco"] < habitual["exposicao_km_risco"] - 1e-6:
            out["menor_exposicao"] = menor
        escolhidas = [out["habitual"]] + ([out["menor_exposicao"]] if "menor_exposicao" in out else [])
        limite_tempo = habitual["tempo_s"] * 1.5 + 600
        viaveis = [c for c in candidatas if c["tempo_s"] <= limite_tempo
                   and all(compartilha(c, e) <= p["compartilhamento_maximo"] for e in escolhidas)]
        if viaveis:
            out["alternativa"] = min(viaveis, key=lambda c: (c["exposicao_km_risco"], c["tempo_s"]))
        return out


def compartilha(a: dict, b: dict) -> float:
    """Fraction of route ``a`` (by segment count) that route ``b`` also uses."""
    sb = set(b["arestas"])
    return sum(e in sb for e in a["arestas"]) / max(len(a["arestas"]), 1)


def impacto_fechamento(rede: Rede, modo: str, aresta: int, raio_km: float = 2.0) -> dict:
    """Simulated detour if one segment closed: extra time between its two ends (no risk involved)."""
    m = rede._modo[modo]
    if not m["usa"][aresta]:
        return {"na_rede": False}
    u, v = int(rede.u[aresta]), int(rede.v[aresta])
    bloqueada = np.zeros(rede.n, bool)
    bloqueada[aresta] = True
    dlat, dlon = raio_km / 110.54, raio_km / (111.32 * rede._cos)
    caixa = (abs(rede.no_lon - rede.no_lon[u]) <= dlon) & (abs(rede.no_lat - rede.no_lat[u]) <= dlat)
    achado = _dijkstra(rede, modo, u, v, 0.0, 0.0, [0.0, 0.0], [0.0] * rede.n, [0.0] * rede.n, bloqueada, 0.0, {}, caixa)
    if achado is None:
        return {"na_rede": True, "sem_alternativa_proxima": True, "raio_km": raio_km}
    caminho = achado[0]
    return {"na_rede": True, "sem_alternativa_proxima": False,
            "desvio_s": round(float(m["tempo_aresta"][caminho].sum() - m["tempo_aresta"][aresta]), 1),
            "desvio_km": round(float(rede.comp_m[caminho].sum() - rede.comp_m[aresta]) / 1000, 3)}
