(function () {
  "use strict";
  var partes = location.hash.replace(/^#/, "").split("/");
  if (partes.length < 2 || partes[1] === "" || partes[1] === "mapa") {      // sem aba no endereço, o painel abre no mapa
    document.documentElement.classList.add("modo-mapa-inicial");
  }
})();
