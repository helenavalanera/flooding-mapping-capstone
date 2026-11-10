/* Dashboard: six areas organised around what a user needs to decide, for two territories. What each territory offers comes from
   Territorio (capabilities), never from tests on the region's name; what is missing is said so ("Dados indisponíveis"), not shown as
   zero. Every text from the data or the API is escaped. The mobility PWA calls the same API. */
(function () {
  "use strict";
  var Lg = window.Logic, T = window.Territorio, L_ = window.L;
  var ABAS = ["geral", "mapa", "previsao", "mobilidade", "ocorrencias", "proveniencia"];
  var st = { aba: "geral", mob: { pontos: {}, camadas: [] }, credencial: "", ultima: null, classico: false };
  var CAP_NOME = { limites_territoriais: "Limites territoriais", malha_rodoviaria: "Malha rodoviária", meteorologia: "Meteorologia", ocorrencias: "Ocorrências e bloqueios",
                   caracteristicas_fisicas: "Características físicas", mobilidade_simulada: "Mobilidade simulada", relevo_3d: "Relevo em 3D", risco_por_trecho: "Risco por trecho", rotas: "Rotas" };

  function el(id) { return document.getElementById(id); }
  function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || "GET", headers: {} };
    if (opts.body) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.body); }
    if (opts.credencial) init.headers.Authorization = "Bearer " + opts.credencial;
    return fetch("api/" + path, init).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) { if (!r.ok) throw new Error(d.erro || "HTTP " + r.status); return d; });
    });
  }
  function fail(node, e) { node.innerHTML = "<p class='aviso'>Não foi possível carregar: " + Lg.esc(e.message) + "</p>"; }
  function ul(items, cls) { return items.length ? "<ul class='" + (cls || "plain") + "'>" + items.map(function (i) { return "<li>" + i + "</li>"; }).join("") + "</ul>" : ""; }
  function legendKinds() {
    return "<div class='kinds-legend'>" + ["observado", "previsto", "simulado", "confirmado"].map(function (k) {
      return Lg.kindBadge(k) + " <span class='small'>" + Lg.esc(Lg.kind(k).hint) + "</span>"; }).join(" · ") + "</div>";
  }
  /* A capability that is off in the current territory, with its reason; "" when it is on. */
  function indisponivel(nome, titulo) {
    var s = T.status(nome);
    if (s.ativa) return "";
    return "<div class='indisp' role='note'><b>" + Lg.esc(titulo || CAP_NOME[nome]) + ": " + Lg.esc(s.rotulo) + ".</b> " + Lg.esc(s.nota) + "</div>";
  }
  function limitacoes(nomes) {
    return nomes.map(function (n) { var s = T.status(n); return s.estado === "disponivel" && s.ativa ? null : "<b>" + Lg.esc(CAP_NOME[n]) + " (" + Lg.esc(s.rotulo.toLowerCase()) + "):</b> " + Lg.esc(s.nota); }).filter(Boolean);
  }
  function irParaOutro() { var o = T.atual === "rs" ? "poa" : "rs"; return "<button type='button' class='btn sec' data-ir='" + o + "'>Abrir a demonstração de " + (o === "poa" ? "Porto Alegre" : "o Rio Grande do Sul") + "</button>"; }
  function ligarIr(box) { Array.prototype.forEach.call(box.querySelectorAll("[data-ir]"), function (b) { b.addEventListener("click", function () { T.definir(b.dataset.ir); }); }); }
  function irAba(a) { return "<button type='button' class='link' data-aba-ir='" + a + "'>abrir " + ({ mapa: "no mapa", previsao: "em Condições e previsão", mobilidade: "em Mobilidade", ocorrencias: "em Ocorrências", proveniencia: "em Proveniência" }[a]) + "</button>"; }
  function ligarAbas(box) { Array.prototype.forEach.call(box.querySelectorAll("[data-aba-ir]"), function (b) { b.addEventListener("click", function () { show(b.dataset.abaIr); }); }); }
  function hora(iso) { return iso ? Lg.formatInstant(iso) : "indisponível"; }

  /* ---------------------------------------------------------------- navegação */
  var RENDER = { geral: geral, previsao: previsao, mobilidade: mobilidade, ocorrencias: ocorrencias, proveniencia: proveniencia };
  function show(aba) {
    st.aba = aba;
    Array.prototype.forEach.call(document.querySelectorAll("#abas button"), function (b) { b.setAttribute("aria-selected", String(b.dataset.aba === aba)); });
    ABAS.forEach(function (n) { el("vista-" + n).hidden = n !== aba; });
    if (history.replaceState) history.replaceState(null, "", "#" + T.atual + "/" + aba);
    if (aba === "mapa") return abrirMapa();
    RENDER[aba]();
  }
  function marcarTerritorio() {
    Array.prototype.forEach.call(document.querySelectorAll("#territorios button"), function (b) { b.setAttribute("aria-checked", String(b.dataset.territorio === T.atual)); });
    var t = T.territorio();
    el("sub-territorio").textContent = t.nome + " · escala " + t.escala + (T.atual === "poa" && !T.online ? " · servidor de análise inativo: parte das funções fica indisponível" : "");
  }

  /* ---------------------------------------------------------------- visão geral: as cinco perguntas */
  function bloco(titulo, pergunta, corpo) { return "<section class='pergunta'><h2><span class='n'>" + pergunta + "</span> " + Lg.esc(titulo) + "</h2>" + corpo + "</section>"; }
  function entrada() {
    return "<div class='entradas'>" + ["rs", "poa"].map(function (id) {
      var t = T.territorio(id), caps = Object.keys(t.capacidades).map(function (k) { return Lg.capStatus(t.capacidades[k], T.online).estado; });
      var conta = function (e) { return caps.filter(function (x) { return x === e; }).length; };
      return "<button type='button' class='entrada" + (id === T.atual ? " atual" : "") + "' data-ir='" + id + "' aria-pressed='" + (id === T.atual) + "'><b>" + Lg.esc(t.nome) + "</b>" +
        "<span class='small'>" + (id === "rs" ? "Inteligência territorial e monitoramento regional" : "Operação urbana e mobilidade preventiva") + "</span>" +
        "<span class='small'>" + conta("disponivel") + " funcionalidades disponíveis · " + conta("parcial") + " parciais · " + conta("indisponivel") + " indisponíveis</span></button>"; }).join("") + "</div>";
  }
  function geral() {
    var box = el("vista-geral");
    box.innerHTML = "<p class='muted'>Carregando…</p>";
    (T.atual === "rs" ? geralRS : geralPOA)(box).catch(function (e) { fail(box, e); });
  }
  function geralRS(box) {
    return T.rs().then(function (d) {
      var prev = d.previsao, est = d.cobertura.estado, nb = d.bloqueios ? d.bloqueios.total : null, oc = d.ocorrencias;
      var hoje = prev ? Lg.countByClass(prev, 0) : null, ranking = prev ? Lg.rankMunicipalities(prev, 6) : [], ativos = d.bloqueios ? d.bloqueios.bloqueios : [];
      var s90 = Object.keys(d.cobertura.municipios).reduce(function (a, k) { return a + d.cobertura.municipios[k].s2id_hidrologicos_90_dias; }, 0);
      var cl = est.municipios_por_classe;
      box.innerHTML = "<h2 class='titulo'>Rio Grande do Sul · monitoramento regional</h2>" + entrada() + legendKinds() +
        bloco("O que está acontecendo?", "1", "<p>" + (hoje ? Lg.kindBadge("previsto") + " Hoje, a estimativa municipal marca <b>" + hoje.alto + "</b> município(s) em Alto e <b>" + hoje.atencao + "</b> em Atenção, de " + (prev.municipios.length) + " com estimativa. " : "<span class='indisp'>Estimativa municipal indisponível.</span> ") +
          (nb != null ? Lg.kindBadge("observado") + " <b>" + nb + "</b> bloqueio(s) ativo(s) nas rodovias (CPRv BM). " : "<span class='indisp'>Bloqueios ativos indisponíveis.</span> ") +
          (oc ? Lg.kindBadge("observado") + " <b>" + s90 + "</b> registro(s) hidrológico(s) do S2iD nos últimos 90 dias." : "") + "</p>" +
          "<p class='small'>A estimativa municipal é a probabilidade relativa de um registro de desastre hídrico, não uma previsão de alagamento em vias. " + irAba("previsao") + "</p>") +
        bloco("Onde estão os pontos de atenção?", "2", (ranking.length ? "<p class='small'>Municípios com a maior classe estimada nos próximos três dias:</p>" + ul(ranking.map(function (r) {
            return "<button class='link' data-foco='" + Lg.esc(r.ibge) + "'>" + Lg.esc(r.nome) + "</button> · " + (r.classe === "alto" ? "Alto" : "Atenção") + " · " + Lg.esc(Lg.dayLabel(r.horizonte, r.data)) + " · chuva " + Lg.mm(r.chuva_dia_mm); })) : "<p class='muted'>Nenhum município em Atenção ou Alto nos próximos três dias.</p>") +
          (ativos.length ? "<p class='small'>Bloqueios ativos (observado):</p>" + ul(ativos.slice(0, 5).map(function (b) { return Lg.esc(b.rodovia) + " " + Lg.esc(Lg.blockageSpan(b)) + " · " + Lg.esc(b.municipio) + " · " + (b.tipo === "total" ? "total" : "parcial"); })) : "") + irAba("mapa")) +
        bloco("Como as condições podem evoluir?", "3", hoje ? "<table><thead><tr><th>Dia</th><th>Alto</th><th>Atenção</th><th>Chuva máxima do dia</th></tr></thead><tbody>" + [0, 1, 2].map(function (h) {
            var c = Lg.countByClass(prev, h), dia = prev.municipios[0].dias[h]; return "<tr><td>" + Lg.esc(Lg.dayLabel(h, dia.data)) + "</td><td>" + c.alto + "</td><td>" + c.atencao + "</td><td>" + Lg.mm(c.chuva_maxima_mm) + "</td></tr>"; }).join("") + "</tbody></table>" +
          "<p class='small'>" + irAba("previsao") + "</p>" : "<p class='indisp'>Sem estimativa para os próximos dias.</p>") +
        bloco("Quais deslocamentos podem ser afetados?", "4", indisponivel("rotas", "Rotas") +
          "<p class='small'>" + Lg.kindBadge("simulado") + " O que existe em escala estadual é a simulação do fechamento de cada segmento da malha DAER. Trechos de maior efeito:</p>" +
          (d.impacto ? ul(d.impacto.ranking_pontes_populacao_isolada.slice(0, 3).map(function (r) { return Lg.esc(r.nome) + " km " + r.km_inicio + "–" + r.km_final + " · isolaria ~" + Math.round(r.pop_isolada).toLocaleString("pt-BR") + " pessoas na malha mapeada"; })) : "<p class='indisp'>Simulação indisponível.</p>") +
          "<p>" + irParaOutro() + " " + irAba("mobilidade") + "</p>") +
        bloco("Quais informações sustentam esta análise?", "5", "<p>Cobertura calculada da malha DAER (" + est.segmentos.toLocaleString("pt-BR") + " segmentos, " + Math.round(est.km).toLocaleString("pt-BR") + " km): <b>" + cl.disponivel + "</b> municípios com dados disponíveis, <b>" + cl.parcial + "</b> com cobertura parcial e <b>" + cl.insuficiente + "</b> com dados insuficientes. " +
          "O índice físico cobre " + Lg.pct(est.fracao_km_com_indice_fisico) + " do km e o tráfego (VDM), " + Lg.pct(est.fracao_km_com_vdm) + ".</p>" +
          "<p class='small'>Atualizações: chuva " + hora(prev && prev.fonte_chuva.emitido_em_utc) + " · bloqueios " + hora(d.bloqueios && d.bloqueios.coletado_em_utc) + " · S2iD até " + (oc ? Lg.esc(oc.ate.split("-").reverse().join("/")) : "indisponível") + ". " + irAba("proveniencia") + "</p>");
      ligarIr(box); ligarAbas(box);
      Array.prototype.forEach.call(box.querySelectorAll("[data-foco]"), function (b) { b.addEventListener("click", function () { st.foco = b.dataset.foco; show("mapa"); }); });
    });
  }
  function geralPOA(box) {
    if (!T.online) {
      box.innerHTML = "<h2 class='titulo'>Porto Alegre · mobilidade preventiva</h2>" + entrada() + indisponivel("meteorologia", "Condições em Porto Alegre") + indisponivel("risco_por_trecho", "Risco por trecho") +
        "<p>O relevo 3D continua disponível na aba Mapa. " + irAba("mapa") + "</p>";
      ligarIr(box); ligarAbas(box); return Promise.resolve();
    }
    return Promise.all([api("visao-geral"), api("previsao?horas=48")]).then(function (r) {
      var v = r[0], p = r[1], mx = v.maior_exposicao, c = v.ocorrencias_por_situacao;
      var pico = mx && (mx.km_alto || mx.km_atencao) ? mx : null;
      return (pico ? api("risco?h=" + Math.max(0, Math.round((new Date(pico.hora) - new Date(v.agora)) / 3600000))).catch(function () { return null; }) : Promise.resolve(null)).then(function (ris) {
        var vias = ris && !ris.sem_estimativa ? Lg.groupStreets(ris.geojson.features).slice(0, 5) : [];
        box.innerHTML = "<h2 class='titulo'>Porto Alegre · mobilidade preventiva</h2>" + entrada() + legendKinds() +
          (v.fonte_chuva.obsoleta ? "<p class='aviso'>A atualização da chuva falhou (" + Lg.esc(v.fonte_chuva.motivo_obsolescencia) + "): valores do último download válido.</p>" : "") +
          bloco("O que está acontecendo?", "1", "<p>" + Lg.kindBadge("previsto") + " Chuva prevista nas próximas 24 h: <b>" + Lg.mm(v.chuva_proximas_24h_mm) + "</b>" + (v.pico_de_chuva ? ", com pico às " + Lg.hhmm(v.pico_de_chuva.hora) + " (" + Lg.mm(v.pico_de_chuva.mm) + " em 1 h)" : "") + ". " +
            Lg.kindBadge("observado") + " <b>" + c.reportada + "</b> ocorrência(s) reportada(s), sem verificação. " + Lg.kindBadge("confirmado") + " <b>" + v.interdicoes_confirmadas_ativas + "</b> interdição(ões) confirmada(s) ativa(s).</p>") +
          bloco("Onde estão os pontos de atenção?", "2", pico ? "<p>" + Lg.kindBadge("previsto") + " Maior exposição estimada: <b>" + Lg.esc(Lg.weekdayHour(pico.hora)) + "</b>, com " + Lg.km(pico.km_alto) + " em Alto e " + Lg.km(pico.km_atencao) + " em Atenção.</p>" +
              (vias.length ? "<p class='small'>Vias com trechos em atenção nesse horário:</p>" + ul(vias.map(function (x) { return Lg.esc(x.nome) + " · " + (x.classe === "alto" ? "Alto" : "Atenção") + " · " + Lg.km(x.km); })) : "") + irAba("mapa")
            : "<p class='muted'>Nenhum trecho com risco estimado nas próximas 48 h.</p>") +
          bloco("Como as condições podem evoluir?", "3", "<p>" + (pico ? "O risco estimado acompanha a chuva e recua em até 6 horas sem chuva." : "Sem chuva relevante prevista, o risco estimado permanece baixo.") + " " + irAba("previsao") + "</p>" +
            "<p class='aviso'>" + Lg.esc(v.aviso) + " É um baseline determinístico, sem validação contra alagamentos em vias.</p>") +
          bloco("Quais deslocamentos podem ser afetados?", "4", "<p>Compare a rota habitual com alternativas de menor exposição estimada, para carro e a pé, no horário de passagem por cada trecho. " + irAba("mobilidade") + "</p>" + indisponivel("rotas", "Rotas")) +
          bloco("Quais informações sustentam esta análise?", "5", "<p class='small'>Chuva: " + Lg.esc(v.fonte_chuva.fonte.replace("https://", "")) + ", emitida em " + Lg.esc(hora(v.fonte_chuva.emitido_em_utc)) + " (uma série para a cidade inteira). " + irAba("proveniencia") + "</p>");
        ligarIr(box); ligarAbas(box);
      });
    });
  }

  /* ---------------------------------------------------------------- condições e previsão */
  /* One series per chart: solid bars were measured, hatched bars are forecast, both in the series colour. */
  function bars(rows, value, color, unit, nowIndex) {
    var w = 960, h = 130, n = rows.length, bw = w / n, hs = Lg.barHeights(rows.map(value), h - 24, unit.floor), pats = {}, body = "";
    rows.forEach(function (r, i) {
      var v = value(r), x = i * bw, c = color(r), prev = r.natureza === "previsto", id = "h" + c.replace("#", "");
      if (prev && !pats[id]) pats[id] = "<pattern id='" + id + "' width='6' height='6' patternUnits='userSpaceOnUse' patternTransform='rotate(45)'><rect width='6' height='6' fill='#fff'/><line x1='0' y1='0' x2='0' y2='6' stroke='" + c + "' stroke-width='3'/></pattern>";
      body += "<rect x='" + (x + 1) + "' y='" + (h - hs[i]) + "' width='" + Math.max(bw - 2, 1) + "' height='" + hs[i] + "' fill='" + (prev ? "url(#" + id + ")" : c) + "' stroke='" + c + "' stroke-width='1.5'" + (prev ? " stroke-dasharray='3 2'" : "") +
        "><title>" + Lg.esc(Lg.weekdayHour(r.hora)) + ": " + (v == null ? "sem estimativa" : Lg.esc(unit.fmt(v))) + " (" + Lg.esc(r.natureza) + ")</title></rect>";
      if (i % 6 === 0 && x < w - 50) body += "<text x='" + (x + 2) + "' y='" + (h + 13) + "'>" + Lg.esc(Lg.hhmm(r.hora)) + "</text>";
    });
    if (nowIndex > 0) body += "<line x1='" + nowIndex * bw + "' x2='" + nowIndex * bw + "' y1='0' y2='" + h + "' stroke='#333' stroke-dasharray='4 3'/><text x='" + (nowIndex * bw + 4) + "' y='10'>agora</text>";
    return "<svg class='chart' viewBox='0 0 " + w + " " + (h + 18) + "' role='img' aria-label='" + Lg.esc(unit.label) + "'><defs>" + Object.keys(pats).map(function (k) { return pats[k]; }).join("") + "</defs>" + body + "</svg>";
  }
  function previsao() {
    var box = el("vista-previsao");
    box.innerHTML = "<p class='muted'>Carregando…</p>";
    (T.atual === "rs" ? previsaoRS(box) : previsaoPOA(box)).catch(function (e) { fail(box, e); });
  }
  function previsaoRS(box) {
    return T.rs().then(function (d) {
      var p = d.previsao;
      if (!p) { box.innerHTML = "<h2 class='titulo'>Condições e previsão · Rio Grande do Sul</h2><p class='indisp'>Dados indisponíveis: a estimativa municipal de 72 h não foi publicada.</p>"; return; }
      var ranking = Lg.rankMunicipalities(p, 12), m = p.modelo;
      box.innerHTML = "<h2 class='titulo'>Condições e previsão · Rio Grande do Sul</h2>" + legendKinds() +
        "<p class='aviso'>Estimativa por <b>município</b> (probabilidade relativa de registro de desastre hídrico). Não é previsão de alagamento por trecho; essa funcionalidade não existe em escala estadual.</p>" +
        indisponivel("risco_por_trecho", "Risco por trecho") +
        "<h3>Distribuição por dia " + Lg.kindBadge("previsto") + "</h3><div class='rolagem'><table><thead><tr><th>Dia</th><th>Alto</th><th>Atenção</th><th>Baixo</th><th>Sem estimativa</th><th>Chuva máx. (mm)</th><th>Chuva média (mm)</th></tr></thead><tbody>" +
        [0, 1, 2].map(function (h) { var c = Lg.countByClass(p, h); return "<tr><td>" + Lg.esc(Lg.dayLabel(h, p.municipios[0].dias[h].data)) + "</td><td>" + c.alto + "</td><td>" + c.atencao + "</td><td>" + c.baixo + "</td><td>" + c.sem_estimativa + "</td><td>" + Lg.mm(c.chuva_maxima_mm) + "</td><td>" + Lg.mm(c.chuva_media_mm) + "</td></tr>"; }).join("") + "</tbody></table></div>" +
        "<p class='small'>Chuva do dia: série do modelo de previsão (Open-Meteo), emitida em " + Lg.esc(hora(p.fonte_chuva.emitido_em_utc)) + ". Os valores diários incluem horas já ocorridas e horas previstas.</p>" +
        "<h3>Municípios em maior classe</h3>" + (ranking.length ? "<div class='rolagem'><table><thead><tr><th>Município</th><th>Classe</th><th>Dia</th><th>Chuva do dia</th><th>Chuva em 3 dias</th></tr></thead><tbody>" + ranking.map(function (r) {
            return "<tr><td><button class='link' data-foco='" + Lg.esc(r.ibge) + "'>" + Lg.esc(r.nome) + "</button></td><td>" + (r.classe === "alto" ? "Alto" : "Atenção") + "</td><td>" + Lg.esc(Lg.dayLabel(r.horizonte, r.data)) + "</td><td>" + Lg.mm(r.chuva_dia_mm) + "</td><td>" + Lg.mm(r.chuva_3d_mm) + "</td></tr>"; }).join("") + "</tbody></table></div>" : "<p class='muted'>Nenhum município em Atenção ou Alto.</p>") +
        "<details><summary>Modelo, qualidade e limites</summary><p class='small'><b>" + Lg.esc(m.descricao) + "</b> (versão " + Lg.esc(m.versao) + "; ajustado de " + Lg.esc(m.treinado_desde) + " a " + Lg.esc(m.treinado_ate) + "). <b>Estado:</b> " + Lg.esc(m.estado) + ". " +
        (m.estado_do_modelo_de_aprendizado_de_maquina ? "<b>Modelo de aprendizado de máquina:</b> " + Lg.esc(m.estado_do_modelo_de_aprendizado_de_maquina) + "." : "") + "</p>" + ul(p.avisos.map(Lg.esc), "plain") + "</details>";
      Array.prototype.forEach.call(box.querySelectorAll("[data-foco]"), function (b) { b.addEventListener("click", function () { st.foco = b.dataset.foco; show("mapa"); }); });
    });
  }
  function previsaoPOA(box) {
    if (!T.online) { box.innerHTML = "<h2 class='titulo'>Condições e previsão · Porto Alegre</h2>" + indisponivel("meteorologia", "Chuva horária") + indisponivel("risco_por_trecho", "Risco por trecho"); return Promise.resolve(); }
    return api("previsao?horas=48").then(function (p) {
      var rows = p.horas, now = rows.findIndex(function (r) { return r.natureza === "previsto"; }), pk = p.hora_de_maior_exposicao;
      box.innerHTML = "<h2 class='titulo'>Condições e previsão · Porto Alegre</h2>" + legendKinds() +
        "<p class='small'>Barras sólidas = horas até agora (" + Lg.kindBadge("observado") + "); tracejadas = horas à frente (" + Lg.kindBadge("previsto") + "). A chuva é uma série para a cidade inteira.</p>" +
        "<h3>Chuva por hora</h3>" + bars(rows, function (r) { return r.chuva_hora_mm; }, function () { return "#1f6fb2"; }, { label: "Chuva por hora (mm)", floor: 5, fmt: Lg.mm }, now) +
        "<h3>Risco estimado por trecho: km de via em classe Alto " + Lg.kindBadge("previsto") + "</h3>" + bars(rows, function (r) { return r.km_alto; }, function () { return "#b3202a"; }, { label: "Km em classe Alto", floor: 1, fmt: Lg.km }, now) +
        "<h3>Km de via em classe Atenção</h3>" + bars(rows, function (r) { return r.km_atencao; }, function () { return "#c27a00"; }, { label: "Km em classe Atenção", floor: 1, fmt: Lg.km }, now) +
        (pk && (pk.km_alto || pk.km_atencao) ? "<p><b>Hora de maior exposição estimada:</b> " + Lg.weekdayHour(pk.hora) + " · " + Lg.km(pk.km_alto) + " em Alto, " + Lg.km(pk.km_atencao) + " em Atenção.</p>" : "<p>Nenhuma hora com trechos em Atenção ou Alto nas próximas 48 h.</p>") +
        "<p class='aviso'>" + Lg.esc(p.natureza) + ". Horas sem janela completa de chuva ficam sem estimativa (barra vazia), não em risco baixo.</p>" +
        "<details><summary>Metodologia e limites</summary><p>" + Lg.esc(p.metodo) + "</p>" + ul(p.limites.map(Lg.esc)) + "</details>";
    });
  }

  /* ---------------------------------------------------------------- contexto do mapa */
  function ocorrenciasDoMunicipio(d, nome, ibge) {
    return { s2id: ((d.ocorrencias && d.ocorrencias.registros) || []).filter(function (r) { return r.ibge === ibge; }),
             bloqueios: ((d.bloqueios && d.bloqueios.bloqueios) || []).filter(function (b) { return Lg.norm(b.municipio) === Lg.norm(nome); }) };
  }
  function atualizacoes(d) {
    return "<p class='small'>Última atualização: chuva " + Lg.esc(hora(d.previsao && d.previsao.fonte_chuva.emitido_em_utc)) + " · bloqueios " + Lg.esc(hora(d.bloqueios && d.bloqueios.coletado_em_utc)) +
      " · S2iD até " + (d.ocorrencias ? Lg.esc(d.ocorrencias.ate.split("-").reverse().join("/")) : "indisponível") + ".</p>";
  }
  function contextoMunicipio(ibge, alvo) {
    T.rs().then(function (d) {
      var f = d.municipios.features.filter(function (x) { return x.properties.ibge === ibge; })[0], p = f.properties, c = d.cobertura.municipios[ibge], prev = d.prevPorIbge[ibge], o = ocorrenciasDoMunicipio(d, p.nome, ibge);
      alvo.innerHTML = "<h2 id='h-contexto'>" + Lg.esc(p.nome) + "</h2><p>" + Lg.classBadge(c.classe) + "</p><p class='small'>" + Lg.esc(c.motivo) + "</p>" +
        "<p class='small'>Código IBGE " + Lg.esc(p.ibge) + " · população " + p.populacao.toLocaleString("pt-BR") + " · região imediata " + Lg.esc(p.regiao_imediata) + "</p>" +
        "<h3>Dados disponíveis</h3>" + Lg.dimensions(c.dimensoes) +
        "<h3>Malha rodoviária DAER</h3>" + (c.km > 0 ? "<p class='small'>" + c.segmentos + " segmentos · " + Lg.km(c.km) + ". Com índice físico: " + Lg.pct(c.km_com_indice_fisico / c.km) + " do km. Com tráfego (VDM): " + Lg.pct(c.km_com_vdm / c.km) + " do km (o restante é <b>sem dado</b>, não tráfego zero)." +
          (c.pontes ? " " + Lg.kindBadge("simulado") + " " + c.pontes + " segmento(s)-ponte na simulação." : "") + "</p>" : "<p class='indisp'>Sem malha DAER mapeada: as funcionalidades viárias estão indisponíveis neste município.</p>") +
        "<h3>Ocorrências " + Lg.kindBadge("observado") + "</h3><p class='small'>Registros hidrológicos do S2iD: <b>" + c.s2id_hidrologicos_2017_2026 + "</b> em 2017–2026, <b>" + c.s2id_hidrologicos_90_dias + "</b> nos últimos 90 dias. Registros de decreto são municipais e não têm geometria.</p>" +
        ul(o.s2id.slice(0, 4).map(function (r) { return Lg.esc(r.data.split("-").reverse().join("/")) + " · " + Lg.esc(r.tipo) + " (" + Lg.esc(r.status) + ")"; })) +
        (o.bloqueios.length ? "<p class='small'><b>" + o.bloqueios.length + "</b> bloqueio(s) ativo(s):</p>" + ul(o.bloqueios.map(function (b) { return Lg.esc(b.rodovia) + " " + Lg.esc(Lg.blockageSpan(b)) + " · " + (b.tipo === "total" ? "total" : "parcial"); })) : "<p class='small'>Nenhum bloqueio ativo neste município.</p>") +
        "<h3>Estimativa municipal 72 h " + Lg.kindBadge("previsto") + "</h3>" + (prev ? "<table><thead><tr><th>Dia</th><th>Chuva</th><th>Classe</th></tr></thead><tbody>" + prev.dias.map(function (x) {
            return "<tr><td>" + Lg.esc(Lg.dayLabel(x.horizonte_dias, x.data)) + "</td><td>" + Lg.mm(x.chuva_dia_mm) + "</td><td>" + Lg.esc(Lg.CLASS_LABEL[x.classe]) + "</td></tr>"; }).join("") + "</tbody></table><p class='small'>Probabilidade relativa de registro de desastre hídrico; não é previsão em vias.</p>"
          : "<p class='indisp'>Sem estimativa: faltam dados de chuva completos para este município.</p>") +
        atualizacoes(d) + "<h3>Limitações</h3>" + ul(limitacoes(["ocorrencias", "meteorologia", "risco_por_trecho", "rotas"]), "plain small");
    }).catch(function (e) { fail(alvo, e); });
  }
  function contextoRodovia(p, alvo) {
    T.rs().then(function (d) {
      var c = d.cobertura.rodovias[p.nome], bl = ((d.bloqueios && d.bloqueios.bloqueios) || []).filter(function (b) { return b.rodovia === p.nome; });
      alvo.innerHTML = "<h2 id='h-contexto'>" + Lg.esc(p.nome) + "</h2>" + (c ? "<p>" + Lg.classBadge(c.classe) + "</p><p class='small'>" + Lg.esc(c.motivo) + "</p>" : "") +
        "<p class='small'>" + (c ? Lg.esc(c.rede.toLowerCase()) + " · " + c.trechos + " trecho(s) · " + c.segmentos + " segmentos · " + Lg.km(c.km) + " · atravessa " + c.municipios_atravessados + " município(s)" : "Sem resumo de cobertura para esta rodovia.") + "</p>" +
        (c ? "<h3>Dados disponíveis</h3>" + Lg.dimensions(c.dimensoes) + "<p class='small'>Índice físico em " + Lg.pct(c.km_com_indice_fisico / c.km) + " do km · tráfego (VDM) em " + Lg.pct(c.km_com_vdm / c.km) + " (o restante é sem dado, não tráfego zero).</p>" : "") +
        "<h3>Trecho selecionado " + Lg.esc(p.codigo_sre) + "</h3><p class='small'>km " + p.km_inicio + " a " + p.km_final + " · VDM " + (p.vdm == null ? "<b>sem dado</b>" : Math.round(p.vdm).toLocaleString("pt-BR") + " veículos/dia") + " · índice físico " +
        (p.indice_fisico == null ? "<b>sem dado</b>" : "percentil " + Math.round(p.indice_fisico) + " (relativo, não é probabilidade)") + ".</p>" +
        "<p class='small'>" + Lg.kindBadge("simulado") + " Se este trecho fechasse: " + (p.ponte ? "dividiria a malha mapeada" + (p.pop_isolada ? ", isolando ~" + Math.round(p.pop_isolada).toLocaleString("pt-BR") + " pessoas" : "") : (p.desvio_km == null ? "sem cálculo de desvio" : "desvio de " + Math.round(p.desvio_km) + " km")) + " (vias municipais ausentes tornam algumas 'pontes' falta de alternativa mapeada).</p>" +
        "<h3>Ocorrências " + Lg.kindBadge("observado") + "</h3>" + (bl.length ? ul(bl.map(function (b) { return Lg.esc(Lg.blockageSpan(b)) + " · " + Lg.esc(b.municipio) + " · " + (b.tipo === "total" ? "total" : "parcial") + " · desde " + Lg.esc(Lg.formatInstant(b.desde)); })) : "<p class='small'>Nenhum bloqueio ativo nesta rodovia.</p>") +
        atualizacoes(d) + "<h3>Limitações</h3>" + ul(limitacoes(["malha_rodoviaria", "caracteristicas_fisicas", "mobilidade_simulada", "risco_por_trecho"]), "plain small");
    }).catch(function (e) { fail(alvo, e); });
  }
  function bloco2(titulo, kind, corpo) { return "<h3>" + Lg.esc(titulo) + " " + (kind ? Lg.kindBadge(kind) : "") + "</h3>" + corpo; }
  function segmento(id, alvo) {
    alvo.innerHTML = "<h2 id='h-contexto'>Trecho de rua</h2><p class='muted'>Carregando trecho…</p>";
    api("trecho?id=" + encodeURIComponent(id)).then(function (t) {
      var f = t.caracteristicas_fisicas, impacto = t.impacto_simulado_do_fechamento, pk = t.hora_de_maior_exposicao;
      var barras = t.risco_por_hora.map(function (h) { return { hora: h.hora, natureza: h.natureza, v: h.escore, classe: h.classe }; });
      var graf = bars(barras, function (r) { return r.v; }, function (r) { return r.classe === "alto" ? "#b3202a" : (r.classe === "atencao" ? "#c27a00" : "#7c8b95"); },
        { label: "Escore de risco por hora", floor: 0.4, fmt: function (v) { return v.toFixed(2).replace(".", ","); } }, barras.findIndex(function (r) { return r.natureza === "previsto"; }));
      var sim = function (m, nome) { var i = impacto[m]; return "<li>" + nome + ": " + (!i.na_rede ? "fora da rede deste modal" : (i.sem_alternativa_proxima ? "sem alternativa mapeada em " + i.raio_km + " km" : "desvio de " + Lg.minutes(i.desvio_s / 60) + " (+" + Lg.km(i.desvio_km) + ")")) + "</li>"; };
      alvo.innerHTML = "<h2 id='h-contexto'>" + Lg.esc(t.nome || "Via sem nome") + "</h2><p class='small'>" + Lg.esc(t.classe_via) + " · " + Math.round(t.comprimento_m) + " m" + (t.interditado ? " · " + Lg.kindBadge("confirmado") + " interditado" : "") + "</p>" +
        bloco2("Risco por hora (24 h)", "previsto", graf + (pk ? "<p class='small'>Maior exposição: " + Lg.weekdayHour(pk.hora) + " (escore " + pk.escore.toFixed(2).replace(".", ",") + ", " + Lg.esc(pk.classe) + ").</p>" : "<p class='small'>Sem estimativa nas próximas 24 h.</p>")) +
        bloco2("Terreno", "observado", "<p class='small'>Cota " + (f.elev == null ? "sem dado" : f.elev + " m") + " · relevo local " + (f.rel_elev_250 == null ? "—" : f.rel_elev_250 + " m") + " · declividade " + (f.slope == null ? "—" : f.slope + "°") + " · altura sobre a água " + (f.height_above_water == null ? "—" : f.height_above_water + " m") +
          ".<br>Índice físico: " + (f.percentil == null ? "<b>sem dado</b> (sem estimativa, não é risco baixo)" : "percentil " + Math.round(f.percentil) + " (relativo, não é probabilidade)") + ".</p>") +
        bloco2("Ocorrências próximas", "observado", t.ocorrencias_proximas.length ? ul(t.ocorrencias_proximas.map(function (o) { return "<span class='sit " + Lg.esc(o.situacao) + "'>" + Lg.esc(o.situacao) + "</span> · " + Lg.esc(o.tipo) + " · " + Lg.esc(o.fonte) + " · confiab. " + Lg.esc(o.confiabilidade); })) : "<p class='small'>Nenhuma ocorrência ativa a 100 m.</p>") +
        bloco2("Se este trecho fechasse", "simulado", "<ul class='plain'>" + sim("carro", "Carro") + sim("pe", "A pé") + "</ul>") +
        "<details><summary>Metodologia e limites</summary><p class='small'>" + Lg.esc(t.metodo) + "</p>" + ul(t.limites.map(Lg.esc), "plain small") + "</details>";
    }).catch(function (e) { fail(alvo, e); });
  }

  /* ---------------------------------------------------------------- mapa (3D por padrão; clássico como alternativa 2D) */
  function abrirMapa() {
    var gl = window.Mapa && window.Mapa.webglOk();
    if (!gl || st.classico) return abrirClassico(!gl ? "Este navegador não oferece WebGL: usando o mapa clássico (2D)." : "");
    el("mapa-3d").hidden = false; el("mapa-classico").hidden = true;
    window.Mapa.iniciar().then(function () {
      window.Mapa.redimensionar();
      if (T.atual === "poa") window.Mapa.recarregarPoa();
      if (st.rotasNoMapa) { var a = st.rotasNoMapa; st.rotasNoMapa = null; window.Mapa.mostrarRotas(a, "habitual"); }
      if (st.foco) { var f = st.foco; st.foco = null; window.Mapa.focarMunicipio(f); }
    }).catch(function (e) { abrirClassico("Não foi possível iniciar o mapa 3D (" + e.message + "): usando o mapa clássico (2D)."); });
  }
  function abrirClassico(aviso) {
    st.classico = true;
    el("mapa-3d").hidden = true; el("mapa-classico").hidden = false;
    var b = el("banner"); b.textContent = aviso || ""; b.hidden = !aviso;
    if (T.atual === "poa") { b.textContent = "O mapa clássico mostra só o Rio Grande do Sul. Para Porto Alegre, use o mapa 3D/2D (precisa de WebGL) ou a aba Mobilidade."; b.hidden = false; }
    window.iniciarMapaClassico();
    setTimeout(function () { window.FloodingMap && window.FloodingMap.invalidateSize(); }, 0);
  }

  /* ---------------------------------------------------------------- mobilidade */
  var mobMap = null;
  function mobilidade() {
    var box = el("vista-mobilidade");
    if (T.atual === "rs") return mobilidadeRS(box);
    if (!T.online) { box.innerHTML = "<h2 class='titulo'>Mobilidade · Porto Alegre</h2>" + indisponivel("rotas", "Rotas") + indisponivel("mobilidade_simulada", "Impacto simulado"); return; }
    var agora = new Date(Date.now() - new Date().getTimezoneOffset() * 60000 + 5 * 60000).toISOString().slice(0, 16);
    box.innerHTML = "<h2 class='titulo'>Mobilidade · Porto Alegre</h2>" + legendKinds() +
      "<p class='small'>Clique no mapa para marcar a origem e depois o destino. As rotas comparam <b>tempo</b> e <b>exposição ao risco estimado</b> no horário de passagem de cada trecho; nenhuma rota é apresentada como segura. " + Lg.esc(T.status("rotas").nota) + "</p>" +
      "<div class='form-linha'><label>Marcar<select id='mob-marcar'><option value='origem'>Origem</option><option value='destino'>Destino</option></select></label>" +
      "<label>Modal<select id='mob-modal'><option value='carro'>Carro</option><option value='pe'>A pé</option></select></label>" +
      "<label>Saída<input type='datetime-local' id='mob-saida' value='" + agora + "'></label><button class='btn' id='mob-analisar'>Analisar rotas</button></div>" +
      "<div id='mapa-rotas' role='application' aria-label='Mapa para marcar origem e destino'></div><div id='mob-resultado' aria-live='polite'></div>" +
      "<h2>Vias potencialmente comprometidas</h2><div class='form-linha'><label>Horizonte<select id='mob-h'>" + [0, 3, 6, 12, 24, 36, 48].map(function (h) { return "<option value='" + h + "'>" + (h ? "+" + h + " h" : "agora") + "</option>"; }).join("") + "</select></label></div><div id='mob-vias'></div>";
    if (mobMap) mobMap.remove();
    st.mob.pontos = {}; st.mob.camadas = [];
    mobMap = L_.map("mapa-rotas").setView([-30.03, -51.22], 12);
    L_.tileLayer(("https://tile.openstreetmap.org/{z}/{x}/{y}.png"), { maxZoom: 18, attribution: "&copy; colaboradores do OpenStreetMap" }).addTo(mobMap);
    mobMap.on("click", function (e) {
      var tipo = el("mob-marcar").value;
      if (st.mob.pontos[tipo]) mobMap.removeLayer(st.mob.pontos[tipo]);
      st.mob.pontos[tipo] = L_.circleMarker(e.latlng, { radius: 9, color: "#fff", weight: 2, fillColor: tipo === "origem" ? "#1b7f5c" : "#b3202a", fillOpacity: 1 }).bindTooltip(tipo === "origem" ? "Origem" : "Destino", { permanent: true, direction: "top" }).addTo(mobMap);
      st.mob[tipo] = { lon: e.latlng.lng, lat: e.latlng.lat };
      if (tipo === "origem") el("mob-marcar").value = "destino";
    });
    el("mob-analisar").addEventListener("click", analisar);
    el("mob-h").addEventListener("change", vias); vias();
  }
  function mobilidadeRS(box) {
    T.rs().then(function (d) {
      var i = d.impacto;
      box.innerHTML = "<h2 class='titulo'>Mobilidade · Rio Grande do Sul</h2>" + legendKinds() + indisponivel("rotas", "Rotas") + indisponivel("risco_por_trecho", "Risco por trecho") +
        "<h3>Impacto simulado do fechamento de trechos da malha DAER " + Lg.kindBadge("simulado") + "</h3>" +
        (i ? "<p class='aviso'>" + Lg.esc(i.natureza) + ". " + Lg.esc(i.limites[0]) + "</p><h3>Segmentos-ponte que mais isolariam população</h3><div class='rolagem'><table><thead><tr><th>Rodovia</th><th>Km</th><th>Pessoas isoladas na malha</th><th>VDM</th></tr></thead><tbody>" +
          i.ranking_pontes_populacao_isolada.slice(0, 10).map(function (r) { return "<tr><td>" + Lg.esc(r.nome) + " (" + Lg.esc(r.codigo_sre) + ")</td><td>" + r.km_inicio + "–" + r.km_final + "</td><td>" + Math.round(r.pop_isolada).toLocaleString("pt-BR") + "</td><td>" + (r.vdm == null ? "sem dado" : Math.round(r.vdm).toLocaleString("pt-BR")) + "</td></tr>"; }).join("") + "</tbody></table></div>" +
          "<p class='small'>VDM disponível em " + Lg.pct(i.cobertura.fracao_com_vdm) + " dos segmentos; VDM ausente fica fora do ranking ponderado, não vale zero.</p>" : "<p class='indisp'>Simulação indisponível.</p>") +
        "<p>" + irParaOutro() + "</p>";
      ligarIr(box);
    }).catch(function (e) { fail(box, e); });
  }
  function analisar() {
    var out = el("mob-resultado");
    if (!st.mob.origem || !st.mob.destino) { out.innerHTML = "<p class='aviso'>Marque a origem e o destino no mapa.</p>"; return; }
    out.innerHTML = "<p class='muted'>Calculando rotas…</p>";
    api("rotas", { method: "POST", body: { origem: st.mob.origem, destino: st.mob.destino, modal: el("mob-modal").value, saida: el("mob-saida").value } }).then(function (a) {
      st.ultima = a;
      st.mob.camadas.forEach(function (l) { mobMap.removeLayer(l); }); st.mob.camadas = [];
      Object.keys(a.rotas).reverse().forEach(function (n) {
        var s = Lg.ROUTE_STYLE[n];
        st.mob.camadas.push(L_.polyline(a.rotas[n].coordenadas.map(function (c) { return [c[1], c[0]]; }), { color: s.color, weight: n === "habitual" ? 6 : 4, dashArray: s.dash, opacity: 0.9 }).addTo(mobMap));
      });
      a.rotas.habitual.trechos_de_risco.forEach(function (t) {
        if (t.coordenadas) st.mob.camadas.push(L_.polyline(t.coordenadas.map(function (c) { return [c[1], c[0]]; }), { color: "#b3202a", weight: 9, opacity: 0.55, dashArray: "2 6" }).addTo(mobMap));
      });
      mobMap.fitBounds(L_.polyline(a.rotas.habitual.coordenadas.map(function (c) { return [c[1], c[0]]; })).getBounds().pad(0.25));
      var linhas = a.comparacao.map(function (c) {
        var r = a.rotas[c.rota];
        return "<tr><td><span class='sw line' style='border-color:" + Lg.ROUTE_STYLE[c.rota].color + ";width:26px;display:inline-block'></span> " + Lg.esc(r.rotulo) + "</td><td>" + Lg.minutes(c.tempo_min) + "</td><td>" + Lg.extraMinutes(c.acrescimo_min) + "</td><td>" + Lg.esc(c.rotulo) + "</td><td>" + Lg.km(c.km_atencao_ou_alto) +
          "</td><td>" + (c.pct_sem_estimativa ? c.pct_sem_estimativa + "% sem dado" : "—") + "</td><td>" + (r.instante_do_pico ? Lg.hhmm(r.instante_do_pico) : "—") + "</td></tr>"; }).join("");
      out.innerHTML = "<div class='alerta " + Lg.esc(a.alerta.nivel) + "'><h3>" + Lg.esc(a.alerta.titulo) + " " + Lg.kindBadge("previsto") + "</h3><p>" + Lg.esc(a.alerta.texto) + "</p>" + (a.alerta.motivos.length ? ul(a.alerta.motivos.map(Lg.esc)) : "") + "</div>" +
        "<div class='rolagem'><table><thead><tr><th>Rota</th><th>Tempo</th><th>Diferença</th><th>Exposição estimada</th><th>Km em Atenção/Alto</th><th>Trajeto sem dado de terreno</th><th>Pico</th></tr></thead><tbody>" + linhas + "</tbody></table></div>" +
        "<p class='small'>Chuva na janela da viagem: " + Lg.mm(a.meteo.total_na_janela_mm) + ". Interdições confirmadas consideradas: " + a.interdicoes_consideradas + ".</p>" +
        "<p><button class='btn sec' id='mob-explicar'>Explicar com mais contexto</button> " + (window.Mapa && window.Mapa.webglOk() ? "<button class='btn sec' id='mob-3d'>Ver as rotas no mapa 3D</button>" : "") + " <span id='mob-explicacao'></span></p>" +
        "<details><summary>Trechos de atenção da rota habitual</summary>" + ul(a.rotas.habitual.trechos_de_risco.map(function (t) { return Lg.esc(t.nome || "via sem nome") + " · " + Lg.esc(t.classe) + " · " + Lg.km(t.km) + " · passagem " + Lg.hhmm(t.inicio) + "–" + Lg.hhmm(t.fim); })) + "</details>" + ul(a.avisos.map(Lg.esc), "plain small");
      el("mob-explicar").addEventListener("click", function () {
        var alvo = el("mob-explicacao"); alvo.textContent = "consultando…";
        api("explicacao", { method: "POST", body: { analise_id: a.analise_id, contextualizar: true } }).then(function (e) {
          alvo.innerHTML = "<br>" + Lg.esc(e.texto) + " <span class='small'>(" + (e.origem === "deterministico" ? "texto padrão" + (e.motivo === "nao_configurado" ? ": provedor de linguagem não configurado" : "") : "contextualizado por provedor de linguagem externo, a partir de resumos agregados") + ")</span>";
        }).catch(function (x) { alvo.textContent = x.message; });
      });
      if (el("mob-3d")) el("mob-3d").addEventListener("click", function () { st.rotasNoMapa = a; show("mapa"); });
    }).catch(function (e) { out.innerHTML = "<p class='aviso'>" + Lg.esc(e.message) + "</p>"; });
  }
  function vias() {
    var box = el("mob-vias");
    api("risco?h=" + el("mob-h").value).then(function (r) {
      var g = r.sem_estimativa ? [] : Lg.groupStreets(r.geojson.features).slice(0, 15);
      box.innerHTML = r.sem_estimativa ? "<p class='muted'>Sem estimativa para este horário.</p>" : (g.length ? "<p class='small'>" + Lg.kindBadge(r.natureza) + " Vias com trechos em Atenção ou Alto às " + Lg.weekdayHour(r.hora) + ":</p><div class='rolagem'><table><thead><tr><th>Via</th><th>Classe</th><th>Km</th><th>Trechos</th></tr></thead><tbody>" +
        g.map(function (x) { return "<tr><td>" + Lg.esc(x.nome) + "</td><td>" + (x.classe === "alto" ? "Alto" : "Atenção") + "</td><td>" + Lg.km(x.km) + "</td><td>" + x.n + "</td></tr>"; }).join("") + "</tbody></table></div>" : "<p class='muted'>Nenhuma via em Atenção ou Alto neste horário.</p>");
    }).catch(function (e) { fail(box, e); });
  }

  /* ---------------------------------------------------------------- ocorrências */
  function ocorrencias() {
    var box = el("vista-ocorrencias");
    box.innerHTML = "<p class='muted'>Carregando…</p>";
    (T.atual === "rs" ? ocorrenciasRS(box) : ocorrenciasPOA(box)).catch(function (e) { fail(box, e); });
  }
  function ocorrenciasRS(box) {
    return T.rs().then(function (d) {
      var s = (d.ocorrencias && d.ocorrencias.registros) || [], b = (d.bloqueios && d.bloqueios.bloqueios) || [];
      box.innerHTML = "<h2 class='titulo'>Ocorrências · Rio Grande do Sul</h2>" + legendKinds() +
        "<p class='aviso'>Aqui há registros oficiais de terceiros, não relatos de usuários: a classificação reportada, confirmada ou descartada vale para os relatos de Porto Alegre. " + irParaOutro() + "</p>" +
        "<h3>Bloqueios ativos em rodovias " + Lg.kindBadge("observado") + "</h3>" + (d.bloqueios ? "<p class='small'>Fonte: CPRv BM, coletado em " + Lg.esc(hora(d.bloqueios.coletado_em_utc)) + ". Confiabilidade: informação oficial sem histórico anterior ao início da coleta.</p>" +
          (b.length ? "<div class='rolagem'><table><thead><tr><th>Rodovia</th><th>Trecho</th><th>Município</th><th>Tipo</th><th>Desde</th><th>Casamento com a malha</th></tr></thead><tbody>" + b.map(function (x) {
            return "<tr><td>" + Lg.esc(x.rodovia) + "</td><td>" + Lg.esc(Lg.blockageSpan(x)) + "</td><td>" + Lg.esc(x.municipio) + "</td><td>" + (x.tipo === "total" ? "total" : "parcial") + (x.climatico ? " · climático" : "") + "</td><td>" + Lg.esc(Lg.formatInstant(x.desde)) + "</td><td>" + Lg.esc((x.casamento || {}).status || "sem casamento") + "</td></tr>"; }).join("") + "</tbody></table></div>" : "<p class='muted'>Nenhum bloqueio ativo.</p>") : "<p class='indisp'>Dados indisponíveis: a fonte não respondeu na última coleta.</p>") +
        "<h3>Registros hidrológicos do S2iD (últimos " + (d.ocorrencias ? d.ocorrencias.janela_dias : "—") + " dias) " + Lg.kindBadge("observado") + "</h3>" + (d.ocorrencias ? "<p class='small'>Fonte: S2iD/MIDR. Confiabilidade: registro de decreto, municipal, sem geometria e com atraso e viés de notificação. Até " + Lg.esc(d.ocorrencias.ate.split("-").reverse().join("/")) + ".</p>" +
          "<div class='rolagem'><table><thead><tr><th>Município</th><th>Data</th><th>Tipo</th><th>Situação</th></tr></thead><tbody>" + s.slice(0, 80).map(function (x) {
            return "<tr><td><button class='link' data-foco='" + Lg.esc(x.ibge) + "'>" + Lg.esc(x.nome) + "</button></td><td>" + Lg.esc(x.data.split("-").reverse().join("/")) + "</td><td>" + Lg.esc(x.tipo) + "</td><td>" + Lg.esc(x.status) + "</td></tr>"; }).join("") + "</tbody></table></div>" +
          (s.length > 80 ? "<p class='small'>Mostrando 80 de " + s.length + " registros.</p>" : "") : "<p class='indisp'>Dados indisponíveis.</p>");
      ligarIr(box);
      Array.prototype.forEach.call(box.querySelectorAll("[data-foco]"), function (x) { x.addEventListener("click", function () { st.foco = x.dataset.foco; show("mapa"); }); });
    });
  }
  function ocorrenciasPOA(box) {
    if (!T.online) { box.innerHTML = "<h2 class='titulo'>Ocorrências · Porto Alegre</h2>" + indisponivel("ocorrencias", "Ocorrências"); return Promise.resolve(); }
    return api("ocorrencias", { credencial: st.credencial }).then(function (d) {
      var linhas = d.ocorrencias.map(function (o) {
        return "<tr data-sit='" + Lg.esc(o.situacao) + "'><td><span class='sit " + Lg.esc(o.situacao) + "'>" + Lg.esc(o.situacao) + "</span></td><td>" + Lg.esc(o.tipo) + "</td><td>" + Lg.esc(o.fonte) + "</td><td>" + Lg.esc(o.confiabilidade) + "</td><td>" + Lg.esc(o.impacto_circulacao) +
          "</td><td>" + Lg.esc(Lg.formatInstant(o.data_hora)) + "</td><td class='small'>" + Lg.esc(o.origem) + " · " + o.historico.length + " registro(s)" + (d.texto_livre_incluido && o.descricao ? "<br><i>" + Lg.esc(o.descricao) + "</i>" : "") + "</td><td>" + (o.situacao === "descartada" ? "" : "<button class='btn sec' data-id='" + Lg.esc(o.id) + "'>Revisar</button>") + "</td></tr>"; }).join("");
      box.innerHTML = "<h2 class='titulo'>Ocorrências · Porto Alegre</h2>" + legendKinds() + "<p class='aviso'>" + Lg.esc(d.natureza) + ". Um relato nunca interdita uma via; só a confirmação por operador, com evidência escrita, o faz. O texto livre dos relatos só aparece para o operador.</p>" +
        "<div class='form-linha'><label>Situação <select id='oc-filtro'><option value=''>todas</option><option>reportada</option><option>confirmada</option><option>descartada</option></select></label><span class='small'>" + d.total + " registro(s)</span>" +
        "<label>Credencial do operador<input type='password' id='op-cred' autocomplete='off' value='" + Lg.esc(st.credencial) + "'></label><button class='btn sec' id='op-ok'>Entrar como operador</button></div><p class='small' id='op-msg'></p>" +
        (d.total ? "<div class='rolagem'><table id='oc-tabela'><thead><tr><th>Situação</th><th>Tipo</th><th>Fonte</th><th>Confiabilidade</th><th>Impacto</th><th>Data/hora</th><th>Origem do registro</th><th></th></tr></thead><tbody>" + linhas + "</tbody></table></div>" : "<p class='muted'>Nenhuma ocorrência registrada.</p>") + "<div id='oc-revisao'></div>";
      el("oc-filtro").addEventListener("change", function (e) { Array.prototype.forEach.call(document.querySelectorAll("#oc-tabela tbody tr"), function (tr) { tr.hidden = e.target.value && tr.dataset.sit !== e.target.value; }); });
      el("op-ok").addEventListener("click", function () { st.credencial = el("op-cred").value; ocorrencias(); });
      Array.prototype.forEach.call(box.querySelectorAll("button[data-id]"), function (b) { b.addEventListener("click", function () { revisar(b.dataset.id); }); });
    }).catch(function (e) { st.credencial = ""; throw e; });
  }
  function revisar(id) {
    el("oc-revisao").innerHTML = "<div class='card'><h3>Revisar ocorrência (operador)</h3><div class='form-linha'><label>Nova situação<select id='rv-sit'><option value='confirmada'>Confirmar</option><option value='descartada'>Descartar</option></select></label>" +
      "<label>Confiabilidade<select id='rv-conf'><option value='alta'>alta</option><option value='media'>média</option><option value='baixa'>baixa</option></select></label></div>" +
      "<label>Evidência (mín. 10 caracteres)<br><textarea id='rv-ev' rows='3' cols='60' maxlength='280'></textarea></label><p><button class='btn' id='rv-ok'>Registrar</button> <span id='rv-msg' class='small'></span></p></div>";
    el("rv-ok").addEventListener("click", function () {
      api("ocorrencias/" + encodeURIComponent(id), { method: "POST", credencial: st.credencial, body: { situacao: el("rv-sit").value, confiabilidade: el("rv-conf").value, evidencia: el("rv-ev").value } })
        .then(function () { ocorrencias(); }).catch(function (e) { el("rv-msg").textContent = e.message; });
    });
  }

  /* ---------------------------------------------------------------- proveniência */
  function matriz() {
    var rs = T.territorio("rs"), poa = T.territorio("poa");
    var cel = function (t, k) { var s = Lg.capStatus(t.capacidades[k], T.online); return "<td><b>" + Lg.esc(s.rotulo) + "</b><br><span class='small'>" + Lg.esc(s.nota) + "</span></td>"; };
    return "<div class='rolagem'><table><thead><tr><th>Funcionalidade</th><th>Rio Grande do Sul</th><th>Porto Alegre</th></tr></thead><tbody>" +
      Object.keys(CAP_NOME).map(function (k) { return "<tr><th scope='row'>" + Lg.esc(CAP_NOME[k]) + "</th>" + cel(rs, k) + cel(poa, k) + "</tr>"; }).join("") + "</tbody></table></div>";
  }
  function proveniencia() {
    var box = el("vista-proveniencia");
    box.innerHTML = "<p class='muted'>Carregando…</p>";
    var pedidos = [T.rs().catch(function () { return null; }), T.online ? api("proveniencia").catch(function () { return null; }) : Promise.resolve(null)];
    Promise.all(pedidos).then(function (r) {
      var d = r[0], p = r[1], e = d && d.cobertura.estado, poa = T.territorio("poa").cobertura || (p && p.cobertura.por_modal_em_km);
      box.innerHTML = "<h2 class='titulo'>Proveniência dos dados</h2>" + legendKinds() +
        "<h3>O que cada região oferece</h3>" + matriz() +
        "<h3>Fontes e atualização</h3><div class='rolagem'><table><thead><tr><th>Fonte</th><th>Uso</th><th>Atualização</th></tr></thead><tbody>" +
        "<tr><td>Open-Meteo</td><td>Chuva diária (estado) e horária (Porto Alegre)</td><td class='small'>" + Lg.esc(hora((d && d.previsao && d.previsao.fonte_chuva.emitido_em_utc) || (p && p.fontes[0].emitido_em_utc))) + "</td></tr>" +
        "<tr><td>CPRv BM</td><td>Bloqueios ativos em rodovias</td><td class='small'>" + Lg.esc(hora(d && d.bloqueios && d.bloqueios.coletado_em_utc)) + "</td></tr>" +
        "<tr><td>S2iD/MIDR</td><td>Registros de decreto, municipais</td><td class='small'>até " + (d && d.ocorrencias ? Lg.esc(d.ocorrencias.ate.split("-").reverse().join("/")) : "indisponível") + "</td></tr>" +
        "<tr><td>DAER</td><td>Malha rodoviária e tráfego (VDM)</td><td class='small'>planilha e camada oficiais; licença a confirmar</td></tr>" +
        "<tr><td>IBGE</td><td>Limites e população municipais</td><td class='small'>—</td></tr>" +
        "<tr><td>OpenStreetMap (Geofabrik)</td><td>Rede de ruas de Porto Alegre e mapa-base</td><td class='small'>ODbL</td></tr>" +
        "<tr><td>Copernicus DEM GLO-30</td><td>Atributos físicos (cota, depressão, fluxo, declividade)</td><td class='small'>—</td></tr>" +
        "<tr><td>AWS Terrain Tiles</td><td>Relevo 3D, só visual</td><td class='small'>não alimenta cálculo</td></tr></tbody></table></div>" +
        "<h3>Cobertura " + Lg.kindBadge("observado") + "</h3><p class='small'>" + Lg.esc(T.dados.metodo_de_cobertura) + "</p>" +
        (e ? "<p><b>Rio Grande do Sul:</b> " + e.municipios + " municípios — " + e.municipios_por_classe.disponivel + " com dados disponíveis, " + e.municipios_por_classe.parcial + " com cobertura parcial, " + e.municipios_por_classe.insuficiente + " com dados insuficientes. Malha DAER: " + e.segmentos.toLocaleString("pt-BR") + " segmentos, índice físico em " + Lg.pct(e.fracao_km_com_indice_fisico) + " do km e tráfego em " + Lg.pct(e.fracao_km_com_vdm) + ". " + e.rodovias + " rodovias (" + e.rodovias_por_classe.disponivel + " com dados disponíveis).</p>" : "<p class='indisp'>Cobertura estadual indisponível.</p>") +
        (poa ? "<p><b>Porto Alegre:</b> índice físico em " + Lg.pct(poa.dirigivel.fracao_com_indice) + " do km dirigível (" + Lg.km(poa.dirigivel.km) + "), " + Lg.pct(poa.caminhavel.fracao_com_indice) + " do km caminhável (" + Lg.km(poa.caminhavel.km) + ") e " + Lg.pct(poa.somente_a_pe.fracao_com_indice) + " dos " + Lg.km(poa.somente_a_pe.km) + " só de pedestres. Trechos sem índice ficam <b>sem estimativa</b>, não em risco baixo.</p>" : "<p class='indisp'>Cobertura de Porto Alegre indisponível (calculada a partir da rede de ruas).</p>") +
        (p ? "<h3>Metodologia do risco por trecho (Porto Alegre)</h3><p>" + Lg.esc(p.metodo) + "</p><h3>Limitações</h3>" + ul(p.limites.map(Lg.esc)) + "<h3>Parâmetros provisórios</h3><p class='small'>" + p.parametros_provisorios.map(Lg.esc).join(", ") + " (em <code>config/analysis.yaml</code>, sem ajuste a ocorrências).</p>"
          : "<h3>Metodologia e limitações do risco por trecho</h3><p class='indisp'>Disponíveis com o servidor de análise ativo. Resumo: baseline determinístico, sem validação em vias, com parâmetros provisórios; o modelo municipal não é usado em vias.</p>");
    }).catch(function (e) { fail(box, e); });
  }

  /* ---------------------------------------------------------------- início */
  window.Painel = { contextoMunicipio: contextoMunicipio, contextoRodovia: contextoRodovia, segmento: segmento };
  Array.prototype.forEach.call(document.querySelectorAll("#abas button"), function (b) { b.addEventListener("click", function () { show(b.dataset.aba); }); });
  Array.prototype.forEach.call(document.querySelectorAll("#territorios button"), function (b) { b.addEventListener("click", function () { T.definir(b.dataset.territorio); }); });
  el("btn-classico").addEventListener("click", function () { st.classico = true; abrirMapa(); });
  el("btn-3d").addEventListener("click", function () { st.classico = false; el("banner").hidden = true; abrirMapa(); });
  T.aoMudar(function (id) {
    marcarTerritorio();
    if (window.Mapa && window.Mapa.pronto) window.Mapa.irParaTerritorio(id);
    show(st.aba);
  });
  T.carregar().then(function () {
    return api("saude").then(function (s) { return s.status === "ok" || s.status === "degradado" ? T.atualizarComServidor() : null; }).catch(function () { return null; });
  }).then(function () {
    var h = Lg.parseHash(location.hash, ABAS, T.ids, "rs");
    T.atual = h.territorio; marcarTerritorio();
    show(h.aba || "geral");
  }).catch(function (e) { var b = el("banner"); b.textContent = "Não foi possível carregar a configuração dos territórios: " + e.message; b.hidden = false; });
})();
