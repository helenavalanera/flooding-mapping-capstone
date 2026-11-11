// Fallback test: a browser WITHOUT WebGL must still offer the essentials in both territories (occurrences, closures, attention
// stretches, routes, selection). Only the relief and the tilted view are lost, and the page says so.
const { assert, abrir, BASE, semTransbordo } = require("./lib");
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } }, true);
  await page.goto(BASE); await page.waitForSelector("#vista-geral .pergunta");
  assert.strictEqual(await page.evaluate(() => window.Mapa.webglOk()), false, "o navegador de teste realmente não tem WebGL");
  await page.click("[data-aba=mapa]"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 60000 });
  assert.strictEqual(await page.evaluate(() => window.Mapa.motorNome), "leaflet", "motor 2D");
  assert.match(await page.innerText("#nota-relevo"), /não tem WebGL[\s\S]*as demais funções são as mesmas/);
  assert.ok(await page.isDisabled("#vista-3d") && await page.isDisabled("#exagero"));
  assert.match((await page.locator("#camadas label.inativa").allInnerTexts()).join(" "), /Relevo sombreado[\s\S]*Exige WebGL/);
  // Rio Grande do Sul: selecionar município e rodovia
  await page.waitForSelector(".leaflet-mun-pane path", { state: "attached", timeout: 30000 });
  assert.ok(await page.locator(".leaflet-mun-pane path").count() > 100, "municípios desenhados");
  await page.locator(".leaflet-mun-pane path").nth(5).dispatchEvent("click"); await page.waitForSelector("#contexto h3", { timeout: 8000 });
  assert.match(await page.innerText("#contexto"), /Malha rodoviária DAER|Sem malha DAER/);
  await page.waitForSelector(".leaflet-rod-pane path", { state: "attached", timeout: 30000 }); await page.locator(".leaflet-rod-pane path").nth(3).dispatchEvent("click");
  await page.waitForFunction(() => /Trecho selecionado/.test(document.getElementById("contexto").textContent), null, { timeout: 8000 });
  await page.selectOption("#cor-mun", "risco"); assert.match(await page.innerText("#legenda-gl"), /Sem estimativa \(não é risco baixo\)/);
  await page.check("[data-camada=trechos_criticos]"); await page.waitForSelector(".leaflet-crit-pane path", { state: "attached", timeout: 30000 });
  // Porto Alegre: risco por trecho, ocorrência, interdição e seleção de trecho
  await page.click("[data-territorio=poa]"); await page.waitForTimeout(2500);
  assert.match((await page.locator("#camadas label").allInnerTexts()).join(" "), /Risco estimado por trecho[\s\S]*Interdições confirmadas/);
  await page.fill("#poa-hora", "5"); await page.waitForFunction(() => /[+]5 h/.test(document.getElementById("poa-hora-rotulo").textContent), null, { timeout: 20000 });
  await page.waitForSelector(".leaflet-risco-pane path", { state: "attached", timeout: 30000 });
  await page.waitForSelector(".leaflet-occ-pane path", { state: "attached", timeout: 15000 }); await page.waitForSelector(".leaflet-int-pane path", { state: "attached", timeout: 15000 });
  await page.locator(".leaflet-risco-pane path").first().dispatchEvent("click");
  await page.waitForFunction(() => /Risco por hora/.test(document.getElementById("contexto").textContent), null, { timeout: 15000 });
  assert.match(await page.innerText("#contexto"), /não é probabilidade/);
  // rotas desenhadas no mapa 2D
  await page.click("[data-aba=mobilidade]"); await page.waitForSelector("#mapa-rotas.leaflet-container"); const mb = await page.locator("#mapa-rotas").boundingBox();
  await page.mouse.click(mb.x + mb.width / 2 + 30, mb.y + mb.height / 2 + 80); await page.mouse.click(mb.x + mb.width / 2 + 190, mb.y + mb.height / 2 - 70);
  await page.fill("#mob-saida", new Date(Date.now() - new Date().getTimezoneOffset() * 60000 + 3.5 * 3600000).toISOString().slice(0, 16)); await page.click("#mob-analisar");
  await page.waitForSelector("#mob-resultado table", { timeout: 60000 });
  await page.click("#mob-3d"); await page.waitForFunction(() => window.Mapa.rotas, null, { timeout: 15000 });
  assert.ok(await page.locator(".leaflet-rotas-pane path").count() >= 2, "rotas desenhadas no mapa 2D");
  // responsividade com o mapa 2D
  const passos = []; for (const ter of ["rs", "poa"]) passos.push(async () => { await page.click(`[data-territorio=${ter}]`); await page.click("[data-aba=mapa]"); });
  await semTransbordo(page, [360, 390, 768, 1024, 1400], passos);
  assert.deepStrictEqual(erros, [], "erros de console: " + erros.join(" | ")); await browser.close(); console.log("sem_webgl: ok");
})().catch((e) => { console.error("FALHOU:", e.message); process.exit(1); });
