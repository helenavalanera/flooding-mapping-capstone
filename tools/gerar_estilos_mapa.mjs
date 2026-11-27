// Gera vendor/mapa/estilo-claro.json e estilo-escuro.json a partir do @protomaps/basemaps (BSD-3-Clause).
//   npm install --prefix /pasta/vazia @protomaps/basemaps@5.7.2
//   node tools/gerar_estilos_mapa.mjs /pasta/vazia/node_modules/@protomaps/basemaps/dist/esm/index.js src/flooding_mapping/app/static/vendor/mapa
// Saem: camadas com ícone (sem sprite no app; os pontos competiriam com as de risco) e rótulos de endereço, vias menores e cursos d'água.
// Medido (Chrome com WebGL por software): o voo da câmera ao trocar de território levava 7 s com todos os rótulos e 2 s com os mantidos abaixo.
// Camadas que um mapa de alagamento dispensa (prédios, túneis, pistas de aeroporto, polígonos de escola, zoológico etc.): custam quadros sem informar nada.
const CAMADAS_DISPENSADAS = /^(buildings|landuse_(hospital|industrial|school|zoo|aerodrome|runway|pedestrian|pier|beach)|roads_(runway|taxiway|pier|tunnels_.*)|boundaries_country)$/;
const ROTULOS_MANTIDOS = /^(places_|roads_labels_major|water_label)/;
const { layers, namedFlavor } = await import(process.argv[2]);
import fs from "node:fs";
const saida = process.argv[3];
for (const [nome, sabor] of [["claro", "grayscale"], ["escuro", "dark"]]) {
  let ls = layers("protomaps", namedFlavor(sabor), { lang: "pt" });
  // Os nomes das cidades (places_locality) vêm com o ponto da cidade como ícone: fica só o texto, centrado, para a cidade não perder o rótulo.
  ls = ls.map(l => {
    if (l.id !== "places_locality") return l;
    const layout = Object.fromEntries(Object.entries(l.layout).filter(([k]) => !k.startsWith("icon-") && !["text-offset", "text-variable-anchor", "text-anchor"].includes(k)));
    return { ...l, layout: { ...layout, "text-anchor": "center" } };
  });
  const comIcone = ls.filter(l => l.layout && l.layout["icon-image"]).map(l => l.id);
  ls = ls.filter(l => !(l.layout && l.layout["icon-image"]) && (l.type !== "symbol" || ROTULOS_MANTIDOS.test(l.id)) && !CAMADAS_DISPENSADAS.test(l.id));
  const fontes = new Set(); ls.forEach(l => (l.layout?.["text-font"] || []).forEach(f => fontes.add(f)));
  console.log(nome, sabor, ls.length, "camadas; sem ícone:", comIcone.length, "removidas; fontes:", [...fontes].join(", "));
  const estilo = { version: 8, glyphs: "__BASE__/fontes/{fontstack}/{range}.pbf",
    sources: { protomaps: { type: "vector", url: "pmtiles://__PMTILES__", attribution: '<a href="https://protomaps.com">Protomaps</a> &copy; <a href="https://openstreetmap.org/copyright">colaboradores do OpenStreetMap</a>' } },
    layers: ls };
  fs.writeFileSync(`${saida}/estilo-${nome}.json`, JSON.stringify(estilo));
}
