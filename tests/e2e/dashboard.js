const { assert, abrir, BASE, semTransbordo, pontoDe } = require("./lib");
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } });
  await page.goto(BASE); await page.waitForSelector("#vista-geral .pergunta");
  assert.strictEqual(await page.locator("#vista-geral .pergunta h2").count(), 5, "a visão geral responde às cinco perguntas");
  assert.strictEqual(await page.getAttribute("#territorios [aria-checked=true]", "data-territorio"), "rs");
  assert.strictEqual(await page.locator(".entrada").count(), 2, "acesso às duas demonstrações");
  // mapa estadual em 3D
  await page.click("[data-aba=mapa]"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 60000 }); await page.waitForTimeout(2000);
  assert.ok(await page.evaluate(() => !!window.Mapa.map.getTerrain()), "relevo 3D ligado");
  assert.ok(await page.evaluate(() => window.Mapa.map.getPitch()) > 20, "mapa inclinado");
  const inativas = (await page.locator("#camadas label.inativa").allInnerTexts()).join(" ");
  assert.match(inativas, /Risco estimado por trecho[\s\S]*Dados indisponíveis/); assert.match(inativas, /Rotas[\s\S]*Dados indisponíveis/);
  await page.evaluate(() => window.Mapa.map.jumpTo({ center: [-51.2, -29.8], zoom: 8, pitch: 50 })); await page.waitForTimeout(1800);
  const m = await pontoDe(page, "mun-fill"); await page.mouse.click(m.x, m.y); await page.waitForSelector("#contexto h3", { timeout: 8000 });
  const ctx = await page.innerText("#contexto"); assert.match(ctx, /Dados disponíveis/); assert.match(ctx, /Malha rodoviária DAER/); assert.match(ctx, /sem dado, não tráfego zero|Sem malha DAER/); assert.match(ctx, /Limitações/);
  const r = await pontoDe(page, "rod"); if (r) { await page.mouse.click(r.x, r.y); await page.waitForTimeout(800); assert.match(await page.innerText("#contexto"), /Trecho selecionado/); }
  await page.click("#vista-2d"); await page.waitForTimeout(1000);
  assert.strictEqual(await page.evaluate(() => window.Mapa.map.getTerrain()), null, "2D sem relevo"); assert.ok(await page.isDisabled("#exagero"));
  await page.click("#vista-3d"); await page.waitForTimeout(600); await page.selectOption("#exagero", "3");
  assert.strictEqual(await page.evaluate(() => window.Mapa.map.getTerrain().exaggeration), 3); assert.match(await page.innerText("#nota-relevo"), /apenas para visualização/);
  await page.selectOption("#cor-mun", "risco"); assert.match(await page.innerText("#legenda-gl"), /Sem estimativa \(não é risco baixo\)/);
  // Porto Alegre: transição, camadas, seleção de trecho
  await page.click("[data-territorio=poa]"); await page.waitForTimeout(3500);
  const centro = await page.evaluate(() => window.Mapa.map.getCenter().toArray()); assert.ok(Math.abs(centro[0] + 51.22) < 0.05 && Math.abs(centro[1] + 30.03) < 0.05, "voou para Porto Alegre");
  assert.match((await page.locator("#camadas label").allInnerTexts()).join(" "), /Risco estimado por trecho[\s\S]*Interdições confirmadas/);
  await page.fill("#poa-hora", "5"); await page.waitForFunction(() => /[+]5 h/.test(document.getElementById("poa-hora-rotulo").textContent), null, { timeout: 15000 }); await page.waitForTimeout(2500);
  await page.evaluate(() => window.Mapa.map.jumpTo({ center: [-51.2, -30.05], zoom: 13.5, pitch: 60 })); await page.waitForTimeout(2500);
  const t = await pontoDe(page, "poa-risco-prev"); assert.ok(t, "há trechos com risco estimado"); await page.mouse.click(t.x, t.y);
  await page.waitForFunction(() => /Risco por hora/.test(document.getElementById("contexto").textContent), null, { timeout: 10000 });
  assert.match(await page.innerText("#contexto"), /não é probabilidade/);
  // assistente contextual: perguntas sugeridas, resposta com a origem declarada
  await page.click("#contexto .assistente summary"); assert.strictEqual(await page.locator("#contexto .assistente [data-q]").count(), 3);
  await page.click("#contexto [data-q=por_que_atencao]");
  await page.waitForFunction(() => /Texto padrão|Reformulado/.test(document.querySelector("#contexto .resposta").textContent), null, { timeout: 30000 });
  assert.match(await page.innerText("#contexto .resposta"), /Por que este trecho está em atenção\?/);
  assert.doesNotMatch(await page.innerText("#contexto .resposta"), /segur[oa]\b/i);
  // mobilidade e rotas no mapa 3D
  await page.click("[data-aba=mobilidade]"); await page.waitForSelector("#mapa-rotas.leaflet-container"); const mb = await page.locator("#mapa-rotas").boundingBox();
  await page.mouse.click(mb.x + mb.width / 2 + 30, mb.y + mb.height / 2 + 80); await page.mouse.click(mb.x + mb.width / 2 + 190, mb.y + mb.height / 2 - 70);
  await page.fill("#mob-saida", new Date(Date.now() - new Date().getTimezoneOffset() * 60000 + 3.5 * 3600000).toISOString().slice(0, 16)); await page.click("#mob-analisar");
  await page.waitForSelector("#mob-resultado table", { timeout: 60000 }); assert.match(await page.innerText("#mob-resultado"), /exposição estimada/);
  // estado de interface sem chuva: a resposta real da análise, com a meteorologia marcada como indisponível no formato que o servidor produz
  // (a produção desse formato é coberta em tests/test_servico.py). Aqui só se confere o que a tela diz.
  await page.route("**/api/rotas", async (route) => {
    const r = await route.fetch(), j = await r.json();
    j.meteo = { indisponivel: true, ultima_atualizacao: "2026-11-10T09:00:00Z", total_na_janela_mm: null, maximo_hora_mm: null, horas: [] };
    j.alerta = { nivel: "sem_dados", titulo: "Sem dados meteorológicos", texto: "A meteorologia está indisponível agora.", motivos: [] };
    await route.fulfill({ response: r, json: j });
  });
  await page.click("#mob-analisar"); await page.waitForSelector("#mob-resultado .alerta.sem_dados", { timeout: 60000 });
  assert.match(await page.innerText("#mob-resultado"), /Chuva indisponível[\s\S]*não significa rota sem risco/); await page.unroute("**/api/rotas");
  await page.click("#mob-analisar"); await page.waitForSelector("#mob-resultado .alerta:not(.sem_dados)", { timeout: 60000 });

  await page.click("#mob-3d"); await page.waitForFunction(() => window.Mapa.rotas, null, { timeout: 15000 });
  assert.ok(await page.evaluate(() => window.Mapa.map.getSource("rotas")._data.features.length) >= 2, "rotas destacadas no mapa");
  // áreas por território: o que não existe diz que não existe
  await page.click("[data-territorio=rs]"); await page.click("[data-aba=mobilidade]"); await page.waitForTimeout(1200);
  assert.match(await page.innerText("#vista-mobilidade"), /Rotas: Dados indisponíveis/);
  await page.click("[data-aba=proveniencia]"); await page.waitForTimeout(1200); assert.match(await page.innerText("#vista-proveniencia"), /O que cada região oferece/); assert.match(await page.innerText("#vista-proveniencia"), /O que se pode e o que não se pode afirmar[\s\S]*Confronto com eventos documentados/);
  await page.click("[data-aba=ocorrencias]"); await page.waitForTimeout(1200); assert.match(await page.innerText("#vista-ocorrencias"), /S2iD/);
  // responsividade, nos dois territórios e nas seis áreas
  const passos = []; for (const ter of ["rs", "poa"]) for (const aba of ["geral", "mapa", "previsao", "mobilidade", "ocorrencias", "proveniencia"]) passos.push(async () => { await page.click(`[data-territorio=${ter}]`); await page.click(`[data-aba=${aba}]`); });
  await semTransbordo(page, [360, 390, 768, 1024, 1400], passos);
  assert.deepStrictEqual(erros, [], "erros de console: " + erros.join(" | ")); await browser.close(); console.log("dashboard: ok");
})().catch((e) => { console.error("FALHOU:", e.message); process.exit(1); });
