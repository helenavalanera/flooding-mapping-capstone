# Referências bibliográficas

Documento **gerado** por `tools/gerar_referencias.py` a partir de `config/referencias.yaml`; não edite à mão. A mesma lista aparece na seção "Referências bibliográficas" da landing. Total: 59 referências. Data de acesso: 26 nov. 2026 (dia em que cada endereço foi consultado).

## Normalização

- **Normas.** Estrutura de referência da ABNT NBR 6023 e sistema autor-data de citação da ABNT NBR 10520. **A edição vigente de cada norma não pôde ser confirmada** nesta revisão (o catálogo da ABNT exige consulta interativa e as normas são pagas; as pesquisas automatizadas não retornaram a edição). A NBR 14724 (trabalhos acadêmicos) também não foi consultada. A forma adotada reúne o que é comum às edições conhecidas e **precisa ser conferida pela autora contra a edição vigente** antes de qualquer entrega formal.
- **Autoria.** Até três autores, todos; mais de três, o primeiro seguido de "et al.". Sem autor pessoal, a instituição ou o projeto, em maiúsculas. Datas ausentes aparecem como "[s. d.]", locais e editoras ausentes como "[S. l.]" e "[s. n.]".
- **Software e conjuntos de dados.** Versão utilizada quando conhecida; o DOI de software do Zenodo é o do **conceito** (todas as versões), conferido na API do Zenodo, porque o DOI de uma versão específica nem sempre é a versão usada.
- **Datas de acesso.** Todos os endereços foram consultados em 26 nov. 2026. Os marcados "[endereço não verificado por acesso automatizado]" não responderam a robôs (bloqueio do site) e precisam de conferência manual.
- **Licença.** Só aparece quando há texto verificável (página do provedor, registro do Zenodo, PyPI, npm ou GitHub). "Não identificada" ou "a confirmar" significa exatamente isso: **nenhuma licença foi atribuída por suposição**, e a licença MIT do código do projeto não se estende aos dados de terceiros.
- **Uso.** Cada item diz se foi utilizado, utilizado em experimento, é de uma frente arquivada ou foi apenas avaliado. O inventário completo está em [`inventario_fontes.md`](inventario_fontes.md).

## 1. Dados geoespaciais e bases territoriais

<a id="ref-daer_rodovias"></a>DEPARTAMENTO AUTÔNOMO DE ESTRADAS DE RODAGEM (DAER-RS). **Rodovias do RS por administração**: camada do serviço ArcGIS da IEDE-RS e Relatório do Sistema Rodoviário Estadual (planilha). [S. l.]: Infraestrutura Estadual de Dados Espaciais (IEDE-RS), [s. d.]. Conjunto de dados. Disponível em: <https://iede.rs.gov.br/server/rest/services/DAER/Rodovias_RS_por_Administracao/MapServer/0>. Acesso em: 26 nov. 2026.  
*Frente arquivada (mobilidade e painel estadual). Licença ou condição de uso: A CONFIRMAR (pendência registrada em docs/qa_relatorio_final.md). Frente estadual (arquivada): 1.683 trechos baixados em 08/11/2026. Não entra no cálculo de escoamento.*

<a id="ref-gtfs_eptc"></a>EMPRESA PÚBLICA DE TRANSPORTE E CIRCULAÇÃO (EPTC). **GTFS de Porto Alegre**: feed estático de ônibus (arquivo-gtfs.zip). Porto Alegre: Portal de Dados Abertos de Porto Alegre, [s. d.]. Conjunto de dados. Disponível em: <https://dadosabertos.poa.br/dataset/gtfs>. Acesso em: 26 nov. 2026.  
*Frente arquivada (mobilidade e painel estadual). Licença ou condição de uso: Creative Commons Atribuição, conforme o portal (informação registrada no README do projeto; não relida nesta revisão). Frente de mobilidade (arquivada): vigência setembro a dezembro de 2025, hoje vencido. Não entra no cálculo de escoamento.*

<a id="ref-ibge_setores2022"></a>INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA (IBGE). **Censo Demográfico 2022**: agregados por setores censitários: malha com atributos, Rio Grande do Sul (RS_setores_CD2022.gpkg) e dicionário de dados. [S. l.]: IBGE, [s. d.]. Conjunto de dados. Disponível em: <https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/malha_com_atributos/setores/gpkg/UF/RS/>. Acesso em: 26 nov. 2026.  
*Frente arquivada (mobilidade e painel estadual). Licença ou condição de uso: não identificada nesta revisão (a pasta não traz arquivo de licença). População por setor, usada na frente de mobilidade (grade de origens). Não entra no cálculo de escoamento.*

<a id="ref-osm_geofabrik"></a>OPENSTREETMAP CONTRIBUTORS. **OpenStreetMap**: extrato do Sul do Brasil (sul-latest.osm.pbf), distribuído pela Geofabrik. [S. l.]: Geofabrik, 2026. Conjunto de dados. Disponível em: <https://download.geofabrik.de/south-america/brazil/sul.html>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: Open Data Commons Open Database License (ODbL), da OpenStreetMap Foundation, com atribuição (página de direitos autorais do OpenStreetMap, conferida em 26/11/2026). Rede viária de Porto Alegre (176.836 trechos, unidade espacial do estudo), hidrografia auxiliar e edificações (verificação cruzada da GeoAI). Baixado em 25/10/2026 (manifesto, UTC).*

