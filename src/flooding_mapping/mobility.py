"""Urban mobility lost along a 24 h rain scale (up to 45 mm).

For each rain level, documented blockages and model hotspots close (see
scenarios.rain_scenario_rows); the measure is the population of the city each
origin reaches within the time limit, by mode. Mobility lost for a mode is the
population-weighted drop in people reachable:

    1 - sum(pop_o * reach_s(o)) / sum(pop_o * reach_0(o))
"""

import argparse
import json

import geopandas as gpd
import pandas as pd

from .config import load_config, resolve
from .metrics import losses, mobility_lost

MODE_NAMES = {"walk": "A pé", "transit": "Ônibus", "car": "Carro"}


def curve_plot(curve: pd.DataFrame, threshold: float, path) -> None:
    """Mobility lost (%) by rain level, one line per mode and factor."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"walk": "#2E8B78", "transit": "#1F6FB2", "car": "#C62828"}
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for (mode, factor), group in curve.groupby(["mode", "factor"]):
        group = group.sort_values("rain_24h_mm")
        # Closures are piecewise constant between computed rain levels: draw steps.
        ax.plot(group["rain_24h_mm"], 100 * group["mobility_lost"], marker="o", drawstyle="steps-post",
                color=colors[mode], linestyle="-" if factor == 1 else "--",
                label=f"{MODE_NAMES[mode]} (fator {factor:g})")
    ax.axvline(threshold, color="0.6", linewidth=1, linestyle=":")
    ax.text(threshold, ax.get_ylim()[1] * 0.95, f" primeiros bloqueios\n registrados ({threshold:g} mm)",
            fontsize=8, color="0.35", va="top")
    ax.set_xlabel("Chuva acumulada em 24 h (mm)")
    ax.set_ylabel("Mobilidade perdida (%)")
    ax.set_title("Quanto da cidade deixa de ser alcançável em 30 minutos")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mobilidade perdida na escala de chuva (até 45 mm/24h)")
    parser.add_argument("--modes", nargs="+", default=None)
    args = parser.parse_args()
    from .accessibility import BASELINE_TABLE, SCENARIO_DIR, accessibility_map, run_baseline, run_scenarios
    from .network import load_or_build_segments
    from .scenarios import blockage_count_fit, load_events, load_scenarios, rain_scenario_rows

    config = load_config()
    modes = args.modes or config["accessibility"]["modos"]
    paths = config["paths"]
    tables, qa, interim = resolve(paths["tables"]), resolve(paths["qa"]), resolve(paths["interim"])
    calibration = json.loads((qa / "rain_calibration.json").read_text())
    events = load_events(resolve(paths["events"]) / "events.csv")
    fit = blockage_count_fit(pd.DataFrame(calibration["per_date"]), events)
    threshold = calibration["thresholds"]["medio_total_24h_mm"]

    segments = load_or_build_segments(interim / "poa.osm.pbf", interim / "segments.parquet",
                                      config["crs_metric"])
    scores = gpd.read_parquet(tables / "susceptibility.parquet")
    # The closure set changes exactly at the threshold, so it is computed as a step too.
    config["mobility"]["chuva_24h_mm"] = sorted({*config["mobility"]["chuva_24h_mm"], threshold})
    rows = rain_scenario_rows(events, segments, scores, fit, threshold, config)

    # Register the closure sets in scenarios.csv (replacing earlier rain rows).
    scenarios_path = resolve(paths["events"]) / "scenarios.csv"
    registry = load_scenarios(scenarios_path)
    registry = registry[~registry["scenario_id"].str.startswith("S-C")]
    pd.concat([registry, rows[registry.columns]], ignore_index=True).to_csv(scenarios_path, index=False)

    # Identical closure sets are computed once.
    canonical = rows.groupby("affected_edge_ids")["scenario_id"].transform("first")
    rows["computed_as"] = canonical

    baseline_path = tables / BASELINE_TABLE
    baseline = pd.read_parquet(baseline_path) if baseline_path.exists() else run_baseline(config, modes)
    run_scenarios(config, sorted(set(canonical)), modes)

    origins = gpd.read_parquet(resolve(paths["processed"]) / "origins.parquet")
    population = origins.set_index("origin_id")["population"]
    curve, per_origin = [], []
    for factor in config["mobility"]["fatores_precariedade"]:
        for rain in config["mobility"]["chuva_24h_mm"]:
            match = rows[(rows["rain_24h_mm"] == rain) & (rows["factor"] == factor)]
            if match.empty:  # below the threshold: nothing closes
                for mode in modes:
                    curve.append({"rain_24h_mm": rain, "factor": factor, "mode": mode, "mobility_lost": 0.0,
                                  "origins_with_loss": 0, "population_with_loss": 0.0,
                                  "max_origin_loss": 0.0, "population_losing_10pct": 0.0,
                                  "extra_points": 0, "scenario_id": None})
                continue
            row = match.iloc[0]
            result = pd.read_parquet(tables / SCENARIO_DIR / f"{row['computed_as']}.parquet")
            table = losses(baseline, result.assign(scenario_id=row["scenario_id"]))
            per_origin.append(table)
            for item in mobility_lost(table, population).to_dict(orient="records"):
                item.pop("scenario_id")
                curve.append({"rain_24h_mm": rain, "factor": factor, **item,
                              "extra_points": int(row["extra_points"]), "scenario_id": row["scenario_id"]})
    curve = pd.DataFrame(curve)
    curve.to_csv(tables / "mobility_curve.csv", index=False)
    per_origin = pd.concat(per_origin, ignore_index=True)
    per_origin.to_parquet(tables / "mobility_losses.parquet", index=False)
    curve_plot(curve, threshold, resolve(paths["maps"]) / "mobility_curve.png")
    for scenario_id in per_origin["scenario_id"].unique():
        if scenario_id.startswith("S-C45-"):
            accessibility_map(per_origin[per_origin["scenario_id"] == scenario_id], config,
                              resolve(paths["maps"]) / f"mobility_loss_{scenario_id}.png",
                              column="P", cmap="Reds", vmin=0, vmax=0.5,
                              title=f"Parcela da cidade alcançável perdida (P) — {scenario_id}")

    total_pop = float(population[origins["has_population"].to_numpy()].sum())
    reach = baseline[baseline["status"] == "ok"].assign(pop=lambda f: f["origin_id"].map(population))
    share = {mode: round(float((g["pop"] * g["reachable_weight"]).sum() / (g["pop"].sum() * total_pop)), 4)
             for mode, g in reach.groupby("mode")}
    report = {
        "measure": "população da cidade alcançável em até "
                   f"{config['accessibility']['limite_min']} min, ponderada pela população de origem",
        "baseline_share_of_city_reachable": share,
        "threshold_24h_mm": threshold, "fit": fit,
        "scenarios": rows.drop(columns=["affected_edge_ids"]).to_dict(orient="records"),
        "curve": curve.round(4).to_dict(orient="records"),
    }
    (qa / "mobility_run.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=float) + "\n",
                                          encoding="utf-8")
    pivot = curve.pivot_table(index=["factor", "rain_24h_mm"], columns="mode", values="mobility_lost")
    print("Parcela da cidade alcançável na linha de base:", share)
    print((100 * pivot).round(2).to_string())


if __name__ == "__main__":
    main()
