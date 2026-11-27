// Cache do mapa: na segunda visita, o mapa-base (faixas Range do PMTiles), o relevo e os tiles de escoamento não vão à rede; sem a Cache API o mapa-base volta ao pedido normal.
const { chromium } = require(process.env.PLAYWRIGHT_CORE); const assert = require("assert");
const BASE = process.env.BASE_URL || "http://127.0.0.1:8766/", URL_MAPA = BASE + "?painel=1#poa/mapa?escoamento=1&p=30";
const ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"];
async function visita(ctx, semCache) {
  const p = await ctx.newPage(), n = { pmtiles: 0, tiles: 0, tilesRede: 0 }, pend = [];
  if (semCache) await p.addInitScript(() => { Object.defineProperty(window, "caches", { value: undefined }); });
  p.on("requestfinished", (rq) => { if (/\.pmtiles/.test(rq.url())) n.pmtiles++; if (/\/fase3\/tiles/.test(rq.url())) pend.push(rq.sizes().then((s) => { n.tiles++; if (s.responseBodySize > 0) n.tilesRede++; })); });
  const erros = []; p.on("pageerror", (e) => erros.push(e.message));
  await p.goto(URL_MAPA, { waitUntil: "load" }); await p.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 120000 });
  await p.waitForFunction(() => window.Fase3 && window.Fase3.meta, null, { timeout: 60000 }); await p.waitForFunction(() => window.Mapa.map.loaded(), null, { timeout: 120000 }).catch(() => {}); await p.waitForTimeout(2500); await Promise.all(pend);
  const fonte = await p.evaluate(async () => (typeof caches === "undefined" ? [] : await caches.keys()));
  await p.close(); return { ...n, erros, caches: fonte };
}
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ARGS });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  const v1 = await visita(ctx), v2 = await visita(ctx);
  assert.ok(v1.pmtiles > 10, "a primeira visita lê o mapa-base por faixas: " + JSON.stringify(v1));
  assert.ok(v1.caches.some((k) => /^fm-pmtiles-/.test(k)), "as faixas ficam na Cache API: " + JSON.stringify(v1.caches));
  assert.ok(v2.pmtiles <= Math.max(3, 0.1 * v1.pmtiles), "a segunda visita quase não faz pedidos Range ao mapa-base (só faixas que a primeira não leu): " + JSON.stringify([v1.pmtiles, v2.pmtiles]));
  assert.ok(v2.tiles > 0 && v2.tilesRede === 0, "os tiles de escoamento vêm do cache do navegador: " + JSON.stringify(v2));
  assert.deepStrictEqual([v1.erros, v2.erros], [[], []]);
  const ctx2 = await b.newContext({ viewport: { width: 1280, height: 900 } });                 // sem Cache API: o mapa funciona e volta a pedir as faixas
  const s1 = await visita(ctx2, true);
  assert.ok(s1.pmtiles > 10 && s1.erros.length === 0, "sem Cache API o mapa-base é lido como antes: " + JSON.stringify(s1));
  await b.close(); console.log("cache_mapa ok", JSON.stringify({ visita1: v1.pmtiles, visita2: v2.pmtiles, tiles2_rede: v2.tilesRede }));
})().catch((e) => { console.error(e); process.exit(1); });
