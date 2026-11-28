// Camada de escoamento potencial (Fase 3) no navegador: ligar, selecionar um trecho, trocar pacote, grandeza e chuva, ausência de dados, limitações e responsividade.
const { assert, abrir, BASE, semTransbordo, pontoDe } = require("./lib");
const modoDeCor = (page, k) => page.evaluate((k) => { const e = document.getElementById("f3-modo-" + k); e.checked = true; e.dispatchEvent(new Event("change", { bubbles: true })); }, k);   // o modo de cor avançado fica num "Como ler"
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } });
  await page.goto(BASE); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  await page.click("[data-aba=mapa]"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 90000 });
  // a camada começa desligada: nenhum tile da Fase 3 é pedido antes
  await page.waitForSelector("button[data-dim=B]", { timeout: 30000 });
  assert.strictEqual(await page.getAttribute("button[data-dim=B]", "aria-pressed"), "false", "desligada por padrão");
  assert.ok(await page.isHidden("#f3-opcoes"), "sem painel enquanto desligada");
  await page.click("button[data-dim=B]");
  await page.waitForSelector("#f3-pacote", { timeout: 30000 });
  const painel = await page.textContent("#f3-opcoes");
  assert.match(painel, /Contribuição potencial estimada, condicionada a uma chuva hipotética/); assert.match(painel, /Não é previsão de alagamento/);
  assert.match(painel, /Chuva/); assert.match(painel, /não diferencia ruas/); assert.match(painel, /não há controle livre de precipitação/);
  assert.deepStrictEqual(await page.locator("#f3-p option").allInnerTexts(), ["10 mm", "20 mm", "30 mm"], "só as execuções do motor");
  const modos = await page.locator("#f3-opcoes .f3-radio").evaluateAll((l) => l.map((e) => e.textContent));
  assert.deepStrictEqual(modos.map((t) => t.trim()), ["Contribuição potencial acumulada", "Geração potencial local", "Indicador topográfico de retenção", "Cobertura dos dados"]);
  const leg = await page.innerText("#legenda-gl");
  assert.match(leg, /Contribuição potencial acumulada \(limite superior\) · Método 1 · chuva de referência de 30 mm/); assert.match(leg, /Zero \(nada escoa neste limite\)/); assert.match(leg, /Trecho sem dados disponíveis \(não é valor zero\)/);
  // a camada aproxima o mapa até o zoom em que os trechos existem
  await page.waitForFunction(() => window.Mapa.map.getZoom() >= 12.9, null, { timeout: 30000 });
  await page.evaluate(() => window.Mapa.map.jumpTo({ center: [-51.2, -30.05], zoom: 14, pitch: 0, bearing: 0 }));
  await page.waitForFunction(() => window.Mapa.map.isStyleLoaded() && window.Mapa.map.queryRenderedFeatures({ layers: ["f3-p-c_m1_max"] }).length > 50, null, { timeout: 60000 });
  // seleção de um trecho com dados
  const t = await pontoDe(page, "f3-p-c_m1_max"); assert.ok(t, "há trechos desenhados"); await page.mouse.click(t.x, t.y);
  await page.waitForSelector("#f3-trecho", { timeout: 20000 });
  let ctx = await page.textContent("#contexto");
  for (const r of [/Geração/, /Concentração/, /Topografia/, /Drenagem/, /—/, /Identificador:/, /Contribuição potencial estimada associada ao trecho/, /Volume potencial gerado localmente/, /Área contribuinte/, /cobertura do pacote/, /Indicador topográfico de retenção/]) assert.match(ctx, r);
  assert.strictEqual(await page.locator("#f3-trecho .sel-ind").count(), 4, "grade com quatro indicadores"); assert.ok(await page.locator("#f3-trecho .sel-rua").innerText(), "nome da rua em destaque");
  assert.match(ctx, /m³/); assert.match(ctx, /Não somar com outros trechos/); assert.ok(!/transportado/i.test(ctx));
  assert.strictEqual(await page.locator("#f3-trecho details").count(), 1, "explicações em um único detalhe secundário");
  const n = await page.getAttribute("#f3-trecho", "data-n"); const antes = await page.innerText("#f3-trecho .f3-ind .f3-val");
  // método e cenário: o painel do trecho acompanha, sem recarregar a seleção
  await page.selectOption("#f3-pacote", "an"); await page.waitForTimeout(300);
  assert.strictEqual(await page.getAttribute("#f3-trecho", "data-n"), n); assert.match(await page.textContent("#contexto"), /Método 2/);
  assert.match(await page.innerText("#legenda-gl"), /Método 2/); assert.match(await page.textContent("#f3-pacote-nota"), /hipótese declarada/i);
  await page.click("#f3-metodo summary"); await page.click("#f3-hipoteses summary"); assert.match(await page.innerText("#f3-hipoteses"), /envelope/i); assert.match(await page.innerText("#f3-hipoteses"), /Fração hipotética de piso[\s\S]*25%[\s\S]*50%[\s\S]*75%/);
  assert.match(await page.innerText("#f3-hipoteses"), /0,225 a 0,8/);
  const prop = await page.evaluate(() => window.Fase3.estilo().prop); assert.strictEqual(prop, "c_an_max");
  // trocar de pacote só alterna qual camada está opaca (não recria nem reprocessa os tiles)
  const opacidades = () => page.evaluate(() => { const m = window.Mapa.map, o = {}; m.getStyle().layers.filter((l) => l.id.startsWith("f3-p-")).forEach((l) => { o[l.id] = m.getPaintProperty(l.id, "line-opacity"); }); return o; });
  const op = await opacidades(); assert.deepStrictEqual(Object.keys(op).sort(), ["f3-p-c_an_max", "f3-p-c_an_min", "f3-p-c_li_max", "f3-p-c_li_min", "f3-p-c_m1_max", "f3-p-c_m1_min"]);
  assert.deepStrictEqual(Object.keys(op).filter((k) => op[k] === 1), ["f3-p-c_an_max"], "uma só camada opaca");
  await page.selectOption("#f3-limite", "min"); assert.strictEqual(await page.evaluate(() => window.Fase3.estilo().prop), "c_an_min");
  await page.selectOption("#f3-pacote", "li"); assert.match(await page.textContent("#f3-pacote-nota"), /não é previsão|não é uma estimativa/i); assert.match(await page.textContent("#contexto"), /limite matemático/);
  await page.selectOption("#f3-pacote", "m1");
  const valor30 = await page.innerText("#f3-trecho .f3-ind .f3-val"); await page.selectOption("#f3-p", "20"); await page.waitForTimeout(300);
  const valor60 = await page.innerText("#f3-trecho .f3-ind .f3-val"); assert.notStrictEqual(valor30, valor60, "a chuva de referência muda os volumes"); assert.match(await page.innerText("#legenda-gl"), /20 mm/);
  // grandezas: cada uma com a sua legenda e sem pacote ou chuva quando não se aplicam
  await modoDeCor(page, "tp");
  await page.waitForFunction(() => window.Mapa.map.getStyle().layers.filter((l) => l.id.startsWith("f3-p-")).map((l) => l.id).join() === "f3-p-tp");
  assert.match(await page.innerText("#legenda-gl"), /Indicador topográfico de retenção/); assert.match(await page.innerText("#legenda-gl"), /Sem preenchimento de depressão no modelo/); assert.ok(!/m³/.test(await page.innerText("#legenda-gl")));
  assert.strictEqual(await page.locator("#f3-pacote").count(), 0); assert.strictEqual(await page.locator("#f3-p").count(), 0);
  assert.match(await page.textContent("#f3-opcoes"), /[Nn]ão é profundidade, volume nem duração/);
  assert.strictEqual(await page.evaluate(() => window.Fase3.estilo().prop), "tp");
  await modoDeCor(page, "cb"); assert.match(await page.innerText("#legenda-gl"), /Cobertura dos dados: Método 1/); assert.strictEqual(await page.evaluate(() => window.Fase3.estilo().prop), "cb_m1");
  await modoDeCor(page, "l"); assert.match(await page.innerText("#legenda-gl"), /Geração potencial local/);
  await modoDeCor(page, "c");
  // ausência de dados: trecho sem dados aparece tracejado e o painel não mostra zero
  // metodologia e limitações acessíveis
  await page.evaluate(() => { document.getElementById("f3-metodo").open = true; }); const met = await page.innerText("#f3-metodo");
  for (const r of [/Como a chuva gera escoamento potencial/, /Como o relevo orienta o fluxo simulado/, /Como as células de 30 m são associadas aos trechos/, /contribuição de trechos diferentes não pode ser somada/, /não são volume efetivamente transportado/, /modelo de elevação de 30 m limita as depressões urbanas/, /drenagem cadastrada não representa capacidade hidráulica/, /chuva uniforme não diferencia eventos localizados/]) assert.match(met, r);
  // um trecho sem dados (achado nos fragmentos): o painel diz que não há dados e não mostra zero
  const idSem = await page.evaluate(async () => { const m = window.Fase3.meta; for (let k = 0; k < 173; k++) { const f = await fetch("fase3/detalhe/" + ("0000" + k).slice(-4) + ".json").then((r) => r.json()); const i = f.linhas.findIndex((l) => l[f.colunas.indexOf("l_m1_max")] === null); if (i >= 0) return f.primeiro_n + i; } return null; });
  assert.ok(idSem !== null, "há trechos sem dados no conjunto");
  await page.evaluate(async (n) => { const el = document.getElementById("contexto"); await window.Fase3.detalhe(n, el); }, idSem);
  const semTxt = await page.textContent("#contexto"); assert.match(semTxt, /—/); assert.match(semTxt, /que não é zero/); assert.strictEqual(await page.locator("#f3-trecho .sel-ind.sem").count(), 4, "os quatro indicadores mostram — (sem dado)");
  // responsividade: sem transbordo horizontal em celular, tablet e desktop, com o painel aberto
  await semTransbordo(page, [360, 768, 1280], [async () => { await page.evaluate(() => document.getElementById("f3-opcoes").scrollIntoView()); }]);
  await page.setViewportSize({ width: 360, height: 780 }); await page.waitForTimeout(300);
  assert.ok(await page.isVisible("#f3-opcoes"), "o painel segue visível no celular");
  // a camada se desliga e o painel some
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.click("button[data-dim=B]"); assert.ok(await page.isHidden("#f3-opcoes")); assert.ok(!/Escoamento potencial/.test(await page.innerText("#legenda-gl")) || !(await page.innerText("#legenda-gl")).includes("limite superior"));
  assert.strictEqual(JSON.stringify(erros), "[]", "sem erros no console nem respostas 4xx/5xx de arquivos nossos: " + JSON.stringify(erros));
  await browser.close();
  console.log("fase3 ok");
})().catch((e) => { console.error(e); process.exit(1); });
