// Painel atual, restrito a Porto Alegre: quatro áreas (Resultados, Mapa, Simulador e Proveniência), sem território estadual, previsão, mobilidade nem ocorrências.
// O roteiro do painel de duas escalas está arquivado em tests/e2e/arquivo/painel_estadual.js.
const { assert, abrir, BASE, semTransbordo } = require("./lib");
const ESTADUAL = /rodovia|bloqueio|S2iD|DAER|CPRv|munic[ií]pio|Rio Grande do Sul|Risco estimado|Rotas da|Ocorr[eê]ncias|Interdi/i;
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } });
  await page.goto(BASE); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  // só as quatro áreas do estudo, e um único território
  const abas = await page.evaluate(() => Array.from(document.querySelectorAll("#abas button")).map((b) => [b.dataset.aba, b.hidden]));
  assert.deepStrictEqual(abas, [["resultados", false], ["mapa", false], ["simulador", false], ["proveniencia", false]]);
  assert.strictEqual(await page.locator("#territorios, #modo, [data-territorio], #vista-previsao, #vista-mobilidade, #vista-ocorrencias, #vista-geral").count(), 0);
  const sub = await page.innerText("#sub-territorio"); assert.match(sub, /Porto Alegre · escala municipal/); assert.doesNotMatch(sub, /Rio Grande do Sul/);
  assert.strictEqual(await page.getAttribute("#abas [aria-selected=true]", "data-aba"), "resultados");
  // mapa em 3D, com relevo
  await page.click("[data-aba=mapa]"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 60000 }); await page.waitForTimeout(2000);
  assert.ok(await page.evaluate(() => !!window.Mapa.map.getTerrain()), "relevo 3D ligado");
  assert.ok(await page.evaluate(() => window.Mapa.map.getPitch()) > 20, "mapa inclinado");
  const centro = await page.evaluate(() => window.Mapa.map.getCenter().toArray()); assert.ok(Math.abs(centro[0] + 51.22) < 0.1 && Math.abs(centro[1] + 30.03) < 0.1, "o mapa abre em Porto Alegre");
  const camadas = (await page.locator("#camadas label").allInnerTexts()).join(" | ");
  assert.match(camadas, /Relevo sombreado/); assert.match(camadas, /Drenagem cadastrada/); assert.match(camadas, /Escoamento potencial/); assert.doesNotMatch(camadas, ESTADUAL);
  assert.strictEqual(await page.locator("#camadas input[data-camada]").count(), 3, "só as camadas do estudo");
  assert.match(await page.innerText("#contexto"), /Ligue uma dimensão e clique em um trecho de rua/); assert.doesNotMatch(await page.innerText("#contexto"), ESTADUAL);
  assert.strictEqual(await page.locator("#poa-opcoes, #cores, #poa-hora").count(), 0, "sem controle de hora à frente nem de cores estaduais");
  // 2D sem relevo, 3D com exagero declarado
  await page.click("#vista-2d"); await page.waitForTimeout(1000);
  assert.strictEqual(await page.evaluate(() => window.Mapa.map.getTerrain()), null, "2D sem relevo"); assert.ok(await page.isDisabled("#exagero"));
  await page.click("#vista-3d"); await page.waitForTimeout(600); await page.selectOption("#exagero", "3");
  assert.strictEqual(await page.evaluate(() => window.Mapa.map.getTerrain().exaggeration), 3); assert.match(await page.innerText("#nota-relevo"), /apenas para visualização/);
  // proveniência: só as fontes do estudo, com a condição de uso, e o que cada dimensão é e não é
  await page.click("[data-aba=proveniencia]"); await page.waitForSelector("#vista-proveniencia table");
  const prov = await page.innerText("#vista-proveniencia");
  for (const t of ["Profill 2022", "Licença não confirmada", "Copernicus DEM GLO-30", "OpenStreetMap", "Open-Meteo", "O que cada dimensão do mapa é, e o que não é", "não afirma que as bases tenham licença aberta irrestrita", "não prevê alagamentos"]) assert.ok(prov.includes(t), t);
  assert.doesNotMatch(prov, /S2iD|DAER|CPRv|bloqueio|rodovia|Rio Grande do Sul/i);
  // endereço antigo de uma área que não existe mais cai em Resultados
  await page.goto(BASE + "#poa/mobilidade"); await page.reload(); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  assert.strictEqual(await page.getAttribute("#abas [aria-selected=true]", "data-aba"), "resultados");
  // responsividade nas quatro áreas
  const passos = ["resultados", "mapa", "simulador", "proveniencia"].map((aba) => async () => { await page.click(`[data-aba=${aba}]`); });
  await semTransbordo(page, [360, 390, 768, 1024, 1400], passos);
  assert.deepStrictEqual(erros, [], "erros de console: " + erros.join(" | ")); await browser.close(); console.log("dashboard: ok");
})().catch((e) => { console.error("FALHOU:", e.message); process.exit(1); });
