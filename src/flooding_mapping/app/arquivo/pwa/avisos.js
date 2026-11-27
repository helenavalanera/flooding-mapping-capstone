/* Tela de Avisos do aplicativo do cidadão: o que a chuva pode afetar perto de você, as áreas em exposição estimada com os pontos de interesse dentro delas,
   e o laço da comunidade (confirmar ou dizer que secou). Tudo é estimativa de um baseline sem validação em vias, não alerta oficial.
   Recebe do pwa.js um contexto com o que precisa (c.ui, c.api, c.el, c.esc, ...); não toca em nada fora dele. */
(function () {
  "use strict";
  var CAT = { saude: "saúde", seguranca: "segurança", educacao: "educação", comunidade: "comunidade", abastecimento: "abastecimento", transporte: "transporte" };
  var HORAS = [[0, "Agora"], [3, "+3 h"], [6, "+6 h"], [12, "+12 h"]];
  var NIVEL = { baixo: "baixo", atencao: "atenção", alto: "alto" };
  var CHAVE = "fm_chave_anonima", CIENTE = "fm_avisos_ciente";
  var st = { h: 0 };

  function ler(c, k) { try { return c.store.getItem(k); } catch (e) { return null; } }
  function gravar(c, k, v) { try { c.store.setItem(k, v); } catch (e) { /* sem armazenamento: o app continua, só pede de novo */ } }
  function chaveAnonima(c) {
    var k = ler(c, CHAVE);
    if (k && k.length >= 16) return k;
    var b = new Uint8Array(12); (window.crypto || window.msCrypto).getRandomValues(b);
    k = Array.prototype.map.call(b, function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
    gravar(c, CHAVE, k); return k;
  }
  function hhmm(iso) { return String(iso).slice(11, 16); }
  function idade(iso) {
    var min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
    return min < 90 ? "há " + Math.max(1, min) + " min" : min < 60 * 36 ? "há " + Math.round(min / 60) + " h" : "há " + Math.round(min / 1440) + " dias";
  }
  function plural(n, um, varios) { return n + " " + (n === 1 ? um : varios); }
  function aviso(c) { return "<p class='small'>Estimativa de exposição à chuva, não é alerta oficial. Em emergência, ligue 199 (Defesa Civil).</p>"; }

  /* ---- mapa: um bolsão por vez, com os pontos de interesse dentro dele (nomes entram como texto, nunca como HTML) ---- */
  function desenhar(c, b, sugerida) {
    var g = c.ui.grupos; g.bolsoes.clearLayers(); g.pois.clearLayers();
    var cor = sugerida ? "#6b3fa0" : "#b3261e";
    var camada = c.L.geoJSON({ type: "Feature", geometry: b.geometria }, { style: { color: cor, weight: 2, fillColor: cor, fillOpacity: .16, dashArray: sugerida ? "6 5" : null } }).addTo(g.bolsoes);
    b.pois.forEach(function (p) {
      var rot = document.createElement("span"); rot.textContent = (p.nome || "Sem nome") + " · " + p.tipo;
      c.L.circleMarker([p.lat, p.lon], { radius: 6, color: "#12161D", weight: 2, fillColor: "#fff", fillOpacity: 1, keyboard: false }).bindTooltip(rot).addTo(g.pois);
    });
    c.ui.camadas.bolsoes = true; c.ui.camadas.pois = true; c.aplicarCamadas();
    c.definirFolha("compacta");
    c.ui.mapa.fitBounds(camada.getBounds(), { padding: [30, 30], maxZoom: 16 });
  }

  function cartaoBolsao(b, i, sugerida) {
    var cats = Object.keys(b.pois_por_categoria || {}).map(function (k) { return "<span class='chip leve'>" + b.pois_por_categoria[k] + " de " + CAT[k] + "</span>"; }).join("");
    var nomes = b.pois.filter(function (p) { return p.nome; }).slice(0, 3).map(function (p) { return "<li>" + window.Logic.esc(p.nome) + " <span class='small'>(" + window.Logic.esc(p.tipo) + ")</span></li>"; }).join("");
    return "<div class='card av'><p>" + window.Logic.esc(b.texto) + "</p>" + (cats ? "<div class='chips'>" + cats + "</div>" : "") +
      (nomes ? "<ul class='plain'>" + nomes + "</ul>" : "") +
      "<button class='chip' data-ver='" + i + "'>Ver no mapa</button></div>";
  }

  /* ---- seus lugares ---- */
  function barras(serie) {
    return "<div class='barras' aria-hidden='true'>" + serie.map(function (s) { return "<i class='b-" + (s.classe || "sem") + "' title='" + hhmm(s.hora) + "'></i>"; }).join("") + "</div>";
  }
  function meusLugares(c) {
    var box = c.el("av-meus"), lugares = c.estado().lugares;
    if (!lugares.length) {
      box.innerHTML = "<div class='card'><h3>Seus lugares</h3><p class='small'>Cadastre casa, trabalho ou escola para ver se as ruas ao redor entram em exposição estimada nas próximas horas.</p><button class='btn sec' id='av-cad'>Cadastrar um lugar</button></div>";
      c.el("av-cad").addEventListener("click", function () { c.ir("lugares"); });
      return;
    }
    var ciente = ler(c, CIENTE) === "1";
    box.innerHTML = "<div class='card'><h3>Seus lugares</h3>" + (ciente ? "" : "<p class='small'>Para calcular, as coordenadas dos seus lugares são enviadas ao servidor <b>só nesta consulta</b>, sem nome nem registro, e esquecidas em seguida.</p>") +
      "<button class='btn' id='av-ver'>" + (ciente ? "Atualizar avisos dos meus lugares" : "Ver avisos dos meus lugares") + "</button><div id='av-lugares' aria-live='polite'></div></div>";
    c.el("av-ver").addEventListener("click", function () {
      gravar(c, CIENTE, "1");
      var alvo = c.el("av-lugares"); alvo.textContent = "Calculando…";
      c.api("avisos", { method: "POST", body: { horas: 12, lugares: lugares.map(function (p) { return { lon: p.lon, lat: p.lat }; }) } }).then(function (r) {
        alvo.innerHTML = r.lugares.map(function (l, i) {
          return "<div class='av-lugar'><b>" + c.esc(lugares[i].nome) + "</b><p>" + c.esc(l.resumo) + "</p>" + barras(l.serie) +
            "<p class='small'>Próximas 12 horas: " + (l.sem_trechos ? "sem trechos no mapa ao redor." : "cada barra é uma hora; mais alta, maior exposição estimada.") + "</p></div>";
        }).join("") + aviso(c);
      }).catch(function (e) { alvo.textContent = /Failed to fetch|NetworkError|Load failed/i.test(e.message) ? "Sem conexão com o servidor. Tente de novo." : e.message; });
    });
  }

  /* ---- áreas em exposição ---- */
  function areas(c) {
    var box = c.el("av-bolsoes"); box.textContent = "Carregando…";
    c.api("bolsoes?h=" + st.h).then(function (r) {
      st.bolsoes = r.bolsoes;
      if (r.sem_estimativa) { box.innerHTML = "<p class='small'>Chuva indisponível agora: não há estimativa, e isso não significa que esteja tudo bem. Consulte os alertas oficiais.</p>"; return; }
      var cab = "<p class='small'>" + (r.natureza === "previsto" ? "Previsto" : "Observado") + " para " + hhmm(r.hora) + ".</p>";
      box.innerHTML = cab + (r.bolsoes.length ? r.bolsoes.slice(0, 5).map(function (b, i) { return cartaoBolsao(b, i, false); }).join("") : "<div class='card'><p>Nenhuma área em exposição estimada para este horário.</p><p class='small'>É uma estimativa da chuva da cidade; não garante que não haja ponto de acúmulo.</p></div>") + aviso(c);
      Array.prototype.forEach.call(box.querySelectorAll("[data-ver]"), function (b) { b.addEventListener("click", function () { desenhar(c, st.bolsoes[+b.dataset.ver], false); }); });
    }).catch(function (e) { box.textContent = /Failed to fetch|NetworkError|Load failed/i.test(e.message) ? "Sem conexão com o servidor." : e.message; });
  }

  /* ---- território da Prefeitura: bairros, arroios e casas de bombas (geometria baixada uma vez) ---- */
  var terr = null;
  function territorio(c) { if (!terr) terr = c.api("territorio").catch(function (e) { terr = null; throw e; }); return terr; }
  function corParcela(p) { return p == null ? "#9aa7b0" : p >= .15 ? "#b3261e" : p >= .08 ? "#e08a1e" : p >= .03 ? "#e9c46a" : "#cfe3ee"; }
  function km(n) { return Number(n).toLocaleString("pt-BR", { maximumFractionDigits: 1 }); }
  function pct(p) { return p == null ? "sem ruas" : (p * 100).toFixed(1).replace(".", ",") + "% das ruas"; }
  function pintarBairros(c) {
    Promise.all([territorio(c), c.api("bairros?h=" + st.h)]).then(function (r) {
      var g = c.ui.grupos.bairros; g.clearLayers();
      if (!r[0].disponivel || r[1].sem_estimativa) return;
      var por = {}; r[1].bairros.forEach(function (b) { por[b.id] = b; });
      r[0].bairros.forEach(function (b) {
        var d = por[b.id] || {};
        var f = c.L.geoJSON({ type: "Feature", geometry: b.geometria }, { style: { color: "#33505f", weight: 1, fillColor: corParcela(d.parcela_exposta), fillOpacity: .38 } }).addTo(g);
        var no = document.createElement("div"); var t = document.createElement("b"); t.textContent = b.nome; no.appendChild(t);
        var p = document.createElement("div"); p.className = "small"; p.textContent = "Exposição estimada: " + pct(d.parcela_exposta) + " (" + km(d.km_alto || 0) + " km em Alto, " + km(d.km_atencao || 0) + " km em Atenção)"; no.appendChild(p);
        f.bindPopup(no);
      });
    }).catch(function () { /* sem território, a camada fica vazia e o resto do app segue */ });
  }
  function desenharDrenagem(c) {
    territorio(c).then(function (t) {
      var g = c.ui.grupos.drenagem; g.clearLayers();
      t.arroios.forEach(function (a) { c.L.geoJSON({ type: "Feature", geometry: a.geometria }, { style: { color: "#1f6fb2", weight: Math.min(1 + a.ordem * .6, 4), opacity: .75 } }).addTo(g); });
      t.bombas.forEach(function (b) {
        var no = document.createElement("div"); var h = document.createElement("b"); h.textContent = "Casa de bombas " + b.nome; no.appendChild(h);
        var l = document.createElement("div"); l.className = "small"; l.textContent = [b.local, b.capacidade_m3s ? "capacidade " + String(b.capacidade_m3s).replace(".", ",") + " m³/s" : null].filter(Boolean).join(" · "); no.appendChild(l);
        c.L.circleMarker([b.lat, b.lon], { radius: 6, color: "#0b3d5c", weight: 2, fillColor: "#f2a33a", fillOpacity: 1 }).bindPopup(no).addTo(g);
      });
    }).catch(function () { /* idem */ });
  }
  function atualizarTerritorio(c) { if (c.ui.camadas.bairros) pintarBairros(c); if (c.ui.camadas.drenagem) desenharDrenagem(c); }

  /* ---- exposição lida por bairro ---- */
  function porBairro(c) {
    var box = c.el("av-bairros"); box.textContent = "Carregando…";
    Promise.all([territorio(c), c.api("bairros?h=" + st.h)]).then(function (r) {
      var d = r[1];
      if (!d.disponivel) { box.innerHTML = "<p class='small'>Divisão por bairros indisponível nesta instalação.</p>"; return; }
      if (d.sem_estimativa) { box.innerHTML = "<p class='small'>Chuva indisponível agora: não há estimativa.</p>"; return; }
      var geo = {}; r[0].bairros.forEach(function (b) { geo[b.id] = b; });
      var lista = d.bairros.filter(function (b) { return b.parcela_exposta != null; }).sort(function (a, b) { return b.parcela_exposta - a.parcela_exposta; }).slice(0, 8);
      var max = lista.length ? lista[0].parcela_exposta || 1 : 1;
      box.innerHTML = "<label class='opcao'><input type='checkbox' id='av-cam-b'" + (c.ui.camadas.bairros ? " checked" : "") + "> Colorir os bairros no mapa</label><label class='opcao'><input type='checkbox' id='av-cam-d'" + (c.ui.camadas.drenagem ? " checked" : "") + "> Mostrar arroios e casas de bombas</label>" +
        "<div class='leg-b' aria-label='Legenda das cores'><span><i style='background:#cfe3ee'></i>menos de 3%</span><span><i style='background:#e9c46a'></i>3 a 8%</span><span><i style='background:#e08a1e'></i>8 a 15%</span><span><i style='background:#b3261e'></i>15% ou mais</span></div>" +
        "<p class='small'>Parcela das ruas de cada bairro em Atenção ou Alto, para " + hhmm(d.hora) + ". Os bairros com vilas e aglomerados (IBGE 2010) mostram quantas pessoas vivem neles: é contexto, não entra no cálculo.</p>" +
        lista.map(function (b) {
          var ctx = b.pop_aglomerados ? "<div class='small'>" + plural(b.aglomerados, "aglomerado", "aglomerados") + " · cerca de " + b.pop_aglomerados.toLocaleString("pt-BR") + " pessoas (IBGE 2010)</div>" : "";
          return "<div class='card av'><div class='linha'><b>" + c.esc(b.nome) + "</b><span class='small'>" + pct(b.parcela_exposta) + "</span></div><div class='barra'><i style='width:" + Math.round(100 * b.parcela_exposta / max) + "%'></i></div>" +
            "<div class='small'>" + km(b.km_alto) + " km em Alto · " + km(b.km_atencao) + " km em Atenção, de " + km(b.km_ruas) + " km de ruas</div>" + ctx + "<button class='chip' data-bairro='" + b.id + "'>Ver no mapa</button></div>"; }).join("") + aviso(c);
      [["av-cam-b", "bairros"], ["av-cam-d", "drenagem"]].forEach(function (x) {
        c.el(x[0]).addEventListener("change", function (ev) { c.ui.camadas[x[1]] = ev.target.checked; c.aplicarCamadas(); if (ev.target.checked) c.definirFolha("compacta"); });
      });
      Array.prototype.forEach.call(box.querySelectorAll("[data-bairro]"), function (bt) {
        bt.addEventListener("click", function () {
          var b = geo[+bt.dataset.bairro]; var g = c.ui.grupos.bolsoes; g.clearLayers(); c.ui.grupos.pois.clearLayers();
          var f = c.L.geoJSON({ type: "Feature", geometry: b.geometria }, { style: { color: "#0b5d8f", weight: 3, fillColor: "#0b5d8f", fillOpacity: .1 } }).addTo(g);
          c.ui.mapa.fitBounds(f.getBounds(), { padding: [30, 30] }); c.definirFolha("compacta");
        });
      });
    }).catch(function (e) { box.textContent = /Failed to fetch|NetworkError|Load failed/i.test(e.message) ? "Sem conexão com o servidor." : e.message; });
  }

  /* ---- o laço: a comunidade confirma ou diz que secou ---- */
  function comunidade(c) {
    var box = c.el("av-comunidade");
    if (c.ui.ocorrencias === undefined) { box.textContent = "Carregando…"; c.recarregarOcorrencias(function () { if (c.ui.tela === "avisos") comunidade(c); }); return; }
    var lista = (c.ui.ocorrencias || []).filter(function (o) {
      return o.situacao === "reportada" || (o.situacao === "confirmada"); }).filter(function (o) {
      return Date.now() - new Date(o.data_hora).getTime() < 72 * 3600 * 1000 && !(o.fim && new Date(o.fim) < new Date()); }).slice(0, 6);
    if (c.ui.ocorrencias === null) { box.innerHTML = "<p class='small'>Ocorrências indisponíveis agora.</p>"; return; }
    if (!lista.length) { box.innerHTML = "<p class='small'>Nenhum relato recente. Se vir uma rua alagada, use <b>Relatar</b>.</p>"; return; }
    box.innerHTML = lista.map(function (o) {
      var conf = o.situacao === "confirmada" ? "<span class='chip leve'>confirmada por operador</span>" : "";
      return "<div class='card av'><p><b>" + c.esc(o.tipo === "alagamento_via" ? "Alagamento na via" : o.tipo.replace(/_/g, " ")) + "</b>" + (o.rua ? " · " + c.esc(o.rua) : "") + " · " + idade(o.data_hora) + "</p>" +
        "<p class='small'>" + plural(o.apoios || 0, "pessoa confirma", "pessoas confirmam") + " · " + plural(o.secou || 0, "disse que secou", "disseram que secou") + "</p>" + conf +
        "<div class='linha'><button class='chip' data-ap='" + c.esc(o.id) + "' data-t='ainda'>Ainda está alagado</button><button class='chip' data-ap='" + c.esc(o.id) + "' data-t='secou'>Já secou</button></div><button class='chip leve' data-ir='" + c.esc(o.id) + "'>Ver no mapa</button></div>";
    }).join("") + "<p class='small' id='av-ap-msg' role='status' aria-live='polite'>Sua confirmação ajuda a priorizar a verificação; ela não interdita nenhuma via. Usamos uma chave aleatória deste aparelho, guardada só em forma de código irreversível.</p>";
    Array.prototype.forEach.call(box.querySelectorAll("[data-ir]"), function (b) {
      b.addEventListener("click", function () {
        var o = lista.filter(function (x) { return x.id === b.dataset.ir; })[0];
        if (o) { c.definirFolha("compacta"); c.ui.mapa.setView([o.lat, o.lon], 17); }
      });
    });
    Array.prototype.forEach.call(box.querySelectorAll("[data-ap]"), function (b) {
      b.addEventListener("click", function () {
        var msg = c.el("av-ap-msg"); msg.textContent = "Enviando…";
        c.api("ocorrencias/" + encodeURIComponent(b.dataset.ap) + "/apoio", { method: "POST", body: { chave: chaveAnonima(c), tipo: b.dataset.t } }).then(function (r) {
          msg.textContent = r.mensagem; c.recarregarOcorrencias(function () { comunidade(c); c.el("av-ap-msg").textContent = r.mensagem; });
        }).catch(function (e) { msg.textContent = /Failed to fetch|NetworkError|Load failed/i.test(e.message) ? "Sem conexão. Tente de novo." : e.message; });
      });
    });
  }

  /* ---- áreas sugeridas para verificar (a IA/ML sugere onde olhar primeiro) ---- */
  function sugeridas(c) {
    var box = c.el("av-sug"); box.textContent = "Carregando…";
    c.api("areas-sugeridas").then(function (r) {
      st.sug = r.areas;
      box.innerHTML = "<p class='small'><b>Fonte:</b> " + c.esc(r.fonte) + ". " + c.esc(r.motivo) + "</p>" +
        r.areas.slice(0, 5).map(function (b, i) { return cartaoBolsao(b, i, true); }).join("") + "<p class='small'>" + c.esc(r.aviso) + "</p>";
      Array.prototype.forEach.call(box.querySelectorAll("[data-ver]"), function (b) { b.addEventListener("click", function () { desenhar(c, st.sug[+b.dataset.ver], true); }); });
    }).catch(function (e) { box.textContent = e.message; });
  }

  function render(c) {
    var t = c.el("tela");
    t.innerHTML = "<h2>Avisos</h2>" + aviso(c) + "<div id='av-meus'></div>" +
      "<h3>Áreas em exposição estimada</h3><div class='chips' role='group' aria-label='Horário'>" + HORAS.map(function (h) {
        return "<button class='chip" + (st.h === h[0] ? " ativo" : "") + "' data-h='" + h[0] + "' aria-pressed='" + (st.h === h[0]) + "'>" + h[1] + "</button>"; }).join("") + "</div><div id='av-bolsoes'></div>" +
      "<details id='av-bar'><summary>Exposição por bairro</summary><div id='av-bairros'></div></details>" +
      "<h3>Ajude a confirmar</h3><div id='av-comunidade'></div>" +
      "<details id='av-det'><summary>Áreas sugeridas para verificar</summary><p class='small'>O sistema aprende com o que a comunidade confirma e sugere onde olhar primeiro. É um ranking de prioridade, não previsão de alagamento.</p><div id='av-sug'></div></details>";
    Array.prototype.forEach.call(t.querySelectorAll("[data-h]"), function (b) { b.addEventListener("click", function () { st.h = +b.dataset.h; render(c); }); });
    meusLugares(c); areas(c); comunidade(c); atualizarTerritorio(c);
    c.el("av-bar").addEventListener("toggle", function () { if (c.el("av-bar").open) porBairro(c); });
    c.el("av-det").addEventListener("toggle", function () { if (c.el("av-det").open && !st.sug) sugeridas(c); });
  }

  window.PwaAvisos = { render: render, atualizarTerritorio: atualizarTerritorio };
})();
