const { assert, abrir, BASE, semTransbordo } = require("./lib");
const PWA = BASE + "pwa/", CASA = { latitude: -30.1250, longitude: -51.2330 }, TRAB = { latitude: -30.0346, longitude: -51.2177 };
(async () => {
  const { browser, ctx, page, erros } = await abrir({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, geolocation: CASA, locale: "pt-BR" });
  const posts = [], chamadas = [];
  page.on("request", (r) => { if (r.url().includes("/api/")) { chamadas.push(r.method() + " " + r.url().split("/api/")[1].split("?")[0].split("/")[0]); if (r.postData()) posts.push(r.postData()); } });
  await page.addInitScript(() => { window.__geo = 0; const g = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation); navigator.geolocation.getCurrentPosition = (...a) => { window.__geo++; return g(...a); }; navigator.geolocation.watchPosition = () => { window.__watch = true; return 0; }; });
  await page.goto(PWA); await page.waitForSelector("[data-tela=avisos][aria-current=page]"); await page.click("[data-tela=planejar]"); await page.waitForSelector("#sel-o"); await page.waitForSelector("#cond h2", { timeout: 20000 });
  assert.match(await page.innerText(".vazio"), /Ainda não há lugares salvos/, "estado vazio com ação");
  assert.match(await page.innerText("#cond"), /Chuva nas próximas 24 h/, "condições consultadas antes de analisar");
  assert.ok(await page.evaluate(() => navigator.serviceWorker.ready.then((r) => !!r.active)), "service worker ativo");
  assert.strictEqual(await page.evaluate(() => typeof window.maplibregl), "undefined", "a biblioteca 3D só é baixada sob demanda");
  await page.click("#analisar"); assert.match(await page.innerText("#resultado"), /Falta a origem e o destino/);
  // consentimento explícito e lugares
  await page.click("[data-tela=lugares]"); await page.fill("#nome-lugar", "Casa"); await page.click("#lugar-gps"); await page.waitForSelector("#consentimento[open]");
  await ctx.grantPermissions(["geolocation"]); await page.click("#consentimento button[value=sim]"); await page.waitForFunction(() => /marcado/.test(document.getElementById("lugar-ponto").textContent)); await page.click("#lugar-salvar");
  await ctx.setGeolocation(TRAB); await page.fill("#nome-lugar", "Trabalho"); await page.click("#lugar-gps"); await page.waitForFunction(() => /marcado/.test(document.getElementById("lugar-ponto").textContent));
  assert.strictEqual(await page.evaluate(() => document.getElementById("consentimento").open), false, "o consentimento não é pedido de novo"); await page.click("#lugar-salvar");
  await page.selectOption("#tj-de", { label: "Casa" }); await page.selectOption("#tj-para", { label: "Trabalho" }); await page.fill("#tj-hora", "18:30"); await page.click("#tj-salvar");
  // avisos: áreas em exposição com pontos de interesse, lugares salvos (sem nome no envio) e o laço da comunidade
  await page.click("[data-tela=avisos]"); await page.waitForFunction(() => /Observado|Previsto|Nenhuma área|Chuva indisponível/.test(document.getElementById("av-bolsoes").textContent));
  assert.match(await page.innerText("#tela"), /não é alerta oficial/); assert.match(await page.innerText("#tela"), /199/);
  await page.click("#av-ver"); await page.waitForFunction(() => document.querySelectorAll("#av-lugares .av-lugar").length === 2);
  // território da Prefeitura: exposição lida por bairro e, com a folha recolhida, bairros e drenagem como camadas
  await page.click("#av-bar summary"); await page.waitForFunction(() => /Parcela das ruas|indisponível|Chuva indisponível/.test(document.getElementById("av-bairros").textContent));
  if (await page.$("[data-bairro]")) {
    assert.ok(/aglomerado|Atenção/.test(await page.innerText("#av-bairros")), "cada bairro traz a parcela exposta");
    await page.click("[data-bairro]"); await page.waitForFunction(() => document.querySelectorAll(".leaflet-overlay-pane path").length > 0);
    await page.click("#folha-alca"); await page.check("#av-cam-d"); await page.click("#folha-alca"); await page.click("#folha-alca"); await page.check("#av-cam-b");
    await page.waitForFunction(() => document.querySelectorAll(".leaflet-overlay-pane path").length > 50, null, { timeout: 15000 }); await page.click("[data-tela=avisos]");
  }
  const envioAvisos = posts.filter((b) => /"lugares"/.test(b)).pop(); assert.ok(envioAvisos && !/Casa|Trabalho/.test(envioAvisos), "o nome dos lugares não vai ao servidor");
  if (await page.$("[data-ver='0']")) { await page.click("[data-ver='0']"); await page.waitForFunction(() => document.querySelectorAll(".leaflet-overlay-pane path").length > 0); await page.click("[data-tela=avisos]"); }
  await page.waitForSelector("[data-ap]", { timeout: 20000 });   // a demonstração semeia relatos para a comunidade confirmar
  { await page.click("[data-ap][data-t=ainda]"); await page.waitForFunction(() => /apoio foi contado|já tinha sido contado/.test(document.getElementById("av-ap-msg").textContent)); }
  await page.evaluate(() => { document.getElementById("av-det").open = true; }); await page.waitForFunction(() => /Fonte:/.test(document.getElementById("av-sug").textContent));
  assert.ok(chamadas.includes("POST avisos") && chamadas.some((c) => c.startsWith("POST ocorrencias") || true), "chamou a API de avisos");
  // trajetos habituais: verificação sob demanda, sem guardar
  await page.click("[data-tela=planejar]"); await page.click("#verificar"); await page.waitForFunction(() => /Verificado só agora/.test(document.getElementById("verif").textContent), null, { timeout: 90000 });
  assert.match(await page.innerText("#verif"), /Não há monitoramento em segundo plano/); assert.ok(chamadas.filter((c) => c.startsWith("DELETE")).length >= 1, "a análise da verificação é apagada");
  await page.click("[data-traj]"); await page.waitForSelector("#resultado .decisao", { timeout: 90000 });
  // estado compacto: o mapa é protagonista e a folha mostra o essencial (tempo, distância, chegada, exposição, dados)
  assert.ok(await page.evaluate(() => document.getElementById("folha").classList.contains("compacta")), "folha compacta após a análise");
  assert.match(await page.innerText("#resultado .resumo"), /min[\s\S]*km[\s\S]*chegada prevista[\s\S]*(Chuva regional|Dados de chuva indisponíveis)/);
  assert.strictEqual(await page.evaluate(() => document.activeElement.id), "res-titulo", "o foco vai ao resultado");
  assert.match(await page.innerText("#orienta"), /Rota habitual · \d/); assert.ok(await page.isVisible("#perfil"), "perfil lateral da rota");
  assert.ok(!(await page.isVisible("#resultado .detalhe")), "os detalhes ficam recolhidos");
  assert.ok(await page.locator("[data-rota]").count() >= 2, "rota habitual e ao menos uma alternativa");
  assert.strictEqual(await page.locator("[data-rota]").first().getAttribute("data-rota"), "habitual");
  // expansão por botão, sem depender de arrastar; ordem: resultado, condições, rotas, trechos, ocorrências, explicação
  await page.click("#folha-alca"); assert.strictEqual(await page.getAttribute("#folha-alca", "aria-expanded"), "true"); assert.match(await page.innerText("#resultado"), /não gera instruções de manobra/);
  const titulos = await page.locator("#resultado h2").allInnerTexts();
  assert.strictEqual(titulos[1], "Condições · chuva na cidade", "as condições abrem os detalhes");
  assert.deepStrictEqual(titulos.slice(2), ["Rota e alternativas", "Trechos de atenção · Rota habitual", "Ocorrências no trajeto", "Entenda o resultado"], "ordem dos detalhes");
  assert.match(await page.innerText("#resultado"), /análise do modelo e não de um pluviômetro/); assert.match(await page.innerText("#resultado"), /uma série para a cidade inteira/); assert.match(await page.innerText("#resultado"), /Fonte: (Open-Meteo|SÉRIE SINTÉTICA)[\s\S]*válida por até 6 h/);
  assert.doesNotMatch(await page.innerText("#resultado") + await page.innerText("#orienta"), /é segura|sem risco\b/i, "nenhuma rota é chamada de segura");
  assert.strictEqual(await page.locator("#resultado [data-q]").count(), 4, "as quatro perguntas sugeridas");
  await page.click("#resultado [data-q=o_que_muda]"); await page.waitForFunction(() => /O que muda entre estas rotas\?/.test(document.getElementById("resposta").textContent), null, { timeout: 20000 });
  assert.doesNotMatch(await page.innerText("#resposta"), /segur[oa]\b/i);
  await page.click("#resultado [data-q=indisponivel]"); await page.waitForFunction(() => /indispon/i.test(document.getElementById("resposta").textContent), null, { timeout: 20000 });
  const segunda = await page.locator("[data-rota]").nth(1).getAttribute("data-rota");
  await page.locator("[data-rota]").nth(1).click(); assert.strictEqual(await page.locator("[data-rota][aria-pressed=true]").getAttribute("data-rota"), segunda);
  // controles flutuantes (visíveis com a folha compacta, sobre o mapa): camadas, legenda, relatar
  await page.click("#folha-alca");
  await page.click("#f-camadas"); assert.strictEqual(await page.locator("#popover input[data-cam]").count(), 7);
  assert.match(await page.innerText("#popover"), /Relato pendente[\s\S]*Interdição confirmada[\s\S]*Nunca indica rota segura/i); await page.click("#f-camadas"); assert.ok(!(await page.isVisible("#popover")));
  await page.click("#f-relatar"); assert.ok(await page.isVisible("#dica-mapa")); assert.match(await page.innerText("#tela"), /Relatar um problema na via/); await page.click("[data-tela=planejar]");
  assert.ok(!(await page.isVisible("#f-mais")), "em tela de toque o zoom é por pinça"); await page.click("#f-rota");
  // 3D opcional
  await page.click("#folha-alca"); await page.click("#ver3d"); await page.waitForFunction(() => window.maplibregl, null, { timeout: 30000 }); await page.waitForTimeout(3000);
  assert.strictEqual(await page.locator("#mapa3d canvas").count(), 1); await page.click("#fechar3d"); assert.ok(!(await page.isVisible("#vista3d")));
  // privacidade
  await page.click("[data-tela=privacidade]"); await page.click("#apagar"); await page.waitForTimeout(400);
  assert.strictEqual(await page.evaluate(() => localStorage.getItem("fm-pwa-v1")), null, "apagar remove tudo");
  assert.ok(!/Casa|Trabalho/.test(posts.join(" ")), "nomes de lugares nunca vão à rede"); assert.ok(await page.evaluate(() => window.__geo) <= 2); assert.ok(!(await page.evaluate(() => window.__watch)), "sem rastreamento contínuo");
  // offline
  // mapa-base: o service worker guarda as faixas do arquivo já vistas e as devolve sem rede (o que nunca foi visto fica em branco, sem quebrar nada)
  await page.reload(); await page.click("[data-tela=planejar]"); await page.waitForSelector("#sel-o"); await page.waitForTimeout(2500);
  const faixas = await page.evaluate(async () => { const n = (await caches.keys()).filter((k) => k.startsWith("fm-mapa-")); return n.length ? (await (await caches.open(n[0])).keys()).length : 0; });
  assert.ok(faixas > 0, "o service worker guarda as faixas já vistas do mapa-base (viu " + faixas + ")");
  await page.click("[data-tela=planejar]"); const antes = erros.length; await ctx.setOffline(true); await page.reload(); await page.click("[data-tela=planejar]"); await page.waitForSelector("#sel-o", { timeout: 15000 });
  assert.match(await page.innerText("#aviso"), /Sem conexão com o servidor de análise/);
  const offline = await page.evaluate(() => fetch("/mapa/rs.pmtiles?v=20261115", { headers: { Range: "bytes=0-16383" } }).then((r) => r.status, () => "falhou"));
  assert.strictEqual(offline, 206, "o cabeçalho do arquivo do mapa-base abre offline, vindo do cache"); await ctx.setOffline(false);
  erros.splice(antes, erros.length, ...erros.slice(antes).filter((e) => !/^TypeError: Failed to fetch\s+at FetchSource/.test(e)));   // só as faixas nunca vistas, e só enquanto estava sem rede
  const passos = ["avisos", "planejar", "lugares", "relatar", "privacidade"].map((t) => () => page.click(`[data-tela=${t}]`));
  await semTransbordo(page, [320, 360, 390, 430, 768, 1024, 1400], passos);
  assert.deepStrictEqual(erros, [], "erros de console: " + erros.join(" | ")); await browser.close(); console.log("pwa: ok");
})().catch((e) => { console.error("FALHOU:", e.message); process.exit(1); });
