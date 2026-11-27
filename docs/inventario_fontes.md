# Inventário de fontes, dados derivados e ferramentas

Inventário feito em 26/11/2026 a partir de **evidências**: `config/analysis.yaml`, `data/raw/manifest.json` (URLs, datas e SHA-256 de 115 arquivos baixados), o código (`src/`, `tools/`), as dependências instaladas no ambiente, os documentos do projeto e as respostas dos próprios provedores. As referências completas, em ABNT, estão em [`referencias_bibliograficas.md`](referencias_bibliograficas.md); as condições de uso de cada fonte estão aqui. O inventário detalhado das camadas da Prefeitura (estado, qualidade e uso) continua em [`inventario_fontes_poa.md`](inventario_fontes_poa.md) e em [`auditoria_fontes_drenagem_poa.md`](auditoria_fontes_drenagem_poa.md).

## Princípio de reuso de dados abertos

O estudo utiliza dados geoespaciais públicos, provenientes de bases governamentais e iniciativas de dados abertos, reutilizados para fins de pesquisa, análise e desenvolvimento de produtos geoespaciais. As fontes originais são referenciadas na documentação técnica.

Essa declaração descreve a **abordagem** do estudo. Ela **não** afirma que todas as bases, dados derivados ou produtos processados tenham licença aberta irrestrita, nem autoriza a redistribuição de qualquer dado. Regras seguidas aqui:

- cada fonte é identificada individualmente, com o órgão responsável, o conjunto de dados, o período, o endereço de origem e a condição de uso conhecida;
- a licença só é registrada quando há texto verificável; quando não foi identificada ou a redistribuição não foi esclarecida, a tabela diz isso;
- **nenhuma licença (MIT, CC BY ou outra) é atribuída a dados de terceiros sem fundamento documental**; a licença MIT do repositório vale para o **código** do projeto;
- distinguem-se quatro naturezas: **dado original** (de terceiros), **dado derivado** (processado pelo projeto), **resultado agregado** (números e figuras) e **código**.

## 1. Dados de terceiros (originais)

"Uso" classifica a situação: **utilizada** no estudo de escoamento; **experimento** (só na frente experimental de GeoAI); **frente arquivada** (mobilidade e painel estadual, fora do estudo atual).

