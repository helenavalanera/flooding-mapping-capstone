/* Map of both territories (MapLibre GL JS): 3D with terrain or flat 2D, one map, layers driven by the capabilities of the
   current territory. Terrain is public elevation used only to look at the relief; it feeds no risk calculation, and the vertical
   exaggeration is chosen by the user and stated. Nothing draws a water depth or an extent: only the classes that the data supports. */
(function () {
  "use strict";
  var Lg = window.Logic, T = window.Territorio, gl = window.maplibregl;
  var DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
  var OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  var M = { map: null, pronto: false, tres_d: true, exagero: 1.5, corMun: "cobertura", corRod: "vdm", dia: 0, marcadas: {}, hora: 0, selecionado: null, rotas: null, dados: null };
  window.Mapa = M;

  var CAMADAS = {
    municipios: { rotulo: "Municípios", kind: null, ids: ["mun-fill", "mun-line"], inicial: true },
    rodovias: { rotulo: "Rodovias do DAER", kind: "observado", ids: ["rod"], inicial: true },
    bloqueios: { rotulo: "Bloqueios ativos (CPRv BM)", kind: "observado", ids: ["bloq"], inicial: true },
    s2id: { rotulo: "Municípios com registro S2iD nos últimos 90 dias", kind: "observado", ids: ["mun-s2id"], inicial: false },
    trechos_criticos: { rotulo: "Trechos críticos na simulação", kind: "simulado", ids: ["rod-crit"], inicial: false },
    relevo: { rotulo: "Relevo sombreado", kind: null, ids: ["sombra"], inicial: true },
    risco_trecho: { rotulo: "Risco estimado por trecho", kind: "previsto", ids: ["poa-risco-obs", "poa-risco-prev"], inicial: true },
    ocorrencias: { rotulo: "Ocorrências reportadas e confirmadas", kind: "observado", ids: ["poa-occ"], inicial: true },
    interdicoes: { rotulo: "Interdições confirmadas", kind: "confirmado", ids: ["poa-int"], inicial: true },
    rotas: { rotulo: "Rotas da última análise", kind: "previsto", ids: ["rotas-casing", "rotas", "rotas-risco"], inicial: true }
  };
  var COR_MUN = {
    cobertura: ["match", ["get", "classe"], "disponivel", "#2e8b57", "parcial", "#e0a030", "insuficiente", "#8d99a0", "#c9d1d6"],
    risco: ["match", ["get", "risco"], "alto", "#b3202a", "atencao", "#f0a830", "baixo", "#dfe7ec", "#c9d1d6"]
  };
  var COR_ROD = {
    vdm: ["step", ["to-number", ["get", "vdm"], -1], "#b9bfc3", 0, "#c6dbef", 2000, "#6baed6", 8000, "#2171b5", 20000, "#08306b"],
    indice: ["step", ["to-number", ["get", "indice_fisico"], -1], "#b9bfc3", 0, "#d9ead3", 50, "#f0c040", 85, "#b3202a"]
  };
  var CLASSE_POA = ["match", ["get", "classe"], "alto", "#b3202a", "atencao", "#d98c00", "#7c8b95"];
  var ROTA_COR = ["match", ["get", "rota"], "habitual", "#333f48", "menor_exposicao", "#1b7f5c", "alternativa", "#1f6fb2", "#333"];

  function el(id) { return document.getElementById(id); }
  function vazio() { return { type: "FeatureCollection", features: [] }; }
  function getJson(u) { return fetch(u, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }); }
  function reduzido() { return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  M.webglOk = function () {
    try { var c = document.createElement("canvas"); return !!(window.maplibregl && (c.getContext("webgl2") || c.getContext("webgl"))); } catch (e) { return false; }
  };

  /* ---------------------------------------------------------------- criação */
  M.iniciar = function () {
    if (M.map) { return Promise.resolve(M.map); }
    var vista = T.territorio().vista;
    M.map = new gl.Map({
      container: "mapa-gl", center: vista.centro, zoom: vista.zoom, pitch: vista.inclinacao, bearing: vista.rumo, maxPitch: 75, attributionControl: { compact: true },
      style: { version: 8, sources: {
        osm: { type: "raster", tiles: [OSM], tileSize: 256, maxzoom: 19, attribution: "&copy; colaboradores do OpenStreetMap" },
        dem: { type: "raster-dem", tiles: [DEM], encoding: "terrarium", tileSize: 256, maxzoom: 14, attribution: "Elevação: AWS Terrain Tiles" } },
        layers: [{ id: "base", type: "raster", source: "osm" },
                 { id: "sombra", type: "hillshade", source: "dem", paint: { "hillshade-exaggeration": 0.4, "hillshade-shadow-color": "#3b4750" } }] }
    });
    M.map.addControl(new gl.NavigationControl({ visualizePitch: true }), "top-left");
    M.map.addControl(new gl.ScaleControl({ unit: "metric" }), "bottom-left");
    M.map.on("error", function (e) {
      var msg = (e && e.error && e.error.message) || "";
      if (/Failed to fetch|NetworkError|Load failed|ERR_/.test(msg)) el("nota-relevo").textContent = "Parte dos mapas-base não carregou (sem conexão?). Os dados do painel continuam valendo.";
    });
    return new Promise(function (resolve) { M.map.on("load", resolve); }).then(function () { return T.rs(); }).then(function (d) {
      M.dados = d; preparar(d); adicionar(d); ligarEventos();
      definir3D(M.tres_d, false); renderControles(); aplicarCamadas(); legenda();
      M.pronto = true;
      return M.map;
    });
  };

  function preparar(d) {
    var cob = d.cobertura.municipios;
    d.municipios.features.forEach(function (f) {
      var c = cob[f.properties.ibge] || {};
      f.properties.classe = c.classe || "insuficiente";
      f.properties.s2id90 = (c.s2id_hidrologicos_90_dias || 0) > 0;
    });
    pintarRisco();
  }
  /* The municipal estimate for the chosen day; a municipality without one stays without a class (grey), never "low". */
  function pintarRisco() {
    var d = M.dados; if (!d) return;
    d.municipios.features.forEach(function (f) {
      var m = d.prevPorIbge[f.properties.ibge], dia = m && (m.dias || []).filter(function (x) { return x.horizonte_dias === M.dia; })[0];
      f.properties.risco = dia ? dia.classe : null;
    });
    if (M.map && M.map.getSource("municipios")) M.map.getSource("municipios").setData(d.municipios);
  }

  function adicionar(d) {
    var map = M.map, criticos = [];
    var imp = d.impacto || {};
    ["ranking_pontes_populacao_isolada", "ranking_veiculos_km_dia_com_vdm"].forEach(function (k) { (imp[k] || []).forEach(function (r) { criticos.push(r.codigo_sre); }); });
    map.addSource("municipios", { type: "geojson", data: d.municipios, promoteId: "ibge" });
    map.addLayer({ id: "mun-fill", type: "fill", source: "municipios", paint: { "fill-color": COR_MUN.cobertura, "fill-opacity": 0.5 } });
    map.addLayer({ id: "mun-line", type: "line", source: "municipios", paint: { "line-color": "#52626d", "line-width": 0.6 } });
    map.addLayer({ id: "mun-s2id", type: "line", source: "municipios", filter: ["==", ["get", "s2id90"], true], paint: { "line-color": "#5b3a8c", "line-width": 2.4 } });
    map.addLayer({ id: "mun-sel", type: "line", source: "municipios", filter: ["==", ["get", "ibge"], ""], paint: { "line-color": "#000", "line-width": 3 } });
    map.addSource("rodovias", { type: "geojson", data: d.rodovias });
    map.addLayer({ id: "rod", type: "line", source: "rodovias", layout: { "line-cap": "round" }, paint: { "line-color": COR_ROD.vdm, "line-width": ["interpolate", ["linear"], ["zoom"], 5, 1.2, 12, 4] } });
    map.addLayer({ id: "rod-crit", type: "line", source: "rodovias", filter: ["in", ["get", "codigo_sre"], ["literal", criticos]], paint: { "line-color": "#7b2d8e", "line-width": 5, "line-dasharray": [2, 1.5] } });
    map.addLayer({ id: "rod-sel", type: "line", source: "rodovias", filter: ["==", ["get", "nome"], ""], paint: { "line-color": "#000", "line-width": 7, "line-opacity": 0.5 } });
    var blq = d.bloqueios ? { type: "FeatureCollection", features: (d.bloqueios.bloqueios || []).filter(function (b) { return b.lat != null; }).map(function (b) {
      return { type: "Feature", geometry: { type: "Point", coordinates: [b.lng, b.lat] }, properties: { id: b.id, tipo: b.tipo, rodovia: b.rodovia, municipio: b.municipio } }; }) } : vazio();
    map.addSource("bloqueios", { type: "geojson", data: blq });
    map.addLayer({ id: "bloq", type: "circle", source: "bloqueios", paint: { "circle-radius": 7, "circle-color": ["match", ["get", "tipo"], "total", "#b3202a", "#e07a1f"], "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
    // Porto Alegre: filled from the API, empty until then
    ["poa-risco", "poa-occ", "poa-int", "rotas", "rotas-risco"].forEach(function (s) { map.addSource(s, { type: "geojson", data: vazio() }); });
    map.addLayer({ id: "poa-risco-obs", type: "line", source: "poa-risco", filter: ["==", ["get", "natureza"], "observado"], layout: { "line-cap": "round" }, paint: { "line-color": CLASSE_POA, "line-width": ["interpolate", ["linear"], ["zoom"], 10, 2, 16, 6] } });
    map.addLayer({ id: "poa-risco-prev", type: "line", source: "poa-risco", filter: ["==", ["get", "natureza"], "previsto"], layout: { "line-cap": "butt" }, paint: { "line-color": CLASSE_POA, "line-dasharray": [1.6, 1.1], "line-width": ["interpolate", ["linear"], ["zoom"], 10, 2, 16, 6] } });
    map.addLayer({ id: "poa-occ", type: "circle", source: "poa-occ", paint: { "circle-radius": 7, "circle-color": ["match", ["get", "situacao"], "confirmada", "#1b2630", "#ffffff"], "circle-stroke-color": ["match", ["get", "situacao"], "confirmada", "#ffffff", "#1f6fb2"], "circle-stroke-width": 2.5 } });
    map.addLayer({ id: "poa-int", type: "circle", source: "poa-int", paint: { "circle-radius": 10, "circle-color": "#000", "circle-stroke-color": "#fff", "circle-stroke-width": 3 } });
    map.addLayer({ id: "rotas-casing", type: "line", source: "rotas", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#fff", "line-width": ["case", ["get", "sel"], 11, 7] } });
    map.addLayer({ id: "rotas", type: "line", source: "rotas", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": ROTA_COR, "line-width": ["case", ["get", "sel"], 6, 3], "line-opacity": ["case", ["get", "sel"], 1, 0.7] } });
    map.addLayer({ id: "rotas-risco", type: "line", source: "rotas-risco", layout: { "line-cap": "butt" }, paint: { "line-color": "#b3202a", "line-width": 6, "line-dasharray": [1.4, 1] } });
  }

  /* ---------------------------------------------------------------- vista 3D / 2D e território */
  function definir3D(ligado, animar) {
    M.tres_d = ligado;
    el("vista-3d").setAttribute("aria-pressed", String(ligado)); el("vista-2d").setAttribute("aria-pressed", String(!ligado));
    el("exagero").disabled = !ligado;
    M.map.setTerrain(ligado ? { source: "dem", exaggeration: M.exagero } : null);
    var v = T.territorio().vista;
    M.map.easeTo({ pitch: ligado ? v.inclinacao : 0, bearing: ligado ? v.rumo : 0, duration: animar === false || reduzido() ? 0 : 900 });
    el("nota-relevo").textContent = ligado ? "Relevo com exagero vertical de " + String(M.exagero).replace(".", ",") + "× apenas para visualização; não entra em nenhum cálculo de risco. O modelo de elevação pode ter artefatos sobre água e vegetação." : "Vista plana (2D). O relevo sombreado continua disponível como camada.";
  }
  M.irParaTerritorio = function (id) {
    if (!M.pronto) return;
    var v = T.territorio(id).vista;
    M.map.flyTo({ center: v.centro, zoom: v.zoom, pitch: M.tres_d ? v.inclinacao : 0, bearing: M.tres_d ? v.rumo : 0, duration: reduzido() ? 0 : 2200, essential: true });
    limparSelecao(); renderControles(); aplicarCamadas(); legenda();
    if (id === "poa") { carregarRisco(); carregarOcorrencias(); }
  };
  M.redimensionar = function () { if (M.map) M.map.resize(); };

  /* ---------------------------------------------------------------- camadas e controles (dirigidos pelas capacidades) */
  function habilitada(nome) { var st = T.camadas()[nome]; return st && st.ativa; }
  function visivel(nome) { return habilitada(nome) && (M.marcadas[nome] !== undefined ? M.marcadas[nome] : CAMADAS[nome].inicial); }
  function aplicarCamadas() {
    if (!M.pronto) return;
    var ids = {};
    Object.keys(CAMADAS).forEach(function (nome) { CAMADAS[nome].ids.forEach(function (id) { ids[id] = (ids[id] || false) || visivel(nome); }); });
    Object.keys(ids).forEach(function (id) { M.map.setLayoutProperty(id, "visibility", ids[id] ? "visible" : "none"); });
    // the colouring modes only apply while their layer is on
    M.map.setPaintProperty("mun-fill", "fill-color", COR_MUN[M.corMun] || COR_MUN.cobertura);
    M.map.setPaintProperty("rod", "line-color", COR_ROD[M.corRod] || COR_ROD.vdm);
    el("poa-opcoes").hidden = !(T.atual === "poa" && habilitada("risco_trecho"));
  }
  function renderControles() {
    var camadas = T.camadas(), box = el("camadas"), cores = el("cores");
    var html = Object.keys(CAMADAS).filter(function (n) { return camadas[n]; }).map(function (n) {
      var st = camadas[n], c = CAMADAS[n], marcada = visivel(n);
      return "<label class='camada" + (st.ativa ? "" : " inativa") + "'><input type='checkbox' data-camada='" + n + "'" + (marcada ? " checked" : "") + (st.ativa ? "" : " disabled") + "> " + Lg.esc(c.rotulo) +
        (c.kind ? " " + Lg.kindBadge(c.kind) : "") + (st.ativa ? "" : "<span class='small'>" + Lg.esc(st.rotulo) + ": " + Lg.esc(st.nota) + "</span>") + "</label>";
    }).join("");
    box.innerHTML = html || "<p class='muted'>Nenhuma camada descrita para este território.</p>";
    Array.prototype.forEach.call(box.querySelectorAll("input[data-camada]"), function (i) { i.addEventListener("change", function () { M.marcadas[i.dataset.camada] = i.checked; aplicarCamadas(); legenda(); }); });
    if (T.atual === "rs") {
      var optsMun = [["cobertura", "Cobertura de dados"]], optsRod = [];
      if (habilitada("municipios") && habilitada("risco_municipal") && M.dados.previsao) optsMun.push(["risco", "Estimativa municipal 72 h"]);
      if (habilitada("rodovias")) optsRod.push(["vdm", "Tráfego (VDM)"]);
      if (habilitada("indice_fisico")) optsRod.push(["indice", "Índice físico (relativo)"]);
      var sel = function (id, rot, opts, atual) { return "<label for='" + id + "'>" + rot + "</label><select id='" + id + "'>" + opts.map(function (o) { return "<option value='" + o[0] + "'" + (o[0] === atual ? " selected" : "") + ">" + o[1] + "</option>"; }).join("") + "</select>"; };
      cores.innerHTML = "<h2 id='h-cores'>Colorir por</h2>" + sel("cor-mun", "Municípios", optsMun, M.corMun) +
        (M.corMun === "risco" ? "<label for='cor-dia'>Dia da estimativa</label><select id='cor-dia'>" + [0, 1, 2].map(function (h) { return "<option value='" + h + "'" + (h === M.dia ? " selected" : "") + ">" + ["Hoje", "Amanhã", "Depois de amanhã"][h] + "</option>"; }).join("") + "</select>" : "") +
        (optsRod.length ? sel("cor-rod", "Rodovias", optsRod, M.corRod) : "");
      el("cor-mun").addEventListener("change", function (e) { M.corMun = e.target.value; renderControles(); aplicarCamadas(); legenda(); });
      if (el("cor-dia")) el("cor-dia").addEventListener("change", function (e) { M.dia = Number(e.target.value); pintarRisco(); });
      if (el("cor-rod")) el("cor-rod").addEventListener("change", function (e) { M.corRod = e.target.value; aplicarCamadas(); legenda(); });
    } else cores.innerHTML = "";
  }
  function item(cor, texto, forma, kind) { return "<li><span class='sw" + (forma === "linha" ? " line" : "") + "' style='" + (forma === "linha" ? "border-color:" : "background:") + cor + (forma === "ponto" ? ";border-radius:50%" : "") + "'></span><span>" + Lg.esc(texto) + (kind ? " " + Lg.kindBadge(kind) : "") + "</span></li>"; }
  function legenda() {
    var h = "";
    if (T.atual === "rs") {
      if (visivel("municipios")) {
        h += M.corMun === "risco"
          ? item("#b3202a", "Alto: 0,5% dos dias-município de maior pontuação", "caixa", "previsto") + item("#f0a830", "Atenção: 2% de maior pontuação", "caixa") + item("#dfe7ec", "Baixo", "caixa") + item("#c9d1d6", "Sem estimativa (não é risco baixo)", "caixa")
          : item("#2e8b57", "Dados disponíveis", "caixa") + item("#e0a030", "Cobertura parcial", "caixa") + item("#8d99a0", "Dados insuficientes", "caixa");
      }
      if (visivel("rodovias")) h += M.corRod === "indice" ? item("#b3202a", "Índice físico alto (relativo)", "linha", "observado") + item("#b9bfc3", "Sem dado", "linha") : item("#08306b", "Tráfego (VDM): mais escuro = mais tráfego", "linha", "observado") + item("#b9bfc3", "VDM sem dado (não é tráfego zero)", "linha");
      if (visivel("bloqueios")) h += item("#b3202a", "Bloqueio total ativo", "ponto", "observado") + item("#e07a1f", "Bloqueio parcial ativo", "ponto");
      if (visivel("s2id")) h += item("#5b3a8c", "Registro S2iD recente no município", "linha", "observado");
      if (visivel("trechos_criticos")) h += item("#7b2d8e", "Trecho crítico (fechamento simulado)", "linha", "simulado");
    } else {
      if (visivel("risco_trecho")) h += item("#b3202a", "Alto (tracejado = hora à frente)", "linha", "previsto") + item("#d98c00", "Atenção", "linha");
      if (visivel("ocorrencias")) h += item("#fff", "Ocorrência reportada (sem verificação)", "ponto", "observado") + item("#1b2630", "Ocorrência confirmada", "ponto", "confirmado");
      if (visivel("interdicoes")) h += item("#000", "Interdição confirmada: o trecho não é usado nas rotas", "ponto", "confirmado");
      if (visivel("rotas")) h += item("#333f48", "Rota habitual", "linha") + item("#1b7f5c", "Menor exposição estimada", "linha") + item("#1f6fb2", "Alternativa", "linha");
    }
    el("legenda-gl").innerHTML = h || "<li class='muted'>Nenhuma camada ativa.</li>";
  }

  /* ---------------------------------------------------------------- seleção */
  function limparSelecao() {
    M.selecionado = null;
    if (M.map && M.map.getLayer("mun-sel")) { M.map.setFilter("mun-sel", ["==", ["get", "ibge"], ""]); M.map.setFilter("rod-sel", ["==", ["get", "nome"], ""]); }
    el("contexto").innerHTML = "<h2 id='h-contexto'>Seleção</h2><p class='muted' id='contexto-vazio'>Clique em " + (T.atual === "rs" ? "um município ou uma rodovia." : "um trecho de rua com risco estimado.") + "</p>";
  }
  function mostrarContexto() { var p = el("painel-mapa"); if (p) p.scrollTop = 0; }
  function selecionarMunicipio(ibge) {
    M.selecionado = { tipo: "municipio", id: ibge };
    M.map.setFilter("mun-sel", ["==", ["get", "ibge"], ibge]); M.map.setFilter("rod-sel", ["==", ["get", "nome"], ""]);
    window.Painel.contextoMunicipio(ibge, el("contexto")); mostrarContexto();
  }
  function selecionarRodovia(p) {
    M.selecionado = { tipo: "rodovia", id: p.nome };
    M.map.setFilter("rod-sel", ["==", ["get", "nome"], p.nome]); M.map.setFilter("mun-sel", ["==", ["get", "ibge"], ""]);
    window.Painel.contextoRodovia(p, el("contexto")); mostrarContexto();
  }
  M.focarMunicipio = function (ibge) {
    T.rs().then(function (d) {
      var f = d.municipios.features.filter(function (x) { return x.properties.ibge === ibge; })[0]; if (!f || !M.pronto) return;
      var xs = [], ys = [];
      (function walk(c) { if (typeof c[0] === "number") { xs.push(c[0]); ys.push(c[1]); } else c.forEach(walk); })(f.geometry.coordinates);
      M.map.fitBounds([[Math.min.apply(null, xs), Math.min.apply(null, ys)], [Math.max.apply(null, xs), Math.max.apply(null, ys)]], { padding: 60, duration: reduzido() ? 0 : 1200 });
      selecionarMunicipio(ibge);
    });
  };
  function ligarEventos() {
    var map = M.map;
    map.on("click", function (e) {
      var caixa = [[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]];
      if (T.atual === "rs") {
        var r = map.queryRenderedFeatures(caixa, { layers: ["rod"] });
        if (r.length && visivel("rodovias")) return selecionarRodovia(r[0].properties);
        var m = map.queryRenderedFeatures(e.point, { layers: ["mun-fill"] });
        if (m.length && visivel("municipios")) selecionarMunicipio(m[0].properties.ibge);
      } else {
        var t = map.queryRenderedFeatures(caixa, { layers: ["poa-risco-obs", "poa-risco-prev"] });
        if (t.length) { M.selecionado = { tipo: "trecho", id: t[0].properties.id }; window.Painel.segmento(t[0].properties.id, el("contexto")); mostrarContexto(); }
      }
    });
    ["rod", "mun-fill", "poa-risco-obs", "poa-risco-prev"].forEach(function (l) {
      map.on("mouseenter", l, function () { map.getCanvas().style.cursor = "pointer"; }); map.on("mouseleave", l, function () { map.getCanvas().style.cursor = ""; });
    });
    el("vista-3d").addEventListener("click", function () { definir3D(true); });
    el("vista-2d").addEventListener("click", function () { definir3D(false); });
    el("exagero").addEventListener("change", function (e) { M.exagero = Number(e.target.value); if (M.tres_d) definir3D(true, false); });
    el("poa-hora").addEventListener("input", function () { clearTimeout(M._t); M._t = setTimeout(carregarRisco, 250); });
  }

  /* ---------------------------------------------------------------- Porto Alegre: dados da API */
  function carregarRisco() {
    if (T.atual !== "poa" || !habilitada("risco_trecho")) return;
    var h = Number(el("poa-hora").value);
    getJson("api/risco?h=" + h).then(function (r) {
      el("poa-hora-rotulo").textContent = h === 0 ? "agora" : "+" + h + " h (" + Lg.weekdayHour(r.hora) + ")";
      el("poa-hora-kind").innerHTML = Lg.kindBadge(r.natureza);
      r.geojson.features.forEach(function (f) { f.properties.natureza = r.natureza; });
      M.map.getSource("poa-risco").setData(r.geojson);
      el("poa-resumo").textContent = r.sem_estimativa ? "Sem estimativa para esta hora (janela de chuva incompleta)."
        : r.total_atencao_ou_alto + " trechos em Atenção ou Alto" + (r.exibidos < r.total_atencao_ou_alto ? " (mostrando os " + r.exibidos + " de maior escore)" : "") + ". Baseline sem validação em vias.";
    }).catch(function (e) { el("poa-resumo").textContent = "Não foi possível carregar o risco: " + e.message; });
  }
  function carregarOcorrencias() {
    if (T.atual !== "poa" || !habilitada("ocorrencias")) return;
    getJson("api/ocorrencias").then(function (d) {
      var ativas = d.ocorrencias.filter(function (o) { return o.situacao !== "descartada"; });
      var pt = function (o) { return { type: "Feature", geometry: { type: "Point", coordinates: [o.lon, o.lat] }, properties: { id: o.id, tipo: o.tipo, situacao: o.situacao } }; };
      M.map.getSource("poa-occ").setData({ type: "FeatureCollection", features: ativas.map(pt) });
      M.map.getSource("poa-int").setData({ type: "FeatureCollection", features: ativas.filter(function (o) { return o.situacao === "confirmada" && o.impacto_circulacao === "interdicao"; }).map(pt) });
    }).catch(function () {});
  }
  M.recarregarPoa = function () { carregarRisco(); carregarOcorrencias(); };

  /* Highlights the routes of an analysis (and their stretches of attention) on the map. */
  M.mostrarRotas = function (a, selecionada) {
    if (!M.pronto) return false;
    M.rotas = { a: a, sel: selecionada };
    var linhas = [], riscos = [];
    Object.keys(a.rotas).forEach(function (n) {
      var r = a.rotas[n], sel = n === selecionada;
      linhas.push({ type: "Feature", geometry: { type: "LineString", coordinates: r.coordenadas }, properties: { rota: n, sel: sel } });
      if (sel) r.trechos_de_risco.forEach(function (t) { if (t.coordenadas && t.coordenadas.length > 1) riscos.push({ type: "Feature", geometry: { type: "LineString", coordinates: t.coordenadas }, properties: { classe: t.classe } }); });
    });
    M.map.getSource("rotas").setData({ type: "FeatureCollection", features: linhas });
    M.map.getSource("rotas-risco").setData({ type: "FeatureCollection", features: riscos });
    var b = new gl.LngLatBounds(); a.rotas[selecionada].coordenadas.forEach(function (c) { b.extend(c); });
    M.map.fitBounds(b, { padding: 70, duration: reduzido() ? 0 : 1000, pitch: M.tres_d ? 55 : 0 });
    return true;
  };
})();
