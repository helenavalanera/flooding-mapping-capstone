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
  function km(v) { return v == null ? "—" : (Math.round(v * 10) / 10).toLocaleString("pt-BR") + " km"; }

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

  var ROUTE_STYLE = {
    habitual: { color: "#333f48", dash: null, label: "Rota habitual" },
    menor_exposicao: { color: "#1b7f5c", dash: null, label: "Menor exposição estimada" },
    alternativa: { color: "#1f6fb2", dash: "8 6", label: "Alternativa" }
  };

  var api = { KINDS: KINDS, kind: kind, kindBadge: kindBadge, hhmm: hhmm, weekdayHour: weekdayHour, minutes: minutes,
              extraMinutes: extraMinutes, mm: mm, km: km, groupStreets: groupStreets, barHeights: barHeights,
              ROUTE_STYLE: ROUTE_STYLE, CLASS_ORDER: CLASS_ORDER, CLASS_LABEL: CLASS_LABEL, esc: esc, classColor: classColor,
              vdmColor: vdmColor, indexByIbge: indexByIbge, classAt: classAt, formatInstant: formatInstant,
              dayLabel: dayLabel, blockageSpan: blockageSpan, percent: percent, NO_DATA: NO_DATA };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Logic = api;
})(typeof window !== "undefined" ? window : this);