<a id="ref-pmpa_mymaps_drenagem"></a>PORTO ALEGRE (RS). Prefeitura Municipal. **Mapa "Drenagem Pluvial"**: bairros, arroios, casas de bombas e aglomerados (KML do Google My Maps). Porto Alegre: Prefeitura Municipal de Porto Alegre, [s. d.]. Conjunto de dados. Disponível em: <https://www.google.com/maps/d/kml?mid=1hKUlnRnx2aRiH3NBYnlLt4qXBUo&forcekml=1>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: não identificada (o serviço não declara licença; a reutilização precisa ser confirmada com a Prefeitura). Limites dos bairros (resultados por bairro) e contexto de arroios e casas de bomba, via tools/preparar_territorio_poa.py. Aglomerados subnormais (IBGE, 2010) entram só como contagem por bairro.*

## 2. Dados de uso e cobertura do solo

<a id="ref-drusch2012"></a>DRUSCH, M. et al. Sentinel-2: ESA's optical high-resolution mission for GMES operational services. **Remote Sensing of Environment**, v. 120, p. 25-36, 2012. DOI: 10.1016/j.rse.2011.11.026. Disponível em: <https://doi.org/10.1016/j.rse.2011.11.026>. Acesso em: 26 nov. 2026.  
*Utilizada em experimento. Licença ou condição de uso: artigo de periódico (direitos do editor). Descrição da missão Sentinel-2 (resolução espacial, bandas e revisita).*

<a id="ref-sentinel2_aws"></a>EUROPEAN SPACE AGENCY. **Sentinel-2 L2A**: produtos de reflectância de superfície em Cloud-Optimized GeoTIFF ("Sentinel-2 Cloud-Optimized GeoTIFFs"), distribuídos pelo Registry of Open Data on AWS e pelo catálogo Earth Search. [S. l.]: Registry of Open Data on AWS; Element 84, [s. d.]. Conjunto de dados. Disponível em: <https://registry.opendata.aws/sentinel-2-l2a-cogs/>. Acesso em: 26 nov. 2026.  
*Utilizada em experimento. Licença ou condição de uso: "Access to Sentinel data is free, full and open" (texto do registro AWS, que remete aos termos e condições do Copernicus). 30 cenas do tile MGRS 22JDM, 2019 a 2021 (mediana por pixel após máscara SCL), usadas só na GeoAI experimental. Contém dados Copernicus Sentinel (2019–2021), modificados.*

<a id="ref-profill2022"></a>PROFILL. **Uso e ocupação do solo 2022**: Porto Alegre, escala de produção 1:2.500, interpretação visual de ortoimagem de 30 cm (2018 a 2021); camada uso_solo_profill_2022 do GeoPOA. Porto Alegre: Prefeitura Municipal de Porto Alegre (serviço gis-smamus), 2023. Conjunto de dados. Disponível em: <https://gis-smamus.portoalegre.rs.gov.br/server/rest/services/01_PUBLICACOES/uso_solo_profill_2022/MapServer/0>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: NÃO CONFIRMADA. O serviço declara apenas os direitos "PROFILL, 2023"; a redistribuição de derivados exige confirmação com a Prefeitura. Classes de uso (15) na grade de 30 m: geração potencial de escoamento (motor) e, na frente experimental de GeoAI, rótulo de treino e referência de avaliação (referência cartográfica, não verdade de campo). Baixada em 25/11/2026 (data dos arquivos). Ano de publicação conforme o aviso de direitos do serviço.*

## 3. Dados de relevo e modelos digitais de elevação

<a id="ref-copernicus_dem"></a>EUROPEAN SPACE AGENCY; AIRBUS. **Copernicus DEM**: produto GLO-30 Public (30 m), em Cloud-Optimized GeoTIFF, distribuído pelo Registry of Open Data on AWS. [S. l.]: European Space Agency, 2022. Conjunto de dados. DOI: 10.5270/ESA-c5d3d65. Disponível em: <https://registry.opendata.aws/copernicus-dem/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: "GLO-30 Public e GLO-90 estão disponíveis gratuitamente ao público geral, nos termos da Licença" do Copernicus DEM (texto do registro AWS; os termos da licença não foram relidos nesta revisão). Atribuição: © DLR e.V. 2010–2014 e © Airbus Defence and Space GmbH 2014–2018, fornecido no âmbito do Copernicus pela União Europeia e pela ESA. Modelo digital de superfície (DSM) de 30 m: relevo, direção de fluxo, depressões e contribuição. Erro médio de 2,18 m contra 334 marcos altimétricos; não resolve microrrelevo urbano. Duas telas (S30 e S31, W052) cobrem Porto Alegre; o diretório local guarda 39 telas do estado, baixadas de 27/10 a 08/11/2026 (manifesto).*

## 4. Dados de drenagem e infraestrutura urbana

<a id="ref-geopoa_drenagem"></a>PORTO ALEGRE (RS). Prefeitura Municipal. **Cadastro de drenagem pluvial**: rede pluvial, poços de visita, bocas de lobo, grelhas, canais, condutos forçados e casas de bomba (camadas do GeoPOA). Porto Alegre: Prefeitura Municipal de Porto Alegre (serviço gis-smamus), [s. d.]. Conjunto de dados. Disponível em: <https://gis-smamus.portoalegre.rs.gov.br/server/rest/services/01_PUBLICACOES/rede_pluvial/FeatureServer/0>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: NÃO CONFIRMADA (o serviço não declara licença; a redistribuição de derivados exige confirmação com a Prefeitura). Camada de contexto (a presença de um elemento não comprova capacidade, conexão nem funcionamento); fora do cálculo de escoamento. Camadas 49 a 59 do serviço POA___Consultas_MIL1, rede_pluvial, bocas_de_lobo, ram_hidrografia_2014 e Casas_de_Bomba___EBAP_210126. Coletadas em 25/11/2026.*

## 5. Dados meteorológicos e precipitação

