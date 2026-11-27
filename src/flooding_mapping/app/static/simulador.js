/* Aba "Simulador de cenários de cálculo" (Porto Alegre). Não é um simulador hidráulico e não tem motor próprio: escolhe entre as três execuções do motor
   da Fase 3 (10, 20 e 30 mm) já resumidas em data/resultados_poa.json e mostra como mudam os volumes potenciais, a distribuição dos trechos por faixa e a
   comparação territorial. A única conta feita aqui é a escala linear V = P x aeq / 1000, a mesma do motor (conferida em tests/test_simulador.py contra a
   saída do motor). A chuva escolhida é a mesma da aba Resultados (window.Resultados.P) e vai para o mapa pelo endereço. */
(function () {
  "use strict";
  var Lg = window.Logic, R = window.Resultados;
  var S = { bairro: null };
  window.Simulador = S;
  var esc = function (s) { return Lg.esc(s); };
  var N0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }), N1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }), N3 = new Intl.NumberFormat("pt-BR", { maximumSignificantDigits: 3 });
  function num(v) { return v == null || !isFinite(v) ? "sem dados" : (Math.abs(v) >= 100 ? N0 : N3).format(v); }
  function mi(v) { return N1.format(v / 1e6); }
  var PS = ["10", "20", "30"], LIM = [100, 1000, 10000];
  var PACOTES = [["metodo1", "Método 1: coeficientes fundamentados", "classes de edificação e via"], ["analoga", "Método 2: cenários por analogia", "vegetação e classes similares, jardins em envelope"], ["limites", "Limites físicos (C de 0 a 1)", "as demais classes; referência matemática, não previsão"]];

  /* Contagem de trechos por faixa de contribuição potencial (Método 1, limite superior), a partir dos cortes de 100, 1.000 e 10.000 m³. */
  S.faixas = function (cen, p) {
    var v = cen.dados[String(p)], a = v.trechos_com_contribuicao_acima_de_m3, n = v.trechos_com_dados;
    return [["Menos de 100 m³", n - a["100"]], ["De 100 a 1.000 m³", a["100"] - a["1000"]], ["De 1.000 a 10.000 m³", a["1000"] - a["10000"]], ["10.000 m³ ou mais", a["10000"]]];
  };
  S.bairros = function (d) { return d.bairros.filter(function (b) { return b.suficiente; }); };
  S.contribuicaoMediana = function (b, P) { return R.volume(b.contribuicao_m1_max_aeq_mediana, P); };

  function barra(rot, frac, valor, sel) {
    return "<div class='rs-barra'><span>" + rot + "</span><div class='rs-trilho' role='img' aria-label='" + rot + ": " + valor + "'><i style='width:" + Math.max(0.6, 100 * frac) + "%;background:" + (sel ? "var(--dim)" : "#9fb1bd") + "'></i></div><span>" + valor + "</span></div>";
  }
  function corpo(d) {
    var P = R.P, c = d.chuva, pos = c.cenarios_na_distribuicao[String(P)], C = d.cenarios, v = C.dados[String(P)], s1 = C.achados[0];
    var seletor = "<div class='rs-seletor' role='group' aria-label='Precipitação do cenário (hipotética)'>" + [10, 20, 30].map(function (p) { return "<button type='button' data-p='" + p + "' aria-pressed='" + (p === P) + "'>" + p + " mm</button>"; }).join("") + "</div>";
    var ctx = P === 30 ? "30 mm é o percentil 75 dos totais por evento de " + c.periodo[0].slice(0, 4) + " a " + c.periodo[1].slice(0, 4) + " (" + N1.format(pos.eventos_por_ano_com_total_igual_ou_maior) + " eventos por ano o igualam ou superam). Não é a média histórica."
      : P + " mm fica no percentil " + N0.format(100 * pos.percentil_do_total_por_evento) + " dos totais por evento (" + N1.format(pos.eventos_por_ano_com_total_igual_ou_maior) + " eventos por ano o igualam ou superam). É um cenário de sensibilidade.";
    var maxCid = Math.max.apply(null, PS.map(function (p) { return C.dados[p].geracao_cidade_m3.limites.max; }));
    var cidade = PACOTES.map(function (k) {
      var g = v.geracao_cidade_m3[k[0]], l = 100 * g.min / maxCid, w = Math.max(0.6, 100 * (g.max - g.min) / maxCid);
      var rot = k[1], val = mi(g.min) + " a " + mi(g.max) + " milhões de m³";
      return "<div class='rs-barra'><span>" + esc(rot) + "<br><span class='small'>" + esc(k[2]) + "</span></span><div class='rs-trilho' role='img' aria-label='" + esc(rot) + ": " + val + "'><i style='left:" + l + "%;width:" + w + "%;background:var(--dim)'></i></div><span>" + val + "</span></div>";
    }).join("");
    var q = v.por_trecho_m1_max_m3;
    var porTrecho = "<table class='rs-tab'><caption>Por trecho de rua (Método 1, limite superior), " + P + " mm</caption><thead><tr><th scope='col'><span class='sr-only'>Medida</span></th><th scope='col'>Mediana</th><th scope='col'>Percentil 90</th><th scope='col'>Percentil 99</th></tr></thead><tbody>" +
      "<tr><th scope='row'>Geração potencial local (m³)</th><td>" + num(q.local.p50) + "</td><td>" + num(q.local.p90) + "</td><td>" + num(q.local.p99) + "</td></tr>" +
      "<tr><th scope='row'>Contribuição potencial acumulada (m³)</th><td>" + num(q.contribuicao.p50) + "</td><td>" + num(q.contribuicao.p90) + "</td><td>" + num(q.contribuicao.p99) + "</td></tr></tbody></table>" +
      "<p class='small'>A contribuição de um trecho inclui a de bacias que ele compartilha com outros trechos: <b>não some os valores entre trechos</b>.</p>";
    var fx = S.faixas(C, P), nTot = v.trechos_com_dados;
    var faixas = fx.map(function (f) { return barra(f[0], f[1] / nTot, N0.format(f[1]) + " trechos (" + N1.format(100 * f[1] / nTot) + "%)", true); }).join("");
    var cmpFaixas = PS.map(function (p) {
      var f = S.faixas(C, p), top = f[3][1] + f[2][1];
      return "<tr" + (Number(p) === P ? " class='sel'" : "") + "><th scope='row'>" + p + " mm</th>" + f.map(function (x) { return "<td>" + N0.format(x[1]) + "</td>"; }).join("") + "</tr>";
    }).join("");
    var fator = function (p) { return { 10: "1/3", 20: "2/3", 30: "1" }[p]; };
    var cmpVol = "<table class='rs-tab rs-cen'><caption>Volume gerado e contribuição nos três cenários</caption><thead><tr><th scope='col'><span class='sr-only'>Medida</span></th>" + PS.map(function (p) { return "<th scope='col'" + (Number(p) === P ? " class='sel'" : "") + ">" + p + " mm</th>"; }).join("") + "</tr></thead><tbody>" +
      "<tr><th scope='row'>Fator em relação a 30 mm</th>" + PS.map(function (p) { return "<td>× " + fator(Number(p)) + "</td>"; }).join("") + "</tr>" +
      "<tr><th scope='row'>Volume gerado, Método 1 (milhões de m³)</th>" + PS.map(function (p) { var g = C.dados[p].geracao_cidade_m3.metodo1; return "<td>" + mi(g.min) + " a " + mi(g.max) + "</td>"; }).join("") + "</tr>" +
      "<tr><th scope='row'>Contribuição mediana por trecho (m³)</th>" + PS.map(function (p) { return "<td>" + num(C.dados[p].por_trecho_m1_max_m3.contribuicao.p50) + "</td>"; }).join("") + "</tr>" +
      "<tr><th scope='row'>Contribuição do percentil 99 (m³)</th>" + PS.map(function (p) { return "<td>" + num(C.dados[p].por_trecho_m1_max_m3.contribuicao.p99) + "</td>"; }).join("") + "</tr></tbody></table>";
    var ok = s1.verificada && s1.evidencia.ordem_dos_trechos_igual;
    var validacao = "<p class='rs-aviso' role='note'>" + (ok ? "<b>Verificado nos dados:</b> a ordem dos trechos por contribuição é a mesma nos três cenários e o volume por trecho de 30 mm é " + N1.format(s1.evidencia.fator_30_sobre_10) + " vezes o de 10 mm (erro máximo " + s1.evidencia.erro_maximo_do_fator_3_por_trecho.toExponential(1) + "). Mais chuva multiplica os volumes; não muda quais trechos concentram mais contribuição."
      : "A verificação da ordem dos trechos não se confirmou nesta geração dos resultados; leia as comparações com cautela.") + "</p>";
    var bs = S.bairros(d).slice().sort(function (a, b) { return a.nome.localeCompare(b.nome, "pt-BR"); });
    if (!S.bairro || !bs.some(function (b) { return b.nome === S.bairro; })) S.bairro = bs.reduce(function (m, b) { return b.contribuicao_m1_max_aeq_mediana > m.contribuicao_m1_max_aeq_mediana ? b : m; }, bs[0]).nome;
    var sel = bs.filter(function (b) { return b.nome === S.bairro; })[0];
    var seletorBairro = "<label for='sim-bairro'>Bairro (somente com 200 trechos com dados ou mais)</label><select id='sim-bairro'>" + bs.map(function (b) { return "<option" + (b.nome === S.bairro ? " selected" : "") + ">" + esc(b.nome) + "</option>"; }).join("") + "</select>";
    var cidMed = d.dimensoes.C.dados.quantis_contribuicao_aeq.p50;
    var terr = "<table class='rs-tab'><caption>Contribuição mediana por trecho, " + esc(sel.nome) + " (Método 1, limite superior)</caption><thead><tr><th scope='col'><span class='sr-only'>Medida</span></th>" + PS.map(function (p) { return "<th scope='col'" + (Number(p) === P ? " class='sel'" : "") + ">" + p + " mm</th>"; }).join("") + "</tr></thead><tbody>" +
      "<tr><th scope='row'>" + esc(sel.nome) + " (m³)</th>" + PS.map(function (p) { return "<td>" + num(S.contribuicaoMediana(sel, Number(p))) + "</td>"; }).join("") + "</tr>" +
      "<tr><th scope='row'>Mediana da cidade (m³)</th>" + PS.map(function (p) { return "<td>" + num(R.volume(cidMed, Number(p))) + "</td>"; }).join("") + "</tr></tbody></table>" +
      "<p class='small'>Parcela dos trechos do bairro no décimo de maior contribuição da cidade: <b>" + N0.format(100 * sel.parcela_no_decil_superior_da_cidade) + "%</b> (não depende da chuva). Bairro atribuído pelo ponto médio do trecho; o valor descreve trechos, não o bairro inteiro.</p>";
    var top = bs.slice().sort(function (a, b) { return b.contribuicao_m1_max_aeq_mediana - a.contribuicao_m1_max_aeq_mediana; }).slice(0, 5);
    var tabTop = "<table class='rs-tab'><caption>Cinco bairros com maior contribuição mediana por trecho, " + P + " mm</caption><thead><tr><th scope='col'>Bairro</th><th scope='col'>Mediana (m³)</th></tr></thead><tbody>" +
      top.map(function (b) { return "<tr><th scope='row'>" + esc(b.nome) + "</th><td>" + num(S.contribuicaoMediana(b, P)) + "</td></tr>"; }).join("") + "</tbody></table><p class='small'>A ordem dos bairros não muda com a chuva, só os valores.</p>";
    return R.avisoCopia() + "<header class='rs-topo' style='--dim:#0b5d8f'><p class='rs-tag'>Simulador de cenários de cálculo · Porto Alegre</p><h1>Como mudam os resultados quando a chuva de referência muda?</h1>" +
      "<p class='rs-aviso'>Este simulador compara três execuções do motor de escoamento potencial. Não é um simulador hidráulico: não calcula profundidade, extensão ou duração de alagamento, nem a capacidade da rede de drenagem. A chuva é uniforme e sem distribuição no tempo: um evento de dois dias não equivale a uma chuva de 24 horas.</p></header>" +
      "<section class='rs-sec' aria-labelledby='sim-h-chuva' style='--dim:#0b5d8f'><h2 id='sim-h-chuva'>Escolha a chuva do cenário</h2>" + seletor + "<p class='rs-lead' id='sim-ctx'>" + esc(ctx) + "</p>" +
      "<p class='small'>Série diária modelada (reanálise ERA5, Open-Meteo), não pluviômetros. Evento = dias seguidos com 1 mm ou mais.</p>" +
      "<p><a class='rs-ir' id='sim-mapa' href='#poa/mapa?escoamento=1&p=" + P + "&pacote=m1&modo=c'>Ver esta chuva no mapa (" + P + " mm)</a> · <a href='#poa/resultados'>Ler os resultados por contexto territorial</a></p></section>" +
      "<section class='rs-sec' aria-labelledby='sim-h-vol' style='--dim:#0b5d8f'><h2 id='sim-h-vol'>Volume potencial gerado na cidade, " + P + " mm</h2>" +
      "<p>Água potencialmente escoada pelas classes de cada pacote: cada pacote cobre classes diferentes, por isso os valores <b>não se somam</b> nem são alternativas diretas.</p>" + cidade + "<p class='small'>Barra = intervalo entre limite inferior e superior dos coeficientes. É estimativa condicionada à chuva hipotética, não volume medido.</p>" + porTrecho + "</section>" +
      "<section class='rs-sec' aria-labelledby='sim-h-faixas' style='--dim:#0b5d8f'><h2 id='sim-h-faixas'>Quantos trechos ficam em cada faixa de contribuição, " + P + " mm</h2>" + faixas +
      "<p class='small'>Trechos com dados: " + N0.format(nTot) + " (Método 1, limite superior). Trechos sem dados ficam fora da contagem e não valem zero.</p>" +
      "<div class='rolagem'><table class='rs-tab'><caption>Os três cenários lado a lado</caption><thead><tr><th scope='col'><span class='sr-only'>Medida</span></th><th scope='col'>&lt; 100 m³</th><th scope='col'>100 a 1.000</th><th scope='col'>1.000 a 10.000</th><th scope='col'>≥ 10.000</th></tr></thead><tbody>" + cmpFaixas + "</tbody></table></div></section>" +
      "<section class='rs-sec' aria-labelledby='sim-h-cmp' style='--dim:#0b5d8f'><h2 id='sim-h-cmp'>Comparação entre os cenários</h2><div class='rolagem'>" + cmpVol + "</div>" + validacao + "</section>" +
      "<section class='rs-sec' aria-labelledby='sim-h-terr' style='--dim:#0b5d8f'><h2 id='sim-h-terr'>Comparação territorial</h2><div class='rs-bairros'>" + seletorBairro + "<div id='sim-terr'>" + terr + "</div></div>" + tabTop +
      "<p class='small'>Os rankings usam quantis e razões entre trechos. Não há índice composto, e a drenagem cadastrada não entra no cálculo.</p></section>";
  }
  S.corpo = corpo;
  S.render = function (box, territorio) {
    if (territorio !== "poa") { box.innerHTML = "<section class='rs-sec'><h1>Simulador de cenários</h1><p>O simulador existe para Porto Alegre, onde o motor de escoamento potencial foi executado. Escolha Porto Alegre no seletor de território.</p></section>"; return; }
    box.innerHTML = "<p class='small' role='status'>Carregando os cenários...</p>";
    R.carregar().then(function (d) { desenhar(box, d); }).catch(function (e) { box.innerHTML = "<p role='alert'>Não foi possível carregar os cenários (" + esc(e.message) + "). Gere-os com tools/gerar_resultados.py.</p>"; });
  };
  function desenhar(box, d) {
    var y = window.scrollY, foco = document.activeElement && document.activeElement.id;
    box.innerHTML = corpo(d);
    Array.prototype.forEach.call(box.querySelectorAll(".rs-seletor button"), function (b) { b.addEventListener("click", function () { R.P = Number(b.dataset.p); desenhar(box, d); window.scrollTo(0, y); var n = box.querySelector(".rs-seletor button[data-p='" + R.P + "']"); if (n) n.focus(); }); });
    var sel = box.querySelector("#sim-bairro"); if (sel) sel.addEventListener("change", function () { S.bairro = sel.value; desenhar(box, d); window.scrollTo(0, y); var n = document.getElementById("sim-bairro"); if (n) n.focus(); });
    if (foco && foco !== "sim-bairro" && document.getElementById(foco)) document.getElementById(foco).focus();
  }
})();
