// Simulador de cenários de cálculo no navegador: escolha da chuva, faixas, comparação territorial e a mesma chuva no mapa e nos resultados.
const { assert, abrir, BASE, semTransbordo } = require("./lib");
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } });
  await page.goto(BASE + "#poa/simulador"); await page.waitForSelector("#vista-simulador .rs-seletor", { timeout: 30000 });
  assert.match(await page.innerText("#vista-simulador"), /Não é um simulador hidráulico/);
  assert.strictEqual(await page.getAttribute("#vista-simulador [data-p='30']", "aria-pressed"), "true");
  assert.match(await page.innerText("#sim-ctx"), /percentil 75/);
  const faixas = async () => (await page.locator("#vista-simulador section:nth-of-type(3) .rs-barra span:last-child").allInnerTexts());
  const f30 = await faixas(); assert.strictEqual(f30.length, 4);
  await page.click("#vista-simulador [data-p='20']"); await page.waitForFunction(() => /20 mm/.test(document.querySelector("#sim-ctx").textContent) && !/percentil 75/.test(document.querySelector("#sim-ctx").textContent));
  const f20 = await faixas(); assert.notDeepStrictEqual(f20, f30, "as faixas mudam com a chuva");
  assert.strictEqual(await page.evaluate(() => window.Resultados.P), 20, "mesma chuva dos Resultados");
  // bairro: valores crescem na proporção da chuva
  await page.selectOption("#sim-bairro", { index: 3 });
  const linha = (await page.locator("#sim-terr tbody tr:first-child td").allInnerTexts()).map((t) => Number(t.replace(/\./g, "").replace(",", ".")));
  assert.ok(Math.abs(linha[2] / linha[0] - 3) < 0.15, "30 mm = 3 x 10 mm no bairro (três algarismos): " + linha);
  // simulador -> mapa: a chuva escolhida chega ao mapa, com a camada de contribuição ligada
  await page.click("#sim-mapa"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 90000 });
  await page.waitForFunction(() => window.Fase3.meta && window.Fase3.estado.p === 20 && window.Mapa.marcadas.escoamento_fase3 === true, null, { timeout: 60000 });
  assert.match(await page.innerText("#dim-chuva"), /20 mm/); assert.match(await page.innerText("#legenda-gl"), /chuva de referência de 20 mm/);
  // mapa -> simulador: trocar a chuva no mapa muda a do simulador
  await page.selectOption("#f3-p", "10");
  await page.click("[data-aba=simulador]"); await page.waitForSelector("#vista-simulador [data-p='10'][aria-pressed=true]");
  // responsivo, sem erros de console
  await semTransbordo(page, [360, 768, 1280], [async () => { await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight)); }, async () => { await page.evaluate(() => window.scrollTo(0, 0)); }]);
  assert.deepStrictEqual(erros, [], "console: " + erros.join(" | "));
  await browser.close(); console.log("simulador ok");
})().catch((e) => { console.error(e); process.exit(1); });
