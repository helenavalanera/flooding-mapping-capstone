# Fase 5: GeoAI para a fração construída por célula de 30 m

Experimento científico e conclusão técnica da Fase 5. Os números vêm de `docs/geoai_resultados.md`, **gerado** dos arquivos de resultado do experimento (`tools/gerar_relatorio_geoai.py`); nada foi digitado à mão. Nada aqui altera o motor de escoamento (Fase 3), a interface (Fase 4) ou os resultados oficiais.

## 1. Resposta curta

**A GeoAI melhorou, de forma mensurável e reproduzível, a caracterização geoespacial necessária para o escoamento em Porto Alegre? Não ficou demonstrado.** O que o experimento mostrou, com evidência:

- Um Random Forest sobre o Sentinel-2 **reproduz a fração construída da Profill** em blocos que nunca viu, com erro absoluto médio de **0,049** (intervalo de 95%: 0,041 a 0,058) e de **0,052** quando um quadrante inteiro do município é deixado de fora. O erro é baixo e estável em 83,5% dos blocos de 3 km.
- Os embeddings AlphaEarth (modelo de fundação) **empatam** com o Random Forest: diferença de MAE de −0,0009, com intervalo de −0,0029 a +0,0013, que contém zero. O macro F1 foi menor (0,624 contra 0,659). **Não há ganho do modelo de fundação.**
- **Não foi possível** medir ganho sobre a Profill, porque ela é o rótulo de treino e, ao mesmo tempo, a referência. Em Porto Alegre ela é interpretação visual de ortoimagem de 30 cm, mais fina que qualquer imagem pública (10 m). Não há o que melhorar na área mapeada.
- **Não foi testada** a hipótese que dá sentido prático à GeoAI no projeto (estimar a fração construída onde **não existe** mapeamento fino): não há outro município com referência equivalente nos dados, e a validação independente (interpretação manual de ortoimagem licenciada) não foi possível (seção 4, questão 4).
- O produto é uma **camada experimental de concordância com a Profill**. Ela não é impermeabilização, não é coeficiente de escoamento e **não entra no motor**.

**Classificação (critério da Fase 5): A, validada para uso experimental**, restrita ao Random Forest e à concordância com a Profill. Para o modelo de fundação o resultado é **C (sem ganho demonstrado)**; o Prithvi ficou **documentado, mas não executado**; a integração ao motor **não está validada** (não é B).

## 2. Problema e hipótese

Pergunta do projeto: *dada uma chuva, como o escoamento superficial tende a se distribuir pelo território?* O motor calcula V = P × A × C ÷ 1000 com C fundamentado só para Edificação e Vias Pavimentadas (17,3% da área); o restante é cenário declarado (`docs/fase3_motor.md`). A fração construída é, portanto, uma entrada central do motor.

Hipótese formulada na pesquisa de viabilidade e mantida: *técnicas de GeoAI aplicadas a imagens e representações geoespaciais podem estimar a fração de superfície construída por célula, com erro conhecido e aceitável, especialmente onde não há mapeamento urbano de alta resolução.* O experimento testa a parte "erro conhecido e aceitável" **dentro** de Porto Alegre e deixa a parte "onde não há mapeamento" como hipótese em aberto.

Definições que não se confundem: **construído** = classes Edificação e Vias Pavimentadas da Profill; **impermeável** = fração que não infiltra, que nenhuma fonte aqui mede; **efetivamente impermeável** e coeficiente C dependem de calibração hidrológica que não existe. A classe "Jardins, Passeios ou Áreas semi urbanizadas" (18,6% da área) é mista e fica **fora** das frações; ela aparece como estrato nas métricas.

## 3. Matriz de aderência ao FTL Capstone

Esta matriz usou os 14 requisitos da Matriz A de `docs/qa_relatorio_final.md` e os eixos informados na tarefa, porque o documento oficial ainda não estava no repositório. **O texto oficial chegou depois; a matriz de referência passou a ser [`capstone_requisitos.md`](capstone_requisitos.md)**, que registra as divergências (em especial a revisão da literatura e o deploy). Estados: Concluído, Parcial, Pendente.

