"""Modo de demonstração: um segundo serviço, isolado, com chuva e ocorrências SINTÉTICAS sobre a rede de ruas real. Origem e destino são livres (inclusive a
localização da pessoa): o que muda é só a chuva, forte e em andamento, para mostrar a rota que o sistema indicaria sob ela.

Serve para mostrar o produto inteiro quando a chuva real está seca (e por isso não há risco a mostrar). Tudo é declarado: a fonte da série diz
"SÉRIE SINTÉTICA DE DEMONSTRAÇÃO", as ocorrências iniciais dizem que são de demonstração, e as telas mostram um aviso. Nada daqui é evidência
meteorológica nem de eventos reais.

Isolamento: o serviço de demonstração tem **o seu próprio** arquivo de ocorrências (só em memória, nunca em disco) e a sua própria credencial de
operador, que é pública. Uma credencial pública só vale sobre dados de demonstração; ela **não** abre o serviço real. O estado de demonstração
é compartilhado por quem o usa e some quando o servidor reinicia.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import ocorrencias as oc
from .chuva_horaria import ChuvaHoraria
from .servico import Servico

TOKEN_DEMO = "demo-operador-com-mais-de-24-caracteres"
FONTE_SINTETICA = "SÉRIE SINTÉTICA DE DEMONSTRAÇÃO (não é previsão)"


def serie_sintetica() -> tuple[pd.Series, dict]:
    """A made-up storm that is happening NOW, over the whole city, so that anyone who leaves now crosses it: heavy rain (14 mm/h) from 3 hours ago
    to 6 hours ahead, then 4 mm/h for 3 more hours. It is relative to the clock (it never drifts into the past) and the "past" part plays the
    role of the model's analysis. It answers "if it were pouring where I am, which route would the system suggest?"; it is not a forecast."""
    agora = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).floor("h")
    indice = pd.date_range(agora - pd.Timedelta(days=5), agora + pd.Timedelta(days=3, hours=-1), freq="h")
    serie = pd.Series(0.0, index=indice)
    serie[agora - pd.Timedelta(hours=3): agora + pd.Timedelta(hours=6)] = 14.0
    serie[agora + pd.Timedelta(hours=7): agora + pd.Timedelta(hours=9)] = 4.0
    meta = {"fonte": FONTE_SINTETICA, "emitido_em_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "primeira_hora": str(indice[0]), "ultima_hora": str(indice[-1]), "resolucao_espacial": "demonstração"}
    return serie, meta


def semear(servico: Servico) -> None:
    """One pending report and one confirmed closure, both declared as demonstration."""
    r = servico.rede
    candidatas = [i for i in r.proximos(-51.2300, -30.0300, 600) if r.arestas["drive"].iat[i] and r.arestas["nome"].iat[i]]
    for i, situacao in ((candidatas[0], "reportada"), (candidatas[len(candidatas) // 2], "confirmada")):
        rec = servico.store.relato({"lon": float(r.no_lon[r.u[i]]), "lat": float(r.no_lat[r.u[i]]), "tipo": "alagamento_via", "severidade": "alta",
                                    "impacto_circulacao": "interdicao", "segmento_ids": [str(r.ids[i])], "descricao": "demonstração"})
        if situacao == "confirmada":
            servico.store.mudar_situacao(rec["id"], "confirmada", por="demo", evidencia="Ocorrência de demonstração, não é real")


def semear_comunidade(servico: Servico, n: int = 12) -> None:
    """Synthetic community activity, to show the loop: reports spread over terrain-prone streets, most backed by people ("ainda alagado"), one dried.

    Invented, like every record of the demonstration. Positions are drawn (fixed seed) among the 8% most terrain-susceptible named streets that
    cars use, one per spatial block, so the demonstration also shows what the model does with labels that are *not* real."""
    r = servico.rede
    pct = np.nan_to_num(r.pct, nan=0.0)
    cand = np.flatnonzero((pct >= 92) & r.arestas["drive"].to_numpy(bool) & r.arestas["nome"].notna().to_numpy())
    if not len(cand):
        return
    rng = np.random.default_rng(7)
    meio = (r._p0[cand] + r._p1[cand]) / 2
    bloco = (np.floor(meio[:, 0] / 2000) * 100003 + np.floor(meio[:, 1] / 2000)).astype(np.int64)
    escolhidas = [cand[np.flatnonzero(bloco == b)[rng.integers(0, (bloco == b).sum())]] for b in rng.permutation(np.unique(bloco))[:n]]
    for k, i in enumerate(escolhidas):
        rec = servico.store.relato({"lon": float(r.no_lon[r.u[i]]), "lat": float(r.no_lat[r.u[i]]), "tipo": "alagamento_via", "severidade": "media",
                                    "impacto_circulacao": "parcial", "descricao": "demonstração"})   # sem segmento: como um relato real, vale o raio
        for j in range(3 if k < n - 3 else 1):
            servico.store.apoiar(rec["id"], f"demo-{k:02d}-{j:02d}-chave-sintetica", "ainda", servico.sal_apoios, servico.pa["apoios_minimos"])
        if k == n - 1:
            for j in range(2):
                servico.store.apoiar(rec["id"], f"demo-{k:02d}-{j:02d}-secou-sintetico", "secou", servico.sal_apoios, servico.pa["apoios_minimos"])


def aplicar(servico: Servico) -> Servico:
    """Turns a service into the demonstration one: synthetic rain, an in-memory store with seeded records and the public demo credential."""
    servico.chuva = ChuvaHoraria(0, 0, fonte=lambda lat, lon: serie_sintetica())
    servico.store, servico.token_operador = oc.Ocorrencias(), TOKEN_DEMO
    semear(servico)
    semear_comunidade(servico)
    return servico


def criar_servico_demo(base: Servico) -> Servico:
    """A second service over the same street network (shared, read-only) with its own rain, store and credential."""
    demo = Servico(base.rede, ChuvaHoraria(0, 0, fonte=lambda lat, lon: serie_sintetica()), oc.Ocorrencias(), base.explicador, base.pr,
                   token_operador=TOKEN_DEMO, territorios=base.territorios_config, resumo_rs=base.resumo_rs, cobertura_rs=base.cobertura_rs,
                   validacao=base.validacao, meta_dados=base.meta_dados, pois=base.pois, params_aprendizado=base.pa, territorio=base.territorio)
    semear(demo)
    semear_comunidade(demo)
    return demo
