"""Accessibility to health destinations within a travel-time limit."""

import argparse
import datetime as dt
import json
import platform
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .config import load_config, resolve

# Transit trips include walking access, egress and transfers.
MODES = {"walk": ["WALK"], "car": ["CAR"], "transit": ["TRANSIT", "WALK"]}
# Street mode an origin must link to (r5py default radius: 1600 m).
LINK_MODE = {"walk": "WALK", "car": "CAR", "transit": "WALK"}


def classify_accessibility(
    frame: pd.DataFrame,
    travel_time_column: str = "travel_time_minutes",
    threshold_minutes: float = 30,
) -> pd.DataFrame:
    """Add a boolean accessibility flag based on travel time."""
    if travel_time_column not in frame:
        raise ValueError(f"Missing travel-time column: {travel_time_column}")
    result = frame.copy()
    result["is_accessible"] = (
        result[travel_time_column] <= threshold_minutes
    )
    return result


def count_accessible(
    times: pd.DataFrame, origin_ids: pd.Series, limit_min: float, unlinked_ids=()
) -> pd.DataFrame:
    """Count destinations reachable within ``limit_min`` (inclusive) per origin.

    ``times`` has one row per origin-destination pair (``from_id``, ``to_id``,
    ``travel_time``), with NaN for pairs not reachable. Status per origin:
    ``ok`` (a count, possibly 0), ``not_linked`` (origin cannot be linked to
    the street network of the mode) or ``missing`` (no result rows: a
    calculation failure). Only ``ok`` origins get a count; others get <NA>.
    """
    reachable = times["travel_time"].notna() & (times["travel_time"] <= limit_min)
    counts = reachable.groupby(times["from_id"]).sum()
    result = pd.DataFrame({"origin_id": origin_ids.to_numpy()})
    result["n_destinations"] = result["origin_id"].map(counts).astype("Int64")
    result["status"] = "ok"
    result.loc[result["n_destinations"].isna(), "status"] = "missing"
    unlinked = result["origin_id"].isin(set(unlinked_ids))
    result.loc[unlinked, "status"] = "not_linked"
    result.loc[unlinked, "n_destinations"] = pd.NA
    return result


def unlinked_origins(network, origins: gpd.GeoDataFrame, mode: str) -> list[str]:
    """Origin ids that cannot be linked to the street network for ``mode``."""
    import r5py

    snapped = network.snap_to_network(
        origins.geometry.to_crs("EPSG:4326"), street_mode=r5py.TransportMode[LINK_MODE[mode]])
    failed = snapped.isna() | snapped.is_empty
    return origins.loc[failed.to_numpy(), "id"].tolist()


def build_network(osm_pbf: str | Path, gtfs: list[str | Path]):
    """Build an r5py transport network."""
    import r5py

    return r5py.TransportNetwork(str(osm_pbf), [str(g) for g in gtfs])


def travel_times(network, origins: gpd.GeoDataFrame, destinations: gpd.GeoDataFrame,
                 mode: str, config: dict) -> pd.DataFrame:
    """Median travel time (minutes) for all pairs.

    ``max_time`` is the limit plus one minute so that trips of exactly the
    limit are kept; the inclusive cut-off is applied in count_accessible.
    """
    import r5py

    departure = dt.datetime.fromisoformat(
        f"{config['time']['data_referencia']}T{config['time']['horario_partida']}")
    matrix = r5py.TravelTimeMatrix(
        network,
        origins=origins[["id", "geometry"]].to_crs("EPSG:4326"),
        destinations=destinations[["id", "geometry"]].to_crs("EPSG:4326"),
        departure=departure,
        departure_time_window=dt.timedelta(minutes=config["time"]["janela_partida_min"]),
        transport_modes=MODES[mode],
        max_time=dt.timedelta(minutes=config["accessibility"]["limite_min"] + 1),
    )
    return pd.DataFrame(matrix)


