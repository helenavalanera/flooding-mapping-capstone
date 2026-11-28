// Fallback: um navegador SEM WebGL ainda abre o painel de Porto Alegre, com o mapa-base em 2D. As camadas de análise (escoamento potencial e drenagem
// cadastrada, em tiles vetoriais) e o relevo exigem WebGL, e a página diz isso em vez de esconder. O roteiro do mapa 2D com as camadas estaduais, de
// ocorrências e de rotas está arquivado em tests/e2e/arquivo/painel_estadual_sem_webgl.js.
const { assert, abrir, BASE, semTransbordo } = require("./lib");
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } }, true);
  await page.goto(BASE); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  assert.strictEqual(await page.evaluate(() => window.Mapa.webglOk()), false, "o navegador de teste realmente não tem WebGL");
  await page.click("[data-aba=mapa]"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 60000 });
  assert.strictEqual(await page.evaluate(() => window.Mapa.motorNome), "leaflet", "motor 2D");
  assert.match(await page.textContent("#nota-relevo"), /não tem WebGL[\s\S]*as demais funções são as mesmas/);
  assert.ok(await page.isDisabled("#vista-3d") && await page.isDisabled("#exagero"));
  assert.match(await page.innerText("#camadas"), /Relevo sombreado[\s\S]*Exige WebGL/); assert.ok(await page.isDisabled("#camadas input[data-camada=relevo]"));
  assert.ok(await page.isVisible("#aviso-webgl") && /Exige WebGL/.test(await page.innerText("#aviso-webgl")), "o motivo aparece uma vez");
  for (const d of ["A", "B", "C", "D", "E"]) assert.ok(await page.isDisabled(`button[data-dim=${d}]`), "dimensão " + d + " desativada sem WebGL");
  assert.ok(await page.isHidden("#f3-opcoes") && await page.isHidden("#dren-opcoes"));
  assert.ok(await page.isHidden("#grupo-legenda"), "sem camada ativa, sem legenda");
  assert.ok(await page.locator(".leaflet-container").count() >= 1, "o mapa-base 2D está desenhado");
  assert.strictEqual(await page.locator(".leaflet-mun-pane, .leaflet-rod-pane, .leaflet-risco-pane, .leaflet-occ-pane, .leaflet-rotas-pane").count(), 0, "nenhuma camada estadual, de ocorrências ou de rotas");
  const passos = ["resultados", "mapa", "simulador", "proveniencia"].map((aba) => async () => { await page.click(`[data-aba=${aba}]`); });
  await semTransbordo(page, [360, 390, 768, 1024, 1400], passos);
  assert.deepStrictEqual(erros, [], "erros de console: " + erros.join(" | ")); await browser.close(); console.log("sem_webgl: ok");
})().catch((e) => { console.error("FALHOU:", e.message); process.exit(1); });
