/* Carregamento sob demanda das bibliotecas do mapa. A página do painel (resultados, simulador, proveniência) não precisa de MapLibre, Leaflet nem PMTiles:
   elas só são baixadas quando o mapa é aberto. Com WebGL, só MapLibre e PMTiles (cerca de 0,8 MB); o Leaflet e o protomaps-leaflet (cerca de 0,3 MB) só vêm
   quando o navegador não tem WebGL ou a pessoa escolhe o mapa 2D simples. Os arquivos de terceiros mantêm o hash de integridade (SRI). */
(function () {
  "use strict";
  var SRI = {
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css": "sha512-h9FcoyWjHcOcmEVkxOfTLnmZFWIH0iZhZT1H2TbOq55xssQGEJHEaIm+PgoUaZbRvQTNTluNOEfb1ZRy6D3BOw==",
  "https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.css": "sha384-MinO0mNliZ3vwppuPOUnGa+iq619pfMhLVUXfC4LHwSCvF9H+6P/KO4Q7qBOYV5V",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js": "sha512-puJW3E/qXDqYp9IfhAI54BJEaWIfloJ7JWs7OeD5i6ruC9JZL1gERT1wjtwXFlh7CjE7ZJ+/vcRZRkIYIb6p4g==",
  "https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.js": "sha384-SYKAG6cglRMN0RVvhNeBY0r3FYKNOJtznwA0v7B5Vp9tr31xAHsZC0DqkQ/pZDmj"
};
  var cache = {};
  function css(url) {
    return new Promise(function (ok, erro) {
      var l = document.createElement("link"); l.rel = "stylesheet"; l.href = url;
      if (SRI[url]) { l.integrity = SRI[url]; l.crossOrigin = "anonymous"; }
      l.onload = ok; l.onerror = function () { erro(new Error("Não foi possível carregar " + url)); }; document.head.appendChild(l);
    });
  }
  function js(url) {
    if (cache[url]) return cache[url];
    return (cache[url] = new Promise(function (ok, erro) {
      var s = document.createElement("script"); s.src = url; s.async = false;
      if (SRI[url]) { s.integrity = SRI[url]; s.crossOrigin = "anonymous"; }
      s.onload = ok; s.onerror = function () { delete cache[url]; erro(new Error("Não foi possível carregar " + url)); }; document.head.appendChild(s);
    }));
  }
  var C = "https://cdnjs.cloudflare.com/ajax/libs/";
  var BASE = new URL(".", document.currentScript.src).href;
  window.CarregarMapa = {
    gl: function () { return Promise.all([css(C + "maplibre-gl/4.7.1/maplibre-gl.css"), js(C + "maplibre-gl/4.7.1/maplibre-gl.js").then(function () { return js(BASE + "vendor/mapa/pmtiles.js"); })]); },
    leaflet: function () { return Promise.all([css(C + "leaflet/1.9.4/leaflet.min.css"), js(C + "leaflet/1.9.4/leaflet.min.js").then(function () { return js(BASE + "vendor/mapa/pmtiles.js"); }).then(function () { return js(BASE + "vendor/mapa/protomaps-leaflet.js"); })]); }
  };
})();
