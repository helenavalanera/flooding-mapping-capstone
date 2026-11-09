"""Train, compare and select the municipal trigger model.

Protocol (see ``evaluation.splits`` for the dates)
    1. Variable sets are compared on the validation years with a fixed gradient-boosting
       model; the smallest set within ``TOLERANCE`` (relative) PR-AUC of the best wins.
    2. Hyperparameters of each family are tuned on the validation years only.
    3. The family is the simplest one within ``TOLERANCE`` of the best PR-AUC. It is called
       *validated* only if it passes three independent checks, all measured before the test
       years: it beats the best baseline by ``MARGIN`` (relative) in validation PR-AUC; it beats
       the best baseline in at least ``WIN_SHARE`` of the rolling-origin years; and it catches at
       least as many out-of-sample events as the best baseline with the same alert budget.
       Otherwise it is reported as experimental and the baseline stays the reference.
    4. A rolling origin (train on the past, predict one year, 2020-2026) gives out-of-sample
       scores. Those of 2020-2024 fit the probability calibration (isotonic) and the
       operating thresholds; the test years are never used for either.
    5. The test years (2025 on) are scored once, by a model trained on everything before them.
    6. Place generalization: train on four fifths of the municipalities, test on the rest.
    7. The operational trigger is the validated model; if none passes the gate it is the best
       rainfall rule (by events caught out of sample), calibrated the same way, and the model is
       kept in the card as experimental. Either is refit/applied on all usable rows.

Training uses all positives and ``NEG_PER_POS`` random negatives per positive (speed and
class balance); evaluation always uses every row, with the natural prevalence, and the
calibration brings the probabilities back to that scale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone

import geopandas as gpd
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from ..config import resolve
from ..datasets import gatilho as dataset
from ..evaluation import metrics, splits
from ..features import weather as feat
from ..ingestion import s2id
from ..ingestion import weather as rain_source
from .rules import RuleScorer

SEED = 20261108
NEG_PER_POS = 50
CLIMATOLOGY_UNTIL = "2019-12-31"
TOLERANCE = 0.10  # relative: PR-AUC is tiny at this prevalence, so absolute gaps mean nothing
MARGIN = 0.10
WIN_SHARE = 0.6
GATE_BUDGET = 0.02
ROLLING_YEARS = range(2020, 2027)
CALIBRATION_YEARS = range(2020, 2025)
LABELS = {"estrito": s2id.HYDRO_STRICT, "amplo": s2id.HYDRO_BROAD}
FEATURE_SETS = {
    "chuva": feat.RAIN_FEATURES,
    "chuva+estacao": feat.RAIN_FEATURES + feat.SEASON_FEATURES,
    "chuva+relativa": feat.RAIN_FEATURES + feat.RELATIVE_FEATURES,
    "chuva+regional": feat.RAIN_FEATURES + feat.RELATIVE_FEATURES + feat.REGIONAL_FEATURES,
    "completo": feat.RAIN_FEATURES + feat.SEASON_FEATURES + feat.RELATIVE_FEATURES
    + feat.REGIONAL_FEATURES + feat.TERRITORY_FEATURES,
}
GRID = {
    "logistica": [{"C": c} for c in (0.01, 0.1, 1.0)],
    "hgb": [{"learning_rate": lr, "max_depth": d, "min_samples_leaf": 100}
            for lr in (0.05, 0.1) for d in (3, 5)],
    "rf": [{"min_samples_leaf": m} for m in (20, 100)],
}
SIMPLICITY = {"logistica": 0, "hgb": 1, "rf": 2}
ABLATION_PARAMS = {"learning_rate": 0.1, "max_depth": 5, "min_samples_leaf": 100}
BASELINE_PARAMS = {"C": 0.1}
# The rainfall rules that can take over when no learned model passes the gate.
RULES = {"regra_p3d": "p_3d", "regra_rel_p3d": "rel_p3d"}
BASELINES = {
    "prior": lambda f: np.zeros(len(f)),
    "regra_p3d": lambda f: f["p_3d"].to_numpy(dtype=float),
    "regra_rel_p3d": lambda f: f["rel_p3d"].to_numpy(dtype=float),
}


# Rainfall can only raise the risk: the trees are told so (monotonic constraints) and the logistic
# model sees rainfall on a log scale. Flexible models trained up to 2022 cannot extrapolate to
# the record rain of 2023, and a function that may fall as rain rises ranks the extremes badly.
RAINFALL = set(feat.RAIN_FEATURES + feat.RELATIVE_FEATURES + feat.REGIONAL_FEATURES)


def make_model(family: str, params: dict, cols: list[str], seed: int = SEED):
    rain_idx = [i for i, c in enumerate(cols) if c in RAINFALL]
    if family == "logistica":
        log = ColumnTransformer([("log", FunctionTransformer(np.log1p), rain_idx)], remainder="passthrough")
        return make_pipeline(log, StandardScaler(), LogisticRegression(max_iter=2000, random_state=seed, **params))
    if family == "hgb":
        monotone = [1 if c in RAINFALL else 0 for c in cols]
        return HistGradientBoostingClassifier(max_iter=300, l2_regularization=1.0, monotonic_cst=monotone,
                                              random_state=seed, **params)
    if family == "rf":
        return RandomForestClassifier(n_estimators=200, max_features="sqrt", n_jobs=-1, random_state=seed, **params)
    raise ValueError(f"unknown model family: {family}")


def training_rows(frame: pd.DataFrame, mask: np.ndarray, seed: int = SEED) -> np.ndarray:
    """Row numbers: every positive plus ``NEG_PER_POS`` random negatives per positive."""
    rng = np.random.default_rng(seed)
    y = frame["y"].to_numpy()
    positives, negatives = np.flatnonzero(mask & (y == 1)), np.flatnonzero(mask & (y == 0))
    keep = rng.choice(negatives, size=min(len(negatives), NEG_PER_POS * len(positives)), replace=False)
    return np.sort(np.concatenate([positives, keep]))


def fit(frame: pd.DataFrame, mask: np.ndarray, family: str, params: dict, cols: list[str]):
    rows = training_rows(frame, mask)
    return make_model(family, params, cols).fit(frame.iloc[rows][cols].to_numpy("float32"),
                                                frame["y"].to_numpy()[rows])


def predict(model, frame: pd.DataFrame, mask: np.ndarray, cols: list[str]) -> np.ndarray:
    return model.predict_proba(frame.loc[mask, cols].to_numpy("float32"))[:, 1]


def ablate(frame: pd.DataFrame, masks: dict) -> tuple[pd.DataFrame, str]:
    """Compare variable sets with one fixed model; keep the smallest within the tolerance."""
    rows = []
    for name, cols in FEATURE_SETS.items():
        model = fit(frame, masks["train"], "hgb", ABLATION_PARAMS, cols)
        score = predict(model, frame, masks["val"], cols)
        rows.append({"conjunto": name, "n_variaveis": len(cols),
                     **metrics.ranking(frame.loc[masks["val"], "y"].to_numpy(), score)})
    table = pd.DataFrame(rows)
    ok = table[table["pr_auc"] >= table["pr_auc"].max() * (1 - TOLERANCE)]
    return table, ok.sort_values("n_variaveis").iloc[0]["conjunto"]


def tune(frame: pd.DataFrame, masks: dict, cols: list[str], grid: dict = GRID) -> pd.DataFrame:
    """Every family and setting, fitted on train and scored on validation."""
    y_val, rows = frame.loc[masks["val"], "y"].to_numpy(), []
    for family, settings in grid.items():
        for params in settings:
            score = predict(fit(frame, masks["train"], family, params, cols), frame, masks["val"], cols)
            rows.append({"familia": family, "parametros": params, **metrics.ranking(y_val, score)})
    return pd.DataFrame(rows)


def baseline_scores(frame: pd.DataFrame, train: np.ndarray) -> dict:
    """Score functions of every baseline: three rules and a logistic model on rainfall alone."""
    simple = fit(frame, train, "logistica", BASELINE_PARAMS, feat.RAIN_FEATURES)
    scores = dict(BASELINES)
    scores["logistica_chuva"] = lambda f: simple.predict_proba(f[feat.RAIN_FEATURES].to_numpy("float32"))[:, 1]
    return scores


def choose(tuned: pd.DataFrame, baseline_best: float) -> dict:
    """Simplest family within the tolerance of the best, and whether it clears the validation margin."""
    best_by_family = tuned.loc[tuned.groupby("familia")["pr_auc"].idxmax()]
    top = best_by_family["pr_auc"].max()
    tied = best_by_family[best_by_family["pr_auc"] >= top * (1 - TOLERANCE)]
    pick = tied.assign(rank=tied["familia"].map(SIMPLICITY)).sort_values("rank").iloc[0]
    return {"familia": pick["familia"], "parametros": pick["parametros"], "pr_auc_val": float(pick["pr_auc"]),
            "melhor_baseline_pr_auc_val": round(float(baseline_best), 4),
            "passa_margem_validacao": bool(pick["pr_auc"] >= baseline_best * (1 + MARGIN))}


def oof_events(frame: pd.DataFrame, rows: pd.Series, scores: dict[str, np.ndarray], budget: float = GATE_BUDGET) -> dict:
    """Events caught out of sample by each scorer with the same alert budget (``budget`` of the days)."""
    subset = frame.iloc[rows].reset_index(drop=True)
    return {name: metrics.event_recall(subset, s, float(np.quantile(s, 1 - budget)))["recall_eventos"]
            for name, s in scores.items()}


GATE_NAMES = {"margem_pr_auc_na_validacao": "margem de PR-AUC na validação",
              "anos_da_janela_movel_vencidos": "anos da janela móvel vencidos",
              "eventos_fora_da_amostra_no_mesmo_orcamento": "eventos detectados fora da amostra no mesmo orçamento de alertas"}


def validation_gate(decision: dict, by_year: list[dict], events: dict) -> dict:
    """Validated only if the model beats the baselines in three independent ways; says which failed."""
    years = [r for r in by_year if r["ano"] in CALIBRATION_YEARS]
    wins = sum(r["pr_auc_modelo"] > max(r["pr_auc_regra_p3d"], r["pr_auc_regra_rel_p3d"], r["pr_auc_logistica_chuva"]) for r in years)
    best_base = max(v for k, v in events.items() if k != "modelo")
    criteria = {
        "margem_pr_auc_na_validacao": {"passa": decision["passa_margem_validacao"],
                                       "detalhe": f"{decision['pr_auc_val']:.4f} contra {decision['melhor_baseline_pr_auc_val']:.4f} (margem {MARGIN:.0%})"},
        "anos_da_janela_movel_vencidos": {"passa": bool(years) and wins / len(years) >= WIN_SHARE,
                                          "detalhe": f"{wins} de {len(years)} anos (mínimo {WIN_SHARE:.0%})"},
        "eventos_fora_da_amostra_no_mesmo_orcamento": {"passa": events["modelo"] >= best_base,
                                                       "detalhe": f"modelo {events['modelo']:.3f} contra melhor baseline {best_base:.3f} com {GATE_BUDGET:.0%} dos dias em alerta"}}
    failed = [k for k, v in criteria.items() if not v["passa"]]
    decision = {k: v for k, v in decision.items() if k != "passa_margem_validacao"}
    return {**decision, "criterios": criteria,
            "estado": "validado frente aos baselines (validação, janela móvel e eventos)" if not failed
            else "experimental: não passa em " + "; ".join(GATE_NAMES[k] for k in failed)}


def rolling_oof(frame: pd.DataFrame, family: str, params: dict, cols: list[str]) -> pd.DataFrame:
    """Out-of-sample scores of every row of each year, from models trained on the past only
    (the selected model and the logistic baseline, each refit per year)."""
    parts = []
    for year, train, test in splits.rolling_origin(frame, ROLLING_YEARS):
        model = fit(frame, train, family, params, cols)
        simple = fit(frame, train, "logistica", BASELINE_PARAMS, feat.RAIN_FEATURES)
        parts.append(pd.DataFrame({"linha": np.flatnonzero(test), "ano": year,
                                   "score": predict(model, frame, test, cols),
                                   "logistica_chuva": predict(simple, frame, test, feat.RAIN_FEATURES)}))
    return pd.concat(parts, ignore_index=True)


def episode_leakage(frame: pd.DataFrame, masks: dict) -> int:
    """Episodes that have positive rows in more than one of train, validation and test."""
    where = np.select([masks["train"], masks["val"], masks["test"]], [1, 2, 3], default=0)
    positive = (frame["y"].to_numpy() == 1) & (where > 0)
    spread = pd.DataFrame({"episodio": frame["episodio"].to_numpy()[positive], "parte": where[positive]})
    return int((spread.groupby("episodio")["parte"].nunique() > 1).sum())


def error_analysis(frame: pd.DataFrame, score: np.ndarray, threshold: float) -> dict:
    """What the misses and the false alarms look like, to read them operationally."""
    runs = metrics.positive_runs(frame).to_numpy()
    alert = score >= threshold
    event = runs >= 0
    caught = pd.Series(alert[event]).groupby(runs[event]).any()
    days = frame[event].assign(detectado=caught.reindex(runs[event]).to_numpy())
    false_alarm = alert & (frame["y"].to_numpy() == 0)
    near_event = frame.groupby("ibge")["y"].transform(
        lambda s: s.rolling(15, center=True, min_periods=1).max()).to_numpy() == 1
    median = lambda rows: round(float(rows["p_3d"].median()), 1) if len(rows) else None  # noqa: E731
    return {
        "eventos_perdidos": int((~caught).sum()),
        "chuva_3d_mediana_mm_nos_eventos_perdidos": median(days[~days["detectado"]]),
        "chuva_3d_mediana_mm_nos_eventos_detectados": median(days[days["detectado"]]),
        "alarmes_falsos_dias": int(false_alarm.sum()),
        "alarmes_falsos_a_menos_de_7_dias_de_um_evento": round(float((false_alarm & near_event).sum() / max(false_alarm.sum(), 1)), 3),
        "alarmes_falsos_chuva_3d_mediana_mm": median(frame[false_alarm]),
        "municipios_com_alarme_falso": int(frame.loc[false_alarm, "ibge"].nunique()),
    }


def threshold_report(test: pd.DataFrame, score: np.ndarray, thresholds: dict) -> dict:
    """Precision, recall, alert days and events caught at each alert budget, on the test rows."""
    y = test["y"].to_numpy()
    return {name: {**metrics.at_threshold(y, score, t), **metrics.event_recall(test, score, t)}
            for name, t in thresholds.items()}


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Rainfall, municipalities, S2iD records and grid cells, all from ``data/``."""
    rain = rain_source.load()
    towns = gpd.read_parquet(resolve("data/interim/municipios.parquet")).drop(columns="geometry")
    records = pd.read_parquet(resolve("data/interim/s2id_rs.parquet"))
    return rain, towns, records, rain.attrs["grade"]


