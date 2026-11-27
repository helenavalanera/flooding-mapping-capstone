/* Painel de análise de Porto Alegre: quatro áreas (Resultados, Mapa, Simulador e Proveniência). Tudo o que vem dos dados é escapado.
   O painel de duas escalas (Rio Grande do Sul e Porto Alegre), com as abas de previsão, mobilidade e ocorrências, está arquivado em
   app/arquivo/painel-estadual/ e não é carregado por esta versão. */
(function () {
  "use strict";
  var Lg = window.Logic, T = window.Territorio;
  var ABAS = ["resultados", "mapa", "simulador", "proveniencia"];
  var st = { aba: "resultados" };

  function el(id) { return document.getElementById(id); }
  function aviso(t) { var b = el("banner"); b.textContent = t; b.hidden = !t; }
  /* O PWA e a aplicação instalável foram arquivados (app/arquivo/): quem os tinha instalado neste endereço recebe o service worker removido e os caches apagados. */
  function limparServiceWorkerAntigo() {
    if (!("serviceWorker" in navigator) || !navigator.serviceWorker.getRegistrations) return;
    var pasta = location.pathname.replace(/[^/]*$/, "");
    navigator.serviceWorker.getRegistrations().then(function (rs) { rs.forEach(function (r) { if (new URL(r.scope).pathname === pasta) r.unregister(); }); }).catch(function () {});
    if (window.caches && caches.keys) caches.keys().then(function (ks) { ks.filter(function (k) { return k.indexOf("fm-app-") === 0; }).forEach(function (k) { caches.delete(k); }); }).catch(function () {});
  }

  /* ---------------------------------------------------------------- navegação */
  var RENDER = {
    resultados: function () { window.Resultados.render(el("vista-resultados"), T.atual); },
    simulador: function () { window.Simulador.render(el("vista-simulador"), T.atual); },
    proveniencia: proveniencia
  };
  function show(aba) {
    if (ABAS.indexOf(aba) < 0) aba = "resultados";
    st.aba = aba;
    Array.prototype.forEach.call(document.querySelectorAll("#abas button"), function (b) {
      b.setAttribute("aria-selected", String(b.dataset.aba === aba));
      if (b.dataset.aba === aba && b.scrollIntoView) { var barra = el("abas"); if (barra && barra.scrollWidth > barra.clientWidth) barra.scrollLeft = b.offsetLeft - (barra.clientWidth - b.offsetWidth) / 2; }
    });
    ABAS.forEach(function (n) { el("vista-" + n).hidden = n !== aba; });
    if (history.replaceState) history.replaceState(null, "", "#" + T.atual + "/" + aba);
    if (aba === "mapa") return abrirMapa();
    RENDER[aba]();
  }
  function marcarTerritorio() { var t = T.territorio(); el("sub-territorio").textContent = t.nome + " · escala " + t.escala + " · análise do escoamento superficial"; }
  /* Nem o mapa 3D nem o 2D puderam iniciar (sem WebGL e sem as bibliotecas, por exemplo): o que a pessoa pode fazer em vez disso, sem script de mapa. */
  function mapaIndisponivel(motivo) {
    aviso("Não foi possível iniciar o mapa: " + motivo);
    var c = el("mapa-gl"); if (!c) return;
    c.innerHTML = "<div class='mapa-indisponivel' role='status'><h2>O mapa interativo não pôde ser exibido</h2><p>Motivo: " + Lg.esc(motivo) + ".</p>" +
      "<p>Isso costuma acontecer quando o navegador não tem aceleração gráfica (WebGL) ou não consegue baixar as bibliotecas do mapa. Tente atualizar o navegador, ativar a aceleração gráfica ou abrir a página com conexão à internet.</p>" +
      "<p>Enquanto isso, os resultados continuam disponíveis: os mapas de manchas das dimensões A a E são imagens, sem WebGL, na <a href='inicio/#dimensoes'>página inicial</a>, e os resultados por bairro estão na aba <a href='#poa/resultados'>Resultados</a>.</p></div>";
  }
  function abrirMapa() {
    window.Mapa.iniciar().then(function () {
      window.Mapa.redimensionar();
    }).catch(function (e) {
      if (window.Mapa.motorNome === "gl") { window.Mapa.trocarMotor(true).then(function () { window.Mapa.redimensionar(); }).catch(function (x) { mapaIndisponivel(x.message); }); aviso("O mapa 3D não pôde iniciar (" + e.message + "): usando o mapa 2D simples."); }
      else mapaIndisponivel(e.message);
    });
  }

  /* ---------------------------------------------------------------- proveniência */
  function linha(fonte, uso, condicao) { return "<tr><th scope='row'>" + Lg.esc(fonte) + "</th><td>" + Lg.esc(uso) + "</td><td class='small'>" + Lg.esc(condicao) + "</td></tr>"; }
  function proveniencia() {
    var box = el("vista-proveniencia");
    box.innerHTML = "<h2 class='titulo'>Proveniência dos dados</h2>" +
      "<p class='small'>Fontes efetivamente usadas na análise de Porto Alegre e a condição de uso conhecida de cada uma. Esta lista não afirma que as bases tenham licença aberta irrestrita nem que possam ser redistribuídas: onde a licença não foi confirmada, isso é dito. As referências completas, em ABNT, estão na <a href='inicio/#referencias'>landing</a>, e o inventário em <code>docs/inventario_fontes.md</code>.</p>" +
      "<div class='rolagem'><table><caption class='small'>Fontes e condições de uso</caption><thead><tr><th scope='col'>Fonte</th><th scope='col'>Uso na análise</th><th scope='col'>Condição de uso</th></tr></thead><tbody>" +
      linha("Uso e ocupação do solo, Profill 2022 (Prefeitura de Porto Alegre)", "Área por classe em cada célula de 30 m (geração de escoamento)", "Licença não declarada pelo serviço; regularização documental à parte; derivados publicados com atribuição") +
      linha("Drenagem cadastrada (Prefeitura de Porto Alegre)", "Camada de contexto, fora do cálculo", "Licença não declarada pelo serviço; regularização documental à parte; a camada só aparece quando os dados são publicados") +
      linha("Copernicus DEM GLO-30", "Relevo: fluxo, depressões e indicador topográfico", "Gratuito, com atribuição; termos a reler antes de publicar derivados") +
      linha("OpenStreetMap (Geofabrik)", "Rede de ruas (trechos) e água", "ODbL, com atribuição") +
      linha("Coeficientes de escoamento (TxDOT; County of San Diego)", "Faixas de C por classe", "Documentos públicos; faixas citadas com a fonte") +
      linha("Open-Meteo (reanálise baseada em ERA5)", "Posição dos cenários de 10, 20 e 30 mm entre os eventos de 2017 a 2026", "Só números agregados; termos da API não relidos") +
      linha("Mapa-base (Protomaps, com dados do OpenStreetMap)", "Fundo do mapa, só visualização", "ODbL, com atribuição") +
      linha("AWS Terrain Tiles", "Relevo 3D, só visual", "Não alimenta nenhum cálculo") +
      "</tbody></table></div>" +
      "<h3>O que cada dimensão do mapa é, e o que não é</h3>" +
      "<ul class='plain'><li><b>Geração de escoamento (A):</b> volume potencial local, limite superior; não é volume que de fato escoou nem vazão.</li>" +
      "<li><b>Concentração do escoamento (B):</b> contribuição acumulada a montante; não é vazão, não é volume transportado e não se soma entre trechos.</li>" +
      "<li><b>Propensão topográfica à retenção (C):</b> indicador relativo do relevo; não é profundidade, volume nem duração.</li>" +
      "<li><b>Drenagem cadastrada (D):</b> o que está registrado; não prova capacidade, funcionamento nem conexão hidráulica.</li></ul>" +
      "<p class='small'>Cenários de 10, 20 e 30 mm são hipóteses de cálculo, uniformes na cidade: não são previsão. O estudo não prevê alagamentos, profundidade nem duração e não opera em tempo real. A frente experimental de GeoAI não alimenta nenhum destes resultados.</p>";
  }

  /* ---------------------------------------------------------------- início */
  Array.prototype.forEach.call(document.querySelectorAll("#abas button"), function (b) { b.addEventListener("click", function () { show(b.dataset.aba); }); });
  /* Um link interno ("#poa/resultados", vindo do mapa ou da landing) troca de aba sem recarregar a página. */
  window.addEventListener("hashchange", function () {
    var h = Lg.parseHash(location.hash, ABAS, T.ids, "poa");
    if (h.consulta && window.Mapa) window.Mapa.pedido = h.consulta;
    if (h.aba) show(h.aba);
    if (h.aba === "mapa" && h.consulta && window.Mapa && window.Mapa.pronto) window.Mapa.aplicarPedido();
  });
  limparServiceWorkerAntigo();
  T.carregar().then(function () {
    var h = Lg.parseHash(location.hash, ABAS, T.ids, "poa");
    marcarTerritorio();
    if (h.consulta && window.Mapa) window.Mapa.pedido = h.consulta;
    show(h.aba || "resultados");
  }).catch(function (e) { aviso("Não foi possível carregar a configuração do território: " + e.message); });
})();
