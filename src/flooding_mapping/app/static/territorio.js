/* Território ativo: Porto Alegre, o único da versão atual. O que ele oferece vem de data/territorio_poa.json (capacidades e vista do mapa); cada
   tela pergunta a este módulo em vez de testar o nome do território. A interface de duas escalas (Rio Grande do Sul e Porto Alegre) está arquivada
   em app/arquivo/painel-estadual/ e não é carregada. */
(function () {
  "use strict";
  var Lg = window.Logic;
  var T = { dados: null, atual: "poa", online: false };
  T.ids = ["poa"];
  T.carregar = function () {
    return fetch("data/territorio_poa.json", { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("data/territorio_poa.json: HTTP " + r.status);
      return r.json();
    }).then(function (d) { T.dados = d; return d; });
  };
  T.territorio = function () { return T.dados && T.dados.territorios[T.atual]; };
  T.camadas = function () { var t = T.territorio(); return t ? Lg.layersOf(t, T.online) : {}; };
  window.Territorio = T;
})();
