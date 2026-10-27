"""Forecast alert dashboard: location, live rain forecast and segment alert levels.

A static page. In the browser it (1) optionally reads the user's location,
(2) fetches the hourly precipitation forecast from Open-Meteo for a few points
over Porto Alegre and (3) combines rain with the precomputed susceptibility
percentile of each road segment into a deterministic alert level. Levels are
heuristic, calibrated on modelled rain at past reported blockages; they are not
probabilities. Locations outside Porto Alegre are reported as not covered.
"""

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np

from .config import load_config, resolve
from .susceptibility import gtfs_routes
from .webmap import BASE_CSS, BASE_CSS_DARK, LEAFLET, _features, basemap_js, carto_key, context, embed_json

FORECAST_API = "https://api.open-meteo.com/v1/forecast"
CANDIDATE_PERCENTILE = 0.90


def forecast_points(area: gpd.GeoDataFrame, n: int = 3) -> gpd.GeoDataFrame:
    """n × n grid of forecast points over the municipality (points inside it)."""
    xmin, ymin, xmax, ymax = area.total_bounds
    xs = np.linspace(xmin, xmax, n + 2)[1:-1]
    ys = np.linspace(ymin, ymax, n + 2)[1:-1]
    gx, gy = np.meshgrid(xs, ys)
    points = gpd.GeoDataFrame(geometry=gpd.points_from_xy(gx.ravel(), gy.ravel()), crs=area.crs)
    inside = points[points.within(area.union_all())]
    return (inside if len(inside) else points).reset_index(drop=True)


def build_data(config: dict) -> dict:
    tables = resolve(config["paths"]["tables"])
    processed = resolve(config["paths"]["processed"])
    qa = resolve(config["paths"]["qa"])
    area = gpd.read_parquet(processed / "municipality.parquet")
    calibration = json.loads((qa / "rain_calibration.json").read_text())
    susceptibility_report = json.loads((qa / "susceptibility_run.json").read_text())

    scores = gpd.read_parquet(tables / "susceptibility.parquet")
    scores = scores[scores["percentile"] >= CANDIDATE_PERCENTILE]
    # susceptibility.parquet stores segment midpoints; draw the segment lines.
    lines = gpd.read_parquet(resolve(config["paths"]["interim"]) / "segments.parquet")
    segments = lines[["segment_id", "geometry"]].merge(
        scores[["segment_id", "percentile"]], on="segment_id").reset_index(drop=True)
    points = forecast_points(area)
    nearest = gpd.sjoin_nearest(segments[["geometry"]], points, how="left")
    segments["point"] = nearest[~nearest.index.duplicated()]["index_right"].astype(int)

    params = config["susceptibility"]
    routes = gtfs_routes(resolve(config["sources"]["gtfs"]["destino"]), area.crs)
    route_names = sorted(routes["route_short_name"].astype(str).unique())
    near_routes = gpd.sjoin(segments.set_geometry(segments.buffer(params["alerta_raio_m"]))[["geometry"]],
                            routes[["route_short_name", "geometry"]], predicate="intersects")
    segments["routes"] = near_routes.groupby(level=0)["route_short_name"].apply(
        lambda names: sorted({route_names.index(str(n)) for n in names})).reindex(segments.index)
    segments["routes"] = segments["routes"].apply(lambda v: v if isinstance(v, list) else [])

    destinations = gpd.read_parquet(processed / "destinations.parquet")
    destinations = destinations[~destinations["duplicate"]].reset_index(drop=True)
    near_dest = gpd.sjoin(segments.set_geometry(segments.buffer(100))[["geometry"]],
                          destinations[["geometry"]], predicate="intersects")
    segments["dests"] = near_dest.groupby(level=0)["index_right"].apply(
        lambda ids: sorted(set(int(i) for i in ids))).reindex(segments.index)
    segments["dests"] = segments["dests"].apply(lambda v: v if isinstance(v, list) else [])
    segments["pct"] = segments["percentile"].round(3)

    points_wgs = points.to_crs("EPSG:4326")
    return {
        "segments": _features(segments, ["pct", "point", "routes", "dests"]),
        "routes": route_names,
        "destinations": _features(destinations, ["name", "category"]),
        "area": _features(area, []),
        "points": [[round(p.y, 4), round(p.x, 4)] for p in points_wgs.geometry],
        "thresholds": calibration["thresholds"],
        "missed": calibration.get("missed_by_model", []),
        "percentiles": {"alto": params["alerta_percentil"], "candidato": CANDIDATE_PERCENTILE},
        "scorer": susceptibility_report.get("selected_scorer"),
        "validation": susceptibility_report["temporal"],
        "model": {
            "events": susceptibility_report["n_events"],
            "segments": susceptibility_report["n_segments"],
            "positive_segments": susceptibility_report["n_positive_segments"],
            "features": susceptibility_report["features"],
            "ablation": susceptibility_report.get("ablation_base_features", {}).get("temporal", {}),
        },
        "api": FORECAST_API,
        "context": context(config),
    }