| Fonte (citação) | Responsável | Conjunto e período | Origem | Baixado em | Uso | Licença ou condição de uso | Redistribuição de derivados |
|---|---|---|---|---|---|---|---|
| Copernicus DEM GLO-30 (EUROPEAN SPACE AGENCY; AIRBUS, 2022) | ESA e Airbus (distribuição pelo Registry of Open Data on AWS) | Modelo digital de superfície de 30 m; duas telas (S30 e S31, W052) cobrem a cidade | registry.opendata.aws/copernicus-dem; bucket `copernicus-dem-30m` | 27/10 a 08/11/2026 | Utilizada | Gratuito ao público geral nos termos da licença do Copernicus DEM; atribuição "© DLR e.V. 2010–2014 e © Airbus Defence and Space GmbH 2014–2018" | Possível com atribuição; **termos da licença a reler** antes de publicar |
| Uso e ocupação do solo, Profill 2022 (PROFILL, 2023) | Prefeitura de Porto Alegre (serviço gis-smamus) | 15 classes, 605.245 polígonos, escala 1:2.500, ortoimagem de 30 cm de 2018 a 2021 | GeoPOA, camada `uso_solo_profill_2022` | 25/11/2026 | Utilizada (motor) e experimento (rótulo e referência da GeoAI) | **Não confirmada**; o serviço declara só os direitos "PROFILL, 2023" | **Não publicar** derivados (tiles de escoamento, raster da GeoAI) até confirmar com a Prefeitura |
| Cadastro de drenagem (PORTO ALEGRE, [s. d.]b) | Prefeitura de Porto Alegre | Rede pluvial (133.060 trechos), poços, bocas de lobo, grelhas, canais, casas de bomba | GeoPOA, camadas 49 a 59 e rede_pluvial | 25/11/2026 | Utilizada (só contexto) | **Não confirmada** (o serviço não declara licença) | **Não publicar** a camada derivada até confirmar |
| Risco de inundação (SERVIÇO GEOLÓGICO DO BRASIL, [s. d.]) | CPRM, via GeoPOA | 2.216 polígonos, modelagem de 2012 a 2014 | GeoPOA, camada `inundacoes_cprm` | 25/11/2026 | Utilizada (contexto qualitativo) | **Não confirmada** | Só números agregados |
| Alagamentos 2013 e 2014 e marcos RRCM (PORTO ALEGRE, [s. d.]c) | Prefeitura de Porto Alegre (Google My Maps) | 124 trechos alagados, sem horário nem chuva; marcos altimétricos | KML do My Maps | 25/11/2026 | Utilizada (validação exploratória, nunca treino) | Não identificada | Só números agregados. **As 127 coordenadas ficam fora do Git** (`data/raw/prefeitura_poa/`, caminho em `dados_restritos.py`); os testes usam pontos **sintéticos** (`tests/dados/alagamentos_sinteticos.csv`) |
| Bairros, arroios, casas de bomba (PORTO ALEGRE, [s. d.]a) | Prefeitura de Porto Alegre (Google My Maps) | Limites de 94 bairros e contexto | KML do My Maps | 25/11/2026 | Utilizada (resultados por bairro) | Não identificada | Só agregados por bairro |
| OpenStreetMap, extrato do Sul (OPENSTREETMAP CONTRIBUTORS, 2026) | Colaboradores do OpenStreetMap (distribuição: Geofabrik) | Rede viária (176.836 trechos), água, edificações | download.geofabrik.de | 25/10/2026 | Utilizada | ODbL (OpenStreetMap Foundation), com atribuição | Derivados seguem a ODbL (atribuição e mesma licença) |
| Série de chuva diária (ZIPPENFENIG, 2023; OPEN-METEO, [s. d.]; HERSBACH et al., 2020) | Open-Meteo, com base na reanálise ERA5 | Porto Alegre, 2017-01-01 a 2026-11-02, 3.593 dias | archive-api.open-meteo.com (cache da ingestão) | 2026 | Utilizada (percentis e cenários) | Registro do software no Zenodo: CC BY 4.0; **termos da API de dados não relidos** (a página do provedor não carrega sem navegador) | Só números agregados |
| Sentinel-2 L2A (EUROPEAN SPACE AGENCY, [s. d.]; ELEMENT 84, [s. d.]) | ESA/Copernicus (distribuição: AWS Open Data e Element 84) | 30 cenas do tile MGRS 22JDM, 2019 a 2021 | registry.opendata.aws/sentinel-2-l2a-cogs; Earth Search | 26/11/2026 | Experimento (GeoAI) | "Access to Sentinel data is free, full and open" (registro AWS) | Raster experimental **não publicado** |
| Satellite Embedding V1 (GOOGLE; GOOGLE DEEPMIND, [s. d.]) | Google e Google DeepMind | Embeddings anuais de 64 dimensões a 10 m; ano 2020 | bucket `gs://alphaearth_foundations` (leitura anônima) | 26/11/2026 | Experimento (GeoAI) | CC BY 4.0, atribuição obrigatória: "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and Google DeepMind." | Raster experimental **não publicado** |
| Mapa-base (PROTOMAPS, 2026b) e relevo 3D (MAPZEN, [s. d.]) | Protomaps (build 20261115) e Mapzen (Terrain Tiles, via AWS) | Tiles vetoriais do RS (OSM) e tiles de elevação | build.protomaps.com e elevation-tiles-prod | 16/11/2026 (mapa-base) | Utilizada (só visualização) | Dados © OpenStreetMap (ODbL); relevo: atribuição conforme o registro AWS | Mapa-base não versionado (217 MB, fora do Git) |
| Coeficientes de escoamento (TEXAS DEPARTMENT OF TRANSPORTATION, [s. d.]; COUNTY OF SAN DIEGO, [s. d.]) | TxDOT e County of San Diego | Tabela 4-10 (Rational Method) e valores de C | txdot.gov; sandiegocounty.gov | consultados em 25/11/2026 | Utilizada | Documentos públicos; reuso não verificado | Só faixas de C citadas |
| Setores censitários 2022 (IBGE, [s. d.]) | IBGE | Malha com atributos do RS | ftp.ibge.gov.br | 25/10/2026 | Frente arquivada | Não identificada | Fora do estudo atual; o recorte municipal (arquivo local) saiu do Git |
| GTFS (EMPRESA PÚBLICA DE TRANSPORTE E CIRCULAÇÃO, [s. d.]) | EPTC | Feed de ônibus, vigência setembro a dezembro de 2025 (vencido) | dadosabertos.poa.br | 25/10/2026 | Frente arquivada | Creative Commons Atribuição, conforme o portal (informação do README, não relida) | Fora do estudo atual |
| Rodovias do RS (DEPARTAMENTO AUTÔNOMO DE ESTRADAS DE RODAGEM, [s. d.]) | DAER-RS (via IEDE-RS) | 1.683 trechos e planilha do sistema rodoviário | iede.rs.gov.br | 08/11/2026 | Frente arquivada | **A confirmar** (pendência de `qa_relatorio_final.md`) | Fora do estudo atual; a camada `rodovias.geojson` e os derivados foram **retirados do Git** e guardados em `data/raw/arquivo_estadual/` |
| Danos informados (BRASIL, [s. d.]) | MIDR (S2iD) | 11 exportações, UF = RS, 2017-01-01 a 2026-11-07 | s2id.mi.gov.br (exportação manual) | 08/11/2026 | Frente arquivada | Não identificada | Fora do estudo atual; `ocorrencias.json` retirado do Git (`data/raw/arquivo_estadual/`) |
| Bloqueios de rodovias (CPRv BM, [s. d.]) | CPRv BM | API pública de bloqueios ativos | bloqueios.cprvbm.rs.gov.br | consulta periódica | Frente arquivada | Não identificada | Fora do estudo atual; a coleta agendada continua habilitada até decisão operacional (`COLETOR_ATIVO`) |
| Eventos de bloqueio de 2025 (FLOODING MAPPING, 2025) | Compilação do projeto sobre notícias da EPTC (Jornal do Comércio, Sul21) | 24 eventos | `data/events/events.csv` (cada linha traz a URL da notícia) | 2025 | Frente arquivada | Compilação do projeto; o texto das notícias pertence aos veículos | Fora do estudo atual |

