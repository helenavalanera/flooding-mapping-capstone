/* Current territory and what it offers. Every view asks this module instead of testing "if Porto Alegre" itself.
   Capabilities come from territorios.json (built from config/territorios.yaml); when the analysis server is up, the
   live coverage of Porto Alegre replaces the one computed at build time. */
(function () {
  "use strict";
  var Lg = window.Logic;
  var T = { dados: null, atual: "rs", online: false, ouvintes: [], _rs: null };
  var IDS = ["rs", "poa"];

  function getJson(url) {
    return fetch(url, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error(url + ": HTTP " + r.status); return r.json(); });
  }
  T.ids = IDS;
  T.carregar = function () {
    return getJson("data/territorios.json").then(function (d) { T.dados = d; return d; });
  };
  /* The server knows Porto Alegre's coverage now (from the street table it loaded). */
  T.atualizarComServidor = function () {
    return getJson("api/territorios").then(function (d) { T.dados = d; T.online = true; return d; }).catch(function () { return T.dados; });
  };
  T.territorio = function (id) { return T.dados && T.dados.territorios[id || T.atual]; };
  T.cap = function (nome, id) { var t = T.territorio(id); return t && t.capacidades[nome]; };
  T.status = function (nome, id) { return Lg.capStatus(T.cap(nome, id), T.online); };
  T.camadas = function (id) { var t = T.territorio(id); return t ? Lg.layersOf(t, T.online) : {}; };
  T.definir = function (id) {
    if (IDS.indexOf(id) < 0 || id === T.atual) return;
    T.atual = id; T.ouvintes.forEach(function (f) { f(id); });
  };
  T.aoMudar = function (f) { T.ouvintes.push(f); };
  /* The state datasets, fetched once and shared by the map and the panels. A missing optional file is null, never zero. */
  T.rs = function () {
    if (!T._rs) {
      var opt = function (u) { return getJson(u).catch(function () { return null; }); };
      T._rs = Promise.all([getJson("data/municipios.geojson"), getJson("data/rodovias.geojson"), getJson("data/cobertura_rs.json"), opt("previsao_72h.json"),
                           opt("bloqueios.json"), opt("data/ocorrencias.json"), opt("data/impacto_rs.json")]).then(function (r) {
        return { municipios: r[0], rodovias: r[1], cobertura: r[2], previsao: r[3], bloqueios: r[4], ocorrencias: r[5], impacto: r[6],
                 prevPorIbge: r[3] ? Lg.indexByIbge(r[3]) : {} };
      });
    }
    return T._rs;
  };
  window.Territorio = T;
})();