<a id="ref-hersbach2020"></a>HERSBACH, Hans et al. The ERA5 global reanalysis. **Quarterly Journal of the Royal Meteorological Society**, v. 146, n. 730, p. 1999-2049, 2020. DOI: 10.1002/qj.3803. Disponível em: <https://doi.org/10.1002/qj.3803>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: artigo de periódico (direitos do editor). Dados ERA5: Copernicus Climate Change Service (C3S), DOI 10.24381/cds.adbb2d47. Reanálise que fundamenta a série de chuva do Open-Meteo.*

<a id="ref-openmeteo_docs"></a>OPEN-METEO. **Historical Weather API**. [S. l.]: Open-Meteo.com, [s. d.]. Disponível em: <https://open-meteo.com/en/docs/historical-weather-api>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: ver a nota da referência do software. Documentação do endpoint de reanálise usado (archive-api.open-meteo.com).*

<a id="ref-openmeteo_software"></a>ZIPPENFENIG, Patrick. **Open-Meteo.com Weather API**. [S. l.]: Zenodo, 2023. Software. DOI: 10.5281/zenodo.7970649. Disponível em: <https://doi.org/10.5281/zenodo.7970649>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: registro do software no Zenodo: CC BY 4.0. A licença e as condições de uso da API de dados (uso não comercial, segundo a documentação do projeto) não puderam ser relidas na página do provedor, que não carrega sem navegador. Série diária de Porto Alegre de 2017-01-01 a 2026-11-02 (3.593 dias; ponto da grade -30,123 / -51,203) pela Historical Weather API, que reúne ERA5, ERA5-Land e ECMWF IFS conforme o provedor. O projeto não fixou o parâmetro models: o modelo efetivo por período não está registrado. Reanálise modelada, não pluviômetro. DOI do conceito (todas as versões); citação conforme o formato recomendado pelo próprio Open-Meteo (2023).*

## 6. Bases históricas e registros de eventos

<a id="ref-s2id_midr"></a>BRASIL. Ministério da Integração e do Desenvolvimento Regional. **Sistema Integrado de Informações sobre Desastres (S2iD)**: Relatório Gerencial: danos informados, exportação manual, UF = RS, de 2017-01-01 a 2026-11-07. [S. l.]: MIDR, [s. d.]. Disponível em: <https://s2id.mi.gov.br/>. Acesso em: 26 nov. 2026.  
*Frente arquivada (mobilidade e painel estadual). Licença ou condição de uso: não identificada nesta revisão. Frente do gatilho municipal (arquivada). Onze exportações em data/raw/s2id.*

<a id="ref-cprvbm_bloqueios"></a>CPRv BM. **Bloqueios ativos**: API pública. [S. l.]: CPRv BM, [s. d.]. Disponível em: <https://bloqueios.cprvbm.rs.gov.br/>. Acesso em: 26 nov. 2026.  
*Frente arquivada (mobilidade e painel estadual). Licença ou condição de uso: não identificada nesta revisão. Frente do painel estadual (arquivada): bloqueios de rodovias consultados pelo coletor. Não faz parte do estudo de escoamento.*

<a id="ref-events2025"></a>FLOODING MAPPING. **Registro de eventos de bloqueio por acúmulo de água em Porto Alegre**: compilação própria a partir de notícias da EPTC divulgadas pelo Jornal do Comércio e pelo Sul21 (data/events/events.csv). [S. l.]: Flooding Mapping, 2025. Conjunto de dados. Sem endereço público.  
*Frente arquivada (mobilidade e painel estadual). Licença ou condição de uso: compilação do projeto; o conteúdo das notícias de origem pertence aos veículos (endereços em source_url). Frente de mobilidade (arquivada). Não é validação de escoamento. Arquivo do repositório (data/events/events.csv); ainda sem endereço público, porque o código não foi enviado.*

<a id="ref-pmpa_alagamentos"></a>PORTO ALEGRE (RS). Prefeitura Municipal. **Alagamentos registrados em 2013 e 2014 e marcos altimétricos RRCM**: mapa público do Google My Maps (KML). Porto Alegre: Prefeitura Municipal de Porto Alegre, [s. d.]. Conjunto de dados. Disponível em: <https://www.google.com/maps/d/kml?mid=1pJ6wqw8YJLxbG7q4IZGCRqP07Os&forcekml=1>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: não identificada (o serviço não declara licença). 124 trechos alagados, sem horário nem chuva associada: validação exploratória, nunca treino, e não validação preditiva. Os marcos RRCM servem à conferência de altitude do relevo.*

## 7. Dados de referência e validação

<a id="ref-olofsson2014"></a>OLOFSSON, Pontus et al. Good practices for estimating area and assessing accuracy of land change. **Remote Sensing of Environment**, v. 148, p. 42-57, 2014. DOI: 10.1016/j.rse.2014.02.015. Disponível em: <https://doi.org/10.1016/j.rse.2014.02.015>. Acesso em: 26 nov. 2026.  
*Utilizada em experimento. Licença ou condição de uso: artigo de periódico (direitos do editor). Referencial para a amostra independente de validação da GeoAI (ainda não executada). Não foi aplicado nos resultados atuais.*

<a id="ref-roberts2017"></a>ROBERTS, David R. et al. Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. **Ecography**, v. 40, n. 8, p. 913-929, 2017. DOI: 10.1111/ecog.02881. Disponível em: <https://doi.org/10.1111/ecog.02881>. Acesso em: 26 nov. 2026.  
*Utilizada em experimento. Licença ou condição de uso: artigo de periódico (direitos do editor). Fundamenta a validação por blocos espaciais da GeoAI (blocos de 3 km com faixa de exclusão).*

