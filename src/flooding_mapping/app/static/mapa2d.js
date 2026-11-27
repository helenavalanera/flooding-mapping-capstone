/* Motor 2D (Leaflet) para navegadores sem WebGL. Mostra o mapa-base de Porto Alegre, com escala e navegação. As camadas de análise (escoamento
   potencial da Fase 3 e drenagem cadastrada) usam tiles vetoriais e exigem WebGL: neste motor elas ficam indisponíveis, e o controlador
   (mapa.js) diz isso no painel. O relevo e a vista inclinada também exigem WebGL. O motor com as camadas da frente estadual arquivada
   está em app/arquivo/painel-estadual/. */
(function () {
  "use strict";
  window.MotorLeaflet = function () {
    var m = { suporta: { tres_d: false, relevo: false } };
    var map;
    m.criar = function (vista) {
      map = window.L.map("mapa-gl", { zoomControl: true, preferCanvas: false, worldCopyJump: false }).setView([vista.centro[1], vista.centro[0]], Math.round(vista.zoom));
      window.MapaBase.camadaLeaflet().addTo(map);
      window.L.control.scale({ metric: true, imperial: false }).addTo(map);
      return Promise.resolve();
    };
    m.adicionar = function () {};
    m.visibilidade = function () {};
    m.dren_grupos = function () {};
    m.f3_pintar = function () {};
    m.selecionar = function () {};
    m.tres_d = function () { /* sem relevo nem inclinação sem WebGL */ };
    m.voar = function (v, tres_d, sem_animacao) {
      var c = [v.centro[1], v.centro[0]], z = Math.round(v.zoom);
      if (sem_animacao) map.setView(c, z, { animate: false }); else map.flyTo(c, z, { duration: 1.6 });
    };
    m.ajustar = function (caixa, o) {
      var b = window.L.latLngBounds([caixa[0][1], caixa[0][0]], [caixa[1][1], caixa[1][0]]);
      map.fitBounds(b, { padding: [o.padding || 40, o.padding || 40], animate: !o.reduzido, maxZoom: 17 });
    };
    m.aoClicar = function () {};
    m.redimensionar = function () { if (map) map.invalidateSize(); };
    m.destruir = function () { if (map) map.remove(); map = null; var c = document.getElementById("mapa-gl"); if (c) { c.innerHTML = ""; c.className = ""; } };
    m.nativo = function () { return map; };
    return m;
  };
})();
