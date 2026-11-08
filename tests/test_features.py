import numpy as np
import pandas as pd
import pytest

from flooding_mapping.features import weather

DAYS = pd.date_range("2024-01-01", periods=120, freq="D")


def series(seed=1, towns=("4300001", "4300002")):
    rng = np.random.default_rng(seed)
    values = rng.gamma(0.4, 12, size=(len(DAYS), len(towns)))
    return pd.DataFrame(values, index=DAYS, columns=list(towns))


def test_rolling_sum_matches_pandas_and_is_nan_until_the_window_is_complete():
    s = series()
    ours = weather.rolling_sum(s.to_numpy(), 7)
    reference = s.rolling(7).sum().to_numpy()
    assert np.isnan(ours[:6]).all() and not np.isnan(ours[6]).any()
    assert np.allclose(ours[6:], reference[6:])


def test_ant_7d_covers_the_seven_days_before_today_not_today():
    s = series()
    feats = weather.rain_features(s)
    expected = s.shift(1).rolling(7).sum().to_numpy()
    assert np.allclose(feats["ant_7d"][7:], expected[7:])
    assert np.allclose(feats["p_7d"][7:] - feats["p0"][7:], feats["ant_7d"][7:] - s.shift(7).to_numpy()[7:])


def test_a_missing_day_makes_every_window_that_contains_it_nan():
    s = series()
    s.iloc[50, 0] = np.nan
    p7 = weather.rain_features(s)["p_7d"]
    assert np.isnan(p7[50:57, 0]).all() and not np.isnan(p7[57, 0]) and not np.isnan(p7[50:57, 1]).any()


def test_no_feature_of_day_d_uses_rain_after_d():
    """The leakage guard: rewrite the future and the past rows must not change."""
    base = series()
    altered = base.copy()
    altered.iloc[80:] = altered.iloc[80:] * 50 + 100  # a flood nobody could have known about
    a, b = weather.rain_features(base), weather.rain_features(altered)
    for name in weather.RAIN_FEATURES:
        assert np.allclose(a[name][:80], b[name][:80], equal_nan=True), name
    qa = weather.local_quantiles(a, DAYS, "2024-03-20")
    qb = weather.local_quantiles(b, DAYS, "2024-03-20")
    assert np.allclose(qa.to_numpy(), qb.to_numpy())  # quantiles fitted on days <= 80 only


def test_local_quantiles_ignore_everything_after_the_cut_date():
    base = series()
    cut = str(DAYS[90].date())
    q1 = weather.local_quantiles(weather.rain_features(base), DAYS, cut)
    changed = base.copy()
    changed.iloc[91:] = 1000.0
    q2 = weather.local_quantiles(weather.rain_features(changed), DAYS, cut)
    assert np.allclose(q1.to_numpy(), q2.to_numpy())


def test_relative_rain_is_the_multiple_of_the_local_95th_percentile():
    s = series()
    feats = weather.rain_features(s)
    q = weather.local_quantiles(feats, DAYS, "2024-04-29").set_axis(s.columns)
    rel = weather.relative_features(feats, q)
    i = 60
    assert np.allclose(rel["rel_p3d"][i], feats["p_3d"][i] / np.maximum(q["q_p3d"].to_numpy(), 1.0))


def test_build_has_one_row_per_municipality_day_and_drops_incomplete_windows():
    s = series()
    towns = pd.DataFrame({"ibge": s.columns, "lat": [-30.0, -29.0], "lon": [-51.0, -52.0],
                          "area_km2": [100.0, 400.0], "populacao": [1000.0, 50000.0],
                          "regiao_imediata": ["R1", "R1"]})
    grid = pd.DataFrame({"ibge": s.columns, "altitude_m": [10.0, 700.0]})
    frame = weather.build(s, towns, grid, weather.fit_quantiles(s, "2024-04-29"))
    assert len(frame) == (len(DAYS) - 30) * 2  # the 30-day window needs 30 days
    assert frame["data"].min() == DAYS[30]
    needed = (weather.RAIN_FEATURES + weather.RELATIVE_FEATURES + weather.REGIONAL_FEATURES
              + weather.SEASON_FEATURES + weather.TERRITORY_FEATURES)
    assert set(needed) <= set(frame.columns) and not frame[needed].isna().any().any()
    row = frame[(frame["ibge"] == "4300002") & (frame["data"] == DAYS[40])].iloc[0]
    assert row["altitude_m"] == 700 and row["lat"] == -29.0
    assert row["p0"] == pytest.approx(s.iloc[40, 1], rel=1e-5)


def test_regional_features_summarize_the_same_day_rain_of_the_region_and_the_state():
    days = pd.date_range("2024-01-01", periods=40)
    series = pd.DataFrame({"A": 10.0, "B": 30.0, "C": 1.0, "D": 1.0}, index=days)
    region = pd.Series({"A": "R1", "B": "R1", "C": "R2", "D": "R2"})
    feats = weather.rain_features(series)
    out = weather.regional_features(feats, series.columns, region)
    i = 35
    assert out["reg_p3d_mean"][i].tolist() == [60.0, 60.0, 3.0, 3.0]    # 3-day totals: A 30, B 90 -> 60
    assert out["reg_p3d_max"][i].tolist() == [90.0, 90.0, 3.0, 3.0]
    assert out["estado_frac_p3d_50"][i].tolist() == [0.25] * 4         # only B has >= 50 mm in 3 days
    assert np.isnan(out["reg_p3d_mean"][:2]).all()                      # window not complete yet


def test_regional_context_never_uses_rain_after_the_day():
    base = series(towns=("4300001", "4300002", "4300003"))
    region = pd.Series({"4300001": "R1", "4300002": "R1", "4300003": "R2"})
    altered = base.copy()
    altered.iloc[80:] = altered.iloc[80:] * 40 + 90
    a = weather.regional_features(weather.rain_features(base), base.columns, region)
    b = weather.regional_features(weather.rain_features(altered), base.columns, region)
    for name in weather.REGIONAL_FEATURES:
        assert np.allclose(a[name][:80], b[name][:80], equal_nan=True), name
