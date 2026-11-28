// Shared by the browser tests. Needs PLAYWRIGHT_CORE (path of playwright-core) and CHROME_PATH (a Chromium/Chrome binary).
const assert = require("assert");
const { chromium } = require(process.env.PLAYWRIGHT_CORE);
const BASE = process.env.BASE_URL || "http://127.0.0.1:8766/";
const ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"];   // WebGL without a GPU
async function abrir(opts, semWebgl) {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: semWebgl ? ["--disable-gpu", "--disable-3d-apis", "--disable-webgl", "--disable-webgl2"] : ARGS });
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage(), erros = [];
  page.setDefaultTimeout(90000);
  // O painel real abre no mapa e esconde as abas no modo mapa; os testes que partem de Resultados usam o endereço explícito, e o clique numa aba (escondida) é feito no DOM.
  const goto0 = page.goto.bind(page); page.goto = (u, o) => goto0(u === BASE ? BASE + "#poa/resultados" : u, o);
  const click0 = page.click.bind(page); page.click = (s, o) => (typeof s === "string" && /^\[data-aba=/.test(s) ? page.evaluate((q) => document.querySelector(q).click(), s) : click0(s, o));
  if (process.env.TRACE) for (const m of ["click", "fill", "selectOption", "waitForSelector", "waitForFunction", "goto"]) { const o = page[m].bind(page); page[m] = (...a) => { console.error(new Date().toISOString().slice(14, 23), m, String(a[0]).slice(0, 70)); return o(...a); }; }   // software WebGL (no GPU) renders the 3D map slowly
  page.on("console", (m) => { if (m.type() === "error" && !/tile\.openstreetmap|amazonaws|ERR_|Failed to load resource/.test(m.text())) erros.push(m.text().slice(0, 200)); });
  page.on("pageerror", (e) => erros.push("pageerror: " + e.message));
  // A static file of ours that answers 4xx/5xx is a bug even when the browser only logs "Failed to load resource" (e.g. a label font that is never found).
  page.on("response", (r) => { const u = new URL(r.url()); if (r.status() >= 400 && u.origin === new URL(BASE).origin && !u.pathname.startsWith("/api/")) erros.push("HTTP " + r.status() + " " + u.pathname); });
  return { browser, ctx, page, erros };
}
async function semTransbordo(page, larguras, passos) {
  const ruins = [];
  for (const w of larguras) {
    await page.setViewportSize({ width: w, height: 900 });
    for (const passo of passos) { await passo(); await page.waitForTimeout(200);
      const [sw, iw] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]); if (sw > iw + 1) ruins.push(w + "px"); }
  }
  assert.deepStrictEqual(ruins, [], "transbordo horizontal em " + ruins.join(", "));
}
// A visible point of a feature: one that is not under the floating panel (the click must reach the map canvas).
const pontoDe = (page, camada) => page.evaluate((c) => {
  const m = window.Mapa.map, f = m.queryRenderedFeatures({ layers: [c] }), cv = m.getCanvas(), r = cv.getBoundingClientRect();
  for (let k = 0; k < f.length; k++) {
    const g = f[(Math.floor(f.length / 2) + k) % f.length].geometry, flat = []; (function w(a) { typeof a[0] === "number" ? flat.push(a) : a.forEach(w); })(g.coordinates);
    for (let j = 0; j < Math.min(flat.length, 12); j++) {
      const p = m.project(flat[Math.floor((flat.length * (j + 1)) / 13)]), x = r.left + p.x, y = r.top + p.y;
      if (p.x > r.width * 0.08 && p.y > r.height * 0.12 && p.x < r.width * 0.92 && p.y < r.height * 0.9 && x > 4 && y > 4 && x < innerWidth - 4 && y < innerHeight - 4 && document.elementFromPoint(x, y) === cv) return { x, y };      // longe das bordas: controles flutuantes e o rodapé do mapa não interceptam
    }
  }
  return null; }, camada);
module.exports = { assert, abrir, BASE, semTransbordo, pontoDe };
