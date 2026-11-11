"""Municipality x day dataset for the trigger model.

Unit and target
    One row per municipality and day. ``y = 1`` when an S2iD record of the chosen disaster
    types has its protocol date ``t`` in ``[d, d + LABEL_BEFORE_DAYS]``, that is, the day
    falls in the ``LABEL_BEFORE_DAYS + 1`` days that end on the record date. The protocol
    date is when the record was opened, usually the day of or after the rainfall that
    caused it, so a window absorbs that offset instead of betting on a single day.

Negatives
    Every other day is labelled 0. They are *unlabelled* rather than confirmed negatives
    (a municipality that did not file is not a municipality without flooding), so metrics are
    read as ranking quality and false alarms are an upper bound. The ``BUFFER_AFTER_DAYS``
    days after a record are dropped: the water is still there and the day is neither a clean
    negative nor a prediction target.

Grouping
    Positive days of all municipalities are clustered into episodes (a new episode starts
    after ``EPISODE_GAP_DAYS`` days without positives). The splits in ``evaluation.splits``
    keep every episode on one side, so one storm never feeds both training and test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LABEL_BEFORE_DAYS = 2
BUFFER_AFTER_DAYS = 3
EPISODE_GAP_DAYS = 5


def label(frame: pd.DataFrame, records: pd.DataFrame, cobrade: tuple[int, ...]) -> pd.DataFrame:
    """Add ``y`` and ``excluido``; ``frame`` has one row per (ibge, data)."""
    chosen = records[records["cobrade"].isin(cobrade)][["ibge", "data_evento"]].drop_duplicates()
    positive: set[tuple[str, pd.Timestamp]] = set()
    buffer: set[tuple[str, pd.Timestamp]] = set()
    for ibge, event in zip(chosen["ibge"], chosen["data_evento"]):
        positive.update((ibge, event - pd.Timedelta(days=k)) for k in range(LABEL_BEFORE_DAYS + 1))
        buffer.update((ibge, event + pd.Timedelta(days=k)) for k in range(1, BUFFER_AFTER_DAYS + 1))
    keys = pd.MultiIndex.from_arrays([frame["ibge"], frame["data"]])
    is_positive = keys.isin(list(positive))
    out = frame.copy()
    out["y"] = is_positive.astype("int8")
    out["excluido"] = keys.isin(list(buffer)) & ~is_positive
    return out


def episodes(positive_dates: pd.Series, gap_days: int = EPISODE_GAP_DAYS) -> pd.Series:
    """Episode number (from 0) for each distinct positive date."""
    dates = pd.Series(sorted(pd.to_datetime(positive_dates).unique()))
    new = dates.diff().dt.days.fillna(gap_days + 1) > gap_days
    return pd.Series(new.cumsum().to_numpy() - 1, index=dates.to_numpy())


def assign_episodes(frame: pd.DataFrame) -> pd.DataFrame:
    """``episodio``: the episode of a positive day, -1 for every other day."""
    numbers = episodes(frame.loc[frame["y"] == 1, "data"])
    out = frame.copy()
    out["episodio"] = out["data"].map(numbers).fillna(-1).astype("int32")
    return out


def describe(frame: pd.DataFrame, label_name: str) -> dict:
    """Dimensions, class balance and coverage, for the dataset card."""
    used = frame[~frame["excluido"]]
    positives = used[used["y"] == 1]
    per_year = used.groupby(used["data"].dt.year)["y"].agg(["size", "sum"])
    return {
        "rotulo": label_name,
        "linhas": int(len(frame)), "linhas_usadas": int(len(used)),
        "linhas_excluidas_pos_evento": int(frame["excluido"].sum()),
        "municipios": int(frame["ibge"].nunique()),
        "periodo": [str(frame["data"].min().date()), str(frame["data"].max().date())],
        "positivos": int(len(positives)), "prevalencia": round(float(used["y"].mean()), 5),
        "positivos_por_negativo": round(float(len(positives) / max((used["y"] == 0).sum(), 1)), 5),
        "municipios_com_positivo": int(positives["ibge"].nunique()),
        "episodios": int(positives["episodio"].nunique()),
        "positivos_por_ano": {int(y): int(v) for y, v in per_year["sum"].items()},
        "janela_rotulo_dias": LABEL_BEFORE_DAYS + 1, "buffer_pos_evento_dias": BUFFER_AFTER_DAYS,
        "intervalo_entre_episodios_dias": EPISODE_GAP_DAYS,
    }


def build(features: pd.DataFrame, records: pd.DataFrame, cobrade: tuple[int, ...]) -> pd.DataFrame:
    """Labelled dataset: features + ``y``, ``excluido``, ``episodio``."""
    return assign_episodes(label(features, records, cobrade))


def rain_profile(series: pd.DataFrame, records: pd.DataFrame, cobrade: tuple[int, ...], seed: int = 0,
                 heavy_mm: float = 20.0, lags: range = range(-3, 4)) -> dict:
    """Daily rain around each record's protocol date: does the date match the rain?

    ``series`` is days x municipalities. Lag 0 is the protocol date; a record whose window falls
    outside the series is skipped. Random days of the same municipalities are the comparison.
    """
    values = series.to_numpy(float)
    chosen = records[records["cobrade"].isin(cobrade) & records["ibge"].isin(series.columns)]
    cols = series.columns.get_indexer(chosen["ibge"])
    around = {}
    for lag in lags:
        rows = series.index.get_indexer(chosen["data_evento"] + pd.Timedelta(days=lag))
        around[lag] = np.where(rows >= 0, values[np.maximum(rows, 0), cols], np.nan)
    table = pd.DataFrame(around).dropna()
    rng = np.random.default_rng(seed)
    random_days = values[rng.integers(0, len(values), len(table)), series.columns.get_indexer(chosen["ibge"])[: len(table)]]
    return {"registros": int(len(table)),
            "mediana_mm_por_defasagem": {int(k): round(float(table[k].median()), 1) for k in lags},
            "fracao_com_chuva_forte_no_dia_do_protocolo": round(float((table[0] >= heavy_mm).mean()), 3),
            "fracao_com_chuva_forte_em_dias_aleatorios": round(float(np.nanmean(random_days >= heavy_mm)), 3),
            "chuva_forte_mm": heavy_mm}
