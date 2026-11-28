/* Camada E, "GeoAI: fração construída estimada" (Porto Alegre): EXPERIMENTAL e independente das dimensões A a D. Uma imagem com transparência (uma célula de 30 m por
   quadradinho) sobre o mapa, só com a fração construída que o modelo estimou. A Profill foi a referência e a fonte dos rótulos; não há validação independente contra verdade
   de campo; a transferência para outras áreas não foi testada. Não é impermeabilidade medida, coeficiente de escoamento, vazão nem ocorrência de alagamento, e não entra em nenhum cálculo. */
(function () {
  "use strict";
  var Lg = window.Logic;
  var G = { meta: null, erro: null, _meta: null, opacidade: 0.85, ouvintes: [] };
  window.Geoai = G;

  var TEXTOS = {
    aviso: "Estimativa de fração construída por célula de 30 m, feita por um modelo de aprendizado de máquina com imagens Sentinel-2. A Profill foi a referência e a fonte dos rótulos; não há validação independente contra dados de campo, e a transferência para outras áreas não foi testada.",
    nao_e: "Não é impermeabilidade medida, coeficiente de escoamento, vazão nem ocorrência de alagamento, e não entra no cálculo das dimensões A, B, C e D."
  };
  G.textos = function () { return TEXTOS; };
  function el(id) { return document.getElementById(id); }
  function esc(s) { return Lg.esc(s); }
  function pct(x) { return String(Math.round(x * 100)).replace(".", ",") + "%"; }
  G.base = function () { return window.FM_DADOS.base("geoai"); };
  G.urlImagem = function () { return G.base() + (G.meta ? G.meta.arquivo : "fracao_construida.webp"); };
  G.carregar = function () {
    if (G._meta) return G._meta;
    G._meta = window.FM_DADOS.lerMeta("geoai").then(function (m) { G.meta = m; G.erro = null; return m; }).catch(function (e) { G.erro = e.message; G._meta = null; throw e; });
    return G._meta;
  };
  G.aoMudar = function (f) { G.ouvintes.push(f); };
  function avisar() { G.ouvintes.forEach(function (f) { f(); }); }

  /* Legenda: cinco classes de fração construída, claro a escuro, e o que a camada NÃO é. */
  G.legenda = function () {
    var h = "<li class='f3-tit'><b>E. Fração construída estimada (GeoAI)</b> <span class='small'>fora do cálculo</span></li>";
    if (G.meta) {
      G.meta.classes.forEach(function (c) {
        h += "<li><span class='sw' style='background:" + esc(c.cor) + "'></span><span>" + esc(pct(c.de) + " a " + pct(c.ate)) + " da célula construída</span></li>";
      });
      h += "<li class='f3-nota small'>Células sem cor: fração zero ou fora do município. Cada quadrado é uma célula de 30 m.</li>";
    } else if (G.erro) {
      h += "<li class='f3-nota small' role='status'>Os dados desta camada não estão disponíveis (" + esc(G.erro) + ").</li>";
    } else {
      h += "<li class='f3-nota small'>Carregando a camada…</li>";
    }
    return h + "<li class='f3-nota small'>" + esc(TEXTOS.nao_e) + "</li>";
  };

  /* Painel da camada: aviso de experimental, controle de opacidade e a origem dos dados. */
  G.montarPainel = function () {
    var box = el("geoai-opcoes"); if (!box) return;
    var m = G.meta;
    box.innerHTML = "<p class='sr-only' id='h-geoai'>E. Fração construída estimada (GeoAI, experimental)</p>" +
      "<div class='ctl-linha'><label for='geoai-opac'>Opacidade</label><input type='range' id='geoai-opac' min='20' max='100' step='5' value='" + Math.round(G.opacidade * 100) + "' aria-describedby='geoai-opac-v'><output id='geoai-opac-v' class='small'>" + Math.round(G.opacidade * 100) + "%</output></div>" +
      "<details class='mais'><summary>Sobre esta camada</summary>" + (window.Mapa && window.Mapa.notaDim ? window.Mapa.notaDim("E") : "") + "<p class='small geoai-aviso' role='note'><b>Experimental.</b> " + esc(TEXTOS.aviso) + "</p>" +
      (m ? "<p class='small'>Origem: " + esc(m.fonte_da_imagem || "") + "; período " + esc(m.periodo || "") + "; referência: " + esc(m.referencia || "") + ". Erro médio absoluto da fração construída: " + String(m.resultados.mae_blocos_3km).replace(".", ",") + " em blocos de 3 km e " + String(m.resultados.mae_quadrante_externo).replace(".", ",") + " no quadrante externo; critério de bairros (80% com erro de área de até 10%) não atingido: " + pct(m.resultados.bairros_com_erro_de_area_ate_10pct) + ".</p>" : "") +
      "</details>" +
      (G.erro ? "<p class='small f3-sem' role='status'>Os dados da camada não estão disponíveis (" + esc(G.erro) + "). <button type='button' class='link' id='geoai-tentar'>Tentar de novo</button></p>" : "");
    var r = el("geoai-opac");
    r.addEventListener("input", function () { G.opacidade = Number(r.value) / 100; el("geoai-opac-v").textContent = r.value + "%"; avisar(); });
    var t = el("geoai-tentar"); if (t) t.addEventListener("click", function () { G.erro = null; G._meta = null; avisar(); });
  };
})();