| Requisito | Evidência existente | Situação | Ação necessária |
|---|---|---|---|
| Problema e justificativa | `README.md`, `docs/fase3_motor.md`, `docs/resultados_executivos.md` | **Parcial** | `docs/proposta.md` e os `.docx` descrevem só o escopo de mobilidade e não foram realinhados |
| Dados geoespaciais | `docs/inventario_fontes_poa.md`, tabela de fontes do README, manifestos de dados | **Parcial** | A regularização documental da Profill e do DAER é conduzida à parte pela responsável (`docs/base_legal_dados.md`); a camada E (derivada da Profill) é publicada com atribuição |
| GIS e sensoriamento remoto | Motor GIS (Fase 3); pipeline de Sentinel-2 executado (Fase 5) | Concluído | — |
| GeoAI | `src/flooding_mapping/geoai/`, `docs/geoai_resultados.md` | Concluído (experimental) | Validação independente e teste de transferência pendentes |
| Pipeline funcional | `tools/executar_geoai.py` (seis etapas), duas execuções idênticas, 27 testes | Concluído | — |
| Metodologia | Este documento e `docs/fase3_motor.md` | Concluído | — |
| Resultados | `docs/geoai_resultados.md`, `reports/qa/geoai_resultados.json`, COG | Concluído | — |
| Validação | Validação espacial por blocos contra a Profill (P1 e P2) | **Parcial** | Referência independente e validação hidrológica do motor não existem |
| Limitações | Seção 9 deste documento; `docs/mapa_simulador_pwa.md` | Concluído | — |
| Produto demonstrável | WebGIS, PWA, simulador (Fases 4 e 4.1); a GeoAI **não** está na interface, por decisão | Concluído | — |
| Código aberto | Licença MIT em `LICENSE`; código local | **Cumprido** | O código das Fases 3 a 5 e a camada E estão no repositório (`develop`); os dados volumosos ficam fora do Git |
| README e reprodução | Seção "Escoamento superficial e GeoAI" com comandos | **Parcial** | A introdução do README ainda trata só de mobilidade; a reprodução da Fase 3 remete a `docs/fase3_motor.md` |
| Documentação técnica | Este documento, `docs/geoai_resultados.md`, `docs/publicacao_pages_releases.md` | Concluído | — |
| Apresentação | `docs/apresentacao/Flooding_Mapping_Capstone_FTL_v2.pptx` (13 slides) | **Parcial** | Os slides e o roteiro não cobrem a Fase 3 a 5 nem a GeoAI |

Oito dos 14 itens estão concluídos e seis parciais. Nenhum está pendente, mas **os parciais incluem o material de entrega (apresentação, proposta, README)**.

## 4. Auditoria da pesquisa de viabilidade e resposta às dez questões

Reconferido diretamente nos arquivos e nas fontes: Apple M1, 8 núcleos, 8 GB de RAM, sem CUDA; Python 3.12.13; scikit-learn 1.9.1 e rasterio 1.5.2 (GDAL 3.12.2) já instalados; torch ausente; grade EPSG:31982 de 30 m (1314 × 1004); 554.807 células com cobertura do solo; Profill com 605.245 polígonos, 95,1% do município coberto e 24,4 km² de lacuna. Duas afirmações do relatório anterior mudaram: o bucket do AlphaEarth **é** legível sem credencial (resposta HTTP 206 anônima), e a documentação do Prithvi **declara** o patch de 16 pixels (`config.json`: `patch_size [1, 16, 16]`, 4 quadros, 6 bandas).