<a id="ref-cprm_inundacao"></a>SERVIÇO GEOLÓGICO DO BRASIL (CPRM). **Risco de inundação, Porto Alegre**: classes Alto, Médio e Baixo, modelagem de 2012 a 2014; camada inundacoes_cprm do GeoPOA. Porto Alegre: Prefeitura Municipal de Porto Alegre (serviço gis-smamus), [s. d.]. Conjunto de dados. Disponível em: <https://gis-smamus.portoalegre.rs.gov.br/server/rest/services/01_PUBLICACOES/inundacoes_cprm/FeatureServer/0>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: NÃO CONFIRMADA (o serviço não declara licença). Só contexto qualitativo (sobreposição com o ranking de contribuição), nunca rótulo nem validação. A classe Alto cobre cerca da metade da área mapeada e discrimina pouco.*

## 8. Métodos e referenciais científicos

<a id="ref-barnes2014"></a>BARNES, Richard; LEHMAN, Clarence; MULLA, David. Priority-flood: an optimal depression-filling and watershed-labeling algorithm for digital elevation models. **Computers & Geosciences**, v. 62, p. 117-127, 2014. DOI: 10.1016/j.cageo.2013.04.024. Disponível em: <https://doi.org/10.1016/j.cageo.2013.04.024>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: artigo de periódico (direitos do editor). Referencial do preenchimento de depressões por priority-flood, implementado no projeto (susceptibility.fill_depressions).*

<a id="ref-beven1979"></a>BEVEN, K. J.; KIRKBY, M. J. A physically based, variable contributing area model of basin hydrology. **Hydrological Sciences Bulletin**, v. 24, n. 1, p. 43-69, 1979. DOI: 10.1080/02626667909491834. Disponível em: <https://doi.org/10.1080/02626667909491834>. Acesso em: 26 nov. 2026. [endereço não verificado por acesso automatizado]  
*Utilizada em experimento. Licença ou condição de uso: artigo de periódico (direitos do editor). Índice topográfico de umidade (TWI), usado só em experimentos anteriores de suscetibilidade (susceptibility.py); não entra no motor de escoamento. O DOI resolve nos metadados, mas o site do editor bloqueia o acesso automatizado.*

<a id="ref-sandiego_c"></a>COUNTY OF SAN DIEGO. **Hydrology Manual**: valores do coeficiente de escoamento C (arquivo hydro-evalcvalues.pdf). [S. l.]: County of San Diego, Department of Public Works, Flood Control, [s. d.]. Disponível em: <https://www.sandiegocounty.gov/content/dam/sdc/dpw/FLOOD_CONTROL/floodcontroldocuments/hydro-evalcvalues.pdf>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: documento público de agência; condições de reuso não verificadas nesta revisão. Conferência das faixas de C do método racional (docs/sensibilidade_hidrologica.md); não fornece os valores adotados.*

<a id="ref-ocallaghan1984"></a>O'CALLAGHAN, John F.; MARK, David M. The extraction of drainage networks from digital elevation data. **Computer Vision, Graphics, and Image Processing**, v. 28, n. 3, p. 323-344, 1984. DOI: 10.1016/S0734-189X(84)80011-0. Disponível em: <https://doi.org/10.1016/S0734-189X(84)80011-0>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: artigo de periódico (direitos do editor). Direção de fluxo D8, implementada no projeto (src/flooding_mapping/fluxo.py).*

<a id="ref-txdot_c"></a>TEXAS DEPARTMENT OF TRANSPORTATION. **Hydraulic Design Manual**: cap. 4, seção 12, Rational Method: Runoff Coefficients (Tabela 4-10). [S. l.]: TxDOT, [s. d.]. Disponível em: <https://www.txdot.gov/manuals/des/hyd/chapter-4--hydrology/section-12--rational-method/runoff-coefficients.html>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: documento público de agência; condições de reuso não verificadas nesta revisão. Faixas do coeficiente de escoamento C do Método 1 (Edificação 0,75 a 0,95; Vias Pavimentadas 0,70 a 0,95) e referências por analogia (Campo, Pastagem, Jardins). Valores de outro país, usados como faixa declarada, não como calibração local. Consultada em 25/11/2026 (config/uso_solo_*.csv).*

## 9. Modelos de inteligência artificial e GeoAI

<a id="ref-breiman2001"></a>BREIMAN, Leo. Random Forests. **Machine Learning**, v. 45, n. 1, p. 5-32, 2001. DOI: 10.1023/A:1010933404324. Disponível em: <https://doi.org/10.1023/A:1010933404324>. Acesso em: 26 nov. 2026.  
*Utilizada em experimento. Licença ou condição de uso: artigo de periódico (direitos do editor). Algoritmo do modelo treinado na GeoAI (RandomForestRegressor do scikit-learn, 200 árvores).*

<a id="ref-brown2025"></a>BROWN, Christopher F. et al. **AlphaEarth Foundations: an embedding field model for accurate and efficient global mapping from sparse label data**. 2025. Pré-publicação (arXiv). DOI: 10.48550/arXiv.2507.22291. Disponível em: <https://arxiv.org/abs/2507.22291>. Acesso em: 26 nov. 2026.  
*Utilizada em experimento. Licença ou condição de uso: pré-publicação no arXiv (licença da versão consultada não verificada). Artigo do modelo cujos embeddings foram avaliados (arXiv, versão 2; 19 autores).*

