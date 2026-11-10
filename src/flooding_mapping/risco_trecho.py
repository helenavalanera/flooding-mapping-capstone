"""Transparent risk baseline per street segment and hour: an ESTIMATE, not a validated forecast.

    escore(segmento, t) = fator_de_chuva(t) x peso(segmento)

``fator_de_chuva`` (0-1) depends only on the city's rain, with windows that end at ``t``:
the 24 h total and the highest hour inside it, each mapped piecewise-linearly so that the
levels measured on days with documented blockages in Porto Alegre (``chuva_medio``, ``chuva_alto``
in ``config/analysis.yaml``, lower bounds from ``reports/qa/rain_calibration.json``) give 0.4 and 1.
Wet antecedent conditions (rain in the 72 h before the window) raise it by a fixed factor.

``peso`` (0-1) is the segment's physical susceptibility percentile (relative index; see
``indice_fisico``), raised to a floor where a recent occurrence is near: a confirmed one more
than a reported one, scaled by its reliability.

What this is not: the municipal x day model (S2iD decrees, no geometry) is not used here, and
no label is propagated to streets. Nothing here was fitted or validated against street-level
flooding; the cutoffs between classes are provisional. The rain is one series for the whole
city, so the same ``fator`` applies to every street at the same hour. A segment with no terrain
data has *no estimate* (NaN); it is never read as safe.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .ocorrencias import agora

CLASSES = ("baixo", "atencao", "alto")
COMPONENTES = ["baixa_altitude", "baixa_cota_local", "perto_da_agua", "acumulacao_fluxo", "terreno_plano"]


def indice_fisico(features: pd.DataFrame) -> pd.DataFrame:
    """Percentile (0-100, 100 = most susceptible) of the equal-weight mean of five terrain facts.

    low ground, local depression (elevation minus its 250 m mean), low height above the nearest
    water, high flow accumulation and flat terrain. ``features`` has the columns of
    ``susceptibility_features_v2``. Nothing is fitted.
    """
    from .models.susceptibility_index import robust_z  # lazy: pulls heavy geospatial imports

    out = pd.DataFrame(index=features.index)
    out["baixa_altitude"] = -robust_z(features["elev"])
    out["baixa_cota_local"] = -robust_z(features["rel_elev_250"])
    out["perto_da_agua"] = -robust_z(np.log1p(features["height_above_water"].clip(lower=0)))
    out["acumulacao_fluxo"] = robust_z(features["log_flow_acc"])
    out["terreno_plano"] = -robust_z(features["slope"])
    out["indice"] = out[COMPONENTES].mean(axis=1, skipna=False)
    out["percentil"] = out["indice"].rank(pct=True) * 100
    return out


def _nivel(x: np.ndarray, medio: float, alto: float, no_medio: float) -> np.ndarray:
    """0 at 0 mm, ``no_medio`` at the medium level, 1 at the high level and above."""
    abaixo = x / medio * no_medio
    acima = no_medio + (1 - no_medio) * (x - medio) / (alto - medio)
    return np.clip(np.where(x < medio, abaixo, acima), 0, 1)


def tabela_de_chuva(serie: pd.Series, p: dict) -> pd.DataFrame:
    """Rain windows and the rain factor for every hour of the series (windows end at that hour)."""
    serie = serie.asfreq("h")
    total = serie.rolling(24, min_periods=24).sum()
    maximo = serie.rolling(24, min_periods=24).max()
    antes = serie.shift(24).rolling(72, min_periods=72).sum()
    nm, na, f0 = p["chuva_medio"], p["chuva_alto"], p["fator_no_medio"]
    fator = np.maximum(_nivel(total.to_numpy(), nm["total_24h_mm"], na["total_24h_mm"], f0),
                       _nivel(maximo.to_numpy(), nm["max_1h_mm"], na["max_1h_mm"], f0))
    umido = antes.to_numpy() >= p["antecedente_72h_mm"]
    fator = np.where(umido, np.minimum(1, fator * p["antecedente_fator"]), fator)
    tabela = pd.DataFrame({"chuva_hora_mm": serie, "total_24h_mm": total, "max_1h_mm": maximo,
                           "antecedente_72h_mm": antes, "antecedente_umido": umido, "fator": fator}, index=serie.index)
    tabela.loc[total.isna() | maximo.isna(), "fator"] = np.nan  # incomplete window: no estimate
    return tabela


def _segundos(indice) -> np.ndarray:
    """Seconds since the epoch whatever the datetime resolution of the pandas object."""
    return np.asarray((indice - pd.Timestamp(0)).total_seconds(), dtype=float)


def fator_em(tabela: pd.DataFrame, instante: pd.Timestamp) -> float:
    """Rain factor at an instant (hourly values, linear in between); NaN outside the series."""
    valid = tabela["fator"].dropna()
    if valid.empty or not (valid.index[0] <= instante <= valid.index[-1]):
        return float("nan")
    return float(np.interp(_segundos(pd.Index([instante]))[0], _segundos(valid.index), valid.to_numpy()))


def natureza(instante: pd.Timestamp, ref: pd.Timestamp) -> str:
    """``observado`` for hours up to now, ``previsto`` after (the rain behind the factor)."""
    return "observado" if instante <= ref else "previsto"


def pesos(pct: np.ndarray, rede, ocorrencias: list[dict], p: dict) -> dict:
    """Static per-segment weight, data reliability and the occurrence behind any floor.

    ``peso`` is NaN where there is neither terrain data nor a nearby occurrence.
    """
    peso = pct / 100.0
    confiab = np.where(np.isnan(pct), np.nan, p["confiabilidade"]["fisico"])
    origem = np.full(len(pct), None, dtype=object)
    for r in ocorrencias:
        if r["situacao"] not in ("reportada", "confirmada"):
            continue
        piso = p["piso_ocorrencia"][r["situacao"]] * p["fator_confiabilidade_ocorrencia"][r["confiabilidade"]]
        idx = [i for i in (rede.indices(r["segmento_ids"]) if r["segmento_ids"] else rede.proximos(r["lon"], r["lat"], p["raio_ocorrencia_m"]))]
        for i in idx:
            if np.isnan(peso[i]) or piso > peso[i]:
                peso[i] = piso
            confiab[i] = np.nanmax([confiab[i], p["confiabilidade"][r["situacao"]]])
            origem[i] = r["id"]
    return {"peso": peso, "confiabilidade": confiab, "ocorrencia": origem, "parametros": p}


def classe(escore: np.ndarray | float, p: dict):
    """``baixo`` / ``atencao`` / ``alto``; ``None`` where there is no estimate."""
    escore = np.asarray(escore, dtype=float)
    out = np.select([escore >= p["classes"]["alto"], escore >= p["classes"]["atencao"]], ["alto", "atencao"], "baixo").astype(object)
    out[np.isnan(escore)] = None
    return out if out.ndim else out.item()


LOCAL = ZoneInfo("America/Sao_Paulo")


def agora_local() -> pd.Timestamp:
    """Now as a naive Brasilia timestamp, comparable with the rain series index."""
    return pd.Timestamp(agora().astimezone(LOCAL).replace(tzinfo=None))


def para_local(instante: datetime) -> pd.Timestamp:
    """An instant as naive Brasilia time (a naive input is taken as already local)."""
    if instante.tzinfo is None:
        return pd.Timestamp(instante)
    return pd.Timestamp(instante.astimezone(LOCAL).replace(tzinfo=None))
