// Aba Resultados no navegador: leitura executiva, chuva de referência, as quatro dimensões, cenários, síntese, rastreabilidade e responsividade.
const { assert, abrir, BASE, semTransbordo } = require("./lib");
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1300, height: 900 } });
  await page.goto(BASE + "?painel=1#poa/resultados"); await page.waitForSelector(".rs-achado", { timeout: 30000 });
  assert.strictEqual(await page.getAttribute("#abas [aria-selected=true]", "data-aba"), "resultados");
  assert.match(await page.innerText("#vista-resultados h1"), /quais contextos territoriais apresentam maior geração potencial de escoamento, concentração de contribuição e propensão topográfica à retenção/);
  assert.match(await page.innerText(".rs-topo"), /não identifica pontos de alagamento confirmado/);
  assert.strictEqual(await page.locator(".rs-achado").count(), 9); assert.strictEqual(await page.locator(".rs-achado[data-verificada=true]").count(), 9);
  for (const id of ["rs-chuva", "rs-A", "rs-B", "rs-C", "rs-D", "rs-cenarios", "rs-sintese", "rs-registro"]) assert.ok(await page.locator("#" + id).count(), id);
  // todos os títulos são conclusivos (nenhum genérico) e cada achado responde as cinco perguntas
  for (const t of await page.locator(".rs-achado h3").allInnerTexts()) assert.ok(t.length > 40 && !/^(Indicadores|Análise|Resultados gerais)/.test(t), t);
  assert.strictEqual(await page.locator(".rs-achado").first().locator(".rs-cinco h4").count(), 5);
  // chuva de referência: 30 mm é cenário ilustrativo, e as médias não se confundem
  const chuva = await page.innerText("#rs-chuva"); assert.match(chuva, /30 mm é um cenário operacional ilustrativo/); assert.match(chuva, /Não é a média histórica/); assert.match(chuva, /Média anual[\s\S]*Média mensal[\s\S]*Média diária[\s\S]*Média por dia com chuva[\s\S]*Por evento/);
  // trocar a chuva reescala os volumes (V = P x aeq / 1000) e mantém o resto
  const antes = await page.innerText("#rs-A .rs-grafico"); await page.click(".rs-seletor button[data-p='20']");
  assert.strictEqual(await page.getAttribute(".rs-seletor button[data-p='20']", "aria-pressed"), "true"); const depois = await page.innerText("#rs-A .rs-grafico");
  assert.notStrictEqual(antes, depois); assert.match(depois, /20 mm/); assert.match(await page.innerText("#rs-chuva"), /20 mm na série histórica[\s\S]*percentil/);
  assert.match(await page.innerText("#rs-cenarios"), /Como os resultados mudam sob 10, 20 e 30 mm/); assert.match(await page.innerText("#rs-cenarios"), /não indicam alagamento maior/);
  await page.click(".rs-seletor button[data-p='30']");
  // contextos territoriais: a métrica muda o ranking
  const r1 = await page.innerText(".rs-bairros"); await page.selectOption("#rs-metrica", "imperm"); assert.notStrictEqual(await page.innerText(".rs-bairros"), r1);
  // drenagem como contexto
  assert.match(await page.innerText("#rs-D"), /não indica capacidade de vazão, funcionamento, conectividade hidráulica nem eficiência/); assert.ok(!/entupid|funcionando/i.test(await page.innerText("#rs-D")));
  // síntese e rastreabilidade
  const sint = await page.innerText("#rs-sintese"); for (const t of ["O que esses resultados significam para o território?", "Contextos que merecem investigação prioritária (hipóteses)", "Lacunas de dados", "Limitações da drenagem cadastrada", "O que seria necessário para uma análise hidráulica de alagamentos"]) assert.ok(sint.includes(t), t);
  await page.click("#rs-registro summary"); const reg = await page.innerText("#rs-registro");
  for (const t of ["Fórmula", "Unidade", "Fonte", "Cenário", "Método", "Cobertura", "Limitações"]) assert.ok(reg.includes(t), t);
  assert.ok((await page.locator("#rs-registro .rs-dl").count()) >= 12);
  // responsividade
  await semTransbordo(page, [360, 390, 768, 1280], [async () => { await page.evaluate(() => scrollTo(0, 0)); }, async () => { await page.evaluate(() => document.getElementById("rs-C").scrollIntoView()); }, async () => { await page.evaluate(() => document.getElementById("rs-cenarios").scrollIntoView()); }]);
  assert.strictEqual(JSON.stringify(erros), "[]", "sem erros: " + JSON.stringify(erros));
  await browser.close(); console.log("resultados ok");
})().catch((e) => { console.error(e); process.exit(1); });