| # | Questão | Resposta e evidência |
|---|---|---|
| 1 | Fonte com cobertura suficiente | **Sentinel-2 L2A**, tile MGRS 22JDM: o footprint STAC contém o município inteiro (cobertura 1,0). HLS não foi usado (exige login Earthdata) e a cobertura do tile HLS não foi verificada |
| 2 | Período comparável com a Profill | **2019 a 2021** (a ortoimagem é de 2018 a 2021). 2018 foi excluído: o arquivo L2A global começa em dez/2018 e há só 14 cenas |
| 3 | Cenas válidas | 866 itens no catálogo (2019 a 2021), 646 aquisições distintas após deduplicar reprocessamentos, 356 com nuvem do tile ≤ 60%, **138 com ≥ 85% do município válido** pela SCL (após 40 m de folga em torno de nuvem e sombra). Usadas: **30** (10 por ano; válido médio 99,5%, mínimo 95,6%) |
| 4 | Licença da referência municipal | **Em regularização documental, conduzida à parte pela responsável** (`docs/base_legal_dados.md`; direitos "PROFILL, 2023"). A autorização de uso e de publicação de derivados, com atribuição, é de 27/11/2026; este documento não faz conclusão jurídica. A ortoimagem municipal, que serviria à validação manual, ainda não foi obtida |
| 5 | Atributos confiáveis | Seis bandas, quatro índices, três atributos temporais e dois de mistura intra-célula. Cada passo de S1 a S4 reduziu o MAE com intervalo que exclui zero (regra fixada antes), então o desvio intra-célula (textura) se justificou, com ganho pequeno (0,055 para 0,049) |
| 6 | Resolução efetiva | Pixels de 10 m agregados em células de 30 m (9 pixels). As bandas SWIR são de 20 m repetidas para 10 m; índices com SWIR têm resolução efetiva de 20 m |
| 7 | Modelos executáveis | Random Forest: sim (1 a 3 min por modelo). AlphaEarth: sim (RF de 21 min; a "inferência" é só leitura de rasters). Prithvi: **não executado** (seção 7) |
| 8 | Custo | Seção 10 (medido) |
| 9 | Independência treino x validação | **Parcial.** Blocos de 3 km com buffer de 150 m reduzem o vazamento espacial, mas o rótulo é da mesma fonte nos dois lados e os atributos vêm das mesmas imagens. Hiperparâmetros fixados antes; só o conjunto de atributos foi escolhido nos mesmos blocos (viés otimista pequeno) |
| 10 | Resultados defensáveis | Os da seção 1. Não são defensáveis: ganho sobre a Profill, exatidão contra a verdade de campo, desempenho em outras cidades, qualquer efeito no escoamento |

**Achado de qualidade de dados.** Os metadados STAC das 30 cenas (linha de processamento 05.00, reprocessadas em 2022 e 2023) declaram deslocamento radiométrico de −0,1, mas os números digitais **não** contêm o +1000 correspondente: a mediana do azul está em DN de 340 a 580 e 87 a 97% dos pixels ficam abaixo de 1.000. Aplicar o deslocamento daria reflectância negativa (observei isso na primeira composição, descartada). O código passou a **conferir** o deslocamento declarado contra os dados (`deslocamento_efetivo`, com teste) e usou deslocamento zero nas 30 cenas; o resultado tem reflectância mediana de 0,047 (azul) e 0,230 (infravermelho próximo). A causa na origem não foi investigada (não verifiquei com a documentação do provedor).

## 5. Fontes de dados e licenças

| Dado | Origem e acesso | Resolução, período, formato | Licença e restrições | Uso e transformação |
|---|---|---|---|---|
| Sentinel-2 L2A | Copernicus; COG em AWS Open Data (`sentinel-cogs`), catálogo Element 84 Earth Search; sem credencial | 10/20 m, 2019 a 2021, 30 cenas; COG | "Livres, completos e abertos" (aviso legal do Copernicus, citado pelo registro AWS) | Janela do município, máscara SCL, mediana, 4 índices, média 3 × 3 por célula |
| AlphaEarth, Satellite Embedding V1 anual | Google e Google DeepMind; `gs://alphaearth_foundations`, leitura anônima (a documentação diz que o bucket é "provider pays" desde julho de 2026) | 10 m, ano 2020, 64 bandas int8, COG, UTM 22S | **CC BY 4.0.** Atribuição obrigatória: "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and Google DeepMind." | Recorte do município, desquantização oficial, média 3 × 3 por célula |
| Profill 2022 | Prefeitura de Porto Alegre; `data/processed/uso_solo/` | Ortoimagem de 30 cm (2018 a 2021), 1:2.500; 605.245 polígonos | Regularização documental à parte (`docs/base_legal_dados.md`); uso e derivados autorizados com atribuição | Rótulos (frações por grupo) e referência |
| Edificações do OpenStreetMap | `data/interim/poa.osm.pbf` (Geofabrik) | Polígonos | ODbL | Verificação cruzada (não é independente) |
| Bairros de Porto Alegre | `data/processed/territorio_poa.json` | Polígonos | Fonte municipal (mesma ressalva) | Erro de área por bairro |

Nenhuma credencial, token ou dado privado foi usado ou gravado. Os dados baixados ficam em `data/interim/geoai/` e `data/processed/geoai/`, fora do Git.

## 6. Metodologia e protocolo

