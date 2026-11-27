/* Landing científica: navegação por âncoras com seção atual, seletor das quatro dimensões do mapa, ampliação do mapa, comparador de cenários e entrada suave.
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

  /* seletor das quatro dimensões: sem script as quatro vêm empilhadas e legíveis; com script, uma de cada vez (as imagens das outras só carregam ao serem escolhidas) */
  var abas = $$("[data-mapas] [role=tab]");
  $$("[data-mapas]").forEach(function (c) {
    var lista = $("[role=tablist]", c); if (lista) lista.hidden = false;
    $$("[role=tabpanel]", c).forEach(function (p) { p.hidden = p.getAttribute("aria-labelledby") !== (abas.filter(function (b) { return b.getAttribute("aria-selected") === "true"; })[0] || {}).id; });
    $$(".ampliar", c).forEach(function (b) { b.hidden = false; });
  });
  function escolher(aba) {
    abas.forEach(function (b) { var ativa = b === aba; b.setAttribute("aria-selected", String(ativa)); b.tabIndex = ativa ? 0 : -1; var p = document.getElementById(b.getAttribute("aria-controls")); if (p) p.hidden = !ativa; });
  }
  abas.forEach(function (aba) {
    aba.addEventListener("click", function () { escolher(aba); });
    aba.addEventListener("keydown", function (e) {
      var i = abas.indexOf(aba), j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? abas.length - 1 : -1;
      if (j >= 0) { var alvo = abas[(j + abas.length) % abas.length]; alvo.focus(); escolher(alvo); e.preventDefault(); }
    });
  });

  /* ampliar o mapa de manchas: a imagem em tamanho natural dentro de uma janela rolável, com mais e menos zoom; o pinça do celular também funciona */
  var zoom = null;
  function janelaZoom() {
    if (zoom) return zoom;
    var d = document.createElement("dialog"); d.className = "zoom"; d.setAttribute("aria-label", "Mapa ampliado");
    d.innerHTML = "<div class='zoom-barra'><strong class='zoom-nome'></strong><span><button type='button' data-z='-' aria-label='Reduzir o mapa'>−</button><button type='button' data-z='+' aria-label='Aumentar o mapa'>+</button><button type='button' data-z='x' class='zoom-fechar'>Fechar</button></span></div><div class='zoom-area' tabindex='0' role='region' aria-label='Mapa ampliado, role para mover'><img alt=''></div>";
    document.body.appendChild(d);
    var img = $("img", d), nivel = 1, base = 0;
    var aplicar = function () { img.style.width = Math.round(base * nivel) + "px"; $("[data-z='-']", d).disabled = nivel <= 1; $("[data-z='+']", d).disabled = nivel >= 4; };
    d.addEventListener("click", function (e) {
      var z = e.target.getAttribute && e.target.getAttribute("data-z"); if (!z) return;
      if (z === "x") { d.close(); return; }
      nivel = Math.max(1, Math.min(4, nivel + (z === "+" ? .5 : -.5))); aplicar();
    });
    d.addEventListener("close", function () { if (d._de) d._de.focus(); });
    d._abrir = function (de, src, alt, nome, larg) { d._de = de; img.src = src; img.alt = alt; $(".zoom-nome", d).textContent = nome; base = Math.min(window.innerWidth - 24, larg); nivel = 1; aplicar(); d.showModal(); $(".zoom-area", d).scrollTop = 0; };
    return (zoom = d);
  }
  $$(".ampliar").forEach(function (b) {
    b.addEventListener("click", function () {
      var f = b.closest("figure"), im = $("img", f); if (typeof HTMLDialogElement === "undefined") { window.open(b.getAttribute("data-ampliar"), "_blank", "noopener"); return; }
      janelaZoom()._abrir(b, im.currentSrc || im.src, im.alt, b.getAttribute("data-nome"), +b.getAttribute("data-largura"));
    });
  });

  /* navegação em telas estreitas: indica que há mais abas além da borda e traz a seção atual para a vista */
  var faixa = $(".ancoras");
  function bordas() { if (!faixa) return; var max = faixa.scrollWidth - faixa.clientWidth; faixa.classList.toggle("rola-esq", faixa.scrollLeft > 4); faixa.classList.toggle("rola-dir", max > 4 && faixa.scrollLeft < max - 4); }
  if (faixa) {
    faixa.addEventListener("scroll", bordas, { passive: true }); window.addEventListener("resize", bordas); bordas();
    var atual = function () { var a = $("a[aria-current=true]", faixa); if (a && faixa.scrollWidth > faixa.clientWidth + 4) faixa.scrollTo({ left: a.offsetLeft - (faixa.clientWidth - a.offsetWidth) / 2, behavior: reduz ? "auto" : "smooth" }); };
    new MutationObserver(atual).observe(faixa, { attributes: true, subtree: true, attributeFilter: ["aria-current"] });
  }

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
      var a = $("#cen-link"); if (a.getAttribute("data-camadas") === "1") { a.href = "../?painel=1#poa/mapa?escoamento=1&p=" + p; a.textContent = "Abrir o simulador no mapa (" + p + " mm)"; }
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
