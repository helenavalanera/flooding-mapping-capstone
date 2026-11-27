// Versão estática (Pages) + dados em outra origem (bucket): a raiz leva à landing, o painel tem só as quatro áreas do estudo e o mapa lê tiles, fragmentos,
// drenagem e mapa-base do bucket (com CORS e Range). PAGES e DADOS são as duas origens; sem rota /api/ em nenhuma delas.
const { assert, abrir } = require("./lib");
const PAGES = process.env.PAGES, DADOS = process.env.DADOS;
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1280, height: 900 } });
  const dadosOrigem = new URL(DADOS).origin, paginasOrigem = new URL(PAGES).origin, contagem = { dados: {}, paginas: {} };
  page.on("response", (r) => { const u = new URL(r.url()); const lado = u.origin === dadosOrigem ? "dados" : u.origin === paginasOrigem ? "paginas" : null; if (!lado) return;
    const k = /fase3\//.test(u.pathname) ? "fase3" : /drenagem\//.test(u.pathname) ? "drenagem" : /rs\.pmtiles/.test(u.pathname) ? "pmtiles" : "outros"; (contagem[lado][k] = contagem[lado][k] || {})[r.status()] = ((contagem[lado][k] || {})[r.status()] || 0) + 1; });
  // 1. a raiz é a landing
  await page.goto(PAGES); await page.waitForURL(/\/inicio\/$/, { timeout: 15000 }); assert.match(await page.innerText("h1"), /Como a chuva transforma o território/);
  // 2. um link antigo (?painel=1#...) segue para o painel, com o hash preservado
  await page.goto(PAGES + "?painel=1#poa/resultados"); await page.waitForURL(/painel\.html\?painel=1#poa\/resultados$/, { timeout: 15000 });
  await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  const abas = await page.evaluate(() => Array.from(document.querySelectorAll("#abas button")).map((b) => [b.dataset.aba, b.hidden]));
  assert.deepStrictEqual(abas, [["resultados", false], ["mapa", false], ["simulador", false], ["proveniencia", false]], "só as quatro áreas do estudo: " + JSON.stringify(abas));
  assert.strictEqual(await page.getAttribute("#abas [data-aba=resultados]", "aria-selected"), "true");
  // 3. sem hash, o painel estático abre em Resultados
  await page.goto(PAGES + "painel.html"); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  assert.strictEqual(await page.getAttribute("#abas [data-aba=resultados]", "aria-selected"), "true");
  assert.strictEqual(await page.evaluate(() => document.getElementById("vista-geral")), null, "não há visão geral que leia a API");
  // 4. um endereço de aba escondida cai em Resultados
  await page.goto(PAGES + "painel.html#poa/mobilidade"); await page.reload(); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  // 5. o simulador funciona sem servidor
  await page.click("[data-aba=simulador]"); await page.waitForSelector("#vista-simulador .rs-seletor"); assert.ok(await page.locator("#vista-simulador table").count() >= 3);
  // 6. mapa: mapa-base, camada de escoamento e drenagem vindos do bucket
  await page.click("[data-aba=mapa]"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 120000 });
  await page.waitForSelector("#dimensoes button[data-dim]", { timeout: 60000 });
  await page.click("[data-dim=B]"); await page.waitForFunction(() => window.Fase3 && window.Fase3.meta, null, { timeout: 90000 });
  await page.waitForFunction(() => window.Mapa.map.isStyleLoaded() && window.Mapa.map.queryRenderedFeatures({ layers: ["f3-p-c_m1_max"] }).length > 20, null, { timeout: 90000 });
  await page.click("[data-dim=D]"); await page.waitForFunction(() => window.Drenagem && window.Drenagem.meta, null, { timeout: 60000 });
  const d = contagem.dados, p = contagem.paginas;
  assert.ok(d.pmtiles && d.pmtiles[206] > 10, "o mapa-base vem do bucket por faixas de bytes: " + JSON.stringify(d.pmtiles));
  assert.ok(d.fase3 && d.fase3[200] > 5 && d.drenagem && d.drenagem[200] >= 1, "escoamento e drenagem vêm do bucket: " + JSON.stringify(d));
  assert.ok(!p.fase3 && !p.drenagem && !p.pmtiles, "nada dos dados é pedido à origem da interface: " + JSON.stringify(p));
  assert.deepStrictEqual(erros.filter((e) => !/\/api\/|previsao_72h\.json|bloqueios\.json/.test(e)), [], "console: " + erros.join(" | "));
  await browser.close(); console.log("estatico ok");
})().catch((e) => { console.error(e); process.exit(1); });