**Pipeline** (`tools/executar_geoai.py`, módulo `src/flooding_mapping/geoai/`): (1) `cenas` consulta o catálogo e mede a fração válida de cada cena no município pela SCL; (2) `baixar` grava o recorte das cenas escolhidas; (3) `atributos` calcula a composição mediana por pixel de 10 m (mínimo de 3 observações), os índices NDVI, NDBI, MNDWI e BSI, os percentis temporais e o desvio intra-célula, e agrega à grade do projeto (cada célula recebe exatamente 3 × 3 pixels; o deslocamento entre EPSG:32722 e EPSG:31982 na origem da grade é de 0,000 m); (4) `aef-baixar` e `aef-atributos` fazem o mesmo para os embeddings; (5) `avaliar` roda a validação e grava métricas, COG e manifesto.

**Rótulos.** Fração da célula em cada grupo (construído, vegetação, solo exposto, água) sobre a área que a Profill classifica fora da classe mista; a célula só entra se ao menos 540 m² (60%) estão em grupo não misto. O agrupamento das 15 classes está em `config/geoai.yaml` e é conferido por teste contra o dicionário real. Vegetação inclui Área Úmida e cultivos; solo exposto inclui Vias não Pavimentadas e Área Degradada (escolhas declaradas, não validadas).

**Modelos.** Random Forest multissaída das quatro frações (200 árvores, `min_samples_leaf` 5, `max_features` 0,33, subamostra de 150.000 células por dobra, semente fixa), com frações normalizadas para somar 1. Controles: média do treino e regressão linear em NDVI, NDBI e MNDWI. Conjuntos de atributos S1 a S4 (bandas; mais índices; mais temporais; mais intra-célula) e embeddings de 64 dimensões com Random Forest e com regressão linear. **Sem ajuste de hiperparâmetros**; sem pesos pré-treinados.

**Validação espacial.** Dois protocolos sobre as mesmas 407.574 células:
- **P1:** blocos de 100 × 100 células (a mesma unidade da pintura do uso do solo), 5 dobras equilibradas pela fração construída média do bloco, com buffer de 5 células (150 m) entre treino e teste; 79 blocos usados, 5 de borda excluídos (menos de 200 células).
- **P2:** deixar um quadrante inteiro (norte/sul × oeste/leste) de fora.

**Métricas.** MAE, RMSE e viés da fração construída; erro da área construída por bairro; matriz de confusão, precisão, recall, F1, macro F1 e IoU das classes duras (F1 de classe existente e nunca acertada vale zero); estabilidade entre blocos; incerteza (desvio entre as árvores, correlação com o erro e cobertura de um intervalo conforme de 90%). Intervalos de 95% por bootstrap de **blocos** (1.000 repetições). Acurácia global não é usada.

**Critérios de decisão.** Os limiares (MAE ≤ 0,10; viés ≤ 0,03; 80% dos bairros com erro de área ≤ 10%; ganho mínimo de 0,03 de macro F1 para o modelo de fundação) são **critérios operacionais propostos antes da execução, sem fundamento normativo**. Foram escolhidos por ordem de grandeza do que o motor tolera, não derivados de uma meta científica. A regra de escolha do conjunto de atributos (adotar o próximo só se o intervalo da redução de MAE exclui zero) também foi fixada antes.

**Hiperparâmetros e treinamento (modelo de documento do Capstone, 3.4).** Não há épocas, lote, taxa de aprendizagem nem otimizador: o Random Forest não é treinado por gradiente. Valores fixados em `config/geoai.yaml` **antes** da execução e **não ajustados** depois.

| Parâmetro | Valor |
|---|---|
| Algoritmo | `RandomForestRegressor` multissaída (scikit-learn 1.9.1) |
| Número de árvores | 200 |
| Tamanho mínimo da folha | 5 |
| Atributos por divisão | 0,33 do total |
| Função de perda | erro quadrático (padrão do scikit-learn) |
| Subamostra de treino por dobra | 150.000 células (sorteio com semente fixa) |
| Semente | 20261126 (cada dobra soma o número da dobra) |
| Divisão | validação cruzada espacial: 5 dobras de blocos de 3 km com buffer de 150 m (P1) e 4 quadrantes (P2); **não há conjunto de validação separado nem ajuste de hiperparâmetros**, então não há tuning a descrever |
| Controles | média do treino; regressão linear em NDVI, NDBI e MNDWI |

