/* Preventive-mobility PWA. Same API and rules as the dashboard; nothing is computed here.
   Privacy: favourite places live only on this device; the server gets the coordinates of one analysis, to
   compute it, and the analysis is deleted when a new one starts or the page closes. Location is asked once,
   in the foreground, after explicit consent. Every text that comes from the API is escaped. */
(function () {
  "use strict";
  var Lg = window.Logic, D = window.PwaDados, L_ = window.L;
  // The PWA lives in /pwa/, one level below the API. A front end hosted elsewhere sets the absolute address (ending in "/") in the meta tag.
  var BASE = (document.querySelector("meta[name=api-base]") || {}).content || "../";
  var store = (function () { try { return window.localStorage; } catch (e) { return { getItem: function () { return null; }, setItem: function () { throw e; }, removeItem: function () {} }; } })();
  var estado = D.load(store);
  var ui = { tela: "planejar", origem: null, destino: null, modal: "carro", analise: null, selecionada: "habitual", modo: null, pendente: null,
             mapa: null, rotas: [], pontos: {}, rascunho: {}, servidor: null };

  function el(id) { return document.getElementById(id); }
  function esc(t) { return Lg.esc(t); }
  function persist() { if (!D.save(store, estado)) aviso("Não foi possível guardar neste aparelho (armazenamento bloqueado). O que você cadastrar vale só até fechar o app."); }
  function aviso(texto) { var a = el("aviso"); a.textContent = texto || ""; a.hidden = !texto; }
  function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || "GET", headers: {}, keepalive: !!opts.keepalive };
    if (opts.body) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.body); }
    return fetch(BASE + "api/" + path, init).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) { if (!r.ok) throw new Error(d.erro || "HTTP " + r.status); return d; });
    });
  }
  function lugar(id) { return estado.lugares.filter(function (p) { return p.id === id; })[0]; }

  /* ---------------------------------------------------------------- mapa e localização */
  function iniciarMapa() {
    ui.mapa = L_.map("mapa", { zoomControl: true }).setView([-30.03, -51.22], 12);
    L_.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "&copy; colaboradores do OpenStreetMap" }).addTo(ui.mapa);
    ui.mapa.on("click", function (e) {
      if (!ui.modo) return;
      var modo = ui.modo, p = { lon: e.latlng.lng, lat: e.latlng.lat };
      ui.modo = null; el("dica-mapa").hidden = true;
      ui.pendente = null;
      if (modo === "origem" || modo === "destino") { ui[modo] = { nome: "Ponto no mapa", lon: p.lon, lat: p.lat }; marcar(modo, p); render(); }
      else if (modo === "lugar" || modo === "relato") { ui.rascunho[modo] = p; marcar(modo, p); render(); }
    });
  }
  function marcar(tipo, p) {
    if (ui.pontos[tipo]) ui.mapa.removeLayer(ui.pontos[tipo]);
    var cor = { origem: "#1b7f5c", destino: "#b3202a", lugar: "#0b5d8f", relato: "#c27a00" }[tipo];
    ui.pontos[tipo] = L_.circleMarker([p.lat, p.lon], { radius: 9, color: "#fff", weight: 2, fillColor: cor, fillOpacity: 1 }).addTo(ui.mapa);
  }
  function escolherNoMapa(modo, texto) { ui.modo = modo; var d = el("dica-mapa"); d.textContent = texto; d.hidden = false; el("mapa").scrollIntoView({ behavior: "smooth", block: "nearest" }); }

  function consentir() {
    if (estado.consentimento) return Promise.resolve(true);
    return new Promise(function (resolve) {
      var dlg = el("consentimento");
      if (!dlg.showModal) { resolve(window.confirm("Usar sua localização uma vez, com o app aberto, sem guardá-la no servidor?")); return; }
      dlg.addEventListener("close", function fim() { dlg.removeEventListener("close", fim); resolve(dlg.returnValue === "sim"); });
      dlg.showModal();
    }).then(function (ok) { if (ok) { estado = D.setConsent(estado, true); persist(); } return ok; });
  }
  /* One position, foreground only: no watchPosition, nothing kept. */
  function minhaLocalizacao() {
    return consentir().then(function (ok) {
      if (!ok) throw new Error("Sem permissão para usar a localização.");
      return new Promise(function (resolve, reject) {
        if (!navigator.geolocation) { reject(new Error("Este aparelho não oferece localização.")); return; }
        navigator.geolocation.getCurrentPosition(function (pos) { resolve({ lon: pos.coords.longitude, lat: pos.coords.latitude }); },
          function (e) { reject(new Error(e.code === 1 ? "Permissão de localização negada no aparelho." : "Não foi possível obter a localização agora.")); },
          { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 });
      });
    });
  }

  /* ---------------------------------------------------------------- telas */
  var TELAS = { planejar: planejar, lugares: lugares, relatar: relatar, privacidade: privacidade };
  function render() { TELAS[ui.tela](); }
  function ir(tela) {
    ui.tela = tela; ui.modo = null; el("dica-mapa").hidden = true;
    Array.prototype.forEach.call(document.querySelectorAll("#abas button"), function (b) { if (b.dataset.tela === tela) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
    render(); el("tela").focus({ preventScroll: true });
  }
  function opcoesLugares(sel) { return estado.lugares.map(function (p) { return "<option value='" + esc(p.id) + "'" + (p.id === sel ? " selected" : "") + ">" + esc(p.nome) + "</option>"; }).join(""); }

  function planejar() {
    var t = el("tela"), agora = D.localField(new Date(Date.now() + 5 * 60000));
    var o = ui.origem && ui.origem.id ? ui.origem.id : (ui.origem ? "__ponto" : ""), d = ui.destino && ui.destino.id ? ui.destino.id : (ui.destino ? "__ponto" : "");
    t.innerHTML =
      (estado.trajetos.length ? "<h2>Trajetos habituais</h2><div class='chips'>" + estado.trajetos.map(function (j) {
        return "<button class='chip' data-traj='" + esc(j.id) + "'>" + esc(j.nome) + " · " + esc(j.horario) + "</button>"; }).join("") + "</div>" : "") +
      "<h2>Seu deslocamento</h2>" +
      "<label for='sel-o'>Origem</label><select id='sel-o'><option value=''>Escolha…</option><option value='__gps'>Minha localização</option>" + opcoesLugares(o) +
        (ui.origem && !ui.origem.id ? "<option value='__ponto' selected>" + esc(ui.origem.nome) + "</option>" : "") + "<option value='__mapa'>Escolher no mapa…</option></select>" +
      "<label for='sel-d'>Destino</label><select id='sel-d'><option value=''>Escolha…</option>" + opcoesLugares(d) +
        (ui.destino && !ui.destino.id ? "<option value='__ponto' selected>" + esc(ui.destino.nome) + "</option>" : "") + "<option value='__mapa'>Escolher no mapa…</option></select>" +
      "<div class='linha'><div><label for='sel-m'>Modal</label><select id='sel-m'><option value='carro'" + (ui.modal === "carro" ? " selected" : "") + ">Carro</option><option value='pe'" + (ui.modal === "pe" ? " selected" : "") + ">A pé</option></select></div>" +
      "<div><label for='in-saida'>Saída</label><input type='datetime-local' id='in-saida' value='" + esc(ui.saida || agora) + "'></div></div>" +
      "<button class='btn block' id='analisar'>Analisar deslocamento</button><div id='resultado' aria-live='polite'></div>" + (ui.analise ? "" : "");
    Array.prototype.forEach.call(t.querySelectorAll("[data-traj]"), function (b) { b.addEventListener("click", function () { usarTrajeto(b.dataset.traj); }); });
    el("sel-o").addEventListener("change", function (e) { escolher("origem", e.target.value); });
    el("sel-d").addEventListener("change", function (e) { escolher("destino", e.target.value); });
    el("sel-m").addEventListener("change", function (e) { ui.modal = e.target.value; });
    el("in-saida").addEventListener("change", function (e) { ui.saida = e.target.value; });
    el("analisar").addEventListener("click", analisar);
    if (ui.analise) mostrar(ui.analise);
  }
  function escolher(tipo, valor) {
    if (valor === "__gps") { minhaLocalizacao().then(function (p) { ui[tipo] = { nome: "Minha localização", lon: p.lon, lat: p.lat }; marcar(tipo, p); ui.mapa.setView([p.lat, p.lon], 14); render(); })
      .catch(function (e) { aviso(e.message); ui[tipo] = null; render(); }); return; }
    if (valor === "__mapa") { escolherNoMapa(tipo, "Toque no mapa para marcar o " + tipo + "."); return; }
    if (valor === "__ponto" || valor === "") { if (!valor) ui[tipo] = null; return; }
    var p = lugar(valor); ui[tipo] = p ? { id: p.id, nome: p.nome, lon: p.lon, lat: p.lat } : null; if (p) marcar(tipo, p);
  }
  function usarTrajeto(id) {
    var j = estado.trajetos.filter(function (x) { return x.id === id; })[0]; if (!j) return;
    var de = lugar(j.deId), para = lugar(j.paraId); if (!de || !para) return;
    ui.origem = { id: de.id, nome: de.nome, lon: de.lon, lat: de.lat }; ui.destino = { id: para.id, nome: para.nome, lon: para.lon, lat: para.lat };
    ui.modal = j.modal; ui.saida = D.localField(D.nextDeparture(j.horario, new Date()));
    marcar("origem", de); marcar("destino", para); render(); analisar();
  }

  function liberarAnalise() {
    if (ui.analise && ui.analise.analise_id) api("analises/" + encodeURIComponent(ui.analise.analise_id), { method: "DELETE", keepalive: true }).catch(function () {});
    ui.analise = null;
  }
  function analisar() {
    var out = el("resultado");
    if (!ui.origem || !ui.destino) { out.innerHTML = "<p class='aviso'>Escolha a origem e o destino.</p>"; return; }
    aviso(""); liberarAnalise();
    out.innerHTML = "<p class='small'>Calculando rotas… pode levar alguns segundos.</p>"; el("analisar").disabled = true;
    api("rotas", { method: "POST", body: { origem: { lon: ui.origem.lon, lat: ui.origem.lat }, destino: { lon: ui.destino.lon, lat: ui.destino.lat }, modal: ui.modal, saida: ui.saida } })
      .then(function (a) { ui.analise = a; ui.selecionada = "habitual"; mostrar(a); })
      .catch(function (e) { out.innerHTML = "<div class='card'><b>Não foi possível analisar.</b><p>" + esc(e.message) + "</p>" + (/Failed to fetch|NetworkError|Load failed/.test(e.message) ? "<p class='small'>Sem conexão com o servidor: a análise precisa dele.</p>" : "") + "</div>"; })
      .then(function () { var b = el("analisar"); if (b) b.disabled = false; });
  }

  function mostrar(a) {
    var out = el("resultado"), nomes = ["habitual", "menor_exposicao", "alternativa"].filter(function (n) { return a.rotas[n]; });
    var numero = 0, titulos = {}; nomes.forEach(function (n) { titulos[n] = n === "habitual" ? "Rota habitual" : "Alternativa " + (++numero); });
    var nivel = a.alerta.nivel, selo = { alto: "Alta exposição estimada", atencao: "Atenção", sem_risco_estimado: "Sem exposição relevante" }[nivel] || "Atenção";
    var horas = a.meteo.horas, altura = Lg.barHeights(horas.map(function (h) { return h.mm; }), 64, 5);
    var cards = nomes.map(function (n) {
      var c = a.comparacao.filter(function (x) { return x.rota === n; })[0], r = a.rotas[n];
      return "<div class='card" + (n === ui.selecionada ? " sel" : "") + "' data-rota='" + n + "' tabindex='0' role='button' aria-pressed='" + (n === ui.selecionada) + "'>" +
        "<div class='cabeca'><b>" + esc(titulos[n]) + "</b><span class='selo " + (c.rotulo === "menor exposição estimada" && nomes.length > 1 ? "menor" : "neutro") + "'>" + esc(c.rotulo) + "</span></div>" +
        "<div class='tempo'>" + Lg.minutes(c.tempo_min) + "</div>" +
        "<div class='small'>" + (n === "habitual" ? "menor tempo" : Lg.extraMinutes(c.acrescimo_min) + " · exposição estimada " + (c.reducao_exposicao_pct > 0 ? c.reducao_exposicao_pct + "% menor" : "semelhante")) + " · " + Lg.km(r.distancia_km) + "</div>" +
        (r.trechos_de_risco.length ? "<div class='small'>Trechos de risco: " + esc(r.trechos_de_risco.slice(0, 2).map(function (t) { return (t.nome || "via sem nome") + " (" + Lg.hhmm(t.inicio) + ")"; }).join(", ")) + (r.trechos_de_risco.length > 2 ? "…" : "") + "</div>" : "") + "</div>";
    }).join("");
    out.innerHTML =
      "<div class='card'><div class='cabeca'><b>Seu deslocamento</b><span class='selo " + esc(nivel) + "'>" + esc(selo) + "</span></div>" +
      "<p class='small'>Saída prevista: " + Lg.hhmm(a.saida) + " · " + (a.modal === "carro" ? "Carro" : "A pé") + " · " + (a.meteo.total_na_janela_mm >= 1 ? "Chuva prevista (" + Lg.mm(a.meteo.total_na_janela_mm) + ")" : "Sem chuva relevante no período") + "</p>" +
      "<div class='chuva' role='img' aria-label='Chuva prevista nas próximas horas'>" + horas.map(function (h, i) { return "<span class='" + (h.natureza === "previsto" ? "prev" : "") + "' style='height:" + Math.max(altura[i], 2) + "px' title='" + esc(Lg.hhmm(h.hora)) + ": " + esc(Lg.mm(h.mm)) + " (" + esc(h.natureza) + ")'></span>"; }).join("") + "</div>" +
      "<div class='horas'><span>" + esc(Lg.hhmm(horas[0].hora)) + "</span><span>" + esc(Lg.hhmm(horas[horas.length - 1].hora)) + "</span></div>" +
      "<p class='small'>Barras tracejadas: previsão. Barras cheias: já ocorrido.</p></div>" +
      "<div class='alerta " + esc(nivel) + "'><b>" + esc(a.alerta.titulo) + "</b><p>" + esc(a.alerta.texto) + "</p>" +
      (a.alerta.motivos.length ? "<p class='small'>Por que você recebeu este alerta:</p><ul>" + a.alerta.motivos.map(function (m) { return "<li>" + esc(m) + "</li>"; }).join("") + "</ul>" : "") + "</div>" +
      cards + "<p><button class='btn sec block' id='explicar'>Explicar com mais contexto</button></p><div id='explicacao' class='small' aria-live='polite'></div>" +
      "<ul class='small'>" + a.avisos.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>";
    Array.prototype.forEach.call(out.querySelectorAll("[data-rota]"), function (c) {
      var escolhe = function () { ui.selecionada = c.dataset.rota; mostrar(a); };
      c.addEventListener("click", escolhe); c.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); escolhe(); } });
    });
    el("explicar").addEventListener("click", function () { explicar(a); });
    desenhar(a);
  }
  function desenhar(a) {
    ui.rotas.forEach(function (l) { ui.mapa.removeLayer(l); }); ui.rotas = [];
    ["alternativa", "menor_exposicao", "habitual"].forEach(function (n) {
      if (!a.rotas[n]) return;
      var st = Lg.ROUTE_STYLE[n], sel = n === ui.selecionada;
      ui.rotas.push(L_.polyline(a.rotas[n].coordenadas.map(function (c) { return [c[1], c[0]]; }), { color: st.color, weight: sel ? 7 : 3, dashArray: st.dash, opacity: sel ? 0.95 : 0.55 }).addTo(ui.mapa));
    });
    var sel = a.rotas[ui.selecionada]; if (sel) ui.mapa.fitBounds(L_.polyline(sel.coordenadas.map(function (c) { return [c[1], c[0]]; })).getBounds().pad(0.15));
  }
  function explicar(a) {
    var alvo = el("explicacao"); alvo.textContent = "Consultando…";
    api("explicacao", { method: "POST", body: { analise_id: a.analise_id, contextualizar: true } }).then(function (e) {
      alvo.innerHTML = "<p>" + esc(e.texto) + "</p><p>" + (e.origem === "deterministico"
        ? "Texto padrão" + (e.motivo === "nao_configurado" ? " (contextualização indisponível neste servidor)." : e.motivo && e.motivo !== "nao_solicitado" ? " (a contextualização não respondeu agora)." : ".")
        : "Explicação contextualizada por um serviço de linguagem externo, a partir de resumos agregados (tempos, trechos de risco e horários), sem sua origem, destino ou localização.") + "</p>";
    }).catch(function (e) { alvo.textContent = e.message; });
  }

  function lugares() {
    var t = el("tela"), r = ui.rascunho.lugar;
    t.innerHTML = "<h2>Lugares frequentes</h2><p class='small'>Ficam só neste aparelho. Não são enviados ao servidor.</p>" +
      (estado.lugares.length ? estado.lugares.map(function (p) { return "<div class='item'><span>" + esc(p.nome) + "</span><button class='chip' data-del-lugar='" + esc(p.id) + "'>Remover</button></div>"; }).join("") : "<p class='small'>Nenhum lugar cadastrado.</p>") +
      "<h3>Novo lugar</h3><label for='nome-lugar'>Nome (casa, trabalho…)</label><input id='nome-lugar' maxlength='40' placeholder='Casa' value='" + esc(ui.rascunho.nome || "") + "'>" +
      "<div class='linha'><button class='btn sec' id='lugar-gps'>Usar minha localização</button><button class='btn sec' id='lugar-mapa'>Escolher no mapa</button></div>" +
      "<p class='small' id='lugar-ponto'>" + (r ? "Ponto marcado." : "Nenhum ponto marcado.") + "</p><button class='btn block' id='lugar-salvar'>Salvar lugar</button><p class='small' id='lugar-msg'></p>" +
      "<h3>Trajeto habitual</h3>" + (estado.lugares.length >= 2 ?
        "<label for='tj-de'>De</label><select id='tj-de'>" + opcoesLugares() + "</select><label for='tj-para'>Para</label><select id='tj-para'>" + opcoesLugares(estado.lugares[1].id) + "</select>" +
        "<div class='linha'><div><label for='tj-modal'>Modal</label><select id='tj-modal'><option value='carro'>Carro</option><option value='pe'>A pé</option></select></div><div><label for='tj-hora'>Horário habitual</label><input type='time' id='tj-hora' value='07:30'></div></div>" +
        "<button class='btn block' id='tj-salvar'>Salvar trajeto</button><p class='small' id='tj-msg'></p>" : "<p class='small'>Cadastre dois lugares para criar um trajeto habitual.</p>") +
      (estado.trajetos.length ? estado.trajetos.map(function (j) { return "<div class='item'><span>" + esc(j.nome) + " · " + esc(j.horario) + " · " + (j.modal === "carro" ? "carro" : "a pé") + "</span><button class='chip' data-del-traj='" + esc(j.id) + "'>Remover</button></div>"; }).join("") : "");
    Array.prototype.forEach.call(t.querySelectorAll("[data-del-lugar]"), function (b) { b.addEventListener("click", function () { estado = D.removePlace(estado, b.dataset.delLugar); persist(); lugares(); }); });
    Array.prototype.forEach.call(t.querySelectorAll("[data-del-traj]"), function (b) { b.addEventListener("click", function () { estado = D.removeTrip(estado, b.dataset.delTraj); persist(); lugares(); }); });
    el("nome-lugar").addEventListener("input", function (e) { ui.rascunho.nome = e.target.value; });
    el("lugar-gps").addEventListener("click", function () { minhaLocalizacao().then(function (p) { ui.rascunho.lugar = p; marcar("lugar", p); ui.mapa.setView([p.lat, p.lon], 15); el("lugar-ponto").textContent = "Ponto marcado (sua localização)."; })
      .catch(function (e) { el("lugar-msg").textContent = e.message; }); });
    el("lugar-mapa").addEventListener("click", function () { escolherNoMapa("lugar", "Toque no mapa para marcar o lugar."); });
    el("lugar-salvar").addEventListener("click", function () {
      var p = ui.rascunho.lugar; if (!p) { el("lugar-msg").textContent = "Marque o ponto no mapa ou use sua localização."; return; }
      var res = D.addPlace(estado, el("nome-lugar").value, p.lon, p.lat); if (res.erro) { el("lugar-msg").textContent = res.erro; return; }
      estado = res.state; ui.rascunho.lugar = null; ui.rascunho.nome = ""; if (ui.pontos.lugar) { ui.mapa.removeLayer(ui.pontos.lugar); delete ui.pontos.lugar; } persist(); lugares();
    });
    var salvarTraj = el("tj-salvar");
    if (salvarTraj) salvarTraj.addEventListener("click", function () {
      var de = el("tj-de").value, para = el("tj-para").value, nomeDe = lugar(de), nomePara = lugar(para);
      var res = D.addTrip(estado, (nomeDe ? nomeDe.nome : "") + " → " + (nomePara ? nomePara.nome : ""), de, para, el("tj-modal").value, el("tj-hora").value);
      if (res.erro) { el("tj-msg").textContent = res.erro; return; }
      estado = res.state; persist(); lugares();
    });
  }

  function relatar() {
    var t = el("tela"), r = ui.rascunho.relato;
    t.innerHTML = "<h2>Relatar um problema na via</h2><p class='small'>Seu relato entra como <b>reportado</b>, sem verificação, e <b>não interdita</b> nenhuma via. Só uma confirmação por um operador, com evidência, interdita.</p>" +
      "<label for='rel-texto'>O que está acontecendo? (até 600 caracteres)</label><textarea id='rel-texto' maxlength='600' placeholder='Ex.: rua alagada, carros parados'>" + esc(ui.rascunho.texto || "") + "</textarea>" +
      "<div class='linha'><button class='btn sec' id='rel-gps'>Usar minha localização</button><button class='btn sec' id='rel-mapa'>Escolher no mapa</button></div>" +
      "<p class='small' id='rel-ponto'>" + (r ? "Ponto marcado." : "Nenhum ponto marcado.") + "</p><button class='btn block' id='rel-enviar'>Enviar relato</button><p id='rel-msg' class='small' aria-live='polite'></p>" +
      "<p class='small'>" + (ui.servidor && ui.servidor.provedor_de_linguagem ? "O texto do relato é enviado a um serviço de linguagem externo para ser organizado em campos; não inclua dados pessoais." : "O texto fica no servidor deste projeto, sem identificação sua. Não inclua dados pessoais.") + "</p>";
    el("rel-texto").addEventListener("input", function (e) { ui.rascunho.texto = e.target.value; });
    el("rel-gps").addEventListener("click", function () { minhaLocalizacao().then(function (p) { ui.rascunho.relato = p; marcar("relato", p); ui.mapa.setView([p.lat, p.lon], 16); el("rel-ponto").textContent = "Ponto marcado (sua localização)."; })
      .catch(function (e) { el("rel-msg").textContent = e.message; }); });
    el("rel-mapa").addEventListener("click", function () { escolherNoMapa("relato", "Toque no mapa onde está o problema."); });
    el("rel-enviar").addEventListener("click", function () {
      var p = ui.rascunho.relato, msg = el("rel-msg");
      if (!p) { msg.textContent = "Marque o local no mapa ou use sua localização."; return; }
      if (!el("rel-texto").value.trim()) { msg.textContent = "Descreva o problema."; return; }
      msg.textContent = "Enviando…";
      api("relatos", { method: "POST", body: { texto: el("rel-texto").value, lon: p.lon, lat: p.lat } }).then(function (d) {
        msg.textContent = d.mensagem; ui.rascunho.relato = null; ui.rascunho.texto = ""; el("rel-texto").value = ""; el("rel-ponto").textContent = "Nenhum ponto marcado.";
      }).catch(function (e) { msg.textContent = e.message; });
    });
  }

  function privacidade() {
    el("tela").innerHTML = "<h2>Privacidade</h2><div class='card'><h3>O que fica no seu aparelho</h3><p class='small'>Seus lugares e trajetos habituais e a escolha sobre usar a localização. Nada disso vai para o servidor.</p></div>" +
      "<div class='card'><h3>O que vai ao servidor</h3><ul><li>Ao analisar um deslocamento: as coordenadas da origem e do destino, o modal e a hora de saída, só para calcular. A análise some da memória do servidor quando você começa outra, fecha o app ou em 30 minutos. Não há registro delas em log.</li>" +
      "<li>Ao enviar um relato: o texto e o ponto, sem identificação sua. Os relatos são apagados após 90 dias.</li></ul></div>" +
      "<div class='card'><h3>Localização</h3><p class='small'>Pedimos uma vez, com o app aberto, e só depois do seu consentimento. Não acompanhamos você em segundo plano.</p><p class='small'>Consentimento atual: <b>" + (estado.consentimento ? "dado" : "não dado") + "</b></p>" +
      (estado.consentimento ? "<button class='btn sec' id='revogar'>Revogar consentimento</button>" : "") + "</div>" +
      "<div class='card'><h3>Apagar meus dados</h3><p class='small'>Remove lugares, trajetos e consentimento deste aparelho e apaga a análise em andamento.</p><button class='btn' id='apagar'>Apagar tudo</button><p id='apagado' class='small' aria-live='polite'></p></div>" +
      "<div class='card'><h3>Sobre as estimativas</h3><p class='small'>O risco por trecho é um baseline determinístico, sem validação contra alagamentos em vias. Mostra exposição estimada, nunca segurança. Não substitui os alertas oficiais da Defesa Civil.</p></div>";
    var rev = el("revogar"); if (rev) rev.addEventListener("click", function () { estado = D.setConsent(estado, false); persist(); privacidade(); });
    el("apagar").addEventListener("click", function () {
      liberarAnalise(); estado = D.wipe(store); ui.origem = ui.destino = null; ui.rascunho = {};
      ["origem", "destino", "lugar", "relato"].forEach(function (k) { if (ui.pontos[k]) { ui.mapa.removeLayer(ui.pontos[k]); delete ui.pontos[k]; } });
      ui.rotas.forEach(function (l) { ui.mapa.removeLayer(l); }); ui.rotas = [];
      el("apagado").textContent = "Dados apagados deste aparelho.";
    });
  }

  /* ---------------------------------------------------------------- início */
  Array.prototype.forEach.call(document.querySelectorAll("#abas button"), function (b) { b.addEventListener("click", function () { ir(b.dataset.tela); }); });
  window.addEventListener("pagehide", liberarAnalise);
  iniciarMapa();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(function () {});
  api("saude").then(function (s) { ui.servidor = s; if (s.status === "degradado") aviso("Os dados de chuva não estão disponíveis agora; as análises podem falhar."); })
    .catch(function () { aviso("Sem conexão com o servidor de análise. Seus lugares continuam aqui; a análise de rotas precisa de conexão."); });
  ir("planejar");
})();
