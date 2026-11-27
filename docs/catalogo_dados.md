# Catálogo do acervo de dados do projeto

Registro de **todos** os conjuntos de dados do Flooding Mapping, estejam ou não no Git, no R2 ou publicados. Os arquivos pesados não vivem no repositório: a arquitetura é Cloudflare Pages (aplicação), Cloudflare R2 (armazenamento operacional dos dados), Google Drive (uma cópia de recuperação, atualizada periodicamente) e GitHub (código e documentação). Medido em 26/11/2026 no disco local.

**Estado de cada coisa, em 26/11/2026:** nenhum conjunto foi migrado para o R2 e nenhuma cópia foi feita no Drive. A coluna "R2 (previsto)" é o desenho da migração, não um fato. O inventário das fontes e das licenças está em [`inventario_fontes.md`](inventario_fontes.md); as referências, em [`referencias_bibliograficas.md`](referencias_bibliograficas.md).

## Armazenar não é publicar

Guardar um arquivo no R2 **não** o torna público. Cada conjunto tem dois estados independentes:

| Estado | Significado |
|---|---|
| **Armazenado** (privado) | Está no bucket, sem URL pública; só o projeto lê |
| **Publicado** (público) | Tem URL pública, com CORS e `Range`; só depois de a licença estar registrada e a redistribuição identificada |

Os conjuntos derivados da Profill, da drenagem cadastrada e dos limites de bairros da Prefeitura são publicados **com atribuição**, com base na autorização de uso de 27/11/2026 e na Política de Dados Abertos do município (`base_legal_dados.md`); a regularização documental de cada conjunto é conduzida à parte pela responsável, e este catálogo não faz conclusão jurídica. Até o envio ao R2, a aplicação mostra o relevo e o mapa-base, e as camadas de escoamento, de drenagem e a experimental E avisam que faltam dados.

## Layout previsto no R2

Um bucket de dados (nome a definir), com prefixos por natureza. Os de acesso público levam um segmento com o hash da versão, para o cache não servir dados antigos (`config-dados.js`: `versao` e `meta_sha256`).

| Prefixo | Conteúdo | Acesso |
|---|---|---|
| `publico/d-<hash>/mapa/` | `rs.pmtiles` | Público |
| `publico/d-<hash>/fase3/` | tiles e fragmentos do escoamento | Público, com atribuição (autorização de 27/11/2026) |
| `publico/d-<hash>/drenagem/` | tiles e fragmentos da drenagem cadastrada | Público só após a licença da drenagem |
| `bruto/` | dados originais baixados, com o SHA-256 do manifesto | Privado |
| `processado/` | derivados em Parquet, JSON e GeoTIFF | Privado |
| `intermediario/` | recortes de imagens, atributos e cenários | Privado |
| `arquivo-estadual/` | dados da frente estadual arquivada | Privado |

## 1. Dados de origem (`data/raw/`)

