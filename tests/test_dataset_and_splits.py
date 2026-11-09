import numpy as np
import pandas as pd
import pytest

from flooding_mapping.datasets import gatilho
from flooding_mapping.evaluation import metrics, splits


def frame_for(towns=("A", "B"), start="2022-12-01", days=120):
    days_index = pd.date_range(start, periods=days, freq="D")
    return pd.DataFrame({"ibge": np.repeat(list(towns), days), "data": np.tile(days_index, len(towns))})


def records(*rows):
    return pd.DataFrame(rows, columns=["ibge", "data_evento", "cobrade"]).assign(
        data_evento=lambda d: pd.to_datetime(d["data_evento"]))


def test_label_window_covers_the_days_ending_on_the_record_date_and_buffers_the_aftermath():
    f = frame_for()
    out = gatilho.label(f, records(("A", "2023-01-10", 12200)), (12200,))
    a = out[out["ibge"] == "A"].set_index("data")
    assert a.loc["2023-01-08":"2023-01-10", "y"].eq(1).all() and a["y"].sum() == 3
    assert a.loc["2023-01-11":"2023-01-13", "excluido"].all() and a["excluido"].sum() == 3
    assert out[out["ibge"] == "B"]["y"].sum() == 0  # another municipality is untouched


def test_only_the_chosen_disaster_types_become_positives():
    f = frame_for()
    rec = records(("A", "2023-01-10", 12200), ("A", "2023-02-10", 13214), ("A", "2023-03-10", 14110))
    strict = gatilho.label(f, rec, (12100, 12200, 12300))
    broad = gatilho.label(f, rec, (12100, 12200, 12300, 13214))
    assert strict["y"].sum() == 3 and broad["y"].sum() == 6  # drought never counts


def test_a_day_that_is_positive_for_another_record_is_not_buffered():
    f = frame_for()
    out = gatilho.label(f, records(("A", "2023-01-10", 12200), ("A", "2023-01-12", 12200)), (12200,))
    day = out[(out["ibge"] == "A") & (out["data"] == "2023-01-12")].iloc[0]
    assert day["y"] == 1 and not day["excluido"]


def test_episodes_split_on_gaps_longer_than_five_days():
    dates = pd.Series(pd.to_datetime(["2023-01-01", "2023-01-03", "2023-01-08", "2023-01-20"]))
    numbers = gatilho.episodes(dates)
    assert list(numbers.values) == [0, 0, 0, 1]  # gap of 5 days keeps the episode together


def test_describe_reports_class_balance_and_coverage():
    f = gatilho.build(frame_for(), records(("A", "2023-01-10", 12200)), (12200,))
    card = gatilho.describe(f, "estrito")
    assert card["positivos"] == 3 and card["episodios"] == 1 and card["municipios"] == 2
    assert card["linhas_excluidas_pos_evento"] == 3 and card["janela_rotulo_dias"] == 3


def long_frame():
    f = frame_for(days=2500, start="2020-01-01")
    f["y"], f["excluido"] = 0, False
    return f


def test_temporal_split_is_ordered_purged_and_disjoint():
    f = long_frame()
    m = splits.temporal(f)
    train, val, test = (f.loc[m[k], "data"] for k in ("train", "val", "test"))
    assert train.max() < splits.VAL_START - pd.Timedelta(days=splits.PURGE_DAYS - 1)
    assert val.min() >= splits.VAL_START and val.max() < splits.TEST_START - pd.Timedelta(days=splits.PURGE_DAYS - 1)
    assert test.min() >= splits.TEST_START
    assert not (m["train"] & m["val"]).any() and not (m["val"] & m["test"]).any()


def test_buffered_rows_never_enter_any_split():
    f = long_frame()
    f.loc[f["data"] == "2021-05-05", "excluido"] = True
    m = splits.temporal(f)
    assert not (m["train"] & f["excluido"].to_numpy()).any()


