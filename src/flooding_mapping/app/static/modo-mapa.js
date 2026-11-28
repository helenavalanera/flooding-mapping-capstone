(function () {
  "use strict";
  var partes = location.hash.replace(/^#/, "").split("/");
  if (partes.length > 1 && partes[1] === "mapa") {
    document.documentElement.classList.add("modo-mapa-inicial");
  }
})();