def build_html(data: dict) -> str:
    return (TEMPLATE.replace("__LEAFLET__", LEAFLET).replace("__BASEMAP__", basemap_js(carto_key()))
            .replace("__BASE_CSS_DARK__", BASE_CSS_DARK).replace("__BASE_CSS__", BASE_CSS)
            .replace("__DATA__", embed_json(data)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera o dashboard de alerta por previsão de chuva")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    config = load_config()
    output = Path(args.output) if args.output else (
        resolve(config["paths"]["maps"]) / "dashboard_alerta.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(build_data(config)), encoding="utf-8")
    print(output, f"{output.stat().st_size / 1e6:.1f} MB")


TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alerta de Alagamento</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400&display=swap">
<link rel="stylesheet" href="__LEAFLET__/leaflet.min.css">
<style>
:root { --ink:#1E3442; --sky:#EEF3F5; --panel:#FFFFFF; --muted:#5E7380; --rule:#D3DEE4;
  --ok:#2E8B78; --warn:#E8A317; --high:#C62828; --focus:#1F6FB2; --chip:#E3ECF0;
  --tint-0:#E4F1EE; --tint-1:#FDF1D8; --tint-2:#F9E0DE; __BASE_CSS__ }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --ink:#E6EEF2; --sky:#14212A; --panel:#1B2B36; --muted:#9DB0BC; --rule:#2E4352; --chip:#25394A;
  --tint-0:#173A35; --tint-1:#3D3218; --tint-2:#432221; --focus:#7DB7E8; __BASE_CSS_DARK__ } }
:root[data-theme="dark"] { --ink:#E6EEF2; --sky:#14212A; --panel:#1B2B36; --muted:#9DB0BC;
  --rule:#2E4352; --chip:#25394A; --tint-0:#173A35; --tint-1:#3D3218; --tint-2:#432221;
  --focus:#7DB7E8; __BASE_CSS_DARK__ }
* { box-sizing:border-box; }
html, body { margin:0; height:100%; background:var(--sky); color:var(--ink);
  font:16px/1.5 "Atkinson Hyperlegible", system-ui, sans-serif; }
#app { display:grid; grid-template-columns:420px minmax(0, 1fr); height:100%; }
#panel { min-width:0; overflow:auto; background:var(--panel); border-right:1px solid var(--rule); }
#map { background:var(--water); }
.hero { padding:22px 22px 18px; background:var(--tint-0); border-bottom:1px solid var(--rule); }
.hero[data-level="1"] { background:var(--tint-1); } .hero[data-level="2"] { background:var(--tint-2); }
.where { margin:0; font-size:14px; color:var(--muted); }
.hero h1 { margin:4px 0 6px; font-size:27px; line-height:1.18; font-weight:700; max-width:22ch; }
.hero p.detail { margin:0; font-size:15px; max-width:38ch; }
.dot { display:inline-block; width:12px; height:12px; border-radius:50%; margin-right:8px;
  vertical-align:baseline; background:var(--ok); }
.hero[data-level="1"] .dot { background:var(--warn); } .hero[data-level="2"] .dot { background:var(--high); }
.actions { display:flex; gap:10px; flex-wrap:wrap; margin-top:14px; }
button { font:inherit; font-size:15px; padding:9px 14px; border-radius:8px; cursor:pointer;
  border:1px solid var(--ink); background:var(--ink); color:var(--panel); }
button.quiet { background:transparent; color:var(--ink); border-color:var(--rule); }
button:focus-visible, input:focus-visible, summary:focus-visible, .bar:focus-visible {
  outline:3px solid var(--focus); outline-offset:2px; }
.status { margin:10px 0 0; font-size:13.5px; color:var(--muted); }
section { padding:18px 22px; border-bottom:1px solid var(--rule); }
h2 { margin:0 0 10px; font-size:18px; }
h3 { margin:14px 0 6px; font-size:15px; }
.ruler { display:block; width:100%; height:96px; }
.ruler text { fill:var(--muted); font-size:11px; }
.bar { cursor:pointer; }
input[type=range] { width:100%; accent-color:var(--ink); }
.hour { font-size:14px; color:var(--muted); margin:2px 0 0; }
.chips { display:flex; flex-wrap:wrap; gap:6px; }
.chip { font-size:13px; padding:2px 9px; border-radius:12px; background:var(--chip); }
button.link { background:none; border:0; padding:4px 0; color:var(--focus); text-decoration:underline; font-size:14px; }
ul.plain { margin:0; padding-left:18px; font-size:14.5px; }
.counts { display:flex; gap:18px; margin:0 0 4px; }
.count strong { display:block; font-size:24px; line-height:1.1; }
.count span { font-size:13px; color:var(--muted); }
.ai ol { margin:0; padding-left:20px; }
.ai li { margin-bottom:8px; }
.engine { margin-top:14px; padding:12px 14px; border-left:4px solid var(--ink); background:var(--sky);
  border-radius:0 8px 8px 0; font-size:14.5px; }
.engine p { margin:0 0 8px; } .engine p:last-child { margin:0; }
.tag { display:inline-block; font-size:12px; font-weight:700; padding:1px 7px; border-radius:6px;
  background:var(--ink); color:var(--panel); margin-right:6px; vertical-align:1px; }
details summary { cursor:pointer; font-weight:700; font-size:16px; }
.sim { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px; }
.sim label { font-size:13px; color:var(--muted); display:block; }
.sim input[type=number] { width:100%; padding:7px; font:inherit; border:1px solid var(--rule);
  border-radius:8px; background:var(--panel); color:var(--ink); }
footer { padding:16px 22px 28px; font-size:12.5px; color:var(--muted); }
.legend { background:var(--panel); color:var(--ink); padding:8px 10px; border-radius:8px;
  font:13px/1.6 "Atkinson Hyperlegible", system-ui, sans-serif; box-shadow:0 1px 3px rgba(30,52,66,.25); }
.legend i { display:inline-block; width:18px; height:4px; margin-right:6px; vertical-align:middle; }
@media (max-width: 820px) {
  #app { grid-template-columns:minmax(0, 1fr); grid-template-rows:auto 55vh; height:auto; }
  #panel { border-right:0; overflow:visible; order:1; }
  #map { order:2; height:55vh; }
  .hero h1 { font-size:24px; }
}
@media (prefers-reduced-motion: reduce) { * { transition:none !important; } }
</style>
</head>
<body>
<div id="app">
<main id="panel">
  <header class="hero" id="hero" data-level="0" aria-live="polite">
    <p class="where" id="where">Porto Alegre, próximas 48 horas</p>
    <h1 id="headline"><span class="dot" aria-hidden="true"></span>Carregando a previsão de chuva</h1>
    <p class="detail" id="detail"></p>
    <div class="actions">
      <button id="locate">Usar minha localização</button>
      <button id="reload" class="quiet">Atualizar previsão</button>
    </div>
    <p class="status" id="status"></p>
  </header>

  <section aria-labelledby="h-rain">
    <h2 id="h-rain">Chuva prevista</h2>
    <svg class="ruler" id="ruler" role="img" aria-label="Chuva prevista e nível de alerta por hora"></svg>
    <label for="hour" class="hour">Hora exibida no mapa</label>
    <input type="range" id="hour" min="0" max="0" value="0">
    <p class="hour" id="hourInfo"></p>
  </section>

  <section aria-labelledby="h-impact">
    <h2 id="h-impact">O que pode ser afetado</h2>
    <div class="counts">
      <div class="count"><strong id="nHigh">0</strong><span>trechos em alerta alto</span></div>
      <div class="count"><strong id="nWarn">0</strong><span>trechos em atenção</span></div>
    </div>
    <h3>Linhas de ônibus que passam por esses trechos</h3>
    <div class="chips" id="routes"></div>
    <button class="link" id="moreRoutes" hidden></button>
    <h3>Serviços de saúde a até 100 m</h3>
    <ul class="plain" id="dests"></ul>
    <button class="link" id="moreDests" hidden></button>
  </section>

  <section class="ai" aria-labelledby="h-ai">
    <h2 id="h-ai">Como a IA calcula o risco</h2>
    <ol>
      <li><strong>Lê a previsão de chuva</strong> para a sua região, hora a hora: quanto chove em uma hora e quanto acumula em 24 horas.</li>
      <li><strong>Consulta o mapa de propensão</strong>: um modelo de aprendizado de máquina deu a cada trecho de via uma nota, aprendida com os locais onde a EPTC já registrou bloqueio por água.</li>
      <li><strong>Cruza as duas coisas</strong>: com chuva forte, os trechos com nota mais alta entram em atenção ou alerta alto.</li>
    </ol>
    <div class="engine" id="engine"></div>
  </section>

  <section>
    <details>
      <summary>Testar com outra chuva</summary>
      <p class="status">Substitui a previsão pelos valores abaixo, para ver como o alerta reage.</p>
      <label style="font-size:15px"><input type="checkbox" id="simulate"> Usar estes valores</label>
      <div class="sim">
        <div><label for="simH">Chuva em uma hora (mm)</label><input id="simH" type="number" min="0" step="0.5" value="12"></div>
        <div><label for="sim24">Chuva em 24 horas (mm)</label><input id="sim24" type="number" min="0" step="1" value="60"></div>
      </div>
    </details>
  </section>

  <footer id="footer"></footer>
</main>
<div id="map" aria-label="Mapa dos trechos em alerta"></div>
</div>
<script src="__LEAFLET__/leaflet.min.js"></script>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const T = D.thresholds, P = D.percentiles;
const $ = id => document.getElementById(id);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const LEVEL = ["Sem alerta", "Atenção", "Alerta alto"];
const FEATURE_NAMES = {
  elev: "altitude do terreno", rel_elev_250: "se o trecho fica abaixo do entorno (250 m)",
  rel_elev_500: "se o trecho fica abaixo do entorno (500 m)", slope: "inclinação da via",
  dist_water: "distância a arroios e valas", height_above_water: "altura acima do curso d'água mais próximo",
  log_flow_acc: "quanta água da chuva escoa até o ponto", twi: "tendência do terreno a acumular umidade",
  drainage_density_250: "quantidade de valas e arroios ao redor"};
const hourFmt = new Intl.DateTimeFormat("pt-BR", {weekday: "short", hour: "2-digit", minute: "2-digit"});
const dayFmt = new Intl.DateTimeFormat("pt-BR", {weekday: "short"});
const num = v => Number(v).toLocaleString("pt-BR", {maximumFractionDigits: 1});

const map = L.map("map", {preferCanvas: true});
const CONTEXT = D.context;
__BASEMAP__
map.attributionControl.addAttribution("Previsão: Open-Meteo");
const area = L.geoJSON(D.area, {style: {color: css("--ink"), weight: 1.2, fillOpacity: 0}}).addTo(map);
map.fitBounds(area.getBounds());
const segLayer = L.geoJSON(null, {style: f => ({color: f.properties.level === 2 ? css("--high") : css("--warn"),
  weight: f.properties.level === 2 ? 4 : 3})}).addTo(map);
const legend = L.control({position: "bottomleft"});
legend.onAdd = () => {
  const box = L.DomUtil.create("div", "legend");
  for (const [color, text] of [[css("--high"), "Alerta alto"], [css("--warn"), "Atenção"]]) {
    const row = document.createElement("div"); const swatch = document.createElement("i");
    swatch.style.background = color; row.append(swatch, document.createTextNode(text)); box.append(row);
  }
  return box;
};
legend.addTo(map);

let forecast = null, user = null, userMarker = null, nearby = null, showAllRoutes = false, showAllDests = false;
const ROUTES_SHOWN = 24, DESTS_SHOWN = 10;

function rainLevel(h1, h24) {
  if (h1 >= T.alto_max_1h_mm || h24 >= T.alto_total_24h_mm) return 2;
  if (h1 >= T.medio_max_1h_mm || h24 >= T.medio_total_24h_mm) return 1;
  return 0;
}
function segmentLevel(rain, pct) {
  if (rain === 2) return pct >= P.alto ? 2 : 1;
  if (rain === 1) return pct >= P.alto ? 1 : 0;
  return 0;
}
const simulating = () => $("simulate").checked || !forecast;
const hours = () => simulating() ? 1 : forecast.times.length - forecast.start;
function rainAt(point, k) {
  if (simulating()) return [Number($("simH").value) || 0, Number($("sim24").value) || 0];
  const i = forecast.start + k;
  return [forecast.h1[point][i], forecast.h24[point][i]];
}
function levelsAt(k) {
  const rain = D.points.map((_, p) => rainLevel(...rainAt(p, k)));
  return D.segments.features.map(f => segmentLevel(rain[f.properties.point], f.properties.pct));
}
// Level of the area in focus: segments near the user, or the whole city.
function focusLevel(levels) {
  const ids = nearby || levels.keys();
  let worst = 0; for (const i of ids) worst = Math.max(worst, levels[i]);
  return worst;
}
function timeLabel(k) { return simulating() ? "Simulação" : hourFmt.format(new Date(forecast.times[forecast.start + k])); }

async function loadForecast() {
  $("status").textContent = "Buscando a previsão de chuva…";
  const params = new URLSearchParams({latitude: D.points.map(p => p[0]).join(","),
    longitude: D.points.map(p => p[1]).join(","), hourly: "precipitation", past_days: "1",
    forecast_days: "2", timezone: "America/Sao_Paulo"});
  try {
    const response = await fetch(`${D.api}?${params}`);
    if (!response.ok) throw new Error(`o serviço respondeu ${response.status}`);
    let json = await response.json(); if (!Array.isArray(json)) json = [json];
    const times = json[0].hourly.time;
    const h1 = json.map(j => j.hourly.precipitation.map(v => v ?? 0));
    const h24 = h1.map(s => s.map((_, i) => s.slice(Math.max(0, i - 23), i + 1).reduce((a, b) => a + b, 0)));
    const now = Date.now() - 3600e3;
    forecast = {times, h1, h24, start: Math.max(0, times.findIndex(t => new Date(t).getTime() >= now))};
    $("hour").max = String(forecast.times.length - 1 - forecast.start); $("hour").value = "0";
    $("status").textContent = `Previsão atualizada às ${new Date().toLocaleTimeString("pt-BR", {hour: "2-digit", minute: "2-digit"})}.`;
  } catch (error) {
    forecast = null;
    $("status").textContent = `Não foi possível buscar a previsão (${error.message}). Tente "Atualizar previsão" ou teste com outra chuva.`;
  }
  render();
}

function headline() {
  const n = hours(), perHour = [];
  for (let k = 0; k < n; k++) perHour.push(focusLevel(levelsAt(k)));
  const worst = Math.max(...perHour);
  const place = nearby ? "perto de você" : "em Porto Alegre";
  if (simulating()) return {level: worst, title: worst ? `${LEVEL[worst]} ${place} com essa chuva` :
    `Sem alerta ${place} com essa chuva`, detail: "Resultado da simulação, não da previsão."};
  if (!worst) {
    const maxRain = Math.max(...forecast.h1.map(s => Math.max(...s.slice(forecast.start))));
    return {level: 0, title: `Sem alerta de alagamento ${place} nas próximas 48 horas`,
      detail: maxRain > 0 ? `A previsão indica até ${num(maxRain)} mm de chuva em uma hora, abaixo do que costuma bloquear vias.`
                          : "Não há chuva prevista."};
  }
  const first = perHour.findIndex(l => l === worst);
  let last = first; while (last + 1 < n && perHour[last + 1] === worst) last++;
  const span = first === last ? timeLabel(first) : `de ${timeLabel(first)} a ${timeLabel(last)}`;
  return {level: worst, title: `${LEVEL[worst]} ${place}: ${span}`,
    detail: "Trechos propensos a acumular água podem ficar bloqueados. Veja no mapa e evite-os, se puder."};
}

function drawRuler() {
  const svg = $("ruler"); svg.replaceChildren();
  const ns = "http://www.w3.org/2000/svg", w = svg.clientWidth || 360, h = 96, base = h - 18;
  const add = (tag, attrs, text) => { const el = document.createElementNS(ns, tag);
    for (const [a, v] of Object.entries(attrs)) el.setAttribute(a, v); if (text) el.textContent = text; svg.append(el); return el; };
  if (simulating()) { add("text", {x: 0, y: 40}, "Simulação ativa: a régua mostra a previsão quando desligada."); return; }
  const n = hours(), bw = w / n;
  const rain = k => Math.max(...forecast.h1.map(s => s[forecast.start + k]));
  const maxRain = 1.25 * Math.max(T.alto_max_1h_mm, ...Array.from({length: n}, (_, k) => rain(k)));
  for (const [value, label] of [[T.medio_max_1h_mm, "atenção"], [T.alto_max_1h_mm, "alerta alto"]]) {
    const y = base - (base - 8) * value / maxRain;
    add("line", {x1: 0, x2: w, y1: y, y2: y, stroke: css("--rule"), "stroke-dasharray": "3 3"});
    add("text", {x: w - 2, y: y - 3, "text-anchor": "end"}, `${num(value)} mm/h ${label}`);
  }
  for (let k = 0; k < n; k++) {
    const level = focusLevel(levelsAt(k)), r = rain(k), bh = Math.max(2, (base - 8) * r / maxRain);
    const bar = add("rect", {x: k * bw + 0.5, y: base - bh, width: Math.max(1, bw - 1), height: bh, class: "bar",
      fill: level === 2 ? css("--high") : level === 1 ? css("--warn") : css("--ok"),
      opacity: k === Number($("hour").value) ? 1 : 0.6});
    add("title", {}).textContent = `${timeLabel(k)}: ${num(r)} mm/h, ${LEVEL[level].toLowerCase()}`;
    bar.append(svg.lastChild);
    bar.addEventListener("click", () => { $("hour").value = String(k); render(); });
    const date = new Date(forecast.times[forecast.start + k]);
    if (date.getHours() % 6 === 0) add("text", {x: k * bw, y: h - 4},
      date.getHours() === 0 ? dayFmt.format(date) : `${date.getHours()}h`);
  }
}

function distanceKm(a, b) {
  const R = 6371, rad = Math.PI / 180, dLat = (b[0] - a[0]) * rad, dLon = (b[1] - a[1]) * rad;
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}
function insideArea(lat, lon) {
  const inRing = ring => { let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside; }
    return inside; };
  return D.area.features.some(f => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates)
    .some(poly => inRing(poly[0]) && !poly.slice(1).some(inRing)));
}

function render() {
  const k = Math.min(Number($("hour").value), hours() - 1), levels = levelsAt(k);
  const active = D.segments.features.map((f, i) => ({...f, properties: {...f.properties, level: levels[i]}}))
    .filter(f => f.properties.level > 0);
  segLayer.clearLayers(); segLayer.addData({type: "FeatureCollection", features: active});
  $("nHigh").textContent = active.filter(f => f.properties.level === 2).length.toLocaleString("pt-BR");
  $("nWarn").textContent = active.filter(f => f.properties.level === 1).length.toLocaleString("pt-BR");
  const routeIds = new Set(), destIds = new Set();
  active.forEach(f => { f.properties.routes.forEach(r => routeIds.add(r)); f.properties.dests.forEach(d => destIds.add(d)); });
  const routes = $("routes"); routes.replaceChildren();
  const names = [...routeIds].map(r => D.routes[r]).sort((a, b) => a.localeCompare(b, "pt-BR", {numeric: true}));
  (showAllRoutes ? names : names.slice(0, ROUTES_SHOWN)).forEach(name => {
    const chip = document.createElement("span"); chip.className = "chip"; chip.textContent = name; routes.append(chip); });
  if (!routeIds.size) routes.textContent = "Nenhuma nesta hora.";
  const more = $("moreRoutes");
  more.hidden = names.length <= ROUTES_SHOWN;
  more.textContent = showAllRoutes ? "Mostrar menos" : `Ver todas as ${names.length} linhas`;
  const dests = $("dests"); dests.replaceChildren();
  const destNames = [...destIds].map(d => D.destinations.features[d].properties.name || "Estabelecimento sem nome no mapa")
    .sort((a, b) => a.localeCompare(b, "pt-BR"));
  (showAllDests ? destNames : destNames.slice(0, DESTS_SHOWN)).forEach(name => {
    const li = document.createElement("li"); li.textContent = name; dests.append(li); });
  if (!destIds.size) { const li = document.createElement("li"); li.textContent = "Nenhum nesta hora."; dests.append(li); }
  const moreDests = $("moreDests");
  moreDests.hidden = destNames.length <= DESTS_SHOWN;
  moreDests.textContent = showAllDests ? "Mostrar menos" : `Ver todos os ${destNames.length} serviços`;

  const head = headline();
  $("hero").dataset.level = String(head.level);
  const h1 = $("headline"); h1.replaceChildren();
  const dot = document.createElement("span"); dot.className = "dot"; dot.setAttribute("aria-hidden", "true");
  h1.append(dot, document.createTextNode(head.title));
  $("detail").textContent = head.detail;
  if (simulating()) $("hourInfo").textContent = `Simulação: ${$("simH").value} mm em uma hora e ${$("sim24").value} mm em 24 horas.`;
  else { const i = forecast.start + k;
    $("hourInfo").textContent = `${timeLabel(k)}: até ${num(Math.max(...forecast.h1.map(s => s[i])))} mm nesta hora e ${num(Math.max(...forecast.h24.map(s => s[i])))} mm nas últimas 24 horas.`; }
  $("hour").disabled = simulating();
  drawRuler();
}

$("locate").addEventListener("click", () => {
  if (!navigator.geolocation) { $("status").textContent = "Este navegador não permite usar a localização."; return; }
  $("status").textContent = "Obtendo sua localização…";
  navigator.geolocation.getCurrentPosition(pos => {
    const lat = pos.coords.latitude, lon = pos.coords.longitude;
    if (userMarker) userMarker.remove();
    userMarker = L.circleMarker([lat, lon], {radius: 8, color: "#fff", weight: 3, fillColor: css("--focus"), fillOpacity: 1})
      .addTo(map).bindTooltip("Você está aqui");
    if (insideArea(lat, lon)) {
      user = [lat, lon];
      nearby = D.segments.features.flatMap((f, i) =>
        f.geometry.coordinates.some(c => distanceKm(user, [c[1], c[0]]) <= 1.5) ? [i] : []);
      map.setView(user, 14);
      $("where").textContent = "Perto de você (1,5 km), próximas 48 horas";
      $("status").textContent = "Sua localização é usada só neste navegador; ela não é enviada a nenhum serviço.";
    } else {
      user = null; nearby = null; map.setView([lat, lon], 10);
      $("where").textContent = "Porto Alegre, próximas 48 horas";
      $("status").textContent = "Você está fora de Porto Alegre. O modelo foi treinado só com dados da cidade, então mostramos o alerta de Porto Alegre.";
    }
    render();
  }, error => { $("status").textContent = `Não foi possível obter a localização (${error.message}). Mostrando Porto Alegre inteira.`; },
  {enableHighAccuracy: false, timeout: 10000, maximumAge: 600000});
});
$("reload").addEventListener("click", loadForecast);
$("moreRoutes").addEventListener("click", () => { showAllRoutes = !showAllRoutes; render(); });
$("moreDests").addEventListener("click", () => { showAllDests = !showAllDests; render(); });
for (const id of ["hour", "simulate", "simH", "sim24"]) $(id).addEventListener("input", render);
window.addEventListener("resize", drawRuler);

// Model card in plain language.
(function engineCard() {
  const v = D.validation, m = D.model, ai = D.scorer === "logistic";
  const box = $("engine"); box.replaceChildren();
  const para = (...parts) => { const p = document.createElement("p"); parts.forEach(x => p.append(x)); box.append(p); return p; };
  const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = ai ? "IA" : "Regra";
  para(tag, ai ? "Motor em uso: modelo de aprendizado de máquina (regressão logística)."
               : "Motor em uso: regra de relevo, porque nesta versão a IA não superou a regra nos testes.");
  para(`Aprendeu com ${m.events} locais onde a EPTC registrou bloqueio por acúmulo de água entre 2019 e 2025, comparando-os com ${m.segments.toLocaleString("pt-BR")} trechos de via da cidade.`);
  para("Observa, em cada trecho: " + m.features.map(f => FEATURE_NAMES[f] || f).join("; ") + ".");
  const t = v.logistic || {}, r = v.elevacao_baixa || {};
  para(`Como foi testado: escondemos os bloqueios de 2025 e pedimos à IA que os encontrasse. ` +
       `Em ${Math.round((t.share_top20 || 0) * 100)}% deles, o trecho estava entre os 20% que ela considera mais propensos ` +
       `(uma regra simples de "terreno mais baixo" acertou ${Math.round((r.share_top20 || 0) * 100)}%; um sorteio, ${Math.round(((v.aleatorio || {}).share_top20 || 0) * 100)}%). ` +
       `Pela posição típica desses trechos na lista, a IA fica um pouco à frente (${Math.round((t.median_percentile || 0) * 100)} contra ${Math.round((r.median_percentile || 0) * 100)} de 100). ` +
       `Com só ${t.events || 0} casos de teste, consideramos IA e regra empatadas.`);
  para("Limites: não é uma probabilidade; não há dados abertos de bocas de lobo nem de limpeza urbana; " +
       "a previsão de chuva pode não captar temporais curtos" + (D.missed.length ? ` (não captou o de ${D.missed.map(d => d.split("-").reverse().join("/")).join(", ")})` : "") + ".");
})();
$("footer").textContent = `Níveis: atenção a partir de ${num(T.medio_max_1h_mm)} mm em uma hora ou ${num(T.medio_total_24h_mm)} mm em 24 horas; ` +
  `alerta alto a partir de ${num(T.alto_max_1h_mm)} mm ou ${num(T.alto_total_24h_mm)} mm, calibrados com a chuva prevista nos dias de bloqueio. ` +
  `Fontes: EPTC e Prefeitura de Porto Alegre (bloqueios), Copernicus DEM (relevo), OpenStreetMap (vias e drenagem), ` +
  `IBGE (limites), Open-Meteo (previsão), GTFS da EPTC de 2025 (linhas). Protótipo de pesquisa; não substitui os avisos da Defesa Civil (199).`;
loadForecast();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
