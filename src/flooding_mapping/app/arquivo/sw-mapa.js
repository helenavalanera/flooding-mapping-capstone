/* Cache do mapa-base, compartilhado pelos dois service workers (a aplicação em "/" e o app de rotas em "/pwa/"): uma única cópia da lógica.
   Cada um o carrega com importScripts. Só o que a pessoa já viu é guardado; nunca o estado inteiro. */
var MAPA_PREFIXO = "fm-mapa-", MAPA_MAX_FAIXAS = 4000;   // faixas do mapa-base já vistas (algumas dezenas de MB), as mais antigas saem primeiro

/* The basemap is one big file read by byte ranges. The Cache API cannot store a 206, so each range is kept as a plain 200 under its own key
   and handed back as a 206. Only what the person has already looked at is stored: no download of the whole state. The cache name carries
   the archive version (?v=), so a new archive never mixes with ranges of the old one. */
function mapaComCache(req, url) {
  var faixa = req.headers.get("Range");
  if (!faixa) return fetch(req);
  var nome = MAPA_PREFIXO + (url.searchParams.get("v") || "0"), chave = new Request(url.origin + url.pathname + "?faixa=" + encodeURIComponent(faixa));
  return caches.open(nome).then(function (c) {
    return c.match(chave).then(function (hit) {
      if (hit) return hit.arrayBuffer().then(function (b) { return new Response(b, { status: 206, headers: hit.headers }); });
      return fetch(req).then(function (r) {
        if (r.status !== 206) return r;
        var copia = r.clone();
        copia.arrayBuffer().then(function (b) {
          var h = new Headers(); ["Content-Type", "Content-Range", "Content-Length", "ETag", "Accept-Ranges"].forEach(function (k) { if (copia.headers.get(k)) h.set(k, copia.headers.get(k)); });
          return c.put(chave, new Response(b, { status: 200, headers: h }));
        }).then(function () { return c.keys(); }).then(function (ks) { if (ks.length > MAPA_MAX_FAIXAS) return Promise.all(ks.slice(0, ks.length - MAPA_MAX_FAIXAS + 500).map(function (k) { return c.delete(k); })); }).catch(function () {});
        caches.keys().then(function (ns) { ns.forEach(function (n) { if (n.indexOf(MAPA_PREFIXO) === 0 && n !== nome) caches.delete(n); }); });
        return r;
      });
    });
  });
}