| Conjunto (finalidade) | Fonte original | Período e abrangência | Formato e tamanho | Processamento | R2 (previsto) | Referência de acesso na aplicação | Licença e acesso público |
|---|---|---|---|---|---|---|---|
| **Copernicus DEM GLO-30** (relevo: fluxo, depressões e indicador topográfico) | ESA e Airbus, via AWS Open Data | Modelo de superfície; 39 telas do RS, 2 cobrem Porto Alegre (S30 e S31, W052) | 39 GeoTIFF (COG), 1,4 GB | Recorte, reprojeção para EPSG:31982 e grade de 30 m | `bruto/dem/` | Nenhuma (só o pipeline) | Gratuito com atribuição; termos a reler. Derivados publicáveis com atribuição |
| **Uso e ocupação do solo, Profill 2022** (geração de escoamento; rótulo da GeoAI) | Prefeitura de Porto Alegre (GeoPOA) | 15 classes, 605.245 polígonos, escala 1:2.500, ortoimagem de 30 cm de 2018 a 2021; baixado em 25/11/2026 | 31 arquivos (JSONL comprimido e metadados), 260 MB | Reparo de 277 polígonos inválidos, exclusão de 852 duplicatas, rasterização a 3 m e área por classe em células de 30 m | `bruto/uso_do_solo_profill_2022/` | Nenhuma (só o pipeline) | **Licença não confirmada.** Armazenar: sim. Público: não |
| **Drenagem cadastrada** (contexto, fora do cálculo) | Prefeitura de Porto Alegre (GeoPOA) | Rede pluvial (133.060 trechos), poços de visita, bocas de lobo, grelhas, canais e casas de bomba; baixado em 25/11/2026 | 16 arquivos (JSON e JSONL), 197 MB | Inventário em GeoParquet (EPSG:31982), controle de qualidade e marcação de duplicados e de trechos sem acesso | `bruto/drenagem_poa/` | Nenhuma (só o pipeline) | **Licença não confirmada.** Armazenar: sim. Público: não |
| **OpenStreetMap, extrato do Sul** (ruas, água, edificações) | Colaboradores do OpenStreetMap, via Geofabrik | Sul do Brasil; cópia de 25/10/2026 | 1 PBF, 409 MB | Recorte do município, 176.836 trechos viários e máscara de água | `bruto/osm/` | Nenhuma (só o pipeline) | ODbL, com atribuição. Derivados seguem a ODbL |
| **Série de chuva diária** (posição dos cenários de 10, 20 e 30 mm) | Open-Meteo, reanálise (base ERA5) | 2017-01-01 a 2026-11-02, malha de municípios do RS; Porto Alegre usa o ponto da grade | 270 JSON, 9,9 MB | Seleção do ponto de Porto Alegre, totais por dia, por mês e por evento | `bruto/weather/` | Nenhuma | Software em CC BY 4.0; termos da API de dados não relidos. Só números agregados são publicados |
| **Mapa-base do RS** (fundo do mapa) | Protomaps (build 20261115), dados do OpenStreetMap | RS, zoom 0 a 14; gerado em 16/11/2026 | 1 PMTiles, 207 MB (217 MB no R2) | Extração com `pmtiles extract`; estilos em tons de cinza | `publico/d-<hash>/mapa/rs.pmtiles` | `FM_DADOS.mapa` em `config-dados.js` | ODbL, atribuição no mapa. **Público: sim**, com CORS e `Range` |
| **Lista de alagamentos da Prefeitura** (validação exploratória do terreno) | Prefeitura de Porto Alegre (Google My Maps) | 127 pontos, 2013 e 2014, sem horário nem chuva | 1 CSV, 8 KB | Casamento com a rede de ruas em 100 m | `bruto/prefeitura_poa/` | Nenhuma | Condição não identificada. Armazenar: sim. Público: não (testes usam pontos sintéticos) |
| **Frente estadual arquivada**: setores censitários (IBGE), malha rodoviária (DAER), registros do S2iD, bloqueios (CPRv BM), GTFS (EPTC) | IBGE, DAER-RS, MIDR, CPRv BM e EPTC | Rio Grande do Sul, 2017 a 2026 | 55 MB, 36 MB, 1,6 MB, 16 KB e 7,4 MB | Ver `app/arquivo/README.md` | `bruto/` (estas cinco fontes) | Nenhuma | DAER a confirmar; IBGE, S2iD e CPRv BM sem licença identificada; GTFS em CC (portal). Público: não |

## 2. Dados derivados (`data/processed/` e `data/interim/`)

