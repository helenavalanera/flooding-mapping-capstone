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
  F.carregar = function () {
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
    var s = F.estado, pal = D.PALETAS[s.modo], h = "<li class='f3-tit'><b>" + esc(tituloAtual()) + "</b> " + Lg.kindBadge("simulado") + "</li>";
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
    if (s.modo === "c" || s.modo === "l") h += "<li class='small f3-nota'>A cor é a posição do trecho entre os trechos com valor positivo (quantis); as faixas em m³ mudam com a chuva de referência.</li>";
    if (s.modo === "tp") h += "<li class='small f3-nota'>Posto relativo entre os trechos. O modelo de elevação de 30 m não resolve depressões urbanas pequenas: não é profundidade, volume nem duração.</li>";
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
  F.montarPainel = function () {
    var box = el("f3-opcoes"); if (!box) return;
    if (!F.meta) {
      box.innerHTML = "<h2>Escoamento potencial por trecho</h2>" + (F.erro ? "<p class='small' role='status'>Os dados de escoamento não estão disponíveis (" + esc(F.erro) + "). Em desenvolvimento, gere-os com tools/preparar_camada_fase3.py. <button type='button' class='link' id='f3-tentar'>Tentar de novo</button></p>" : "<p class='small' role='status'>Carregando...</p>");
      var tentar = el("f3-tentar"); if (tentar) tentar.addEventListener("click", function () { if (window.Mapa) window.Mapa.tentarFase3(); });
      return;
    }
    var s = F.estado, volumes = s.modo === "c" || s.modo === "l", pacotes = s.modo !== "tp";
    var modos = Object.keys(D.MODOS).map(function (k) {
      return "<label class='f3-radio'><input type='radio' name='f3-modo' id='f3-modo-" + k + "' value='" + k + "'" + (s.modo === k ? " checked" : "") + "> " + esc(D.MODOS[k].nome) + "</label>"; }).join("");
    box.innerHTML = "<h2 id='h-f3'>Escoamento potencial por trecho " + Lg.kindBadge("simulado") + "</h2>" +
      "<p class='small f3-aviso' role='note'>" + esc(TEXTOS.aviso) + "</p>" +
      "<p class='small' id='f3-dica'>" + esc(TEXTOS.dica) + "</p>" +
      "<fieldset class='f3-modos'><legend>O que mostrar</legend>" + modos + "</fieldset>" +
      (pacotes ? "<label for='f3-pacote'>Pacote de coeficientes <em>(alternativas, nunca somadas)</em></label><select id='f3-pacote'>" + opcoes(Object.keys(D.PACOTES).map(function (k) { return [k, D.PACOTES[k].nome]; }), s.pacote) + "</select>" +
        "<p class='small' id='f3-pacote-nota'><b>" + esc(D.PACOTES[s.pacote].natureza.charAt(0).toUpperCase() + D.PACOTES[s.pacote].natureza.slice(1)) + ".</b> " + esc(D.PACOTES[s.pacote].nota) + "</p>" +
        "<details id='f3-hipoteses'><summary>Coeficientes e hipóteses deste pacote</summary>" + tabelaDeHipoteses() + "</details>" : "") +
      (volumes ? "<label for='f3-limite'>Limite do intervalo exibido no mapa</label><select id='f3-limite'>" + opcoes([["max", "Limite superior"], ["min", "Limite inferior"]], s.limite) + "</select>" +
        "<label for='f3-p'>Chuva de referência (hipotética)</label><select id='f3-p'>" + opcoes(F.meta.precipitacoes_mm.map(function (p) { return [p, D.formatar(p) + " mm"]; }), s.p) + "</select>" +
        "<p class='small'>" + esc(TEXTOS.chuva) + "</p>" : "") +
      (s.modo === "tp" ? "<p class='small'>Posição de cada trecho pela altura que o preenchimento de depressões soma ao relevo. É um indicador relativo de propensão topográfica à retenção, calculado sobre um modelo de elevação de 30 m. Não é profundidade, volume nem duração. Não depende de pacote nem de chuva.</p>" : "") +
      (TEXTOS.modos[s.modo] ? "<p class='small' id='f3-modo-nota'>" + esc(TEXTOS.modos[s.modo]) + "</p>" : "") +
      "<p class='small' id='f3-zoom' aria-live='polite'></p>" +
      "<details id='f3-metodo'><summary>Metodologia e limitações</summary>" + TEXTOS.metodologia.map(function (m) { return "<h3>" + esc(m[0]) + "</h3><p class='small'>" + esc(m[1]) + "</p>"; }).join("") +
      "<p class='small'>Detalhes: docs/fase3_motor.md e docs/fase3_resultados.md do repositório.</p></details>";
    Array.prototype.forEach.call(box.querySelectorAll("input[name=f3-modo]"), function (i) { i.addEventListener("change", function () { s.modo = i.value; F.montarPainel(); mudou(); }); });
    var liga = function (id, campo, num) { var e = el(id); if (e) e.addEventListener("change", function () { s[campo] = num ? Number(e.value) : e.value; F.montarPainel(); mudou(); }); };
    liga("f3-pacote", "pacote"); liga("f3-limite", "limite"); liga("f3-p", "p", true);
    if (F._zoom != null) F.avisarZoom(F._zoom);
    var foco = document.activeElement && document.activeElement.id;
    if (foco && el(foco)) el(foco).focus();
  };
  F.avisarZoom = function (zoom) {
    F._zoom = zoom; var e = el("f3-zoom"); if (!e || !F.meta) return;
    e.textContent = zoom < F.meta.zoom[0] ? "Aproxime o mapa (zoom " + F.meta.zoom[0] + " ou mais): são " + D.formatar(F.meta.trechos) + " trechos e eles só são desenhados de perto." : "";
  };

  /* ------------------------------------------------------------------ painel do trecho */
  function indicador(chave, valor, extra) {
    var t = TEXTOS.indicadores[chave];
    return "<div class='f3-ind'><div class='f3-rot'>" + esc(t[0]) + " <span class='small'>(" + esc(t[1]) + ")</span></div><div class='f3-val'>" + valor + "</div>" +
      (extra ? "<div class='small'>" + extra + "</div>" : "") +
      "<details><summary>O que é e como ler</summary><p class='small'><b>O que é:</b> " + esc(t[2]) + "</p><p class='small'><b>Como ler:</b> " + esc(t[3]) + "</p></details></div>";
  }
  F.corpoDoTrecho = function (r) {
    var s = F.estado, pk = D.PACOTES[s.pacote], nome = r.nome || "Trecho sem nome no OpenStreetMap";
    var cab = "<h3>Trecho viário selecionado " + Lg.kindBadge("simulado") + "</h3><p><b>" + esc(nome) + "</b>" + (r.via ? " <span class='small'>(" + esc(r.via) + ")</span>" : "") + "<br><span class='small'>Identificador: <code>" + esc(r.id) + "</code></span></p>";
    if (r.l_m1_max == null) {
      return cab + "<p class='f3-sem' role='status'><b>Trecho sem dados disponíveis.</b> Ele está fora da grade de 30 m do modelo ou passa só por células sem dado ou de água. Isso não significa contribuição zero.</p>" +
        indicador("topo", "sem dados disponíveis") + "<p class='small'>" + esc(TEXTOS.aviso) + "</p>";
    }
    var p = s.p, ctx = "Chuva de referência hipotética de " + D.formatar(p) + " mm · " + pk.curto + " (" + pk.natureza + ")";
    var l = D.intervalo(r["l_" + s.pacote + "_min"], r["l_" + s.pacote + "_max"], p), c = D.intervalo(r["c_" + s.pacote + "_min"], r["c_" + s.pacote + "_max"], p);
    var fcob = { m1: r.f_m1, li: r.f_li, an: r.f_an }[s.pacote];
    var topo = r.topo_altura_max_m > 0 ? "posto " + D.formatar(r.topo_posto) + " de 100" : "sem preenchimento de depressão no modelo";
    var avisoCob = fcob < 0.25 ? "<p class='f3-sem small' role='note'>Menos de 25% da área a montante tem coeficiente neste pacote: o intervalo considera só uma parte da área. Leia como parcial.</p>" : "";
    var aviso_li = s.pacote === "li" ? "<p class='small'>Limites matemáticos (C = 0 e C = 1): referência, não previsão.</p>" : "";
    return cab + "<p class='small f3-ctx'>" + esc(ctx) + "</p>" +
      indicador("contrib", c ? "<b>" + esc(c.texto) + "</b>" : "sem valor", "Inclui o volume gerado sob o trecho. Não somar com outros trechos.") +
      indicador("local", l ? "<b>" + esc(l.texto) + "</b>" : "sem valor") + aviso_li +
      indicador("area", "<b>" + esc(D.area(r.area_montante_m2)) + "</b>") +
      indicador("cobertura", "<b>" + esc(D.pct(fcob)) + "</b>", "Método 1: " + esc(D.pct(r.f_m1)) + " · Analogia: " + esc(D.pct(r.f_an)) + " · Limites físicos: " + esc(D.pct(r.f_li)) + ". Sem valor na analogia: " + esc(D.pct(r.f_an_sem)) + "; fora do cálculo: " + esc(D.pct(r.f_fora)) + "; sem classe: " + esc(D.pct(r.f_sem_classe)) + ".") + avisoCob +
      indicador("topo", "<b>" + esc(topo) + "</b>", "Altura de preenchimento no modelo de elevação: " + esc(D.formatar(r.topo_altura_max_m)) + " m (grandeza do modelo, não é profundidade).") +
      "<p class='small'><b>Qualidade:</b> " + r.n_cel + " células de 30 m sob o trecho, " + r.n_cheg + " de chegada. Valores do Parquet da Fase 3, com 9 algarismos significativos; a tela mostra 3.</p>" +
      "<p class='small'>" + esc(TEXTOS.aviso) + "</p>";
  };
  F.detalhe = function (n, alvo) {
    F.selecionado = n; alvo.innerHTML = "<h2 id='h-contexto'>Seleção</h2><p class='small' role='status'>Carregando o trecho...</p>";
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
