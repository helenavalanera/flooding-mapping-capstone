// Camada E (GeoAI, fração construída estimada) no navegador: experimental, independente das dimensões A a D, com controle de visibilidade, opacidade, legenda e avisos.
const { assert, abrir, BASE } = require("./lib");
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } });
  const pedidos = []; page.on("response", (r) => { if (/\/geoai\//.test(r.url())) pedidos.push(r.status() + " " + new URL(r.url()).pathname); });
  await page.goto(BASE); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  await page.click("[data-aba=mapa]"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 90000 });
  await page.waitForFunction(() => /GeoAI/.test(document.getElementById("camadas").textContent), null, { timeout: 30000 });
  assert.strictEqual(await page.isChecked("input[data-camada=geoai_fracao_construida]"), false, "a camada E começa desligada"); assert.ok(await page.isHidden("#geoai-opcoes"));
  assert.deepStrictEqual(pedidos, [], "nada da camada E é baixado antes de ligá-la");
  assert.match(await page.innerText("label.camada:has(input[data-camada=geoai_fracao_construida])"), /E\. Fração construída estimada \(GeoAI, experimental\)[\s\S]*Experimental/);
  await page.click("input[data-camada=geoai_fracao_construida]"); await page.waitForSelector("#geoai-opcoes #geoai-opac", { timeout: 30000 });
  await page.waitForFunction(() => window.Geoai && window.Geoai.meta && window.Mapa.map.getLayer("geoai-e"), null, { timeout: 30000 });
  const painel = await page.innerText("#geoai-opcoes");
  for (const r of [/Experimental\./, /A Profill foi a referência e a fonte dos rótulos/, /não há validação independente contra dados de campo/, /transferência para outras áreas não foi testada/, /0,049 em blocos de 3 km e 0,052 no quadrante externo/, /não atingido: 57%/]) assert.match(painel, r);
  const leg = await page.innerText("#legenda-gl");
  for (const r of [/E\. Fração construída estimada \(GeoAI\)[\s\S]*Experimental/, /0% a 20% da célula construída/, /80% a 100% da célula construída/, /Não é impermeabilidade medida, coeficiente de escoamento, vazão nem ocorrência de alagamento/, /não entra no cálculo das dimensões A, B, C e D/]) assert.match(leg, r);
  assert.ok(pedidos.some((p) => /^200 \/geoai\/meta\.json/.test(p)) && pedidos.some((p) => /^200 \/geoai\/fracao_construida\.webp/.test(p)), "meta e imagem vêm de /geoai/: " + pedidos.join(", "));
  assert.strictEqual(await page.evaluate(() => window.Mapa.map.getLayoutProperty("geoai-e", "visibility")), "visible");
  assert.strictEqual(await page.evaluate(() => window.Fase3.meta), null, "a camada E é independente: não carrega os dados de escoamento"); assert.strictEqual(await page.evaluate(() => window.Drenagem.meta), null);
  // opacidade
  await page.fill("#geoai-opac", "40"); await page.waitForFunction(() => Math.abs(window.Mapa.map.getPaintProperty("geoai-e", "raster-opacity") - 0.4) < 1e-9, null, { timeout: 5000 });
  assert.match(await page.innerText("#geoai-opac-v"), /40%/);
  // ordem: por baixo das camadas de análise e do que o mapa-base escreve
  const ordem = await page.evaluate(() => { const ids = window.Mapa.map.getStyle().layers.map((l) => l.id); return { e: ids.indexOf("geoai-e"), sombra: ids.indexOf("sombra"), f3: ids.indexOf("f3-casing") }; });
  assert.ok(ordem.e === ordem.sombra + 1 && ordem.e < ordem.f3, "a camada E fica logo acima do relevo e abaixo das ruas e das análises: " + JSON.stringify(ordem));
  // ela aparece nas dimensões, sem índice, e desliga
  assert.match(await page.innerText("#dimensoes"), /E\s*GeoAI \(experimental\)/); assert.match(await page.innerText("#dimensoes"), /sem índice único/);
  await page.click("input[data-camada=geoai_fracao_construida]"); await page.waitForFunction(() => window.Mapa.map.getLayoutProperty("geoai-e", "visibility") === "none", null, { timeout: 5000 });
  assert.ok(await page.isHidden("#geoai-opcoes"));
  assert.deepStrictEqual(erros, [], "console: " + erros.join(" | "));
  await browser.close(); console.log("geoai ok");
})().catch((e) => { console.error(e); process.exit(1); });
