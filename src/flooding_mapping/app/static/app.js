/* State flood-risk interface: a static page that only reads the published JSON files. */
(function () {
  "use strict";
  var L_ = window.L, Lg = window.Logic;
  var DATA = "data/";
  var state = { day: 0, forecast: null, byIbge: {}, blockages: null, occurrences: null, impact: null };
  var layers = {};

  function getJson(name) {
    return fetch(name, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error(name + ": HTTP " + r.status);
      return r.json();
    });
  }
  function el(id) { return document.getElementById(id); }
  function banner(text) { var b = el("banner"); b.textContent = text; b.hidden = false; }

  var map = L_.map("map", { zoomControl: true }).setView([-30.0, -53.2], 6);
  L_.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 12, attribution: "&copy; colaboradores do OpenStreetMap" }).addTo(map);

  function riskStyle(feature) {
    var m = state.byIbge[feature.properties.ibge];
    var cls = Lg.classAt(m, state.day);
    return { fillColor: Lg.classColor(cls), fillOpacity: cls ? 0.78 : 0.5, color: cls ? "#52626d" : "#6b7780",
             weight: 0.6, dashArray: cls ? null : "3 3" };
  }

  function showMunicipality(ibge, name) {
    var m = state.byIbge[ibge];
    var records = ((state.occurrences || {}).registros || []).filter(function (r) { return r.ibge === ibge; });
    var impact = ((state.impact || {}).municipios || {})[ibge];
    var html = "<h2>" + Lg.esc(name) + "</h2>";
    if (!m) {
      html += "<p><b>Sem estimativa.</b> Faltam dados de chuva completos para este município; ele não recebeu uma estimativa.</p>";
    } else {
      html += "<p class='small'>População: " + Lg.esc(m.populacao.toLocaleString("pt-BR")) + "</p>" +
        "<table><tr><th>Dia</th><th>Chuva no dia</th><th>Chuva em 3 dias</th><th>Risco</th></tr>" +
        m.dias.map(function (d) {
          return "<tr><td>" + Lg.esc(Lg.dayLabel(d.horizonte_dias, d.data)) + "</td><td>" + d.chuva_dia_mm.toFixed(0) + " mm</td><td>" +
            d.chuva_3d_mm.toFixed(0) + " mm</td><td><span class='tag' style='background:" + Lg.classColor(d.classe) + (d.classe === "alto" ? ";color:#fff" : "") + "'>" +
            Lg.esc(Lg.CLASS_LABEL[d.classe]) + "</span><div class='small'>prob. relativa " + Lg.percent(d.probabilidade) + "</div></td></tr>";
        }).join("") + "</table><p class='small'>Estimativa do modelo, a partir da chuva prevista. Não é uma ocorrência.</p>";
    }
    if (records.length) {
      html += "<h2>Registros recentes (observado)</h2><ul class='plain'>" + records.slice(0, 6).map(function (r) {
        return "<li>" + Lg.esc(r.data) + ": " + Lg.esc(r.tipo) + " (" + Lg.esc(r.status) + ")</li>"; }).join("") + "</ul>";
    }
    if (impact) {
      html += "<h2>Malha rodoviária (simulação)</h2><p class='small'>" + impact.km_rede.toLocaleString("pt-BR") + " km mapeados; VDM em " +
        impact.km_com_vdm.toLocaleString("pt-BR") + " km (o restante é <b>sem dado</b>, não tráfego zero). " +
        (impact.trecho_critico ? "Trecho mais crítico: " + Lg.esc(impact.trecho_critico) + "." : "Sem trechos-ponte mapeados.") + "</p>";
    }
    el("detail").innerHTML = html;
  }

  function buildRisk(geo) {
    layers.risk = L_.geoJSON(geo, {
      style: riskStyle,
      onEachFeature: function (f, layer) {
        layer.on("click", function () { showMunicipality(f.properties.ibge, f.properties.nome); });
        layer.bindTooltip(Lg.esc(f.properties.nome), { sticky: true });
      }
    });
    layers.occurrences = L_.geoJSON(geo, {
      filter: function (f) { return ((state.occurrences || {}).registros || []).some(function (r) { return r.ibge === f.properties.ibge; }); },
      style: { fill: false, color: "#5b3a8c", weight: 2.4 }, interactive: false });
  }

  function buildRoads(geo) {
    layers.roads = L_.geoJSON(geo, {
      style: function (f) { return { color: Lg.vdmColor(f.properties.vdm), weight: 1.8, opacity: 0.9 }; },
      onEachFeature: function (f, layer) {
        var p = f.properties;
        layer.bindTooltip(Lg.esc(p.nome) + " · " + (p.vdm == null ? "VDM sem dado" : "VDM " + Math.round(p.vdm).toLocaleString("pt-BR") + " veíc./dia"), { sticky: true });
      } });
    var top = {};
    var imp = state.impact || {};
    ["ranking_pontes_populacao_isolada", "ranking_veiculos_km_dia_com_vdm"].forEach(function (k) {
      (imp[k] || []).forEach(function (r) { top[r.codigo_sre] = true; }); });
    layers.critical = L_.geoJSON(geo, {
      filter: function (f) { return top[f.properties.codigo_sre]; },
      style: { color: "#7b2d8e", weight: 4.5, opacity: 0.95 },
      onEachFeature: function (f, layer) {
        var p = f.properties;
        layer.bindTooltip(Lg.esc(p.nome) + " (" + Lg.esc(p.codigo_sre) + ") · fechamento simulado" +
          (p.ponte && p.pop_isolada ? " isola ~" + Math.round(p.pop_isolada).toLocaleString("pt-BR") + " pessoas na malha mapeada" : ""), { sticky: true });
      } });
  }

  function buildBlockages(data) {
    layers.blockages = L_.layerGroup((data.bloqueios || []).filter(function (b) { return b.lat != null; }).map(function (b) {
      var c = b.casamento || {};
      var m = L_.circleMarker([b.lat, b.lng], { radius: 7, color: "#fff", weight: 2, fillColor: b.tipo === "total" ? "#b3202a" : "#e07a1f", fillOpacity: 1 });
      m.bindPopup("<b>" + Lg.esc(b.rodovia) + "</b> · " + Lg.esc(Lg.blockageSpan(b)) + "<br>" + Lg.esc(b.municipio) +
        "<br>" + (b.tipo === "total" ? "Totalmente interrompido" : "Parcial") + (b.climatico ? " · causa climática" : "") +
        "<br><span class='small'>" + Lg.esc(b.informacoes || "") + "</span><br><span class='small'>Observado (CPRv BM), desde " +
        Lg.esc(Lg.formatInstant(b.desde)) + ". Casamento com a malha: " + Lg.esc(c.status || "sem casamento") +
        (c.codigo_sre ? " (" + Lg.esc(c.codigo_sre) + ")" : "") + (b.impacto ? ". Simulação: " + (b.impacto.ponte ? "fechamento isolaria ~" + Math.round(b.impacto.pop_isolada).toLocaleString("pt-BR") + " pessoas na malha mapeada" : "desvio de " + (b.impacto.desvio_km == null ? "n/d" : b.impacto.desvio_km.toFixed(0) + " km")) : "") + "</span>");
      return m;
    }));
  }

  function setDay(h) {
    state.day = h;
    Array.prototype.forEach.call(el("days").children, function (b) { b.setAttribute("aria-checked", String(Number(b.dataset.h) === h)); });
    if (layers.risk) layers.risk.setStyle(riskStyle);
  }

  function buildControls(f) {
    var days = (f.municipios[0] || { dias: [] }).dias;
    el("days").innerHTML = "";
    days.forEach(function (d) {
      var b = document.createElement("button");
      b.type = "button"; b.setAttribute("role", "radio"); b.dataset.h = d.horizonte_dias;
      b.textContent = Lg.dayLabel(d.horizonte_dias, d.data);
      b.addEventListener("click", function () { setDay(d.horizonte_dias); });
      el("days").appendChild(b);
    });
    setDay(0);
    var legend = Lg.CLASS_ORDER.map(function (c) {
      return "<li><span class='sw' style='background:" + Lg.classColor(c) + "'></span><b>" + Lg.CLASS_LABEL[c] + "</b> · " + Lg.esc(f.classes[c]) + "</li>"; }).join("") +
      "<li><span class='sw' style='background:" + Lg.NO_DATA + ";border-style:dashed'></span><b>Sem estimativa</b> · dados de chuva incompletos (" + f.municipios_sem_dados.length + ")</li>" +
      "<li><span class='sw' style='background:#b3202a;border-radius:50%'></span>Bloqueio total ativo (observado)</li>" +
      "<li><span class='sw' style='background:#e07a1f;border-radius:50%'></span>Bloqueio parcial ativo (observado)</li>" +
      "<li><span class='sw' style='border:2px solid #5b3a8c;background:none'></span>Registro S2iD recente (observado)</li>" +
      "<li><span class='sw line' style='border-color:#2171b5'></span>Rodovia: tom mais escuro = mais tráfego (VDM); cinza = sem dado</li>" +
      "<li><span class='sw line' style='border-color:#7b2d8e'></span>Trecho crítico na simulação</li>";
    el("legend").innerHTML = legend;
  }

  function describeModel(f) {
    var m = f.modelo, t = m.desempenho_teste_2025_em_diante, o = t.orcamento_2pct;
    var validated = m.estado.indexOf("validado") === 0;
    var badge = el("status-badge"); badge.textContent = validated ? "validado frente aos baselines" : "experimental"; badge.className = "badge" + (validated ? " ok" : "");
    el("model").innerHTML = "<h2>Modelo</h2><p class='small'><b>" + Lg.esc(m.versao) + "</b> (" + Lg.esc(m.familia) + ")<br>Treinado com dados de " +
      Lg.esc(m.treinado_desde) + " a " + Lg.esc(m.treinado_ate) + ".<br><b>Estado:</b> " + Lg.esc(m.estado) + ".</p>" +
      "<p class='small'>No teste (2025 em diante, nunca usado para ajustar): com 2% dos dias em alerta, o modelo detecta " +
      Math.round(o.recall_eventos * 100) + "% dos eventos, com precisão de " + (o.precisao * 100).toFixed(1).replace(".", ",") +
      "% (negativos não rotulados: é um piso). PR-AUC " + t.pr_auc.toFixed(4).replace(".", ",") + " contra prevalência " + t.prevalencia.toFixed(4).replace(".", ",") + ".</p>";
    el("limits").innerHTML = "<h2>Limites</h2><ul class='plain'>" + f.avisos.map(function (a) { return "<li>" + Lg.esc(a) + "</li>"; }).join("") + "</ul>" +
      "<p class='small'>Chuva: " + Lg.esc(f.fonte_chuva.fonte.replace("https://", "")) + ", emitida em " + Lg.esc(Lg.formatInstant(f.fonte_chuva.emitido_em_utc)) + ".</p>";
    el("updated").textContent = "atualizado em " + Lg.formatInstant(f.gerado_em_utc) + " (Brasília) · emitido para " + f.emitido_para.split("-").reverse().join("/");
  }

  function toggle(id, layer) {
    el(id).addEventListener("change", function (e) { if (!layer()) return; (e.target.checked ? layer().addTo(map) : map.removeLayer(layer())); });
  }

  Promise.all([getJson("previsao_72h.json"), getJson("bloqueios.json").catch(function () { return null; }),
               getJson(DATA + "ocorrencias.json").catch(function () { return null; }),
               getJson(DATA + "impacto_rs.json").catch(function () { return null; }),
               getJson(DATA + "municipios.geojson"), getJson(DATA + "rodovias.geojson")])
    .then(function (r) {
      state.forecast = r[0]; state.blockages = r[1]; state.occurrences = r[2]; state.impact = r[3];
      state.byIbge = Lg.indexByIbge(state.forecast);
      buildControls(state.forecast); describeModel(state.forecast);
      buildRisk(r[4]); buildRoads(r[5]);
      layers.risk.addTo(map);
      if (state.blockages) { buildBlockages(state.blockages); layers.blockages.addTo(map); }
      else { banner("Bloqueios ativos indisponíveis neste momento (a fonte não respondeu)."); el("l-block").disabled = true; el("l-block").checked = false; }
      toggle("l-risk", function () { return layers.risk; }); toggle("l-block", function () { return layers.blockages; });
      toggle("l-occ", function () { return layers.occurrences; }); toggle("l-road", function () { return layers.roads; });
      toggle("l-crit", function () { return layers.critical; });
      var params = new URLSearchParams(window.location.search);   // deep links: ?dia=1&municipio=4314902
      var day = parseInt(params.get("dia"), 10);
      if (day >= 0 && day <= 2) setDay(day);
      layers.risk.eachLayer(function (l) {
        if (l.feature.properties.ibge === params.get("municipio")) showMunicipality(l.feature.properties.ibge, l.feature.properties.nome);
      });
      setTimeout(function () { map.invalidateSize(); map.fitBounds(layers.risk.getBounds()); }, 0);
    })
    .catch(function (e) { banner("Não foi possível carregar os dados da estimativa: " + e.message); });
})();
