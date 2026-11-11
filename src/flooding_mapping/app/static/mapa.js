/* Map of both territories. One controller (layers, panels, selection, data) over two interchangeable engines: MapLibre GL JS for 3D
   with terrain or flat 2D, and Leaflet (mapa2d.js) when the browser has no WebGL. Both offer the same essentials in both territories
   (occurrences, confirmed closures, attention stretches, routes, selection); only the relief and the tilted view need WebGL, and the
   panel says so. Terrain is public elevation used only to look at the relief; it feeds no risk calculation, and the vertical
   exaggeration is chosen by the user and stated. Nothing draws a water depth or an extent: only the classes that the data supports. */
(function () {
  "use strict";
  var Lg = window.Logic, T = window.Territorio, gl = window.maplibregl;
  var M = { motor: null, motorNome: null, map: null, pronto: false, iniciando: null, tres_d: true, exagero: 1.5, corMun: "cobertura", corRod: "vdm", dia: 0, marcadas: {}, selecionado: null, rotas: null, dados: null, forcarLeaflet: false };
  window.Mapa = M;

  /* Logical layers. ``ids`` are the GL layer ids of each one (the Leaflet engine maps the names to its own groups). */
  var CAMADAS = {
    municipios: { rotulo: "Municípios", kind: null, ids: ["mun-fill", "mun-line"], inicial: true },
    rodovias: { rotulo: "Rodovias do DAER", kind: "observado", ids: ["rod"], inicial: true },
    bloqueios: { rotulo: "Bloqueios ativos (CPRv BM)", kind: "observado", ids: ["bloq"], inicial: true },
    s2id: { rotulo: "Municípios com registro S2iD nos últimos 90 dias", kind: "observado", ids: ["mun-s2id"], inicial: false },
    trechos_criticos: { rotulo: "Trechos críticos na simulação", kind: "simulado", ids: ["rod-crit"], inicial: false },
    relevo: { rotulo: "Relevo sombreado", kind: null, ids: ["sombra"], inicial: true, so3d: true },
    risco_trecho: { rotulo: "Risco estimado por trecho", kind: "previsto", ids: ["poa-risco-obs", "poa-risco-prev"], inicial: true },
    ocorrencias: { rotulo: "Ocorrências reportadas e confirmadas", kind: "observado", ids: ["poa-occ"], inicial: true },
    interdicoes: { rotulo: "Interdições confirmadas", kind: "confirmado", ids: ["poa-int"], inicial: true },
    rotas: { rotulo: "Rotas da última análise", kind: "previsto", ids: ["rotas-casing", "rotas", "rotas-risco"], inicial: true }
  };
  M.CAMADAS = CAMADAS;
  var VAZIO_MUN = "#c9d1d6";

  function el(id) { return document.getElementById(id); }
  function vazio() { return { type: "FeatureCollection", features: [] }; }
  function getJson(u) { return fetch(u, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }); }
  function reduzido() { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  M.reduzido = reduzido;
  M.webglOk = function () {
    try { var c = document.createElement("canvas"); return !!(window.maplibregl && (c.getContext("webgl2") || c.getContext("webgl"))); } catch (e) { return false; }
  };

  /* ---------------------------------------------------------------- creation */
  M.iniciar = function () {
    if (M.pronto) return Promise.resolve(M.motor);
    if (M.iniciando) return M.iniciando;
    M.motorNome = (M.forcarLeaflet || !M.webglOk()) ? "leaflet" : "gl";
    M.motor = M.motorNome === "gl" ? motorGL() : window.MotorLeaflet(M);
    M.iniciando = M.motor.criar(T.territorio().vista).then(function () { return T.rs(); }).then(function (d) {
      M.dados = d; preparar(d);
      M.motor.adicionar(d, { criticos: criticos(d) });
      M.motor.aoClicar(aoClicar);
      M.map = M.motorNome === "gl" ? M.motor.nativo() : null;
      M.pronto = true; M.iniciando = null;
      renderControles(); definir3D(M.tres_d, false); aplicarCamadas(); legenda();
      var b = el("btn-motor");
      b.textContent = M.motorNome === "gl" ? "Usar o mapa 2D simples (sem WebGL)" : "Voltar ao mapa 3D";
      b.hidden = M.motorNome === "leaflet" && !M.webglOk();
      if (T.atual === "poa") M.recarregarPoa();
      return M.motor;
    }).catch(function (e) { M.iniciando = null; M.motor = null; throw e; });
    return M.iniciando;
  };
  M.trocarMotor = function (forcarLeaflet) {
    M.forcarLeaflet = forcarLeaflet;
    if (M.motor) M.motor.destruir();
    M.motor = null; M.map = null; M.pronto = false; M.iniciando = null;
    return M.iniciar().then(function () { if (M.rotas) M.mostrarRotas(M.rotas.a, M.rotas.sel); });
  };
  function criticos(d) {
    var lista = [], imp = d.impacto || {};
    ["ranking_pontes_populacao_isolada", "ranking_veiculos_km_dia_com_vdm"].forEach(function (k) { (imp[k] || []).forEach(function (r) { lista.push(r.codigo_sre); }); });
    return lista;
  }
  function preparar(d) {
    var cob = d.cobertura.municipios;
    d.municipios.features.forEach(function (f) {
      var c = cob[f.properties.ibge] || {};
      f.properties.classe = c.classe || "insuficiente";
      f.properties.s2id90 = (c.s2id_hidrologicos_90_dias || 0) > 0;
    });
    pintarRisco(false);
  }
  /* The municipal estimate for the chosen day; a municipality without one stays without a class (grey), never "low". */
  function pintarRisco(aplicar) {
    var d = M.dados; if (!d) return;
    d.municipios.features.forEach(function (f) {
      var m = d.prevPorIbge[f.properties.ibge], dia = m && (m.dias || []).filter(function (x) { return x.horizonte_dias === M.dia; })[0];
      f.properties.risco = dia ? dia.classe : null;
    });
    if (aplicar !== false && M.motor && M.pronto) M.motor.municipios(d.municipios);
  }

  /* ---------------------------------------------------------------- 3D / 2D view and territory */
  function definir3D(ligado, animar) {
    var so3d = M.motor.suporta.tres_d;
    M.tres_d = ligado && so3d;
    el("vista-3d").setAttribute("aria-pressed", String(M.tres_d)); el("vista-2d").setAttribute("aria-pressed", String(!M.tres_d));
    el("vista-3d").disabled = !so3d; el("exagero").disabled = !M.tres_d;
    M.motor.tres_d(M.tres_d, M.exagero, T.territorio().vista, animar !== false && !reduzido());
    el("nota-relevo").textContent = !so3d ? "Este navegador não tem WebGL: o mapa está em 2D simples. O relevo e a vista inclinada exigem WebGL; as demais funções são as mesmas."
      : M.tres_d ? "Relevo com exagero vertical de " + String(M.exagero).replace(".", ",") + "× apenas para visualização; não entra em nenhum cálculo de risco. O modelo de elevação pode ter artefatos sobre água e vegetação."
      : "Vista plana (2D). O relevo sombreado continua disponível como camada.";
  }
  M.irParaTerritorio = function (id) {
    if (!M.pronto) return;
    M.motor.voar(T.territorio(id).vista, M.tres_d, reduzido());
    limparSelecao(); renderControles(); aplicarCamadas(); legenda();
    if (id === "poa") M.recarregarPoa();
  };
  M.redimensionar = function () { if (M.motor && M.pronto) M.motor.redimensionar(); };

  /* ---------------------------------------------------------------- layers and controls (driven by the capabilities) */
  function habilitada(nome) { var st = T.camadas()[nome], c = CAMADAS[nome]; return !!(st && st.ativa && !(c && c.so3d && !M.motor.suporta.relevo)); }
  function visivel(nome) { return habilitada(nome) && (M.marcadas[nome] !== undefined ? M.marcadas[nome] : CAMADAS[nome].inicial); }
  function aplicarCamadas() {
    if (!M.pronto) return;
    Object.keys(CAMADAS).forEach(function (nome) { M.motor.visibilidade(nome, visivel(nome)); });
    M.motor.cores(M.corMun, M.corRod);
    el("poa-opcoes").hidden = !(T.atual === "poa" && habilitada("risco_trecho"));
  }
  function renderControles() {
    var camadas = T.camadas(), box = el("camadas"), cores = el("cores");
    var html = Object.keys(CAMADAS).filter(function (n) { return camadas[n]; }).map(function (n) {
      var st = camadas[n], c = CAMADAS[n], semMotor = c.so3d && !M.motor.suporta.relevo, ativa = st.ativa && !semMotor, marcada = visivel(n);
      return "<label class='camada" + (ativa ? "" : " inativa") + "'><input type='checkbox' data-camada='" + n + "'" + (marcada ? " checked" : "") + (ativa ? "" : " disabled") + "> " + Lg.esc(c.rotulo) +
        (c.kind ? " " + Lg.kindBadge(c.kind) : "") + (ativa ? "" : "<span class='small'>" + (semMotor ? "Exige WebGL (indisponível neste navegador)." : Lg.esc(st.rotulo) + ": " + Lg.esc(st.nota)) + "</span>") + "</label>";
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

  /* ---------------------------------------------------------------- selection */
  function limparSelecao() {
    M.selecionado = null; if (M.motor && M.pronto) M.motor.selecionar({});
    el("contexto").innerHTML = "<h2 id='h-contexto'>Seleção</h2><p class='muted' id='contexto-vazio'>Clique em " + (T.atual === "rs" ? "um município ou uma rodovia." : "um trecho de rua com risco estimado.") + "</p>";
  }
  M.limparSelecao = limparSelecao;
  function mostrarContexto() {
    var p = el("painel-mapa"); if (!p) return;
    p.scrollTop = 0; p.classList.add("aberto"); p.classList.remove("recolhido");
    el("painel-alca").setAttribute("aria-expanded", "true"); el("painel-alca").textContent = "Recolher painel";
  }
  function aoClicar(alvo) {
    if (alvo.tipo === "municipio") M.selecionarMunicipio(alvo.props.ibge);
    else if (alvo.tipo === "rodovia") {
      M.selecionado = { tipo: "rodovia", id: alvo.props.nome }; M.motor.selecionar({ rodovia: alvo.props.nome });
      window.Painel.contextoRodovia(alvo.props, el("contexto")); mostrarContexto();
    } else if (alvo.tipo === "trecho") {
      M.selecionado = { tipo: "trecho", id: alvo.props.id }; window.Painel.segmento(alvo.props.id, el("contexto")); mostrarContexto();
    }
  }
  M.selecionarMunicipio = function (ibge) {
    M.selecionado = { tipo: "municipio", id: ibge }; M.motor.selecionar({ municipio: ibge });
    window.Painel.contextoMunicipio(ibge, el("contexto")); mostrarContexto();
  };
  function caixaDe(coords) {
    var xs = [], ys = [];
    (function walk(c) { if (typeof c[0] === "number") { xs.push(c[0]); ys.push(c[1]); } else c.forEach(walk); })(coords);
    return [[Math.min.apply(null, xs), Math.min.apply(null, ys)], [Math.max.apply(null, xs), Math.max.apply(null, ys)]];
  }
  M.focarMunicipio = function (ibge) {
    T.rs().then(function (d) {
      var f = d.municipios.features.filter(function (x) { return x.properties.ibge === ibge; })[0]; if (!f || !M.pronto) return;
      M.motor.ajustar(caixaDe(f.geometry.coordinates), { padding: 60, reduzido: reduzido() });
      M.selecionarMunicipio(ibge);
    });
  };

  /* ---------------------------------------------------------------- Porto Alegre: data from the API */
  function carregarRisco() {
    if (T.atual !== "poa" || !habilitada("risco_trecho")) return;
    var h = Number(el("poa-hora").value);
    getJson("api/risco?h=" + h).then(function (r) {
      el("poa-hora-rotulo").textContent = h === 0 ? "agora" : "+" + h + " h (" + Lg.weekdayHour(r.hora) + ")";
      el("poa-hora-kind").innerHTML = Lg.kindBadge(r.natureza);
      r.geojson.features.forEach(function (f) { f.properties.natureza = r.natureza; });
      M.motor.dados("poa-risco", r.geojson);
      el("poa-resumo").textContent = r.sem_estimativa ? "Sem estimativa para esta hora (janela de chuva incompleta)."
        : r.total_atencao_ou_alto + " trechos em Atenção ou Alto" + (r.exibidos < r.total_atencao_ou_alto ? " (mostrando os " + r.exibidos + " de maior escore)" : "") + ". Baseline sem validação em vias." + (r.escopo_da_chuva ? " " + r.escopo_da_chuva.charAt(0).toUpperCase() + r.escopo_da_chuva.slice(1) + "." : "");
    }).catch(function (e) {
      M.motor.dados("poa-risco", vazio());
      el("poa-resumo").textContent = "Risco indisponível: " + e.message + (e.ultima ? " Última atualização conhecida: " + Lg.formatInstant(e.ultima) + "." : "");
    });
  }
  function carregarOcorrencias() {
    if (T.atual !== "poa" || !habilitada("ocorrencias")) return;
    getJson("api/ocorrencias").then(function (d) {
      var ativas = d.ocorrencias.filter(function (o) { return o.situacao !== "descartada"; });
      var pt = function (o) { return { type: "Feature", geometry: { type: "Point", coordinates: [o.lon, o.lat] }, properties: { id: o.id, tipo: o.tipo, situacao: o.situacao } }; };
      M.motor.dados("poa-occ", { type: "FeatureCollection", features: ativas.map(pt) });
      M.motor.dados("poa-int", { type: "FeatureCollection", features: ativas.filter(function (o) { return o.situacao === "confirmada" && o.impacto_circulacao === "interdicao"; }).map(pt) });
    }).catch(function () {});
  }
  M.recarregarPoa = function () { if (M.pronto) { carregarRisco(); carregarOcorrencias(); } };

  /* Highlights the routes of an analysis (and their stretches of attention) on the map. */
  M.mostrarRotas = function (a, selecionada) {
    if (!M.pronto) return false;
    M.rotas = { a: a, sel: selecionada };
    var linhas = [], riscos = [], pts = [];
    Object.keys(a.rotas).forEach(function (n) {
      var r = a.rotas[n], sel = n === selecionada;
      linhas.push({ type: "Feature", geometry: { type: "LineString", coordinates: r.coordenadas }, properties: { rota: n, sel: sel } });
      if (sel) {
        pts = r.coordenadas;
        r.trechos_de_risco.forEach(function (t) { if (t.coordenadas && t.coordenadas.length > 1) riscos.push({ type: "Feature", geometry: { type: "LineString", coordinates: t.coordenadas }, properties: { classe: t.classe } }); });
      }
    });
    M.motor.dados("rotas", { type: "FeatureCollection", features: linhas }); M.motor.dados("rotas-risco", { type: "FeatureCollection", features: riscos });
    if (pts.length) M.motor.ajustar(caixaDe(pts), { padding: 70, reduzido: reduzido(), pitch: M.tres_d ? 55 : 0 });
    return true;
  };

  /* ---------------------------------------------------------------- general controls */
  function ligarControles() {
    el("vista-3d").addEventListener("click", function () { if (M.pronto) definir3D(true); });
    el("vista-2d").addEventListener("click", function () { if (M.pronto) definir3D(false); });
    el("exagero").addEventListener("change", function (e) { M.exagero = Number(e.target.value); if (M.pronto && M.tres_d) definir3D(true, false); });
    el("poa-hora").addEventListener("input", function () { clearTimeout(M._t); M._t = setTimeout(carregarRisco, 250); });
    el("painel-alca").addEventListener("click", function () {
      var p = el("painel-mapa"), recolher = !p.classList.contains("recolhido");
      p.classList.toggle("recolhido", recolher); if (!recolher) p.classList.add("aberto");
      this.setAttribute("aria-expanded", String(!recolher)); this.textContent = recolher ? "Mostrar painel" : "Recolher painel";
    });
    el("btn-motor").addEventListener("click", function () {
      var paraLeaflet = M.motorNome === "gl";
      if (!paraLeaflet && !M.webglOk()) return;
      M.trocarMotor(paraLeaflet).then(function () { M.redimensionar(); });
    });
  }

  /* ---------------------------------------------------------------- MapLibre engine (3D, and 2D with WebGL) */
  function motorGL() {
    var DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png", OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png", map;
    var CLASSE_POA = ["match", ["get", "classe"], "alto", "#b3202a", "atencao", "#d98c00", "#7c8b95"];
    var ROTA_COR = ["match", ["get", "rota"], "habitual", "#333f48", "menor_exposicao", "#1b7f5c", "alternativa", "#1f6fb2", "#333"];
    var COR_MUN_GL = { cobertura: ["match", ["get", "classe"], "disponivel", "#2e8b57", "parcial", "#e0a030", "insuficiente", "#8d99a0", VAZIO_MUN],
                       risco: ["match", ["get", "risco"], "alto", "#b3202a", "atencao", "#f0a830", "baixo", "#dfe7ec", VAZIO_MUN] };
    var COR_ROD_GL = { vdm: ["step", ["to-number", ["get", "vdm"], -1], "#b9bfc3", 0, "#c6dbef", 2000, "#6baed6", 8000, "#2171b5", 20000, "#08306b"],
                       indice: ["step", ["to-number", ["get", "indice_fisico"], -1], "#b9bfc3", 0, "#d9ead3", 50, "#f0c040", 85, "#b3202a"] };
    var m = { suporta: { tres_d: true, relevo: true } };
    m.criar = function (vista) {
      map = new gl.Map({ container: "mapa-gl", center: vista.centro, zoom: vista.zoom, pitch: vista.inclinacao, bearing: vista.rumo, maxPitch: 75, attributionControl: { compact: true },
        style: { version: 8, sources: { osm: { type: "raster", tiles: [OSM], tileSize: 256, maxzoom: 19, attribution: "&copy; colaboradores do OpenStreetMap" },
                                        dem: { type: "raster-dem", tiles: [DEM], encoding: "terrarium", tileSize: 256, maxzoom: 14, attribution: "Elevação: AWS Terrain Tiles" } },
                 layers: [{ id: "base", type: "raster", source: "osm" }, { id: "sombra", type: "hillshade", source: "dem", paint: { "hillshade-exaggeration": 0.4, "hillshade-shadow-color": "#3b4750" } }] } });
      map.addControl(new gl.NavigationControl({ visualizePitch: true }), "top-left");
      map.addControl(new gl.ScaleControl({ unit: "metric" }), "bottom-left");
      map.on("error", function (e) { var t = (e && e.error && e.error.message) || ""; if (/Failed to fetch|NetworkError|Load failed|ERR_/.test(t)) el("nota-relevo").textContent = "Parte dos mapas-base não carregou (sem conexão?). Os dados do painel continuam valendo."; });
      return new Promise(function (resolve) { map.on("load", resolve); });
    };
    m.adicionar = function (d, o) {
      map.addSource("municipios", { type: "geojson", data: d.municipios, promoteId: "ibge" });
      map.addLayer({ id: "mun-fill", type: "fill", source: "municipios", paint: { "fill-color": COR_MUN_GL.cobertura, "fill-opacity": 0.5 } });
      map.addLayer({ id: "mun-line", type: "line", source: "municipios", paint: { "line-color": "#52626d", "line-width": 0.6 } });
      map.addLayer({ id: "mun-s2id", type: "line", source: "municipios", filter: ["==", ["get", "s2id90"], true], paint: { "line-color": "#5b3a8c", "line-width": 2.4 } });
      map.addLayer({ id: "mun-sel", type: "line", source: "municipios", filter: ["==", ["get", "ibge"], ""], paint: { "line-color": "#000", "line-width": 3 } });
      map.addSource("rodovias", { type: "geojson", data: d.rodovias });
      map.addLayer({ id: "rod", type: "line", source: "rodovias", layout: { "line-cap": "round" }, paint: { "line-color": COR_ROD_GL.vdm, "line-width": ["interpolate", ["linear"], ["zoom"], 5, 1.2, 12, 4] } });
      map.addLayer({ id: "rod-crit", type: "line", source: "rodovias", filter: ["in", ["get", "codigo_sre"], ["literal", o.criticos]], paint: { "line-color": "#7b2d8e", "line-width": 5, "line-dasharray": [2, 1.5] } });
      map.addLayer({ id: "rod-sel", type: "line", source: "rodovias", filter: ["==", ["get", "nome"], ""], paint: { "line-color": "#000", "line-width": 7, "line-opacity": 0.5 } });
      var blq = d.bloqueios ? { type: "FeatureCollection", features: (d.bloqueios.bloqueios || []).filter(function (b) { return b.lat != null; }).map(function (b) {
        return { type: "Feature", geometry: { type: "Point", coordinates: [b.lng, b.lat] }, properties: { id: b.id, tipo: b.tipo, rodovia: b.rodovia, municipio: b.municipio } }; }) } : vazio();
      map.addSource("bloqueios", { type: "geojson", data: blq });
      map.addLayer({ id: "bloq", type: "circle", source: "bloqueios", paint: { "circle-radius": 7, "circle-color": ["match", ["get", "tipo"], "total", "#b3202a", "#e07a1f"], "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
      ["poa-risco", "poa-occ", "poa-int", "rotas", "rotas-risco"].forEach(function (s) { map.addSource(s, { type: "geojson", data: vazio() }); });
      map.addLayer({ id: "poa-risco-obs", type: "line", source: "poa-risco", filter: ["==", ["get", "natureza"], "observado"], layout: { "line-cap": "round" }, paint: { "line-color": CLASSE_POA, "line-width": ["interpolate", ["linear"], ["zoom"], 10, 2, 16, 6] } });
      map.addLayer({ id: "poa-risco-prev", type: "line", source: "poa-risco", filter: ["==", ["get", "natureza"], "previsto"], layout: { "line-cap": "butt" }, paint: { "line-color": CLASSE_POA, "line-dasharray": [1.6, 1.1], "line-width": ["interpolate", ["linear"], ["zoom"], 10, 2, 16, 6] } });
      map.addLayer({ id: "poa-occ", type: "circle", source: "poa-occ", paint: { "circle-radius": 7, "circle-color": ["match", ["get", "situacao"], "confirmada", "#1b2630", "#ffffff"], "circle-stroke-color": ["match", ["get", "situacao"], "confirmada", "#ffffff", "#1f6fb2"], "circle-stroke-width": 2.5 } });
      map.addLayer({ id: "poa-int", type: "circle", source: "poa-int", paint: { "circle-radius": 10, "circle-color": "#000", "circle-stroke-color": "#fff", "circle-stroke-width": 3 } });
      map.addLayer({ id: "rotas-casing", type: "line", source: "rotas", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#fff", "line-width": ["case", ["get", "sel"], 11, 7] } });
      map.addLayer({ id: "rotas", type: "line", source: "rotas", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": ROTA_COR, "line-width": ["case", ["get", "sel"], 6, 3], "line-opacity": ["case", ["get", "sel"], 1, 0.7] } });
      map.addLayer({ id: "rotas-risco", type: "line", source: "rotas-risco", layout: { "line-cap": "butt" }, paint: { "line-color": "#b3202a", "line-width": 6, "line-dasharray": [1.4, 1] } });
    };
    m.visibilidade = function (nome, ligado) { CAMADAS[nome].ids.forEach(function (id) { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", ligado ? "visible" : "none"); }); };
    m.cores = function (cm, cr) { map.setPaintProperty("mun-fill", "fill-color", COR_MUN_GL[cm] || COR_MUN_GL.cobertura); map.setPaintProperty("rod", "line-color", COR_ROD_GL[cr] || COR_ROD_GL.vdm); };
    m.municipios = function (geo) { map.getSource("municipios").setData(geo); };
    m.dados = function (nome, geo) { map.getSource(nome).setData(geo); };
    m.selecionar = function (s) {
      map.setFilter("mun-sel", ["==", ["get", "ibge"], s.municipio || ""]); map.setFilter("rod-sel", ["==", ["get", "nome"], s.rodovia || ""]);
    };
    m.tres_d = function (ligado, exagero, vista, animar) {
      map.setTerrain(ligado ? { source: "dem", exaggeration: exagero } : null);
      map.easeTo({ pitch: ligado ? vista.inclinacao : 0, bearing: ligado ? vista.rumo : 0, duration: animar ? 900 : 0 });
    };
    m.voar = function (v, tres_d, sem_animacao) { map.flyTo({ center: v.centro, zoom: v.zoom, pitch: tres_d ? v.inclinacao : 0, bearing: tres_d ? v.rumo : 0, duration: sem_animacao ? 0 : 2200, essential: true }); };
    m.ajustar = function (caixa, o) { map.fitBounds(caixa, { padding: o.padding, duration: o.reduzido ? 0 : 1000, pitch: o.pitch }); };
    m.aoClicar = function (cb) {
      map.on("click", function (e) {
        var caixa = [[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]];
        if (T.atual === "rs") {
          var r = map.queryRenderedFeatures(caixa, { layers: ["rod"] });
          if (r.length && map.getLayoutProperty("rod", "visibility") !== "none") return cb({ tipo: "rodovia", props: r[0].properties });
          var mu = map.queryRenderedFeatures(e.point, { layers: ["mun-fill"] });
          if (mu.length && map.getLayoutProperty("mun-fill", "visibility") !== "none") cb({ tipo: "municipio", props: mu[0].properties });
        } else {
          var t = map.queryRenderedFeatures(caixa, { layers: ["poa-risco-obs", "poa-risco-prev"] });
          if (t.length) cb({ tipo: "trecho", props: t[0].properties });
        }
      });
      ["rod", "mun-fill", "poa-risco-obs", "poa-risco-prev"].forEach(function (l) {
        map.on("mouseenter", l, function () { map.getCanvas().style.cursor = "pointer"; }); map.on("mouseleave", l, function () { map.getCanvas().style.cursor = ""; });
      });
    };
    m.redimensionar = function () { map.resize(); };
    m.destruir = function () { map.remove(); el("mapa-gl").innerHTML = ""; };
    m.nativo = function () { return map; };
    return m;
  }
  ligarControles();
})();