| Conjunto (finalidade) | Fonte original | Período e abrangência | Formato e tamanho | Processamento | R2 (previsto) | Referência de acesso na aplicação | Licença e acesso público |
|---|---|---|---|---|---|---|---|
| **Saídas do motor da Fase 3** (células de 30 m, contribuição por trecho, propensão topográfica, cenários) | Copernicus DEM, Profill, OpenStreetMap e coeficientes (TxDOT, San Diego) | Porto Alegre; 10, 20 e 30 mm | 5 Parquet, 37 MB (`fase3/`) | Motor determinístico: D8, acumulação, V = P × A × C ÷ 1000 | `processado/fase3/` | Nenhuma (alimenta `fase3_web`) | Deriva da Profill: **armazenar sim; público não** |
| **Camada de escoamento para a aplicação** (tiles vetoriais e fragmentos) | Saídas da Fase 3 | Porto Alegre; zoom 13 a 15 | 2.059 arquivos (MVT e JSON, `meta.json`), 69 MB | `tools/preparar_camada_fase3.py` | `publico/d-<hash>/fase3/` | `FM_DADOS.fase3`, conferido por `meta_sha256.fase3` | Deriva da Profill: **publicar só após a licença** |
| **Inventário de drenagem processado** | Drenagem cadastrada | Porto Alegre | 6 Parquet, 13 MB (`drenagem/`) | `tools/processar_drenagem_poa.py` | `processado/drenagem/` | Nenhuma (alimenta `drenagem_web`) | Licença não confirmada: armazenar sim; público não |
| **Camada de drenagem para a aplicação** | Inventário processado | Porto Alegre | 3.536 arquivos (MVT e JSON, `meta.json`), 68 MB | `tools/preparar_camada_drenagem.py` | `publico/d-<hash>/drenagem/` | `FM_DADOS.drenagem`, conferido por `meta_sha256.drenagem` | **Publicar só após a licença** |
| **Uso do solo na grade de 30 m** (área por classe, qualidade) | Profill | Porto Alegre | 88 arquivos, 241 MB (`uso_solo/`) | `tools/processar_uso_solo_poa.py` | `processado/uso_solo/` | Nenhuma | Deriva da Profill: armazenar sim; público não |
| **Tabela de ruas de Porto Alegre** (unidade de apresentação) | OpenStreetMap | Porto Alegre; 176.836 trechos | 1 Parquet, 16 MB | `make rede` | `processado/rede_poa.parquet` | Nenhuma | ODbL; público possível com atribuição |
| **Território de Porto Alegre** (bairros, arroios, casas de bomba) | Prefeitura de Porto Alegre (My Maps) | 94 bairros | 1 JSON, 244 KB | `tools/preparar_territorio_poa.py` | `processado/territorio_poa.json` | Nenhuma | Condição não identificada; só agregados por bairro são publicados |
| **Resultados executivos e rankings** (aplicação e landing) | Saídas da Fase 3 e série de chuva | Porto Alegre | JSON, 122 KB e 6 KB, **versionados** | `tools/gerar_resultados.py` e `tools/gerar_rankings.py` | Não vão ao R2: ficam no Pages com o código | `data/resultados_poa.json` e `data/rankings_poa.json` | Só agregados; publicado |
| **Experimento GeoAI**: recortes do Sentinel-2, embeddings do AlphaEarth, atributos de 30 m e raster experimental | Sentinel-2 L2A (ESA), AlphaEarth (Google), Profill | Tile 22JDM, 2019 a 2021; embeddings de 2020 | 247 arquivos, 3,8 GB (`interim/geoai/`) e 6 arquivos, 434 MB (`processed/geoai/`) | `tools/executar_geoai.py` | `intermediario/geoai/` e `processado/geoai/` | Nenhuma | Raster e figuras derivam da Profill: armazenar sim; público não. Sentinel livre; AlphaEarth CC BY 4.0 |
| **Mapas de trechos e figuras da GeoAI** (visualização) | Profill, OpenStreetMap, drenagem | Porto Alegre | 7 + 3 PNG, cerca de 3 MB | `gerar_landing.py --mapas-locais` e `executar_geoai.py` | `processado/figuras/` | Nenhuma (a landing usa texto) | Derivados da Profill e da drenagem: armazenar sim; público não |
| **Saídas da frente estadual e de mobilidade** (gatilho, previsão, cenários, criticidade, camadas do painel estadual) | DAER, S2iD, IBGE, Open-Meteo, EPTC | Rio Grande do Sul | 1,7 GB (`interim/scenarios/`), cerca de 150 MB de Parquets do gatilho, 4,4 MB em `arquivo_estadual/` | Pipelines da frente arquivada | `arquivo-estadual/` | Nenhuma | Derivam de fontes sem licença confirmada: armazenar sim; público não |

## Referências de acesso, hoje

- A aplicação lê os dados publicados por `window.FM_DADOS` em [`config-dados.js`](../src/flooding_mapping/app/static/config-dados.js): `fase3`, `drenagem` e `mapa` (URL-base relativa ou absoluta), `versao` e `meta_sha256` por camada. É o único ponto que muda entre ambientes.
- Os pipelines leem caminhos locais (`config/analysis.yaml` e os `tools/`). Depois da migração, o passo de baixar do R2 para o disco local deve preceder cada etapa; ainda não existe.
- Integridade: o `data/raw/manifest.json` guarda URL, data e SHA-256 de 115 arquivos baixados. Os demais hashes serão gerados na migração e gravados em um manifesto no próprio bucket.

## Migração controlada (pendente)

1. Criar o bucket e as credenciais (token do R2 com acesso só a esse bucket), sem gravá-las no repositório.
2. Subir por prefixo, com SHA-256 de cada arquivo conferido na ida (envio) e na volta (leitura), e registrar o manifesto.
3. Configurar o CORS do bucket público (origem do Pages; métodos `GET` e `HEAD`; cabeçalho `Range`; expor `Content-Range`, `Accept-Ranges` e `Content-Length`).
4. Testar requisições `Range` no `rs.pmtiles` (resposta `206` e `Content-Range` correto) e a leitura dos tiles pela aplicação publicada.
5. Atualizar `config-dados.js` com as URLs públicas, a versão e os hashes; incluir a origem do R2 na política de conteúdo (`connect-src` e `img-src`).
6. Só então, e conjunto a conjunto, liberar o acesso público, **após registrar a licença**. Profill e drenagem seguem privadas até lá.
7. Cópia de recuperação no Google Drive, uma só, com periodicidade definida; verificar a integridade por amostragem de hashes antes de apagar qualquer arquivo local.
