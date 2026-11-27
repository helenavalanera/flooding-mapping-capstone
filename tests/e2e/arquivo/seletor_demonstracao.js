// ARQUIVADO (frente estadual): roteiro do painel de duas escalas (Rio Grande do Sul e Porto Alegre), com previsão, mobilidade e ocorrências.
// Preservado sem alteração para consulta; não é executado, porque o painel atual é restrito a Porto Alegre (ver app/arquivo/painel-estadual/).
// O seletor de dados: serviço "real" (chuva seca de teste, sem ocorrências) e o serviço de demonstração, isolado, escolhido por cookie.
const { assert, abrir, BASE } = require("../lib");
const total = (page) => page.evaluate(() => fetch("../api/ocorrencias").then((r) => r.json()).then((d) => d.total));
const saude = (page) => page.evaluate(() => fetch("../api/saude").then((r) => r.json()));
(async () => {
  const m = await abrir({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, locale: "pt-BR" });
  const p = m.page; await p.goto(BASE + "pwa/"); await p.waitForSelector("#modo:not([hidden])", { timeout: 30000 });
  assert.strictEqual(await p.getAttribute("#modo [data-modo=real]", "aria-pressed"), "true", "começa nos dados reais");
  assert.strictEqual((await saude(p)).modo, "real"); assert.strictEqual(await total(p), 0, "o serviço real não tem ocorrências");
  assert.ok(!(await p.isVisible("#faixa-demo")), "sem demonstração, sem faixa");
  // para a demonstração
  await Promise.all([p.waitForNavigation(), p.click("#modo [data-modo=demo]")]); await p.waitForSelector("#modo.demo");
  assert.strictEqual(await p.getAttribute("#modo [data-modo=demo]", "aria-pressed"), "true");
  const s = await saude(p); assert.strictEqual(s.modo, "demonstracao"); assert.strictEqual(s.chuva.sintetica, true, "a chuva da demonstração se declara sintética");
  assert.ok((await total(p)) >= 2, "a demonstração traz as ocorrências de demonstração");
  assert.ok(await p.evaluate(() => /fm_modo=demo/.test(document.cookie)), "a escolha vive num cookie de sessão");
  // um relato em demonstração não aparece no serviço real
  const rid = await p.evaluate(() => fetch("../api/relatos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto: "relato da demonstração (sintético)", lon: -51.23, lat: -30.03 }) }).then((r) => r.json()).then((d) => d.id));
  assert.ok(rid);
  // de volta ao real
  await Promise.all([p.waitForNavigation(), p.click("#modo [data-modo=real]")]); await p.waitForSelector("#modo:not(.demo)");
  assert.strictEqual((await saude(p)).modo, "real"); assert.strictEqual(await total(p), 0, "nada da demonstração vazou para o serviço real");
  // painel: o mesmo seletor
  const d = await abrir({ viewport: { width: 1400, height: 900 } });
  await d.page.goto(BASE); await d.page.waitForSelector("#modo:not([hidden])", { timeout: 30000 });
  await Promise.all([d.page.waitForNavigation(), d.page.click("#modo [data-modo=demo]")]); await d.page.waitForSelector("#modo.demo");
  await d.page.waitForFunction(() => /sintéticas/.test(document.getElementById("banner").textContent), null, { timeout: 30000 });
  // um celular que abre o endereço do painel NÃO é mais levado ao aplicativo do cidadão (arquivado): o painel abre
  const c = await abrir({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1" }); await c.page.goto(BASE); await c.page.waitForSelector("#abas");
  assert.ok(!/\/pwa\/$/.test(c.page.url()), "o celular fica no painel");
  assert.deepStrictEqual(m.erros.concat(d.erros), [], "erros de console: " + m.erros.concat(d.erros).join(" | "));
  console.log("seletor: ok");
  await Promise.race([Promise.all([m.browser.close(), d.browser.close(), c.browser.close()]), new Promise((r) => setTimeout(r, 15000))]); process.exit(0);
})().catch((e) => { console.error("FALHOU:", e.message); process.exit(1); });
