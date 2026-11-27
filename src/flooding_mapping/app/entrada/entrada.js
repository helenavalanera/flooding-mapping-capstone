/* Porta de entrada da versão estática (Cloudflare Pages): a raiz mostra a landing page do estudo.
   Os links antigos que apontam para a raiz com "?painel=1" ou com "#território/aba" continuam levando ao painel (painel.html), com a consulta e o trecho preservados. */
(function () {
  "use strict";
  var abrePainel = /(^|[?&])painel=/.test(location.search) || location.hash.length > 1;
  location.replace(abrePainel ? "painel.html" + location.search + location.hash : "inicio/");
})();
