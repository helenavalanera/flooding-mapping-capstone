"""Audit of the street-risk baseline: what its parameters rest on and where the evidence ends.

    python -m flooding_mapping.auditoria_risco      ->  reports/ml/risco_trecho_auditoria.json

Nothing here changes a parameter. It measures (1) how much of the network the terrain index covers,
(2) which share of it each class flags at three rain levels, and (3) the rain factor at the hour
each documented blockage was reported, with and without the post-rain recession, to see whether
those events say anything about the recession length. They do not constrain it: that is the finding.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from .cobertura import cobertura_poa
from .config import load_config, resolve
from .ingestion.weather import ARCHIVE_URL, TIMEZONE, request
from .risco_trecho import classe, pesos, tabela_de_chuva
from .rotas import Rede

POA = {"latitude": -30.03, "longitude": -51.22}
EVENTOS = {"2019-09-17": 18, "2021-09-08": 7, "2022-03-06": 17, "2025-06-18": 21}   # date -> hour of the report (rain_calibration.json)


def fracao_sinalizada(rede: pd.DataFrame, p: dict, fatores=(0.4, 0.7, 1.0)) -> dict:
    """Share of the km that has an index flagged at each class for a given rain factor."""
    com = rede[rede["percentil"].notna()]
    km = (com["comprimento_m"] / 1000).to_numpy()
    peso = np.clip((com["percentil"].to_numpy() - p["corte_fisico"]) / (100 - p["corte_fisico"]), 0, 1)
    out = {}
    for f in fatores:
        e = f * peso
        out[str(f)] = {"alto": round(float(km[e >= p["classes"]["alto"]].sum() / km.sum()), 4),
                       "atencao": round(float(km[(e >= p["classes"]["atencao"]) & (e < p["classes"]["alto"])].sum() / km.sum()), 4)}
    return out


def tabelas_dos_eventos(p: dict, buscar=request) -> dict:
    """Hourly rain table (with and without the recession) of each documented event date, from the five days before it."""
    saida = {}
    for dia in EVENTOS:
        d0 = pd.Timestamp(dia)
        resposta, _ = buscar(ARCHIVE_URL, {**POA, "hourly": "precipitation", "timezone": TIMEZONE,
                                           "start_date": (d0 - pd.Timedelta(days=5)).date().isoformat(), "end_date": d0.date().isoformat()})
        serie = pd.Series(resposta["hourly"]["precipitation"], index=pd.to_datetime(resposta["hourly"]["time"]), dtype=float)
        saida[dia] = {"serie": serie, "com": tabela_de_chuva(serie, p), "sem": tabela_de_chuva(serie, {**p, "recuo_h": 10**6})}
    return saida


def fator_nos_eventos(p: dict, buscar=request, tabelas: dict | None = None) -> list[dict]:
    """Rain factor at the report hour of each documented event, with and without the recession."""
    tabelas, linhas = tabelas or tabelas_dos_eventos(p, buscar), []
    for dia, hora in EVENTOS.items():
        d0, t = pd.Timestamp(dia), tabelas[dia]
        quando, dia_todo = d0 + pd.Timedelta(hours=hora), t["serie"][d0:d0 + pd.Timedelta(hours=23)]
        chuvosas = dia_todo[dia_todo >= p["chuva_minima_mm"]]
        ultima = chuvosas.index.max() if len(chuvosas) else None
        linhas.append({"data": dia, "hora_do_reporte": hora, "chuva_no_dia_mm": round(float(dia_todo.sum()), 1), "max_1h_mm": round(float(dia_todo.max()), 1),
                       "ultima_hora_com_chuva": None if ultima is None else ultima.strftime("%H:%M"),
                       "horas_secas_antes_do_reporte": None if ultima is None or ultima >= quando else int((quando - ultima) / pd.Timedelta(hours=1)),
                       "fator_com_recuo": round(float(t["com"].loc[quando, "fator"]), 2), "fator_sem_recuo": round(float(t["sem"].loc[quando, "fator"]), 2)})
    return linhas


def eventos_confrontados(rede: Rede, eventos: pd.DataFrame, horas: dict, tabelas: dict, p: dict, raio_m: float = 50) -> dict:
    """Does the baseline flag the streets of each documented blockage, at the hour it was reported and at some hour that day?

    An event with no street that has a terrain index cannot be assessed (there is nothing to weigh), which is different from
    missing it. Nothing here treats a street without a record as a negative example."""
    peso = pesos(rede.pct, rede, [], p)["peso"]
    uteis = rede.arestas["drive"].to_numpy(bool) & np.isfinite(rede.pct)
    linhas = []
    for ev in eventos.dropna(subset=["latitude", "longitude"]).itertuples():
        proximos = [i for i in rede.proximos(ev.longitude, ev.latitude, raio_m) if uteis[i]]
        base = {"evento": ev.event_id, "data": ev.event_date, "geocodificacao": ev.geocode_method, "confianca_do_evento": ev.confidence, "segmentos_proximos_com_indice": len(proximos)}
        if not proximos:
            linhas.append({**base, "avaliavel": False, "motivo": "nenhum segmento dirigível com índice físico a até 50 m"})
            continue
        t, hora = tabelas[ev.event_date]["com"], horas[ev.event_id]
        d0 = pd.Timestamp(ev.event_date)
        w = float(np.nanmax(peso[proximos]))
        f_hora = float(t.loc[d0 + pd.Timedelta(hours=hora), "fator"])
        f_dia = float(t.loc[d0:d0 + pd.Timedelta(hours=23), "fator"].max())
        c_hora, c_dia = classe(f_hora * w, p), classe(f_dia * w, p)
        ok_hora, ok_dia = c_hora in ("atencao", "alto"), c_dia in ("atencao", "alto")
        motivo = None
        if not ok_dia:
            motivo = "peso zero: segmentos abaixo do percentil de corte" if w == 0 else "chuva abaixo do nível que sinaliza esses trechos"
        elif not ok_hora:
            motivo = "sinalizado em outra hora do dia, não na hora do reporte"
        linhas.append({**base, "avaliavel": True, "peso_maximo": round(w, 3), "fator_na_hora": round(f_hora, 2), "classe_na_hora": c_hora, "fator_maximo_do_dia": round(f_dia, 2),
                       "classe_maxima_do_dia": c_dia, "detectado_na_hora_do_reporte": bool(ok_hora), "detectado_em_alguma_hora_do_dia": bool(ok_dia), "motivo_se_nao_detectado": motivo})
    ok = [x for x in linhas if x["avaliavel"]]
    return {"eventos": linhas, "resumo": {
        "eventos_geocodificados": len(linhas), "avaliaveis": len(ok), "nao_avaliaveis": len(linhas) - len(ok),
        "detectados_na_hora_do_reporte": sum(x["detectado_na_hora_do_reporte"] for x in ok), "detectados_em_alguma_hora_do_dia": sum(x["detectado_em_alguma_hora_do_dia"] for x in ok),
        "nao_detectados_no_dia": sum(not x["detectado_em_alguma_hora_do_dia"] for x in ok), "datas_distintas": int(eventos["event_date"].nunique()),
        "motivos_dos_nao_detectados": {m: sum(1 for x in ok if x["motivo_se_nao_detectado"] == m) for m in {x["motivo_se_nao_detectado"] for x in ok} - {None}}}}


def sensibilidade_do_corte(rede: Rede, eventos: pd.DataFrame, tabelas: dict, p: dict, cortes=(0, 50, 70, 80, 85, 90), raio_m: float = 50) -> list[dict]:
    """For several cutoffs of the weight ramp: how many documented events are flagged at some hour of their day, and how much of the
    network is flagged at the maximum rain factor. It is information about the trade-off, not a recommendation to change the cutoff:
    the events are few and clustered in four dates, and the rain levels were anchored on them."""
    com_indice = rede.arestas["drive"].to_numpy(bool) & np.isfinite(rede.pct)
    km = rede.comp_m / 1000
    pontos = [(ev, [i for i in rede.proximos(ev.longitude, ev.latitude, raio_m) if com_indice[i]]) for ev in eventos.dropna(subset=["latitude", "longitude"]).itertuples()]
    pontos = [(ev, prox) for ev, prox in pontos if prox]
    saida = []
    for corte in cortes:
        pc = {**p, "corte_fisico": corte}
        peso = pesos(rede.pct, rede, [], pc)["peso"]
        detectados = 0
        for ev, prox in pontos:
            f_dia = float(tabelas[ev.event_date]["com"].loc[pd.Timestamp(ev.event_date):pd.Timestamp(ev.event_date) + pd.Timedelta(hours=23), "fator"].max())
            detectados += classe(f_dia * float(np.nanmax(peso[prox])), pc) in ("atencao", "alto")
        escore = np.nan_to_num(peso)
        sinalizado = km[(escore >= p["classes"]["atencao"]) & np.isfinite(rede.pct)].sum() / km[np.isfinite(rede.pct)].sum()
        saida.append({"corte_fisico": corte, "eventos_detectados_em_algum_hora_do_dia": int(detectados), "de": len(pontos), "malha_sinalizada_com_chuva_no_maximo": round(float(sinalizado), 3),
                      "e_o_valor_atual": corte == p["corte_fisico"]})
    return saida


def dias_de_alerta_sem_registro(p: dict, dias_documentados: set, buscar=request, ate: str | None = None) -> dict:
    """Days from 2019 on in which SOME street would be flagged, against the days with a documented blockage.

    The documented days are few and come from news and operators, so a flagged day without a record is NOT a false alarm: the
    absence of a record is not a negative. It only says how often the baseline would speak and how few of those days we can check."""
    fim = ate or (pd.Timestamp.now() - pd.Timedelta(days=8)).date().isoformat()
    resposta, _ = buscar(ARCHIVE_URL, {**POA, "hourly": "precipitation", "timezone": TIMEZONE, "start_date": "2019-01-01", "end_date": fim})
    serie = pd.Series(resposta["hourly"]["precipitation"], index=pd.to_datetime(resposta["hourly"]["time"]), dtype=float)
    fator = tabela_de_chuva(serie, p)["fator"].groupby(lambda t: t.date().isoformat()).max()
    atencao, alto = fator[fator >= p["classes"]["atencao"]], fator[fator >= p["classes"]["alto"]]
    marcados = set(atencao.index)
    return {"periodo": ["2019-01-01", fim], "dias": int(len(fator)), "dias_com_alguma_via_em_atencao": int(len(atencao)), "dias_com_alguma_via_em_alto": int(len(alto)),
            "dias_documentados": len(dias_documentados), "dias_documentados_sinalizados": len(dias_documentados & marcados),
            "dias_sinalizados_sem_registro": len(marcados - dias_documentados),
            "leitura": "ausência de registro não é exemplo negativo: os dias sinalizados sem registro não são falsos alertas comprovados, apenas dias que não conseguimos conferir"}


def main() -> None:
    argparse.ArgumentParser(description="Auditoria do baseline de risco por trecho").parse_args()
    p = load_config()["risco_trecho"]
    rede = pd.read_parquet(resolve("data/processed/rede_poa.parquet"), columns=["comprimento_m", "percentil", "drive", "walk"])
    tabelas = tabelas_dos_eventos(p)
    eventos = fator_nos_eventos(p, tabelas=tabelas)
    rede_completa = Rede(pd.read_parquet(resolve("data/processed/rede_poa.parquet")), load_config()["roteamento"])
    calibracao = json.loads(resolve("reports/qa/rain_calibration.json").read_text())
    horas = {e["event_id"]: e["report_hour"] for e in calibracao["events"]}
    confronto = eventos_confrontados(rede_completa, pd.read_csv(resolve("data/events/events.csv")), horas, tabelas, p)
    sem_registro = dias_de_alerta_sem_registro(p, set(EVENTOS))
    eventos_csv = pd.read_csv(resolve("data/events/events.csv"))
    curva = sensibilidade_do_corte(rede_completa, eventos_csv, tabelas, p)
    relatorio = {
        "natureza": "auditoria descritiva; nenhum parâmetro foi alterado",
        "cobertura_do_indice_fisico": cobertura_poa(rede), "fracao_da_malha_sinalizada_por_fator_de_chuva": fracao_sinalizada(rede, p),
        "fator_nas_horas_dos_bloqueios_documentados": eventos, "confronto_com_eventos_documentados": confronto, "dias_de_alerta_sem_registro": sem_registro, "sensibilidade_do_corte_fisico": curva,
        "conclusoes": [
            "Os trechos só de pedestres (calçadas e passagens) não têm índice: para quem anda a pé, parte do percurso fica sem estimativa, e o rótulo de menor exposição deve avisar quando vier de trechos sem dado.",
            "Nos quatro eventos a chuva continuou até a noite ou o reporte ocorreu durante ela: eles não restringem a duração do recuo (6 h é provisório, sem evidência a favor nem contra).",
            "Em 2022-03-06 o fator na hora do reporte fica abaixo do corte de Atenção para qualquer trecho: o baseline não sinalizaria esse evento (já era erro conhecido do gatilho municipal).",
            "Os eventos ancoram os níveis de chuva (limites inferiores): a verificação dos níveis contra eles é circular e não os valida.",
            "Dos bloqueios documentados, o baseline sinaliza uma minoria: em vários deles os segmentos próximos têm peso zero, mesmo com chuva no nível máximo. O índice físico não discrimina bem esses locais.",
            "Nenhum corte do índice detecta os eventos sem sinalizar uma parcela grande da malha (ver a curva): não há ajuste de parâmetro que resolva a falta de poder discriminativo, e os eventos são poucos e concentrados em quatro datas.",
            "Dias sinalizados sem registro não são falsos alertas: ausência de registro não é exemplo negativo."]}
    destino = resolve("reports/ml/risco_trecho_auditoria.json")
    destino.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: relatorio[k] for k in ("cobertura_do_indice_fisico", "fracao_da_malha_sinalizada_por_fator_de_chuva")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
