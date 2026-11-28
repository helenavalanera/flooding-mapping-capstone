// Mapa final: escoamento (B), drenagem (D) e GeoAI (E) juntos, o limite municipal, o alinhamento da imagem GeoAI e a navegação entre Mapa e Resultados, sem erros no console.
const { assert, abrir, BASE } = require("./lib");
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } });
  await page.goto(BASE + "?painel=1#poa/mapa"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 120000 });
  // navegação: no modo mapa as abas continuam visíveis
  assert.ok(await page.isVisible("#abas"), "as abas ficam visíveis no modo mapa");
  // escoamento + limite municipal
  await page.click("#dimensoes button[data-dim=B]"); await page.waitForFunction(() => window.Fase3 && window.Fase3.meta && window.Mapa.limite && window.Mapa.map.getLayer("limite-mascara"), null, { timeout: 120000 });
  assert.strictEqual(await page.evaluate(() => window.Mapa.map.getLayoutProperty("limite-mascara", "visibility")), "visible");
  assert.deepStrictEqual(await page.evaluate(() => [Mapa.dentroDePoa(-51.2177, -30.0346), Mapa.dentroDePoa(-51.18, -29.92)]), [true, false], "centro dentro, Canoas fora");
  // drenagem junto
  await page.click("#dimensoes button[data-dim=D]"); await page.waitForFunction(() => window.Drenagem && window.Drenagem.meta, null, { timeout: 120000 });
  // GeoAI junto, sem desligar as outras
  await page.click("input[data-camada=geoai_fracao_construida]"); await page.waitForFunction(() => window.Geoai && window.Geoai.meta && window.Mapa.map.getLayer("geoai-e") && window.Mapa.map.getLayoutProperty("geoai-e", "visibility") === "visible", null, { timeout: 60000 });
  const est = await page.evaluate(() => {
    const m = window.Mapa.map, ids = m.getStyle().layers.map((l) => l.id), meta = window.Geoai.meta, src = m.getSource("geoai-e") || m.getSource(m.getLayer("geoai-e").source);
    return { e: ids.indexOf("geoai-e"), f3: ids.indexOf("f3-casing"), mask: ids.indexOf("limite-mascara"), vis: m.getLayoutProperty("geoai-e", "visibility"), f3vis: m.getLayoutProperty("f3-casing", "visibility"), coords: src && src.coordinates, meta: meta.coordenadas, op: m.getPaintProperty("geoai-e", "raster-opacity") };
  });
  assert.ok(est.e < est.f3 && est.e < est.mask, "a GeoAI fica abaixo das ruas e do sombreado do município: " + JSON.stringify([est.e, est.f3, est.mask]));
  assert.deepStrictEqual(est.coords, est.meta, "a imagem é posicionada exatamente pelos cantos do meta.json");
  assert.ok(est.op > 0 && est.op < 1, "a camada é semitransparente (a base continua visível): " + est.op);
  // as outras camadas continuam ativas e os filtros funcionam com a E ligada
  await page.click("#dimensoes button[data-dim=B]");
  assert.strictEqual(await page.evaluate(() => window.Mapa.map.getLayoutProperty("geoai-e", "visibility")), "visible", "mudar de dimensão não desliga a E");
  // Resultados e volta ao mapa
  await page.click("[data-aba=resultados]"); await page.waitForSelector("#vista-resultados .rs-achado", { state: "visible", timeout: 30000 });
  await page.click("[data-aba=mapa]"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto && document.getElementById("vista-mapa") && !document.getElementById("vista-mapa").hidden, null, { timeout: 30000 });
  assert.deepStrictEqual(erros, [], "console: " + erros.join(" | "));
  await browser.close(); console.log("mapa_integrado ok");
})().catch((e) => { console.error(e); process.exit(1); });
