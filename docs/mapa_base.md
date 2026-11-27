# Mapa-base (Protomaps)

Todos os mapas do produto (painel 3D e 2D, PWA 2D e 3D) usam o mesmo mapa-base: tiles vetoriais do Rio Grande do Sul do **Protomaps**
(derivados do OpenStreetMap), em tons de cinza, para que risco, chuva e rotas sejam as únicas cores fortes. Nenhuma página chama servidor
de tiles de terceiros.

## Como funciona

| Peça | Onde |
|---|---|
| Arquivo (um só `.pmtiles`, RS, zoom 0 a 14, ~217 MB) | `data/raw/basemap/rs.pmtiles` (fora do Git); servido em `/mapa/rs.pmtiles` com HTTP `Range` (`servidor.py`) |
| Módulo comum dos mapas | `app/static/mapa-base.js` (`MapaBase.estiloGL`, `MapaBase.camadaLeaflet`) |
| Bibliotecas e estilos (vendorizados) | `app/static/vendor/mapa/`: `pmtiles.js` 4.5.0, `protomaps-leaflet.js` 5.1.0, `estilo-claro.json`, `estilo-escuro.json`, fontes Noto Sans |
| Cache offline do PWA | `pwa/sw.js`: guarda as faixas do arquivo já vistas pela pessoa (nunca baixa o estado inteiro) |

Os estilos mantêm só os rótulos úteis ao produto (cidades, bairros, regiões, vias principais, água) e saem os de endereço, vias menores e cursos d'água, além de ícones: medido no Chrome com WebGL por software, o voo da câmera ao trocar de território caiu de 7 s para 2 s. A aplicação é **só em modo claro**: `escuro()` em `mapa-base.js` é sempre falso, e o tema do sistema não muda o mapa. `estilo-escuro.json` permanece no diretório só como arquivo vendorizado, sem uso. O mapa 2D (Leaflet, sem WebGL) usa a mesma fonte de dados, desenhada em canvas.

## Gerar ou atualizar

```bash
brew install pmtiles
tools/gerar_mapa_base.sh 20261115          # build do Protomaps (AAAAMMDD); baixa só a caixa do RS (~220 MB)
shasum -a 256 data/raw/basemap/rs.pmtiles
```

Depois: enviar o arquivo ao R2, atualizar `VERSAO_ARQUIVO` em `mapa-base.js` (chave do cache offline) e, no Render, `FM_MAPA_URL` e
`FM_MAPA_SHA256`. Para regenerar os estilos: ver o cabeçalho de `tools/gerar_estilos_mapa.mjs` (a saída é reproduzível byte a byte).

## Custo medido

Só em WebGL por software (Chrome sem GPU, a única forma de rodar os testes aqui): o `tests/e2e/dashboard.js` levou **311 s** com o mapa raster
antigo (`HEAD`) e **470 s** com este mapa vetorial já enxugado (550 s com o estilo completo), e a câmera leva cerca de 6 s para chegar a Porto
Alegre com o relevo 3D ligado (2,2 s programados). Por isso o limite dos testes de navegador subiu de 420 s para 900 s e o teste espera a chegada
da câmera. **Não medido:** o custo em celular ou computador com GPU, onde desenhar vetor costuma ser muito mais barato; confirmar no teste em
dispositivo físico (`docs/produto_preventivo.md`). Se pesar, as alavancas são menos camadas e menos rótulos em `tools/gerar_estilos_mapa.mjs`.

## Implantação

O Render não tem `data/`. Com `FM_MAPA_URL` (https) e `FM_MAPA_SHA256`, o servidor baixa o arquivo uma vez na partida e **recusa** o que não
bater com o hash. Sem o arquivo, `/mapa/rs.pmtiles` responde 404 e o mapa fica sem fundo (os dados continuam). No plano gratuito do Render o
serviço dorme após 15 minutos: cada partida a frio repete o download de ~217 MB (uma operação Classe B no R2; a saída de dados do R2 não é
cobrada). **Não verificado:** o tamanho do disco efêmero do plano gratuito e o tempo de partida com esse download. Se for um problema, a
alternativa é servir o arquivo direto de um bucket R2 público com CORS e `Range`, com ajuste da CSP.

## Atribuição e licenças

- Dados: © colaboradores do OpenStreetMap (ODbL), via Protomaps; a atribuição aparece no mapa.
- `pmtiles`, `protomaps-leaflet`, `@protomaps/basemaps`: BSD-3-Clause. Fontes Noto Sans (Protomaps `basemaps-assets`): SIL Open Font License 1.1.
- Os textos das licenças e a conferência de cada arquivo contra a distribuição original (SHA-256) estão em `app/static/vendor/mapa/AVISOS.md` e `app/static/vendor/mapa/LICENSES/`. Os termos próprios do serviço de builds do Protomaps não foram lidos.
- Relevo (sombreamento 3D): AWS Terrain Tiles, como antes.
