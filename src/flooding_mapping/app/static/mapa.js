/* Mapa de Porto Alegre. Um controlador (camadas, painéis, seleção, dados) sobre dois motores intercambiáveis: MapLibre GL JS para 3D com relevo
   ou 2D plano, e Leaflet (mapa2d.js) quando o navegador não tem WebGL. As camadas de análise (escoamento potencial da Fase 3 e drenagem cadastrada)
   usam tiles vetoriais e exigem WebGL; o painel diz isso. O relevo é elevação pública usada só para olhar o terreno: não entra em nenhum cálculo,
   e o exagero vertical é escolhido pelo usuário e declarado. Nada aqui desenha profundidade nem extensão de água. O mapa de duas escalas
   (Rio Grande do Sul e Porto Alegre) está arquivado em app/arquivo/painel-estadual/. */
(function () {
  "use strict";
  var Lg = window.Logic, T = window.Territorio, gl = window.maplibregl;
  var M = { motor: null, motorNome: null, map: null, pronto: false, iniciando: null, tres_d: true, exagero: 1.5, marcadas: {}, selecionado: null, forcarLeaflet: false };
  window.Mapa = M;

  /* Logical layers. ``ids`` are the GL layer ids of each one (the Leaflet engine maps the names to its own groups). */
  var CAMADAS = {
    relevo: { rotulo: "Relevo sombreado", kind: null, ids: ["sombra"], inicial: true, so3d: true },
    drenagem_cadastro: { rotulo: "Drenagem cadastrada (inventário, só contexto)", kind: "observado", ids: ["dren-rede-halo", "dren-rede-0", "dren-rede-1", "dren-rede-2", "dren-rede-dup", "dren-pocos", "dren-bocas", "dren-bombas", "dren-pt-dup", "dren-sel-rede", "dren-sel-pocos", "dren-sel-bocas", "dren-sel-bombas"], inicial: false, so3d: true },
    escoamento_fase3: { rotulo: "Escoamento potencial por trecho (motor da Fase 3)", kind: "simulado", ids: ["f3-casing", "f3-sem-dados", "f3-sel"], inicial: false, so3d: true }
  };
  M.CAMADAS = CAMADAS;

  function el(id) { return document.getElementById(id); }
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
    M.iniciando = M.motor.criar(T.territorio().vista).then(function () {
      M.motor.adicionar();
      M.motor.aoClicar(aoClicar);
      M.map = M.motorNome === "gl" ? M.motor.nativo() : null;
      M.pronto = true; M.iniciando = null;
      aplicarPedido(); renderControles(); definir3D(M.tres_d, false); aplicarCamadas(); legenda();
      var b = el("btn-motor");
      b.textContent = M.motorNome === "gl" ? "Usar o mapa 2D simples (sem WebGL)" : "Voltar ao mapa 3D";
      b.hidden = M.motorNome === "leaflet" && !M.webglOk();
      return M.motor;
    }).catch(function (e) { M.iniciando = null; M.motor = null; throw e; });
    return M.iniciando;
  };
  M.trocarMotor = function (forcarLeaflet) {
    M.forcarLeaflet = forcarLeaflet;
    if (M.motor) M.motor.destruir();
    M.motor = null; M.map = null; M.pronto = false; M.iniciando = null;
    return M.iniciar();
  };
  /* ---------------------------------------------------------------- vista 3D / 2D */
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
  M.redimensionar = function () { if (M.motor && M.pronto) M.motor.redimensionar(); };

  /* ---------------------------------------------------------------- layers and controls (driven by the capabilities) */
  function habilitada(nome) { var st = T.camadas()[nome], c = CAMADAS[nome]; return !!(st && st.ativa && !(c && c.so3d && !M.motor.suporta.relevo)); }
  function visivel(nome) { return habilitada(nome) && (M.marcadas[nome] !== undefined ? M.marcadas[nome] : CAMADAS[nome].inicial); }
  function aplicarCamadas() {
    if (!M.pronto) return;
    Object.keys(CAMADAS).forEach(function (nome) { M.motor.visibilidade(nome, visivel(nome)); });
    var f3 = visivel("escoamento_fase3");
    el("f3-opcoes").hidden = !f3;
    if (f3) ligarFase3();
    var dr = visivel("drenagem_cadastro");
    el("dren-opcoes").hidden = !dr;
    if (dr) ligarDrenagem();
    renderDimensoes();
  }
  /* Drenagem cadastrada: contexto do inventário da Fase 2, sem relação com o cálculo. Carregada só quando ligada. */
  function ligarDrenagem() {
    var Dr = window.Drenagem;
    if (!M._drOuvindo) { M._drOuvindo = true; Dr.aoMudar(function () { if (M.motor && M.pronto) M.motor.dren_grupos(Dr.grupos); legenda(); }); }
    Dr.montarPainel(); M.motor.dren_grupos(Dr.grupos);
    Dr.carregar().then(function () { Dr.montarPainel(); M.motor.dren_grupos(Dr.grupos); legenda(); }).catch(function () { Dr.montarPainel(); legenda(); });
  }
  /* Pedido de abertura vindo do endereço ("#poa/mapa?escoamento=1&p=30&pacote=an&modo=l"): só valores conhecidos, uma única vez. */
  function aplicarPedido() {
    var q = M.pedido; M.pedido = null; if (!q) return;
    var F = window.Fase3, e = F.estado;
    if (q.escoamento === "1") M.marcadas.escoamento_fase3 = true;
    if (q.drenagem === "1") M.marcadas.drenagem_cadastro = true;
    if (["m1", "an", "li"].indexOf(q.pacote) >= 0) e.pacote = q.pacote;
    if (["c", "l", "tp", "cb"].indexOf(q.modo) >= 0) e.modo = q.modo;
    if (["10", "20", "30"].indexOf(q.p) >= 0) { F.pedidoP = Number(q.p); if (F.meta) e.p = F.pedidoP; }
    /* Vista e trecho pedidos (demonstração no celular, links de estudo): só números dentro de Porto Alegre e um índice inteiro de trecho. */
    var lon = Number(q.lon), lat = Number(q.lat), z = Number(q.zoom);
    if (q.lon && q.lat && isFinite(lon) && isFinite(lat) && lon > -51.4 && lon < -50.9 && lat > -30.35 && lat < -29.9) M._vistaPedida = { centro: [lon, lat], zoom: isFinite(z) ? Math.min(18, Math.max(10, z)) : 15 };
    if (/^\d{1,7}$/.test(q.trecho || "")) M._trechoPedido = Number(q.trecho);
  }
  /* Pedido que chega com o mapa já aberto (link do simulador): aplica e redesenha. */
  M.aplicarPedido = function () { if (!M.pronto) return; aplicarPedido(); renderControles(); aplicarCamadas(); legenda(); pintarFase3(); };
  /* A chuva escolhida no mapa é a mesma do simulador e dos resultados. */
  function sincronizarChuva() { var F = window.Fase3; if (window.Resultados && F.estado.p != null) window.Resultados.P = F.estado.p; }
  /* Camada da Fase 3: os dados são carregados só quando ela é ligada; o desenho e a legenda seguem os controles do painel. */
  function ligarFase3() {
    var F = window.Fase3;
    if (!M._f3ouvindo) {
      M._f3ouvindo = true; F.aoMudar(function () { sincronizarChuva(); pintarFase3(); legenda(); renderDimensoes(); });
      if (M.map) M.map.on("zoomend", function () { F.avisarZoom(M.map.getZoom()); });
    }
    F.montarPainel();
    F.carregar().then(function () {
      if (M._vistaPedida && M.map) { M.map.jumpTo({ center: M._vistaPedida.centro, zoom: M._vistaPedida.zoom }); M._vistaPedida = null; M._f3aproximou = true; }
      if (M._trechoPedido != null) { var n = M._trechoPedido; M._trechoPedido = null; if (n < F.meta.trechos) aoClicar({ tipo: "trecho_f3", props: { n: n } }); }
      sincronizarChuva(); F.montarPainel(); pintarFase3(); legenda(); renderDimensoes(); F.avisarZoom(M.map ? M.map.getZoom() : 99);
      if (M.map && M.map.getZoom() < F.meta.zoom[0] && !M._f3aproximou) { M._f3aproximou = true; M.map.easeTo({ zoom: F.meta.zoom[0], duration: reduzido() ? 0 : 900 }); }
    }).catch(function () { F.montarPainel(); legenda(); renderDimensoes(); });
  }
  function pintarFase3() { if (M.motor && M.pronto && window.Fase3.meta && visivel("escoamento_fase3")) M.motor.f3_pintar(window.Fase3.estilo()); }

  /* ---------------------------------------------------------------- dimensões de análise (Porto Alegre)
     Quatro perguntas, cada uma ligada a uma grandeza que já existe: A, B e C usam a camada de escoamento (a cor das linhas mostra uma por vez);
     D, a drenagem cadastrada, é outra camada e pode ser sobreposta. Nenhuma combina as outras em índice. */
  var DIMENSOES = [
    { id: "A", modo: "l", camada: "escoamento_fase3", nome: "Geração", pergunta: "Quanto da chuva pode se transformar em água que escoa pela superfície (geração de escoamento superficial).",
      nota: "Escoamento potencial só da superfície sob o trecho, pelo uso do solo e pelos coeficientes de escoamento do pacote escolhido. Não inclui o que vem de montante." },
    { id: "B", modo: "c", camada: "escoamento_fase3", nome: "Concentração", pergunta: "Para onde a água que escoa tende a convergir pelo território (concentração de escoamento superficial).",
      nota: "Escoamento potencial somado sobre a área a montante que o relevo encaminha ao trecho. É contribuição potencial, não vazão, e não se soma entre trechos." },
    { id: "C", modo: "tp", camada: "escoamento_fase3", nome: "Topografia", pergunta: "Onde o relevo apresenta condições mais favoráveis à retenção de água (propensão topográfica à retenção).",
      nota: "Posto relativo entre trechos pelo preenchimento de depressões no Copernicus GLO-30 (30 m). Não é profundidade de alagamento, e o modelo não resolve depressões urbanas pequenas." },
    { id: "D", camada: "drenagem_cadastro", nome: "Drenagem", pergunta: "Onde estão localizados os dispositivos e as redes de drenagem cadastrados (infraestrutura de drenagem).",
      nota: "Presença no cadastro não comprova conexão hidráulica, capacidade nem funcionamento. Fica fora do cálculo." }
  ];
  M.DIMENSOES = DIMENSOES;
  function dimensaoAtiva(d) {
    if (d.modo) return visivel(d.camada) && window.Fase3.estado.modo === d.modo;
    return visivel(d.camada);
  }
  function alternarDimensao(d) {
    var F = window.Fase3;
    if (dimensaoAtiva(d)) M.marcadas[d.camada] = false;
    else { M.marcadas[d.camada] = true; if (d.modo) F.estado.modo = d.modo; }
    renderControles(); aplicarCamadas(); legenda();
  }
  M.tentarFase3 = function () { var F = window.Fase3; F.erro = null; F._meta = null; ligarFase3(); renderDimensoes(); };
  M.voltarVisaoGeral = function () {
    if (!M.pronto) return;
    limparSelecao(); M.motor.voar(T.territorio().vista, M.tres_d, reduzido());
  };
  function renderDimensoes() {
    var box = el("dimensoes"), F = window.Fase3;
    if (!box) return;
    var foco = document.activeElement && document.activeElement.dataset && document.activeElement.dataset.dim;
    var poa = M.pronto && (habilitada("escoamento_fase3") || habilitada("drenagem_cadastro"));
    box.hidden = !poa; el("camadas-sub").textContent = poa ? "(outras)" : "";
    if (!poa) { box.innerHTML = ""; return; }
    var ativas = DIMENSOES.filter(dimensaoAtiva);
    var botoes = DIMENSOES.filter(function (d) { return habilitada(d.camada); }).map(function (d) {
      var on = dimensaoAtiva(d);
      return "<li><button type='button' class='dim" + (on ? " on" : "") + "' data-dim='" + d.id + "' aria-pressed='" + on + "'><span class='dim-id'>" + d.id + "</span><span><b>" + Lg.esc(d.nome) + "</b><span class='small'>" + Lg.esc(d.pergunta) + "</span></span></button></li>";
    }).join("");
    var f3on = visivel("escoamento_fase3") && F.meta && F.estado.modo !== "tp", p = F.estado.p;
    var chuva = f3on && p != null ? "<p class='small dim-chuva' id='dim-chuva'><b>Chuva de referência: " + String(p).replace(".", ",") + " mm</b>, igual em toda a cidade. " +
      (p === 30 ? "É o percentil 75 dos totais por evento de 2017 a 2026 (reanálise ERA5), não a média. " : "") + "Cenário de cálculo, não previsão.</p>" : "";
    var erro = F.erro && visivel("escoamento_fase3") ? "<p class='small f3-sem' role='status'>Os dados de escoamento não estão disponíveis (" + Lg.esc(F.erro) + "); esta dimensão não pode ser mostrada. <button type='button' class='link' id='dim-tentar'>Tentar de novo</button></p>" : "";
    var versao = F.meta && visivel("escoamento_fase3") ? "<p class='small' id='dim-versao'>Dados de escoamento: camada v" + Lg.esc(F.meta.versao) + (window.FM_DADOS.versao ? ", conjunto " + Lg.esc(window.FM_DADOS.versao) : "") + ".</p>" : "";
    box.innerHTML = "<h2 id='h-dim'>O que você quer ver?</h2><p class='small'>Cada item é independente, sem índice único. A, B e C pintam as linhas, um por vez. D pode ficar por cima.</p>" +
      "<ul class='dim-lista'>" + botoes + "</ul>" +
      (ativas.length ? "<details class='dim-nota small'><summary>Como ler " + (ativas.length > 1 ? "estas dimensões" : "esta dimensão") + "</summary>" + ativas.map(function (d) { return "<p><b>" + d.id + ".</b> " + Lg.esc(d.nota) + "</p>"; }).join("") + "</details>" : "<p class='small muted'>Nenhuma dimensão ligada. Escolha uma acima para colorir os trechos.</p>") +
      chuva + erro + versao +
      "<p class='dim-nav small'><a href='#poa/resultados'>Ler os resultados por contexto territorial</a> · <button type='button' class='link' id='dim-geral'>Voltar à visão geral da cidade</button></p>";
    Array.prototype.forEach.call(box.querySelectorAll("button[data-dim]"), function (b) {
      b.addEventListener("click", function () { alternarDimensao(DIMENSOES.filter(function (d) { return d.id === b.dataset.dim; })[0]); });
    });
    el("dim-geral").addEventListener("click", M.voltarVisaoGeral);
    if (el("dim-tentar")) el("dim-tentar").addEventListener("click", M.tentarFase3);
    if (foco) { var f = box.querySelector("button[data-dim=" + foco + "]"); if (f) f.focus(); }
  }
  function renderControles() {
    var camadas = T.camadas(), box = el("camadas");
    var html = Object.keys(CAMADAS).filter(function (n) { return camadas[n]; }).map(function (n) {
      var st = camadas[n], c = CAMADAS[n], semMotor = c.so3d && !M.motor.suporta.relevo, ativa = st.ativa && !semMotor, marcada = visivel(n);
      return "<label class='camada" + (ativa ? "" : " inativa") + "'><input type='checkbox' data-camada='" + n + "'" + (marcada ? " checked" : "") + (ativa ? "" : " disabled") + "> " + Lg.esc(c.rotulo) +
        (c.kind ? " " + Lg.kindBadge(c.kind) : "") + (ativa ? "" : "<span class='small'>" + (semMotor ? "Exige WebGL (indisponível neste navegador)." : Lg.esc(st.rotulo) + ": " + Lg.esc(st.nota)) + "</span>") + "</label>";
    }).join("");
    box.innerHTML = html || "<p class='muted'>Nenhuma camada descrita.</p>";
    Array.prototype.forEach.call(box.querySelectorAll("input[data-camada]"), function (i) { i.addEventListener("change", function () { M.marcadas[i.dataset.camada] = i.checked; aplicarCamadas(); legenda(); }); });
    renderDimensoes();
  }
  function item(cor, texto, forma, kind) { return "<li><span class='sw" + (forma === "linha" ? " line" : "") + "' style='" + (forma === "linha" ? "border-color:" : "background:") + cor + (forma === "ponto" ? ";border-radius:50%" : "") + "'></span><span>" + Lg.esc(texto) + (kind ? " " + Lg.kindBadge(kind) : "") + "</span></li>"; }
  function legenda() {
    var h = "";
    if (visivel("escoamento_fase3")) h += window.Fase3.legenda();
    if (visivel("drenagem_cadastro")) h += window.Drenagem.legenda();
    el("legenda-gl").innerHTML = h || "<li class='muted'>Nenhuma camada ativa.</li>";
  }

  /* ---------------------------------------------------------------- selection */
  function limparSelecao() {
    M.selecionado = null; if (M.motor && M.pronto) M.motor.selecionar({});
    el("contexto").innerHTML = "<h2 id='h-contexto'>Seleção</h2><p class='muted' id='contexto-vazio'>Ligue uma dimensão e clique em um trecho de rua, ou um item da drenagem cadastrada.</p>";
  }
  M.limparSelecao = limparSelecao;
  function mostrarContexto() {
    var p = el("painel-mapa"); if (!p) return;
    p.scrollTop = 0; p.classList.add("aberto"); p.classList.remove("recolhido");
    el("painel-alca").setAttribute("aria-expanded", "true"); el("painel-alca").textContent = "Recolher painel";
  }
  function aoClicar(alvo) {
    if (alvo.tipo === "dren") {
      M.selecionado = { tipo: "dren", id: alvo.camada + ":" + alvo.n }; M.motor.selecionar({ dren: { camada: alvo.camada, n: alvo.n } });
      window.Drenagem.detalhe(alvo.camada, alvo.n, el("contexto")); mostrarContexto();
    } else if (alvo.tipo === "trecho_f3") {
      M.selecionado = { tipo: "trecho_f3", id: alvo.props.n }; M.motor.selecionar({ f3: alvo.props.n });
      window.Fase3.detalhe(alvo.props.n, el("contexto")); mostrarContexto();
    }
  }
  /* ---------------------------------------------------------------- controles gerais */
  function ligarControles() {
    el("vista-3d").addEventListener("click", function () { if (M.pronto) definir3D(true); });
    el("vista-2d").addEventListener("click", function () { if (M.pronto) definir3D(false); });
    el("exagero").addEventListener("change", function (e) { M.exagero = Number(e.target.value); if (M.pronto && M.tres_d) definir3D(true, false); });
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
    var map;
    var m = { suporta: { tres_d: true, relevo: true } };
    m.criar = function (vista) {
      return window.MapaBase.estiloGL({ relevo: { exagero: 0.4 } }).then(function (estilo) {
        map = new gl.Map({ container: "mapa-gl", center: vista.centro, zoom: vista.zoom, pitch: vista.inclinacao, bearing: vista.rumo, maxPitch: 75, attributionControl: { compact: true }, style: estilo });
        map.addControl(new gl.NavigationControl({ visualizePitch: true }), "top-left");
        map.addControl(new gl.ScaleControl({ unit: "metric" }), "bottom-left");
        map.on("error", function (e) { var t = (e && e.error && e.error.message) || ""; if (/Failed to fetch|NetworkError|Load failed|ERR_/.test(t)) el("nota-relevo").textContent = "Parte dos mapas-base não carregou (sem conexão?). Os dados do painel continuam valendo."; });
        return new Promise(function (resolve) { map.on("load", resolve); });
      });
    };
    m.adicionar = function () {
      map.addSource("f3", { type: "vector", tiles: [window.Fase3.urlTiles()], minzoom: 13, maxzoom: 15, promoteId: "n", attribution: "Escoamento potencial: motor da Fase 3 (Flooding Mapping)" });
      var larg = ["interpolate", ["linear"], ["zoom"], 13, 1.6, 16, 5];
      var DR = window.Drenagem, vtile = function (nome, zmin) { map.addSource("dren-" + nome, { type: "vector", tiles: [DR.urlTiles(nome)], minzoom: zmin, maxzoom: 15, attribution: "Drenagem cadastrada: Prefeitura de Porto Alegre" }); };
      vtile("rede", 14); vtile("pocos", 15); vtile("bocas", 15); vtile("bombas", 14);
      map.addLayer({ id: "f3-casing", type: "line", source: "f3", "source-layer": "trechos", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#3c4a54", "line-opacity": 0.55, "line-width": ["interpolate", ["linear"], ["zoom"], 13, 2.6, 16, 7] } });
      map.addLayer({ id: "f3-sem-dados", type: "line", source: "f3", "source-layer": "trechos", filter: ["!", ["has", "c_m1_max"]], layout: { "line-cap": "butt" }, paint: { "line-color": "#7d8a93", "line-width": 2, "line-dasharray": [1.4, 1.4] } });
      var lw = ["interpolate", ["linear"], ["zoom"], 14, 1, 18, 3.5], oculto = { visibility: "none" }, dren = function (l) { map.addLayer(l); };
      var fr = function (cat) { return ["all", ["==", ["get", "cat"], cat], ["==", ["get", "u"], 0]]; };
      dren({ id: "dren-rede-halo", type: "line", source: "dren-rede", "source-layer": "rede", filter: ["==", ["get", "s"], 1], layout: { "line-cap": "round", visibility: "none" }, paint: { "line-color": DR.COR.sinalizado, "line-opacity": 0.6, "line-width": ["interpolate", ["linear"], ["zoom"], 14, 4, 18, 9] } });
      dren({ id: "dren-rede-0", type: "line", source: "dren-rede", "source-layer": "rede", filter: fr(0), layout: { "line-cap": "round", visibility: "none" }, paint: { "line-color": DR.COR.cadastro, "line-width": lw } });
      dren({ id: "dren-rede-1", type: "line", source: "dren-rede", "source-layer": "rede", filter: fr(1), layout: { "line-cap": "round", visibility: "none" }, paint: { "line-color": DR.COR.sem_acesso, "line-width": lw } });
      dren({ id: "dren-rede-2", type: "line", source: "dren-rede", "source-layer": "rede", filter: fr(2), layout: { "line-cap": "butt", visibility: "none" }, paint: { "line-color": DR.COR.nao_interligada, "line-width": lw, "line-dasharray": [2, 1.5] } });
      dren({ id: "dren-rede-dup", type: "line", source: "dren-rede", "source-layer": "rede", filter: ["==", ["get", "u"], 1], layout: { "line-cap": "butt", visibility: "none" }, paint: { "line-color": DR.COR.duplicado, "line-width": lw, "line-dasharray": [0.4, 1.6] } });
      var pt = function (id, fonte, camada, cor, r) { dren({ id: id, type: "circle", source: fonte, "source-layer": camada, filter: ["==", ["get", "u"], 0], layout: { visibility: "none" }, paint: { "circle-radius": r, "circle-color": cor, "circle-stroke-color": "#fff", "circle-stroke-width": 1 } }); };
      pt("dren-pocos", "dren-pocos", "pocos", DR.COR.poco, ["interpolate", ["linear"], ["zoom"], 15, 2, 18, 5]);
      pt("dren-bocas", "dren-bocas", "bocas", DR.COR.boca, ["interpolate", ["linear"], ["zoom"], 15, 2, 18, 5]);
      dren({ id: "dren-bombas", type: "circle", source: "dren-bombas", "source-layer": "bombas", layout: { visibility: "none" }, paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 14, 5, 18, 10], "circle-color": DR.COR.bomba, "circle-stroke-color": "#000", "circle-stroke-width": 2 } });
      dren({ id: "dren-pt-dup", type: "circle", source: "dren-pocos", "source-layer": "pocos", filter: ["==", ["get", "u"], 1], layout: { visibility: "none" }, paint: { "circle-radius": 4, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": DR.COR.duplicado, "circle-stroke-width": 1.5 } });
      [["rede", "line"], ["pocos", "circle"], ["bocas", "circle"], ["bombas", "circle"]].forEach(function (c) {
        dren({ id: "dren-sel-" + c[0], type: c[1], source: "dren-" + c[0], "source-layer": c[0], filter: ["==", ["get", "n"], -1], layout: { visibility: "none" },
               paint: c[1] === "line" ? { "line-color": "#000", "line-width": 7, "line-opacity": 0.55 } : { "circle-radius": 9, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#000", "circle-stroke-width": 3 } });
      });
      map.addLayer({ id: "f3-sel", type: "line", source: "f3", "source-layer": "trechos", filter: ["==", ["get", "n"], -1], layout: { "line-cap": "round" }, paint: { "line-color": "#000", "line-width": ["interpolate", ["linear"], ["zoom"], 13, 5, 16, 11], "line-opacity": 0.55 } });
    };
    m.visibilidade = function (nome, ligado) {
      CAMADAS[nome].ids.concat(nome === "escoamento_fase3" ? f3Camadas : []).forEach(function (id) { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", ligado ? "visible" : "none"); });
    };
    /* A cor dos trechos: uma camada por propriedade da grandeza escolhida (os 6 pacotes x limites, ou os 3 pacotes), todas com a cor definida uma vez
       e só uma opaca. Trocar de pacote ou de limite muda apenas a opacidade, que não reprocessa os tiles; mudar a expressão de cor reprocessava
       todos (medido: a nova cor levava ~7 s em vez de ~1 s no mapa 3D com WebGL por software). Trocar de grandeza recria o conjunto, uma vez. */
    var f3Camadas = [], f3Modo = null;
    var F3_LARGURA = ["interpolate", ["linear"], ["zoom"], 13, 1.6, 16, 5];
    m.f3_pintar = function (e) {
      var visivel = map.getLayoutProperty("f3-sem-dados", "visibility") !== "none";
      if (f3Modo !== e.modo) {
        f3Camadas.forEach(function (id) { if (map.getLayer(id)) map.removeLayer(id); });
        f3Camadas = e.props.map(function (p) {
          var id = "f3-p-" + p;
          map.addLayer({ id: id, type: "line", source: "f3", "source-layer": "trechos", filter: ["has", "c_m1_max"], layout: { "line-cap": "round", "line-join": "round", visibility: visivel ? "visible" : "none" },
                         paint: { "line-color": e.expressoes[p], "line-opacity": 0, "line-width": F3_LARGURA } }, "f3-sem-dados");
          return id;
        });
        f3Modo = e.modo;
      }
      e.props.forEach(function (p) { map.setPaintProperty("f3-p-" + p, "line-opacity", p === e.prop ? 1 : 0); });
    };
    m.f3_camadas = function () { return f3Camadas.slice(); };
    /* Quais grupos da drenagem aparecem; só é chamado com a camada ligada (o botão da lista liga e desliga tudo). */
    var DREN_GRUPOS = { rede: ["dren-rede-halo", "dren-rede-0", "dren-rede-1", "dren-rede-2", "dren-rede-dup"], pocos: ["dren-pocos"], bocas: ["dren-bocas"], bombas: ["dren-bombas"] };
    m.dren_grupos = function (g) {
      Object.keys(DREN_GRUPOS).forEach(function (k) { DREN_GRUPOS[k].forEach(function (id) { map.setLayoutProperty(id, "visibility", g[k] ? "visible" : "none"); }); });
      map.setLayoutProperty("dren-pt-dup", "visibility", g.pocos ? "visible" : "none");
    };
    m.selecionar = function (s) {
      map.setFilter("f3-sel", ["==", ["get", "n"], s.f3 == null ? -1 : s.f3]);
      ["rede", "pocos", "bocas", "bombas"].forEach(function (c) { map.setFilter("dren-sel-" + c, ["==", ["get", "n"], s.dren && s.dren.camada === c ? s.dren.n : -1]); });
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
        if (map.getLayoutProperty("f3-sem-dados", "visibility") === "visible") {
          var f = map.queryRenderedFeatures(caixa, { layers: ["f3-casing"] });
          if (f.length) return cb({ tipo: "trecho_f3", props: f[0].properties });
        }
        if (map.getLayoutProperty("dren-rede-0", "visibility") === "visible" || map.getLayoutProperty("dren-pocos", "visibility") === "visible") {
          var ordem = [["bombas", "dren-bombas"], ["bocas", "dren-bocas"], ["pocos", "dren-pocos"], ["rede", "dren-rede-0"]];
          for (var i = 0; i < ordem.length; i++) {
            var camadas = ordem[i][0] === "rede" ? ["dren-rede-0", "dren-rede-1", "dren-rede-2", "dren-rede-dup"] : ordem[i][0] === "pocos" ? ["dren-pocos", "dren-pt-dup"] : [ordem[i][1]];
            var d = map.getLayoutProperty(camadas[0], "visibility") === "visible" ? map.queryRenderedFeatures(caixa, { layers: camadas }) : [];
            if (d.length) return cb({ tipo: "dren", camada: ordem[i][0], n: d[0].properties.n });
          }
        }
      });
      ["f3-casing"].forEach(function (l) {
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
