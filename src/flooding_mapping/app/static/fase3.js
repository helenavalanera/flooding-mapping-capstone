/* Camada "Escoamento potencial por trecho" (resultados reais da Fase 3, Porto Alegre).
   Este módulo cuida do acesso aos dados (meta.json, tiles e fragmentos por trecho), dos controles, da legenda e do painel do trecho.
   Quem desenha no mapa é mapa.js. A lógica pura está em fase3-dados.js. O motor não é recalculado aqui: a chuva de referência
   escolhe entre execuções que já existem (10, 20 e 30 mm) e o volume mostrado é P x área equivalente / 1000, a mesma conta do motor. */
(function () {
  "use strict";
  var D = window.Fase3Dados, Lg = window.Logic;
  var F = { meta: null, erro: null, estado: { modo: "c", pacote: "m1", limite: "max", p: null }, frags: {}, ouvintes: [], selecionado: null, _meta: null };
  window.Fase3 = F;

  var TEXTOS = {
    aviso: "Contribuição potencial estimada, condicionada a uma chuva hipotética. Não é previsão de alagamento, nem volume que de fato chegou ao trecho, nem profundidade ou duração. Não substitui os alertas oficiais da Defesa Civil (199).",
    dica: "As linhas vermelhas e laranja de \"Risco estimado por trecho\" são outra camada (um baseline sem validação). Desligue-a para ver só esta.",
    modos: {
      c: "Contribuição acumulada: soma o escoamento potencial de toda a área a montante que o relevo encaminha ao trecho. Mostra por onde pode passar mais água, não onde ela é gerada.",
      l: "Geração local: o escoamento potencial só da superfície sob o trecho, sem o que vem de cima. Mostra onde a água se origina, segundo o uso do solo.",
      cb: "Cobertura dos dados: parte da área a montante de cada trecho cujas classes têm coeficiente no pacote escolhido: o grau de confiança do valor. Cobertura baixa significa que o intervalo considera só uma parte da área."
    },
    chuva: "Chuva hipotética e uniforme: o mesmo valor em toda a cidade. Ela multiplica os volumes, mas não diferencia ruas nem representa uma tempestade localizada. Os três valores vêm de execuções do motor; por isso não há controle livre de precipitação.",
    metodologia: [
      ["Como a chuva gera escoamento potencial", "Para cada célula de 30 m, o modelo usa o uso do solo (edificação, via pavimentada, vegetação...). Cada tipo de superfície tem um coeficiente C, entre 0 e 1, que diz que fração da chuva escoa em vez de infiltrar. O volume potencial é V = P × A × C ÷ 1000, com P em mm, A em m² e V em m³. É um limite superior: não desconta infiltração nem perdas."],
      ["Como o relevo orienta o fluxo simulado", "O modelo de elevação indica, para cada célula, para qual vizinha a água desce (a mais baixa das oito, o método D8). Seguindo essas direções, soma-se o escoamento potencial de tudo que está a montante. Depressões são preenchidas só para que o caminho da água não se interrompa."],
      ["Como as células de 30 m são associadas aos trechos", "O trecho é amostrado a cada 6 m e as células sob ele formam a pegada. Entram na contribuição só as células da pegada que não têm outra célula da pegada a jusante (as células de chegada). Assim a área a montante de cada uma é contada uma única vez, sem duplicar volumes."],
      ["Por que a contribuição de trechos diferentes não pode ser somada", "Trechos vizinhos, ou um a montante do outro, compartilham a mesma área contribuinte. Somar os valores contaria a mesma água várias vezes. Por isso a aplicação não mostra total da cidade nem soma entre trechos."],
      ["Por que os resultados não são volume efetivamente transportado", "O modelo não conhece infiltração real, evaporação, capacidade das galerias e das bombas, nem a duração da chuva. O resultado é água potencialmente escoada, e não o que de fato chega ao trecho. Também não indica profundidade, extensão nem duração de alagamento."],
      ["Por que o modelo de elevação de 30 m limita as depressões urbanas", "O relevo vem do Copernicus GLO-30, um modelo de superfície de 30 m com erro médio de cerca de 2 m na região. Ele não resolve pequenas depressões urbanas, como um cruzamento rebaixado ou uma passagem inferior. O indicador topográfico só serve para comparar trechos entre si; sua altura não é interpretável em metros."],
      ["Por que a drenagem cadastrada não representa capacidade hidráulica", "A rede de drenagem municipal foi inventariada, mas sem capacidade hidráulica nem conexões confirmadas, e por isso não entra no cálculo. Onde há galeria, a água real pode seguir por ela."],
      ["Por que a chuva uniforme não diferencia eventos localizados", "A chuva de referência (10, 20 ou 30 mm) é a mesma em toda a cidade. Um evento concentrado em um bairro teria outro resultado. A chuva distribuída no espaço é um passo futuro; o motor já aceita esse parâmetro, mas ele não foi usado."]
    ],
    indicadores: {
      local: ["Volume potencial gerado localmente", "m³ (intervalo)", "Água que a superfície das células sob o trecho pode escoar na chuva de referência, segundo o uso do solo.", "Mede o que se origina ali, sem o que vem de cima. Um trecho com valor local pequeno pode receber muita água de áreas a montante."],
      contrib: ["Contribuição potencial estimada associada ao trecho", "m³ (intervalo)", "Escoamento potencial somado sobre toda a área a montante que o relevo encaminha ao trecho, incluindo o que se gera sob ele.", "Quanto maior, mais água pode passar por ali na chuva de referência. É potencial: não é o volume que de fato chegou e não pode ser somado com outros trechos."],
      area: ["Área contribuinte estimada", "m² ou ha", "Área a montante que o relevo encaminha ao trecho, em células de 30 m.", "Dá a escala da bacia que alimenta o trecho. Áreas grandes costumam indicar vales ou eixos de drenagem."],
      cobertura: ["Cobertura do pacote selecionado", "% da área a montante", "Parte da área a montante cujas classes de uso do solo têm coeficiente no pacote escolhido.", "É o grau de confiança do valor: com cobertura baixa, o intervalo considera só uma parte da área e deve ser lido como parcial."],
      topo: ["Indicador topográfico de retenção", "posto de 0 a 100", "Posição do trecho entre todos pela altura que o preenchimento de depressões soma ao relevo na pegada.", "Indica se o relevo do modelo favorece reter água ali, em comparação com os outros trechos. Não é profundidade, volume nem duração, e o modelo de 30 m não resolve depressões pequenas."]
    }
  };
  F.textos = function () { return TEXTOS; };

  function el(id) { return document.getElementById(id); }
  function esc(s) { return Lg.esc(s); }
  function getJson(u) { return fetch(u, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status + " em " + u); return r.json(); }); }

  /* ------------------------------------------------------------------ dados */
  F.base = function () { return window.FM_DADOS.base("fase3"); };
  F.urlTiles = function () { return F.base() + "tiles/{z}/{x}/{y}.pbf"; };
  /* Os tiles trazem a malha inteira da caixa em volta de Porto Alegre, inclusive vias de cidades vizinhas. Os números do estudo valem só para as ruas dentro da cidade
     (data/limite_poa.json); o mapa as sombreia e diz quantas são. */
  F.carregarRecorte = function () {
    if (F._rec) return F._rec;
    F._rec = fetch("data/limite_poa.json").then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(function (j) { F.recorte = j.properties; if (F.avisarZoom && F._zoom != null) F.avisarZoom(F._zoom); var n = el("f3-recorte"); if (n) n.innerHTML = notaDoRecorte(); return j; }).catch(function () { F._rec = null; });
    return F._rec;
  };
  var EXATO = new Intl.NumberFormat("pt-BR");
  function foraDePoa() { var r = F.recorte; return r && F.meta && F.meta.trechos > r.trechos_dentro ? F.meta.trechos - r.trechos_dentro : 0; }   // só quando os tiles ainda trazem as vias de fora
  function notaDoRecorte() {
    var r = F.recorte, fora = foraDePoa(); if (!fora) return "";
    return "<b>Malha e limite de Porto Alegre.</b> O mapa traz " + EXATO.format(F.meta.trechos) + " trechos de rua, dos quais " + EXATO.format(fora) + " são de cidades vizinhas e aparecem sombreados. Os resultados e os números do estudo valem para os " + EXATO.format(r.trechos_dentro) + " trechos dentro de Porto Alegre.";
  }
  F.carregar = function () {
    F.carregarRecorte();
    if (F._meta) return F._meta;
    F._meta = window.FM_DADOS.lerMeta("fase3").then(function (m) {
      F.meta = m; if (F.estado.p == null) F.estado.p = m.precipitacoes_mm.indexOf(F.pedidoP) >= 0 ? F.pedidoP : (m.precipitacoes_mm.indexOf(30) >= 0 ? 30 : m.precipitacoes_mm[0]);
      return m;
    }).catch(function (e) { F.erro = e.message; F._meta = null; throw e; });
    return F._meta;
  };
  F.fragmento = function (n) {
    var k = D.indiceDoFragmento(n, F.meta.tamanho_do_fragmento);
    if (!F.frags[k]) F.frags[k] = getJson(F.base() + "detalhe/" + D.nomeDoFragmento(k)).catch(function (e) { delete F.frags[k]; throw e; });
    return F.frags[k].then(function (frag) { return D.linhaDoFragmento(frag, n); });
  };

  /* ------------------------------------------------------------------ estado e estilo */
  F.aoMudar = function (f) { F.ouvintes.push(f); };
  function mudou() { F.ouvintes.forEach(function (f) { f(); }); }
  F.estilo = function () {
    var s = F.estado, prop = D.propriedadeDoModo(s.modo, s.pacote, s.limite);
    var props = D.propriedadesDoModo(s.modo), expressoes = {};
    props.forEach(function (p) { expressoes[p] = D.expressaoDeCor(p, D.PALETAS[s.modo]); });
    return { prop: prop, modo: s.modo, props: props, expressoes: expressoes };
  };
  function tituloAtual() {
    var s = F.estado, m = D.MODOS[s.modo], pk = D.PACOTES[s.pacote];
    if (s.modo === "tp") return m.nome;
    if (s.modo === "cb") return m.nome + ": " + pk.curto;
    return m.nome + " (" + D.LIMITES[s.limite] + ") · " + pk.curto + " · chuva de referência de " + D.formatar(s.p) + " mm";
  }

  /* ------------------------------------------------------------------ legenda */
  function li(cor, texto, tracejado) {
    return "<li><span class='sw" + (tracejado ? " line" : "") + "' style='" + (tracejado ? "border-top:4px dashed " + cor : "background:" + cor) + "'></span><span>" + esc(texto) + "</span></li>";
  }
  F.legenda = function () {
    if (!F.meta) return "<li class='muted'>Escoamento potencial: dados ainda não carregados.</li>";
    var s = F.estado, pal = D.PALETAS[s.modo], h = "<li class='f3-tit'><b>" + esc(tituloAtual()) + "</b></li>";
    if (s.modo === "c" || s.modo === "l") {
      var cortes = F.meta.cortes_das_classes_aeq_m2[D.propriedade(s.modo, s.pacote, s.limite)];
      h += li(pal[0], "Zero (nada escoa neste limite)");
      if (!cortes.length) h += "<li class='small'>Nenhum trecho tem valor positivo neste pacote e limite: todos os trechos com dados valem zero.</li>";
      for (var c = 1; cortes.length && c <= cortes.length + 1; c++) h += li(pal[c], D.rotuloDaFaixa(D.faixaDaClasse(cortes, c, s.p)));
    } else if (s.modo === "tp") {
      var t = F.meta.cortes_do_posto_topografico;
      h += li(pal[0], "Sem preenchimento de depressão no modelo") + li(pal[1], "Posto até " + D.formatar(t[0])) + li(pal[2], "Posto de " + D.formatar(t[0]) + " a " + D.formatar(t[1])) +
        li(pal[3], "Posto de " + D.formatar(t[1]) + " a " + D.formatar(t[2])) + li(pal[4], "Posto acima de " + D.formatar(t[2]));
    } else {
      h += li(pal[0], "Nenhuma parte da área a montante coberta") + li(pal[1], "Até 25% coberta") + li(pal[2], "De 25% a 50%") + li(pal[3], "De 50% a 75%") + li(pal[4], "Mais de 75% coberta");
    }
    h += li(D.COR_SEM_DADOS, "Trecho sem dados disponíveis (não é valor zero)", true);
    return h;
  };

  /* ------------------------------------------------------------------ controles */
  function opcoes(lista, atual) { return lista.map(function (o) { return "<option value='" + esc(o[0]) + "'" + (String(o[0]) === String(atual) ? " selected" : "") + ">" + esc(o[1]) + "</option>"; }).join(""); }
  function tabelaDeHipoteses() {
    var hp = F.meta.hipoteses, s = F.estado, num = function (x) { return D.formatar(x); };
    if (s.pacote === "m1") {
      return "<table><thead><tr><th>Classe</th><th>C</th><th>Incerteza</th></tr></thead><tbody>" + hp.metodo1.map(function (r) {
        return "<tr><td>" + esc(r.classe) + "</td><td>" + num(r.c_min) + " a " + num(r.c_max) + "</td><td>" + esc(r.grau_de_incerteza) + "</td></tr>"; }).join("") + "</tbody></table>" +
        "<p class='small'>Fonte: tabela de coeficientes do método racional (TxDOT, Tabela 4-10). As demais classes de uso do solo ficam fora deste método.</p>";
    }
    if (s.pacote === "li") return "<p class='small'>Nas " + hp.limites_fisicos.classes + " classes sem coeficiente fundamentado: C = " + num(hp.limites_fisicos.c_min) + " (limite inferior) e C = " + num(hp.limites_fisicos.c_max) + " (limite superior). " + esc(hp.limites_fisicos.natureza) + ".</p>";
    var j = hp.jardins_e_passeios;
    return "<p class='small'><b>Fração hipotética de piso</b> (parte construída de " + esc(j.classe) + "): " + j.cenarios_de_fracao_de_piso.map(function (c) { return c.fracao_de_piso + "% → C de " + num(c.c_min) + " a " + num(c.c_max); }).join("; ") +
      ". O resultado usa sempre o <b>envelope</b>, C de " + num(j.envelope[0]) + " a " + num(j.envelope[1]) + ": nenhum cenário do meio é tratado como valor verdadeiro.</p>" +
      "<table><thead><tr><th>Classe</th><th>C (analogia)</th></tr></thead><tbody>" + hp.referencia_analoga.map(function (r) { return "<tr><td>" + esc(r.classe) + "</td><td>" + num(r.c_min) + " a " + num(r.c_max) + "</td></tr>"; }).join("") + "</tbody></table>" +
      "<p class='small'>Hipótese: " + esc(j.hipotese) + "</p>";
  }
  function campo(id, rotulo, opts) { return "<div class='ctl'><label for='" + id + "'>" + rotulo + "</label><select id='" + id + "'>" + opts + "</select></div>"; }
  /* Opções da análise: três seletores curtos (chuva, pacote, limite, só os que valem para a dimensão ligada). Tudo o que explica fica em "Como ler e limitações". */
  F.montarPainel = function () {
    var box = el("f3-opcoes"); if (!box) return;
    if (!F.meta) {
      box.innerHTML = F.erro ? "<p class='small f3-sem' role='status'>Os dados de escoamento não estão disponíveis (" + esc(F.erro) + "). <button type='button' class='link' id='f3-tentar'>Tentar de novo</button></p>" : "<p class='small' role='status'>Carregando…</p>";
      var tentar = el("f3-tentar"); if (tentar) tentar.addEventListener("click", function () { if (window.Mapa) window.Mapa.tentarFase3(); });
      return;
    }
    var s = F.estado, volumes = s.modo === "c" || s.modo === "l", pacotes = s.modo !== "tp", sel = [];
    var det = el("f3-metodo"), hip = el("f3-hipoteses"); if (det) { F._abertoMetodo = det.open; F._abertoHipoteses = !!(hip && hip.open); }
    if (volumes) sel.push(campo("f3-p", "Chuva", opcoes(F.meta.precipitacoes_mm.map(function (p) { return [p, D.formatar(p) + " mm"]; }), s.p)));
    if (pacotes) sel.push(campo("f3-pacote", "Pacote", opcoes(Object.keys(D.PACOTES).map(function (k) { return [k, D.PACOTES[k].curto]; }), s.pacote)));
    if (volumes) sel.push(campo("f3-limite", "Limite", opcoes([["max", "Superior"], ["min", "Inferior"]], s.limite)));
    var modos = Object.keys(D.MODOS).map(function (k) {
      return "<label class='f3-radio'><input type='radio' name='f3-modo' id='f3-modo-" + k + "' value='" + k + "'" + (s.modo === k ? " checked" : "") + "> " + esc(D.MODOS[k].nome) + "</label>"; }).join("");
    box.innerHTML = (sel.length ? "<div class='ctl-grade n" + sel.length + "'>" + sel.join("") + "</div>" : "") +
      "<p class='small' id='f3-zoom' aria-live='polite'></p>" +
      "<details id='f3-metodo' class='mais'><summary>Como ler e limitações</summary>" +
      (window.Mapa && window.Mapa.notaDim ? window.Mapa.notaDim({ l: "A", c: "B", tp: "C" }[s.modo] || "") : "") +
      "<p class='small f3-aviso' role='note'>" + esc(TEXTOS.aviso) + "</p>" +
      (TEXTOS.modos[s.modo] ? "<p class='small' id='f3-modo-nota'>" + esc(TEXTOS.modos[s.modo]) + "</p>" : "") +
      (s.modo === "tp" ? "<p class='small'>Posição de cada trecho pela altura que o preenchimento de depressões soma ao relevo, em um modelo de elevação de 30 m. Indicador relativo: não é profundidade, volume nem duração, e não depende de pacote nem de chuva.</p>" : "") +
      (volumes ? "<p class='small' id='f3-chuva-nota'><b>Chuva de referência: " + D.formatar(s.p) + " mm</b>, igual em toda a cidade. " + (s.p === 30 ? "É o percentil 75 dos totais por evento de 2017 a 2026 (reanálise ERA5), não a média. " : "") + "Cenário de cálculo, não previsão.</p><p class='small'>" + esc(TEXTOS.chuva) + "</p><p class='small f3-nota'>A cor é a posição do trecho entre os trechos com valor positivo (quantis); as faixas em m³ mudam com a chuva de referência.</p>" : "") +
      (pacotes ? "<p class='small' id='f3-pacote-nota'><b>" + esc(D.PACOTES[s.pacote].nome) + " (" + esc(D.PACOTES[s.pacote].natureza) + ").</b> " + esc(D.PACOTES[s.pacote].nota) + "</p><details id='f3-hipoteses'><summary>Coeficientes e hipóteses deste pacote</summary>" + tabelaDeHipoteses() + "</details>" : "") +
      "<p class='small' id='f3-recorte'>" + notaDoRecorte() + (foraDePoa() ? " " : "") + "Área sombreada, com contorno tracejado: fora de Porto Alegre, fora da análise.</p>" +
      "<fieldset class='f3-modos'><legend>Modo de cor (avançado)</legend>" + modos + "</fieldset>" +
      TEXTOS.metodologia.map(function (m) { return "<h3>" + esc(m[0]) + "</h3><p class='small'>" + esc(m[1]) + "</p>"; }).join("") +
      "<p class='small' id='f3-versao'>Dados de escoamento: camada v" + esc(F.meta.versao) + (window.FM_DADOS && window.FM_DADOS.versao ? ", conjunto " + esc(window.FM_DADOS.versao) : "") + ". Detalhes em docs/fase3_motor.md e docs/fase3_resultados.md.</p></details>";
    if (F._abertoMetodo && el("f3-metodo")) el("f3-metodo").open = true; if (F._abertoHipoteses && el("f3-hipoteses")) el("f3-hipoteses").open = true;      // redesenhar não fecha o que a pessoa abriu
    Array.prototype.forEach.call(box.querySelectorAll("input[name=f3-modo]"), function (i) { i.addEventListener("change", function () { s.modo = i.value; F.montarPainel(); mudou(); }); });
    var liga = function (id, campoNome, num) { var e = el(id); if (e) e.addEventListener("change", function () { s[campoNome] = num ? Number(e.value) : e.value; F.montarPainel(); mudou(); }); };
    liga("f3-pacote", "pacote"); liga("f3-limite", "limite"); liga("f3-p", "p", true);
    if (F._zoom != null) F.avisarZoom(F._zoom);
    var foco = document.activeElement && document.activeElement.id;
    if (foco && el(foco)) el(foco).focus();
  };
  F.avisarZoom = function (zoom) {
    F._zoom = zoom; var e = el("f3-zoom"); if (!e || !F.meta) return;
    e.textContent = zoom < F.meta.zoom[0] ? "Aproxime o mapa (zoom " + F.meta.zoom[0] + " ou mais): são " + EXATO.format(F.meta.trechos) + " trechos na malha" + (foraDePoa() ? " (" + EXATO.format(F.recorte.trechos_dentro) + " em Porto Alegre)" : "") + " e eles só são desenhados de perto." : "";
  };

  /* ------------------------------------------------------------------ painel do trecho */
  /* Nome da rua e quatro indicadores em grade 2 x 2 (A, B, C, D). "Sem dado" nunca é zero; zero aparece como 0. Detalhes e métodos ficam em "Detalhes e como ler". */
  function celula(id, rotulo, valor, un, sem, estado) {
    var v = sem ? "<span class='v' role='img' aria-label='Sem dado' title='Sem dado'>—</span>" : "<span class='v'>" + valor + "</span>";   // travessão = sem dado (nunca zero); leitores de tela ouvem "Sem dado"
    return "<div class='f3-ind sel-ind" + (sem ? " sem" : estado ? " estado" : "") + "' data-dim='" + id + "'><dt><b>" + id + "</b>" + esc(rotulo) + "</dt><dd class='f3-val'>" + v + (un ? "<span class='u'>" + esc(un) + "</span>" : "") + "</dd></div>";
  }
  var SEM = "—";
  function ajuda(chave) { var t = TEXTOS.indicadores[chave]; return "<p class='small'><b>" + esc(t[0]) + ".</b> " + esc(t[2]) + " " + esc(t[3]) + "</p>"; }
  F.corpoDoTrecho = function (r) {
    var s = F.estado, pk = D.PACOTES[s.pacote], nome = r.nome || "Trecho sem nome";
    var cab = "<div class='sel-topo'><h3 class='sel-rua'>" + esc(nome) + "</h3></div>";
    var drenagem = celula("D", "Drenagem", SEM, "", true);
    var mais = "<details class='mais sel-mais'><summary>Detalhes e como ler</summary>" + "<p class='small'>Identificador: <code>" + esc(r.id) + "</code>" + (r.via ? " · via " + esc(r.via) : "") + ".</p>";
    if (r.l_m1_max == null) {
      return cab + "<dl class='sel-grade'>" + celula("A", "Geração", SEM, "", true) + celula("B", "Concentração", SEM, "", true) + celula("C", "Topografia", SEM, "", true) + drenagem + "</dl>" +
        "<p class='small sel-ctx'>— indica sem dado, que não é zero: o trecho está fora da grade de 30 m do modelo ou passa só por células sem dado ou de água.</p>" +
        mais + "<p class='small'>O cadastro de drenagem não está associado aos trechos; para ver um dispositivo, ligue D e clique nele no mapa.</p><p class='small'>" + esc(TEXTOS.aviso) + "</p></details>";
    }
    var p = s.p;
    var l = D.intervalo(r["l_" + s.pacote + "_min"], r["l_" + s.pacote + "_max"], p), c = D.intervalo(r["c_" + s.pacote + "_min"], r["c_" + s.pacote + "_max"], p);
    var faixa = function (x) { return x.min === x.max ? D.formatar(x.min) : D.formatar(x.min) + " a " + D.formatar(x.max); };
    var topo = r.topo_altura_max_m > 0 ? celula("C", "Topografia", "posto " + D.formatar(r.topo_posto), "de 100") : celula("C", "Topografia", "Sem depressão", "no modelo", false, true);
    var fcob = { m1: r.f_m1, li: r.f_li, an: r.f_an }[s.pacote];
    mais += "<p class='small'>Contribuição de trechos diferentes não se soma: as áreas a montante se sobrepõem. Não somar com outros trechos.</p><p class='small'>Valores para o pacote <b>" + esc(pk.curto) + "</b> (" + esc(pk.natureza) + "), chuva de " + esc(D.formatar(p)) + " mm. Área contribuinte: " + esc(D.area(r.area_montante_m2)) + "; cobertura do pacote: " + esc(D.pct(fcob)) + " da área a montante" + (fcob < 0.25 ? " (parcial: o intervalo considera só uma parte da área)" : "") + ". Altura de preenchimento no modelo: " + esc(D.formatar(r.topo_altura_max_m)) + " m (grandeza do modelo, não é profundidade). " + r.n_cel + " células de 30 m sob o trecho.</p>" +
      ajuda("local") + ajuda("contrib") + ajuda("topo") +
      "<p class='small'>O cadastro de drenagem não está associado aos trechos; para ver um dispositivo, ligue D e clique nele no mapa.</p><p class='small'>" + esc(TEXTOS.aviso) + "</p></details>";
    var un = fcob < 0.25 ? "m³ · parcial" : "m³";                                       // pouca área a montante com coeficiente neste pacote: o intervalo é parcial
    return cab + "<dl class='sel-grade'>" + celula("A", "Geração", l ? faixa(l) : SEM, l ? un : "", !l) + celula("B", "Concentração", c ? faixa(c) : SEM, c ? un : "", !c) + topo + drenagem + "</dl>" +
      "<p class='small sel-ctx'>Chuva de referência de " + esc(D.formatar(p)) + " mm · valores potenciais estimados, não observados.</p>" + mais;
  };
  F.detalhe = function (n, alvo) {
    F.selecionado = n; alvo.innerHTML = "<h2 id='h-contexto'>Seleção</h2><p class='small' role='status'>Carregando o trecho…</p>";
    return F.carregar().then(function () { return F.fragmento(n); }).then(function (r) {
      if (F.selecionado !== n) return;
      if (!r) throw new Error("trecho " + n + " fora do fragmento");
      alvo.innerHTML = "<h2 id='h-contexto'>Seleção</h2><div id='f3-trecho' data-n='" + n + "'>" + F.corpoDoTrecho(r) + "</div>"; F._linha = r;
    }).catch(function (e) { alvo.innerHTML = "<h2 id='h-contexto'>Seleção</h2><p class='small' role='alert'>Não foi possível ler os dados deste trecho (" + esc(e.message) + ").</p>"; });
  };
  F.redesenharTrecho = function () {
    var c = el("f3-trecho"); if (c && F._linha) c.innerHTML = F.corpoDoTrecho(F._linha);
  };
  F.aoMudar(F.redesenharTrecho);
})();
