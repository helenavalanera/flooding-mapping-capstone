"""Self-contained interactive map (Leaflet) of accessibility, losses and events.

All data is embedded as JSON; external text (OSM names, sources) is inserted in
the page with textContent, never as HTML.
"""

import argparse
import json
import urllib.parse
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .config import load_config, resolve

LEAFLET = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4"
# Own basemap embedded in the page (land from IBGE tracts, main roads from the OSM
# extract): no tile server, so it works from file:// and offline. OSM tiles stay
# available as an option for pages served over http(s) — tile.openstreetmap.org
# blocks requests without a valid Referer, which is the file:// case.
WATER_TRACT = "9"  # CD_SIT: massas de água
ROAD_CLASS = {"motorway": 1, "motorway_link": 1, "trunk": 1, "trunk_link": 1,
              "primary": 2, "primary_link": 2, "secondary": 3, "secondary_link": 3}
CARTO_TILES = "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key="
CARTO_KEY_FILE = "config/carto_api_key.txt"  # git-ignored


def carto_key() -> str | None:
    """CARTO basemap key from $CARTO_API_KEY or the git-ignored key file."""
    import os

    key = os.environ.get("CARTO_API_KEY", "").strip()
    path = resolve(CARTO_KEY_FILE)
    if not key and path.is_file():
        key = path.read_text(encoding="utf-8").strip()
    return key or None


def basemap_js(key: str | None = None) -> str:
    """Basemap script: CARTO (if a key is available) as default, the embedded
    basemap otherwise; both, plus OSM tiles, stay selectable."""
    if not key:
        return BASEMAP_JS
    url = json.dumps(CARTO_TILES + urllib.parse.quote(key, safe=""))
    return BASEMAP_JS.replace("]).addTo(map);\nconst osmTiles", "]);\nconst osmTiles").replace(
        'L.control.layers({"Base própria (offline)": ownBase,',
        f'const cartoTiles = L.tileLayer({url}, {{maxZoom: 20, '
        f'attribution: "© colaboradores do OpenStreetMap, © CARTO"}}).addTo(map);\n'
        f'L.control.layers({{"CARTO Voyager": cartoTiles, "Base própria (offline)": ownBase,')


BASEMAP_JS = """map.createPane("base"); map.getPane("base").style.zIndex = 250;
const ownBase = L.layerGroup([
  L.geoJSON(CONTEXT.land, {pane: "base", interactive: false,
    attribution: "Base: IBGE (setores 2022) e © colaboradores do OpenStreetMap",
    style: {stroke: false, fillColor: css("--land"), fillOpacity: 1}}),
  L.geoJSON(CONTEXT.roads, {pane: "base", interactive: false,
    style: f => ({color: css("--road"), weight: [0, 2.4, 1.6, 1][f.properties.c], opacity: 0.9})}),
]).addTo(map);
const osmTiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 19,
  attribution: "© colaboradores do OpenStreetMap"});
L.control.layers({"Base própria (offline)": ownBase,
                  "OpenStreetMap (requer servidor ou https)": osmTiles}, null, {position: "topright"}).addTo(map);"""
BASE_CSS = """--land:#fbfaf7; --water:#cfe2ee; --road:#c9c3b8;"""
BASE_CSS_DARK = """--land:#2b2b28; --water:#16242e; --road:#5a564f;"""