**Correspondência com o modelo de documento do Capstone:** dados (3.1) na seção 5; ETL e engenharia de atributos (3.2) na seção 6; seleção do modelo (3.3) nas seções 6 e 7; treinamento (3.4) nesta tabela; validação cruzada (3.5) na seção 6 e em `geoai_resultados.md` (seções 1 e 2); avaliação (3.6) em `geoai_resultados.md`. Aderência aos requisitos oficiais do programa: [`capstone_requisitos.md`](capstone_requisitos.md).

## 7. Foundation models

**Experimento B, AlphaEarth: executado.** As condições foram atendidas e verificadas: cobertura (anos 2017 a 2025 na zona UTM 22S, um arquivo cobre o município), acesso anônimo confirmado, licença CC BY 4.0 com atribuição documentada, grade compatível (10 m em UTM 22S) e custo aceitável (14 min de leitura, 0,7 GB). Mesmo protocolo e mesmas células. Resultado: **sem ganho** (seção 1). O embedding é anual e opaco: não permite ver mudança dentro do ano e não se explica por bandas.

**Experimento C, Prithvi: documentado, não executado.** Motivos, com evidência:
1. **Escala.** O `config.json` oficial dá patch de 16 pixels e 4 quadros: a 30 m, cada token cobre 480 m, dezesseis vezes o lado da célula. Estimar fração por célula exigiria um decodificador treinado, ou seja, ajuste fino.
2. **Recursos.** O ajuste fino é descrito pelos autores como feito em "uma única GPU" (A100 no pré-treino); a máquina disponível não tem CUDA e a inferência em CPU e a memória não são declaradas.
3. **Ambiente.** O `requirements.txt` do repositório fixa torch 2.5.0 e numpy 1.26.4, em conflito com o numpy 2.5.4 e o pandas 3.1 do projeto: exigiria ambiente isolado de vários gigabytes, mais 1,33 GB de pesos.
4. **Licença.** Pesos Apache-2.0 (Hugging Face) e código MIT (GitHub): permissivas, mas divergentes entre si; teria de ser conferido.
5. **Dados.** O pré-treino usa HLS de 30 m; o HLS exige login Earthdata (credencial que não foi usada).
6. **Hipótese.** Não há hipótese técnica melhor que a do AlphaEarth, que já empatou com o Random Forest: faltaria um motivo para esperar que um modelo de 30 m pré-treinado em tarefas sem classe urbana avaliada supere ambos.

Não foi baixado nenhum peso, e nenhuma dependência pesada foi instalada.

## 8. Resultados (síntese)

Detalhes, tabelas, matriz de confusão e figuras em [`geoai_resultados.md`](geoai_resultados.md). Resumo:

| | Resultado |
|---|---|
| MAE da fração construída, P1 | 0,049 [0,041; 0,058] (controle linear 0,116; média do treino 0,270) |
| MAE, P2 (quadrante fora) | 0,052 [0,044; 0,062] |
| Viés, P1 | 0,001 [−0,005; 0,006] |
| Blocos com MAE ≤ 0,10 | 83,5% |
| Erro da área construída, total dos bairros | +2,84%; mas só 57,4% dos bairros dentro de 10% (critério de 80% **não cumprido**) |
| Classes duras | construído F1 0,900 e IoU 0,818; vegetação F1 0,965; **solo exposto F1 0,228 e água F1 0,542: sem uso** |
| Células com mistura "Jardins/Passeios" > 30% | MAE 0,123 e viés −0,059 (contra MAE 0,029 sem mistura) |
| Incerteza | desvio entre árvores correlaciona 0,96 com o erro; cobertura do intervalo de 90% entre 87,7% e 91,2% por dobra |
| Verificação com OSM | OSM tem 92,5% da área de edificações da Profill, com correlação 0,959; **não é independente** |

Leitura. O erro é pequeno onde a célula é quase toda construída ou toda vegetada e cresce onde há mistura (jardins, passeios, telhados sob árvores). O critério por bairro falha por bairros periféricos com pouca área construída, onde um erro absoluto de até 0,48 km² vira erro relativo de 260% (o erro absoluto mediano é 0,036 km²); entre os nove bairros com mais de 1 km² construído, 67% ficam dentro de 10% (leitura exploratória, posterior à execução, que **não substitui** o critério fixado). Os mapas mostram viés negativo no centro denso e superestimação em áreas isoladas e grandes (pátios e coberturas amplas), que sem ortoimagem não consegui diagnosticar.

