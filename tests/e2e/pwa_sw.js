// Update of the service worker: with the PWA open, a new version is published on disk (STATIC_COPY is a copy of the static folder).
const fs = require("fs");
const { assert, abrir } = require("./lib");
const BASE = process.env.BASE_URL, SW = process.env.STATIC_COPY + "/pwa/sw.js";
(async () => {
  const { browser, page } = await abrir({ viewport: { width: 390, height: 844 } });
  await page.goto(BASE + "pwa/"); await page.waitForSelector("#tela .passos"); await page.evaluate(() => navigator.serviceWorker.ready); await page.waitForTimeout(1500);
  const antes = await page.evaluate(() => caches.keys()); assert.strictEqual(antes.length, 1);
  fs.writeFileSync(SW, fs.readFileSync(SW, "utf8").replace(/var VERSAO = "[^"]+"/, 'var VERSAO = "fm-pwa-teste-nova"'));
  await page.evaluate(() => navigator.serviceWorker.getRegistration().then((r) => r.update()));
  await page.waitForFunction(() => /nova versão/i.test(document.getElementById("aviso").textContent), null, { timeout: 15000 }); await page.waitForTimeout(1500);
  assert.deepStrictEqual(await page.evaluate(() => caches.keys()), ["fm-pwa-teste-nova"], "o cache da versão antiga é removido");
  await page.click("#aviso button"); await page.waitForSelector("#tela .passos"); await page.waitForTimeout(1000); assert.ok(!/nova versão/i.test(await page.evaluate(() => document.getElementById("aviso").textContent)), "o aviso de nova versão some após atualizar");
  await browser.close(); console.log("sw: ok");
})().catch((e) => { console.error("FALHOU:", e.message); process.exit(1); });
