// Dados em URL configurável e conferidos por hash: base alternativa, hash errado recusa, hash certo carrega, indisponibilidade tem mensagem e "tentar de novo".
const crypto = require("crypto"), fs = require("fs");
const { assert, abrir, BASE } = require("./lib");
(async () => {
  const meta = fs.readFileSync(process.env.META_FASE3);
  const hashCerto = crypto.createHash("sha256").update(meta).digest("hex");
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 }, serviceWorkers: "block" });
  let modo = "errado", pedidos = 0;
  await page.route("**/config-dados.js", (r) => r.fulfill({ contentType: "text/javascript", body: fs.readFileSync(process.env.CONFIG_JS, "utf8").replace('fase3: "fase3/"', 'fase3: "copia-dos-dados/fase3/"').replace("versao: null", 'versao: "d-teste"').replace("fase3: null, drenagem", `fase3: "${modo === "errado" ? "0".repeat(64) : hashCerto}", drenagem`) }));
  await page.route("**/copia-dos-dados/fase3/**", (r) => { pedidos++; if (modo === "fora") return r.fulfill({ status: 503, body: "indisponível" }); r.continue({ url: r.request().url().replace("copia-dos-dados/", "") }); });
  await page.goto(BASE + "#poa/mapa"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 90000 });
  assert.strictEqual(await page.evaluate(() => window.FM_DADOS.base("fase3").endsWith("/copia-dos-dados/fase3/")), true, "a base vem da configuração, não do código");
  // hash errado: a camada é recusada, com o motivo, e nada de dado é mostrado
  await page.click("[data-dim=A]"); await page.waitForSelector("#f3-tentar", { timeout: 30000 });
  assert.match(await page.innerText("#f3-opcoes"), /não corresponde à versão esperada dos dados/); assert.strictEqual(await page.evaluate(() => !!window.Fase3.meta), false);
  assert.strictEqual(await page.locator("#f3-p").count(), 0, "sem dados, sem valores");
  // hash certo: carrega e mostra a versão do conjunto
  modo = "certo"; await page.evaluate((h) => { window.FM_DADOS.meta_sha256.fase3 = h; }, hashCerto); await page.click("#f3-tentar"); await page.waitForSelector("#f3-versao", { state: "attached", timeout: 30000 });
  assert.match(await page.textContent("#f3-versao"), /camada v1, conjunto d-teste/);
  // indisponível: mensagem e nova tentativa
  modo = "fora"; await page.evaluate(() => { window.Fase3.meta = null; window.Fase3._meta = null; });
  await page.click("[data-dim=A]"); await page.click("[data-dim=A]"); await page.waitForSelector("#f3-tentar", { timeout: 30000 });
  assert.match(await page.innerText("#f3-opcoes"), /não estão disponíveis \(HTTP 503/);
  modo = "certo"; await page.click("#f3-tentar"); await page.waitForSelector("#f3-versao", { state: "attached", timeout: 30000 });
  assert.ok(pedidos >= 3);
  assert.deepStrictEqual(erros.filter((e) => !/503|net::|Failed to load/.test(e)), [], "console: " + erros.join(" | "));
  await browser.close(); console.log("dados_config ok");
})().catch((e) => { console.error(e); process.exit(1); });
