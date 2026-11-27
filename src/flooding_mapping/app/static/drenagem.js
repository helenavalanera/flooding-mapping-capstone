/* Camada "Drenagem cadastrada" (inventário da Fase 2, Porto Alegre): contexto, independente do cálculo de escoamento.
   Mostra o que o cadastro da Prefeitura REGISTRA: onde há rede, poços de visita, bocas de lobo e casas de bomba, e as marcas de qualidade
   medidas na Fase 2. Não mostra nem infere capacidade de vazão, funcionamento atual, conectividade hidráulica ou eficiência. */
(function () {
  "use strict";
  var Lg = window.Logic;
  var Dr = { meta: null, erro: null, frags: {}, grupos: { rede: true, pocos: true, bocas: true, bombas: true }, selecionado: null, _meta: null, ouvintes: [] };
  window.Drenagem = Dr;

  var NOME = { rede: "Rede pluvial", pocos: "Poços de visita", bocas: "Bocas de lobo", bombas: "Casas de bomba" };
  var COR = { cadastro: "#2f6f9f", sem_acesso: "#b5651d", nao_interligada: "#7b2d8e", duplicado: "#7d8a93", poco: "#1b4f72", boca: "#0e8a8a", bomba: "#f5c518", sinalizado: "#e0a030" };
  Dr.COR = COR;
  var CATEGORIAS = { rede_pluvial: "Cadastro existente (rede pluvial)", rede_pluvial_sem_acesso: "Registro sem acesso", rede_pluvial_nao_interligada: "Cadastrado como não interligado" };
  var SINAIS = { diametro_fora_da_faixa_plausivel: "diâmetro fora da faixa plausível", altitude_montante_fora_da_faixa_plausivel: "altitude de montante fora da faixa plausível",
    altitude_jusante_fora_da_faixa_plausivel: "altitude de jusante fora da faixa plausível", declividade_fora_da_faixa_plausivel: "declividade fora da faixa plausível",
    insercao_montante_fora_da_faixa_plausivel: "inserção de montante fora da faixa plausível", insercao_jusante_fora_da_faixa_plausivel: "inserção de jusante fora da faixa plausível",
    altitude_da_tampa_fora_da_faixa_plausivel: "altitude da tampa fora da faixa plausível", profundidade_fora_da_faixa_plausivel: "profundidade fora da faixa plausível",
    data_implantacao_suspeita: "data de implantação suspeita" };
  var EVIDENCIAS = { evidencia_geometrica_inicio_coincide_com_outro_extremo: "início coincide com o extremo de outra linha", evidencia_geometrica_fim_coincide_com_outro_extremo: "fim coincide com o extremo de outra linha",
    evidencia_geometrica_inicio_perto_de_poco_de_visita: "início perto de um poço de visita", evidencia_geometrica_fim_perto_de_poco_de_visita: "fim perto de um poço de visita",
    evidencia_geometrica_ambos_extremos_ligados: "os dois extremos coincidem com outros elementos" };
  var TEXTOS = {
    aviso: "Cadastro municipal: mostra o que está registrado, não o que funciona. Não indica capacidade de vazão, funcionamento atual, conectividade hidráulica nem eficiência de drenagem, e não entra no cálculo de escoamento potencial.",
    fonte: "Fonte: serviços GIS da Prefeitura de Porto Alegre, coletados em 25/11/2026 e processados na Fase 2 (docs/qualidade_dados_fase2.md). Os atributos são mostrados como estão na fonte; nenhum serviço declara unidades, que foram inferidas e estão marcadas.",
    pontual: "Poços de visita, bocas de lobo e casas de bomba aparecem a partir do zoom 15; a rede, a partir do zoom 14.",
    evidencia: "Coincidência de geometria medida na Fase 2 (tolerância de 0,5 m para extremos e 1 m para poços). Não é conexão hidráulica confirmada."
  };
  Dr.textos = function () { return TEXTOS; };

  function el(id) { return document.getElementById(id); }
  function esc(s) { return Lg.esc(s); }
  function getJson(u) { return fetch(u, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status + " em " + u); return r.json(); }); }
  Dr.base = function () { return window.FM_DADOS.base("drenagem"); };
  Dr.urlTiles = function (camada) { return Dr.base() + "tiles/" + camada + "/{z}/{x}/{y}.pbf"; };
  Dr.carregar = function () {
    if (Dr._meta) return Dr._meta;
    Dr._meta = window.FM_DADOS.lerMeta("drenagem").then(function (m) { Dr.meta = m; return m; }).catch(function (e) { Dr.erro = e.message; Dr._meta = null; throw e; });
    return Dr._meta;
  };
  Dr.fragmento = function (camada, n) {
    var k = Math.floor(n / Dr.meta.tamanho_do_fragmento), chave = camada + "/" + k, nome = ("0000" + k).slice(-4) + ".json";
    if (!Dr.frags[chave]) Dr.frags[chave] = getJson(Dr.base() + "detalhe/" + camada + "/" + nome).catch(function (e) { delete Dr.frags[chave]; throw e; });
    return Dr.frags[chave].then(function (f) {
      var l = f.linhas[n - f.primeiro_n]; if (!l) return null;
      var o = {}; f.colunas.forEach(function (c, j) { o[c] = l[j]; }); return o;
    });
  };
  Dr.aoMudar = function (f) { Dr.ouvintes.push(f); };

  /* ---------------------------------------------------------------- legenda e painel de controles */
  function swatch(cor, forma, extra) {
    if (forma === "linha") return "<span class='sw line' style='border-top:4px " + (extra || "solid") + " " + cor + "'></span>";
    return "<span class='sw' style='background:" + (extra === "oco" ? "transparent" : cor) + ";border-radius:50%;border:2px solid " + (extra === "oco" ? cor : "#fff") + ";box-shadow:0 0 0 1px #6b7780'></span>";
  }
  function li(sw, texto, tipo) { return "<li>" + sw + "<span>" + esc(texto) + " <span class='small'>(" + tipo + ")</span></span></li>"; }
  Dr.legenda = function () {
    var g = Dr.grupos, h = "<li class='f3-tit'><b>Drenagem cadastrada</b> " + Lg.kindBadge("observado") + " <span class='small'>contexto, fora do cálculo</span></li>";
    if (g.rede) h += li(swatch(COR.cadastro, "linha"), "Cadastro existente", "linha") + li(swatch(COR.sem_acesso, "linha"), "Registro sem acesso", "linha") + li(swatch(COR.nao_interligada, "linha", "dashed"), "Cadastrado como não interligado", "linha") +
      li(swatch(COR.duplicado, "linha", "dotted"), "Registro duplicado (fora do inventário)", "linha");
    if (g.pocos) h += li(swatch(COR.poco, "ponto"), "Poço de visita", "ponto");
    if (g.bocas) h += li(swatch(COR.boca, "ponto"), "Boca de lobo", "ponto");
    if (g.bombas) h += li(swatch(COR.bomba, "ponto"), "Casa de bomba", "ponto");
    if (g.pocos || g.bocas || g.bombas) h += li(swatch(COR.duplicado, "ponto", "oco"), "Ponto duplicado (fora do inventário)", "ponto");
    h += li("<span class='sw line' style='border-top:8px solid " + COR.sinalizado + ";opacity:.6'></span>", "Rede com valor fora da faixa plausível (halo)", "linha");
    h += "<li class='small f3-nota'>Atributo não preenchido na fonte aparece como \"não informado\" no painel, nunca como zero.</li>";
    return h;
  };
  Dr.montarPainel = function () {
    var box = el("dren-opcoes"); if (!box) return;
    if (!Dr.meta) { box.innerHTML = "<h2>Drenagem cadastrada</h2>" + (Dr.erro ? "<p class='small' role='status'>Os dados da drenagem não estão disponíveis neste ambiente (" + esc(Dr.erro) + "). Gere-os com tools/preparar_camada_drenagem.py.</p>" : "<p class='small' role='status'>Carregando...</p>"); return; }
    var cont = Dr.meta.camadas;
    box.innerHTML = "<h2 id='h-dren'>Drenagem cadastrada " + Lg.kindBadge("observado") + "</h2><p class='small f3-aviso' role='note'>" + esc(TEXTOS.aviso) + "</p>" +
      "<fieldset class='f3-modos'><legend>O que mostrar</legend>" + Object.keys(NOME).map(function (k) {
        return "<label class='f3-radio'><input type='checkbox' data-dren='" + k + "'" + (Dr.grupos[k] ? " checked" : "") + "> " + esc(NOME[k]) + " <span class='small'>(" + cont[k].registros.toLocaleString("pt-BR") + " registros)</span></label>"; }).join("") + "</fieldset>" +
      "<p class='small'>" + esc(TEXTOS.pontual) + "</p><p class='small'>" + esc(TEXTOS.fonte) + "</p>";
    box.querySelectorAll("input[data-dren]").forEach(function (i) { i.addEventListener("change", function () { Dr.grupos[i.dataset.dren] = i.checked; Dr.ouvintes.forEach(function (f) { f(); }); }); });
  };

  /* ---------------------------------------------------------------- painel do registro */
  function rotuloDoCampo(camada, campo) {
    var d = Dr.meta.dicionario_de_campos[camada === "rede" ? "rede_pluvial" : camada === "bombas" ? "casas_de_bomba" : "pontos"] || {}, x = d[campo];
    return x ? { original: x.campo_original, unidade: x.unidade, inferida: x.origem_da_unidade } : { original: null, unidade: null, inferida: null };
  }
  function valorTexto(v) {
    if (v === null || v === undefined) return "<span class='muted'>não informado</span>";
    if (v === true) return "sim"; if (v === false) return "não";
    return esc(typeof v === "number" ? String(v).replace(".", ",") : v);
  }
  Dr.corpo = function (camada, r) {
    var cab, resumo = [];
    if (camada === "rede") {
      cab = "Trecho de rede pluvial";
      resumo.push(["Categoria no cadastro", CATEGORIAS[r.camada_origem] || "não informada"], ["Diâmetro", r.diametro == null ? null : r.diametro + " mm (unidade inferida)"],
        ["Comprimento pela geometria", r.comprimento_pela_geometria == null ? null : Lg.esc(String(Math.round(r.comprimento_pela_geometria * 10) / 10).replace(".", ",")) + " m"],
        ["Marcado como ativo no cadastro", r.ativo_no_cadastro == null ? null : (r.ativo_no_cadastro ? "sim" : "não")]);
    } else if (camada === "bombas") {
      cab = "Casa de bomba"; resumo.push(["Nome", r.nome], ["Capacidade informada no cadastro", r.capacidade_informada ? r.capacidade_texto_original : null]);
    } else {
      cab = camada === "pocos" ? "Poço de visita" : "Boca de lobo";
      resumo.push(["Profundidade", r.profundidade == null ? null : r.profundidade + " (unidade inferida)"], ["Altitude da tampa", r.altitude_da_tampa == null ? null : r.altitude_da_tampa + " (referência vertical não declarada)"]);
    }
    var sinais = Object.keys(SINAIS).filter(function (k) { return r[k] === true; }).map(function (k) { return SINAIS[k]; });
    var q = "<p class='small'><b>Qualidade do registro:</b> " + (r.usar_no_inventario === false ? "registro duplicado (duplicata exata de <code>" + esc(r.duplicata_exata_de) + "</code>), fora do inventário. " : "") +
      (sinais.length ? "valores sinalizados: " + esc(sinais.join("; ")) + "." : "nenhum valor sinalizado como fora da faixa plausível.") + "</p>";
    var ev = Object.keys(EVIDENCIAS).filter(function (k) { return k in r; });
    var evid = ev.length ? "<details><summary>Evidência geométrica (não é conexão hidráulica)</summary><p class='small'>" + esc(TEXTOS.evidencia) + "</p><ul class='plain'>" + ev.map(function (k) { return "<li>" + esc(EVIDENCIAS[k]) + ": " + valorTexto(r[k]) + "</li>"; }).join("") + "</ul></details>" : "";
    var linhas = Object.keys(r).map(function (c) {
      var m = rotuloDoCampo(camada, c);
      return "<tr><th scope='row'>" + esc(c) + (m.original ? " <span class='small'>(" + esc(m.original) + (m.unidade ? ", " + esc(m.unidade) + (m.inferida ? ", unidade inferida" : "") : "") + ")</span>" : "") + "</th><td>" + valorTexto(r[c]) + "</td></tr>"; }).join("");
    return "<h3>" + esc(cab) + " " + Lg.kindBadge("observado") + "</h3><p class='small'>Registro do cadastro, não funcionamento.</p>" +
      "<dl class='dren-resumo'>" + resumo.map(function (x) { return "<dt>" + esc(x[0]) + "</dt><dd>" + (x[1] == null ? "<span class='muted'>não informado</span>" : esc(x[1])) + "</dd>"; }).join("") + "</dl>" + q + evid +
      "<details><summary>Todos os atributos do cadastro, como na fonte</summary><table><tbody>" + linhas + "</tbody></table></details>" +
      "<p class='small'>" + esc(TEXTOS.aviso) + "</p>";
  };
  Dr.detalhe = function (camada, n, alvo) {
    Dr.selecionado = camada + ":" + n; alvo.innerHTML = "<h2 id='h-contexto'>Seleção</h2><p class='small' role='status'>Carregando o registro...</p>";
    return Dr.carregar().then(function () { return Dr.fragmento(camada, n); }).then(function (r) {
      if (Dr.selecionado !== camada + ":" + n) return;
      if (!r) throw new Error("registro fora do fragmento");
      alvo.innerHTML = "<h2 id='h-contexto'>Seleção</h2><div id='dren-registro' data-camada='" + camada + "' data-n='" + n + "'>" + Dr.corpo(camada, r) + "</div>";
    }).catch(function (e) { alvo.innerHTML = "<h2 id='h-contexto'>Seleção</h2><p class='small' role='alert'>Não foi possível ler este registro (" + esc(e.message) + ").</p>"; });
  };
})();
