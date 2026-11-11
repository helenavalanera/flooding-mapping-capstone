/* On-device data of the PWA: favourite places, habitual trips and the location consent.
   Nothing here is sent anywhere: the server only ever receives the coordinates of one analysis.
   Pure functions over a plain state object, so the rules can be tested without a browser. */
(function (root) {
  "use strict";
  var KEY = "fm-pwa-v1", MAX_PLACES = 20, MAX_TRIPS = 10, RS = { lon: [-58, -48], lat: [-34, -27] };

  function empty() { return { consentimento: false, lugares: [], trajetos: [] }; }
  function uid() { return Math.random().toString(36).slice(2, 10); }
  function text(v, max) { return String(v == null ? "" : v).replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, max); }
  function inRS(lon, lat) {
    return isFinite(lon) && isFinite(lat) && lon >= RS.lon[0] && lon <= RS.lon[1] && lat >= RS.lat[0] && lat <= RS.lat[1];
  }

  /* Whatever comes out of storage is untrusted: keep only well-formed entries. */
  function sanitize(d) {
    var s = empty();
    if (!d || typeof d !== "object") return s;
    s.consentimento = d.consentimento === true;
    (Array.isArray(d.lugares) ? d.lugares : []).slice(0, MAX_PLACES).forEach(function (p) {
      if (p && typeof p.id === "string" && text(p.nome, 40) && inRS(+p.lon, +p.lat)) s.lugares.push({ id: text(p.id, 12), nome: text(p.nome, 40), lon: +p.lon, lat: +p.lat });
    });
    var ids = s.lugares.map(function (p) { return p.id; });
    (Array.isArray(d.trajetos) ? d.trajetos : []).slice(0, MAX_TRIPS).forEach(function (t) {
      if (t && t.deId !== t.paraId && ids.indexOf(t.deId) >= 0 && ids.indexOf(t.paraId) >= 0 && /^([01]\d|2[0-3]):[0-5]\d$/.test(t.horario || "") && (t.modal === "carro" || t.modal === "pe"))
        s.trajetos.push({ id: text(t.id, 12) || uid(), nome: text(t.nome, 40) || "Trajeto", deId: t.deId, paraId: t.paraId, modal: t.modal, horario: t.horario });
    });
    return s;
  }
  function load(storage) {
    try { var raw = storage.getItem(KEY); return raw ? sanitize(JSON.parse(raw)) : empty(); } catch (e) { return empty(); }
  }
  function save(storage, state) {
    try { storage.setItem(KEY, JSON.stringify(state)); return true; } catch (e) { return false; }
  }
  function wipe(storage) {
    try { storage.removeItem(KEY); } catch (e) { /* storage blocked: nothing was kept anyway */ }
    return empty();
  }

  function addPlace(state, nome, lon, lat) {
    nome = text(nome, 40);
    if (!nome) return { state: state, erro: "Dê um nome ao lugar." };
    if (!inRS(+lon, +lat)) return { state: state, erro: "Localização fora do Rio Grande do Sul." };
    if (state.lugares.length >= MAX_PLACES) return { state: state, erro: "Limite de " + MAX_PLACES + " lugares." };
    if (state.lugares.some(function (p) { return p.nome.toLowerCase() === nome.toLowerCase(); })) return { state: state, erro: "Já existe um lugar com esse nome." };
    var lugares = state.lugares.concat([{ id: uid(), nome: nome, lon: +(+lon).toFixed(5), lat: +(+lat).toFixed(5) }]);
    return { state: Object.assign({}, state, { lugares: lugares }) };
  }
  /* Removing a place removes the trips that use it, so nothing refers to data that is gone. */
  function removePlace(state, id) {
    return Object.assign({}, state, {
      lugares: state.lugares.filter(function (p) { return p.id !== id; }),
      trajetos: state.trajetos.filter(function (t) { return t.deId !== id && t.paraId !== id; })
    });
  }
  function addTrip(state, nome, deId, paraId, modal, horario) {
    var ids = state.lugares.map(function (p) { return p.id; });
    if (deId === paraId || ids.indexOf(deId) < 0 || ids.indexOf(paraId) < 0) return { state: state, erro: "Escolha dois lugares diferentes." };
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(horario || "")) return { state: state, erro: "Informe o horário habitual." };
    if (state.trajetos.length >= MAX_TRIPS) return { state: state, erro: "Limite de " + MAX_TRIPS + " trajetos." };
    var t = { id: uid(), nome: text(nome, 40) || "Trajeto", deId: deId, paraId: paraId, modal: modal === "pe" ? "pe" : "carro", horario: horario };
    return { state: Object.assign({}, state, { trajetos: state.trajetos.concat([t]) }) };
  }
  function removeTrip(state, id) { return Object.assign({}, state, { trajetos: state.trajetos.filter(function (t) { return t.id !== id; }) }); }
  function setConsent(state, value) { return Object.assign({}, state, { consentimento: value === true }); }

  /* The next time "HH:MM" happens: today if it is still ahead (or within 10 minutes), otherwise tomorrow. */
  function nextDeparture(horario, now) {
    var p = horario.split(":"), d = new Date(now.getTime());
    d.setHours(+p[0], +p[1], 0, 0);
    if (d.getTime() < now.getTime() - 10 * 60000) d.setDate(d.getDate() + 1);
    return d;
  }
  /* "2026-11-09T17:30" in the device's local time, the format of <input type="datetime-local">. */
  function localField(date) {
    var z = function (n) { return ("0" + n).slice(-2); };
    return date.getFullYear() + "-" + z(date.getMonth() + 1) + "-" + z(date.getDate()) + "T" + z(date.getHours()) + ":" + z(date.getMinutes());
  }

  var api = { KEY: KEY, MAX_PLACES: MAX_PLACES, empty: empty, sanitize: sanitize, load: load, save: save, wipe: wipe, addPlace: addPlace,
              removePlace: removePlace, addTrip: addTrip, removeTrip: removeTrip, setConsent: setConsent, nextDeparture: nextDeparture, localField: localField };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PwaDados = api;
})(typeof window !== "undefined" ? window : this);