## 2. Dados derivados e resultados agregados do projeto

| Produto | Origem | Natureza | Onde está | Situação de publicação |
|---|---|---|---|---|
| Parquets da Fase 3 (células, trechos, cenários) | Profill, Copernicus DEM, OSM, coeficientes | Derivado | `data/processed/fase3/` (fora do Git) | Não publicado (depende da Profill) |
| Tiles e fragmentos do escoamento | Parquets da Fase 3 | Derivado | `data/processed/fase3_web/` (69 MB, fora do Git) | **Não publicar** até a licença da Profill ser esclarecida |
| Tiles da drenagem cadastrada | Cadastro da Prefeitura | Derivado | `data/processed/drenagem_web/` (68 MB, fora do Git) | **Não publicar** até a confirmação |
| Mapa-base do RS | Protomaps (OSM) | Derivado de dado ODbL | `data/raw/basemap/rs.pmtiles` (217 MB, fora do Git) | Publicável com atribuição (ODbL); avisos das bibliotecas, estilos e fontes em `app/static/vendor/mapa/AVISOS.md` |
| Mapas de trechos e de drenagem da landing (7 imagens) | Profill, OpenStreetMap e cadastro de drenagem | Derivado (visualização) | `data/interim/landing_mapas_historicos/` (fora do Git); `tools/gerar_landing.py --mapas-locais` | **Não publicar**: a landing usa texto no lugar |
| Figuras da GeoAI (mapas, dispersão, erro por bloco) | Profill e imagens | Derivado (visualização) | `data/interim/geoai/figuras_locais/` (fora do Git) | **Não publicar** até confirmar a Profill |
| Camadas e saídas do painel estadual (DAER, IBGE, S2iD) | DAER, IBGE e MIDR | Derivado | `data/raw/arquivo_estadual/` (fora do Git) | Frente arquivada; **não publicar** |
| Resultados e indicadores (`resultados_poa.json`, figuras, tabelas, `docs/*`) | Todos os acima | Resultado agregado | Repositório | Versionado; números agregados, sem geometria da Profill |
| Atributos de 30 m, embeddings agregados e COG da GeoAI | Sentinel-2, AlphaEarth, Profill | Derivado | `data/processed/geoai/` (fora do Git) | **Não publicado** (depende da Profill) |
| Manifestos de dados | Os arquivos acima | Metadados | `data/raw/manifest.json`, `data/processed/publicacao/` | `manifest.json` versionado; SHA-256 de cada arquivo |