def water_polygons(config: dict, bbox: tuple) -> gpd.GeoSeries:
    """OSM water areas (lake, rivers) around the city, cached in data/interim.

    Read from the raw regional PBF with osmium's ``smart`` strategy so large
    multipolygons such as Lago Guaíba stay complete (the municipal clip cuts
    them).
    """
    import subprocess

    from pyrosm import OSM

    interim = resolve(config["paths"]["interim"])
    cache = interim / "water.parquet"
    if cache.exists():
        return gpd.read_parquet(cache).geometry
    filtered, local = interim / "water_sul.osm.pbf", interim / "water_poa.osm.pbf"
    subprocess.run(["osmium", "tags-filter", "-O", "-o", str(filtered),
                    str(resolve(config["sources"]["osm"]["destino"])),
                    "nwr/natural=water", "nwr/water", "nwr/waterway=riverbank"],
                   check=True, capture_output=True)
    subprocess.run(["osmium", "extract", "-O", "--strategy", "smart", "--bbox",
                    ",".join(f"{v:.4f}" for v in bbox), "-o", str(local), str(filtered)],
                   check=True, capture_output=True)
    water = OSM(str(local)).get_data_by_custom_criteria(custom_filter={"natural": ["water"]},
                                                         keep_nodes=False)
    water = gpd.GeoDataFrame(geometry=water.geometry.make_valid(), crs=water.crs)
    water.to_parquet(cache)
    return water.geometry


def context(config: dict) -> dict:
    """Land (IBGE tracts minus OSM water) and main roads around the city."""
    area = gpd.read_parquet(resolve(config["paths"]["processed"]) / "municipality.parquet")
    bbox_sirgas = tuple(area.buffer(15000).to_crs("EPSG:4674").total_bounds)
    tracts = gpd.read_file(resolve(config["sources"]["ibge_setores"]["destino"]), bbox=bbox_sirgas,
                           columns=["CD_SIT"])
    land = tracts[tracts["CD_SIT"] != WATER_TRACT].to_crs(area.crs).union_all()
    # Neighbouring tracts extend over Lago Guaíba, so water comes from OSM.
    water = water_polygons(config, tuple(area.buffer(15000).to_crs("EPSG:4326").total_bounds))
    land = land.difference(water.to_crs(area.crs).union_all()).simplify(25)
    segments = gpd.read_parquet(resolve(config["paths"]["interim"]) / "segments.parquet")
    major = segments[segments["highway"].isin(ROAD_CLASS)].assign(
        c=lambda f: f["highway"].map(ROAD_CLASS))
    roads = major.dissolve(by=["c"]).reset_index()[["c", "geometry"]]
    roads["geometry"] = roads.geometry.line_merge().simplify(10)
    return {"land": _features(gpd.GeoDataFrame(geometry=[land], crs=area.crs), []),
            "roads": _features(roads, ["c"])}
MODES = ["walk", "car", "transit"]
DIGITS = 5


def _features(frame: gpd.GeoDataFrame, columns: list[str]) -> dict:
    """GeoJSON (WGS84, rounded coordinates) with the selected properties."""
    frame = frame.to_crs("EPSG:4326")
    frame = frame.set_geometry(frame.geometry.set_precision(10**-DIGITS))
    data = json.loads(frame[columns + ["geometry"]].to_json(na="null", drop_id=True))
    return {"type": "FeatureCollection", "features": data["features"]}


def _int_or_none(value):
    return None if pd.isna(value) else int(value)


