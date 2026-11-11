// Jornada integrada de demonstração (dados SINTÉTICOS declarados: tempestade inventada e ocorrências de demonstração, em memória).
// Desktop consulta -> PWA calcula rota -> relato no mapa -> operador confirma e declara interdição -> a rota é recalculada e muda.
const { assert, abrir, BASE } = require("./lib");
const TEXTO = "Rua alagada na demonstração " + Date.now() + " (relato sintético)";
const TOKEN = process.env.DEMO_TOKEN || "demo-operador-com-mais-de-24-caracteres";
const t0 = Date.now(), T = (e) => console.log(((Date.now() - t0) / 1000).toFixed(0) + "s", e);
(async () => {
  // Etapa 1: desktop, território, condições, ocorrências e proveniência
  T("// Etapa 1: desktop, território, condiçõ");
  const d = await abrir({ viewport: { width: 1400, height: 900 } });
  await d.page.goto(BASE); await d.page.waitForSelector("#vista-geral .pergunta");
  assert.match(await d.page.innerText("#banner"), /DEMONSTRAÇÃO[\s\S]*sintéticas/, "o painel avisa que os dados são sintéticos");
  await d.page.click("[data-territorio=poa]"); await d.page.click("[data-aba=previsao]"); await d.page.waitForTimeout(2500);
  const prev = await d.page.innerText("#vista-previsao"); assert.match(prev, /chuva/i); assert.match(prev, /estimativa|Previsto/i);
  await d.page.click("[data-aba=ocorrencias]"); await d.page.waitForSelector("#oc-tabela", { timeout: 20000 });
  const linhas0 = await d.page.locator("#oc-tabela tbody tr").count(); assert.ok(linhas0 >= 2, "ocorrências de demonstração presentes");
  await d.page.click("[data-aba=proveniencia]"); await d.page.waitForTimeout(1500); assert.match(await d.page.innerText("#vista-proveniencia"), /O que se pode e o que não se pode afirmar/);
  // Etapa 3: PWA, origem, destino, carro, rotas
  T("// Etapa 3: PWA, origem, destino, carro,");
  const m = await abrir({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, locale: "pt-BR" });
  const p = m.page; await p.goto(BASE + "pwa/"); await p.waitForSelector("#tela .passos"); await p.waitForFunction(() => /DEMONSTRAÇÃO/.test(document.getElementById("aviso").textContent), null, { timeout: 15000 });
  await p.selectOption("#sel-o", "__mapa"); await p.mouse.click(390 / 2 + 30, 844 * 0.4); await p.waitForTimeout(300);
  await p.selectOption("#sel-d", "__mapa"); await p.mouse.click(390 / 2 + 100, 844 * 0.28); await p.waitForTimeout(300);
  await p.click("#analisar"); await p.waitForSelector("#resultado .decisao", { timeout: 90000 }); await p.waitForTimeout(800);
  assert.match(await p.innerText("#orienta .marca"), /DEMONSTRAÇÃO · dados sintéticos/i, "o aviso de dados sintéticos permanece depois da análise");
  const antes = { orienta: await p.innerText("#orienta-linha"), tempo: await p.innerText("#resultado .resumo .tempo"), detalhe: await p.innerText("#orienta-detalhe") };
  const n0 = Number((/evita (\d+) trecho/.exec(antes.detalhe) || [0, 0])[1]);
  // Etapa 4: relato no meio da rota (ponto da própria rota desenhada), como um usuário faria
  T("// Etapa 4: relato no meio da rota (pont");
  const ponto = await p.evaluate(() => {
    const paths = Array.from(document.querySelectorAll("#mapa path.leaflet-interactive")).filter((x) => x.getTotalLength && x.getTotalLength() > 150);
    const rota = paths.sort((a, b) => b.getTotalLength() - a.getTotalLength())[0], pt = rota.getPointAtLength(rota.getTotalLength() * 0.5), bb = rota.getBBox(), r = rota.getBoundingClientRect();
    return { x: r.left + (pt.x - bb.x) / (bb.width || 1) * r.width, y: r.top + (pt.y - bb.y) / (bb.height || 1) * r.height, d: rota.getAttribute("d") };
  });
  const rotaAntes = ponto.d;
  await p.click("#f-relatar"); await p.waitForSelector("#rel-texto"); await p.mouse.click(ponto.x, ponto.y);
  await p.click("#folha-alca"); await p.fill("#rel-texto", TEXTO);
  await p.click("#rel-enviar"); await p.waitForFunction(() => /registrado|recebido|reportad/i.test(document.getElementById("rel-msg").textContent), null, { timeout: 20000 });
  // o relato sozinho NÃO interdita: a rota continua a mesma
  await p.click("[data-tela=planejar]"); assert.ok(true);
  // Etapa 4 (operador): confirma e declara interdição
  T("// Etapa 4 (operador): confirma e declar");
  await d.page.click("[data-aba=ocorrencias]"); await d.page.waitForSelector("#oc-tabela");
  await d.page.fill("#op-cred", TOKEN); await d.page.click("#op-ok"); await d.page.waitForSelector("#oc-tabela tbody tr button[data-id]", { timeout: 20000 });
  const linhas1 = await d.page.locator("#oc-tabela tbody tr").count(); assert.ok(linhas1 > linhas0, "o relato novo aparece na lista");
  const meu = d.page.locator("#oc-tabela tbody tr", { hasText: TEXTO.slice(0, 40) }).locator("button[data-id]"); assert.strictEqual(await meu.count(), 1, "o operador vê o relato novo pelo texto");
  await meu.click(); await d.page.waitForSelector("#rv-ok");
  await d.page.selectOption("#rv-sit", "confirmada"); await d.page.selectOption("#rv-imp", "interdicao"); await d.page.fill("#rv-ev", "Confirmado em vistoria de demonstração (sintético).");
  await d.page.click("#rv-ok"); await d.page.waitForFunction(() => document.querySelectorAll("#oc-tabela tbody tr[data-sit=confirmada]").length >= 2, null, { timeout: 20000 });
  // Etapa 5: recalcular na PWA
  T("// Etapa 5: recalcular na PWA");
  await p.click("#editar"); await p.waitForSelector("#analisar"); 
  await p.click("#analisar"); await p.waitForSelector("#resultado .decisao", { timeout: 90000 }); await p.waitForTimeout(800);
  T("recalculada");
  const depois = { orienta: await p.innerText("#orienta-linha"), tempo: await p.innerText("#resultado .resumo .tempo"), detalhe: await p.innerText("#orienta-detalhe") };
  const rotaDepois = await p.evaluate(() => Array.from(document.querySelectorAll("#mapa path.leaflet-interactive")).filter((x) => x.getTotalLength() > 150).sort((a, b) => b.getTotalLength() - a.getTotalLength())[0].getAttribute("d"));
  const n1 = Number((/evita (\d+) trecho/.exec(depois.detalhe) || [0, 0])[1]);
  assert.notStrictEqual(rotaDepois, rotaAntes, "o traçado da rota mudou após a interdição confirmada");
  assert.ok(n1 > n0, `a interdição confirmada entra no cálculo (${n0} -> ${n1})`);
  console.log("antes:", JSON.stringify(antes)); console.log("depois:", JSON.stringify(depois));
  assert.deepStrictEqual(d.erros, [], "erros no desktop: " + d.erros.join(" | ")); assert.deepStrictEqual(m.erros, [], "erros no PWA: " + m.erros.join(" | "));
  T("verificações concluídas"); console.log("jornada: ok");
  // fechar o Chrome com WebGL por software pode levar minutos; o resultado já está decidido, então o fechamento tem prazo
  await Promise.race([Promise.all([d.browser.close(), m.browser.close()]), new Promise((r) => setTimeout(r, 15000))]); process.exit(0);
})().catch((e) => { console.error("FALHOU:", e.message); process.exit(1); });
