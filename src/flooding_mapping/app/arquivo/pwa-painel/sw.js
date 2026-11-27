/* Service worker da aplicação de análise (painel, mapa, resultados, simulador e a landing em inicio/).
   POLÍTICA DE CACHE (o que fica no aparelho e o que nunca fica):
   - Interface (HTML, JS, CSS, bibliotecas do mapa): guardada na instalação e atualizada pela rede primeiro; offline abre a última cópia.
   - Resultados do estudo (data/resultados_poa.json, territorios.json e os demais data/*): rede primeiro, cópia salva como reserva. Quando a cópia é usada,
     a resposta leva o cabeçalho X-FM-Copia-Salva e a página avisa que são resultados salvos, com a data.
   - Mapa-base: só as faixas que a pessoa já viu (sw-mapa.js, compartilhado com /pwa/).
   - NUNCA guardados: /api/, previsao_72h.json e bloqueios.json (descrevem o agora: uma estimativa velha não pode passar por atual) e os tiles e fragmentos das camadas
     de escoamento e drenagem (fase3/, drenagem/: ~140 MB; sem rede essas camadas não aparecem e a tela diz isso).
   Versão: o nome do cache. Mudou o nome, o cache antigo (só os "fm-app-") é apagado; o do mapa-base e o do app de rotas (/pwa/) não são tocados. */
var VERSAO = "fm-app-v1";
importScripts("sw-mapa.js");   // mapaComCache, MAPA_PREFIXO
var BASE = new URL("./", self.location).href;
var CASCA = ["./", "index.html", "style.css", "painel.js", "territorio.js", "logic.js", "mapa.js", "mapa2d.js", "mapa-base.js", "fase3-dados.js", "fase3.js", "drenagem.js", "resultados.js", "simulador.js", "instalar.js", "config-dados.js",
  "manifest.webmanifest", "pwa/icon-192.png", "pwa/icon-512.png", "vendor/mapa/pmtiles.js", "vendor/mapa/protomaps-leaflet.js", "vendor/mapa/estilo-claro.json",
  "data/territorios.json", "data/resultados_poa.json", "data/cobertura_rs.json", "data/impacto_rs.json", "data/municipios.geojson", "data/rodovias.geojson",
  "inicio/", "inicio/estudo.css", "inicio/estudo.js", "inicio/dados.json"];
var EXTERNOS = ["https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js", "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.js", "https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.css"];
var NUNCA = ["api/", "previsao_72h.json", "bloqueios.json", "fase3/", "drenagem/"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSAO).then(function (c) {
    return c.addAll(CASCA).then(function () {   // as bibliotecas vêm da CDN; maplibre exige resposta CORS por causa da verificação de integridade
      return Promise.all(EXTERNOS.map(function (u) { return fetch(u, { mode: "cors" }).then(function (r) { if (r.ok) return c.put(u, r); }).catch(function () {}); }));
    });
  }).then(function () { return self.skipWaiting(); }));
});
function varrer() { return caches.keys().then(function (ks) { return Promise.all(ks.filter(function (k) { return k.indexOf("fm-app-") === 0 && k !== VERSAO; }).map(function (k) { return caches.delete(k); })); }); }
self.addEventListener("activate", function (e) {   // a segunda varredura apanha o que um service worker antigo, com pedidos em andamento, tenha recriado
  e.waitUntil(varrer().then(function () { return self.clients.claim(); }).then(function () { return new Promise(function (ok) { setTimeout(ok, 2500); }); }).then(varrer));
});
self.addEventListener("message", function (e) { if (e.data === "versao" && e.source) e.source.postMessage({ versao: VERSAO }); });

function naoGuardar(url) { var rel = url.href.indexOf(BASE) === 0 ? url.href.slice(BASE.length) : ""; return NUNCA.some(function (p) { return rel.indexOf(p) === 0; }); }
function comAviso(resposta) {   // a cópia salva sai marcada: a página mostra que não são dados recém-baixados
  var h = new Headers(resposta.headers); h.set("X-FM-Copia-Salva", "1");
  return resposta.blob().then(function (b) { return new Response(b, { status: resposta.status, statusText: resposta.statusText, headers: h }); });
}
/* Só escreve em um cache que ainda existe: um service worker antigo, já substituído, não recria o cache da sua versão depois de apagado. */
function guardar(req, copia) { return caches.has(VERSAO).then(function (existe) { if (existe) return caches.open(VERSAO).then(function (c) { return c.put(req, copia); }); }).catch(function () {}); }
self.addEventListener("fetch", function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== "GET") return;
  if (url.origin === location.origin) {
    if (naoGuardar(url) || url.pathname.indexOf("/api/") >= 0) return;                       // a rede decide; nada é guardado
    if (/\/mapa\/rs\.pmtiles$/.test(url.pathname)) { e.respondWith(mapaComCache(req, url)); return; }
  } else if (EXTERNOS.indexOf(req.url) < 0) return;                                           // outros domínios (mapa-base OSM etc.): fora do cache
  var dado = url.origin === location.origin && url.href.indexOf(BASE + "data/") === 0;
  e.respondWith(fetch(req).then(function (r) {
    if (r.ok) guardar(req, r.clone());
    return r;
  }).catch(function () {
    return caches.match(req, { ignoreSearch: true }).then(function (c) {
      if (c) return dado ? comAviso(c) : c;
      if (req.mode === "navigate") return caches.match(url.href.indexOf(BASE + "inicio/") === 0 ? "inicio/" : "index.html");
      return Response.error();
    });
  }));
});
