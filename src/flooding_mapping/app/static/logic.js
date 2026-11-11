/* Pure helpers of the state interface (no DOM, no network), testable with Node. */
(function (root) {
  "use strict";

  var CLASS_ORDER = ["baixo", "atencao", "alto"];
  var CLASS_LABEL = { baixo: "Baixo", atencao: "Atenção", alto: "Alto" };
  var CLASS_COLOR = { baixo: "#dfe7ec", atencao: "#f0a830", alto: "#b3202a" };
  var NO_DATA = "#9aa3a8";

  function esc(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function classColor(cls) { return CLASS_COLOR[cls] || NO_DATA; }

  /* Traffic (VDM, vehicles/day): a missing value is "no data", never "no traffic". */
  function vdmColor(vdm) {
    if (vdm == null || isNaN(vdm)) return "#b9bfc3";
    if (vdm >= 20000) return "#08306b";
    if (vdm >= 8000) return "#2171b5";
    if (vdm >= 2000) return "#6baed6";
    return "#c6dbef";
  }

  function indexByIbge(forecast) {
    var out = {};
    (forecast.municipios || []).forEach(function (m) { out[m.ibge] = m; });
    return out;
  }

  function classAt(muni, horizon) {
    if (!muni) return null;
    var day = (muni.dias || []).filter(function (d) { return d.horizonte_dias === horizon; })[0];
    return day ? day.classe : null;
  }

  /* "08/11/2026 17:42" in Brasilia time, from an ISO UTC instant. */
  function formatInstant(iso) {
    var d = new Date(iso);
    if (isNaN(d)) return "indisponível";
    return new Intl.DateTimeFormat("pt-BR", {
      timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit"
    }).format(d).replace(",", "");
  }

  function dayLabel(horizon, isoDate) {
    var names = ["Hoje", "Amanhã", "Depois de amanhã"];
    var p = isoDate.split("-");
    return names[horizon] + " (" + p[2] + "/" + p[1] + ")";
  }

  function blockageSpan(b) {
    if (b.km_fim != null && b.km_fim > b.km) return "km " + b.km + " a " + b.km_fim;
    return "km " + b.km;
  }

  function percent(p) {
    if (p == null) return "—";
    return p < 0.001 ? "<0,1%" : (p * 100).toFixed(p < 0.1 ? 1 : 0).replace(".", ",") + "%";
  }

  /* The four kinds of data are never mixed: each has its own word, class and border style. */
  var KINDS = {
    observado: { label: "Observado", cls: "k-observado", hint: "medido ou registrado" },
    previsto: { label: "Previsto", cls: "k-previsto", hint: "estimado a partir da previsão de chuva" },
    simulado: { label: "Simulado", cls: "k-simulado", hint: "efeito calculado em um cenário" },
    confirmado: { label: "Confirmado", cls: "k-confirmado", hint: "validado por operador com evidência" }
  };
  function kind(name) { return KINDS[name] || { label: "Sem classificação", cls: "k-nenhum", hint: "" }; }
  function kindBadge(name) {
    var k = kind(name);
    return "<span class='kind " + k.cls + "' title='" + esc(k.hint) + "'>" + esc(k.label) + "</span>";
  }

  /* "17:30" in Brasilia time from an ISO instant with offset. */
  function hhmm(iso) {
    var d = new Date(iso);
    if (isNaN(d)) return "—";
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
  }
  function weekdayHour(iso) {
    var d = new Date(iso);
    if (isNaN(d)) return "—";
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false })
      .format(d).replace(",", "");
  }
  function minutes(n) {
    if (n == null || isNaN(n)) return "—";
    n = Math.round(n);
    return n < 60 ? n + " min" : Math.floor(n / 60) + " h " + ("0" + (n % 60)).slice(-2);
  }
  function extraMinutes(n) {
    if (n == null || isNaN(n)) return "—";
    return n === 0 ? "mesmo tempo" : (n > 0 ? "+" : "−") + Math.abs(Math.round(n)) + " min";
  }
  function mm(v) { return v == null ? "—" : (Math.round(v * 10) / 10).toLocaleString("pt-BR") + " mm"; }
  function km(v) {
    if (v == null) return "—";
    if (v > 0 && v < 0.1) return "<0,1 km";   // a short stretch is not "0 km"
    return (Math.round(v * 10) / 10).toLocaleString("pt-BR") + " km";
  }

  /* Streets of a risk layer grouped by name: total length and the worst class. Unnamed streets stay apart. */
  function groupStreets(features) {
    var rank = { atencao: 1, alto: 2 }, by = {};
    features.forEach(function (f) {
      var p = f.properties, name = p.nome || "(via sem nome)";
      var g = by[name] || (by[name] = { nome: name, km: 0, classe: "atencao", n: 0, escore: 0 });
      g.km += p.km || 0; g.n += 1; g.escore = Math.max(g.escore, p.escore || 0);
      if ((rank[p.classe] || 0) > rank[g.classe]) g.classe = p.classe;
    });
    return Object.keys(by).map(function (k) { by[k].km = Math.round(by[k].km * 100) / 100; return by[k]; })
      .sort(function (a, b) { return (rank[b.classe] - rank[a.classe]) || (b.escore - a.escore) || (b.km - a.km); });
  }

  /* Bar heights (0..height) for a series; NaN/null become 0 and the maximum never shrinks below `floor`. */
  function barHeights(values, height, floor) {
    var top = Math.max.apply(null, values.map(function (v) { return v == null || isNaN(v) ? 0 : v; }).concat([floor || 0, 1e-9]));
    return values.map(function (v) { return v == null || isNaN(v) ? 0 : Math.round(height * v / top); });
  }

  /* Capabilities: one place decides what a region offers (config/territorios.yaml, published as territorios.json).
     A missing capability is shown as unavailable with its reason, never as a zero. */
  var STATE_LABEL = { disponivel: "Dados disponíveis", parcial: "Cobertura parcial", indisponivel: "Dados indisponíveis" };
  var CLASS_LABEL_COV = { disponivel: "Dados disponíveis", parcial: "Cobertura parcial", insuficiente: "Dados insuficientes" };
  function capStatus(cap, online) {
    if (!cap) return { ativa: false, rotulo: "Dados indisponíveis", nota: "Capacidade não descrita.", estado: "indisponivel" };
    if (cap.estado === "indisponivel") return { ativa: false, rotulo: STATE_LABEL.indisponivel, nota: cap.motivo || "", estado: cap.estado };
    if (cap.requer_servidor && !online) return { ativa: false, rotulo: "Requer o servidor de análise", nota: "Esta funcionalidade só existe com o servidor ativo (python -m flooding_mapping.servidor).", estado: cap.estado };
    return { ativa: true, rotulo: STATE_LABEL[cap.estado] || cap.estado, nota: cap.nota || "", estado: cap.estado };
  }
  /* Map layers a territory may show: those named by a capability that is active. Returns {layerName: status}. */
  function layersOf(territory, online) {
    var out = {};
    Object.keys(territory.capacidades).forEach(function (name) {
      var cap = territory.capacidades[name], st = capStatus(cap, online);
      (cap.camadas || []).forEach(function (layer) { out[layer] = Object.assign({ capacidade: name }, st); });
    });
    return out;
  }
  function pct(f) { return f == null || isNaN(f) ? "—" : Math.round(f * 100) + "%"; }
  function classBadge(c) {
    var ok = { disponivel: 1, parcial: 1, insuficiente: 1 }[c];
    return "<span class='cls cls-" + (ok ? c : "nenhum") + "'>" + esc(CLASS_LABEL_COV[c] || "Sem classificação") + "</span>";
  }
  var DIM_NAME = { malha: "Malha rodoviária DAER", indice_fisico: "Índice físico", vdm: "Tráfego (VDM)", ocorrencias_s2id: "Registros hidrológicos do S2iD" };
  /* Each dimension in words and with a mark that does not depend on colour. */
  function dimensions(dims) {
    return "<ul class='dims'>" + Object.keys(dims).map(function (k) {
      return "<li class='" + (dims[k] ? "sim" : "nao") + "'><span aria-hidden='true'>" + (dims[k] ? "✓" : "✗") + "</span> " + esc(DIM_NAME[k] || k) + " <span class='small'>" + (dims[k] ? "atende o mínimo" : "abaixo do mínimo ou ausente") + "</span></li>";
    }).join("") + "</ul>";
  }
  /* Accent- and case-insensitive key, to match names written differently by two sources. */
  function norm(s) { return String(s == null ? "" : s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim(); }
  /* "#poa/mobilidade" -> {territorio, aba}; a bare tab ("#mapa") keeps the default territory; anything else falls back. */
  function parseHash(hash, tabs, territories, fallback) {
    var parts = String(hash || "").replace(/^#/, "").split("/"), t = territories.indexOf(parts[0]) >= 0 ? parts.shift() : fallback;
    return { territorio: t, aba: tabs.indexOf(parts[0]) >= 0 ? parts[0] : null };
  }

  /* Fragments of one street along a route read as one line: total length, first to last passage, worst class.
     Streets keep the order in which the route meets them. */
  function groupStretches(stretches) {
    var order = [], by = {};
    stretches.forEach(function (t) {
      var key = t.nome || "(via sem nome)", g = by[key];
      if (!g) { g = by[key] = { nome: key, km: 0, classe: "atencao", inicio: t.inicio, fim: t.fim, n: 0, ocorrencia: false }; order.push(key); }
      g.km += t.km; g.n += 1; g.ocorrencia = g.ocorrencia || !!t.ocorrencia;
      if (t.classe === "alto") g.classe = "alto";
      if (t.inicio < g.inicio) g.inicio = t.inicio;
      if (t.fim > g.fim) g.fim = t.fim;
    });
    return order.map(function (k) { by[k].km = Math.round(by[k].km * 1000) / 1000; return by[k]; });
  }

  /* Municipal estimate (72 h): municipalities ordered by class then by rain, and the count per class for one day.
     A municipality without an estimate is left out of the ranking, never counted as "low". */
  var CLASS_RANK = { alto: 2, atencao: 1, baixo: 0 };
  function rankMunicipalities(forecast, n) {
    var rows = [];
    (forecast.municipios || []).forEach(function (m) {
      var worst = null;
      (m.dias || []).forEach(function (d) { if (!worst || CLASS_RANK[d.classe] > CLASS_RANK[worst.classe] || (d.classe === worst.classe && d.chuva_3d_mm > worst.chuva_3d_mm)) worst = d; });
      if (worst && CLASS_RANK[worst.classe] > 0) rows.push({ ibge: m.ibge, nome: m.nome, classe: worst.classe, data: worst.data, horizonte: worst.horizonte_dias, chuva_dia_mm: worst.chuva_dia_mm, chuva_3d_mm: worst.chuva_3d_mm });
    });
    rows.sort(function (a, b) { return (CLASS_RANK[b.classe] - CLASS_RANK[a.classe]) || (b.chuva_3d_mm - a.chuva_3d_mm); });
    return n ? rows.slice(0, n) : rows;
  }
  function countByClass(forecast, horizon) {
    var out = { baixo: 0, atencao: 0, alto: 0, sem_estimativa: (forecast.municipios_sem_dados || []).length, chuva_maxima_mm: 0, chuva_media_mm: 0 }, n = 0, soma = 0;
    (forecast.municipios || []).forEach(function (m) {
      var d = (m.dias || []).filter(function (x) { return x.horizonte_dias === horizon; })[0];
      if (!d) return;
      out[d.classe] += 1; n += 1; soma += d.chuva_dia_mm; out.chuva_maxima_mm = Math.max(out.chuva_maxima_mm, d.chuva_dia_mm);
    });
    out.chuva_media_mm = n ? Math.round(soma / n * 10) / 10 : 0;
    return out;
  }

  var ROUTE_STYLE = {
    habitual: { color: "#333f48", dash: null, label: "Rota habitual" },
    menor_exposicao: { color: "#1b7f5c", dash: null, label: "Menor exposição estimada" },
    alternativa: { color: "#1f6fb2", dash: "8 6", label: "Alternativa" }
  };

  var api = { KINDS: KINDS, kind: kind, kindBadge: kindBadge, hhmm: hhmm, weekdayHour: weekdayHour, minutes: minutes,
              extraMinutes: extraMinutes, mm: mm, km: km, groupStreets: groupStreets, barHeights: barHeights,
              ROUTE_STYLE: ROUTE_STYLE, groupStretches: groupStretches, rankMunicipalities: rankMunicipalities, countByClass: countByClass, STATE_LABEL: STATE_LABEL, CLASS_LABEL_COV: CLASS_LABEL_COV, capStatus: capStatus, layersOf: layersOf, pct: pct,
              classBadge: classBadge, dimensions: dimensions, norm: norm, parseHash: parseHash, CLASS_ORDER: CLASS_ORDER, CLASS_LABEL: CLASS_LABEL, esc: esc, classColor: classColor,
              vdmColor: vdmColor, indexByIbge: indexByIbge, classAt: classAt, formatInstant: formatInstant,
              dayLabel: dayLabel, blockageSpan: blockageSpan, percent: percent, NO_DATA: NO_DATA };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Logic = api;
})(typeof window !== "undefined" ? window : this);