def test_rolling_origin_trains_only_on_the_past():
    f = long_frame()
    for year, train, test in splits.rolling_origin(f, range(2022, 2024)):
        assert f.loc[train, "data"].max() < pd.Timestamp(year=year, month=1, day=1) - pd.Timedelta(days=splits.PURGE_DAYS)
        assert f.loc[test, "data"].dt.year.eq(year).all()


def test_spatial_holdout_never_trains_on_the_held_out_region_and_tests_in_the_future():
    towns = pd.DataFrame({"ibge": list("ABCDEF"), "lat": [-30, -30.1, -29, -29.1, -31, -31.1],
                          "lon": [-51, -51.1, -53, -53.1, -52, -52.1]})
    blocks = splits.spatial_blocks(towns, k=3)
    f = frame_for(towns=towns["ibge"], days=2500, start="2020-01-01")
    f["y"], f["excluido"] = 0, False
    train, test = splits.spatial_holdout(f, blocks, held_out=0)
    held = set(blocks[blocks == 0].index)
    assert set(f.loc[train, "ibge"]).isdisjoint(held) and set(f.loc[test, "ibge"]) <= held
    assert f.loc[train, "data"].max() < f.loc[test, "data"].min()


def test_metrics_at_a_threshold_and_event_recall():
    f = pd.DataFrame({"ibge": ["A"] * 8, "data": pd.date_range("2025-01-01", periods=8),
                      "y": [0, 1, 1, 0, 0, 1, 0, 0]})
    score = np.array([0.1, 0.2, 0.9, 0.1, 0.1, 0.1, 0.1, 0.8])
    row = metrics.at_threshold(f["y"].to_numpy(), score, 0.5)
    assert (row["tp"], row["fp"], row["fn"], row["tn"]) == (1, 1, 2, 4)
    assert row["precisao"] == 0.5 and row["recall"] == pytest.approx(0.3333, abs=1e-3)
    events = metrics.event_recall(f, score, 0.5)
    assert events["eventos"] == 2 and events["eventos_detectados"] == 1  # run 1-2 caught, day 5 missed


def test_ranking_and_calibration_return_the_documented_fields():
    rng = np.random.default_rng(0)
    y = (rng.random(5000) < 0.05).astype(int)
    score = np.clip(y * 0.3 + rng.random(5000) * 0.7, 0, 1)
    r = metrics.ranking(y, score)
    assert r["roc_auc"] > 0.7 and r["pr_auc"] > r["prevalencia"]
    cal = metrics.calibration(y, np.clip(score * 0.2, 0, 1))
    assert {"brier", "brier_referencia_prevalencia", "confiabilidade"} <= set(cal)
    budgets = metrics.budget_thresholds(score)
    assert budgets["alertas_0.5pct"] > budgets["alertas_2pct"] > budgets["alertas_5pct"]
    for share, key in ((0.005, "alertas_0.5pct"), (0.02, "alertas_2pct"), (0.05, "alertas_5pct")):
        assert (score >= budgets[key]).mean() == pytest.approx(share, abs=0.002)


def test_rain_profile_shows_whether_the_protocol_date_matches_the_rain():
    days = pd.date_range("2024-01-01", periods=60)
    series = pd.DataFrame(0.0, index=days, columns=["A", "B"])
    series.loc["2024-02-10", "A"] = 40.0       # the rain falls on the protocol date
    series.loc["2024-02-09", "A"] = 10.0
    records = pd.DataFrame({"ibge": ["A", "Z"], "data_evento": pd.to_datetime(["2024-02-10", "2024-02-10"]), "cobrade": [12200, 12200]})
    profile = gatilho.rain_profile(series, records, (12200,))
    assert profile["registros"] == 1                                  # municipality Z is not in the series
    assert profile["mediana_mm_por_defasagem"][0] == 40.0 and profile["mediana_mm_por_defasagem"][-1] == 10.0
    assert profile["mediana_mm_por_defasagem"][1] == 0.0 and profile["fracao_com_chuva_forte_no_dia_do_protocolo"] == 1.0
    assert profile["fracao_com_chuva_forte_em_dias_aleatorios"] < 0.2
