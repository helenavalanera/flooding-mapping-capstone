/* Service worker: caches the app shell so it opens offline. It never stores API answers, because they
   describe places and times of a person, and an old risk estimate must not be shown as current. */
var VERSAO = "fm-pwa-v1";
var CASCA = ["./", "index.html", "pwa.css", "pwa.js", "dados.js", "../logic.js", "manifest.webmanifest", "icon-192.png", "icon-512.png"];
var EXTERNOS = ["https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js", "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSAO).then(function (c) {
    return c.addAll(CASCA).then(function () {   // the map library comes from a CDN: kept as an opaque copy so the shell opens offline
      return Promise.all(EXTERNOS.map(function (u) { return fetch(u, { mode: "no-cors" }).then(function (r) { return c.put(u, r); }).catch(function () {}); }));
    });
  }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (ks) { return Promise.all(ks.filter(function (k) { return k !== VERSAO; }).map(function (k) { return caches.delete(k); })); })
    .then(function () { return self.clients.claim(); }));
});
self.addEventListener("fetch", function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.pathname.indexOf("/api/") >= 0) return;          // the network decides; nothing is kept
  if (url.hostname.indexOf("tile.openstreetmap.org") >= 0) return;                  // map tiles: browser cache only
  e.respondWith(fetch(req).then(function (r) {                                      // network first so updates arrive
    if (r.ok || (r.type === "opaque" && url.hostname === "cdnjs.cloudflare.com")) { var copia = r.clone(); caches.open(VERSAO).then(function (c) { c.put(req, copia); }); }
    return r;
  }).catch(function () {
    return caches.match(req).then(function (c) { return c || (req.mode === "navigate" ? caches.match("index.html") : Response.error()); });   // an HTML page is only a fallback for a page
  }));
});
