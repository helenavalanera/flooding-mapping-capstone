"""Municipal risk for the next 72 hours: operational rainfall + the trained trigger model.

The features are the ones used in training, built by the same code with the climatology
quantiles stored in the model artifact, so training and operation cannot drift apart. Only
days up to the issue day exist as observations; the next two days are forecasts, and the
window of every feature ends on its own day, so nothing later than the day is ever used.

``classe`` comes from the raw-score thresholds of the alert budgets stored with the model:
``alto`` is the 0.5% of municipality-days with the highest score in the out-of-sample years,
``atencao`` the 2%, ``baixo`` the rest. ``probabilidade`` is the calibrated estimate. Both are
relative estimates of a disaster *record* being opened, not of flood depth or extent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ..features import weather as feat

CLASSES = ("baixo", "atencao", "alto")
LEVELS = {"alto": "alertas_0.5pct", "atencao": "alertas_2pct"}


def load_artifact(path: str | Path) -> dict:
    """The model artifact (a joblib file kept outside git); fails on a scikit-learn mismatch."""
    import sklearn

    artifact = joblib.load(path)
    if artifact["sklearn"] != sklearn.__version__:
        raise RuntimeError(f"model trained with scikit-learn {artifact['sklearn']}, "
                           f"installed {sklearn.__version__}")
    return artifact


def classify(score: np.ndarray, thresholds: dict) -> np.ndarray:
    return np.select([score >= thresholds[LEVELS["alto"]], score >= thresholds[LEVELS["atencao"]]],
                     ["alto", "atencao"], default="baixo")


def estimate(artifact: dict, series: pd.DataFrame, towns: pd.DataFrame, grid: pd.DataFrame,
             issue_day: pd.Timestamp, horizon: int = 3) -> tuple[pd.DataFrame, list[str]]:
    """Risk of each municipality for the issue day and the following ones.

    Returns the estimates and the municipalities for which at least one day had no usable
    rainfall window (they get no estimate rather than a guess).
    """
    frame = feat.build(series, towns, grid, artifact["quantis"])
    days = pd.date_range(issue_day, periods=horizon)
    rows = frame[frame["data"].isin(days)].reset_index(drop=True)
    cols = artifact["colunas"]
    score = artifact["modelo"].predict_proba(rows[cols].to_numpy("float32"))[:, 1]
    estimates = pd.DataFrame({
        "ibge": rows["ibge"], "data": rows["data"],
        "horizonte_dias": (rows["data"] - issue_day).dt.days,
        "chuva_dia_mm": rows["p0"].round(1), "chuva_3d_mm": rows["p_3d"].round(1),
        "pontuacao": score, "probabilidade": artifact["calibrador"].predict(score),
        "classe": classify(score, artifact["limiares"])})
    complete = estimates.groupby("ibge")["data"].nunique().eq(horizon)
    missing = sorted(set(towns["ibge"]) - set(complete[complete].index))
    return estimates[estimates["ibge"].isin(complete[complete].index)].reset_index(drop=True), missing


def payload(estimates: pd.DataFrame, missing: list[str], towns: pd.DataFrame, artifact: dict,
            card: dict, meta: dict, issue_day: pd.Timestamp) -> dict:
    """The JSON the static interface reads: estimates, their provenance and their limits."""
    trigger = card["gatilho_operacional"]
    test = trigger["desempenho_teste"]
    names = towns.set_index("ibge")
    municipalities = []
    for ibge, group in estimates.groupby("ibge"):
        municipalities.append({
            "ibge": ibge, "nome": names.at[ibge, "nome"], "populacao": int(names.at[ibge, "populacao"]),
            "classe_maxima": max(group["classe"], key=CLASSES.index),
            "dias": [{"data": str(r.data.date()), "horizonte_dias": int(r.horizonte_dias),
                      "chuva_dia_mm": float(r.chuva_dia_mm), "chuva_3d_mm": float(r.chuva_3d_mm),
                      "probabilidade": round(float(r.probabilidade), 5), "classe": r.classe}
                     for r in group.sort_values("data").itertuples()]})
    return {
        "gerado_em_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "emitido_para": str(issue_day.date()),
        "tipo": "estimativa do modelo (não é observação)",
        "modelo": {"versao": artifact["versao"], "rotulo": artifact["rotulo"], "tipo": trigger["tipo"],
                   "descricao": trigger["descricao"], "familia": artifact["familia"], "estado": trigger["estado"],
                   "estado_do_modelo_de_aprendizado_de_maquina": trigger["motivo"],
                   "treinado_desde": artifact["treinado_desde"], "treinado_ate": artifact["treinado_ate"],
                   "n_variaveis": len(artifact["colunas"]),
                   "desempenho_teste_2025_em_diante": {
                       "pr_auc": test["pr_auc"], "roc_auc": test["roc_auc"], "prevalencia": test["prevalencia"],
                       "orcamento_2pct": {k: test["orcamentos"]["alertas_2pct"][k]
                                          for k in ("recall_eventos", "precisao", "dias_alerta_por_mil")}}},
        "classes": {"alto": "0,5% dos dias-município de maior pontuação no histórico",
                    "atencao": "2% dos dias-município de maior pontuação no histórico",
                    "baixo": "demais casos"},
        "fonte_chuva": {k: meta[k] for k in ("fonte", "emitido_em_utc", "primeira_data", "ultima_data")},
        "municipios_sem_dados": [{"ibge": i, "nome": names.at[i, "nome"]} for i in missing],
        "avisos": ["Estimativa estatística de que um município registre desastre hídrico; "
                   "não prevê profundidade, extensão nem duração da água.",
                   "Não substitui os alertas oficiais da Defesa Civil.",
                   "O gatilho foi ajustado com chuva de reanálise e opera com previsão: a qualidade "
                   "cai quando a previsão erra a chuva.",
                   "Municípios sem registro no S2iD não são municípios sem alagamento."],
        "municipios": municipalities}
