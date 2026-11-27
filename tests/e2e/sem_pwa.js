// A aplicação atual não é um PWA: sem manifesto, sem botão de instalar, sem service worker (o antigo é removido) e sem rota para o app arquivado.
const { assert, abrir, BASE } = require("./lib");
(async () => {
  const { browser, ctx, page, erros } = await abrir({ viewport: { width: 1280, height: 800 } });
  // quem tinha a versão instalável recebe o cache antigo apagado
  await page.goto(BASE + "inicio/"); await page.evaluate(() => caches.open("fm-app-v1").then((c) => c.put("/x", new Response("antigo"))));
  await page.goto(BASE + "?painel=1#poa/resultados", { waitUntil: "load" }); await page.waitForSelector("#vista-resultados .rs-achado", { timeout: 60000 });
  await page.waitForFunction(() => caches.keys().then((k) => !k.includes("fm-app-v1")), null, { timeout: 15000 });
  const estado = await page.evaluate(async () => ({ manifesto: !!document.querySelector("link[rel=manifest]"), instalar: !!document.getElementById("instalar"), faixas: !!document.getElementById("aviso-conexao") || !!document.getElementById("aviso-versao"),
    registros: (await navigator.serviceWorker.getRegistrations()).length, caches: await caches.keys() }));
  assert.deepStrictEqual([estado.manifesto, estado.instalar, estado.faixas, estado.registros], [false, false, false, 0], JSON.stringify(estado));
  assert.ok(!estado.caches.some((k) => k.indexOf("fm-app-") === 0), "cache antigo apagado: " + estado.caches);
  // nada de acompanhamento operacional no texto do cabeçalho e do rodapé
  const cabecalho = await page.innerText("header"), rodape = await page.innerText("footer");
  assert.ok(!/monitoramento regional|mobilidade preventiva|tempo real|Instalar/i.test(cabecalho + rodape), cabecalho + " | " + rodape);
  assert.match(rodape, /não previsão de alagamentos/);
  // o app arquivado e os arquivos de instalação não são servidos
  for (const c of ["pwa/", "pwa/pwa.js", "sw.js", "manifest.webmanifest", "instalar.js", "inicio/aplicativo.html"]) assert.strictEqual((await page.request.get(BASE + c)).status(), 404, c);
  // um celular não é levado a lugar nenhum: o painel abre
  const cel = await abrir({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1" });
  await cel.page.goto(BASE); await cel.page.waitForSelector("#abas"); assert.ok(!/\/pwa\//.test(cel.page.url()));
  await cel.browser.close();
  // a landing não aponta para o app arquivado
  await page.goto(BASE + "inicio/"); assert.strictEqual(await page.locator("a[href*='pwa/'], a[href*='aplicativo.html']").count(), 0);
  assert.deepStrictEqual(erros, [], "sem erros no console: " + erros.join(" | "));
  await browser.close(); console.log("sem_pwa ok");
})().catch((e) => { console.error(e); process.exit(1); });
