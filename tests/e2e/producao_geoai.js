// Produção com a camada E publicada em prefixo PRÓPRIO (geoai-<hash>/): Pages com CSP do _headers + R2 simulado. Confere URL, hash do meta conferido pela página, imagem, CORS/CSP, convivência
// com escoamento e drenagem (versão principal), cabeçalhos e ausência de erros.
const { chromium } = require(process.env.PLAYWRIGHT_CORE); const assert = require("assert");
const PAGES = process.env.PAGES, R2 = process.env.R2, VERSAO = process.env.VERSAO, GEOAI = process.env.GEOAI;
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  if (process.env.PAGES_LOCAL) {   // o site (build de produção) é servido localmente, mas o navegador o enxerga na origem pública: o CORS e a CSP valem como em produção, e o R2 é o real
    await ctx.route(PAGES + "/**", async (route) => { const u = new URL(route.request().url()); const resp = await route.fetch({ url: process.env.PAGES_LOCAL + u.pathname + u.search }); await route.fulfill({ response: resp }); });
  }
  const page = await ctx.newPage(); page.setDefaultTimeout(120000);
  const erros = [], r2 = [], pend = [];
  await page.addInitScript(() => { window.__csp = []; document.addEventListener("securitypolicyviolation", (e) => window.__csp.push(e.violatedDirective + " " + e.blockedURI)); });
  page.on("pageerror", (e) => erros.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/GL Driver|amazonaws|ERR_NAME|Failed to load resource: net::ERR_(NAME|INTERNET|CONNECTION)/.test(m.text())) erros.push("console: " + m.text().slice(0, 200)); });
  page.on("response", (r) => { if (r.url().startsWith(R2)) pend.push((async () => r2.push({ u: r.url().slice(R2.length), s: r.status(), h: await r.allHeaders() }))()); });
  await page.goto(PAGES + "/painel.html#poa/mapa", { waitUntil: "load" });
  await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 150000 });
  const cfg = await page.evaluate(() => ({ geoai: FM_DADOS.geoai, h: FM_DADOS.meta_sha256.geoai, fase3: FM_DADOS.fase3 }));
  assert.strictEqual(cfg.geoai, `${R2}/${GEOAI}/geoai/`, "a camada E vem do prefixo próprio"); assert.ok(/^[0-9a-f]{64}$/.test(cfg.h)); assert.strictEqual(cfg.fase3, `${R2}/${VERSAO}/fase3/`, "a versão principal não muda");
  await page.waitForFunction(() => /GeoAI/.test(document.getElementById("camadas").textContent));
  assert.ok(!(await page.evaluate(() => /ainda não publicada/.test(document.getElementById("camadas").textContent))), "com a camada publicada, o aviso de ausência some");
  await page.click("#dimensoes button[data-dim=B]"); await page.waitForFunction(() => window.Fase3 && window.Fase3.meta);
  await page.click("#dimensoes button[data-dim=D]"); await page.waitForFunction(() => window.Drenagem && window.Drenagem.meta);
  await page.click("input[data-camada=geoai_fracao_construida]");
  await page.waitForFunction(() => window.Geoai && window.Geoai.meta && window.Mapa.map.getLayer("geoai-e") && window.Mapa.map.getLayoutProperty("geoai-e", "visibility") === "visible");
  await page.waitForTimeout(2500); await Promise.all(pend);
  const g = r2.filter((x) => x.u.startsWith("/" + GEOAI + "/"));
  assert.ok(g.some((x) => /geoai\/meta\.json$/.test(x.u) && x.s === 200) && g.some((x) => /fracao_construida\.webp$/.test(x.u) && x.s === 200), "meta e imagem pelo prefixo da E: " + JSON.stringify(g.map((x) => [x.u, x.s])));
  for (const x of g) { assert.ok(["*", PAGES].includes(x.h["access-control-allow-origin"]), "CORS: " + x.u); assert.ok(/immutable|max-age/.test(x.h["cache-control"] || ""), "cache: " + x.u); }
  assert.ok(g.find((x) => /\.webp$/.test(x.u)).h["content-type"] === "image/webp");
  assert.ok(r2.some((x) => x.u.startsWith("/" + VERSAO + "/fase3/") && x.s === 200) && r2.some((x) => x.u.startsWith("/" + VERSAO + "/drenagem/") && x.s === 200), "escoamento e drenagem seguem pela versão principal");
  assert.deepStrictEqual(await page.evaluate(() => window.__csp), [], "violações de CSP");
  assert.deepStrictEqual(erros, [], "erros: " + erros.join(" | "));
  await b.close(); console.log("producao_geoai ok", JSON.stringify({ geoai: g.length, r2: r2.length }));
})().catch((e) => { console.error(e); process.exit(1); });
