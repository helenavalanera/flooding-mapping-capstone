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

  var api = { CLASS_ORDER: CLASS_ORDER, CLASS_LABEL: CLASS_LABEL, esc: esc, classColor: classColor,
              vdmColor: vdmColor, indexByIbge: indexByIbge, classAt: classAt, formatInstant: formatInstant,
              dayLabel: dayLabel, blockageSpan: blockageSpan, percent: percent, NO_DATA: NO_DATA };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Logic = api;
})(typeof window !== "undefined" ? window : this);
