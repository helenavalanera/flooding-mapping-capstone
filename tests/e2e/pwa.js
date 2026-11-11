const { assert, abrir, BASE, semTransbordo } = require("./lib");
const PWA = BASE + "pwa/", CASA = { latitude: -30.1250, longitude: -51.2330 }, TRAB = { latitude: -30.0346, longitude: -51.2177 };
(async () => {
  const { browser, ctx, page, erros } = await abrir({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, geolocation: CASA, locale: "pt-BR" });
  const posts = [], chamadas = [];
  page.on("request", (r) => { if (r.url().includes("/api/")) { chamadas.push(r.method() + " " + r.url().split("/api/")[1].split("?")[0].split("/")[0]); if (r.postData()) posts.push(r.postData()); } });
  await page.addInitScript(() => { window.__geo = 0; const g = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation); navigator.geolocation.getCurrentPosition = (...a) => { window.__geo++; return g(...a); }; navigator.geolocation.watchPosition = () => { window.__watch = true; return 0; }; });
  await page.goto(PWA); await page.waitForSelector("#tela .passos"); await page.waitForSelector("#cond h2", { timeout: 20000 });
  assert.match(await page.innerText(".vazio"), /Ainda não há lugares salvos/, "estado vazio com ação");
  assert.match(await page.innerText("#cond"), /Chuva prevista nas próximas 24 h/, "condições consultadas antes de analisar");
  assert.ok(await page.evaluate(() => navigator.serviceWorker.ready.then((r) => !!r.active)), "service worker ativo");
  assert.strictEqual(await page.evaluate(() => typeof window.maplibregl), "undefined", "a biblioteca 3D só é baixada sob demanda");
  await page.click("#analisar"); assert.match(await page.innerText("#resultado"), /Falta a origem e o destino/);
  // consentimento explícito e lugares
  await page.click("[data-tela=lugares]"); await page.fill("#nome-lugar", "Casa"); await page.click("#lugar-gps"); await page.waitForSelector("#consentimento[open]");
  await ctx.grantPermissions(["geolocation"]); await page.click("#consentimento button[value=sim]"); await page.waitForFunction(() => /marcado/.test(document.getElementById("lugar-ponto").textContent)); await page.click("#lugar-salvar");
  await ctx.setGeolocation(TRAB); await page.fill("#nome-lugar", "Trabalho"); await page.click("#lugar-gps"); await page.waitForFunction(() => /marcado/.test(document.getElementById("lugar-ponto").textContent));
  assert.strictEqual(await page.evaluate(() => document.getElementById("consentimento").open), false, "o consentimento não é pedido de novo"); await page.click("#lugar-salvar");
  await page.selectOption("#tj-de", { label: "Casa" }); await page.selectOption("#tj-para", { label: "Trabalho" }); await page.fill("#tj-hora", "18:30"); await page.click("#tj-salvar");
  // trajetos habituais: verificação sob demanda, sem guardar
  await page.click("[data-tela=planejar]"); await page.click("#verificar"); await page.waitForFunction(() => /Verificado só agora/.test(document.getElementById("verif").textContent), null, { timeout: 90000 });
  assert.match(await page.innerText("#verif"), /Não há monitoramento em segundo plano/); assert.ok(chamadas.filter((c) => c.startsWith("DELETE")).length >= 1, "a análise da verificação é apagada");
  await page.click("[data-traj]"); await page.waitForSelector("#resultado .decisao", { timeout: 90000 });
  const titulos = await page.locator("#resultado h2").allInnerTexts();
  assert.strictEqual(titulos[0], "Condições · chuva na cidade", "primeiro as condições");
  assert.deepStrictEqual(titulos.slice(2), ["Rota e alternativas", "Trechos de atenção · Rota habitual", "Entenda o resultado"], "ordem: condições, resultado, rotas, trechos, explicação");
  assert.match(await page.innerText("#resultado"), /análise do modelo e não de um pluviômetro/); assert.match(await page.innerText("#resultado"), /uma série para a cidade inteira/);
  assert.strictEqual(await page.evaluate(() => document.activeElement.id), "res-titulo", "o foco vai ao resultado");
  assert.ok(await page.locator("[data-rota]").count() >= 2, "rota habitual e ao menos uma alternativa");
  assert.strictEqual(await page.locator("[data-rota]").first().getAttribute("data-rota"), "habitual");
  assert.doesNotMatch(await page.innerText("#resultado"), /é segura|sem risco\b/i, "nenhuma rota é chamada de segura");
  assert.strictEqual(await page.locator("#resultado [data-q]").count(), 4, "as quatro perguntas sugeridas");
  await page.click("#resultado [data-q=o_que_muda]"); await page.waitForFunction(() => /O que muda entre estas rotas\?/.test(document.getElementById("resposta").textContent), null, { timeout: 20000 });
  assert.doesNotMatch(await page.innerText("#resposta"), /segur[oa]\b/i);
  await page.click("#resultado [data-q=indisponivel]"); await page.waitForFunction(() => /indispon/i.test(document.getElementById("resposta").textContent), null, { timeout: 20000 });
  const segunda = await page.locator("[data-rota]").nth(1).getAttribute("data-rota");
  await page.locator("[data-rota]").nth(1).click(); assert.strictEqual(await page.locator("[data-rota].sel").getAttribute("data-rota"), segunda);
  // 3D opcional
  await page.click("#ver3d"); await page.waitForFunction(() => window.maplibregl, null, { timeout: 30000 }); await page.waitForTimeout(3000);
  assert.strictEqual(await page.locator("#mapa3d canvas").count(), 1); await page.click("#fechar3d"); assert.ok(!(await page.isVisible("#vista3d")));
  // privacidade
  await page.click("[data-tela=privacidade]"); await page.click("#apagar"); await page.waitForTimeout(400);
  assert.strictEqual(await page.evaluate(() => localStorage.getItem("fm-pwa-v1")), null, "apagar remove tudo");
  assert.ok(!/Casa|Trabalho/.test(posts.join(" ")), "nomes de lugares nunca vão à rede"); assert.ok(await page.evaluate(() => window.__geo) <= 2); assert.ok(!(await page.evaluate(() => window.__watch)), "sem rastreamento contínuo");
  // offline
  await page.click("[data-tela=planejar]"); await ctx.setOffline(true); await page.reload(); await page.waitForSelector("#tela .passos", { timeout: 15000 });
  assert.match(await page.innerText("#aviso"), /Sem conexão com o servidor de análise/); await ctx.setOffline(false);
  const passos = ["planejar", "lugares", "relatar", "privacidade"].map((t) => () => page.click(`[data-tela=${t}]`));
  await semTransbordo(page, [360, 390, 768, 1024, 1400], passos);
  assert.deepStrictEqual(erros, [], "erros de console: " + erros.join(" | ")); await browser.close(); console.log("pwa: ok");
})().catch((e) => { console.error("FALHOU:", e.message); process.exit(1); });
