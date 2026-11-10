// Shared by the browser tests. Needs PLAYWRIGHT_CORE (path of playwright-core) and CHROME_PATH (a Chromium/Chrome binary).
const assert = require("assert");
const { chromium } = require(process.env.PLAYWRIGHT_CORE);
const BASE = process.env.BASE_URL || "http://127.0.0.1:8766/";
const ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"];   // WebGL without a GPU
async function abrir(opts) {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ARGS });
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage(), erros = [];
  page.setDefaultTimeout(90000);   // software WebGL (no GPU) renders the 3D map slowly
  page.on("console", (m) => { if (m.type() === "error" && !/tile\.openstreetmap|amazonaws|ERR_|Failed to load resource/.test(m.text())) erros.push(m.text().slice(0, 200)); });
  page.on("pageerror", (e) => erros.push("pageerror: " + e.message));
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
const pontoDe = (page, camada) => page.evaluate((c) => {
  const m = window.Mapa.map, f = m.queryRenderedFeatures({ layers: [c] }); if (!f.length) return null;
  const g = f[Math.floor(f.length / 2)].geometry, flat = []; (function w(a) { typeof a[0] === "number" ? flat.push(a) : a.forEach(w); })(g.coordinates);
  const p = m.project(flat[Math.floor(flat.length / 2)]), r = m.getCanvas().getBoundingClientRect(); return { x: r.left + p.x, y: r.top + p.y }; }, camada);
module.exports = { assert, abrir, BASE, semTransbordo, pontoDe };
