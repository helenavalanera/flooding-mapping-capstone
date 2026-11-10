/* Operational dashboard: six areas over the same API the mobility PWA uses. Every text from the API is escaped. */
(function () {
  "use strict";
  var Lg = window.Logic, L_ = window.L, map = window.FloodingMap;
  var state = { online: false, poa: false, hora: 0, layers: {}, mob: { pontos: {}, camadas: [] } };

  function el(id) { return document.getElementById(id); }
  function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || "GET", headers: {} };
    if (opts.body) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.body); }
    if (opts.credencial) init.headers.Authorization = "Bearer " + opts.credencial;
    return fetch("api/" + path, init).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok) throw new Error(d.erro || "HTTP " + r.status);
        return d;
      });
    });
  }
  function fail(node, e) { node.innerHTML = "<p class='aviso'>Não foi possível carregar: " + Lg.esc(e.message) + "</p>"; }
  function legendKinds() {
    return "<div class='kinds-legend'>" + ["observado", "previsto", "simulado", "confirmado"].map(function (k) {
      return Lg.kindBadge(k) + " <span class='small'>" + Lg.esc(Lg.kind(k).hint) + "</span>"; }).join(" · ") + "</div>";
  }

  /* ---------------------------------------------------------------- abas */
  var RENDER = { geral: geral, previsao: previsao, mobilidade: mobilidade, ocorrencias: ocorrencias, proveniencia: proveniencia };
  function show(name) {
    Array.prototype.forEach.call(document.querySelectorAll("#abas button"), function (b) { b.setAttribute("aria-selected", String(b.dataset.aba === name)); });
    ["geral", "mapa", "previsao", "mobilidade", "ocorrencias", "proveniencia"].forEach(function (n) { el("vista-" + n).hidden = n !== name; });
    if (history.replaceState) history.replaceState(null, "", "#" + name);
    if (name === "mapa") { setTimeout(function () { map.invalidateSize(); }, 0); return; }
    if (!state.online) {
      el("vista-" + name).innerHTML = "<p class='aviso'>O servidor de análise não está ativo neste endereço. Esta área precisa dele " +
        "(a versão publicada no GitHub Pages mostra só o mapa estadual). Rode <code>python -m flooding_mapping.servidor</code>.</p>";
      return;
    }
    RENDER[name]();
  }

  /* ---------------------------------------------------------------- visão geral */
  function geral() {
    var box = el("vista-geral");
    box.innerHTML = "<p class='muted'>Carregando…</p>";
    api("visao-geral").then(function (v) {
      var mx = v.maior_exposicao, c = v.ocorrencias_por_situacao;
      box.innerHTML = "<h2>Visão geral · Porto Alegre</h2>" + legendKinds() +
        (v.fonte_chuva.obsoleta ? "<p class='aviso'>A atualização da chuva falhou (" + Lg.esc(v.fonte_chuva.motivo_obsolescencia) + "): os valores abaixo são do último download válido.</p>" : "") +
        "<div class='cards'>" +
        "<div class='card'>" + Lg.kindBadge("previsto") + "<h2>Chuva nas próximas 24 h</h2><div class='big'>" + Lg.mm(v.chuva_proximas_24h_mm) + "</div>" +
        (v.pico_de_chuva ? "<div class='small'>pico às " + Lg.hhmm(v.pico_de_chuva.hora) + " (" + Lg.mm(v.pico_de_chuva.mm) + " em 1 h)</div>" : "") + "</div>" +
        "<div class='card'>" + Lg.kindBadge("previsto") + "<h2>Maior exposição estimada (48 h)</h2>" +
        (mx && (mx.km_alto || mx.km_atencao) ? "<div class='big'>" + Lg.weekdayHour(mx.hora) + "</div><div class='small'>" + Lg.km(mx.km_alto) + " em classe Alto · " + Lg.km(mx.km_atencao) + " em Atenção</div>"
          : "<div class='big'>—</div><div class='small'>nenhum trecho com risco estimado nas próximas 48 h</div>") + "</div>" +
        "<div class='card'>" + Lg.kindBadge("observado") + "<h2>Ocorrências reportadas</h2><div class='big'>" + c.reportada + "</div><div class='small'>relatos sem verificação</div></div>" +
        "<div class='card'>" + Lg.kindBadge("confirmado") + "<h2>Interdições confirmadas</h2><div class='big'>" + v.interdicoes_confirmadas_ativas + "</div><div class='small'>ativas · " + c.confirmada + " ocorrências confirmadas no total</div></div>" +
        "</div><h2>Indicativos de atenção</h2>" +
        (v.indicativos.length ? "<ul class='plain'>" + v.indicativos.map(function (i) {
          return "<li>" + Lg.kindBadge("previsto") + " " + Lg.esc(i.nivel === "alto" ? "Alto" : "Atenção") + " a partir de " + Lg.weekdayHour(i.hora) + ": " + Lg.km(i.km) + " (critério: " + Lg.esc(i.criterio) + ")</li>"; }).join("") + "</ul>"
          : "<p class='muted'>Sem indicativos: nenhum trecho atinge os critérios nas próximas 48 h.</p>") +
        "<p class='aviso'>" + Lg.esc(v.aviso) + " O risco por trecho é um baseline determinístico, sem validação contra alagamentos em vias.</p>" +
        "<p class='small'>Chuva: " + Lg.esc(v.fonte_chuva.fonte.replace("https://", "")) + ", emitida em " + Lg.esc(Lg.formatInstant(v.fonte_chuva.emitido_em_utc)) + ". Agora: " + Lg.hhmm(v.agora) + " (Brasília).</p>";
    }).catch(function (e) { fail(box, e); });
  }

  /* ---------------------------------------------------------------- previsão */
  /* One series per chart: solid bars were measured, hatched bars are forecast, both in the series colour. */
  function bars(rows, value, color, unit, nowIndex) {
    var w = 960, h = 130, n = rows.length, bw = w / n, hs = Lg.barHeights(rows.map(value), h - 24, unit.floor), pats = {};
    var body = "";
    rows.forEach(function (r, i) {
      var v = value(r), x = i * bw, c = color(r), prev = r.natureza === "previsto", id = "h" + c.replace("#", "");
      if (prev && !pats[id]) pats[id] = "<pattern id='" + id + "' width='6' height='6' patternUnits='userSpaceOnUse' patternTransform='rotate(45)'><rect width='6' height='6' fill='#fff'/><line x1='0' y1='0' x2='0' y2='6' stroke='" + c + "' stroke-width='3'/></pattern>";
      body += "<rect x='" + (x + 1) + "' y='" + (h - hs[i]) + "' width='" + Math.max(bw - 2, 1) + "' height='" + hs[i] + "' fill='" + (prev ? "url(#" + id + ")" : c) +
        "' stroke='" + c + "' stroke-width='1.5'" + (prev ? " stroke-dasharray='3 2'" : "") + "><title>" + Lg.esc(Lg.weekdayHour(r.hora)) + ": " + (v == null ? "sem estimativa" : Lg.esc(unit.fmt(v))) + " (" + Lg.esc(r.natureza) + ")</title></rect>";
      if (i % 6 === 0 && x < w - 50) body += "<text x='" + (x + 2) + "' y='" + (h + 13) + "'>" + Lg.esc(Lg.hhmm(r.hora)) + "</text>";
    });
    if (nowIndex > 0) body += "<line x1='" + nowIndex * bw + "' x2='" + nowIndex * bw + "' y1='0' y2='" + h + "' stroke='#333' stroke-dasharray='4 3'/><text x='" + (nowIndex * bw + 4) + "' y='10'>agora</text>";
    return "<svg class='chart' viewBox='0 0 " + w + " " + (h + 18) + "' role='img' aria-label='" + Lg.esc(unit.label) + "'><defs>" + Object.keys(pats).map(function (k) { return pats[k]; }).join("") + "</defs>" + body + "</svg>";
  }
  function previsao() {
    var box = el("vista-previsao");
    box.innerHTML = "<p class='muted'>Carregando…</p>";
    api("previsao?horas=48").then(function (p) {
      var rows = p.horas, now = rows.findIndex(function (r) { return r.natureza === "previsto"; }), pk = p.hora_de_maior_exposicao;
      var mmUnit = { label: "Chuva por hora (mm)", floor: 5, fmt: Lg.mm };
      box.innerHTML = "<h2>Previsão · evolução do risco estimado por trecho</h2>" + legendKinds() +
        "<p class='small'>Barras sólidas = horas até agora (" + Lg.kindBadge("observado") + "); tracejadas = horas à frente (" + Lg.kindBadge("previsto") + ").</p>" +
        "<h3>Chuva por hora</h3>" + bars(rows, function (r) { return r.chuva_hora_mm; }, function () { return "#1f6fb2"; }, mmUnit, now) +
        "<h3>Km de via em classe Alto</h3>" + bars(rows, function (r) { return r.km_alto; }, function () { return "#b3202a"; }, { label: "Km em classe Alto", floor: 1, fmt: Lg.km }, now) +
        "<h3>Km de via em classe Atenção</h3>" + bars(rows, function (r) { return r.km_atencao; }, function () { return "#c27a00"; }, { label: "Km em classe Atenção", floor: 1, fmt: Lg.km }, now) +
        (pk && (pk.km_alto || pk.km_atencao) ? "<p><b>Hora de maior exposição estimada:</b> " + Lg.weekdayHour(pk.hora) + " · " + Lg.km(pk.km_alto) + " em Alto, " + Lg.km(pk.km_atencao) + " em Atenção.</p>"
          : "<p>Nenhuma hora com trechos em Atenção ou Alto nas próximas 48 h.</p>") +
        "<p class='aviso'>" + Lg.esc(p.natureza) + ". Horas sem janela completa de chuva ficam sem estimativa (barra vazia), não em risco baixo.</p>" +
        "<details><summary>Metodologia e limites</summary><p>" + Lg.esc(p.metodo) + "</p><ul class='plain'>" + p.limites.map(function (l) { return "<li>" + Lg.esc(l) + "</li>"; }).join("") + "</ul></details>";
    }).catch(function (e) { fail(box, e); });
  }

  /* ---------------------------------------------------------------- mapa de Porto Alegre */
  var CLASS_STYLE = { atencao: { color: "#c27a00", weight: 4 }, alto: { color: "#b3202a", weight: 5 } };
  var timer = null;
  function loadRisk() {
    var h = Number(el("poa-hora").value);
    api("risco?h=" + h).then(function (r) {
      if (state.layers.risco) map.removeLayer(state.layers.risco);
      el("poa-hora-rotulo").textContent = h === 0 ? "agora" : "+" + h + " h (" + Lg.weekdayHour(r.hora) + ")";
      el("poa-hora-kind").innerHTML = Lg.kindBadge(r.natureza);
      if (r.sem_estimativa) { el("poa-resumo").textContent = "Sem estimativa para esta hora (janela de chuva incompleta)."; return; }
      var prev = r.natureza === "previsto";
      state.layers.risco = L_.geoJSON(r.geojson, {
        renderer: L_.canvas(),
        style: function (f) { var s = CLASS_STYLE[f.properties.classe]; return f.properties.interditado ? { color: "#000", weight: 7 } : { color: s.color, weight: s.weight, dashArray: prev ? "7 5" : null, opacity: 0.9 }; },
        onEachFeature: function (f, layer) {
          layer.bindTooltip(Lg.esc(f.properties.nome || "via sem nome") + " · " + (f.properties.classe === "alto" ? "Alto" : "Atenção") + " (" + r.natureza + ")", { sticky: true });
          layer.on("click", function () { segmento(f.properties.id); });
        } });
      if (el("l-poa-risco").checked) state.layers.risco.addTo(map);
      el("poa-resumo").textContent = r.total_atencao_ou_alto + " trechos em Atenção ou Alto" + (r.exibidos < r.total_atencao_ou_alto ? " (mostrando os " + r.exibidos + " de maior escore)" : "") +
        ". Fator de chuva " + (r.fator == null ? "—" : r.fator.toFixed(2).replace(".", ",")) + ".";
    }).catch(function (e) { el("poa-resumo").textContent = "Erro: " + e.message; });
  }
  function loadOccurrences() {
    api("ocorrencias").then(function (d) {
      ["occ", "int"].forEach(function (k) { if (state.layers[k]) map.removeLayer(state.layers[k]); });
      var ativos = d.ocorrencias.filter(function (o) { return o.situacao !== "descartada"; });
      state.layers.occ = L_.layerGroup(ativos.map(function (o) {
        var conf = o.situacao === "confirmada";
        return L_.circleMarker([o.lat, o.lon], { radius: conf ? 8 : 7, color: conf ? "#000" : "#1f6fb2", weight: conf ? 3 : 2, dashArray: conf ? null : "3 3", fillColor: conf ? "#1b2630" : "#fff", fillOpacity: conf ? 0.9 : 0.4 })
          .bindTooltip(Lg.esc(o.tipo) + " · " + Lg.esc(o.situacao) + " · confiabilidade " + Lg.esc(o.confiabilidade) + " · " + Lg.esc(o.fonte));
      }));
      state.layers.int = L_.layerGroup(ativos.filter(function (o) { return o.situacao === "confirmada" && o.impacto_circulacao === "interdicao"; }).map(function (o) {
        return L_.marker([o.lat, o.lon], { icon: L_.divIcon({ className: "", html: "<div class='x-int'>✕</div>", iconSize: [18, 18] }) }).bindTooltip("Interdição confirmada · " + Lg.esc(o.fonte));
      }));
      if (el("l-poa-occ").checked) state.layers.occ.addTo(map);
      if (el("l-poa-int").checked) state.layers.int.addTo(map);
    }).catch(function () {});
  }
  function bloco(titulo, kind, corpo) { return "<h3>" + Lg.esc(titulo) + " " + (kind ? Lg.kindBadge(kind) : "") + "</h3>" + corpo; }
  function segmento(id) {
    var box = el("detalhe-trecho");
    box.innerHTML = "<p class='muted'>Carregando trecho…</p>";
    api("trecho?id=" + encodeURIComponent(id)).then(function (t) {
      var f = t.caracteristicas_fisicas, impacto = t.impacto_simulado_do_fechamento, pk = t.hora_de_maior_exposicao;
      var barras = t.risco_por_hora.map(function (h) { return { hora: h.hora, natureza: h.natureza, v: h.escore, classe: h.classe }; });
      var chart = bars(barras, function (r) { return r.v; }, function (r) { return r.classe === "alto" ? "#b3202a" : (r.classe === "atencao" ? "#c27a00" : "#7c8b95"); },
        { label: "Escore de risco por hora", floor: 0.4, fmt: function (v) { return v.toFixed(2).replace(".", ","); } }, barras.findIndex(function (r) { return r.natureza === "previsto"; }));
      var simular = function (m, nome) {
        var i = impacto[m];
        return "<li>" + nome + ": " + (!i.na_rede ? "fora da rede deste modal" : (i.sem_alternativa_proxima ? "sem alternativa mapeada em " + i.raio_km + " km" : "desvio de " + Lg.minutes(i.desvio_s / 60) + " (+" + Lg.km(i.desvio_km) + ")")) + "</li>";
      };
      box.innerHTML = "<h3>" + Lg.esc(t.nome || "Via sem nome") + "</h3><p class='small'>" + Lg.esc(t.classe_via) + " · " + Math.round(t.comprimento_m) + " m" +
        (t.interditado ? " · " + Lg.kindBadge("confirmado") + " interditado" : "") + "</p>" +
        bloco("Risco por hora (24 h)", "previsto", chart + (pk ? "<p class='small'>Maior exposição: " + Lg.weekdayHour(pk.hora) + " (escore " + pk.escore.toFixed(2).replace(".", ",") + ", " + Lg.esc(pk.classe) + ").</p>" : "<p class='small'>Sem estimativa nas próximas 24 h.</p>")) +
        bloco("Terreno", "observado", "<p class='small'>Cota " + (f.elev == null ? "sem dado" : f.elev + " m") + " · relevo local " + (f.rel_elev_250 == null ? "—" : f.rel_elev_250 + " m") + " · declividade " + (f.slope == null ? "—" : f.slope + "°") +
          " · altura sobre a água " + (f.height_above_water == null ? "—" : f.height_above_water + " m") + ".<br>Índice físico: " + (f.percentil == null ? "<b>sem dado</b> (sem estimativa, não é risco baixo)" : "percentil " + Math.round(f.percentil) + " (relativo, não é probabilidade)") + ".</p>") +
        bloco("Ocorrências próximas", "observado", t.ocorrencias_proximas.length ? "<ul class='plain'>" + t.ocorrencias_proximas.map(function (o) {
          return "<li><span class='sit " + Lg.esc(o.situacao) + "'>" + Lg.esc(o.situacao) + "</span> · " + Lg.esc(o.tipo) + " · " + Lg.esc(o.fonte) + " · confiab. " + Lg.esc(o.confiabilidade) + "</li>"; }).join("") + "</ul>" : "<p class='small'>Nenhuma ocorrência ativa a 100 m.</p>") +
        bloco("Se este trecho fechasse", "simulado", "<ul class='plain'>" + simular("carro", "Carro") + simular("pe", "A pé") + "</ul>") +
        "<details><summary>Metodologia e limites</summary><p class='small'>" + Lg.esc(t.metodo) + "</p><ul class='plain'>" + t.limites.map(function (l) { return "<li>" + Lg.esc(l) + "</li>"; }).join("") + "</ul></details>";
    }).catch(function (e) { fail(box, e); });
  }
  function escopo(poa) {
    state.poa = poa;
    el("escopo-rs").setAttribute("aria-pressed", String(!poa)); el("escopo-poa").setAttribute("aria-pressed", String(poa));
    el("poa-opcoes").hidden = !poa;
    ["h-day", "h-layers"].forEach(function (id) { el(id).closest("section").hidden = poa; });
    ["l-risk", "l-block"].forEach(function (id) { var c = el(id); if (!c.disabled && c.checked === poa) { c.checked = !poa; c.dispatchEvent(new Event("change")); } });
    ["risco", "occ", "int"].forEach(function (k) { if (state.layers[k] && !poa) map.removeLayer(state.layers[k]); });
    if (poa) { map.setView([-30.03, -51.22], 12); loadRisk(); loadOccurrences(); }
    else map.setView([-30.0, -53.2], 6);
  }
  function iniciarMapa() {
    el("poa-controles").hidden = false;
    el("escopo-rs").addEventListener("click", function () { escopo(false); });
    el("escopo-poa").addEventListener("click", function () { escopo(true); });
    el("poa-hora").addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(loadRisk, 250); });
    [["l-poa-risco", "risco"], ["l-poa-occ", "occ"], ["l-poa-int", "int"]].forEach(function (p) {
      el(p[0]).addEventListener("change", function (e) { var l = state.layers[p[1]]; if (l) (e.target.checked ? l.addTo(map) : map.removeLayer(l)); });
    });
  }

  /* ---------------------------------------------------------------- mobilidade */
  var mobMap = null;
  function limparRotas() { state.mob.camadas.forEach(function (l) { mobMap.removeLayer(l); }); state.mob.camadas = []; }
  function marcar(tipo, latlng) {
    if (state.mob.pontos[tipo]) mobMap.removeLayer(state.mob.pontos[tipo]);
    state.mob.pontos[tipo] = L_.circleMarker(latlng, { radius: 9, color: "#fff", weight: 2, fillColor: tipo === "origem" ? "#1b7f5c" : "#b3202a", fillOpacity: 1 })
      .bindTooltip(tipo === "origem" ? "Origem" : "Destino", { permanent: true, direction: "top" }).addTo(mobMap);
  }
  function mobilidade() {
    var box = el("vista-mobilidade");
    var agora = new Date(Date.now() - new Date().getTimezoneOffset() * 60000 + 5 * 60000).toISOString().slice(0, 16);
    box.innerHTML = "<h2>Mobilidade · rotas e trechos potencialmente comprometidos</h2>" + legendKinds() +
      "<p class='small'>Clique no mapa para marcar a origem e depois o destino. As rotas comparam <b>tempo</b> e <b>exposição ao risco estimado</b> no horário de passagem de cada trecho; nenhuma rota é apresentada como segura.</p>" +
      "<div class='form-linha'><label>Marcar<select id='mob-marcar'><option value='origem'>Origem</option><option value='destino'>Destino</option></select></label>" +
      "<label>Modal<select id='mob-modal'><option value='carro'>Carro</option><option value='pe'>A pé</option></select></label>" +
      "<label>Saída<input type='datetime-local' id='mob-saida' value='" + agora + "'></label><button class='btn' id='mob-analisar'>Analisar rotas</button></div>" +
      "<div id='mapa-rotas' role='application' aria-label='Mapa para marcar origem e destino'></div><div id='mob-resultado' aria-live='polite'></div>" +
      "<h2>Vias potencialmente comprometidas</h2><div class='form-linha'><label>Horizonte<select id='mob-h'>" + [0, 3, 6, 12, 24, 36, 48].map(function (h) { return "<option value='" + h + "'>" + (h ? "+" + h + " h" : "agora") + "</option>"; }).join("") + "</select></label></div><div id='mob-vias'></div>";
    if (mobMap) mobMap.remove();
    state.mob.pontos = {}; state.mob.camadas = [];
    mobMap = L_.map("mapa-rotas").setView([-30.03, -51.22], 12);
    L_.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "&copy; colaboradores do OpenStreetMap" }).addTo(mobMap);
    mobMap.on("click", function (e) {
      var tipo = el("mob-marcar").value; marcar(tipo, e.latlng); state.mob[tipo] = { lon: e.latlng.lng, lat: e.latlng.lat };
      if (tipo === "origem") el("mob-marcar").value = "destino";
    });
    el("mob-analisar").addEventListener("click", analisar);
    el("mob-h").addEventListener("change", vias); vias();
  }
  function analisar() {
    var out = el("mob-resultado");
    if (!state.mob.origem || !state.mob.destino) { out.innerHTML = "<p class='aviso'>Marque a origem e o destino no mapa.</p>"; return; }
    out.innerHTML = "<p class='muted'>Calculando rotas…</p>";
    api("rotas", { method: "POST", body: { origem: state.mob.origem, destino: state.mob.destino, modal: el("mob-modal").value, saida: el("mob-saida").value } }).then(function (a) {
      limparRotas();
      Object.keys(a.rotas).reverse().forEach(function (n) {
        var st = Lg.ROUTE_STYLE[n], line = L_.polyline(a.rotas[n].coordenadas.map(function (c) { return [c[1], c[0]]; }), { color: st.color, weight: n === "habitual" ? 6 : 4, dashArray: st.dash, opacity: 0.9 }).addTo(mobMap);
        state.mob.camadas.push(line);
      });
      mobMap.fitBounds(state.mob.camadas[state.mob.camadas.length - 1].getBounds().pad(0.2));
      var linhas = a.comparacao.map(function (c) {
        var r = a.rotas[c.rota];
        return "<tr><td><span class='sw line' style='border-color:" + Lg.ROUTE_STYLE[c.rota].color + ";width:26px;display:inline-block'></span> " + Lg.esc(r.rotulo) + "</td><td>" + Lg.minutes(c.tempo_min) + "</td><td>" + Lg.extraMinutes(c.acrescimo_min) +
          "</td><td>" + Lg.esc(c.rotulo) + "</td><td>" + Lg.km(c.km_atencao_ou_alto) + "</td><td>" + (r.instante_do_pico ? Lg.hhmm(r.instante_do_pico) : "—") + "</td></tr>"; }).join("");
      out.innerHTML = "<div class='alerta " + Lg.esc(a.alerta.nivel) + "'><h3>" + Lg.esc(a.alerta.titulo) + " " + Lg.kindBadge("previsto") + "</h3><p>" + Lg.esc(a.alerta.texto) + "</p>" +
        (a.alerta.motivos.length ? "<ul class='plain'>" + a.alerta.motivos.map(function (m) { return "<li>" + Lg.esc(m) + "</li>"; }).join("") + "</ul>" : "") + "</div>" +
        "<div class='rolagem'><table><thead><tr><th>Rota</th><th>Tempo</th><th>Diferença</th><th>Exposição estimada</th><th>Km em Atenção/Alto</th><th>Pico</th></tr></thead><tbody>" + linhas + "</tbody></table></div>" +
        "<p class='small'>Chuva na janela da viagem: " + Lg.mm(a.meteo.total_na_janela_mm) + ". Interdições confirmadas consideradas: " + a.interdicoes_consideradas + ".</p>" +
        "<p><button class='btn sec' id='mob-explicar'>Explicar com mais contexto</button> <span id='mob-explicacao'></span></p>" +
        "<details><summary>Trechos de risco da rota habitual</summary><ul class='plain'>" + (a.rotas.habitual.trechos_de_risco.map(function (t) {
          return "<li>" + Lg.esc(t.nome || "via sem nome") + " · " + Lg.esc(t.classe) + " · " + Lg.km(t.km) + " · passagem " + Lg.hhmm(t.inicio) + "–" + Lg.hhmm(t.fim) + "</li>"; }).join("") || "<li>nenhum</li>") + "</ul></details>" +
        "<ul class='plain'>" + a.avisos.map(function (x) { return "<li>" + Lg.esc(x) + "</li>"; }).join("") + "</ul>";
      el("mob-explicar").addEventListener("click", function () {
        var alvo = el("mob-explicacao"); alvo.textContent = "consultando…";
        api("explicacao", { method: "POST", body: { analise_id: a.analise_id, contextualizar: true } }).then(function (e) {
          alvo.innerHTML = "<br>" + Lg.esc(e.texto) + " <span class='small'>(" + (e.origem === "deterministico" ? "texto padrão" + (e.motivo === "nao_configurado" ? ": provedor de linguagem não configurado" : "") : "contextualizado por provedor de linguagem externo, a partir de resumos agregados") + ")</span>";
        }).catch(function (x) { alvo.textContent = x.message; });
      });
    }).catch(function (e) { out.innerHTML = "<p class='aviso'>" + Lg.esc(e.message) + "</p>"; });
  }
  function vias() {
    var box = el("mob-vias");
    api("risco?h=" + el("mob-h").value).then(function (r) {
      var g = r.sem_estimativa ? [] : Lg.groupStreets(r.geojson.features).slice(0, 15);
      box.innerHTML = r.sem_estimativa ? "<p class='muted'>Sem estimativa para este horário.</p>" : (g.length ? "<p class='small'>" + Lg.kindBadge(r.natureza) + " Vias com trechos em Atenção ou Alto às " + Lg.weekdayHour(r.hora) + ":</p><div class='rolagem'><table><thead><tr><th>Via</th><th>Classe</th><th>Km</th><th>Trechos</th></tr></thead><tbody>" +
        g.map(function (x) { return "<tr><td>" + Lg.esc(x.nome) + "</td><td>" + (x.classe === "alto" ? "Alto" : "Atenção") + "</td><td>" + Lg.km(x.km) + "</td><td>" + x.n + "</td></tr>"; }).join("") + "</tbody></table></div>"
        : "<p class='muted'>Nenhuma via em Atenção ou Alto neste horário.</p>");
    }).catch(function (e) { fail(box, e); });
  }

  /* ---------------------------------------------------------------- ocorrências */
  function ocorrencias() {
    var box = el("vista-ocorrencias");
    box.innerHTML = "<p class='muted'>Carregando…</p>";
    api("ocorrencias").then(function (d) {
      var filtro = "<label>Situação <select id='oc-filtro'><option value=''>todas</option><option>reportada</option><option>confirmada</option><option>descartada</option></select></label>";
      var linhas = d.ocorrencias.map(function (o) {
        return "<tr data-sit='" + Lg.esc(o.situacao) + "'><td><span class='sit " + Lg.esc(o.situacao) + "'>" + Lg.esc(o.situacao) + "</span></td><td>" + Lg.esc(o.tipo) + "</td><td>" + Lg.esc(o.fonte) + "</td><td>" + Lg.esc(o.confiabilidade) +
          "</td><td>" + Lg.esc(o.impacto_circulacao) + "</td><td>" + Lg.esc(Lg.formatInstant(o.data_hora)) + "</td><td class='small'>" + Lg.esc(o.origem) + " · " + o.historico.length + " registro(s)</td>" +
          "<td>" + (o.situacao === "descartada" ? "" : "<button class='btn sec' data-id='" + Lg.esc(o.id) + "'>Revisar</button>") + "</td></tr>"; }).join("");
      box.innerHTML = "<h2>Ocorrências</h2>" + legendKinds() + "<p class='aviso'>" + Lg.esc(d.natureza) + ". Um relato nunca interdita uma via; só a confirmação por operador, com evidência escrita, o faz.</p>" +
        "<div class='form-linha'>" + filtro + "<span class='small'>" + d.total + " registro(s)</span></div>" +
        (d.total ? "<div class='rolagem'><table id='oc-tabela'><thead><tr><th>Situação</th><th>Tipo</th><th>Fonte</th><th>Confiabilidade</th><th>Impacto</th><th>Data/hora</th><th>Origem do registro</th><th></th></tr></thead><tbody>" + linhas + "</tbody></table></div>"
          : "<p class='muted'>Nenhuma ocorrência registrada.</p>") +
        "<div id='oc-revisao'></div>";
      el("oc-filtro").addEventListener("change", function (e) {
        Array.prototype.forEach.call(document.querySelectorAll("#oc-tabela tbody tr"), function (tr) { tr.hidden = e.target.value && tr.dataset.sit !== e.target.value; }); });
      Array.prototype.forEach.call(box.querySelectorAll("button[data-id]"), function (b) { b.addEventListener("click", function () { revisar(b.dataset.id); }); });
    }).catch(function (e) { fail(box, e); });
  }
  function revisar(id) {
    el("oc-revisao").innerHTML = "<div class='card'><h3>Revisar ocorrência (operador)</h3><div class='form-linha'><label>Nova situação<select id='rv-sit'><option value='confirmada'>Confirmar</option><option value='descartada'>Descartar</option></select></label>" +
      "<label>Confiabilidade<select id='rv-conf'><option value='alta'>alta</option><option value='media'>média</option><option value='baixa'>baixa</option></select></label>" +
      "<label>Credencial do operador<input type='password' id='rv-cred' autocomplete='off'></label></div><label>Evidência (mín. 10 caracteres)<br><textarea id='rv-ev' rows='3' cols='60' maxlength='280'></textarea></label>" +
      "<p><button class='btn' id='rv-ok'>Registrar</button> <span id='rv-msg' class='small'></span></p></div>";
    el("rv-ok").addEventListener("click", function () {
      api("ocorrencias/" + encodeURIComponent(id), { method: "POST", credencial: el("rv-cred").value, body: { situacao: el("rv-sit").value, confiabilidade: el("rv-conf").value, evidencia: el("rv-ev").value } })
        .then(function () { ocorrencias(); }).catch(function (e) { el("rv-msg").textContent = e.message; });
    });
  }

  /* ---------------------------------------------------------------- proveniência */
  function proveniencia() {
    var box = el("vista-proveniencia");
    box.innerHTML = "<p class='muted'>Carregando…</p>";
    api("proveniencia").then(function (p) {
      box.innerHTML = "<h2>Proveniência dos dados</h2>" + legendKinds() +
        "<div class='rolagem'><table><thead><tr><th>Fonte</th><th>Uso</th><th>Atualização / licença</th></tr></thead><tbody>" + p.fontes.map(function (f) {
          return "<tr><td>" + Lg.esc(f.nome) + "</td><td>" + Lg.esc(f.uso) + "</td><td class='small'>" + Lg.esc(f.emitido_em_utc ? "emitido em " + Lg.formatInstant(f.emitido_em_utc) + (f.obsoleta ? " (defasado)" : "") : (f.licenca || (f.criterio ? "situações: " + f.criterio.join(", ") : "—"))) + "</td></tr>"; }).join("") + "</tbody></table></div>" +
        "<h3>Cobertura</h3><p>" + p.cobertura.segmentos.toLocaleString("pt-BR") + " segmentos de via; <b>" + (p.cobertura.fracao_com_indice_fisico * 100).toFixed(0) + "%</b> têm índice físico. O restante fica <b>sem estimativa</b> (não é risco baixo).</p>" +
        "<h3>Natureza dos dados</h3><ul class='plain'>" + Object.keys(p.natureza).map(function (k) { return "<li>" + Lg.kindBadge(k) + " " + Lg.esc(p.natureza[k]) + "</li>"; }).join("") + "</ul>" +
        "<h3>Metodologia</h3><p>" + Lg.esc(p.metodo) + "</p><h3>Limitações</h3><ul class='plain'>" + p.limites.map(function (l) { return "<li>" + Lg.esc(l) + "</li>"; }).join("") + "</ul>" +
        "<h3>Parâmetros provisórios</h3><p class='small'>" + p.parametros_provisorios.map(Lg.esc).join(", ") + " (em <code>config/analysis.yaml</code>, sem ajuste a ocorrências).</p>" +
        "<p class='small'>Rede: " + Lg.esc(JSON.stringify(p.dados_da_rede)) + "</p>";
    }).catch(function (e) { fail(box, e); });
  }

  /* ---------------------------------------------------------------- início */
  Array.prototype.forEach.call(document.querySelectorAll("#abas button"), function (b) { b.addEventListener("click", function () { show(b.dataset.aba); }); });
  api("saude").then(function (s) {
    state.online = s.status === "ok" || s.status === "degradado";
    if (state.online) iniciarMapa();
    var alvo = (location.hash || "").slice(1);
    show(["geral", "mapa", "previsao", "mobilidade", "ocorrencias", "proveniencia"].indexOf(alvo) >= 0 ? alvo : (state.online ? "geral" : "mapa"));
  }).catch(function () { show("mapa"); });
})();