<a id="ref-alphaearth_dataset"></a>GOOGLE; GOOGLE DEEPMIND. **Satellite Embedding V1**: embeddings anuais de 64 dimensões a 10 m (GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL), Earth Engine Data Catalog e bucket gs://alphaearth_foundations. [S. l.]: Google, [s. d.]. Conjunto de dados. Disponível em: <https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL>. Acesso em: 26 nov. 2026.  
*Utilizada em experimento. Licença ou condição de uso: CC BY 4.0, com atribuição obrigatória: "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and Google DeepMind.". Ano 2020, zona UTM 22S, agregado às células de 30 m. Experimento B da GeoAI: empatou com o Random Forest, sem ganho demonstrado.*

## 10. Bibliotecas, ferramentas e tecnologias

<a id="ref-pyarrow"></a>APACHE SOFTWARE FOUNDATION. **Apache Arrow**: PyArrow, Python library for Apache Arrow. Versão 26.0.0. [S. l.]: Apache Software Foundation, 2026. Software. Disponível em: <https://arrow.apache.org/docs/python/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: Apache-2.0 (PyPI e GitHub). Versão 26.0.0 (PyPI, 09/10/2026): leitura e gravação de Parquet.*

<a id="ref-python_pptx"></a>CANNY, Steve. **python-pptx**. [S. l.]: python-pptx, [s. d.]. Software. Disponível em: <https://python-pptx.readthedocs.io/>. Acesso em: 26 nov. 2026.  
*Utilizada em experimento. Licença ou condição de uso: MIT (PyPI e GitHub). Usado só nos geradores da apresentação (tools/gerar_apresentacao*.py); não está instalado no ambiente atual.*

<a id="ref-r5py"></a>FINK, Christoph et al. **r5py: Rapid Realistic Routing with R5 in Python**. Versão 1.1.7. [S. l.]: Zenodo, 2022. Software. DOI: 10.5281/zenodo.7060437. Disponível em: <https://r5py.readthedocs.io/>. Acesso em: 26 nov. 2026.  
*Frente arquivada (mobilidade e painel estadual). Licença ou condição de uso: MIT (registro Zenodo); o PyPI declara "GPL-3.0-or-later or MIT". Versão 1.1.7 instalada; só na frente de mobilidade (arquivada). DOI do conceito (todas as versões); o DOI de versão citado em docs/proposta.md (zenodo.7060438) é o da versão 0.0.4.*

<a id="ref-geopandas"></a>GEOPANDAS. **GeoPandas**: Geographic pandas extensions. Versão 1.1.4. [S. l.]: GeoPandas, 2026. Software. DOI: 10.5281/zenodo.2585848. Disponível em: <https://geopandas.org>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-3-Clause (PyPI). Versão 1.1.4 (PyPI, 26/06/2026); DOI do conceito (todas as versões).*

<a id="ref-rasterio"></a>GILLIES, Sean et al. **Rasterio**: Fast and direct raster I/O for use with NumPy. Versão 1.5.2. [S. l.]: Rasterio, 2026. Software. Disponível em: <https://rasterio.readthedocs.io/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-3-Clause (PyPI). Versão 1.5.2 (PyPI, 30/09/2026), com o GDAL 3.12.2 embutido; grava o COG experimental.*

<a id="ref-shapely"></a>GILLIES, Sean et al. **Shapely**: Manipulation and analysis of geometric objects. Versão 2.2.0. [S. l.]: Zenodo, 2026. Software. DOI: 10.5281/zenodo.5597138. Disponível em: <https://doi.org/10.5281/zenodo.5597138>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-3-Clause (registro Zenodo e PyPI). Versão 2.2.0 (PyPI, 07/10/2026); DOI do conceito (todas as versões).*

<a id="ref-networkx"></a>HAGBERG, Aric A.; SCHULT, Daniel A.; SWART, Pieter J. Exploring network structure, dynamics, and function using NetworkX. **Proceedings of the 7th Python in Science Conference (SciPy 2008)**, p. 11-15, 2008. DOI: 10.25080/TCWV9851. Disponível em: <https://doi.org/10.25080/TCWV9851>. Acesso em: 26 nov. 2026.  
*Frente arquivada (mobilidade e painel estadual). Licença ou condição de uso: NetworkX: BSD-3-Clause (PyPI). NetworkX 3.7: roteamento da frente de mobilidade (arquivada).*

<a id="ref-numpy"></a>HARRIS, Charles R. et al. Array programming with NumPy. **Nature**, v. 585, n. 7825, p. 357-362, 2020. DOI: 10.1038/s41586-020-2649-2. Disponível em: <https://doi.org/10.1038/s41586-020-2649-2>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-3-Clause, com licenças de componentes incluídos (PyPI: BSD-3-Clause AND 0BSD AND MIT AND Zlib e outras). NumPy 2.5.4 (versão instalada).*

<a id="ref-matplotlib"></a>HUNTER, John D. Matplotlib: a 2D graphics environment. **Computing in Science & Engineering**, v. 9, n. 3, p. 90-95, 2007. DOI: 10.1109/MCSE.2007.55. Disponível em: <https://doi.org/10.1109/MCSE.2007.55>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: Matplotlib: licença própria (PyPI: "License agreement for matplotlib"). Matplotlib 3.11.2 (versão instalada): figuras da GeoAI e dos relatórios.*

<a id="ref-joblib"></a>JOBLIB DEVELOPERS. **Joblib**: Lightweight pipelining with Python functions. Versão 1.6.0. [S. l.]: Joblib, 2026. Software. Disponível em: <https://joblib.readthedocs.io/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-3-Clause (PyPI e GitHub). Versão 1.6.0 (PyPI, 31/08/2026): paralelismo do scikit-learn e serialização de modelos.*

