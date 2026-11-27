// Landing científica no navegador: navegação por âncoras, abas das camadas, comparador de cenários com os números do motor, links para o mapa e responsividade.
const { assert, abrir, BASE, semTransbordo } = require("./lib");
const fs = require("fs"), path = require("path");
(async () => {
  const dados = JSON.parse(fs.readFileSync(path.join(__dirname, "../../src/flooding_mapping/app/static/inicio/dados.json"), "utf8"));
  const { browser, page, erros } = await abrir({ viewport: { width: 1400, height: 900 } });
  await page.goto(BASE + "inicio/");
  assert.match(await page.innerText("h1"), /Dada uma chuva, onde a água tende a se acumular\?/);
  assert.strictEqual(await page.locator("h1").count(), 1);
  assert.match(await page.innerText(".hero-quadro"), /Geração de escoamento[\s\S]*Concentração do escoamento[\s\S]*Propensão topográfica à retenção[\s\S]*Drenagem cadastrada/); assert.strictEqual(await page.locator(".hero img").count(), 0, "sem mapa derivado de dado restrito no início");
  // âncoras: cada link leva à sua seção e a atual é marcada
  const hrefs = await page.locator(".ancoras a").evaluateAll((a) => a.map((x) => x.getAttribute("href")));
  assert.deepStrictEqual(hrefs, ["#apresentacao", "#mapa", "#cenarios", "#resultados", "#contato"]);
  await page.click(".ancoras a[href='#resultados']");
  await page.waitForFunction(() => { const a = document.querySelector(".ancoras a[aria-current=true]"); return a && a.getAttribute("href") === "#resultados"; }, null, { timeout: 15000 });
  await page.waitForFunction(() => { const r = document.getElementById("resultados").getBoundingClientRect(); return r.top >= 0 && r.top < 200; }, null, { timeout: 8000 }).catch(() => {});   // a rolagem é suave e a página ficou mais alta
  assert.ok(await page.evaluate(() => document.getElementById("resultados").getBoundingClientRect().top < 200), "a âncora rolou até a seção");
  // as quatro dimensões: texto de cada uma e um mapa de manchas pré-renderizado por dimensão, escolhido por um seletor (sem WebGL na landing)
  await page.click(".ancoras a[href='#mapa']"); await page.waitForTimeout(2500);
  for (const id of ["p-contribuicao", "p-local", "p-topografico", "p-drenagem"]) assert.ok(await page.locator("#" + id).isVisible(), id + " visível");
  assert.strictEqual(await page.locator(".hero img").count(), 0); assert.strictEqual(await page.locator("#mapa canvas").count(), 0, "sem canvas (WebGL) na landing");
  assert.strictEqual(await page.locator("#mapa [role=tab]").count(), 4); assert.strictEqual(await page.locator("#mapa [role=tabpanel]:not([hidden])").count(), 1, "um painel por vez");
  const ESPERADO = { a: [/mapa-geracao\.webp$/, /m³/, /Profill/], b: [/mapa-concentracao\.webp$/, /m³/, /Não é vazão/], c: [/mapa-propensao\.webp$/, /mais de 0 até 0,5 m/, /ocorrência ou risco de alagamento/], d: [/mapa-drenagem\.webp$/, /200 a 300 m[\s\S]*sem rede cadastrada/, /não o funcionamento nem a capacidade/] };
  for (const k of ["a", "b", "c", "d"]) {
    await page.click("#aba-" + k); await page.waitForFunction((id) => { const i = document.querySelector("#painel-" + id + " img"); return i.complete && i.naturalWidth > 0; }, k, { timeout: 8000 });
    assert.strictEqual(await page.locator("#mapa [role=tabpanel]:not([hidden])").count(), 1); assert.strictEqual(await page.getAttribute("#aba-" + k, "aria-selected"), "true");
    const [arq, leg, aviso] = ESPERADO[k]; assert.match(await page.getAttribute("#painel-" + k + " img", "src"), arq); assert.match(await page.innerText("#painel-" + k + " .leg"), leg); assert.match(await page.innerText("#painel-" + k), aviso);
    assert.match(await page.innerText("#painel-" + k + " .mapa-lacunas"), /sem dado|sem rede|sem preenchimento/); assert.strictEqual(await page.locator("#painel-" + k + " .mapa-bairros tbody tr").count(), 5);
  }
  await page.keyboard.press("ArrowLeft"); assert.strictEqual(await page.getAttribute("#aba-c", "aria-selected"), "true", "setas trocam de dimensão");
  await page.click("#painel-c .ampliar"); assert.ok(await page.evaluate(() => document.querySelector(".zoom").open), "o mapa amplia"); await page.keyboard.press("Escape"); assert.ok(!(await page.evaluate(() => document.querySelector(".zoom").open)));
  assert.match(await page.innerText("#p-drenagem"), /não prova capacidade, funcionamento nem conexão/); assert.match(await page.innerText("#p-topografico"), /Não é profundidade, volume nem duração/);
  assert.match(await page.innerText("#mapa"), /Decreto Municipal nº 20\.315\/2019/); assert.match(await page.innerText("#mapa"), /dependem da publicação dos arquivos derivados/);
  assert.match(await page.innerText("#painel-a"), /Zero não é ausência de dado/); assert.match(await page.innerText("#painel-c"), /Não é a profundidade que a água atingiria/);
  // nenhuma imagem quebrada na página inteira
  await page.evaluate(() => document.querySelectorAll('img[loading=lazy]').forEach((i) => { i.loading = 'eager'; }));   // imagens preguiçosas só carregam ao rolar
  await page.waitForFunction(() => Array.from(document.images).every((i) => i.complete), null, { timeout: 20000 }).catch(() => {});
  const quebradas = await page.evaluate(() => Array.from(document.images).filter((i) => !i.complete || i.naturalWidth === 0).map((i) => i.src));
  assert.deepStrictEqual(quebradas, [], "imagens quebradas: " + quebradas.join(", "));
  // comparador de cenários: os números mostrados são os das execuções reais
  await page.click(".ancoras a[href='#cenarios']"); await page.waitForTimeout(2500);
  const mi = (v) => new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(v / 1e6);
  for (const p of [10, 20, 30]) {
    await page.click(`.seletor button[data-p='${p}']`);
    assert.strictEqual(await page.getAttribute(`.seletor button[data-p='${p}']`, "aria-pressed"), "true"); assert.match(await page.innerText("#cen-p"), new RegExp(p + " mm"));
    const t = dados.cenarios.totais_m3[String(p)], txt = await page.innerText("#cen-barras");
    for (const k of ["metodo1", "referencia_analoga", "limites_fisicos"]) assert.ok(txt.includes(mi(t[k].min_m3) + " a " + mi(t[k].max_m3) + " milhões de m³"), `${p} mm ${k}: ${mi(t[k].min_m3)} a ${mi(t[k].max_m3)}`);
    const comCamadas = (await page.getAttribute("#cen-link", "data-camadas")) === "1";           // só promete a camada quando os derivados estão publicados
    assert.strictEqual(await page.getAttribute("#cen-link", "href"), comCamadas ? `../?painel=1#poa/mapa?escoamento=1&p=${p}` : "../?painel=1#poa/mapa");
  }
  assert.match(await page.innerText("#cen-trecho"), /Contribuição potencial acumulada[\s\S]*mediana[\s\S]*percentil 99/); assert.match(await page.innerText("#cenarios"), /e não previsões/);
  // o link do simulador abre o mapa já configurado (camada ligada, chuva e pacote pedidos)
  await page.click(".seletor button[data-p='20']");
  await page.goto(BASE + "?painel=1#poa/mapa?escoamento=1&p=20&pacote=an&modo=l");
  await page.waitForFunction(() => window.Mapa && window.Mapa.pronto, null, { timeout: 120000 });
  await page.waitForFunction(() => window.Fase3 && window.Fase3.meta, null, { timeout: 60000 });
  const e = await page.evaluate(() => ({ ...window.Fase3.estado, marcada: window.Mapa.marcadas.escoamento_fase3, camada: document.querySelector("input[data-camada=escoamento_fase3]").checked }));
  assert.deepStrictEqual([e.p, e.pacote, e.modo, e.marcada, e.camada], [20, "an", "l", true, true], "o mapa abriu como a landing pediu");
  assert.match(await page.innerText("#legenda-gl"), /Geração potencial local[\s\S]*Método 2[\s\S]*20 mm/);
  // responsividade da landing
  await page.goto(BASE + "inicio/");
  await semTransbordo(page, [360, 390, 768, 1024, 1440], [async () => { await page.evaluate(() => scrollTo(0, 0)); }, async () => { await page.evaluate(() => document.getElementById("resultados").scrollIntoView()); }]);
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.isVisible(".hero .btn"), "CTA visível no celular");
  // celular: a navegação lateral indica que há mais seções e o mapa de manchas pode ser ampliado e percorrido
  await page.evaluate(() => scrollTo(0, 0)); await page.waitForTimeout(300);
  const nav = await page.evaluate(() => { const f = document.querySelector(".ancoras"); return { rola: f.scrollWidth > f.clientWidth + 4, dir: f.classList.contains("rola-dir"), mask: getComputedStyle(f).maskImage || getComputedStyle(f).webkitMaskImage }; });
  assert.ok(nav.rola && nav.dir && /gradient/.test(nav.mask), "a faixa de seções mostra o esmaecimento de que há mais à direita: " + JSON.stringify(nav));
  await page.evaluate(() => document.getElementById("mapa").scrollIntoView()); await page.waitForTimeout(1200);
  assert.ok(await page.evaluate(() => document.querySelector(".ancoras a[aria-current=true]").textContent.trim() === "Mapa"), "a seção atual fica marcada na faixa");
  await page.click("#painel-a .ampliar"); const z0 = await page.evaluate(() => document.querySelector(".zoom img").getBoundingClientRect().width);
  for (let i = 0; i < 4; i++) await page.click(".zoom [data-z='+']");
  const z1 = await page.evaluate(() => { const a = document.querySelector(".zoom-area"); return { w: document.querySelector(".zoom img").getBoundingClientRect().width, rola: a.scrollWidth > a.clientWidth }; });
  assert.ok(z1.w > 1.8 * z0 && z1.rola, "o mapa ampliado passa da largura da tela e rola: " + JSON.stringify([z0, z1])); await page.keyboard.press("Escape");
  assert.strictEqual(JSON.stringify(erros), "[]", "sem erros de console nem 4xx/5xx: " + JSON.stringify(erros));
  await browser.close(); console.log("landing ok");
})().catch((e) => { console.error(e); process.exit(1); });
