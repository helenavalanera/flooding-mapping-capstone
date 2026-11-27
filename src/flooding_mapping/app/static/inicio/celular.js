/* Troca a tela mostrada no aparelho: cada botão aponta para um endereço real da aplicação (os mesmos links profundos do restante do produto). Sem script, o aparelho mostra o mapa e os links do topo levam às telas. */
(function () {
  "use strict";
  var TELAS = {
    territorio: { url: "../?painel=1#poa/mapa", nota: "Visão territorial: o mapa 3D de Porto Alegre. Os controles ficam em uma folha que se recolhe para liberar o mapa." },
    camadas: { url: "../?painel=1#poa/mapa?escoamento=1&modo=l&p=30&pacote=m1", nota: "Camadas: dimensão A (geração potencial de escoamento) para uma chuva hipotética de 30 mm. A legenda traz unidade, pacote de coeficientes e o que significa dado ausente." },
    consulta: { url: "../?painel=1#poa/mapa?escoamento=1&modo=c&p=30&pacote=m1&lon=-51.2104&lat=-30.0144&zoom=15.5&trecho=26114", nota: "Consulta: um trecho de rua com contribuição potencial acumulada, área contribuinte, cobertura do pacote e indicador topográfico, cada um com a sua leitura e limitação. O trecho é um exemplo de demonstração, não um ponto de alagamento." },
    resultados: { url: "../?painel=1#poa/resultados", nota: "Resultados: o que foi observado, o que o modelo estimou, o contexto, a relevância e a limitação de cada achado." },
    simulador: { url: "../?painel=1#poa/simulador", nota: "Simulador: compara as três execuções do motor (10, 20 e 30 mm). Não é um simulador hidráulico." }
  };
  var quadro = document.getElementById("tela"), nota = document.getElementById("nota"), abrir = document.getElementById("abrir"), botoes = Array.prototype.slice.call(document.querySelectorAll("#telas button"));
  function mostrar(id) {
    var t = TELAS[id]; if (!t) return;
    botoes.forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.tela === id)); });
    nota.textContent = t.nota; abrir.href = t.url;
    var novo = quadro.cloneNode(false); novo.src = t.url;   // um quadro novo a cada tela: o mapa começa limpo, como se fosse aberto pelo endereço
    quadro.parentNode.replaceChild(novo, quadro); quadro = novo;
  }
  botoes.forEach(function (b) { b.addEventListener("click", function () { mostrar(b.dataset.tela); }); });
  nota.textContent = TELAS.territorio.nota;
})();
