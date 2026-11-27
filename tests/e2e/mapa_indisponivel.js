// Quando nem o MapLibre nem o Leaflet podem ser baixados, a aba Mapa explica o motivo e leva às alternativas que não precisam de WebGL; o resto do painel segue funcionando.
const { assert, abrir, BASE } = require("./lib");
(async () => {
  const { browser, ctx, page, erros } = await abrir({ viewport: { width: 1280, height: 900 } });
  await ctx.route(/cdnjs\.cloudflare\.com/, (r) => r.abort());                       // sem as bibliotecas do mapa (rede de terceiros bloqueada)
  await page.goto(BASE); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  const bibliotecas = await page.evaluate(() => ({ gl: !!window.maplibregl, leaflet: !!window.L }));
  assert.deepStrictEqual(bibliotecas, { gl: false, leaflet: false }, "as bibliotecas só carregam ao abrir o mapa");
  await page.click("[data-aba=mapa]"); await page.waitForSelector(".mapa-indisponivel", { timeout: 60000 });
  const txt = await page.innerText("#mapa-gl");
  assert.match(txt, /O mapa interativo não pôde ser exibido/); assert.match(txt, /Motivo:/); assert.match(txt, /aceleração gráfica \(WebGL\)/);
  assert.match(txt, /mapas de manchas das dimensões A a E são imagens, sem WebGL/);
  assert.strictEqual(await page.getAttribute(".mapa-indisponivel a[href='inicio/#dimensoes']", "href"), "inicio/#dimensoes");
  assert.ok(await page.isVisible("#banner"), "o aviso do topo também diz que não foi possível iniciar o mapa");
  await page.click("[data-aba=resultados]"); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 30000 });
  assert.ok(await page.isVisible("#vista-resultados"));
  await page.goto(BASE + "inicio/"); assert.ok(await page.locator("#dimensoes img").first().isVisible());
  assert.strictEqual(await page.evaluate(() => !!window.maplibregl), false);
  const relevantes = erros.filter((e) => !/cdnjs|ERR_FAILED|Failed to load resource|Não foi possível carregar/.test(e));
  assert.deepStrictEqual(relevantes, [], "console: " + relevantes.join(" | "));
  await browser.close(); console.log("mapa_indisponivel ok");
})().catch((e) => { console.error(e); process.exit(1); });
