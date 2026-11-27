/* Aba "Resultados": leitura executiva e territorial dos resultados de Porto Alegre. Lê data/resultados_poa.json, gerado dos dados reais por
   tools/gerar_resultados.py. Nada é recalculado aqui além da escala linear pela chuva de referência (V = P x aeq / 1000), que o gerador e os testes
   conferem contra a saída do motor. Cada seção responde: o que foi observado, o que o modelo estimou, em que contexto, qual a relevância e qual a limitação.
   A drenagem é contexto: não se infere capacidade, funcionamento nem conectividade. Nada é somado entre trechos. */
(function () {
  "use strict";
  var Lg = window.Logic;
  var R = { dados: null, erro: null, P: null, _p: null, metricaBairro: "contribuicao" };
  window.Resultados = R;
  var esc = function (s) { return Lg.esc(s); };
  var N1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }), N0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }), N3 = new Intl.NumberFormat("pt-BR", { maximumSignificantDigits: 3 });
  function num(v) { return v == null || !isFinite(v) ? "sem dados" : (Math.abs(v) >= 100 ? N0 : N3).format(v); }
  function pct(f, c) { return f == null ? "sem dados" : (c ? new Intl.NumberFormat("pt-BR", { maximumFractionDigits: c }) : N0).format(100 * f) + "%"; }
  R.volume = function (aeq, P) { return aeq == null || !isFinite(aeq) ? null : P * aeq / 1000; };          // m³ = P (mm) x aeq (m²) / 1000

  var DIM_COR = { A: "#0b5d8f", B: "#2e8b57", C: "#5b3a8c", D: "#b5651d" };
  var TEXTOS = {
    pergunta: "Dada uma precipitação de referência em Porto Alegre, quais contextos territoriais apresentam maior geração potencial de escoamento, concentração de contribuição e propensão topográfica à retenção?",
    aviso: "Estimativa condicionada a uma chuva hipotética e uniforme. Não é previsão de alagamento, nem volume que de fato chegou, nem profundidade ou duração, e não identifica pontos de alagamento confirmado.",
    drenagem: "A drenagem cadastrada é contexto: o cadastro mostra o que está registrado e não indica capacidade de vazão, funcionamento, conectividade hidráulica nem eficiência.",
    rotulos: ["O que foi observado nos dados", "O que o modelo estimou", "Em que contexto territorial", "Por que importa para o planejamento", "Limitação da interpretação"]
  };
  R.textos = function () { return TEXTOS; };
  R.carregar = function () { return carregar(); };
  /* Aviso de cópia salva: sem conexão, os resultados vêm da última cópia guardada no aparelho, que pode não ser a versão mais recente. */
  R.avisoCopia = function () { return R.copia ? "<p class='rs-aviso' role='status'><b>Sem conexão:</b> estes resultados são a cópia salva neste aparelho em " + esc(R.copia) + ". Podem não ser a versão mais recente.</p>" : ""; };

  function carregar() {
    if (R._p) return R._p;
    R._p = fetch("data/resultados_poa.json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      var salva = r.headers.get("X-FM-Copia-Salva"), quando = r.headers.get("Date");   // o service worker marca a cópia usada sem conexão (sw.js)
      R.copia = salva ? (quando && !isNaN(new Date(quando)) ? new Date(quando).toLocaleString("pt-BR") : "data desconhecida") : null;
      return r.json(); })
      .then(function (d) { R.dados = d; if (R.P == null) R.P = d.precipitacao_de_referencia_mm; return d; }).catch(function (e) { R.erro = e.message; R._p = null; throw e; });
    return R._p;
  }

  /* ---------------------------------------------------------------- gráficos em HTML (acessíveis, leves, sem biblioteca) */
  function barra(rotulo, frac, texto, cor, extra) {
    return "<div class='rs-barra'><div class='rs-rot'>" + esc(rotulo) + "</div><div class='rs-trilho' role='img' aria-label='" + esc(rotulo + ": " + texto) + "'><i style='width:" + Math.max(0.6, 100 * frac) + "%;background:" + (cor || "var(--accent)") + "'></i></div><div class='rs-val'>" + esc(texto) + (extra ? " <span class='small'>" + esc(extra) + "</span>" : "") + "</div></div>";
  }
  function faixa(rotulo, lo, hi, max, texto, cor) {
    return "<div class='rs-barra'><div class='rs-rot'>" + esc(rotulo) + "</div><div class='rs-trilho' role='img' aria-label='" + esc(rotulo + ": " + texto) + "'><i style='left:" + 100 * lo / max + "%;width:" + Math.max(0.8, 100 * (hi - lo) / max) + "%;background:" + (cor || "var(--accent)") + "'></i></div><div class='rs-val'>" + esc(texto) + "</div></div>";
  }
  function ficha(achado) {
    var ev = achado.evidencia;
    return "<details class='rs-ficha'><summary>Evidência e verificação</summary><p class='small'>" + (achado.verificada ? "Afirmação verificada pelos dados: o título só é conclusivo porque a condição calculada se cumpriu." : "A condição calculada não se cumpriu: vale o título neutro.") +
      " Valores brutos no arquivo <code>data/resultados_poa.json</code> (campo <code>evidencia</code> de <code>" + esc(achado.id) + "</code>).</p><pre class='rs-json'>" + esc(JSON.stringify(ev, function (k, v) { return typeof v === "number" ? Number(v.toPrecision(5)) : v; }, 1).slice(0, 1800)) + (JSON.stringify(ev).length > 1800 ? "\n..." : "") + "</pre></details>";
  }
  function cartao(d, achado, grafico) {
    var r = TEXTOS.rotulos, a = achado;
    return "<article class='rs-achado' data-achado='" + esc(a.id) + "' data-verificada='" + a.verificada + "'><h3>" + esc(a.titulo) + "</h3>" +
      "<div class='rs-cinco'><div><h4>" + r[0] + "</h4><p>" + esc(a.observado) + "</p></div><div><h4>" + r[1] + "</h4><p>" + esc(a.estimado) + "</p></div><div><h4>" + r[2] + "</h4><p>" + esc(a.contexto) + "</p></div>" +
      "<div><h4>" + r[3] + "</h4><p>" + esc(a.relevancia) + "</p></div><div class='lim'><h4>" + r[4] + "</h4><p>" + esc(a.limitacao) + "</p></div></div>" +
      (grafico ? "<div class='rs-grafico'>" + grafico + "</div>" : "") + ficha(a) + "</article>";
  }
  function indicadoresDe(dim) {
    var lista = R.dados.indicadores.filter(function (i) { return i.dimensao === dim; });
    return "<details class='rs-indic'><summary>Fichas técnicas dos indicadores desta dimensão (" + lista.length + ")</summary>" + lista.map(tabelaIndicador).join("") + "</details>";
  }
  function tabelaIndicador(i) {
    return "<dl class='rs-dl' id='ind-" + esc(i.id) + "'><dt>Indicador</dt><dd><b>" + esc(i.titulo) + "</b> <code>" + esc(i.id) + "</code></dd><dt>Fórmula</dt><dd>" + esc(i.formula) + "</dd><dt>Unidade</dt><dd>" + esc(i.unidade) + "</dd><dt>Fonte</dt><dd><code>" + esc(i.fonte) + "</code></dd>" +
      "<dt>Cenário</dt><dd>" + esc(i.cenario) + "</dd><dt>Método</dt><dd>" + esc(i.metodo) + "</dd><dt>Cobertura</dt><dd>" + esc(i.cobertura) + "</dd><dt>Limitações</dt><dd>" + esc(i.limitacoes) + "</dd></dl>";
  }

  /* ---------------------------------------------------------------- chuva de referência */
  function secaoChuva(d) {
    var c = d.chuva, e = c.total_por_evento_mm, P = R.P, pos = c.cenarios_na_distribuicao[String(P)], max = 160;
    var marcas = [["mediana", e.mediana], ["média", e.media], ["percentil 75", e.p75], ["percentil 90", e.p90], ["percentil 95", e.p95], ["percentil 99", e.p99]];
    var eixo = "<div class='rs-eixo' role='img' aria-label='Totais por evento de chuva e cenários de 10, 20 e 30 mm'>" + [10, 20, 30].map(function (p) { return "<span class='cen" + (p === P ? " sel" : "") + "' style='left:" + 100 * p / max + "%'><b>" + p + " mm</b></span>"; }).join("") +
      marcas.map(function (m, i) { return "<span class='qt" + (m[1] / max > 0.6 ? " dir" : "") + "' style='left:" + 100 * m[1] / max + "%;top:" + (46 + (i % 3) * 22) + "px'>" + m[0] + " " + N1.format(m[1]) + "</span>"; }).join("") + "</div>";
    return "<section class='rs-sec' id='rs-chuva' aria-labelledby='rs-h-chuva'><h2 id='rs-h-chuva'>Que chuva o estudo usa como referência?</h2>" +
      "<p class='rs-lead'>Os resultados abaixo valem para uma chuva hipotética de <b>" + P + " mm</b>, escolhida entre 10, 20 e 30 mm. Para saber que lugar cada uma ocupa nos eventos reais, medimos a série diária de " + c.periodo[0].slice(0, 4) + " a " + c.periodo[1].slice(0, 4) + ".</p>" +
      "<div class='rs-seletor' role='group' aria-label='Precipitação de referência (hipotética)'>" + [10, 20, 30].map(function (p) { return "<button type='button' data-p='" + p + "' aria-pressed='" + (p === P) + "'>" + p + " mm</button>"; }).join("") + "</div>" +
      "<div class='rs-chuva'><div><h3>" + P + " mm na série histórica</h3><p>" + esc(P === 30 ? c.leitura_da_referencia : "Corresponde ao percentil " + N0.format(100 * pos.percentil_do_total_por_evento) + " dos totais por evento; " + N1.format(pos.eventos_por_ano_com_total_igual_ou_maior) + " eventos por ano o igualam ou superam. É um cenário de sensibilidade, não a média da cidade.") + "</p>" +
      "<p class='small'>Os cenários de 10, 20 e 30 mm continuam disponíveis para análise de sensibilidade. A referência operacional é 30 mm: ilustrativa, e não a média histórica.</p></div>" +
      "<div><h3>Não confundir as médias</h3><table class='rs-tab'><tbody><tr><th scope='row'>Média anual</th><td>" + N0.format(c.media_anual_mm) + " mm por ano</td></tr><tr><th scope='row'>Média mensal</th><td>" + N0.format(c.media_mensal_mm) + " mm por mês</td></tr>" +
      "<tr><th scope='row'>Média diária (todos os dias)</th><td>" + N1.format(c.media_diaria_todos_os_dias_mm) + " mm por dia</td></tr><tr><th scope='row'>Média por dia com chuva (1 mm ou mais)</th><td>" + N1.format(c.media_por_dia_com_chuva_mm) + " mm (" + pct(c.dias_com_chuva_fracao) + " dos dias)</td></tr>" +
      "<tr><th scope='row'>Por evento (dias seguidos com chuva)</th><td>média " + N1.format(e.media) + " mm; mediana " + N1.format(e.mediana) + " mm; percentil 90 de " + N1.format(e.p90) + " mm</td></tr></tbody></table></div></div>" +
      "<h3 class='rs-sub'>Onde 10, 20 e 30 mm ficam entre os " + N0.format(c.eventos) + " eventos</h3>" + eixo +
      "<details class='rs-ficha'><summary>Fonte, tratamento e limites da série</summary><dl class='rs-dl'><dt>Fonte</dt><dd>" + esc(c.fonte) + "</dd><dt>Período</dt><dd>" + esc(c.periodo[0]) + " a " + esc(c.periodo[1]) + " (" + N0.format(c.dias) + " dias)</dd><dt>Tratamento</dt><dd>" + esc(c.tratamento) + "</dd>" +
      "<dt>Natureza</dt><dd>" + esc(c.natureza) + "</dd><dt>Evento</dt><dd>" + N0.format(c.eventos) + " eventos (" + N1.format(c.eventos_por_ano) + " por ano), duração média de " + N1.format(c.duracao_media_dias) + " dias</dd>" +
      "<dt>Limite</dt><dd>O motor aplica a chuva como um total uniforme, sem distribuição no tempo: um evento de vários dias não é uma chuva de 24 horas, e infiltração e drenagem durante o evento não são modeladas.</dd></dl></details></section>";
  }

  /* ---------------------------------------------------------------- dimensões */
  function dimA(d) {
    var D = d.dimensoes.A, P = R.P, fx = D.dados.faixas, max = 0;
    fx.forEach(function (l) { max = Math.max(max, l.c_efetivo_metodo1_max * P * 10); });
    var g = fx.map(function (l) {
      var rot = pct(l.faixa[0]) + " a " + pct(l.faixa[1]) + " construído e pavimentado";
      return faixa(rot, l.c_efetivo_metodo1_min * P * 10, l.c_efetivo_metodo1_max * P * 10, max, num(l.c_efetivo_metodo1_min * P * 10) + " a " + num(l.c_efetivo_metodo1_max * P * 10) + " m³/ha · " + N0.format(l.area_km2) + " km²", DIM_COR.A);
    }).join("");
    var t = D.dados.totais_m3, k = P / 30, f = function (x) { return N1.format(x * k / 1e6); }, tot = "<table class='rs-tab'><caption>Volume potencial gerado, " + P + " mm (milhões de m³), pelas classes que cada pacote cobre</caption><thead><tr><th scope='col'>Pacote</th><th scope='col'>Classes</th><th scope='col'>Limite inferior</th><th scope='col'>Limite superior</th></tr></thead><tbody>" +
      "<tr><th scope='row'>Método 1</th><td>edificação e via pavimentada</td><td>" + f(t.metodo1.min) + "</td><td>" + f(t.metodo1.max) + "</td></tr><tr><th scope='row'>Analogia</th><td>vegetação e similares com valor de referência</td><td>" + f(t.analoga.min) + "</td><td>" + f(t.analoga.max) + "</td></tr>" +
      "<tr><th scope='row'>Limites físicos</th><td>as demais classes (C de 0 a 1)</td><td>" + f(t.limites.min) + "</td><td>" + f(t.limites.max) + "</td></tr></tbody></table>";
    return "<section class='rs-sec rs-dim' id='rs-A' style='--dim:" + DIM_COR.A + "' aria-labelledby='rs-h-A'><p class='rs-tag'>Dimensão A · Geração (urbanização)</p><h2 id='rs-h-A'>" + esc(D.nome) + "</h2>" +
      cartao(d, D.achados[0], "<h4>Volume potencial por hectare, " + P + " mm, Método 1 (limite inferior a superior), por faixa de parcela construída e pavimentada</h4>" + g) +
      cartao(d, D.achados[1], tot) + indicadoresDe("A") + "</section>";
  }
  function dimB(d) {
    var D = d.dimensoes.B, cl = D.dados.classes, maxA = Math.max.apply(null, cl.map(function (c) { return c.area_km2; })), maxU = Math.max.apply(null, cl.map(function (c) { return c.parcela_da_incerteza_da_analogia; }));
    var areas = cl.map(function (c) { var f = c.metodo1 ? "Método 1" : c.fora_do_calculo ? "fora do cálculo" : c.analoga ? "analogia" : "só limites físicos"; return barra(c.classe, c.area_km2 / maxA, N0.format(c.area_km2) + " km² (" + pct(c.fracao, 1) + ")", c.metodo1 ? DIM_COR.A : c.fora_do_calculo ? "#8d99a0" : DIM_COR.B, f + (c.metodo1 ? ", C " + N3.format(c.metodo1[0]) + " a " + N3.format(c.metodo1[1]) : c.analoga ? ", C " + N3.format(c.analoga[0]) + " a " + N3.format(c.analoga[1]) : "")); }).join("");
    var inc = cl.filter(function (c) { return c.parcela_da_incerteza_da_analogia > 0.005; }).map(function (c) { return barra(c.classe, c.parcela_da_incerteza_da_analogia / maxU, pct(c.parcela_da_incerteza_da_analogia, 0), DIM_COR.D); }).join("");
    return "<section class='rs-sec rs-dim' id='rs-B' style='--dim:" + DIM_COR.B + "' aria-labelledby='rs-h-B'><p class='rs-tag'>Dimensão A · Geração (vegetação)</p><h2 id='rs-h-B'>" + esc(D.nome) + "</h2>" +
      cartao(d, D.achados[1], "<h4>Área de cada classe de uso do solo e o coeficiente disponível</h4><p class='small rs-leg'><span style='background:" + DIM_COR.A + "'></span>Método 1 (fundamentado) <span style='background:" + DIM_COR.B + "'></span>analogia ou só limites físicos <span style='background:#8d99a0'></span>fora do cálculo</p>" + areas) +
      cartao(d, D.achados[0], "<h4>Parcela da largura do intervalo da analogia, por classe</h4>" + inc) + indicadoresDe("B") + "</section>";
  }
  function metricasBairro() {
    return { contribuicao: ["Contribuição potencial mediana por trecho", function (b, P) { return b.contribuicao_m1_max_aeq_mediana * P / 1000; }, "m³"], decil: ["Parcela dos trechos no décimo de maior contribuição da cidade", function (b) { return b.parcela_no_decil_superior_da_cidade; }, "%"],
             geracao: ["Geração potencial por hectare (analogia, limite superior)", function (b, P) { return b.geracao_analoga_max_aeq_por_ha * P / 1000; }, "m³/ha"], imperm: ["Parcela construída e pavimentada (edificação e via)", function (b) { return b.fracao_impermeavel; }, "%"],
             topo: ["Parcela dos trechos com preenchimento de depressão", function (b) { return b.parcela_com_preenchimento; }, "%"] };
  }
  function tabelaBairros(d) {
    var P = R.P, M = metricasBairro(), m = M[R.metricaBairro], ok = d.bairros.filter(function (b) { return b.suficiente; }).slice().sort(function (a, b) { return m[1](b, P) - m[1](a, P); }).slice(0, 10);
    var max = m[1](ok[0], P), fmt = function (v) { return m[2] === "%" ? pct(v, 0) : num(v) + " " + m[2]; };
    var opc = Object.keys(M).map(function (k) { return "<option value='" + k + "'" + (k === R.metricaBairro ? " selected" : "") + ">" + esc(M[k][0]) + "</option>"; }).join("");
    return "<div class='rs-bairros'><h4>Contextos territoriais: os dez bairros de maior valor</h4><label for='rs-metrica'>Ordenar por</label><select id='rs-metrica'>" + opc + "</select>" +
      ok.map(function (b) { return barra(b.nome, m[1](b, P) / max, fmt(m[1](b, P)), DIM_COR.C, b.trechos_com_dados + " trechos · cobertura M1 " + pct(b.cobertura_m1_a_montante_mediana, 0)); }).join("") +
      "<p class='small'>Bairros com ao menos 200 trechos com dados. Valor por bairro calculado por quantis, razões ou área (nada é somado entre trechos). A cobertura do Método 1 informa o grau de confiança.</p></div>";
  }
  function dimC(d) {
    var D = d.dimensoes.C, P = R.P, q = D.dados.quantis_contribuicao_aeq, max = Math.log10(q.p99 * P / 1000) + 1, v = function (a) { return a * P / 1000; };
    var qs = [["p10", "percentil 10"], ["p25", "percentil 25"], ["p50", "mediana"], ["p75", "percentil 75"], ["p90", "percentil 90"], ["p99", "percentil 99"]];
    var g1 = "<h4>Contribuição potencial por trecho, " + P + " mm (Método 1, limite superior; escala logarítmica)</h4>" + qs.map(function (x) { var val = v(q[x[0]]); return barra(x[1], Math.max(0.01, (Math.log10(Math.max(val, 1e-3)) + 1) / max), num(val) + " m³", DIM_COR.C); }).join("");
    var e2 = D.achados[1].evidencia, g2 = "<h4>Trechos com algum preenchimento de depressão</h4>" + barra("no décimo de maior contribuição", e2.parcela_com_preenchimento_no_decil_superior, pct(e2.parcela_com_preenchimento_no_decil_superior, 0), DIM_COR.C) +
      barra("nos demais trechos", e2.parcela_com_preenchimento_nos_demais, pct(e2.parcela_com_preenchimento_nos_demais, 0), "#9a86bd");
    return "<section class='rs-sec rs-dim' id='rs-C' style='--dim:" + DIM_COR.C + "' aria-labelledby='rs-h-C'><p class='rs-tag'>Dimensões B e C · Concentração e topografia</p><h2 id='rs-h-C'>" + esc(D.nome) + "</h2>" +
      cartao(d, D.achados[0], g1) + cartao(d, D.achados[1], g2 + tabelaBairros(d)) + indicadoresDe("C") + "</section>";
  }
  function dimD(d) {
    var D = d.dimensoes.D, q = D.dados.por_quintil, cat = D.dados.rede_por_categoria, nome = { rede_pluvial: "Cadastro existente", rede_pluvial_sem_acesso: "Registro sem acesso", rede_pluvial_nao_interligada: "Cadastrado como não interligado" };
    var g1 = "<h4>Rede pluvial cadastrada por categoria</h4>" + Object.keys(cat).map(function (k) { return barra(nome[k], cat[k].km / cat.rede_pluvial.km, N1.format(cat[k].km) + " km", DIM_COR.D, N0.format(cat[k].trechos) + " trechos"); }).join("");
    var g2 = "<h4>Parcela dos trechos com elemento cadastrado por perto, por quintil de contribuição potencial (1 = menor, 5 = maior)</h4>" + q.map(function (l) {
      return barra("Quintil " + l.quintil + ": boca de lobo a até 50 m", l.com_boca_de_lobo_ate_50m, pct(l.com_boca_de_lobo_ate_50m, 0), DIM_COR.D) + barra("Quintil " + l.quintil + ": rede a até 30 m", l.com_rede_ate_30m, pct(l.com_rede_ate_30m, 0), "#c9a27a"); }).join("");
    return "<section class='rs-sec rs-dim' id='rs-D' style='--dim:" + DIM_COR.D + "' aria-labelledby='rs-h-D'><p class='rs-tag'>Dimensão D · Drenagem</p><h2 id='rs-h-D'>" + esc(D.nome) + "</h2><p class='rs-aviso'>" + esc(TEXTOS.drenagem) + "</p>" +
      cartao(d, D.achados[0], g1) + cartao(d, D.achados[1], g2) + indicadoresDe("D") + "</section>";
  }

  /* ---------------------------------------------------------------- cenários e síntese */
  function secaoCenarios(d) {
    var C = d.cenarios, v = C.dados, P = R.P, ps = ["10", "20", "30"], mi = function (x) { return N1.format(x / 1e6); }, lim = ["100", "1000", "10000"];
    var linha = function (rot, f) { return "<tr><th scope='row'>" + rot + "</th>" + ps.map(function (p) { return "<td" + (Number(p) === P ? " class='sel'" : "") + ">" + f(v[p]) + "</td>"; }).join("") + "</tr>"; };
    var tab = "<table class='rs-tab rs-cen'><caption>Como os resultados mudam sob 10, 20 e 30 mm</caption><thead><tr><th scope='col'><span class='sr-only'>Medida</span></th>" + ps.map(function (p) { return "<th scope='col'" + (Number(p) === P ? " class='sel'" : "") + ">" + p + " mm</th>"; }).join("") + "</tr></thead><tbody>" +
      linha("Volume gerado, Método 1 (milhões de m³)", function (x) { return mi(x.geracao_cidade_m3.metodo1.min) + " a " + mi(x.geracao_cidade_m3.metodo1.max); }) +
      linha("Volume gerado, analogia (milhões de m³)", function (x) { return mi(x.geracao_cidade_m3.analoga.min) + " a " + mi(x.geracao_cidade_m3.analoga.max); }) +
      linha("Volume gerado, limites físicos (milhões de m³)", function (x) { return mi(x.geracao_cidade_m3.limites.min) + " a " + mi(x.geracao_cidade_m3.limites.max); }) +
      linha("Geração local por trecho: mediana / percentil 99 (m³)", function (x) { return num(x.por_trecho_m1_max_m3.local.p50) + " / " + num(x.por_trecho_m1_max_m3.local.p99); }) +
      linha("Contribuição por trecho: mediana / percentil 99 (m³)", function (x) { return num(x.por_trecho_m1_max_m3.contribuicao.p50) + " / " + num(x.por_trecho_m1_max_m3.contribuicao.p99); }) +
      lim.map(function (L) { return linha("Trechos com contribuição de " + N0.format(Number(L)) + " m³ ou mais", function (x) { return N0.format(x.trechos_com_contribuicao_acima_de_m3[L]); }); }).join("") + "</tbody></table>";
    return "<section class='rs-sec' id='rs-cenarios' aria-labelledby='rs-h-cen'><p class='rs-tag'>Comparação</p><h2 id='rs-h-cen'>Cenários de 10, 20 e 30 mm</h2>" + cartao(d, C.achados[0], "<div class='rolagem'>" + tab + "</div>") +
      "<p class='small'>Os volumes por pacote são os das classes que cada pacote cobre e não se somam. A distribuição espacial das classes é idêntica nos três cenários; só muda a faixa em m³. Os números maiores não indicam alagamento maior.</p></section>";
  }
  function secaoSintese(d) {
    var S = d.sintese, P = R.P, L = S.lacunas_de_dados, p = S.contextos_prioritarios_hipoteses;
    var linhasB = function (lista) {
      return "<div class='rolagem'><table class='rs-tab'><thead><tr><th scope='col'>Bairro</th><th scope='col'>Contribuição mediana (m³)</th><th scope='col'>No décimo superior</th><th scope='col'>Construído e pavimentado</th><th scope='col'>Cobertura Método 1</th><th scope='col'>Trechos</th><th scope='col'>Rede cadastrada (km/km²)</th></tr></thead><tbody>" +
        lista.map(function (b) { return "<tr><th scope='row'>" + esc(b.nome) + "</th><td>" + num(b.contribuicao_m1_max_aeq_mediana * P / 1000) + "</td><td>" + pct(b.parcela_no_decil_superior_da_cidade, 0) + "</td><td>" + pct(b.fracao_impermeavel, 0) + "</td><td>" + pct(b.cobertura_m1_a_montante_mediana, 0) + "</td><td>" + N0.format(b.trechos_com_dados) + "</td><td>" + (b.rede_km_por_km2 == null ? "sem dados" : N1.format(b.rede_km_por_km2)) + "</td></tr>"; }).join("") + "</tbody></table></div>";
    };
    return "<section class='rs-sec rs-sintese' id='rs-sintese' aria-labelledby='rs-h-sint'><p class='rs-tag'>Síntese</p><h2 id='rs-h-sint'>O que esses resultados significam para o território?</h2><p class='rs-aviso'>" + esc(TEXTOS.aviso) + "</p>" +
      "<h3>Contextos que merecem investigação prioritária (hipóteses)</h3><p>" + esc(p.criterio) + ". São pontos de partida para investigar, não achados confirmados nem pontos de alagamento.</p>" +
      "<h4>Maior contribuição potencial mediana por trecho, " + P + " mm</h4>" + linhasB(p.por_contribuicao_mediana) + "<h4>Maior parcela dos trechos no décimo de maior contribuição da cidade</h4>" + linhasB(p.por_parcela_no_decil_superior) +
      "<h3>Áreas com maior contribuição potencial estimada</h3><p>Os valores mais altos vêm de eixos onde o relevo junta bacias extensas (percentil 99 de " + num(d.dimensoes.C.dados.quantis_contribuicao_aeq.p99 * P / 1000) + " m³ por trecho para " + P + " mm), em contraste com uma mediana de " + num(d.dimensoes.C.dados.quantis_contribuicao_aeq.p50 * P / 1000) + " m³. A leitura é por trecho e por contexto, nunca soma.</p>" +
      "<h3>Lacunas de dados</h3><ul><li><b>Coeficientes:</b> " + pct(L.area_sem_coeficiente_fundamentado) + " da área classificada não tem coeficiente fundamentado.</li><li><b>Cobertura espacial:</b> " + N0.format(L.trechos_sem_dados) + " trechos sem dados, que ficam sem valor, nunca com zero.</li><li><b>Validação:</b> " + esc(L.validacao) + ".</li><li><b>Relevo:</b> " + esc(L.relevo) + ".</li></ul>" +
      "<h3>Limitações da drenagem cadastrada</h3><p>" + esc(L.drenagem) + ". O cadastro está fora do cálculo e a sua cobertura confunde comparações: onde não há cadastro, não se sabe se não há infraestrutura.</p>" +
      "<h3>O que seria necessário para uma análise hidráulica de alagamentos</h3><ul>" + S.para_uma_analise_hidraulica.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul></section>";
  }
  function registro(d) {
    return "<section class='rs-sec' id='rs-registro' aria-labelledby='rs-h-reg'><h2 id='rs-h-reg'>Registro de indicadores e rastreabilidade</h2><p>Cada indicador executivo é calculado dos dados reais por <code>tools/gerar_resultados.py</code>. Fórmula, unidade, fonte, cenário, método, cobertura e limitações de todos eles:</p>" +
      "<details class='rs-indic'><summary>Ver os " + d.indicadores.length + " indicadores</summary>" + d.indicadores.map(tabelaIndicador).join("") + "</details></section>";
  }

  R.corpo = function (d) {
    return R.avisoCopia() + "<header class='rs-topo'><p class='rs-tag'>Resultados do estudo · Porto Alegre</p><h1>" + esc(d.pergunta) + "</h1><p class='rs-aviso'>" + esc(TEXTOS.aviso) + "</p>" +
      "<nav class='rs-nav' aria-label='Seções dos resultados'><a href='#rs-chuva'>Chuva de referência</a><a href='#rs-A'>A Urbanização</a><a href='#rs-B'>B Vegetação</a><a href='#rs-C'>C Topografia</a><a href='#rs-D'>D Drenagem</a><a href='#rs-cenarios'>Cenários</a><a href='#rs-sintese'>Síntese</a><a href='#rs-registro'>Indicadores</a></nav></header>" +
      secaoChuva(d) + dimA(d) + dimB(d) + dimC(d) + dimD(d) + secaoCenarios(d) + secaoSintese(d) + registro(d);
  };
  R.render = function (box, territorio) {
    if (territorio !== "poa") { box.innerHTML = "<section class='rs-sec'><h1>Resultados do estudo</h1><p>Os resultados executivos existem para Porto Alegre, onde o motor de escoamento potencial foi executado. Escolha Porto Alegre no seletor de território.</p></section>"; return; }
    box.innerHTML = "<p class='small' role='status'>Carregando os resultados...</p>";
    carregar().then(function (d) { desenhar(box, d); }).catch(function (e) { box.innerHTML = "<p role='alert'>Não foi possível carregar os resultados (" + esc(e.message) + "). Gere-os com tools/gerar_resultados.py.</p>"; });
  };
  function desenhar(box, d) {
    var aberto = Array.prototype.map.call(box.querySelectorAll("details[open]"), function (x) { return x.querySelector("summary").textContent; }), y = window.scrollY;
    box.innerHTML = R.corpo(d);
    Array.prototype.forEach.call(box.querySelectorAll("details"), function (x) { if (aberto.indexOf(x.querySelector("summary").textContent) >= 0) x.open = true; });
    Array.prototype.forEach.call(box.querySelectorAll(".rs-seletor button"), function (b) { b.addEventListener("click", function () { R.P = Number(b.dataset.p); desenhar(box, d); window.scrollTo(0, y); }); });
    var sel = box.querySelector("#rs-metrica"); if (sel) sel.addEventListener("change", function () { R.metricaBairro = sel.value; desenhar(box, d); window.scrollTo(0, y); var n = document.getElementById("rs-metrica"); if (n) n.focus(); });
  }
})();