## 9. Limitações e ameaças à validade

- **A Profill é rótulo e referência.** Os números medem concordância com ela em blocos não vistos, não exatidão contra a verdade de campo. Seus erros e a idade do mapeamento (2018 a 2021) entram nas métricas. **Não houve validação independente** (interpretação manual de ortoimagem com licença de uso).
- **Sem teste de transferência.** Não há outro município com referência equivalente; o desempenho onde não existe mapeamento fino, que motivaria a GeoAI, é hipótese. P2 testa só quadrantes de uma mesma cidade.
- **Viés sazonal da composição.** A seleção das cenas mais limpas não incluiu nenhuma cena de janeiro a março (embora 38 das 138 cenas boas sejam desses meses), então os atributos temporais pouco representam o auge de vegetação. Não corrigi depois de ver os resultados para não ajustar a seleção ao desfecho.
- **Janelas diferentes.** Imagens de 2019 a 2021 e embedding de 2020 contra uma referência de 2018 a 2021; mudanças no período entram como erro.
- **Classes pequenas.** Solo exposto (2,8% das células) e água (0,8%) não são confiáveis a 10 m; o produto traz as frações, mas só a fração construída foi avaliada como alvo principal.
- **Classe mista.** "Jardins, Passeios..." fica fora; nas células com muita mistura o resultado piora e o viés é negativo.
- **Incerteza é do modelo.** O desvio entre árvores indica instabilidade do modelo, não probabilidade de erro; a alta correlação com o erro vem em parte de células triviais (vegetação pura). O intervalo conforme é aproximado.
- **Seleção do conjunto de atributos e do protocolo** nos mesmos blocos: viés otimista pequeno.
- **Extrapolação.** Fora das 407.574 células avaliadas (lago, outros municípios, células sem rótulo utilizável), o COG traz previsão do modelo final **sem validação** (banda `origem_da_previsao` = 2; 911.682 células).
- **COG.** A estrutura foi confirmada pelo marcador `LAYOUT=COG` do GDAL; a ferramenta formal de validação não rodou no ambiente.
- **Construído não é impermeável, e impermeável não é C.** Nada aqui se converte em volume, vazão, profundidade ou alagamento.

## 10. Requisitos computacionais (medidos neste experimento)

Máquina: Apple M1, 8 núcleos, 8 GB de RAM, sem GPU CUDA; Python 3.12.13. Memória de pico **não foi medida**; as etapas concluíram sem falha.

| Etapa | Tempo medido | Armazenamento |
|---|---|---|
| Consulta do catálogo e qualidade de 356 cenas (só SCL) | 9 min | — |
| Download do recorte de 30 cenas | 23,6 min (2,3 MB/s) | 3,3 GB em disco |
| Composição e atributos (por faixas de 40 linhas de células) | 12 a 14 min | 84 MB |
| Download do recorte AlphaEarth 2020 (leitura de um COG de 3,4 GB) | 14 min | 0,77 GB |
| Embeddings por célula | 28 s | 338 MB |
| Random Forest por modelo (5 dobras): S1 / S2 / S3 / S4 | 1 / 2 / 3 / 3 min | — |
| Random Forest com embeddings (64 atributos) | 21 min | — |
| Avaliação completa (P1, P2, OSM, COG, figuras) | 53 min | COG de 28 MB |

Tudo local e incremental; **nenhuma nuvem paga foi necessária**. Uma execução completa do zero leva cerca de 2 horas, quase toda de rede e do Random Forest sobre os embeddings.

## 11. Arquitetura e rastreabilidade

```
src/flooding_mapping/geoai/
  imagens.py     catálogo STAC, qualidade por cena, recorte em cache, conferência do deslocamento, embeddings do bucket
  atributos.py   composição mediana, índices, agregação 3 x 3 à grade de 30 m
  referencia.py  rótulos da Profill, blocos, dobras, buffer, OSM e bairros
  modelos.py     Random Forest, controles, validação por dobras
  avaliacao.py   métricas, bootstrap por blocos, incerteza
tools/executar_geoai.py            etapas cenas, baixar, atributos, aef-baixar, aef-atributos, avaliar (--rapido só checa o código)
tools/gerar_relatorio_geoai.py     docs/geoai_resultados.md e o mapa comparativo
config/geoai.yaml                  todos os parâmetros
tests/test_geoai.py                27 testes das peças, com dados sintéticos
```