def build_dataset(label_name: str, rain, towns, records, grid):
    series = feat.wide(rain)
    quantiles = feat.fit_quantiles(series, CLIMATOLOGY_UNTIL)
    features = feat.build(series, towns, grid, quantiles)
    return dataset.build(features, records, LABELS[label_name]), quantiles


def run(label_name: str, quick: bool = False) -> dict:
    """Run the whole protocol for one label definition and write the card and the artifact."""
    rain, towns, records, grid = load_inputs()
    frame, quantiles = build_dataset(label_name, rain, towns, records, grid)
    masks = splits.temporal(frame)
    card = {"rotulo": label_name, "cobrade": list(LABELS[label_name]),
            "dataset": dataset.describe(frame, label_name), "semente": SEED,
            "chuva_em_torno_dos_registros": dataset.rain_profile(feat.wide(rain), records, LABELS[label_name], SEED),
            "vazamento_episodios_entre_particoes": episode_leakage(frame, masks),
            "particoes": {k: {"linhas": int(v.sum()), "positivos": int(frame.loc[v, "y"].sum()),
                              "periodo": [str(frame.loc[v, "data"].min().date()), str(frame.loc[v, "data"].max().date())]}
                          for k, v in masks.items()},
            "ambiente": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                         "numpy": np.__version__, "pandas": pd.__version__}}

    ablation, feature_set = ablate(frame, masks)
    cols = FEATURE_SETS[feature_set]
    tuned = tune(frame, masks, cols, {k: v[:1] for k, v in GRID.items()} if quick else GRID)
    y_val = frame.loc[masks["val"], "y"].to_numpy()
    val_scorers = baseline_scores(frame, masks["train"])
    base_val = {n: metrics.ranking(y_val, fn(frame.loc[masks["val"]])) for n, fn in val_scorers.items()}
    decision = choose(tuned, max(r["pr_auc"] for n, r in base_val.items() if n != "prior"))
    family, params = decision["familia"], decision["parametros"]

    oof = rolling_oof(frame, family, params, cols)
    oof_y = frame["y"].to_numpy()[oof["linha"]]
    base_oof = {n: fn(frame.iloc[oof["linha"]]) for n, fn in BASELINES.items()}
    base_oof["logistica_chuva"] = oof["logistica_chuva"].to_numpy()
    calib_rows = oof["ano"].isin(CALIBRATION_YEARS).to_numpy()
    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(
        oof["score"][calib_rows], oof_y[calib_rows])
    thresholds = metrics.budget_thresholds(oof["score"].to_numpy()[calib_rows])
    base_thresholds = {n: metrics.budget_thresholds(s[calib_rows]) for n, s in base_oof.items() if n != "prior"}

    final_train = masks["train"] | masks["val"]
    scorers = baseline_scores(frame, final_train)  # baselines see the same past as the model
    tested = fit(frame, final_train, family, params, cols)
    raw = predict(tested, frame, masks["test"], cols)
    probability = calibrator.predict(raw)
    test = frame.loc[masks["test"]].reset_index(drop=True)
    y_test = test["y"].to_numpy()
    baseline_test = {n: metrics.ranking(y_test, fn(test)) for n, fn in scorers.items()}
    by_year = []
    for year in ROLLING_YEARS:
        rows = (oof["ano"] == year).to_numpy()
        yy = oof_y[rows]
        if yy.sum() == 0:
            continue
        by_year.append({"ano": year, "positivos": int(yy.sum()),
                        "pr_auc_modelo": metrics.ranking(yy, oof["score"][rows])["pr_auc"],
                        "pr_auc_regra_p3d": metrics.ranking(yy, base_oof["regra_p3d"][rows])["pr_auc"],
                        "pr_auc_regra_rel_p3d": metrics.ranking(yy, base_oof["regra_rel_p3d"][rows])["pr_auc"],
                        "pr_auc_logistica_chuva": metrics.ranking(yy, base_oof["logistica_chuva"][rows])["pr_auc"]})
    calibration_rows = oof.loc[calib_rows, "linha"].to_numpy()
    gate_events = oof_events(frame, calibration_rows, {"modelo": oof["score"].to_numpy()[calib_rows],
                                                       **{n: base_oof[n][calib_rows] for n in base_oof if n != "prior"}})
    decision = validation_gate(decision, by_year, gate_events)
    use_rule = not decision["estado"].startswith("validado")
    rule = max(RULES, key=lambda n: (gate_events[n], base_val[n]["pr_auc"])) if use_rule else None
    blocks = splits.spatial_blocks(towns)
    spatial = []
    for block in sorted(blocks.unique()):
        train, held = splits.spatial_holdout(frame, blocks, block)
        sub = frame.loc[held]
        if sub["y"].sum() == 0:
            continue
        model = fit(frame, train, family, params, cols)
        score = predict(model, frame, held, cols)
        spatial.append({"bloco": int(block), "municipios": int((blocks == block).sum()),
                        "positivos": int(sub["y"].sum()),
                        "pr_auc_modelo": metrics.ranking(sub["y"].to_numpy(), score)["pr_auc"],
                        "pr_auc_regra_p3d": metrics.ranking(sub["y"].to_numpy(), sub["p_3d"].to_numpy(float))["pr_auc"]})

    negatives = np.flatnonzero(y_test == 0)
    sample = np.concatenate([np.flatnonzero(y_test == 1), np.random.default_rng(SEED).choice(
        negatives, min(100_000, len(negatives)), replace=False)])
    importance = permutation_importance(tested, test.iloc[sample][cols].to_numpy("float32"), y_test[sample],
                                        scoring="average_precision", n_repeats=3, random_state=SEED)
    card.update({
        "selecao_de_variaveis": {"ablacao_val": ablation.to_dict("records"), "escolhido": feature_set, "variaveis": cols},
        "ajuste_de_hiperparametros_val": tuned.assign(parametros=tuned["parametros"].map(json.dumps)).to_dict("records"),
        "baselines_val": base_val, "decisao": decision, "eventos_oof_no_orcamento_do_portao": gate_events,
        "limiares_pontuacao_bruta_(oof_2020_2024)": thresholds,
        "probabilidade_calibrada_nos_limiares": {k: round(float(calibrator.predict([v])[0]), 5) for k, v in thresholds.items()},
        "teste_2025_em_diante": {
            "modelo": metrics.ranking(y_test, raw),
            "baselines": baseline_test,
            "calibracao": metrics.calibration(y_test, probability),
            "orcamentos_de_alerta": {"modelo": threshold_report(test, raw, thresholds),
                                     **{n: threshold_report(test, fn(test), base_thresholds[n])
                                        for n, fn in scorers.items() if n != "prior"}},
            "analise_de_erros_no_orcamento_2pct": error_analysis(test, raw, thresholds["alertas_2pct"])},
        "estabilidade_temporal_janela_movel": by_year,
        "generalizacao_espacial_blocos_fora_do_treino": spatial,
        "importancia_por_permutacao_pr_auc": sorted(
            [{"variavel": c, "queda_media": round(float(m), 5), "desvio": round(float(s), 5)}
             for c, m, s in zip(cols, importance.importances_mean, importance.importances_std)],
            key=lambda r: -r["queda_media"]),
    })

    if use_rule:
        op_cols, op_thresholds, op_family, op_params = [RULES[rule]], base_thresholds[rule], "regra", {"coluna": RULES[rule]}
        op_calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(
            base_oof[rule][calib_rows], oof_y[calib_rows])
        tested_model, op_test_score = RuleScorer(0), scorers[rule](test)
    else:
        op_cols, op_thresholds, op_family, op_params = cols, thresholds, family, params
        op_calibrator, tested_model, op_test_score = calibrator, tested, raw
    op_probability = op_calibrator.predict(op_test_score)
    op_budgets = threshold_report(test, op_test_score, op_thresholds)
    card["gatilho_operacional"] = {
        "tipo": "regra" if use_rule else "modelo",
        "descricao": (f"regra de chuva ({'chuva relativa ao percentil 95 local em 3 dias' if rule == 'regra_rel_p3d' else 'chuva acumulada em 3 dias'}), "
                      "calibrada em frequência") if use_rule else f"modelo {family}",
        "regra": rule, "colunas": op_cols, "limiares": op_thresholds,
        "estado": ("regra simples calibrada: o modelo de aprendizado de máquina ficou experimental e não é o gatilho em uso"
                   if use_rule else decision["estado"]),
        "motivo": decision["estado"],
        "desempenho_teste": {**metrics.ranking(y_test, op_test_score), "calibracao": metrics.calibration(y_test, op_probability),
                             "orcamentos": op_budgets}}
    # The trigger that was tested (trained/fitted before 2025), kept for the forecast-skew evaluation.
    tested_artifact = {"modelo": tested_model, "calibrador": op_calibrator, "limiares": op_thresholds, "colunas": op_cols,
                       "quantis": quantiles, "municipios": towns[["ibge", "nome", "lat", "lon", "area_km2", "populacao", "regiao_imediata"]].copy(),
                       "grade": grid[["ibge", "altitude_m"]].copy(), "sklearn": sklearn.__version__,
                       "treinado_ate": str(frame.loc[final_train, "data"].max().date())}
    operational = RuleScorer(0) if use_rule else fit(frame, ~frame["excluido"].to_numpy(), family, params, cols)
    version = f"gatilho-{label_name}-{datetime.now(timezone.utc):%Y%m%d}"
    artifact = {"versao": version, "rotulo": label_name, "familia": op_family, "parametros": op_params,
                "colunas": op_cols, "modelo": operational, "calibrador": op_calibrator, "limiares": op_thresholds,
                "tipo": "regra" if use_rule else "modelo",
                "limiares_orcamento": "pontuação bruta do gatilho; alertas_X = X% dos dias-município (OOF 2020-2024)",
                "quantis": quantiles, "climatologia_ate": CLIMATOLOGY_UNTIL,
                # static inputs of the features, so the published site needs only this file
                "municipios": towns[["ibge", "nome", "lat", "lon", "area_km2", "populacao", "regiao_imediata"]].copy(),
                "grade": grid[["ibge", "altitude_m"]].copy(),
                "treinado_ate": str(frame.loc[~frame["excluido"], "data"].max().date()),
                "treinado_desde": str(frame["data"].min().date()), "sklearn": sklearn.__version__}
    path = resolve(f"artifacts/models/{version}/modelo.joblib")
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    joblib.dump(tested_artifact, path.with_name("modelo_teste.joblib"))
    card["artefato"] = {"versao": version, "caminho_local": str(path.relative_to(resolve("."))),
                        "sha256": sha256(path), "treinado_desde": artifact["treinado_desde"],
                        "treinado_ate": artifact["treinado_ate"], "versionado_no_git": False,
                        "observacao": "o artefato fica fora do git; o cartão registra o hash"}
    out = resolve(f"reports/ml/gatilho_{label_name}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(card, indent=2, ensure_ascii=False, default=str) + "\n")
    resolve("data/processed").mkdir(parents=True, exist_ok=True)
    frame.to_parquet(resolve(f"data/processed/gatilho_{label_name}.parquet"))
    oof.assign(y=oof_y).to_parquet(resolve(f"data/processed/gatilho_{label_name}_oof.parquet"))
    test[["ibge", "data", "y"]].assign(
        score=raw, probabilidade=probability,
        **{n: fn(test) for n, fn in scorers.items() if n != "prior"}).to_parquet(
        resolve(f"data/processed/gatilho_{label_name}_teste.parquet"))
    return card


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the municipal trigger model")
    parser.add_argument("--label", choices=sorted(LABELS), default="estrito")
    parser.add_argument("--quick", action="store_true", help="one setting per family (development)")
    args = parser.parse_args()
    card = run(args.label, args.quick)
    test = card["teste_2025_em_diante"]
    print(json.dumps({"decisao": card["decisao"], "teste_modelo": test["modelo"],
                      "baselines": {k: v["pr_auc"] for k, v in test["baselines"].items()}},
                     ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
