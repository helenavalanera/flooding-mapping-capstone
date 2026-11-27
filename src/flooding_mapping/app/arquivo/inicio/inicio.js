// Landing: o nível de chuva muda a cor do capítulo, o acordeão abre uma etapa por vez e as partes entram uma vez ao rolar.
// Sem script, tudo continua legível: o nível 0 e a lista de faixas ficam à mostra.
(function () {
  "use strict";
  var NIVEIS = [
    { rotulo: "abaixo de 26,2\u00a0mm", valor: "abaixo de 26,2 milímetros", numero: "0%", leitura: "Nenhum bloqueio é atribuído a chuvas abaixo de 26,2 mm. A cidade alcançável em 30 minutos não muda." },
    { rotulo: "26 a 35\u00a0mm", valor: "de 26 a 35 milímetros", numero: "3,5%", leitura: "A cidade perde 3,5% da mobilidade de carro. Os trechos que fecham vêm de uma regra explícita, não de uma previsão validada." },
    { rotulo: "40 a 45\u00a0mm", valor: "de 40 a 45 milímetros", numero: "7%", leitura: "O valor dobra: 7% da mobilidade de carro, e 190 mil pessoas perdem ao menos 10% do que alcançam. Em algumas áreas a perda chega a 79%." }
  ];
  var reduz = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  requestAnimationFrame(function () { requestAnimationFrame(function () { document.documentElement.classList.add("carregado"); }); });
  if (document.documentElement.classList.contains("js")) document.body.classList.add("carregado");

  var campo = document.getElementById("chuva"), mm = document.getElementById("mm");
  if (campo && mm) {
    var rotulo = document.getElementById("mm-rotulo"), numero = document.getElementById("mm-numero"), leitura = document.getElementById("mm-leitura");
    var aplicar = function () {
      var n = NIVEIS[+mm.value] || NIVEIS[0];
      campo.setAttribute("data-nivel", mm.value);
      rotulo.textContent = n.rotulo; numero.textContent = n.numero; leitura.textContent = n.leitura;
      mm.setAttribute("aria-valuetext", n.valor);
    };
    mm.addEventListener("input", aplicar); aplicar();
  }

  var etapas = Array.prototype.slice.call(document.querySelectorAll(".etapa"));
  etapas.forEach(function (e) {
    e.querySelector("button").addEventListener("click", function () {
      etapas.forEach(function (o) { var a = o === e; o.classList.toggle("aberta", a); o.querySelector("button").setAttribute("aria-expanded", String(a)); });
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll(".titulo, .intro p, .chuva-painel, .chuva-lista li, .limites li, .lugares li, .fontes, .acordeao"), function (a) { a.classList.add("rv"); });
  var alvos = document.querySelectorAll(".rv");
  if (!("IntersectionObserver" in window) || reduz) { Array.prototype.forEach.call(alvos, function (a) { a.classList.add("vista"); }); return; }
  var io = new IntersectionObserver(function (itens) {
    itens.forEach(function (i) { if (i.isIntersecting) { i.target.classList.add("vista"); io.unobserve(i.target); } });
  }, { threshold: .12, rootMargin: "0px 0px -6% 0px" });
  Array.prototype.forEach.call(alvos, function (a, k) { a.style.setProperty("--d", (k % 3) * 0.08 + "s"); io.observe(a); });
})();
