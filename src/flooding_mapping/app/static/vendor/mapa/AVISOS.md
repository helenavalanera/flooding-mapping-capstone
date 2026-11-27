# Avisos de terceiros do mapa-base

Tudo o que está nesta pasta (`vendor/mapa/`) é de terceiros e traz aqui o aviso de licença exigido. Nada foi alterado em `pmtiles.js`, `protomaps-leaflet.js` nem nos glifos: a conferência de
identidade com a distribuição original está na coluna "Origem". Os textos completos das licenças estão em `LICENSES/`. A licença MIT do repositório cobre só o código do projeto, não estes arquivos.

| Arquivo | O que é | Licença | Origem e conferência |
|---|---|---|---|
| `pmtiles.js` (4.5.0) | Leitor de PMTiles (Protomaps) | BSD-3-Clause, Copyright 2021 Protomaps LLC (`LICENSES/pmtiles-LICENSE.txt`). A especificação PMTiles é domínio público (CC0) | `dist/pmtiles.js` do pacote npm `pmtiles@4.5.0`; SHA-256 idêntico (`caf981bc…`). O pacote npm declara `BSD-3-Clause` mas não traz arquivo de licença: o texto vem do repositório `protomaps/PMTiles` |
| `protomaps-leaflet.js` (5.1.0) | Camada vetorial para o Leaflet (Protomaps) | BSD-3-Clause, Copyright 2021-2024 Protomaps LLC (`LICENSES/protomaps-leaflet-LICENSE.txt`) | `dist/protomaps-leaflet.js` do pacote npm `protomaps-leaflet@5.1.0`; SHA-256 idêntico (`26af014f…`); o texto da licença é o `LICENSE` do próprio pacote |
| `estilo-claro.json`, `estilo-escuro.json` | Estilos do mapa-base, gerados por `tools/gerar_estilos_mapa.mjs` a partir de `@protomaps/basemaps` 5.7.2 | Código BSD-3-Clause, Copyright 2019-2023 Protomaps LLC e Kelso Cartography; design visual dos estilos em CC0 (Geraldine Sarmiento); esquema de camadas adaptado do Tilezen; ícones derivados do Mapzen, MIT (`LICENSES/protomaps-basemaps-LICENSE.md`) | O estilo escuro existe como arquivo, mas **não é usado**: a interface é só em modo claro |
| `fontes/Noto Sans Regular/`, `Noto Sans Medium/`, `Noto Sans Italic/` (glifos `.pbf`) | Glifos dos rótulos do mapa, gerados do Noto Sans com o `font-maker` do MapLibre | SIL Open Font License 1.1, Copyright 2022 The Noto Project Authors (`LICENSES/Noto-Sans-OFL.txt`); a OFL permite redistribuir com o aviso e não permite vender a fonte isolada | Os 9 arquivos têm SHA-256 idêntico aos publicados em `protomaps/basemaps-assets` (`fonts/`); só os intervalos 0-255, 256-511 e 8192-8447 estão aqui |

## Dados exibidos pelo mapa-base

O arquivo `rs.pmtiles` (tiles vetoriais do Rio Grande do Sul, derivados do OpenStreetMap, build 20261115 do Protomaps) **não está no Git** (217 MB, regenerável com `tools/gerar_mapa_base.sh`). Os dados são
© colaboradores do OpenStreetMap, sob a Open Database License (ODbL). A atribuição exibida no mapa é "Protomaps © colaboradores do OpenStreetMap" (`mapa-base.js`), e a do relevo, "Elevação: AWS Terrain Tiles".
Os termos próprios do serviço de builds do Protomaps não foram lidos nesta revisão; só o que está acima foi verificado.