<a id="ref-leaflet"></a>LEAFLET. **Leaflet**: JavaScript library for mobile-friendly interactive maps. Versão 1.9.4. [S. l.]: Leaflet, 2023. Software. Disponível em: <https://leafletjs.com/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-2-Clause (npm e GitHub). Versão 1.9.4 (npm, 18/05/2023), com hash de integridade: mapa 2D de reserva, sem WebGL.*

<a id="ref-maplibre"></a>MAPLIBRE. **MapLibre GL JS**: BSD licensed community fork of mapbox-gl, a WebGL interactive maps library. Versão 4.7.1. [S. l.]: MapLibre, 2024. Software. Disponível em: <https://maplibre.org/maplibre-gl-js/docs/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-3-Clause (npm). Versão 4.7.1 (npm, 23/09/2024), fixada com hash de integridade em index.html: mapa 3D.*

<a id="ref-playwright"></a>MICROSOFT. **Playwright**. Versão 1.63.0. [S. l.]: Microsoft, [s. d.]. Software. Disponível em: <https://playwright.dev/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: Apache-2.0 (GitHub: microsoft/playwright). playwright-core 1.63.0 (cache do npx), fora das dependências do projeto, com o Chrome 158 instalado: testes de navegador (e2e), acessibilidade e medições.*

<a id="ref-pyosmium"></a>OSMCODE. **pyosmium**: Python bindings for libosmium, the data processing library for OSM data. Versão 4.3.2. [S. l.]: osmcode, 2026. Software. Disponível em: <https://osmcode.org/pyosmium/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-2-Clause (PyPI e GitHub). Versão 4.3.2 (módulo osmium, PyPI, 18/10/2026): recorte do OSM.*

<a id="ref-pedregosa2011"></a>PEDREGOSA, Fabian et al. Scikit-learn: machine learning in Python. **Journal of Machine Learning Research**, v. 12, p. 2825-2830, 2011. Disponível em: <https://jmlr.org/papers/v12/pedregosa11a.html>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: scikit-learn: BSD-3-Clause (PyPI). scikit-learn 1.9.1 (versão instalada): Random Forest, gradient boosting e regressão linear.*

<a id="ref-pmtiles"></a>PROTOMAPS. **PMTiles**: PMTiles archive decoder for browsers (pmtiles.js 4.5.0) e formato de arquivo de tiles lido por faixas de bytes. Versão 4.5.0. [S. l.]: Protomaps, 2026. Software. Disponível em: <https://docs.protomaps.com/pmtiles/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-3-Clause (npm, pmtiles.js); protomaps-leaflet 5.1.0 também BSD-3-Clause. pmtiles.js 4.5.0 (npm, 10/08/2026) e protomaps-leaflet 5.1.0 (npm, 18/06/2025), vendorizados em app/static/vendor/mapa/.*

<a id="ref-pyproj"></a>PYPROJ4. **pyproj**: Python interface to PROJ (cartographic projections and coordinate transformations library). Versão 3.6.1. [S. l.]: pyproj4, 2023. Software. Disponível em: <https://github.com/pyproj4/pyproj>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: MIT (PyPI e GitHub). Versão 3.6.1 (PyPI, 21/09/2023): conversão entre EPSG:4326, 31982 (grade do projeto) e 32722 (tiles Sentinel-2).*

<a id="ref-pytest"></a>PYTEST-DEV. **pytest**: simple powerful testing with Python. Versão 9.1.1. [S. l.]: pytest-dev, 2026. Software. Disponível em: <https://docs.pytest.org/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: MIT (PyPI e GitHub). Versão 9.1.1 (PyPI, 19/06/2026): suíte de testes do projeto.*

<a id="ref-requests"></a>PYTHON SOFTWARE FOUNDATION. **Requests**: Python HTTP for Humans. Versão 2.34.2. [S. l.]: Python Software Foundation, 2026. Software. Disponível em: <https://requests.readthedocs.io/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: Apache-2.0 (PyPI e GitHub). Versão 2.34.2 (PyPI, 14/05/2026): consultas HTTP e ao catálogo STAC.*

<a id="ref-pillow"></a>PYTHON-PILLOW. **Pillow**: Python Imaging Library (fork). Versão 13.0.0. [S. l.]: Pillow, 2026. Software. Disponível em: <https://python-pillow.org/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: MIT-CMU (PyPI). Versão 13.0.0 (PyPI, 16/10/2026): leitura de dimensões de imagens nas ferramentas da landing.*

<a id="ref-gdal"></a>ROUAULT, Even et al. **GDAL**. Versão 3.12.2. [S. l.]: Zenodo, 2026. Software. DOI: 10.5281/zenodo.5884351. Disponível em: <https://gdal.org/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: MIT (registro Zenodo). Versão 3.12.2 embutida no Rasterio (leitura de COG remotos, driver COG); a ferramenta de linha de comando 3.13.2 foi usada só para inspeção. DOI do conceito (todas as versões).*

<a id="ref-pyyaml"></a>SIMONOV, Kirill. **PyYAML**: YAML parser and emitter for Python. Versão 6.0.3. [S. l.]: PyYAML, 2025. Software. Disponível em: <https://pyyaml.org/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: MIT (PyPI e GitHub). Versão 6.0.3 (PyPI, 25/09/2025): leitura das configurações em YAML.*

<a id="ref-pyrosm"></a>TENKANEN, Henrikki. **pyrosm**: A Python tool to parse OSM data from Protobuf format into GeoDataFrame. Versão 0.24.0. [S. l.]: pyrosm, 2026. Software. Disponível em: <https://pyrosm.readthedocs.io/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-3-Clause AND MIT AND ISC (PyPI). Versão 0.24.0 (PyPI, 23/10/2026): leitura das edificações e da rede do OSM.*

