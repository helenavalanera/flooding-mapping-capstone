/* Onde estão os dados derivados e qual versão a página espera. Esta é a única peça que muda entre ambientes: a interface não tem caminho de máquina nenhum.
   - fase3, drenagem e mapa: URL-base das camadas (e URL do arquivo do mapa-base), relativa a esta página ("fase3/") ou absoluta ("https://dados.exemplo.org/d-6c3c2b28e0ee/fase3/").
     Origem externa exige CORS no servidor dos dados e a origem listada em connect-src e img-src da política de conteúdo (docs/publicacao_pages_releases.md).
   - versao: identificador do conjunto (tools/gerar_manifesto_publicacao.py). meta_sha256: hash esperado do meta.json de cada camada; quando preenchido, a página
     recusa um meta.json diferente (dados que não são os da versão) em vez de mostrá-lo. Nulo = sem conferência (desenvolvimento local). */
window.FM_DADOS = {
  fase3: "fase3/", drenagem: "drenagem/", geoai: "geoai/", versao: null, meta_sha256: { fase3: null, drenagem: null, geoai: null },
  /* Arquivo do mapa-base (Protomaps, lido por faixas de bytes). Padrão: o servidor local, na raiz ("/mapa/rs.pmtiles"). Com os dados no R2: a URL pública do objeto
     ("https://dados.exemplo.org/d-<hash>/mapa/rs.pmtiles"), que precisa de CORS com o cabeçalho Range e da origem em connect-src. */
  mapa: "/mapa/rs.pmtiles",
  base: function (camada) { var u = new URL(window.FM_DADOS[camada], location.href).href; return u.slice(-1) === "/" ? u : u + "/"; },
  /* Lê o meta.json da camada; com hash esperado, confere o conteúdo antes de usá-lo. */
  lerMeta: function (camada) {
    var url = window.FM_DADOS.base(camada) + "meta.json", esperado = window.FM_DADOS.meta_sha256[camada];
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status + " em " + url);
      if (!esperado) return r.json();
      if (!(window.crypto && crypto.subtle)) throw new Error("este navegador não consegue conferir a integridade dos dados (exige HTTPS)");
      return r.arrayBuffer().then(function (b) { return crypto.subtle.digest("SHA-256", b).then(function (h) {
        var hex = Array.prototype.map.call(new Uint8Array(h), function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
        if (hex !== esperado) throw new Error("o meta.json de " + camada + " não corresponde à versão esperada dos dados (hash " + hex.slice(0, 12) + " em vez de " + esperado.slice(0, 12) + ")");
        return JSON.parse(new TextDecoder().decode(b));
      }); });
    });
  }
};
