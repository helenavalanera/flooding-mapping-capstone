// "No celular": a interface real em 390 px dentro do aparelho, sem imagem ilustrativa; cada tela abre o que promete.
const { assert, abrir, BASE } = require("./lib");
(async () => {
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 1000 } });
  await page.goto(BASE + "inicio/celular.html"); await page.waitForSelector("#tela");
  const dim = await page.evaluate(() => { const f = document.getElementById("tela"); return [f.clientWidth, f.clientHeight, f.contentWindow.innerWidth]; });
  assert.deepStrictEqual(dim.slice(0, 1).concat(dim[2]), [390, 390], "o quadro tem a largura de um celular: " + dim);
  const quadro = () => page.frames().find((f) => f !== page.mainFrame() && /\?painel=1/.test(f.url()));
  const abre = async (id, seletor, texto) => {
    await page.click(`[data-tela=${id}]`); assert.strictEqual(await page.getAttribute(`[data-tela=${id}]`, "aria-pressed"), "true");
    await page.waitForFunction((u) => { const f = document.getElementById("tela"); return f && f.getAttribute("src") === u; }, await page.getAttribute("#abrir", "href"));
    let f; await page.waitForFunction(() => true); for (let i = 0; i < 60 && !(f = quadro()); i++) await page.waitForTimeout(500);
    await f.waitForSelector(seletor, { timeout: 120000 });
    if (texto) assert.match(await f.innerText(seletor), texto);
    assert.strictEqual(await f.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true, id + ": sem rolagem horizontal em 390 px");
    return f;
  };
  await abre("resultados", ".rs-achado", /./);
  await abre("simulador", "#vista-simulador .rs-seletor", /./);
  const camadas = await abre("camadas", "#legenda-gl", /Geração potencial local/);
  const consulta = await abre("consulta", "#f3-trecho", /Rua Álvaro Chaves/);
  assert.match(await consulta.innerText("#f3-trecho"), /Contribuição potencial estimada associada ao trecho/); assert.match(await consulta.innerText("#f3-trecho"), /Não somar com outros trechos/);
  assert.match(await page.innerText(".cel-nota"), /./);
  // a moldura não é uma imagem: não há img do aplicativo na página
  assert.strictEqual(await page.locator(".cel-corpo img").count(), 0);
  assert.deepStrictEqual(erros.filter((e) => !/net::|Failed to fetch/.test(e)), [], "console: " + erros.join(" | "));
  await page.setViewportSize({ width: 360, height: 800 }); await page.waitForTimeout(300);
  assert.strictEqual(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true, "a página do aparelho cabe em 360 px");
  await browser.close(); console.log("celular ok");
})().catch((e) => { console.error(e); process.exit(1); });
