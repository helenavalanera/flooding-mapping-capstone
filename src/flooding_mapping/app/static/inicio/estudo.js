/* Landing científica: navegação por âncoras com seção atual, abas das camadas do mapa, comparador de cenários e entrada suave.
   Sem script, tudo continua legível: as abas mostram só a primeira camada, mas as quatro imagens estão no HTML; o comparador mostra os valores de 30 mm.
   O comparador usa os números reais das três execuções do motor (embutidos na página): nenhuma conta nova, só a escolha da chuva. */
(function () {
  "use strict";
  var reduz = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (s, r) { return (r || document).querySelector(s); }, $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var NUM = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }), NUM0 = new Intl.NumberFormat("pt-BR", { maximumSignificantDigits: 3 });

  /* Gráficos que rolam na horizontal (telas estreitas) precisam ser alcançáveis pelo teclado: só recebem foco quando de fato rolam. */
  function regioesRolaveis() { $$(".graficos > figure, .grafico-grande, .tabela-rolagem").forEach(function (f) { if (f.scrollWidth > f.clientWidth + 1) { f.setAttribute("tabindex", "0"); } else { f.removeAttribute("tabindex"); } }); }
  regioesRolaveis(); window.addEventListener("resize", regioesRolaveis); window.addEventListener("load", regioesRolaveis);

  /* Uma citação do texto leva a uma referência dentro de uma categoria recolhida: abre a categoria antes de rolar até ela. */
  function abrirReferenciaAlvo() {
    var alvo = location.hash.length > 1 ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    var cat = alvo && alvo.closest ? alvo.closest("details.ref-cat") : null;
    if (cat && !cat.open) { cat.open = true; alvo.scrollIntoView(); }
  }
  window.addEventListener("hashchange", abrirReferenciaAlvo); abrirReferenciaAlvo();

  /* seção atual na navegação */
  var links = $$(".ancoras a"), secoes = links.map(function (a) { return document.getElementById(a.getAttribute("href").slice(1)); });
  if ("IntersectionObserver" in window) {
    var visiveis = {};
    var io = new IntersectionObserver(function (itens) {
      itens.forEach(function (i) { visiveis[i.target.id] = i.isIntersecting ? i.intersectionRatio : 0; });
      var melhor = null, v = 0; secoes.forEach(function (s) { if (s && (visiveis[s.id] || 0) > v) { v = visiveis[s.id]; melhor = s.id; } });
      links.forEach(function (a) { if (a.getAttribute("href") === "#" + melhor) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current"); });
    }, { rootMargin: "-20% 0px -55% 0px", threshold: [0, .1, .3, .6, 1] });
    secoes.forEach(function (s) { if (s) io.observe(s); });
  }

  /* abas das camadas do mapa */
  var abas = $$("[data-mapas] [role=tab]");
  abas.forEach(function (aba) {
    aba.addEventListener("click", function () {
      abas.forEach(function (b) { var ativa = b === aba; b.setAttribute("aria-selected", String(ativa)); var p = document.getElementById(b.getAttribute("aria-controls")); if (p) p.hidden = !ativa; });
    });
    aba.addEventListener("keydown", function (e) {
      var i = abas.indexOf(aba), j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : -1;
      if (j >= 0) { var alvo = abas[(j + abas.length) % abas.length]; alvo.focus(); alvo.click(); e.preventDefault(); }
    });
  });

  /* comparador de cenários */
  var bruto = $("#dados-cenarios"), campo = $("[data-cenarios]");
  if (bruto && campo) {
    var D = JSON.parse(bruto.textContent), P0 = 30;
    var PACOTES = [["metodo1", "Método 1: coeficientes fundamentados", "estimativa com referência publicada", false], ["referencia_analoga", "Método 2: cenários por analogia", "hipótese declarada; jardins e passeios em envelope", false],
                   ["limites_fisicos", "Limites físicos (C de 0 a 1)", "referência matemática, não previsão", true]];
    var maximo = 0; Object.keys(D.totais_m3).forEach(function (p) { PACOTES.forEach(function (k) { maximo = Math.max(maximo, D.totais_m3[p][k[0]].max_m3); }); });
    var milhoes = function (v) { return NUM.format(v / 1e6); };
    var desenhar = function (p) {
      var t = D.totais_m3[String(p)];
      $("#cen-p").textContent = p + " mm";
      $("#cen-barras").innerHTML = PACOTES.map(function (k) {
        var v = t[k[0]], l = 100 * v.min_m3 / maximo, w = 100 * (v.max_m3 - v.min_m3) / maximo;
        return "<div class='barra" + (k[3] ? " limite" : "") + "'><div class='nome'><span>" + k[1] + "</span><span class='valor'>" + milhoes(v.min_m3) + " a " + milhoes(v.max_m3) + " milhões de m³</span></div>" +
               "<div class='trilho' role='img' aria-label='" + k[1] + ": de " + milhoes(v.min_m3) + " a " + milhoes(v.max_m3) + " milhões de metros cúbicos'><i style='left:" + l + "%;width:" + w + "%'></i></div><div class='nota'>" + k[2] + "</div></div>";
      }).join("");
      var f = p / P0, c = D.por_trecho_p30_metodo1.contrib_potencial_max_m3, g = D.por_trecho_p30_metodo1.v_gerado_local_max_m3;
      var linha = function (q) { return "mediana <b>" + NUM0.format(q.q50 * f) + "</b> m³ · percentil 90: " + NUM0.format(q.q90 * f) + " m³ · percentil 99: " + NUM0.format(q.q99 * f) + " m³"; };
      $("#cen-trecho").innerHTML = "<div><dt>Contribuição potencial acumulada</dt><dd>" + linha(c) + "</dd></div><div><dt>Geração potencial local</dt><dd>" + linha(g) + "</dd></div>";
      var a = $("#cen-link"); a.href = "../?painel=1#poa/mapa?escoamento=1&p=" + p; a.textContent = "Abrir o simulador no mapa (" + p + " mm)";
      $$(".seletor button").forEach(function (b) { b.setAttribute("aria-pressed", String(Number(b.dataset.p) === p)); });
    };
    $$(".seletor button").forEach(function (b) { b.addEventListener("click", function () { desenhar(Number(b.dataset.p)); }); });
    desenhar(P0);
  }

  /* entrada suave, só com script e sem preferência por menos movimento */
  var alvos = $$(".achados li, .num, .fluxo li, .tres article, .pilares li, .contribuicoes li, .graficos figure, .grafico-grande");
  if ("IntersectionObserver" in window && !reduz) {
    alvos.forEach(function (a) { a.classList.add("rv"); });
    var io2 = new IntersectionObserver(function (itens) { itens.forEach(function (i) { if (i.isIntersecting) { i.target.classList.add("vista"); io2.unobserve(i.target); } }); }, { threshold: .08, rootMargin: "0px 0px -4% 0px" });
    alvos.forEach(function (a) { io2.observe(a); });
  }
})();
