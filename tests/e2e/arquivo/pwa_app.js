// PWA da aplicação de análise: instala o service worker, guarda só o que a política manda, abre sem conexão dizendo a verdade e atualiza a versão.
const fs = require("fs");
const { assert, abrir } = require("./lib");
const BASE = process.env.BASE_URL, SW = process.env.STATIC_COPY + "/sw.js";
(async () => {
  const { browser, ctx, page, erros } = await abrir({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const rede = []; page.on("request", (r) => rede.push(r.url()));
  await page.goto(BASE + "?painel=1#poa/resultados"); await page.waitForSelector(".rs-achado", { timeout: 30000 });
  // manifesto servido e válido
  const man = await page.evaluate(() => fetch(document.querySelector("link[rel=manifest]").href).then((r) => ({ tipo: r.headers.get("content-type"), j: r.json() })).then(async (x) => ({ tipo: x.tipo, j: await x.j })));
  assert.match(man.tipo, /manifest\+json/); assert.strictEqual(man.j.display, "standalone");
  for (const i of man.j.icons) assert.strictEqual((await page.evaluate((u) => fetch(u).then((r) => r.status), new URL(i.src, BASE).href)), 200, i.src);
  // service worker ativo e cache da versão
  await page.evaluate(() => navigator.serviceWorker.ready); await page.waitForFunction(() => caches.keys().then((k) => k.includes("fm-app-v1")), null, { timeout: 30000 });
  const guardados = await page.evaluate(() => caches.open("fm-app-v1").then((c) => c.keys()).then((ks) => ks.map((k) => new URL(k.url).pathname)));
  for (const p of ["/index.html", "/resultados.js", "/simulador.js", "/data/resultados_poa.json", "/inicio/estudo.js"]) assert.ok(guardados.includes(p), "pré-carga: " + p);
  assert.ok(!guardados.some((p) => /\/(fase3|drenagem|api)\//.test(p) || /previsao_72h|bloqueios/.test(p)), "nada de camadas, API ou dados do agora no cache: " + guardados.filter((p) => /fase3|drenagem|api/.test(p)));
  assert.match(await page.innerText("#versao-app"), /fm-app-v1/, "a versão da interface aparece");
  // a página tem que estar sob o controle do service worker para o teste offline valer
  await page.reload(); await page.waitForSelector(".rs-achado"); assert.ok(await page.evaluate(() => !!navigator.serviceWorker.controller), "página controlada");
  // camadas de escoamento: usar a camada e conferir que tiles e fragmentos não entram no cache
  await page.goto(BASE + "?painel=1#poa/mapa?escoamento=1"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 90000 });
  await page.waitForFunction(() => window.Fase3 && window.Fase3.meta, null, { timeout: 60000 });
  await page.evaluate(() => window.Mapa.map.jumpTo({ center: [-51.2, -30.05], zoom: 14 })); await page.waitForTimeout(4000);
  const depois = await page.evaluate(() => caches.keys().then((ks) => Promise.all(ks.map((k) => caches.open(k).then((c) => c.keys()).then((q) => q.map((r) => new URL(r.url).pathname))))).then((l) => l.flat()));
  assert.ok(!depois.some((p) => /\/fase3\/|\/drenagem\/|\/api\//.test(p)), "tiles, fragmentos e API nunca são guardados");
  assert.ok(rede.some((u) => /\/fase3\//.test(u)), "mas a camada foi pedida à rede");
  // sem conexão: resultados e simulador abrem com a cópia salva, e a tela avisa o que falta
  await page.goto(BASE + "?painel=1#poa/resultados"); await page.waitForSelector(".rs-achado");
  await ctx.setOffline(true);
  await page.reload(); await page.waitForSelector(".rs-achado", { timeout: 30000 });
  assert.match(await page.innerText("#aviso-conexao"), /Sem conexão/); assert.match(await page.innerText("#aviso-conexao"), /Dependem de conexão: as camadas de escoamento e de drenagem/);
  assert.match(await page.innerText("#vista-resultados"), /Sem conexão: estes resultados são a cópia salva neste aparelho/);
  await page.click("[data-aba=simulador]"); await page.waitForSelector("#vista-simulador .rs-seletor"); assert.match(await page.innerText("#vista-simulador"), /cópia salva neste aparelho/);
  await page.goto(BASE + "inicio/"); assert.match(await page.title(), /./); assert.ok((await page.locator("h1").count()) > 0, "a landing abre sem conexão");
  // o mapa sem rede não finge dados: a camada de escoamento diz que está indisponível ou aproxima sem tiles
  await page.goto(BASE + "?painel=1#poa/mapa"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 90000 });
  await page.click("[data-dim=A]"); await page.waitForTimeout(3000);
  const msg = await page.innerText("#dimensoes"); assert.ok(/Os dados de escoamento não estão disponíveis|Carregando|Chuva de referência/.test(msg));
  await ctx.setOffline(false); await page.waitForFunction(() => document.getElementById("aviso-conexao").hidden);
  // atualização: uma nova versão publicada apaga o cache antigo (só os fm-app-) e avisa
  fs.writeFileSync(SW, fs.readFileSync(SW, "utf8").replace(/var VERSAO = "[^"]+"/, 'var VERSAO = "fm-app-teste-nova"'));
  await page.goto(BASE + "?painel=1"); await page.waitForSelector("#abas");
  await page.evaluate(() => navigator.serviceWorker.getRegistration().then((r) => r.update()));
  await page.waitForFunction(() => !document.getElementById("aviso-versao").hidden, null, { timeout: 20000 }); assert.match(await page.innerText("#aviso-versao"), /nova versão/);
  await page.waitForTimeout(4500); const chaves = await page.evaluate(() => caches.keys()); assert.ok(chaves.includes("fm-app-teste-nova") && !chaves.includes("fm-app-v1"), "cache antigo removido: " + JSON.stringify(chaves));
  assert.deepStrictEqual(erros.filter((e) => !/net::|Failed to fetch|NetworkError|Load failed/.test(e)), [], "console: " + erros.join(" | "));
  await browser.close(); console.log("pwa_app ok");
})().catch((e) => { console.error(e); process.exit(1); });
