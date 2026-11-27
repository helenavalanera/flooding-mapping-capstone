/* Instalação e uso sem conexão da aplicação de análise: registra o service worker (sw.js), oferece "Instalar" quando o navegador permite, avisa a falta de
   conexão dizendo o que continua e o que deixa de funcionar, avisa uma nova versão e mostra a versão da interface. Nada aqui afirma funcionar offline além do que
   a política de cache de sw.js guarda. */
(function () {
  "use strict";
  var el = function (id) { return document.getElementById(id); };
  var oferta = null, controlava = !!(navigator.serviceWorker && navigator.serviceWorker.controller);
  var TEXTO_OFFLINE = "Sem conexão. Continuam disponíveis a interface, os resultados e o simulador (última cópia salva) e as áreas do mapa-base já vistas. Dependem de conexão: as camadas de escoamento e de drenagem, a previsão, os bloqueios, as ocorrências e as rotas.";
  function aviso(id, texto) { var b = el(id); if (!b) return; b.textContent = texto || ""; b.hidden = !texto; }
  function conexao() { aviso("aviso-conexao", navigator.onLine === false ? TEXTO_OFFLINE : ""); }
  window.addEventListener("online", conexao); window.addEventListener("offline", conexao); conexao();

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault(); oferta = e; var b = el("instalar"); if (b) b.hidden = false;
  });
  window.addEventListener("appinstalled", function () { oferta = null; var b = el("instalar"); if (b) b.hidden = true; });
  var botao = el("instalar");
  if (botao) botao.addEventListener("click", function () { if (!oferta) return; var o = oferta; oferta = null; botao.hidden = true; o.prompt(); });

  function versao() {
    var alvo = el("versao-app"); if (!alvo || !window.caches) return;
    caches.keys().then(function (ks) { var v = ks.filter(function (k) { return k.indexOf("fm-app-") === 0; })[0]; if (v) alvo.textContent = "Interface " + v; });
  }
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    navigator.serviceWorker.register("sw.js").then(versao).catch(function () {});
    navigator.serviceWorker.addEventListener("controllerchange", function () {
      if (controlava) aviso("aviso-versao", "Há uma nova versão da interface. Recarregue a página para usá-la.");
      controlava = true; versao();
    });
  }
})();
