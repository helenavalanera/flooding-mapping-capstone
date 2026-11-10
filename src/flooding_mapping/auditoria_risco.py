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
from .risco_trecho import tabela_de_chuva

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


def fator_nos_eventos(p: dict, buscar=request) -> list[dict]:
    """Rain factor at the report hour of each documented event, with and without the recession."""
    linhas = []
    for dia, hora in EVENTOS.items():
        d0 = pd.Timestamp(dia)
        resposta, _ = buscar(ARCHIVE_URL, {**POA, "hourly": "precipitation", "timezone": TIMEZONE,
                                           "start_date": (d0 - pd.Timedelta(days=5)).date().isoformat(), "end_date": d0.date().isoformat()})
        serie = pd.Series(resposta["hourly"]["precipitation"], index=pd.to_datetime(resposta["hourly"]["time"]), dtype=float)
        com, sem = tabela_de_chuva(serie, p), tabela_de_chuva(serie, {**p, "recuo_h": 10**6})
        quando, dia_todo = d0 + pd.Timedelta(hours=hora), serie[d0:d0 + pd.Timedelta(hours=23)]
        chuvosas = dia_todo[dia_todo >= p["chuva_minima_mm"]]
        ultima = chuvosas.index.max() if len(chuvosas) else None
        linhas.append({"data": dia, "hora_do_reporte": hora, "chuva_no_dia_mm": round(float(dia_todo.sum()), 1), "max_1h_mm": round(float(dia_todo.max()), 1),
                       "ultima_hora_com_chuva": None if ultima is None else ultima.strftime("%H:%M"),
                       "horas_secas_antes_do_reporte": None if ultima is None or ultima >= quando else int((quando - ultima) / pd.Timedelta(hours=1)),
                       "fator_com_recuo": round(float(com.loc[quando, "fator"]), 2), "fator_sem_recuo": round(float(sem.loc[quando, "fator"]), 2)})
    return linhas


def main() -> None:
    argparse.ArgumentParser(description="Auditoria do baseline de risco por trecho").parse_args()
    p = load_config()["risco_trecho"]
    rede = pd.read_parquet(resolve("data/processed/rede_poa.parquet"), columns=["comprimento_m", "percentil", "drive", "walk"])
    eventos = fator_nos_eventos(p)
    relatorio = {
        "natureza": "auditoria descritiva; nenhum parâmetro foi alterado",
        "cobertura_do_indice_fisico": cobertura_poa(rede), "fracao_da_malha_sinalizada_por_fator_de_chuva": fracao_sinalizada(rede, p),
        "fator_nas_horas_dos_bloqueios_documentados": eventos,
        "conclusoes": [
            "Os trechos só de pedestres (calçadas e passagens) não têm índice: para quem anda a pé, parte do percurso fica sem estimativa, e o rótulo de menor exposição deve avisar quando vier de trechos sem dado.",
            "Nos quatro eventos a chuva continuou até a noite ou o reporte ocorreu durante ela: eles não restringem a duração do recuo (6 h é provisório, sem evidência a favor nem contra).",
            "Em 2022-03-06 o fator na hora do reporte fica abaixo do corte de Atenção para qualquer trecho: o baseline não sinalizaria esse evento (já era erro conhecido do gatilho municipal).",
            "Os eventos ancoram os níveis de chuva (limites inferiores): a verificação dos níveis contra eles é circular e não os valida."]}
    destino = resolve("reports/ml/risco_trecho_auditoria.json")
    destino.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: relatorio[k] for k in ("cobertura_do_indice_fisico", "fracao_da_malha_sinalizada_por_fator_de_chuva")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
