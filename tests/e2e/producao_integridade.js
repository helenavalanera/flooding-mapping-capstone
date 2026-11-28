// Com um hash esperado que não confere com o meta.json do R2, a página RECUSA os dados (a verificação de integridade não é desligada para o mapa carregar) e diz por quê.
const { chromium } = require(process.env.PLAYWRIGHT_CORE); const assert = require("assert");
const PAGES = process.env.PAGES, R2 = process.env.R2;
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage(); page.setDefaultTimeout(120000);
  const tiles = []; page.on("request", (r) => { if (r.url().startsWith(R2) && /\/fase3\/(tiles|detalhe)\//.test(r.url())) tiles.push(r.url()); });
  await page.goto(PAGES + "/painel.html#poa/mapa"); await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 150000 });
  await page.click("#dimensoes button[data-dim=B]"); await page.waitForFunction(() => window.Fase3 && window.Fase3.erro, null, { timeout: 60000 });
  const erro = await page.evaluate(() => window.Fase3.erro); assert.match(erro, /o meta\.json de fase3 não corresponde à versão esperada dos dados/);
  assert.strictEqual(await page.evaluate(() => window.Fase3.meta), null, "os dados recusados não podem ser usados"); assert.deepStrictEqual(tiles, [], "nenhum tile é pedido depois da recusa");
  assert.match(await page.innerText("#f3-opcoes"), /não estão disponíveis|não pode ser mostrada/);
  assert.ok(await page.evaluate(() => window.Mapa.pronto), "o mapa-base e as outras camadas continuam funcionando");
  console.log("producao_integridade ok"); await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
