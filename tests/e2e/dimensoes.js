// Dimensões de análise do mapa (A geração, B contribuição, C topografia, D drenagem): independentes, sem índice composto, sem carga antecipada.
const { assert, abrir, BASE, semTransbordo } = require("./lib");
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } });
  const f3 = []; page.on("request", (r) => { if (/\/fase3\//.test(r.url())) f3.push(r.url()); });
  await page.goto(BASE + "#poa/mapa"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 90000 });
  await page.waitForSelector("button[data-dim]");
  assert.deepStrictEqual(await page.locator("button[data-dim]").evaluateAll((b) => b.map((x) => x.dataset.dim)), ["A", "B", "C", "D", "E"]);   // E: camada experimental de GeoAI, independente
  assert.strictEqual(f3.length, 0, "nenhum dado da Fase 3 antes de escolher uma dimensão");
  assert.strictEqual(await page.locator("button[data-dim][aria-pressed=true]").count(), 0, "começa sem dimensão ligada");
  // A: geração local
  await page.click("[data-dim=A]"); await page.waitForSelector("#f3-pacote");
  assert.strictEqual(await page.getAttribute("[data-dim=A]", "aria-pressed"), "true");
  assert.strictEqual(await page.evaluate(() => window.Fase3.estado.modo), "l"); assert.match(await page.innerText("#legenda-gl"), /Geração potencial local/);
  await page.waitForSelector("#f3-chuva-nota", { state: "attached" }); assert.strictEqual(await page.inputValue("#f3-p"), "30"); const chuva = await page.textContent("#f3-chuva-nota");
  assert.match(chuva, /30 mm/); assert.match(chuva, /percentil 75/); assert.match(chuva, /não a média/); assert.match(chuva, /Cenário de cálculo, não previsão/);
  // B troca A (mesma camada de cor): uma grandeza por vez
  await page.click("[data-dim=B]"); await page.waitForFunction(() => /Contribuição potencial acumulada/.test(document.getElementById("legenda-gl").textContent));
  assert.strictEqual(await page.getAttribute("[data-dim=A]", "aria-pressed"), "false"); assert.strictEqual(await page.getAttribute("[data-dim=B]", "aria-pressed"), "true");
  assert.match(await page.textContent("#f3-opcoes"), /contribuição potencial, não vazão/);
  const oficial = { A: /Quanto da chuva pode se transformar em água que escoa pela superfície \(geração de escoamento superficial\)\./, B: /Para onde a água que escoa tende a convergir pelo território \(concentração de escoamento superficial\)\./, C: /Onde o relevo apresenta condições mais favoráveis à retenção de água \(propensão topográfica à retenção\)\./, D: /Onde estão localizados os dispositivos e as redes de drenagem cadastrados \(infraestrutura de drenagem\)\./ };
  for (const k of Object.keys(oficial)) assert.match(await page.getAttribute(`[data-dim=${k}]`, "title"), oficial[k], "texto oficial da dimensão " + k);
  assert.strictEqual(await page.locator("#f3-opcoes details#f3-metodo").count(), 1, "a explicação metodológica fica em detalhe complementar");
  // D é independente: sobrepõe sem desligar B
  await page.click("[data-dim=D]"); await page.waitForSelector("#dren-opcoes input[data-dren]", { timeout: 30000 });
  assert.strictEqual(await page.getAttribute("[data-dim=B]", "aria-pressed"), "true"); assert.strictEqual(await page.getAttribute("[data-dim=D]", "aria-pressed"), "true");
  assert.match(await page.textContent("#dren-opcoes"), /não comprova conexão hidráulica/);
  // C: topografia não mostra chuva nem sugere profundidade
  await page.click("[data-dim=C]"); await page.waitForFunction(() => /topográfico/i.test(document.getElementById("legenda-gl").textContent));
  assert.strictEqual(await page.locator("#f3-p").count(), 0, "topografia não depende da chuva");
  assert.match(await page.textContent("#f3-opcoes"), /Não é profundidade de alagamento/); assert.match(await page.textContent("#f3-opcoes"), /Copernicus GLO-30/);
  // desligar a dimensão ativa devolve o mapa sem a camada
  await page.click("[data-dim=C]"); assert.ok(await page.isHidden("#f3-opcoes")); assert.strictEqual(await page.getAttribute("[data-dim=D]", "aria-pressed"), "true");
  // navegação: resultados e visão geral
  await page.click("[data-dim=A]");
  await page.evaluate(() => window.Mapa.map.jumpTo({ center: [-51.2, -30.05], zoom: 15 }));
  await page.click("#dim-geral"); await page.waitForFunction(() => window.Mapa.map.getZoom() < 14, null, { timeout: 20000 });
  await page.click(".sobre-mapa summary"); await page.click(".sobre-mapa a[href='#poa/resultados']"); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 20000 });
  await page.click("[data-aba=mapa]");
  // teclado e telas pequenas
  await page.focus("[data-dim=A]"); await page.keyboard.press("Enter"); assert.strictEqual(await page.evaluate(() => document.activeElement.dataset.dim), "A", "foco permanece após alternar");
  await semTransbordo(page, [360, 768, 1280], [async () => { await page.evaluate(() => document.getElementById("dimensoes").scrollIntoView()); }]);
  assert.deepStrictEqual(erros, [], "sem erros no console: " + erros.join(" | "));
  await browser.close(); console.log("dimensoes ok");
})().catch((e) => { console.error(e); process.exit(1); });
