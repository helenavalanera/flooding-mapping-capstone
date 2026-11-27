// Modo claro permanente: o tema escuro do sistema não muda a aparência de nenhuma página, nem o mapa-base.
const { assert, abrir, BASE } = require("./lib");
const PAGINAS = ["", "?painel=1#poa/resultados", "inicio/", "inicio/celular.html"];
(async () => {
  const cores = {};
  for (const esquema of ["light", "dark"]) {
    const { browser, page, erros } = await abrir({ viewport: { width: 1280, height: 800 }, colorScheme: esquema });
    for (const p of PAGINAS) {
      await page.goto(BASE + p, { waitUntil: "load" }); await page.waitForTimeout(1200);
      const c = await page.evaluate(() => { const s = getComputedStyle(document.body); return { fundo: s.backgroundColor, texto: s.color, esquema: getComputedStyle(document.documentElement).colorScheme, escuroMq: matchMedia("(prefers-color-scheme: dark)").matches }; });
      (cores[p] = cores[p] || {})[esquema] = c;
    }
    if (esquema === "dark") assert.strictEqual(await page.evaluate(() => (window.MapaBase ? window.MapaBase.escuro() : false)), false, "mapa-base escolhe o estilo claro");
    await browser.close();
  }
  for (const p of PAGINAS) {
    const { light, dark } = cores[p];
    assert.strictEqual(dark.fundo, light.fundo, `${p || "/"}: fundo igual com o sistema em modo escuro`); assert.strictEqual(dark.texto, light.texto, `${p || "/"}: texto igual`);
    assert.ok(dark.escuroMq, "o navegador de teste realmente está em modo escuro");
    const [r, g, b] = dark.fundo.match(/\d+/g).map(Number); assert.ok((r + g + b) / 3 > 200 || /inicio\/$/.test(p), `${p || "/"}: fundo claro (${dark.fundo})`);
  }
  console.log("modo_claro ok");
})().catch((e) => { console.error(e); process.exit(1); });
