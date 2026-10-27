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
from .webmap import BASE_CSS, BASE_CSS_DARK, BASEMAP_JS, LEAFLET, _features, context, embed_json

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
        "api": FORECAST_API,
        "context": context(config),
    }


def build_html(data: dict) -> str:
    return (TEMPLATE.replace("__LEAFLET__", LEAFLET).replace("__BASEMAP__", BASEMAP_JS)
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
<link rel="stylesheet" href="__LEAFLET__/leaflet.min.css">
<style>
:root { --bg:#f7f7f5; --panel:#fff; --text:#1d1d1b; --muted:#5f5f5a; --line:#d9d9d4;
  --none:#cfd8dc; --medio:#f39c12; --alto:#c0392b; --accent:#1f5f99; __BASE_CSS__ }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#151514; --panel:#22221f;
  --text:#ecece8; --muted:#a5a59e; --line:#3a3a36; --none:#45494b; --accent:#6aa8d1; __BASE_CSS_DARK__ } }
:root[data-theme="dark"] { --bg:#151514; --panel:#22221f; --text:#ecece8; --muted:#a5a59e;
  --line:#3a3a36; --none:#45494b; --accent:#6aa8d1; __BASE_CSS_DARK__ }
* { box-sizing:border-box; }
html, body { margin:0; height:100%; background:var(--bg); color:var(--text);
  font:14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
#app { display:flex; height:100%; }
#panel { width:360px; flex:none; overflow:auto; padding:16px; background:var(--panel);
  border-right:1px solid var(--line); }
#map { flex:1; background:var(--water); }
h1 { font-size:17px; margin:0 0 2px; } h2 { font-size:13px; margin:16px 0 6px; text-transform:uppercase;
  letter-spacing:.04em; color:var(--muted); }
.sub, .muted { color:var(--muted); font-size:12.5px; }
button { font:inherit; padding:7px 10px; border-radius:6px; border:1px solid var(--line);
  background:var(--accent); color:#fff; cursor:pointer; }
button.secondary { background:transparent; color:var(--text); }
.status { margin:10px 0; padding:8px 10px; border-radius:6px; background:var(--bg);
  border:1px solid var(--line); font-size:13px; }
.level { display:inline-block; padding:2px 8px; border-radius:10px; color:#fff; font-weight:600;
  font-size:12px; }
.level.n0 { background:var(--none); color:var(--text); } .level.n1 { background:var(--medio); }
.level.n2 { background:var(--alto); }
#timeline { width:100%; height:70px; display:block; }
input[type=range] { width:100%; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.grid2 label { font-size:12px; color:var(--muted); }
.grid2 input { width:100%; padding:5px; border:1px solid var(--line); border-radius:6px;
  background:var(--bg); color:var(--text); font:inherit; }
ul.list { margin:4px 0; padding-left:18px; max-height:140px; overflow:auto; font-size:13px; }
.chips { display:flex; flex-wrap:wrap; gap:4px; max-height:110px; overflow:auto; }
.chip { font-size:11.5px; padding:1px 6px; border:1px solid var(--line); border-radius:8px; }
.note { margin-top:14px; padding-top:10px; border-top:1px solid var(--line); color:var(--muted);
  font-size:12px; }
@media (max-width: 760px) { #app { flex-direction:column; }
  #panel { width:100%; max-height:52%; border-right:0; border-bottom:1px solid var(--line); } }
</style>
</head>
<body>
<div id="app">
<aside id="panel">
  <h1>Alerta de alagamento em vias</h1>
  <div class="sub">Porto Alegre · previsão horária de chuva × suscetibilidade dos trechos</div>
  <div style="display:flex; gap:8px; margin-top:12px; flex-wrap:wrap">
    <button id="locate">Usar minha localização</button>
    <button id="reload" class="secondary">Atualizar previsão</button>
  </div>
  <div class="status" id="locStatus">Localização não informada: mostrando Porto Alegre.</div>
  <div class="status" id="fcStatus">Carregando previsão…</div>

  <h2>Linha do tempo (nível na cidade)</h2>
  <svg id="timeline" role="img" aria-label="Nível de alerta por hora"></svg>
  <input type="range" id="hour" min="0" max="0" value="0" aria-label="Hora selecionada">
  <div id="hourInfo" class="muted"></div>

  <h2>Simulação</h2>
  <label style="font-size:13px"><input type="checkbox" id="simulate"> Usar chuva informada (substitui a previsão)</label>
  <div class="grid2" style="margin-top:6px">
    <div><label for="simH">mm na hora</label><input id="simH" type="number" min="0" step="0.5" value="12"></div>
    <div><label for="sim24">mm em 24 h</label><input id="sim24" type="number" min="0" step="1" value="60"></div>
  </div>

  <h2>Trechos em alerta</h2>
  <div id="summary"></div>
  <h2>Perto de você</h2>
  <div id="nearby" class="muted">Informe a localização para ver alertas num raio de 1,5 km.</div>
  <h2>Linhas de ônibus expostas</h2>
  <div class="chips" id="routes"></div>
  <h2>Serviços de saúde a até 100 m de trechos em alerta</h2>
  <ul class="list" id="dests"></ul>
  <p class="note" id="method"></p>
</aside>
<div id="map"></div>
</div>
<script src="__LEAFLET__/leaflet.min.js"></script>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const T = D.thresholds, P = D.percentiles;
const $ = id => document.getElementById(id);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const LEVEL = ["sem alerta", "médio", "alto"];

const map = L.map("map", {preferCanvas: true});
const CONTEXT = D.context;
__BASEMAP__
map.attributionControl.addAttribution("previsão: Open-Meteo");
const area = L.geoJSON(D.area, {style: {color: "#55554f", weight: 1, fillOpacity: 0}}).addTo(map);
map.fitBounds(area.getBounds());
const segLayer = L.geoJSON(null, {style: f => ({color: f.properties.level === 2 ? css("--alto") : css("--medio"),
  weight: f.properties.level === 2 ? 3 : 2})}).addTo(map);
let userMarker = null, user = null;

// Rain level from hourly intensity and 24 h accumulation (calibrated thresholds).
function rainLevel(h1, h24) {
  if (h1 >= T.alto_max_1h_mm || h24 >= T.alto_total_24h_mm) return 2;
  if (h1 >= T.medio_max_1h_mm || h24 >= T.medio_total_24h_mm) return 1;
  return 0;
}
// Segment alert: rain level combined with the susceptibility percentile.
function segmentLevel(rain, pct) {
  if (rain === 2) return pct >= P.alto ? 2 : 1;
  if (rain === 1) return pct >= P.alto ? 1 : 0;
  return 0;
}

let forecast = null;   // {times: [...], h1: [[point][hour]], h24: [[point][hour]], start}
async function loadForecast() {
  $("fcStatus").textContent = "Carregando previsão…";
  const params = new URLSearchParams({
    latitude: D.points.map(p => p[0]).join(","), longitude: D.points.map(p => p[1]).join(","),
    hourly: "precipitation", past_days: "1", forecast_days: "2", timezone: "America/Sao_Paulo"});
  try {
    const response = await fetch(`${D.api}?${params}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    let json = await response.json();
    if (!Array.isArray(json)) json = [json];
    const times = json[0].hourly.time;
    const h1 = json.map(j => j.hourly.precipitation.map(v => v ?? 0));
    const h24 = h1.map(series => series.map((_, i) =>
      series.slice(Math.max(0, i - 23), i + 1).reduce((a, b) => a + b, 0)));
    const now = new Date();
    const start = Math.max(0, times.findIndex(t => new Date(t) >= new Date(now.getTime() - 3600e3)));
    forecast = {times, h1, h24, start};
    $("hour").max = String(times.length - 1 - start);
    $("hour").value = "0";
    $("fcStatus").textContent = `Previsão Open-Meteo carregada (${D.points.length} pontos, até ${times.at(-1).replace("T", " ")}).`;
  } catch (error) {
    forecast = null;
    $("fcStatus").textContent = `Não foi possível obter a previsão (${error.message}). Use a simulação.`;
    $("simulate").checked = true;
  }
  render();
}

function rainAt(point, hourIndex) {
  if ($("simulate").checked || !forecast) return [Number($("simH").value) || 0, Number($("sim24").value) || 0];
  const i = forecast.start + hourIndex;
  return [forecast.h1[point][i], forecast.h24[point][i]];
}
function levelsAt(hourIndex) {
  const rain = D.points.map((_, p) => rainLevel(...rainAt(p, hourIndex)));
  return D.segments.features.map(f => segmentLevel(rain[f.properties.point], f.properties.pct));
}

function drawTimeline() {
  const svg = $("timeline"); svg.replaceChildren();
  if (!forecast || $("simulate").checked) return;
  const n = forecast.times.length - forecast.start, w = svg.clientWidth || 320, h = 70;
  const bw = w / n, maxRain = Math.max(1, ...forecast.h1.flat());
  if (Math.max(...forecast.h1.map(s => Math.max(...s.slice(forecast.start)))) === 0) {
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", 4); text.setAttribute("y", 38); text.setAttribute("fill", css("--muted"));
    text.setAttribute("font-size", "12"); text.textContent = "Sem chuva prevista nas próximas 48 h.";
    svg.append(text); return;
  }
  for (let k = 0; k < n; k++) {
    const i = forecast.start + k;
    const city = Math.max(...D.points.map((_, p) => rainLevel(forecast.h1[p][i], forecast.h24[p][i])));
    const rain = Math.max(...forecast.h1.map(s => s[i]));
    const bar = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    const bh = Math.max(2, (h - 14) * rain / maxRain);
    bar.setAttribute("x", k * bw); bar.setAttribute("y", h - 12 - bh);
    bar.setAttribute("width", Math.max(1, bw - 1)); bar.setAttribute("height", bh);
    bar.setAttribute("fill", city === 2 ? css("--alto") : city === 1 ? css("--medio") : css("--none"));
    if (k === Number($("hour").value)) { bar.setAttribute("stroke", css("--text")); bar.setAttribute("stroke-width", "1.5"); }
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${forecast.times[i].replace("T", " ")} · ${rain.toFixed(1)} mm/h (máx. entre pontos) · ${LEVEL[city]}`;
    bar.append(title); svg.append(bar);
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
  return D.area.features.some(f => {
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    return polys.some(poly => inRing(poly[0]) && !poly.slice(1).some(inRing));
  });
}
function li(list, text) { const item = document.createElement("li"); item.textContent = text; list.append(item); }

function render() {
  const k = Number($("hour").value);
  const levels = levelsAt(k);
  segLayer.clearLayers();
  const active = D.segments.features.map((f, i) => ({...f, properties: {...f.properties, level: levels[i]}}))
                                   .filter(f => f.properties.level > 0);
  segLayer.addData({type: "FeatureCollection", features: active});
  const counts = [0, 0, 0]; levels.forEach(l => counts[l]++);
  const summary = $("summary"); summary.replaceChildren();
  for (const l of [2, 1]) {
    const span = document.createElement("span"); span.className = `level n${l}`;
    span.textContent = `${LEVEL[l]}: ${counts[l].toLocaleString("pt-BR")} trechos`;
    summary.append(span, document.createTextNode(" "));
  }
  if (!counts[1] && !counts[2]) { const s = document.createElement("span"); s.className = "level n0";
    s.textContent = "nenhum trecho em alerta"; summary.append(s); }

  const routeIds = new Set(), destIds = new Set();
  active.forEach(f => { f.properties.routes.forEach(r => routeIds.add(r)); f.properties.dests.forEach(d => destIds.add(d)); });
  const routes = $("routes"); routes.replaceChildren();
  [...routeIds].map(r => D.routes[r]).sort().forEach(name => {
    const chip = document.createElement("span"); chip.className = "chip"; chip.textContent = name; routes.append(chip); });
  if (!routeIds.size) routes.textContent = "nenhuma";
  const dests = $("dests"); dests.replaceChildren();
  [...destIds].forEach(d => { const p = D.destinations.features[d].properties;
    li(dests, `${p.name || "(sem nome no OSM)"} — ${p.category}`); });
  if (!destIds.size) li(dests, "nenhum");

  const label = $("simulate").checked || !forecast ? `Simulação: ${$("simH").value} mm/h, ${$("sim24").value} mm em 24 h`
    : (() => { const i = forecast.start + k;
        const r1 = Math.max(...forecast.h1.map(s => s[i])), r24 = Math.max(...forecast.h24.map(s => s[i]));
        return `${forecast.times[i].replace("T", " ")} · até ${r1.toFixed(1)} mm/h · até ${r24.toFixed(1)} mm em 24 h`; })();
  $("hourInfo").textContent = label;
  $("hour").disabled = $("simulate").checked || !forecast;

  const nearby = $("nearby");
  if (user && user.inside) {
    const close = active.filter(f => f.geometry.coordinates.some(c => distanceKm(user.latlon, [c[1], c[0]]) <= 1.5));
    const worst = Math.max(0, ...close.map(f => f.properties.level));
    let nearest = null;
    D.destinations.features.forEach(f => { const [lon, lat] = f.geometry.coordinates;
      const d = distanceKm(user.latlon, [lat, lon]); if (!nearest || d < nearest.d) nearest = {d, p: f.properties}; });
    nearby.replaceChildren();
    const badge = document.createElement("span"); badge.className = `level n${worst}`;
    badge.textContent = `${close.length} trechos em alerta a até 1,5 km (${LEVEL[worst]})`;
    nearby.append(badge, document.createElement("br"));
    if (nearest) nearby.append(document.createTextNode(
      `Serviço de saúde mais próximo (linha reta): ${nearest.p.name || "(sem nome)"} — ${nearest.d.toFixed(1)} km`));
  }
  drawTimeline();
}

$("locate").addEventListener("click", () => {
  if (!navigator.geolocation) { $("locStatus").textContent = "Este navegador não oferece geolocalização."; return; }
  $("locStatus").textContent = "Obtendo localização…";
  navigator.geolocation.getCurrentPosition(pos => {
    const lat = pos.coords.latitude, lon = pos.coords.longitude;
    const inside = insideArea(lat, lon);
    user = {latlon: [lat, lon], inside};
    if (userMarker) userMarker.remove();
    userMarker = L.circleMarker([lat, lon], {radius: 7, color: "#fff", weight: 2, fillColor: css("--accent"), fillOpacity: 1}).addTo(map);
    if (inside) { map.setView([lat, lon], 14);
      $("locStatus").textContent = "Você está em Porto Alegre: alertas próximos abaixo. A localização fica só no navegador.";
    } else {
      $("locStatus").textContent = "Fora de Porto Alegre: área não coberta pelo modelo (treinado só com dados da cidade).";
      $("nearby").textContent = "Área não coberta.";
    }
    render();
  }, error => { $("locStatus").textContent = `Localização indisponível (${error.message}). Mostrando Porto Alegre.`; },
  {enableHighAccuracy: false, timeout: 10000, maximumAge: 600000});
});
$("reload").addEventListener("click", loadForecast);
for (const id of ["hour", "simulate", "simH", "sim24"]) $(id).addEventListener("input", render);
window.addEventListener("resize", drawTimeline);

const v = D.validation[D.scorer] || {};
$("method").textContent =
  `Nível de alerta heurístico, não probabilidade. Chuva: médio a partir de ${T.medio_max_1h_mm} mm/h ou ` +
  `${T.medio_total_24h_mm} mm em 24 h; alto a partir de ${T.alto_max_1h_mm} mm/h ou ${T.alto_total_24h_mm} mm ` +
  `(chuva modelada em datas com bloqueio informado; limite inferior). Trechos: percentil de suscetibilidade ` +
  `≥ ${P.alto} (alto) ou ≥ ${P.candidato} com chuva de nível alto (médio), pelo critério "${D.scorer}", ` +
  `que melhor ordenou os eventos de 2025 (percentil mediano ${v.median_percentile}). ` +
  (D.missed.length ? `A previsão não captou a chuva em ${D.missed.join(", ")}: temporais curtos podem não aparecer. ` : "") +
  `Suscetibilidade = semelhança com locais já interditados (viés de notificação), não previsão de alagamento. ` +
  `Cobertura: só Porto Alegre.`;
loadForecast();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
