// A configuração de PRODUÇÃO funcionando de ponta a ponta contra a infraestrutura simulada: Pages (com a CSP do _headers) numa origem e o bucket do R2 (Range, gzip, CORS só para o site) em outra.
// Confere: URLs e hashes de integridade do config-dados.js, PMTiles por faixas (206), metadados conferidos por hash, tiles e fragmentos, CORS, CSP sem violações, erros de JavaScript,
// a camada E ausente sem afetar as outras, e os filtros (dimensão, pacote, limite, chuva) com atualização visual e dos resultados.
const { chromium } = require(process.env.PLAYWRIGHT_CORE); const assert = require("assert");
const PAGES = process.env.PAGES, R2 = process.env.R2, VERSAO = process.env.VERSAO;
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  if (process.env.PAGES_LOCAL) {   // o site (build de produção) é servido localmente, mas o navegador o enxerga na origem pública: o CORS e a CSP valem como em produção, e o R2 é o real
    await ctx.route(PAGES + "/**", async (route) => { const u = new URL(route.request().url()); const resp = await route.fetch({ url: process.env.PAGES_LOCAL + u.pathname + u.search }); await route.fulfill({ response: resp }); });
  }
  const page = await ctx.newPage(); page.setDefaultTimeout(120000);
  const erros = [], falhas = [], r2 = [], pend = [];
  await page.addInitScript(() => { window.__csp = []; document.addEventListener("securitypolicyviolation", (e) => window.__csp.push(e.violatedDirective + " " + e.blockedURI)); });
  page.on("pageerror", (e) => erros.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/GL Driver|amazonaws|ERR_NAME|Failed to load resource: net::ERR_(NAME|INTERNET|CONNECTION)/.test(m.text())) erros.push("console: " + m.text().slice(0, 200)); });
  page.on("requestfailed", (r) => { const msg = (r.failure() || {}).errorText || ""; if ((r.url().startsWith(R2) || r.url().startsWith(PAGES)) && !/ERR_ABORTED/.test(msg)) falhas.push(r.url() + " " + msg); });   // pedido cancelado pelo próprio mapa (tile que saiu da tela) não é falha
  page.on("response", (r) => { if (r.url().startsWith(R2)) pend.push((async () => r2.push({ u: r.url().slice(R2.length), s: r.status(), h: await r.allHeaders() }))()); });
  const resp = await page.goto(PAGES + "/painel.html#poa/mapa", { waitUntil: "load" });
  // CSP entregue pelo Pages deve liberar a origem do R2 só em connect-src e img-src
  const csp = (await resp.allHeaders())["content-security-policy"] || "";
  assert.ok(new RegExp("connect-src[^;]*" + R2.replace(/[.:\/]/g, "\\$&")).test(csp) && new RegExp("img-src[^;]*" + R2.replace(/[.:\/]/g, "\\$&")).test(csp), "CSP sem a origem do R2: " + csp);
  assert.ok(!new RegExp("(script-src|default-src)[^;]*" + R2.replace(/[.:\/]/g, "\\$&")).test(csp), "o R2 não pode valer em script-src nem default-src");
  await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 150000 });
  // configuração de produção
  const cfg = await page.evaluate(() => ({ fase3: FM_DADOS.fase3, drenagem: FM_DADOS.drenagem, geoai: FM_DADOS.geoai, mapa: FM_DADOS.mapa, versao: FM_DADOS.versao, h: FM_DADOS.meta_sha256 }));
  assert.strictEqual(cfg.fase3, `${R2}/${VERSAO}/fase3/`); assert.strictEqual(cfg.drenagem, `${R2}/${VERSAO}/drenagem/`); assert.strictEqual(cfg.mapa, `${R2}/${VERSAO}/mapa/poa.pmtiles`); assert.strictEqual(cfg.versao, VERSAO);
  assert.ok(/^[0-9a-f]{64}$/.test(cfg.h.fase3) && /^[0-9a-f]{64}$/.test(cfg.h.drenagem) && cfg.h.geoai === null && cfg.geoai === null, JSON.stringify(cfg));
  // mapa-base por faixas
  await page.waitForTimeout(1500); await Promise.all(pend);
  const pm = r2.filter((x) => /\.pmtiles/.test(x.u));
  assert.ok(pm.length > 10 && pm.every((x) => x.s === 206 && /^bytes \d+-\d+\/\d+$/.test(x.h["content-range"]) && x.h["accept-ranges"] === "bytes" && x.h["etag"] && x.h["access-control-allow-origin"] === PAGES), "PMTiles: " + JSON.stringify(pm.slice(0, 2)));
  // a camada E, ausente: desabilitada, com aviso, sem pedidos, e sem tirar as demais
  assert.strictEqual(await page.isDisabled("button[data-dim=E]"), true); assert.match(await page.getAttribute("button[data-dim=E]", "title"), /ainda não publicada neste ambiente/);
  assert.strictEqual(await page.locator("button[data-dim=E]:not([disabled])").count(), 0);
  // escoamento: metadados conferidos por hash, tiles e fragmentos
  await page.click("button[data-dim=B]"); await page.waitForFunction(() => window.Fase3 && window.Fase3.meta, null, { timeout: 150000 });
  assert.strictEqual(await page.evaluate(() => window.Fase3.erro), null);
  await page.waitForFunction(() => window.Mapa.map.isStyleLoaded() && window.Mapa.map.queryRenderedFeatures({ layers: ["f3-p-c_m1_max"] }).length > 20, null, { timeout: 150000 });
  await Promise.all(pend);
  const tiles = r2.filter((x) => /\/fase3\/tiles\//.test(x.u) && x.s === 200);
  assert.ok(tiles.length > 5 && tiles.every((x) => x.h["content-encoding"] === "gzip" && /immutable/.test(x.h["cache-control"]) && x.h["access-control-allow-origin"] === PAGES), "tiles: " + JSON.stringify(tiles.slice(0, 1)));
  const meta = r2.filter((x) => /meta\.json$/.test(x.u)); assert.ok(meta.length >= 1 && meta.every((x) => x.s === 200 && !/immutable/.test(x.h["cache-control"])), "meta.json revalidado: " + JSON.stringify(meta.map((x) => x.u)));
  // um trecho com contribuição positiva (o índice n depende da versão dos dados, por isso é procurado) e o fragmento de detalhe que o contém
  const n = await page.evaluate(async () => { for (let k = 5000; k < 9000; k++) { const r = await window.Fase3.fragmento(k); if (r && r.c_m1_max > 100) return k; } return null; });
  assert.ok(n !== null, "nenhum trecho com contribuição positiva entre os 4.000 primeiros");
  await page.evaluate((k) => window.Fase3.detalhe(k, document.getElementById("contexto")), n); await page.waitForFunction(() => /Identificador/.test(document.getElementById("contexto").innerText), null, { timeout: 30000 }); await Promise.all(pend);
  const frag = ("0000" + Math.floor(n / 1024)).slice(-4);
  assert.ok(r2.some((x) => new RegExp("/fase3/detalhe/" + frag + "\\.json$").test(x.u) && x.s === 200 && x.h["content-encoding"] === "gzip" && x.h["access-control-allow-origin"] === PAGES), "fragmento do detalhe " + frag);
  // filtros: dimensão, pacote, limite e chuva mudam o desenho e os resultados
  const estado = () => page.evaluate(() => ({ ...window.Fase3.estado, leg: document.getElementById("legenda-gl").innerText, ctx: document.getElementById("contexto").innerText, op: window.Mapa.map.getStyle().layers.filter((l) => /^f3-p-/.test(l.id)).map((l) => [l.id, window.Mapa.map.getPaintProperty(l.id, "line-opacity")]).filter((x) => x[1] === 1).map((x) => x[0]) }));
  const e0 = await estado(); assert.strictEqual(e0.modo, "c"); assert.ok(e0.op.length === 1 && /c_m1_max/.test(e0.op[0]), "uma camada opaca: " + JSON.stringify(e0.op));
  await page.selectOption("#f3-p", "10"); await page.waitForFunction(() => window.Fase3.estado.p === 10, null, { timeout: 15000 }); const e10 = await estado();
  await page.selectOption("#f3-p", "30"); await page.waitForFunction(() => window.Fase3.estado.p === 30, null, { timeout: 15000 }); const e30 = await estado();
  assert.ok(/10 mm/.test(e10.leg) && /30 mm/.test(e30.leg), "a legenda acompanha a chuva"); assert.notStrictEqual(e10.ctx, e30.ctx, "o resultado do trecho muda com a chuva");
  const v = (t) => Number(((t.match(/Concentração[\s\S]*?([\d.]+(?:,\d+)?)\s*a\s*([\d.]+(?:,\d+)?)/) || [])[2] || "0").replace(/\./g, "").replace(",", "."));
  assert.ok(v(e10.ctx) > 0 && Math.abs(v(e30.ctx) / v(e10.ctx) - 3) < 0.05, "30 mm = 3 x 10 mm no mesmo trecho: " + v(e10.ctx) + " e " + v(e30.ctx) + " | " + JSON.stringify(e10.ctx.slice(0, 400)));
  await page.selectOption("#f3-pacote", "an"); await page.waitForFunction(() => window.Fase3.estado.pacote === "an", null, { timeout: 15000 }); const ean = await estado();
  assert.ok(ean.op.length === 1 && /c_an_max/.test(ean.op[0]), "o pacote muda a camada desenhada: " + JSON.stringify(ean.op));
  await page.selectOption("#f3-limite", "min"); await page.waitForFunction(() => window.Fase3.estado.limite === "min", null, { timeout: 15000 }); const emin = await estado();
  assert.ok(emin.op.length === 1 && /c_an_min/.test(emin.op[0]), "o limite muda a camada desenhada: " + JSON.stringify(emin.op));
  await page.click("button[data-dim=C]"); await page.waitForFunction(() => window.Fase3.estado.modo === "tp", null, { timeout: 15000 }); const etp = await estado();
  assert.ok(etp.op.length === 1 && /topo|tp/.test(etp.op[0]) && /retenção|topogr/i.test(etp.leg), "a dimensão C muda o desenho e a legenda: " + JSON.stringify(etp.op));
  // drenagem
  await page.click("button[data-dim=D]"); await page.waitForFunction(() => window.Drenagem && window.Drenagem.meta, null, { timeout: 150000 }); assert.strictEqual(await page.evaluate(() => window.Drenagem.erro), null);
  await page.waitForFunction(() => window.Mapa.map.isStyleLoaded(), null, { timeout: 60000 }); await page.waitForTimeout(3000); await Promise.all(pend);
  assert.ok(r2.some((x) => /\/drenagem\/tiles\//.test(x.u) && x.s === 200) || r2.some((x) => /\/drenagem\/meta\.json$/.test(x.u) && x.s === 200), "drenagem do R2");
  // nada da camada E, nenhuma falha, nenhuma violação de CSP, nenhum erro
  assert.ok(!r2.some((x) => /\/geoai\//.test(x.u)), "a camada E ausente não gera pedidos");
  assert.deepStrictEqual(await page.evaluate(() => window.__csp), [], "violações de CSP");
  assert.deepStrictEqual(falhas, [], "requisições com falha (CORS, rede): " + falhas.join(" | "));
  assert.deepStrictEqual(erros, [], "erros de JavaScript e do console: " + erros.join(" | "));
  console.log("producao ok", JSON.stringify({ r2_requisicoes: r2.length, pmtiles_206: pm.length, tiles_gzip: tiles.length }));
  await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