<a id="ref-pandas"></a>THE PANDAS DEVELOPMENT TEAM. **pandas-dev/pandas: Pandas**. Versão 3.1.0. [S. l.]: Zenodo, 2026. Software. DOI: 10.5281/zenodo.3509134. Disponível em: <https://doi.org/10.5281/zenodo.3509134>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-3-Clause (registro Zenodo e PyPI). Versão 3.1.0 (publicada no PyPI em 22/10/2026); DOI do conceito (todas as versões).*

<a id="ref-scipy"></a>VIRTANEN, Pauli et al. SciPy 1.0: fundamental algorithms for scientific computing in Python. **Nature Methods**, v. 17, n. 3, p. 261-272, 2020. DOI: 10.1038/s41592-019-0686-2. Disponível em: <https://doi.org/10.1038/s41592-019-0686-2>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: BSD-3-Clause (repositório no GitHub). SciPy 1.18.1 (versão instalada): morfologia, estatística e interpolação.*

## 11. Mapas-base, serviços cartográficos e provedores

<a id="ref-earthsearch"></a>ELEMENT 84. **Earth Search**: STAC API v1 da coleção sentinel-2-l2a. [S. l.]: Element 84, [s. d.]. Disponível em: <https://earth-search.aws.element84.com/v1>. Acesso em: 26 nov. 2026.  
*Utilizada em experimento. Licença ou condição de uso: não identificada nesta revisão (serviço de catálogo; os dados seguem a licença do Copernicus). Catálogo consultado pela GeoAI para localizar as cenas Sentinel-2 e suas máscaras de nuvem.*

<a id="ref-aws_terrain"></a>MAPZEN. **Terrain Tiles**: tiles de elevação no formato Terrarium (elevation-tiles-prod), Registry of Open Data on AWS. [S. l.]: Mapzen, a Linux Foundation project, [s. d.]. Conjunto de dados. Disponível em: <https://registry.opendata.aws/terrain-tiles/>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: atribuição conforme https://github.com/tilezen/joerd/blob/master/docs/attribution.md (indicada no registro AWS). Só para o relevo 3D da visualização; não entra em nenhum cálculo. Atribuição exibida no mapa: "Elevação: AWS Terrain Tiles".*

<a id="ref-protomaps_basemap"></a>PROTOMAPS. **Protomaps basemaps**: build 20261115, extrato do Rio Grande do Sul (rs.pmtiles), zoom 0 a 14, derivado do OpenStreetMap. [S. l.]: Protomaps, 2026. Disponível em: <https://docs.protomaps.com/basemaps/downloads>. Acesso em: 26 nov. 2026.  
*Utilizada. Licença ou condição de uso: dados © contribuidores do OpenStreetMap (ODbL); os termos próprios do Protomaps não foram lidos nesta revisão. Mapa-base de todos os mapas do produto, em tons de cinza; arquivo gerado em 16/11/2026 por tools/gerar_mapa_base.sh, fora do Git. Atribuição exibida no mapa: Protomaps e colaboradores do OpenStreetMap.*

## Tecnologias avaliadas, não utilizadas, e planejadas

Aparecem aqui só para registrar a avaliação ou o plano; **não fazem parte da metodologia executada**.

<a id="ref-cloudflare_pages"></a>CLOUDFLARE. **Cloudflare Pages**: documentação. [S. l.]: Cloudflare, [s. d.]. Disponível em: <https://developers.cloudflare.com/pages/>. Acesso em: 26 nov. 2026.  
*Planejada para etapas futuras, ainda não utilizada. Licença ou condição de uso: serviço comercial com plano gratuito; termos não analisados. PLANEJADO, ainda não utilizado: hospedagem prevista da interface estática. Nada foi publicado.*

<a id="ref-cloudflare_r2"></a>CLOUDFLARE. **Cloudflare R2**: documentação. [S. l.]: Cloudflare, [s. d.]. Disponível em: <https://developers.cloudflare.com/r2/>. Acesso em: 26 nov. 2026.  
*Planejada para etapas futuras, ainda não utilizada. Licença ou condição de uso: serviço comercial com faixa gratuita; termos não analisados. PLANEJADO para os dados publicados (tiles, fragmentos, mapa-base). O R2 já é usado pelo coletor e pelo armazenamento do modelo da frente arquivada (src/flooding_mapping/r2.py), com credenciais fora do repositório; nenhum bucket de dados do estudo foi criado.*

<a id="ref-szwarcman2024"></a>SZWARCMAN, Daniela et al. **Prithvi-EO-2.0: a versatile multi-temporal foundation model for Earth observation applications**. 2024. Pré-publicação (arXiv). DOI: 10.48550/arXiv.2412.02732. Disponível em: <https://arxiv.org/abs/2412.02732>. Acesso em: 26 nov. 2026.  
*Avaliada, não utilizada. Licença ou condição de uso: pesos Apache-2.0 (cartão do modelo no Hugging Face) e código MIT (repositório): licenças divergentes entre si, conferidas só na página, sem uso. AVALIADO E NÃO EXECUTADO: cada unidade de entrada do modelo cobre 480 m a 30 m (patch de 16 pixels), a inferência e o ajuste fino exigem GPU, e o ambiente exigiria versões de torch e numpy em conflito com o projeto. Nenhum peso foi baixado.*

## Chaves de citação

Citações no texto (autor-data) e a referência correspondente:

