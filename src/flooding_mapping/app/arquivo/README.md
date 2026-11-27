# Arquivo: frentes fora do escopo atual

A versão atual do Flooding Mapping é um **estudo** sobre o escoamento superficial **em Porto Alegre**, não um serviço de acompanhamento operacional e não uma análise estadual. Tudo o que pertence às frentes anteriores
(mobilidade e rotas, PWA, painel de duas escalas com o Rio Grande do Sul, previsão de 72 h, bloqueios de rodovias, registros do S2iD e malha do DAER) está guardado aqui, **sem ter sido apagado**, para uma retomada futura, por exemplo uma frente de **monitoramento em tempo real**, que não é o escopo do estudo.
Nada do que está aqui é carregado pela interface atual, pela montagem do site (`app/build.py`) nem pelos testes ativos.

## O que há nesta pasta

| Pasta ou arquivo | O que é | Saiu de |
|---|---|---|
| `pwa/` | App de rotas do cidadão (mobilidade preventiva, avisos, relatos): HTML, JS, CSS, manifesto, ícones e service worker próprio | `static/pwa/` |
| `sw-mapa.js` | Módulo de cache do mapa-base (só faixas já vistas), compartilhado pelos dois service workers | `static/sw-mapa.js` |
| `pwa-painel/` | Instalação do painel como aplicativo: `sw.js`, `manifest.webmanifest` e `instalar.js` | `static/` |
| `inicio/aplicativo.html`, `inicio/inicio.css`, `inicio/inicio.js` e `inicio/img/` | Página da landing que apresentava o app do cidadão, com seu estilo, seu script e as capturas de tela (dados sintéticos) | `static/inicio/` |
| `painel-estadual/` | **Cópia fiel** do painel de duas escalas (Rio Grande do Sul e Porto Alegre), com as abas Visão geral, Condições e previsão, Mobilidade e Ocorrências: `index.html`, `painel.js`, `mapa.js`, `mapa2d.js`, `territorio.js`, `logic.js`, `style.css`, `territorios.yaml` e `data/territorios.json` | `static/` (versão de 26/11/2026, antes da restrição a Porto Alegre) |
| `site_estadual.py` | Montagem do site de duas escalas, com previsão de 72 h, bloqueios de rodovias e modelo (era `app/build.py`) | `app/build.py` |

Os testes dessas frentes também foram guardados: `tests/arquivo/test_site_estadual.py` (ignorado), `tests/e2e/arquivo/painel_estadual.js`, `painel_estadual_sem_webgl.js`, `jornada_painel_pwa.js`, `seletor_demonstracao.js` e `pwa_app.js`.

## Dados retirados do Git (licença não confirmada)

Estes arquivos eram versionados e foram **movidos, sem alteração, para o disco local**, em `data/raw/arquivo_estadual/` (pasta ignorada pelo Git). Continuam no histórico dos commits anteriores; só deixam de acompanhar a árvore atual,
porque derivam de fontes cuja redistribuição não foi confirmada (DAER, IBGE, S2iD, CPRv BM):

| Arquivo local | O que é |
|---|---|
| `static_data/rodovias.geojson`, `municipios.geojson`, `cobertura_rs.json`, `impacto_rs.json`, `ocorrencias.json` | Camadas do painel estadual (malha do DAER, limites municipais do IBGE, cobertura de dados, impacto simulado, registros do S2iD) |
| `outputs_web/` (`critical_segments.geojson`, `impacto_rs.json`, `lcc.json`, `ranking.json`) | Saídas da análise de criticidade das rodovias |
| `app_data/` (`impacto_segmentos.parquet`, `segmentos_indice.parquet`) | Índice de segmentos rodoviários usado só pela montagem do site estadual |
| `figuras/painel-rs.png` | Captura do painel estadual, que mostrava a malha do DAER |

Também ficaram fora do Git, por licença não confirmada: os derivados da Profill (tiles de escoamento, raster e figuras da GeoAI, mapas de trechos da landing) e a lista de alagamentos da Prefeitura (`data/raw/prefeitura_poa/`). Ver `docs/inventario_fontes.md`.

## Módulos Python da frente estadual (mantidos nos lugares originais)

Os módulos abaixo pertencem às frentes arquivadas, mas **não foram movidos**: o servidor histórico (`servidor.py`, `servico.py`) e os testes que os cobrem os importam, e mudá-los de pacote seria uma refatoração ampla sem ganho para o produto atual.
O produto atual não os carrega: `app/build.py` não importa nenhum deles (há um teste que garante isso), e a interface não chama a API.

| Módulo | Frente |
|---|---|
| `ingestion/daer.py`, `ingestion/s2id.py`, `ingestion/forecast.py`, `collector.py`, `r2.py` (coleta dos bloqueios) | Fontes estaduais: DAER, S2iD, CPRv BM e previsão de chuva |
| `cobertura.py`, `app/layers.py`, `criticality.py`, `geospatial/impact.py`, `geospatial/matching.py`, `evaluation/report.py` | Cobertura de dados, camadas e impacto das rodovias |
| `models/gatilho.py`, `models/susceptibility_index.py`, `inference/`, `dashboard.py` | Gatilho municipal de risco e previsão de 72 h |
| `servico.py`, `servidor.py`, `demonstracao.py`, `aprendizado.py`, `bolsoes.py`, `pois.py`, `territorio.py`, `ocorrencias.py` | Servidor de mobilidade, ocorrências e avisos (API histórica) |
| `app/static/logic.js` | Biblioteca de funções puras compartilhada com o PWA arquivado; traz rótulos de rodovia e S2iD em funções que o painel atual não chama |

A coleta agendada dos bloqueios (`.github/workflows/coletor-crbm.yml`, a cada 30 minutos, para o R2) **continua habilitada** no repositório: desligá-la é uma decisão operacional sua (variável `COLETOR_ATIVO = false` nas configurações do GitHub). Workflows só valem a partir da branch padrão.

## Como o app arquivado volta a ser servido (testes e retomada)

O servidor local só serve `pwa/` com a variável `FM_ARQUIVO_PWA=1` (`servidor.py`: `ARQUIVO` entra em `RAIZES`). Os testes do app de rotas (`tests/e2e/pwa.js`, `pwa_sw.js`, `tests/test_pwa_*.py`) rodam com essa variável. O painel estadual **não é servido**: para restaurá-lo,
copie `painel-estadual/` de volta para `app/static/`, recoloque os dados de `data/raw/arquivo_estadual/` e restaure `site_estadual.py` como `app/build.py`.

A API do servidor (`/api/rotas`, ocorrências, risco por trecho) continua no código; só a **interface** foi arquivada.
