/* Basemap shared by every map in the product (dashboard 3D/2D and the citizen PWA).
   Vector tiles of Rio Grande do Sul (Protomaps, derived from OpenStreetMap) read from our own server (or from the bucket named in config-dados.js), in a muted grayscale so the risk,
   rain and route layers are the only strong colours. Nothing here calls a third-party tile server: the archive is /mapa/rs.pmtiles, answered
   with HTTP Range, and the label fonts and styles are files of this app (vendor/mapa).
   - estiloGL(opcoes): MapLibre style (promise). Registers the pmtiles:// protocol once.
   - camadaLeaflet(): Leaflet layer for the engine that runs without WebGL (canvas-drawn, no WebGL needed). */
(function () {
  "use strict";
  var BASE = new URL(".", document.currentScript.src).href;          // .../static/
  var VENDOR = BASE + "vendor/mapa";
  var VERSAO_ARQUIVO = "20261115";                                   // build of the Protomaps archive; the offline cache is keyed by it
  var ARQUIVO = new URL(((window.FM_DADOS && window.FM_DADOS.mapa) || "/mapa/rs.pmtiles") + "?v=" + VERSAO_ARQUIVO, location.href).href;   // config-dados.js (carregado antes) pode apontar para o R2
  var DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
  var protocoloRegistrado = false;

  function escuro() { return false; }                                // a aplicação é só em modo claro: o tema do sistema não muda a aparência

  /* Cache das faixas de bytes do mapa-base. O navegador não guarda respostas parciais (206) no cache HTTP: sem isto, cada visita repete as mesmas dezenas de pedidos Range (medido:
     50 pedidos e cerca de 1,2 MB por visita, nenhum vindo do cache). Aqui cada faixa lida fica na Cache API, chaveada pela URL do arquivo (que leva a versão do mapa-base) e pela faixa,
     e é reaproveitada nas visitas seguintes. Não é Service Worker, não baixa o arquivo inteiro e cai no pedido normal se algo falhar. */
  function hashCurto(t) { var h = 0; for (var i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) | 0; return (h >>> 0).toString(36); }
  var CACHE_NOME = "fm-pmtiles-" + VERSAO_ARQUIVO + "-" + hashCurto(ARQUIVO);   // outro arquivo ou outra versão: outro cache, e o antigo é apagado
  var limpou = false;
  function limparCachesAntigos() {
    if (limpou) return; limpou = true;
    caches.keys().then(function (ks) { ks.forEach(function (k) { if (k.indexOf("fm-pmtiles-") === 0 && k !== CACHE_NOME) caches.delete(k); }); }).catch(function () {});
  }
  function FonteComCache(url) {
    var base = new window.pmtiles.FetchSource(url);
    this.getKey = function () { return url; };
    this.getBytes = function (offset, length, signal, etag) {
      var chave = url + (url.indexOf("?") < 0 ? "?" : "&") + "faixa=" + offset + "-" + (offset + length - 1);
      limparCachesAntigos();
      return caches.open(CACHE_NOME).then(function (cache) {
        return cache.match(chave).then(function (hit) {
          if (hit && (!etag || hit.headers.get("x-etag") === etag)) return hit.arrayBuffer().then(function (data) { return { data: data, etag: hit.headers.get("x-etag") || undefined }; });
          return base.getBytes(offset, length, signal, etag).then(function (r) {
            if (r && r.data && r.data.byteLength <= 4 * 1024 * 1024) cache.put(chave, new Response(r.data.slice(0), { headers: { "x-etag": r.etag || "" } })).catch(function () {});
            return r;
          });
        });
      }).catch(function (e) { if (e && e.name === "AbortError") throw e; return base.getBytes(offset, length, signal, etag); });
    };
  }

  function registrar() {
    if (protocoloRegistrado) return;
    if (!window.pmtiles || !window.maplibregl) throw new Error("Mapa-base: bibliotecas não carregadas");
    var protocolo = new window.pmtiles.Protocol();
    if (typeof caches !== "undefined" && window.isSecureContext !== false) protocolo.add(new window.pmtiles.PMTiles(new FonteComCache(ARQUIVO)));   // sem a Cache API, o PMTiles lê direto do servidor, como antes
    window.maplibregl.addProtocol("pmtiles", protocolo.tile);
    protocoloRegistrado = true;
  }

  /* opcoes.relevo: {exagero} adds the hillshade from the elevation tiles, under roads and labels. */
  function estiloGL(opcoes) {
    opcoes = opcoes || {};
    registrar();
    return fetch(VENDOR + "/estilo-" + (escuro() ? "escuro" : "claro") + ".json").then(function (r) {
      if (!r.ok) throw new Error("Mapa-base: estilo indisponível");
      return r.text();
    }).then(function (texto) {
      var estilo = JSON.parse(texto.split("__BASE__").join(VENDOR).split("__PMTILES__").join(ARQUIVO));
      if (opcoes.relevo) {
        estilo.sources.dem = { type: "raster-dem", tiles: [DEM], encoding: "terrarium", tileSize: 256, maxzoom: 12, attribution: "Elevação: AWS Terrain Tiles" };
        var camada = { id: "sombra", type: "hillshade", source: "dem", paint: { "hillshade-exaggeration": opcoes.relevo.exagero || 0.4, "hillshade-shadow-color": escuro() ? "#05080a" : "#3b4750" } };
        var posicao = estilo.layers.findIndex(function (l) { return l.id === "roads_tunnels_other_casing"; });
        estilo.layers.splice(posicao < 0 ? 2 : posicao, 0, camada);
      }
      return estilo;
    });
  }

  function camadaLeaflet() {
    if (!window.protomapsL) throw new Error("Mapa-base: biblioteca 2D não carregada");
    return window.protomapsL.leafletLayer({
      url: ARQUIVO, flavor: escuro() ? "dark" : "grayscale", lang: "pt", maxDataZoom: 14,
      attribution: '<a href="https://protomaps.com">Protomaps</a> &copy; <a href="https://openstreetmap.org/copyright">colaboradores do OpenStreetMap</a>'
    });
  }

  window.MapaBase = { estiloGL: estiloGL, camadaLeaflet: camadaLeaflet, arquivo: ARQUIVO, escuro: escuro, vendor: VENDOR };
})();
