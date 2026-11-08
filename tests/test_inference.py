import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from flooding_mapping.features import weather as feat
from flooding_mapping.inference import forecast

TOWNS = ["4300001", "4300002", "4300003"]
DAYS = pd.date_range("2026-09-29", periods=43)  # 40 past days + 3 forecast days


def towns():
    return pd.DataFrame({"ibge": TOWNS, "nome": ["A", "B", "C"], "lat": [-30.0, -29.0, -28.0],
                         "lon": [-51.0, -52.0, -53.0], "area_km2": 100.0, "populacao": [1000, 5000, 90000],
                         "regiao_imediata": ["R1", "R1", "R2"]})


def artifact(series, tw, grid):
    cols = feat.RAIN_FEATURES + feat.RELATIVE_FEATURES
    quantiles = feat.fit_quantiles(series, str(series.index[-1].date()))
    frame = feat.build(series, tw, grid, quantiles)
    y = (frame["p_3d"] > frame["p_3d"].quantile(0.97)).astype(int)
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(frame[cols].to_numpy("float32"), y)
    score = model.predict_proba(frame[cols].to_numpy("float32"))[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(score, y)
    thresholds = {"alertas_0.5pct": float(np.quantile(score, 0.995)), "alertas_2pct": float(np.quantile(score, 0.98)),
                  "alertas_5pct": float(np.quantile(score, 0.95))}
    return {"versao": "t-1", "rotulo": "estrito", "familia": "logistica", "parametros": {}, "colunas": cols,
            "modelo": model, "calibrador": calibrator, "limiares": thresholds, "quantis": quantiles,
            "treinado_desde": "2017-01-01", "treinado_ate": "2026-10-31", "sklearn": __import__("sklearn").__version__}


def series(days=DAYS, seed=3):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.gamma(0.4, 8, size=(len(days), len(TOWNS))), index=days, columns=TOWNS)


def history():
    """Two years of training rain, the same kind as the 43-day operational series."""
    return series(pd.date_range("2024-01-01", periods=700), seed=11)


def test_estimates_cover_the_issue_day_and_the_next_two():
    tw, s = towns(), series()
    grid = pd.DataFrame({"ibge": TOWNS, "altitude_m": [10.0, 300.0, 700.0]})
    art = artifact(history(), tw, grid)
    est, missing = forecast.estimate(art, s, tw, grid, pd.Timestamp("2026-11-08"))
    assert missing == [] and len(est) == 9 and set(est["horizonte_dias"]) == {0, 1, 2}
    assert est["probabilidade"].between(0, 1).all() and set(est["classe"]) <= set(forecast.CLASSES)


def test_a_storm_in_the_forecast_raises_the_class_of_that_municipality_only():
    tw, base = towns(), series()
    grid = pd.DataFrame({"ibge": TOWNS, "altitude_m": [10.0, 300.0, 700.0]})
    art = artifact(history(), tw, grid)
    stormy = base.copy()
    stormy.loc["2026-11-09":, "4300002"] = 180.0  # 180 mm/day forecast for tomorrow onwards
    est, _ = forecast.estimate(art, stormy, tw, grid, pd.Timestamp("2026-11-08"))
    storm = est[(est["ibge"] == "4300002") & (est["horizonte_dias"] >= 1)]
    assert len(storm) == 2 and (storm["classe"] == "alto").all()
    assert (est[est["ibge"] == "4300001"]["classe"] == "baixo").all()


def test_a_municipality_with_a_missing_forecast_day_gets_no_estimate():
    tw, s = towns(), series()
    grid = pd.DataFrame({"ibge": TOWNS, "altitude_m": [10.0, 300.0, 700.0]})
    art = artifact(history(), tw, grid)
    broken = s.copy()
    broken.loc["2026-11-10", "4300003"] = np.nan
    est, missing = forecast.estimate(art, broken, tw, grid, pd.Timestamp("2026-11-08"))
    assert missing == ["4300003"] and "4300003" not in set(est["ibge"])


def test_estimate_ignores_everything_after_the_horizon():
    """Rain after the third day cannot exist at issue time; the estimate must not depend on it."""
    tw = towns()
    s = series()
    grid = pd.DataFrame({"ibge": TOWNS, "altitude_m": [10.0, 300.0, 700.0]})
    art = artifact(history(), tw, grid)
    longer = pd.concat([s, pd.DataFrame(500.0, index=pd.date_range("2026-11-11", periods=3), columns=TOWNS)])
    a, _ = forecast.estimate(art, s, tw, grid, pd.Timestamp("2026-11-08"))
    b, _ = forecast.estimate(art, longer, tw, grid, pd.Timestamp("2026-11-08"))
    assert np.allclose(a["pontuacao"], b["pontuacao"])


def test_classify_uses_the_stored_thresholds():
    thresholds = {"alertas_0.5pct": 0.8, "alertas_2pct": 0.5, "alertas_5pct": 0.2}
    assert list(forecast.classify(np.array([0.1, 0.5, 0.79, 0.8, 0.99]), thresholds)) == [
        "baixo", "atencao", "atencao", "alto", "alto"]


def test_a_scikit_learn_mismatch_is_refused(tmp_path):
    path = tmp_path / "m.joblib"
    joblib.dump({"sklearn": "0.0.1"}, path)
    with pytest.raises(RuntimeError, match="scikit-learn"):
        forecast.load_artifact(path)