def build_data(config: dict) -> dict:
    """Collect every layer of the map from the pipeline outputs."""
    processed = resolve(config["paths"]["processed"])
    tables = resolve(config["paths"]["tables"])
    spacing = config["grid"]["espacamento_m"]

    origins = gpd.read_parquet(processed / "origins.parquet")
    baseline = pd.read_parquet(tables / "accessibility_baseline.parquet")
    a0 = baseline.pivot(index="origin_id", columns="mode", values="n_destinations")
    origins = origins[origins["origin_id"].isin(a0.index)].reset_index(drop=True)
    cells = origins.set_geometry(origins.buffer(spacing / 2, cap_style="square"))
    cells["population"] = cells["population"].round(0).astype(int)
    for mode in MODES:
        cells[f"a0_{mode}"] = cells["origin_id"].map(a0[mode]).map(_int_or_none)
    order = cells["origin_id"]

    losses = pd.read_parquet(tables / "losses.parquet")
    scenario_table = pd.read_csv(resolve(config["paths"]["events"]) / "scenarios.csv")
    computed = sorted(losses["scenario_id"].unique())
    scenarios, segments_by_scenario = {}, {}
    for scenario_id in computed:
        subset = losses[losses["scenario_id"] == scenario_id]
        row = scenario_table.set_index("scenario_id").loc[scenario_id]
        scenarios[scenario_id] = {
            "event_id": row["event_id"], "radius_m": int(row["radius_m"]),
            "status": row["validation_status"],
            "L": {mode: [_int_or_none(v) for v in order.map(
                subset[subset["mode"] == mode].set_index("origin_id")["L"])] for mode in MODES},
        }
        for segment_id in str(row["affected_edge_ids"]).split(";"):
            segments_by_scenario.setdefault(segment_id, []).append(scenario_id)

    segments = gpd.read_parquet(resolve(config["paths"]["interim"]) / "segments.parquet")
    blocked = segments[segments["segment_id"].isin(segments_by_scenario)].copy()
    blocked["scenarios"] = blocked["segment_id"].map(segments_by_scenario)

    events = pd.read_csv(resolve(config["paths"]["events"]) / "events.csv")
    events = events.dropna(subset=["latitude", "longitude"])
    events = gpd.GeoDataFrame(events, geometry=gpd.points_from_xy(
        events["longitude"], events["latitude"]), crs="EPSG:4326")

    destinations = gpd.read_parquet(processed / "destinations.parquet")
    destinations = destinations[~destinations["duplicate"]]

    susceptibility = gpd.read_parquet(tables / "susceptibility.parquet")
    top = susceptibility[susceptibility["percentile"] >= config["susceptibility"]["alerta_percentil"]]
    # susceptibility.parquet stores segment midpoints; draw the segment lines.
    top = segments[["segment_id", "geometry"]].merge(
        top[["segment_id", "percentile"]].assign(percentile=top["percentile"].round(3)),
        on="segment_id")

    area = gpd.read_parquet(processed / "municipality.parquet")
    return {
        "cells": _features(cells, ["origin_id", "population"] + [f"a0_{m}" for m in MODES]),
        "scenarios": scenarios,
        "blocked": _features(blocked, ["segment_id", "scenarios"]),
        "events": _features(events, ["event_id", "event_date", "event_type", "location_text",
                                     "confidence", "verification_status", "source_url"]),
        "destinations": _features(destinations, ["name", "category"]),
        "susceptibility": _features(top, ["percentile"]),
        "boundary": _features(gpd.GeoDataFrame(geometry=area.boundary, crs=area.crs), []),
        "context": context(config),
        "meta": {
            "data_referencia": config["time"]["data_referencia"],
            "horario_partida": config["time"]["horario_partida"],
            "limite_min": config["accessibility"]["limite_min"],
            "alerta_percentil": config["susceptibility"]["alerta_percentil"],
        },
    }