| Citação | Referência |
|---|---|
| (APACHE SOFTWARE FOUNDATION, 2026) | [pyarrow](#ref-pyarrow) |
| (BARNES; LEHMAN; MULLA, 2014) | [barnes2014](#ref-barnes2014) |
| (BEVEN; KIRKBY, 1979) | [beven1979](#ref-beven1979) |
| (BRASIL, [s. d.]) | [s2id_midr](#ref-s2id_midr) |
| (BREIMAN, 2001) | [breiman2001](#ref-breiman2001) |
| (BROWN et al., 2025) | [brown2025](#ref-brown2025) |
| (CANNY, [s. d.]) | [python_pptx](#ref-python_pptx) |
| (CLOUDFLARE, [s. d.]a) | [cloudflare_pages](#ref-cloudflare_pages) |
| (CLOUDFLARE, [s. d.]b) | [cloudflare_r2](#ref-cloudflare_r2) |
| (COUNTY OF SAN DIEGO, [s. d.]) | [sandiego_c](#ref-sandiego_c) |
| (CPRv BM, [s. d.]) | [cprvbm_bloqueios](#ref-cprvbm_bloqueios) |
| (DEPARTAMENTO AUTÔNOMO DE ESTRADAS DE RODAGEM, [s. d.]) | [daer_rodovias](#ref-daer_rodovias) |
| (DRUSCH et al., 2012) | [drusch2012](#ref-drusch2012) |
| (ELEMENT 84, [s. d.]) | [earthsearch](#ref-earthsearch) |
| (EMPRESA PÚBLICA DE TRANSPORTE E CIRCULAÇÃO, [s. d.]) | [gtfs_eptc](#ref-gtfs_eptc) |
| (EUROPEAN SPACE AGENCY, [s. d.]) | [sentinel2_aws](#ref-sentinel2_aws) |
| (EUROPEAN SPACE AGENCY; AIRBUS, 2022) | [copernicus_dem](#ref-copernicus_dem) |
| (FINK et al., 2022) | [r5py](#ref-r5py) |
| (FLOODING MAPPING, 2025) | [events2025](#ref-events2025) |
| (GEOPANDAS, 2026) | [geopandas](#ref-geopandas) |
| (GILLIES et al., 2026a) | [shapely](#ref-shapely) |
| (GILLIES et al., 2026b) | [rasterio](#ref-rasterio) |
| (GOOGLE; GOOGLE DEEPMIND, [s. d.]) | [alphaearth_dataset](#ref-alphaearth_dataset) |
| (HAGBERG; SCHULT; SWART, 2008) | [networkx](#ref-networkx) |
| (HARRIS et al., 2020) | [numpy](#ref-numpy) |
| (HERSBACH et al., 2020) | [hersbach2020](#ref-hersbach2020) |
| (HUNTER, 2007) | [matplotlib](#ref-matplotlib) |
| (IBGE, [s. d.]) | [ibge_setores2022](#ref-ibge_setores2022) |
| (JOBLIB DEVELOPERS, 2026) | [joblib](#ref-joblib) |
| (LEAFLET, 2023) | [leaflet](#ref-leaflet) |
| (MAPLIBRE, 2024) | [maplibre](#ref-maplibre) |
| (MAPZEN, [s. d.]) | [aws_terrain](#ref-aws_terrain) |
| (MICROSOFT, [s. d.]) | [playwright](#ref-playwright) |
| (O'CALLAGHAN; MARK, 1984) | [ocallaghan1984](#ref-ocallaghan1984) |
| (OLOFSSON et al., 2014) | [olofsson2014](#ref-olofsson2014) |
| (OPEN-METEO, [s. d.]) | [openmeteo_docs](#ref-openmeteo_docs) |
| (OPENSTREETMAP CONTRIBUTORS, 2026) | [osm_geofabrik](#ref-osm_geofabrik) |
| (OSMCODE, 2026) | [pyosmium](#ref-pyosmium) |
| (PEDREGOSA et al., 2011) | [pedregosa2011](#ref-pedregosa2011) |
| (PORTO ALEGRE, [s. d.]a) | [pmpa_mymaps_drenagem](#ref-pmpa_mymaps_drenagem) |
| (PORTO ALEGRE, [s. d.]b) | [geopoa_drenagem](#ref-geopoa_drenagem) |
| (PORTO ALEGRE, [s. d.]c) | [pmpa_alagamentos](#ref-pmpa_alagamentos) |
| (PROFILL, 2023) | [profill2022](#ref-profill2022) |
| (PROTOMAPS, 2026a) | [pmtiles](#ref-pmtiles) |
| (PROTOMAPS, 2026b) | [protomaps_basemap](#ref-protomaps_basemap) |
| (PYPROJ4, 2023) | [pyproj](#ref-pyproj) |
| (PYTEST-DEV, 2026) | [pytest](#ref-pytest) |
| (PYTHON SOFTWARE FOUNDATION, 2026) | [requests](#ref-requests) |
| (PYTHON-PILLOW, 2026) | [pillow](#ref-pillow) |
| (ROBERTS et al., 2017) | [roberts2017](#ref-roberts2017) |
| (ROUAULT et al., 2026) | [gdal](#ref-gdal) |
| (SERVIÇO GEOLÓGICO DO BRASIL, [s. d.]) | [cprm_inundacao](#ref-cprm_inundacao) |
| (SIMONOV, 2025) | [pyyaml](#ref-pyyaml) |
| (SZWARCMAN et al., 2024) | [szwarcman2024](#ref-szwarcman2024) |
| (TENKANEN, 2026) | [pyrosm](#ref-pyrosm) |
| (TEXAS DEPARTMENT OF TRANSPORTATION, [s. d.]) | [txdot_c](#ref-txdot_c) |
| (THE PANDAS DEVELOPMENT TEAM, 2026) | [pandas](#ref-pandas) |
| (VIRTANEN et al., 2020) | [scipy](#ref-scipy) |
| (ZIPPENFENIG, 2023) | [openmeteo_software](#ref-openmeteo_software) |
