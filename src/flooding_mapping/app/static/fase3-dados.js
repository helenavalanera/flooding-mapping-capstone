/* Camada da Fase 3: lógica pura (sem DOM, sem mapa), testável em Node. Nada aqui recalcula o motor.
   O que o navegador recebe do motor são (a) classes visuais inteiras nos tiles e (b) valores por trecho em m² de área equivalente
   (``aeq``, soma de área x coeficiente). A única conta feita aqui é o volume de uma chuva de referência: V (m³) = P (mm) x aeq (m²) / 1000,
   linear em P, conferida nos testes contra a saída do motor. Ausência (null) nunca vira zero. */
(function (root) {
  "use strict";

  var PACOTES = {
    m1: { nome: "Método 1: coeficientes fundamentados", curto: "Método 1", natureza: "estimativa com coeficientes de referência publicada",
          nota: "Só as classes com coeficiente em referência publicada: edificação e vias pavimentadas. O resto da área a montante fica fora deste método, não é preenchido com valor arbitrário." },
    an: { nome: "Método 2: cenários por analogia", curto: "Método 2", natureza: "hipótese declarada, não estimativa fundamentada",
          nota: "Coeficientes de tipos de superfície análogos, em intervalo. Jardins e passeios sempre aparecem como envelope dos cenários de fração de piso (25%, 50% e 75%): nenhum cenário do meio é tratado como valor verdadeiro." },
    li: { nome: "Limites físicos", curto: "Limites físicos", natureza: "limite matemático, não é previsão",
          nota: "Referência matemática: nas classes sem coeficiente fundamentado, C = 0 (nada escoa) e C = 1 (tudo escoa). Vale por definição, não é uma estimativa nem um cenário operacional." }
  };
  var LIMITES = { min: "limite inferior", max: "limite superior" };
  var MODOS = {
    c: { nome: "Contribuição potencial acumulada", curto: "contribuição potencial estimada" },
    l: { nome: "Geração potencial local", curto: "volume potencial gerado localmente" },
    tp: { nome: "Indicador topográfico de retenção", curto: "indicador topográfico de retenção" },
    cb: { nome: "Cobertura dos dados", curto: "cobertura dos dados" }
  };
  /* Uma escala por grandeza: cores de famílias diferentes, para que a mesma cor nunca signifique duas coisas. */
  var COR_SEM_DADOS = "#7d8a93";
  var PALETAS = {
    c: ["#f7fbff", "#edf8b1", "#c7e9b4", "#7fcdbb", "#41b6c4", "#2c7fb8", "#253494"],   // 0 = exatamente zero; 1..6 = quantis dos valores positivos
    l: ["#f7fbff", "#efedf5", "#dadaeb", "#bcbddc", "#9e9ac8", "#756bb1", "#54278f"],
    tp: ["#f7fbff", "#e9dcc8", "#c4a47c", "#8f6a3f", "#4e3320"],                         // tons de terra, longe do vermelho e laranja do risco; 0 = sem preenchimento de depressão; 1..4 = posto
    cb: ["#f7fbff", "#d9ead3", "#a1d99b", "#41ab5d", "#00682f"]                           // 0 = nada coberto; 1..4 = quartis da fração da área a montante
  };

  /* Termos que a camada nunca usa: seriam afirmações que o motor não faz (conferido nos testes sobre todos os textos). */
  var TERMOS_PROIBIDOS = ["probabilidade de alagamento", "previsão de enchente", "profundidade prevista", "profundidade da água", "volume retido", "volume acumulado",
                          "rua alagada", "capacidade de retenção", "volume armazenável", "duração do alagamento", "rota segura"];

  function volumeM3(aeq, p) { return aeq == null || !isFinite(aeq) ? null : p * aeq / 1000; }
  function propriedade(grandeza, pacote, limite) { return grandeza + "_" + pacote + "_" + limite; }
  function propriedadeDoModo(modo, pacote, limite) {
    if (modo === "tp") return "tp";
    if (modo === "cb") return "cb_" + pacote;
    return propriedade(modo, pacote, limite);
  }

  var NUM = typeof Intl !== "undefined" ? new Intl.NumberFormat("pt-BR", { maximumSignificantDigits: 3, useGrouping: true }) : null;
  /* Só para exibir: 3 algarismos significativos, vírgula decimal, sem notação científica. O valor guardado não muda. */
  function formatar(v) {
    if (v == null || !isFinite(v)) return null;
    if (v === 0) return "0";
    var a = Math.abs(v);
    if (a >= 1e-3 && a < 1e12) return NUM.format(v);
    return String(v).replace(".", ",");
  }
  function volume(m3) { var t = formatar(m3); return t == null ? "sem dados" : t + " m³"; }
  function area(m2) {
    if (m2 == null || !isFinite(m2)) return "sem dados";
    return m2 >= 100000 ? formatar(m2 / 10000) + " ha" : formatar(m2) + " m²";
  }
  function pct(f) {
    if (f == null || !isFinite(f)) return "sem dados";
    var p = f * 100;
    return (p === 0 ? "0" : p < 1 ? "<1" : p > 99 && p < 100 ? ">99" : String(Math.round(p))) + "%";
  }
  function intervalo(min, max, p) {
    var a = volumeM3(min, p), b = volumeM3(max, p);
    if (a == null || b == null) return null;
    return { min: a, max: b, texto: formatar(a) + " a " + formatar(b) + " m³" };
  }

  /* Faixa (em m³) de uma classe visual 1..6: entre os cortes consecutivos dos trechos com valor positivo. */
  function faixaDaClasse(cortes, classe, p) {
    var lo = classe === 1 ? 0 : cortes[classe - 2], hi = classe - 1 < cortes.length ? cortes[classe - 1] : null;
    return { de: volumeM3(lo, p), ate: hi == null ? null : volumeM3(hi, p), semLimite: hi == null };
  }
  function rotuloDaFaixa(f) {
    if (f.semLimite) return "mais de " + formatar(f.de) + " m³";
    return (f.de === 0 ? "até " : formatar(f.de) + " a ") + formatar(f.ate) + " m³";
  }

  /* Propriedades que o mapa mantém como camadas para a grandeza: trocar de pacote ou de limite só alterna qual está opaca. */
  function propriedadesDoModo(modo) {
    if (modo === "tp") return ["tp"];
    if (modo === "cb") return ["cb_m1", "cb_li", "cb_an"];
    var o = [];
    ["m1", "an", "li"].forEach(function (p) { ["min", "max"].forEach(function (b) { o.push(propriedade(modo, p, b)); }); });
    return o;
  }

  function indiceDoFragmento(n, tamanho) { return Math.floor(n / tamanho); }
  function nomeDoFragmento(k) { return ("0000" + k).slice(-4) + ".json"; }
  function linhaDoFragmento(frag, n) {
    var i = n - frag.primeiro_n, l = frag.linhas[i];
    if (!l) return null;
    var o = {};
    frag.colunas.forEach(function (c, j) { o[c] = l[j]; });
    return o;
  }

  /* Expressão de cor do MapLibre: classe -> cor; só entra a camada de trechos que TÊM a propriedade (os sem dados ficam em outra camada). */
  function expressaoDeCor(prop, paleta) {
    var e = ["match", ["get", prop]];
    paleta.forEach(function (cor, i) { e.push(i, cor); });
    e.push(COR_SEM_DADOS);
    return e;
  }

  var api = { PACOTES: PACOTES, LIMITES: LIMITES, MODOS: MODOS, PALETAS: PALETAS, COR_SEM_DADOS: COR_SEM_DADOS, TERMOS_PROIBIDOS: TERMOS_PROIBIDOS, volumeM3: volumeM3, propriedade: propriedade,
              propriedadeDoModo: propriedadeDoModo, propriedadesDoModo: propriedadesDoModo, formatar: formatar, volume: volume, area: area, pct: pct, intervalo: intervalo, faixaDaClasse: faixaDaClasse, rotuloDaFaixa: rotuloDaFaixa,
              indiceDoFragmento: indiceDoFragmento, nomeDoFragmento: nomeDoFragmento, linhaDoFragmento: linhaDoFragmento, expressaoDeCor: expressaoDeCor };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Fase3Dados = api;
})(typeof window !== "undefined" ? window : this);