## 3. Código e ferramentas

Classificação por evidência: **utilizada** (importada ou executada no pipeline, nos testes ou na interface), **utilizada em experimento**, **avaliada, mas não utilizada** e **planejada**. Versões: as do ambiente do projeto em 26/11/2026.

| Ferramenta (citação) | Classe | Evidência |
|---|---|---|
| NumPy 2.5.4 (HARRIS et al., 2020), SciPy 1.18.1 (VIRTANEN et al., 2020), pandas 3.1.0 (THE PANDAS DEVELOPMENT TEAM, 2026) | Utilizadas | Importadas em mais de 100 módulos e testes |
| scikit-learn 1.9.1 (PEDREGOSA et al., 2011) e joblib 1.6.0 (JOBLIB DEVELOPERS, 2026) | Utilizadas | Random Forest, gradient boosting, regressão linear; gatilho municipal e GeoAI |
| GeoPandas 1.1.4 (GEOPANDAS, 2026), Shapely 2.2.0 (GILLIES et al., 2026a), PyProj 3.6.1 (PYPROJ4, 2023), Rasterio 1.5.2 (GILLIES et al., 2026b), PyArrow 26.0.0 (APACHE SOFTWARE FOUNDATION, 2026) | Utilizadas | Motor, tiles, GeoAI (COG) e Parquet |
| GDAL 3.12.2 (ROUAULT et al., 2026) | Utilizada | Embutida no Rasterio (leitura de COG remotos, driver COG); a ferramenta de linha de comando 3.13.2 só serviu à inspeção do COG |
| pyrosm 0.24.0 (TENKANEN, 2026) e pyosmium 4.3.2 (OSMCODE, 2026) | Utilizadas | Leitura e recorte do OSM |
| Matplotlib 3.11.2 (HUNTER, 2007), Pillow 13.0.0 (PYTHON-PILLOW, 2026), PyYAML 6.0.3 (SIMONOV, 2025), Requests 2.34.2 (PYTHON SOFTWARE FOUNDATION, 2026) | Utilizadas | Figuras, imagens, configuração e consultas HTTP/STAC |
| pytest 9.1.1 (PYTEST-DEV, 2026) e Playwright 1.63.0 (MICROSOFT, [s. d.]) | Utilizadas (testes) | Suíte do projeto e testes de navegador; o Playwright fica fora das dependências do projeto |
| MapLibre GL JS 4.7.1 (MAPLIBRE, 2024), Leaflet 1.9.4 (LEAFLET, 2023), pmtiles.js 4.5.0 e protomaps-leaflet 5.1.0 (PROTOMAPS, 2026a) | Utilizadas | Mapa 3D, mapa 2D de reserva e leitura do mapa-base por faixas de bytes (`index.html`, `vendor/mapa/`) |
| NetworkX 3.7 (HAGBERG; SCHULT; SWART, 2008) e r5py 1.1.7 (FINK et al., 2022) | Frente arquivada | Roteamento da frente de mobilidade; não entram no estudo de escoamento |
| python-pptx (CANNY, [s. d.]) | Utilizada em ferramenta de apresentação | Geradores de slides em `tools/`; não instalado no ambiente atual |
| Random Forest (BREIMAN, 2001) | Utilizada em experimento | `RandomForestRegressor`, 200 árvores, na GeoAI e no gatilho municipal |
| AlphaEarth (GOOGLE; GOOGLE DEEPMIND, [s. d.]; BROWN et al., 2025) | Utilizado em experimento | Experimento B da GeoAI: empate com o Random Forest |
| Direção D8 (O'CALLAGHAN; MARK, 1984) e preenchimento de depressões por priority-flood (BARNES; LEHMAN; MULLA, 2014) | Utilizados | `fluxo.py` e `susceptibility.fill_depressions` (implementação própria; não é biblioteca) |
| Índice topográfico de umidade (BEVEN; KIRKBY, 1979) | Utilizado em experimento | Experimentos anteriores de suscetibilidade; fora do motor |
| Validação por blocos espaciais (ROBERTS et al., 2017) | Utilizada em experimento | GeoAI: blocos de 3 km com faixa de exclusão |
| Boas práticas de amostragem de validação (OLOFSSON et al., 2014) | **Planejada** | A amostra independente da GeoAI não foi executada |
| Cloudflare Pages (CLOUDFLARE, [s. d.]a) e R2 (CLOUDFLARE, [s. d.]b) | **Planejadas** | Hospedagem prevista; nada foi publicado. O R2 já guarda o modelo e os dados do coletor da frente arquivada, com credenciais fora do repositório |
| Prithvi-EO-2.0 (SZWARCMAN et al., 2024) | **Avaliada, não utilizada** | Unidade de entrada de 480 m a 30 m, exigência de GPU e de versões de torch e numpy em conflito; nenhum peso baixado |
| Clay, TorchGeo e HLS (NASA) | **Avaliados, não utilizados** | Considerados na pesquisa de viabilidade (`geoai_fase5.md`); nada instalado nem baixado. O HLS exigiria login da NASA |
| MDT 2010 da Prefeitura (Image Service) | **Avaliado, não adotado** | Piloto de 1 m sem arquivo para baixar; licença e precisão não declaradas (`inventario_fontes_poa.md`) |
| Streamlit | **Não utilizado** | Nenhuma ocorrência no código, nas dependências, nos notebooks ou na documentação |
| Tiles raster de terceiros (CARTO) | **Removidos** | Substituídos pelo mapa-base próprio (Protomaps); o arquivo `config/carto_api_key.txt` é um resquício local ignorado pelo Git |
| Earth Engine (Google) | **Não utilizado** | Os embeddings foram lidos do bucket público; nenhuma conta ou credencial do Earth Engine foi usada |

## 4. Licenças ainda por confirmar

1. **Profill 2022** (Prefeitura): redistribuição de derivados, incluindo os tiles de escoamento e o raster da GeoAI.
2. **Cadastro de drenagem e risco de inundação da CPRM** (Prefeitura): reuso dos derivados.
3. **DAER** (rodovias): reuso (frente arquivada).
4. **Open-Meteo**: termos da API de dados (a página de licença do provedor não pôde ser lida automaticamente).
5. **Copernicus DEM**: reler os termos da licença antes de publicar derivados.
6. **TxDOT e San Diego County**: condições de reuso dos manuais (só faixas de C são citadas).
7. **IBGE** (setores 2022), **S2iD** e **CPRv BM**: sem licença identificada (frente arquivada).
