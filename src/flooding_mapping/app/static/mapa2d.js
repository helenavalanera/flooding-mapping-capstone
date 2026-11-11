/* 2D map engine (Leaflet) for browsers without WebGL. It offers the same layers and selection as the 3D engine, in both
   territories: occurrences, confirmed closures, attention stretches, routes and the municipal and road layers. Only the relief and the
   tilted view need WebGL; the controller (mapa.js) says so in the panel. */
(function () {
  "use strict";
  var L_ = window.L;
  var OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  var COR_MUN = { cobertura: { disponivel: "#2e8b57", parcial: "#e0a030", insuficiente: "#8d99a0" }, risco: { alto: "#b3202a", atencao: "#f0a830", baixo: "#dfe7ec" } };
  var COR_CLASSE_POA = { alto: "#b3202a", atencao: "#d98c00" };
  var COR_ROTA = { habitual: "#333f48", menor_exposicao: "#1b7f5c", alternativa: "#1f6fb2" };
  var VAZIO = "#c9d1d6";

  window.MotorLeaflet = function (M) {
    var m = { suporta: { tres_d: false, relevo: false } };
    var map, cb = null, G = {}, modo = { mun: "cobertura", rod: "vdm" }, sel = { municipio: "", rodovia: "" }, criticos = [];
    var PANES = ["mun", "s2id", "rod", "crit", "risco", "rotas", "rotasRisco", "occ", "int", "bloq"];
    var GRUPOS = { municipios: ["mun"], rodovias: ["rod"], bloqueios: ["bloq"], s2id: ["s2id"], trechos_criticos: ["crit"], risco_trecho: ["risco"], ocorrencias: ["occ"], interdicoes: ["int"], rotas: ["rotas", "rotasRisco"], relevo: [] };
    var DADOS = { "poa-risco": "risco", "poa-occ": "occ", "poa-int": "int", "rotas": "rotas", "rotas-risco": "rotasRisco" };
    var lat = function (c) { return [c[1], c[0]]; };
    function vazio() { return { type: "FeatureCollection", features: [] }; }

    function estiloMun(f) {
      var p = f.properties, modoRisco = modo.mun === "risco", chave = modoRisco ? p.risco : p.classe, cor = (COR_MUN[modo.mun] || COR_MUN.cobertura)[chave] || VAZIO;
      var s = p.ibge === sel.municipio;
      return { fillColor: cor, fillOpacity: 0.5, color: s ? "#000" : "#52626d", weight: s ? 3 : 0.6 };
    }
    function estiloRod(f) {
      var p = f.properties, s = p.nome === sel.rodovia, cor;
      if (modo.rod === "indice") { var i = p.indice_fisico; cor = i == null ? "#b9bfc3" : (i >= 85 ? "#b3202a" : (i >= 50 ? "#f0c040" : "#d9ead3")); } else cor = window.Logic.vdmColor(p.vdm);
      return { color: s ? "#000" : cor, weight: s ? 6 : 2.4, opacity: 0.95, lineCap: "round" };
    }
    function estiloRisco(f) {
      var p = f.properties, previsto = p.natureza === "previsto";
      return { color: COR_CLASSE_POA[p.classe] || "#7c8b95", weight: 4, opacity: 0.95, dashArray: previsto ? "6 5" : null, lineCap: previsto ? "butt" : "round" };
    }
    function ponto(pane, cor, borda, raio) { return function (f, ll) { return L_.circleMarker(ll, { pane: pane, radius: raio, color: borda(f), weight: 2.5, fillColor: cor(f), fillOpacity: 1 }); }; }

    m.criar = function (vista) {
      map = L_.map("mapa-gl", { zoomControl: true, preferCanvas: false, worldCopyJump: false }).setView([vista.centro[1], vista.centro[0]], Math.round(vista.zoom));
      L_.tileLayer(OSM, { maxZoom: 19, attribution: "&copy; colaboradores do OpenStreetMap" }).addTo(map);
      L_.control.scale({ metric: true, imperial: false }).addTo(map);
      PANES.forEach(function (p, i) { map.createPane(p).style.zIndex = 400 + i * 5; });
      PANES.forEach(function (p) { G[p] = L_.geoJSON(null, { pane: p }); });
      return Promise.resolve();
    };

    m.adicionar = function (d, o) {
      criticos = o.criticos || [];
      G.mun = L_.geoJSON(d.municipios, { pane: "mun", style: estiloMun, onEachFeature: function (f, layer) {
        layer.bindTooltip(window.Logic.esc(f.properties.nome), { sticky: true });
        layer.on("click", function () { if (cb) cb({ tipo: "municipio", props: f.properties }); });
      } });
      G.s2id = L_.geoJSON(d.municipios, { pane: "s2id", filter: function (f) { return f.properties.s2id90; }, style: { fill: false, color: "#5b3a8c", weight: 2.4 }, interactive: false });
      G.rod = L_.geoJSON(d.rodovias, { pane: "rod", style: estiloRod, bubblingMouseEvents: false, onEachFeature: function (f, layer) {
        var p = f.properties;
        layer.bindTooltip(window.Logic.esc(p.nome) + " · " + (p.vdm == null ? "VDM sem dado" : "VDM " + Math.round(p.vdm).toLocaleString("pt-BR") + " veíc./dia"), { sticky: true });
        layer.on("click", function () { if (cb) cb({ tipo: "rodovia", props: p }); });
      } });
      G.crit = L_.geoJSON(d.rodovias, { pane: "crit", filter: function (f) { return criticos.indexOf(f.properties.codigo_sre) >= 0; }, style: { color: "#7b2d8e", weight: 5, opacity: 0.95, dashArray: "8 6" }, interactive: false });
      var blq = (d.bloqueios && d.bloqueios.bloqueios || []).filter(function (b) { return b.lat != null; }).map(function (b) {
        return { type: "Feature", geometry: { type: "Point", coordinates: [b.lng, b.lat] }, properties: { id: b.id, tipo: b.tipo, rodovia: b.rodovia, municipio: b.municipio } };
      });
      G.bloq = L_.geoJSON({ type: "FeatureCollection", features: blq }, { pane: "bloq", pointToLayer: ponto("bloq", function (f) { return f.properties.tipo === "total" ? "#b3202a" : "#e07a1f"; }, function () { return "#fff"; }, 7),
        onEachFeature: function (f, layer) { layer.bindTooltip(window.Logic.esc(f.properties.rodovia || "Bloqueio") + " · " + window.Logic.esc(f.properties.municipio || ""), { sticky: true }); } });
      G.risco = L_.geoJSON(null, { pane: "risco", style: estiloRisco, bubblingMouseEvents: false, onEachFeature: function (f, layer) {
        layer.on("click", function () { if (cb) cb({ tipo: "trecho", props: f.properties }); });
      } });
      G.occ = L_.geoJSON(null, { pane: "occ", pointToLayer: ponto("occ", function (f) { return f.properties.situacao === "confirmada" ? "#1b2630" : "#ffffff"; }, function (f) { return f.properties.situacao === "confirmada" ? "#ffffff" : "#1f6fb2"; }, 7),
        onEachFeature: function (f, layer) { layer.bindTooltip((f.properties.situacao === "confirmada" ? "Confirmada" : "Reportada, sem verificação") + " · " + window.Logic.esc(f.properties.tipo || ""), { sticky: true }); } });
      G.int = L_.geoJSON(null, { pane: "int", pointToLayer: ponto("int", function () { return "#000"; }, function () { return "#fff"; }, 10),
        onEachFeature: function (f, layer) { layer.bindTooltip("Interdição confirmada: o trecho não é usado nas rotas", { sticky: true }); } });
      G.rotas = L_.geoJSON(null, { pane: "rotas", interactive: false, style: function (f) { return { color: COR_ROTA[f.properties.rota] || "#333", weight: f.properties.sel ? 6 : 3, opacity: f.properties.sel ? 1 : 0.7, lineCap: "round" }; } });
      G.rotasRisco = L_.geoJSON(null, { pane: "rotasRisco", interactive: false, style: { color: "#b3202a", weight: 8, opacity: 0.6, dashArray: "2 6" } });
    };

    m.visibilidade = function (nome, ligado) {
      (GRUPOS[nome] || []).forEach(function (g) {
        if (!G[g]) return;
        if (ligado && !map.hasLayer(G[g])) map.addLayer(G[g]); else if (!ligado && map.hasLayer(G[g])) map.removeLayer(G[g]);
      });
    };
    m.cores = function (cm, cr) { modo.mun = cm; modo.rod = cr; if (G.mun) G.mun.setStyle(estiloMun); if (G.rod) G.rod.setStyle(estiloRod); };
    m.municipios = function () { if (G.mun) G.mun.setStyle(estiloMun); };
    m.dados = function (nome, geo) {
      var g = G[DADOS[nome]]; if (!g) return;
      g.clearLayers(); g.addData(geo || vazio());
    };
    m.selecionar = function (s) {
      sel.municipio = s.municipio || ""; sel.rodovia = s.rodovia || "";
      if (G.mun) G.mun.setStyle(estiloMun); if (G.rod) G.rod.setStyle(estiloRod);
      if (sel.rodovia && G.rod && map.hasLayer(G.rod)) G.rod.eachLayer(function (l) { if (l.feature.properties.nome === sel.rodovia) l.bringToFront(); });
    };
    m.tres_d = function () { /* no relief or tilt without WebGL */ };
    m.voar = function (v, tres_d, sem_animacao) {
      var c = [v.centro[1], v.centro[0]], z = Math.round(v.zoom);
      if (sem_animacao) map.setView(c, z, { animate: false }); else map.flyTo(c, z, { duration: 1.6 });
    };
    m.ajustar = function (caixa, o) {
      var b = L_.latLngBounds([caixa[0][1], caixa[0][0]], [caixa[1][1], caixa[1][0]]);
      map.fitBounds(b, { padding: [o.padding || 40, o.padding || 40], animate: !o.reduzido, maxZoom: 17 });
    };
    m.aoClicar = function (f) { cb = f; };
    m.redimensionar = function () { if (map) map.invalidateSize(); };
    m.destruir = function () { if (map) map.remove(); map = null; G = {}; cb = null; var c = document.getElementById("mapa-gl"); if (c) { c.innerHTML = ""; c.className = ""; } };
    m.nativo = function () { return map; };
    return m;
  };
})();