def embed_json(data: dict) -> str:
    """JSON safe to place inside a <script> element."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build_html(data: dict) -> str:
    return (TEMPLATE.replace("__LEAFLET__", LEAFLET).replace("__BASEMAP__", basemap_js(carto_key()))
            .replace("__BASE_CSS_DARK__", BASE_CSS_DARK).replace("__BASE_CSS__", BASE_CSS)
            .replace("__DATA__", embed_json(data)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera o mapa interativo em HTML")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    config = load_config()
    output = Path(args.output) if args.output else (
        resolve(config["paths"]["maps"]) / "mapa_interativo.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(build_data(config)), encoding="utf-8")
    print(output, f"{output.stat().st_size / 1e6:.1f} MB")


TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flooding Mapping</title>
<link rel="stylesheet" href="__LEAFLET__/leaflet.min.css">
<style>
:root { --bg:#f7f7f5; --panel:#ffffff; --text:#1d1d1b; --muted:#5f5f5a; --line:#d9d9d4;
        --accent:#b2182b; --na:#c9c9c4; __BASE_CSS__ }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --bg:#151514; --panel:#22221f; --text:#ecece8;
        --muted:#a5a59e; --line:#3a3a36; --accent:#ef6f6c; --na:#55554f; __BASE_CSS_DARK__ } }
:root[data-theme="dark"] { --bg:#151514; --panel:#22221f; --text:#ecece8; --muted:#a5a59e;
        --line:#3a3a36; --accent:#ef6f6c; --na:#55554f; __BASE_CSS_DARK__ }
* { box-sizing:border-box; }
html, body { margin:0; height:100%; background:var(--bg); color:var(--text);
  font:14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
#app { display:flex; height:100%; }
#panel { width:330px; flex:none; overflow:auto; padding:16px; background:var(--panel);
  border-right:1px solid var(--line); }
#map { flex:1; background:var(--water); }
h1 { font-size:17px; margin:0 0 4px; }
.sub { color:var(--muted); font-size:12.5px; margin:0 0 14px; }
label.field { display:block; font-weight:600; font-size:12.5px; margin:12px 0 4px; }
select { width:100%; padding:6px 8px; border:1px solid var(--line); border-radius:6px;
  background:var(--bg); color:var(--text); font:inherit; }
.check { display:flex; gap:8px; align-items:center; margin:6px 0; font-size:13px; }
.legend { margin-top:14px; font-size:12.5px; }
.legend .row { display:flex; align-items:center; gap:8px; margin:3px 0; }
.swatch { width:18px; height:12px; border-radius:2px; flex:none; border:1px solid var(--line); }
.note { margin-top:14px; padding-top:10px; border-top:1px solid var(--line);
  color:var(--muted); font-size:12px; }
.popup dt { font-weight:600; } .popup dd { margin:0 0 4px; }
.popup a { color:var(--accent); }
@media (max-width: 720px) {
  #app { flex-direction:column; }
  #panel { width:100%; max-height:45%; border-right:0; border-bottom:1px solid var(--line); }
}
</style>
</head>
<body>
<div id="app">
  <aside id="panel">
    <h1>Flooding Mapping</h1>
    <p class="sub" id="subtitle"></p>
    <label class="field" for="indicator">Indicador</label>
    <select id="indicator">
      <option value="a0">Acessibilidade de base (A0)</option>
      <option value="L">Perda absoluta no cenário (L)</option>
      <option value="P">Perda relativa no cenário (P)</option>
    </select>
    <label class="field" for="mode">Modo</label>
    <select id="mode">
      <option value="walk">A pé</option>
      <option value="car">Carro</option>
      <option value="transit">Ônibus</option>
    </select>
    <label class="field" for="scenario">Cenário</label>
    <select id="scenario"></select>
    <div style="margin-top:12px">
      <label class="check"><input type="checkbox" id="showEvents" checked> Eventos de bloqueio</label>
      <label class="check"><input type="checkbox" id="showBlocked" checked> Trechos bloqueados do cenário</label>
      <label class="check"><input type="checkbox" id="showDest"> Destinos de saúde</label>
      <label class="check"><input type="checkbox" id="showSusc"> Suscetibilidade (topo)</label>
    </div>
    <div class="legend" id="legend"></div>
    <p class="note" id="note"></p>
  </aside>
  <div id="map"></div>
</div>
<script src="__LEAFLET__/leaflet.min.js"></script>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const MODES = {walk: "a pé", car: "carro", transit: "ônibus"};
const SCALES = {
  a0: {bins: [0, 1, 6, 21, 51, 101, 151], labels: ["0", "1–5", "6–20", "21–50", "51–100", "101–150", "> 150"],
       colors: ["#f7f4f0", "#d6e6f0", "#a6cbe3", "#6aa8d1", "#3a82bc", "#1d5a9a", "#0b3369"]},
  L:  {bins: [0, 1, 2, 3, 6, 11], labels: ["0", "1", "2", "3–5", "6–10", "> 10"],
       colors: ["#f7f4f0", "#fdd9c4", "#fbab8a", "#f2715a", "#d1352e", "#8f0c1f"]},
  P:  {bins: [0, 0.0001, 0.10, 0.25, 0.50, 0.75], labels: ["0%", "≤ 10%", "10–25%", "25–50%", "50–75%", "> 75%"],
       colors: ["#f7f4f0", "#fdd9c4", "#fbab8a", "#f2715a", "#d1352e", "#8f0c1f"]},
};
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const $ = id => document.getElementById(id);
const meta = DATA.meta;
$("subtitle").textContent = `Destinos de saúde alcançáveis em até ${meta.limite_min} min · partida ${meta.horario_partida} de ${meta.data_referencia} (GTFS histórico)`;

const map = L.map("map", {preferCanvas: true});
const CONTEXT = DATA.context;
__BASEMAP__
const boundary = L.geoJSON(DATA.boundary, {style: {color: "#55554f", weight: 1, fill: false}}).addTo(map);
map.fitBounds(boundary.getBounds());

const scenarioIds = Object.keys(DATA.scenarios);
for (const id of scenarioIds) {
  const s = DATA.scenarios[id];
  const option = document.createElement("option");
  option.value = id;
  option.textContent = `${id} (${s.radius_m} m, ${s.status})`;
  $("scenario").appendChild(option);
}
// Initial view: hash state (#indicador=L&modo=car&cenario=...) or the main finding.
const hash = new URLSearchParams(location.hash.slice(1));
const pick = (value, allowed, fallback) => allowed.includes(value) ? value : fallback;
$("indicator").value = pick(hash.get("indicador"), ["a0", "L", "P"], "L");
$("mode").value = pick(hash.get("modo"), Object.keys(MODES), "car");
$("scenario").value = pick(hash.get("cenario"), scenarioIds,
  scenarioIds.includes("S-D20250618-100-all") ? "S-D20250618-100-all" : scenarioIds[0]);

const index = new Map(DATA.cells.features.map((f, i) => [f.properties.origin_id, i]));
function value(props, indicator, mode, scenario) {
  const a0 = props[`a0_${mode}`];
  if (indicator === "a0") return a0;
  const loss = DATA.scenarios[scenario].L[mode][index.get(props.origin_id)];
  if (indicator === "L") return loss;
  return (loss === null || !a0) ? null : loss / a0;
}
function color(v, scale) {
  if (v === null || v === undefined) return css("--na");
  let c = scale.colors[0];
  scale.bins.forEach((b, i) => { if (v >= b) c = scale.colors[i]; });
  return c;
}
function addRow(list, term, text) {
  const dt = document.createElement("dt"); dt.textContent = term;
  const dd = document.createElement("dd"); dd.textContent = text;
  list.append(dt, dd);
}
function cellPopup(props) {
  const state = current();
  const box = document.createElement("dl"); box.className = "popup";
  addRow(box, "Célula", props.origin_id);
  addRow(box, "População (estimada)", props.population.toLocaleString("pt-BR"));
  for (const m of Object.keys(MODES)) {
    const a0 = props[`a0_${m}`];
    const l = DATA.scenarios[state.scenario].L[m][index.get(props.origin_id)];
    const text = a0 === null ? "sem ligação à rede" :
      `A0 = ${a0}` + (l === null ? "" : ` · L = ${l}` + (a0 > 0 ? ` (${Math.round(100 * l / a0)}%)` : ""));
    addRow(box, MODES[m], text);
  }
  return box;
}
const cells = L.geoJSON(DATA.cells, {
  style: () => ({weight: 0, fillOpacity: 0.72}),
  onEachFeature: (f, layer) => layer.bindPopup(() => cellPopup(f.properties)),
}).addTo(map);

const blocked = L.geoJSON(DATA.blocked, {style: {color: "#111", weight: 3}});
const events = L.geoJSON(DATA.events, {
  pointToLayer: (f, ll) => L.circleMarker(ll, {radius: 6, color: "#111", weight: 1.5,
    fillColor: f.properties.event_type.includes("total") ? "#e31a1c" : "#fd8d3c", fillOpacity: 1}),
  onEachFeature: (f, layer) => layer.bindPopup(() => {
    const p = f.properties, box = document.createElement("dl"); box.className = "popup";
    addRow(box, p.event_id, p.location_text);
    addRow(box, "Data", p.event_date);
    addRow(box, "Tipo", p.event_type.replaceAll("_", " "));
    addRow(box, "Confiança", `${p.confidence} · ${p.verification_status.replaceAll("_", " ")}`);
    const link = document.createElement("a");
    link.href = p.source_url; link.target = "_blank"; link.rel = "noopener"; link.textContent = "Fonte";
    box.append(link);
    return box;
  }),
}).addTo(map);
const destinations = L.geoJSON(DATA.destinations, {
  pointToLayer: (f, ll) => L.circleMarker(ll, {radius: 4, color: "#fff", weight: 1,
    fillColor: {hospital: "#1b7837", clinic: "#5aae61", doctors: "#a6dba0"}[f.properties.category], fillOpacity: 1}),
  onEachFeature: (f, layer) => layer.bindPopup(() => {
    const box = document.createElement("dl"); box.className = "popup";
    addRow(box, f.properties.category, f.properties.name || "(sem nome no OSM)");
    return box;
  }),
});
const susceptibility = L.geoJSON(DATA.susceptibility, {style: {color: "#6a3d9a", weight: 2}});

function current() {
  return {indicator: $("indicator").value, mode: $("mode").value, scenario: $("scenario").value};
}
function render() {
  const state = current(), scale = SCALES[state.indicator];
  cells.eachLayer(layer => {
    const v = value(layer.feature.properties, state.indicator, state.mode, state.scenario);
    // Zero is drawn almost transparent so the basemap stays readable.
    layer.setStyle({fillColor: color(v, scale), fillOpacity: v === 0 ? 0.12 : 0.75});
  });
  history.replaceState(null, "", `#indicador=${state.indicator}&modo=${state.mode}&cenario=${state.scenario}`);
  $("scenario").disabled = state.indicator === "a0" && !$("showBlocked").checked;
  blocked.clearLayers();
  if ($("showBlocked").checked) blocked.addData({type: "FeatureCollection",
    features: DATA.blocked.features.filter(f => f.properties.scenarios.includes(state.scenario))});
  for (const [box, layer] of [["showBlocked", blocked], ["showEvents", events],
                              ["showDest", destinations], ["showSusc", susceptibility]]) {
    if ($(box).checked) layer.addTo(map); else layer.remove();
  }
  const legend = $("legend"); legend.replaceChildren();
  const title = document.createElement("strong");
  title.textContent = {a0: `A0 — ${MODES[state.mode]}`, L: `Perda L — ${MODES[state.mode]}`,
                       P: `Perda relativa P — ${MODES[state.mode]}`}[state.indicator];
  legend.append(title);
  const rows = scale.labels.map((t, i) => [scale.colors[i], t]).concat([[css("--na"), "sem valor"]]);
  for (const [c, t] of rows) {
    const row = document.createElement("div"); row.className = "row";
    const sw = document.createElement("span"); sw.className = "swatch"; sw.style.background = c;
    const label = document.createElement("span"); label.textContent = t;
    row.append(sw, label); legend.append(row);
  }
  const s = DATA.scenarios[state.scenario];
  $("note").textContent = `Cenário ${state.scenario}: eventos ${s.event_id.replaceAll(";", ", ")}; trechos com status "${s.status}" ` +
    `(ainda não validados). Ônibus seguem o GTFS de 2025; variações de até 2 destinos no ônibus ` +
    `estão dentro do ruído de religamento. Suscetibilidade: segmentos acima do percentil ` +
    `${Math.round(meta.alerta_percentil * 100)} — semelhança de terreno com locais já interditados, não previsão de alagamento.`;
}
for (const id of ["indicator", "mode", "scenario", "showEvents", "showBlocked", "showDest", "showSusc"])
  $(id).addEventListener("change", render);
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