O módulo não importa o motor e o motor não importa o módulo. Entradas: `config/geoai.yaml`, `data/processed/uso_solo/*`, `data/processed/municipality.parquet`, `data/interim/poa.osm.pbf`, `data/processed/territorio_poa.json`. Saídas, todas fora do Git: `data/processed/geoai/atributos_30m.npy`, `aef_30m_2020.npy`, `fracao_construida_30m_<id>.tif` (COG de 7 bandas em EPSG:31982, grade do projeto), `manifesto_<id>.json` e `reports/qa/geoai_resultados.json`.

O **manifesto** (`manifesto_geoai-fase5-f082089c4c59.json`) registra: identificador derivado do conteúdo da configuração e das cenas, fonte e período das imagens, as 30 cenas e o hash do registro de cada banda, CRS e resolução, modelo, conjunto de atributos e parâmetros, ausência de pesos pré-treinados, dobras e blocos excluídos, hashes SHA-256 dos dados de referência, dos atributos e do produto, versões de todas as dependências e a data. As bandas do COG: `fracao_construido`, `fracao_vegetacao`, `fracao_solo_exposto`, `fracao_agua`, `desvio_entre_arvores_construido`, `classe_predominante`, `origem_da_previsao`; fonte, período, versão do modelo e resolução vão também nas etiquetas do arquivo.

**Reprodutibilidade verificada:** duas execuções de `avaliar --rapido` (parâmetros mínimos) deram resultados **idênticos**. A execução completa não foi repetida (53 min); usa o mesmo código e as mesmas sementes.

**Formato.** COG para análise. Para a interface, o caminho seria derivar tiles agregados, como se fez com o escoamento; não se carregam rasters pesados no navegador, e nada disso foi feito.

## 12. Relação com o motor de escoamento

A camada pode servir a: (a) **caracterização independente** do território e **comparação** com a base cartográfica; (b) **variável de experimentos de sensibilidade**, alternando a fração construída de entrada e medindo o efeito sobre V. **Não deve** substituir coeficientes, converter probabilidade em C, tratar construído como impermeável ou aparecer como vazão, profundidade ou alagamento. Um pacote alternativo de coeficientes só faria sentido depois de calibração com escoamento medido, que não existe nos dados. Condições para qualquer uso além do experimental: referência independente, teste de transferência, validação hidrológica e autorização específica.

## 13. Trabalho futuro e pendências

1. Validação independente: amostra estratificada interpretada manualmente em ortoimagem municipal (ainda não obtida).
2. Teste de transferência em município com referência equivalente.
3. Seleção de cenas balanceada por estação (incluindo janeiro a março) e repetição do experimento.
4. Concluir a regularização documental da Profill e do DAER (conduzida à parte pela responsável).
5. Investigar a origem da divergência do deslocamento radiométrico com o provedor.
6. Só então reavaliar o Prithvi (ou outro modelo de 30 m) com ajuste fino em GPU.

## 14. Referências consultadas

- AlphaEarth Foundations: Brown e colegas, 2025, arXiv:2507.22291 (resumo); documentação do conjunto: `developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL` e `.../guides/aef_on_gcs_readme` (consultadas em 26/11/2026).
- Prithvi-EO-2.0: arXiv:2412.02732; cartões de modelo e `config.json` no Hugging Face (`ibm-nasa-geospatial/Prithvi-EO-2.0-300M`); repositório `NASA-IMPACT/Prithvi-EO-2.0`.
- Sentinel-2: SentiWiki (`sentiwiki.copernicus.eu`); registro AWS Open Data `sentinel-2-l2a-cogs`.
- Não foi feita revisão sistemática de literatura. Práticas usadas sem consulta nesta sessão e, portanto, não citadas como evidência: amostragem e estimação de área para validação de mapas de cobertura (Olofsson e colegas, 2014) e Random Forest (Breiman, 2001).


## 15. Integração ao produto: a camada E (27/11/2026)
O resultado da Fase 5 entra no produto como uma **quinta camada, experimental e independente**: *E. Fração construída estimada (GeoAI)*. Detalhes, arquivos, números e limites em [`geoai_camada_e.md`](geoai_camada_e.md). Nenhum modelo foi retreinado, nenhum experimento novo foi executado e nada do que a camada mostra entra no motor nem nas dimensões A a D.
