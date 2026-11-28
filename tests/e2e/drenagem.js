// Inventário de drenagem (Fase 2) no navegador: contexto, independente do cálculo; categorias distintas; registro com atributos originais e ausência explícita.
const { assert, abrir, BASE, semTransbordo } = require("./lib");
// Um ponto da tela, fora do painel, onde a camada tem feição sob o cursor (varre a área do mapa; linhas finas não se acham pelos vértices).
const pontoSobre = (page, camadas, evitar = []) => page.evaluate(([cs, ev]) => {
  const m = window.Mapa.map, cv = m.getCanvas(), r = cv.getBoundingClientRect(), pts = ev.filter((id) => m.getLayer(id));
  for (let y = 80; y < r.height - 40; y += 7) for (let x = 40; x < Math.min(r.width - 420, 900); x += 7)
    if (m.queryRenderedFeatures([[x - 3, y - 3], [x + 3, y + 3]], { layers: cs }).length && !(pts.length && m.queryRenderedFeatures([[x - 10, y - 10], [x + 10, y + 10]], { layers: pts }).length) && document.elementFromPoint(r.left + x, r.top + y) === cv) return { x: r.left + x, y: r.top + y };
  return null; }, [camadas, evitar]);
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } });
  await page.goto(BASE); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  await page.click("[data-aba=mapa]"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 90000 });
  await page.waitForSelector("button[data-dim=D]", { timeout: 30000 });
  assert.strictEqual(await page.getAttribute("button[data-dim=D]", "aria-pressed"), "false"); assert.ok(await page.isHidden("#dren-opcoes"));
  await page.click("button[data-dim=D]"); await page.waitForSelector("#dren-opcoes input[data-dren]", { timeout: 30000 });
  const painel = await page.textContent("#dren-opcoes");
  assert.match(painel, /mostra o que está registrado, não o que funciona/); assert.match(painel, /não entra no cálculo de escoamento potencial/); assert.match(painel, /Rede pluvial[\s\S]*135\.856/);
  const leg = await page.innerText("#legenda-gl");
  for (const r of [/Cadastro existente \(linha\)/, /Registro sem acesso \(linha\)/, /Cadastrado como não interligado \(linha\)/, /Registro duplicado \(fora do inventário\)/, /Poço de visita \(ponto\)/, /Boca de lobo \(ponto\)/, /Casa de bomba \(ponto\)/, /nunca como zero/]) assert.match(leg, r);
  // a camada e a da Fase 3 convivem sem se misturar: a legenda de uma não aparece na outra
  assert.ok(!/Escoamento potencial|Contribuição potencial/.test(leg));
  await page.evaluate(() => window.Mapa.map.jumpTo({ center: [-51.2, -30.05], zoom: 16, pitch: 0, bearing: 0 }));
  await page.waitForFunction(() => window.Mapa.map.isStyleLoaded() && window.Mapa.map.queryRenderedFeatures({ layers: ["dren-rede-0"] }).length > 20, null, { timeout: 90000 });
  const r = await pontoSobre(page, ["dren-rede-0"], ["dren-pocos", "dren-bocas", "dren-bombas"]); assert.ok(r, "há trecho de rede sem ponto por cima"); await page.mouse.click(r.x, r.y);
  await page.waitForSelector("#dren-registro", { timeout: 20000 });
  let ctx = await page.innerText("#contexto");
  assert.match(ctx, /Trecho de rede pluvial/); assert.match(ctx, /Registro do cadastro, não funcionamento/); assert.match(ctx, /Categoria no cadastro[\s\S]*Cadastro existente/); assert.match(ctx, /Qualidade do registro/);
  assert.match(ctx, /Marcado como ativo no cadastro/); assert.ok(!/capacidade de vazão:|funcionando|eficiência:/i.test(ctx.replace(/Não indica capacidade de vazão[^.]*\./i, "")));
  await page.click("#dren-registro details:last-of-type summary"); ctx = await page.innerText("#dren-registro");
  for (const c of ["id_origem", "camada_origem", "diametro", "material", "usar_no_inventario", "evidencia_geometrica_ambos_extremos_ligados"]) assert.ok(ctx.includes(c), "atributo original " + c);
  assert.match(ctx, /não informado/, "atributo ausente aparece como não informado"); assert.ok(!/\bNaN\b|undefined|null/.test(ctx));
  assert.match(ctx, /diametro[\s\S]*mm[\s\S]*unidade inferida/);
  // grupos: desligar a rede esconde as linhas e mantém os pontos; religar volta
  await page.uncheck("#dren-opcoes input[data-dren=rede]");
  assert.strictEqual(await page.evaluate(() => window.Mapa.map.getLayoutProperty("dren-rede-0", "visibility")), "none"); assert.ok(!/Cadastro existente/.test(await page.innerText("#legenda-gl")));
  await page.check("#dren-opcoes input[data-dren=rede]"); assert.strictEqual(await page.evaluate(() => window.Mapa.map.getLayoutProperty("dren-rede-0", "visibility")), "visible");
  // ponto: poço de visita
  await page.evaluate(() => window.Mapa.map.jumpTo({ center: [-51.2, -30.05], zoom: 17, pitch: 0 }));
  await page.waitForFunction(() => window.Mapa.map.isStyleLoaded() && window.Mapa.map.queryRenderedFeatures({ layers: ["dren-pocos"] }).length > 3, null, { timeout: 90000 });
  const p = await pontoSobre(page, ["dren-pocos"]); assert.ok(p, "há poços de visita"); await page.mouse.click(p.x, p.y);
  await page.waitForFunction(() => /Poço de visita|Boca de lobo|Trecho de rede/.test(document.getElementById("contexto").textContent), null, { timeout: 20000 });
  // responsividade e desligar
  await semTransbordo(page, [360, 768, 1280], [async () => { await page.evaluate(() => document.getElementById("dren-opcoes").scrollIntoView()); }]);
  await page.setViewportSize({ width: 1400, height: 900 }); await page.click("button[data-dim=D]"); assert.ok(await page.isHidden("#dren-opcoes"));
  assert.strictEqual(JSON.stringify(erros), "[]", "sem erros no console nem 4xx/5xx de arquivos nossos: " + JSON.stringify(erros));
  await browser.close(); console.log("drenagem ok");
})().catch((e) => { console.error(e); process.exit(1); });