def load_inputs(config: dict) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Origins (populated ones, if configured) and non-duplicate destinations."""
    processed = resolve(config["paths"]["processed"])
    origins = gpd.read_parquet(processed / "origins.parquet")
    if config["population"]["excluir_origens_sem_populacao"]:
        origins = origins[origins["has_population"]]
    destinations = gpd.read_parquet(processed / "destinations.parquet")
    destinations = destinations[~destinations["duplicate"]]
    return (origins.rename(columns={"origin_id": "id"}),
            destinations.rename(columns={"dest_id": "id"}))


def accessibility(network, origins, destinations, modes, config, label: str) -> tuple[pd.DataFrame, dict]:
    """Count accessible destinations per origin and mode for one network."""
    limit = config["accessibility"]["limite_min"]
    frames, seconds = [], {}
    for mode in modes:
        started = time.perf_counter()
        times = travel_times(network, origins, destinations, mode, config)
        counts = count_accessible(times, origins["id"], limit,
                                  unlinked_origins(network, origins, mode))
        counts["mode"] = mode
        counts["scenario_id"] = label
        frames.append(counts)
        seconds[mode] = round(time.perf_counter() - started, 1)
    return pd.concat(frames, ignore_index=True), seconds


def run_log(config: dict, seconds: dict, n_origins: int, n_destinations: int) -> dict:
    """Parameters, versions and timings of an accessibility run."""
    import geopandas
    import r5py

    return {
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "data_referencia": config["time"]["data_referencia"],
        "horario_partida": config["time"]["horario_partida"],
        "janela_partida_min": config["time"]["janela_partida_min"],
        "limite_min": config["accessibility"]["limite_min"],
        "percentile": 50,
        "speed_walking_kmh": 3.6,
        "n_origins": n_origins,
        "n_destinations": n_destinations,
        "seconds": seconds,
        "versions": {"python": platform.python_version(), "r5py": r5py.__version__,
                     "geopandas": geopandas.__version__},
    }


def accessibility_map(result: pd.DataFrame, config: dict, path: str | Path, column="n_destinations",
                      title="Destinos de saúde acessíveis em até 30 min (A0)", cmap="viridis",
                      vmin=None, vmax=None) -> None:
    """One panel per mode on a shared colour scale; grey marks origins without a value."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    processed = resolve(config["paths"]["processed"])
    cells = gpd.read_parquet(processed / "origins.parquet")
    area = gpd.read_parquet(processed / "municipality.parquet")
    modes = list(dict.fromkeys(result["mode"]))
    values = result[column].astype("Float64")
    vmin = values.min() if vmin is None else vmin
    vmax = values.max() if vmax is None else vmax
    spacing = config["grid"]["espacamento_m"]
    fig, axes = plt.subplots(1, len(modes), figsize=(5 * len(modes), 7), squeeze=False)
    for ax, mode in zip(axes[0], modes):
        data = cells.merge(result[result["mode"] == mode], on="origin_id")
        data = data.set_geometry(data.buffer(spacing / 2, cap_style="square"))
        area.boundary.plot(ax=ax, color="0.4", linewidth=0.5)
        data[data[column].isna()].plot(ax=ax, color="0.85")
        data[data[column].notna()].astype({column: float}).plot(
            ax=ax, column=column, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(mode)
        ax.set_axis_off()
    mappable = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin, vmax))
    fig.colorbar(mappable, ax=axes[0].tolist(), shrink=0.6)
    fig.suptitle(title)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calcula a linha de base A0 de acessibilidade")
    parser.add_argument("--modes", nargs="+", default=None, choices=sorted(MODES))
    args = parser.parse_args()
    config = load_config()
    modes = args.modes or config["accessibility"]["modos"]
    origins, destinations = load_inputs(config)

    started = time.perf_counter()
    network = build_network(resolve(config["paths"]["interim"]) / "poa.osm.pbf",
                            [resolve(config["sources"]["gtfs"]["destino"])])
    network_seconds = round(time.perf_counter() - started, 1)
    result, seconds = accessibility(network, origins, destinations, modes, config, "baseline")
    seconds["network"] = network_seconds

    tables = resolve(config["paths"]["tables"])
    tables.mkdir(parents=True, exist_ok=True)
    result.to_parquet(tables / "accessibility_baseline.parquet", index=False)
    accessibility_map(result, config, resolve(config["paths"]["maps"]) / "accessibility_baseline.png")
    log = run_log(config, seconds, len(origins), len(destinations))
    log["summary"] = (result.groupby("mode")["n_destinations"]
                      .agg(["mean", "median", "min", "max", lambda s: int((s == 0).sum())])
                      .set_axis(["mean", "median", "min", "max", "zero"], axis=1)
                      .round(2).to_dict(orient="index"))
    log["status"] = result.groupby(["mode", "status"]).size().unstack(fill_value=0).to_dict(
        orient="index")
    path = resolve(config["paths"]["qa"]) / "accessibility_baseline_run.json"
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False, default=float) + "\n",
                    encoding="utf-8")
    print(json.dumps(log, indent=2, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
