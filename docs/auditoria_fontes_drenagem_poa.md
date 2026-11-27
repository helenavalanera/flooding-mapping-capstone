# Auditoria das fontes municipais de drenagem, uso do solo, relevo e risco (Porto Alegre)

Coleta e medição em 25/11/2026, a partir dos serviços GIS da Prefeitura (`gis-smamus.portoalegre.rs.gov.br`). Relatório técnico, sem integração ao modelo: nada aqui calcula alagamento.

- Dados: [reports/qa/auditoria_drenagem_poa.json](../reports/qa/auditoria_drenagem_poa.json), [reports/qa/mdt_2010_piloto.json](../reports/qa/mdt_2010_piloto.json).
- Reprodução: `tools/baixar_drenagem_poa.py` (coleta, manifesto e hash em `data/raw/manifest.json`), `tools/auditar_drenagem_poa.py`, `tools/avaliar_mdt_poa.py`.
- Testes: `tests/test_drenagem_poa.py` (dados sintéticos, sem consultar o servidor).
- Os arquivos brutos ficam em `data/raw/drenagem_poa/` (fora do Git). Não foram baixados campos com nomes de servidores ou de empresas, documentos, links nem texto livre.

## 1. Os endereços do enunciado diferem do que o serviço publica

| No enunciado | O que o serviço é de fato |
|---|---|
| Camada 49, "grupo de consulta" | **Coletor de Fundo** (pontos, 1.868). O grupo "Cadastro Pluvial" é a camada **48** |
| Camada 58, "rede pluvial" | **Rede Pluvial sem Acesso**. A rede pluvial é a camada **57** |
| Camada 59, "rede pluvial sem acesso" | **Rede Pluvial não interligada** |
| `rede_pluvial/FeatureServer` | Cópia pública, em SIRGAS 2000 (EPSG:4674), **sem altitudes, inserção nem declividade** |
| `recurso_hidrico` | É uma pasta, sem camadas. O recurso hídrico do cadastro é a camada **56** da consulta |
| `ram_hidrografia_2014/0` | **Polígonos de Áreas de Preservação Permanente** (139), não cursos d'água; créditos: "com base no aerolevantamento de 1982" |

Camadas do cadastro pluvial que o enunciado não citava e que a auditoria incluiu: poço de visita (88.906), grelha (955), canal pluvial (1.752 e 31 sem acesso), conduto forçado (108).

## 2. Rede pluvial (camada 57)

| Medida | Resultado |
|---|---|
| Trechos | 133.060, em 2.877,7 km pela geometria (2.877,8 km pelo campo `EXTENSAO`: consistente) |
| Geometria | 0 inválidas, 0 sem geometria, 73 duplicatas exatas |
| Referência espacial | 3857 no serviço; coletada em SIRGAS 2000 / UTM 22S (métrica) |
| **Identificador próprio** | **Não há.** Só `OBJECTID`, que pode mudar se a camada for republicada |
| **Nós ou trechos a montante e a jusante** | **Não há campo.** A conectividade só pode ser inferida pela geometria |
| `DIAMETRO` (mm) | 100% preenchido; 75 a 2.000, mediana 300 (69% dos trechos têm 300 mm) |
| `MATERIAL` | **7,7%** preenchido (concreto "CR" na maior parte) |
| `CLASSE` | 12,5% com valor real (o resto é vazio ou espaço em branco) |
| `ALTITUDE_MONTANTE` e `ALTITUDE_JUSANTE` | 88,0% e 88,3% preenchidas; **3 e 5 valores impossíveis** (até 283.465 m) |
| `INSERCAOMONTANTE` | 89,9% preenchida, mas **43.820 trechos (33% do total) têm valor zero** (zero pode ser dado ausente) |
| `DECLIVIDADE` | **4,2%** preenchida, com 132 valores fora de faixa (de −93.539 a 519) |
| Consistência | Entre os trechos com as duas altitudes, **85% têm montante ≥ jusante** (15% invertidos); a declividade informada bate com a calculada (correlação 0,998) |
| `ATIVO` | 97,6% preenchido; 129.858 ativos, 3.202 sem informação |
| Datas | Datas de implantação só em 4,8% (há um ano 0202, erro de digitação); atualização em 20,7% |

**Conectividade geométrica** (extremos que coincidem com outro extremo ou com um poço de visita; evidência, não confirmação hidráulica):

| Tolerância | Ambos os extremos ligados | Um extremo | Nenhum |
|---|---|---|---|
| 0,1 m | 59,4% | 39,4% | 1,2% |
| 0,5 m | 69,5% | 29,9% | 0,6% |
| 2 m | 79,9% | 19,7% | 0,5% |

Cerca de 81% dos extremos caem a até 1 m de um poço de visita. Há 41.477 extremos livres (sem outro extremo a 0,5 m nem poço a 1 m). Só **9,3%** deles estão a até 25 m de um recurso hídrico, então os extremos livres não são, em geral, pontos de descarga: são lacunas do cadastro ou trechos sem poço registrado.

**Classificação dos registros (item 3.1).** Rede pluvial (camada 57): 133.060 trechos. **Rede sem acesso** (58): 2.775 trechos, 84,1 km, `ACESSO = 0` em todos, **diâmetro em só 45%** e altitudes em **0,6%**. **Rede não interligada** (59): 21 trechos, 0,5 km, `ATIVO = 0` em todos. As duas últimas não têm a mesma funcionalidade hidráulica da rede operacional e **não entram** em um grafo funcional.

**Camada pública contra a de consulta.** 127.416 trechos coincidem por geometria (a 1 m); 5.485 só existem na consulta e 5.860 só na pública (cópias de datas diferentes). Entre os coincidentes, 99,9% têm o mesmo diâmetro. A pública não traz altitudes, inserção nem declividade.

## 3. Bocas de lobo (camada 51)

| Medida | Resultado |
|---|---|
| Pontos | 44.868 na consulta (44.336 na pública); 4 rejeitados por coordenada `NaN` |
| Capacidade | **Não há campo de capacidade** |
| Relação com a rede | **Não há campo** que diga em que trecho cada boca descarrega |
| `TIPO` | 85,9% preenchido, com códigos numéricos (1 a 5) sem legenda no serviço; 85% de todos os pontos são "1" |
| `ESPELHO` | 6,5% preenchido |
| `PROFUNDIDADE` | 91,6% preenchida, mas **36.785 pontos (82% do total) têm valor zero** (provável valor ausente, não profundidade) |
| `ALTITUDETAMPA` | 89,3% preenchida; 19 valores negativos (até −0,47 m, plausíveis em Porto Alegre) |
| Estado de funcionamento | Não informado (`ENABLED = 1` em 100%, sem significado hidráulico) |
| Distância à rede pluvial mais próxima | Mediana 0 m; **99% a até 2 m**; 0,2% a mais de 50 m |
| Densidade por bairro | Mediana de 205 por km²; bairros rurais ou de ilhas com menos de 5 por km² (Arquipélago, Extrema, Lageado, Lami, São Caetano, Boa Vista do Sul) |

A proximidade de 99% a até 2 m mostra que os pontos foram desenhados sobre a rede, mas **não prova conexão hidráulica nem funcionamento**. Por isso o resultado serve para representar os pontos de captação, não para calcular capacidade de captação.

## 4. Casas de bombas e EBAPs

- 24 unidades no serviço; **só o campo `name` está preenchido**. `capacidade`, `local`, área protegida, área de contribuição, configuração e endereço estão **vazios em todos os registros** (100%).
- **Não há capacidade, nem unidade, nem grandeza (vazão ou potência).** O campo é texto e está em branco; nenhum cálculo pode usá-lo.
- Contra as 20 do projeto: 19 têm o mesmo nome, com diferença de posição de até **443 m** entre as duas fontes. O projeto tem uma única "CB-11"; o serviço tem "CB-11A" e "CB-11B" (a 177 m e 80 m). Há **3 unidades novas** no serviço: CB ASA BRANCA, CB TRINCHEIRA CEARÁ e CB SANTA TEREZINHA.
- O que os dados permitem: localização e nome das unidades. Nada de operação.

## 5. Hidrografia

| Camada | Resultado |
|---|---|
| Recurso hídrico (56) | 5.989 feições, 766,1 km, 13 duplicatas exatas; `TIPO` vazio em 45%; `NOME` em 25%; `LEITO` em 99,95% |
| Natural e artificial | `LEITO` separa os dois: natural (4.194), canalizado (875), em galeria (790), retificado (127). Há escrita inconsistente (ARROIO e Arroio) |
| Datas | `DATACAMPO` quase vazia, com um valor 1899-12-30 (data zero de planilha) |
| Os 679 arroios do projeto | 471,6 km. **Só 18% dos pontos dos arroios do projeto estão a até 25 m do recurso hídrico** (34% a até 50 m): as duas fontes divergem muito |
| APP, "Hidrografia 2014" | 139 polígonos, 81,8 km², baseados no aerolevantamento de 1982: **áreas de preservação, não cursos d'água** |

As três coisas (recurso hídrico do cadastro, arroios do mapa e APP) **não são duplicatas** e precisam de reconciliação antes de qualquer uso. Hidrografia natural e drenagem urbana ficam separadas.

## 6. Uso e ocupação do solo, Profill 2022

| Medida | Resultado |
|---|---|
| Polígonos | 605.245, em 15 classes, 472,5 km² classificados |
| Origem | Interpretação visual de ortoimagem de 2018 a 2021 (30 cm), escala de produção 1:2.500, feita para a política de proteção da Mata Atlântica; créditos PROFILL, 2023 |
| Escala 1:2.500 | É a escala do mapa. **Não é resolução de 2.500 m nem garantia de precisão dos limites** |
| Referência espacial | SIRGAS 2000 (4674) |
| Campos | `classe`, `area_m2`, `area_ha`, `fitofisionomia`, `estagio`, `regiao` |
| Qualidade da geometria (piloto de 1 km², 2.208 polígonos) | **0 inválidas, cobertura de 100% da caixa, 0 sobreposição, 4,4 m² de lacuna**; o campo `area_m2` difere da geometria em 0,08% (mediana) |
| Não medido | A validade, a sobreposição e as lacunas do município inteiro: só o recorte piloto foi baixado (605 mil polígonos) |

Área por classe (km² e % dos 472,5): Vegetação Nativa 137,9 (29,2%); Jardins, Passeios ou Áreas semi urbanizadas 87,9 (18,6%); **Edificação 58,4 (12,4%)**; Campo 48,1 (10,2%); Área Úmida 32,5 (6,9%); **Vias Pavimentadas 23,3 (4,9%)**; Cultivo não Irrigado 17,2; Vegetação Mista 15,1; Cultivo Irrigado 14,1; Reflorestamento 11,6; Pastagem 8,3; Solo Exposto 8,0; Corpo Hídrico 3,6; Área Degradada 3,3; Vias não Pavimentadas 3,3.

**Correspondência com categorias hidrológicas** ([config/uso_solo_profill_hidrologia.csv](../config/uso_solo_profill_hidrologia.csv)). Cada classe registra categoria, coeficiente (ou a ausência dele), fonte, justificativa e incerteza. A fonte consultada é a Tabela 4-10 do manual de hidráulica da TxDOT (obtida e lida em 25/11/2026).

| Tratamento | Classes | Área |
|---|---|---|
| **Faixa fundamentada** | Edificação (0,75 a 0,95, "Roofs"); Vias Pavimentadas (0,70 a 0,95, envelope de tijolo, asfalto e concreto) | **17,3%** |
| **Cenário declarado** (sem número defensável) | 11 classes: vegetação, campo, pastagem, cultivos, solo exposto, área degradada, via sem pavimento e **Jardins, Passeios ou Áreas semi urbanizadas** | **75,1%** |
| **Fora do cálculo de escoamento** | Área Úmida e Corpo Hídrico | 7,6% |

A classe "Jardins, Passeios ou Áreas semi urbanizadas" mistura vegetação e piso sem dizer a proporção e ocupa **40% da área do piloto urbano**: é a maior fonte de incerteza para a impermeabilização na cidade construída. Os coeficientes das demais classes dependem de solo e declividade, que não foram integrados (a pedologia de 2008 existe no catálogo municipal e não foi inspecionada).

Termo a usar: **"impermeabilização estimada a partir do uso e ocupação do solo"**, nunca "impermeabilização medida".

## 7. Relevo: MDT, MDS e LiDAR

Busca no portal do GeoPOA (a página é uma aplicação que carrega o catálogo por um portal ArcGIS) por MDT, MDS, LiDAR, curvas de nível, ortofoto, aerolevantamento e relevo.

| Produto | O que é | Situação |
|---|---|---|
| **MDT 2010** (`urb_mdt_2010_102100`, Image Service) | Raster de ponto flutuante (F32), **pixel de 1 m** (unidade de Web Mercator, ~0,87 m no terreno), valores de −1,28 a 310,63 m, média 43,4 m | Acesso confirmado (identify e exportImage). **Sem download de arquivo, sem licença e sem precisão vertical declaradas.** Dados de 2010 |
| **MDE_tif** (Image Service, 09/10/2026) | Raster de **8 bits**, pixel de 29 m, valores de 73 a 250, `noData` 255 | **Não é elevação em metros** (parece imagem escalada). Não usar sem documentação |
| Curvas de Nível e Pontos Cotados (2010) | Feições vetoriais | Disponíveis (não inspecionadas em detalhe) |
| "Relevo" (Curvas de Nível e Pontos Cotados, 2026) | Feições vetoriais, TM-POA | Disponível (não inspecionada em detalhe) |
| **LiDAR** | Nenhum item no portal | **Não encontrado** |
| Edificações 2010 3D | Extrudidas a partir do aerolevantamento de 2010, do MDT e de outros dados | Confirma a existência do MDT de 2010 |

**Comparação com o Copernicus GLO-30** (334 marcos geodésicos da Prefeitura, altitude ortométrica, mesmos pontos; piloto):

| Medida | MDT 2010 | Copernicus GLO-30 |
|---|---|---|
| Erro médio absoluto | **0,77 m** | 2,18 m |
| Viés | −0,68 m | +1,26 m |
| RMSE (viés removido) | 3,21 m | 3,76 m |
| Dentro de 1 m | **79,9%** | 32,6% |
| Dentro de 2 m | 97,6% | 62,6% |
| Cotas abaixo de 10 m (80 marcos): erro médio absoluto | **0,62 m** | 1,89 m |
| Cotas abaixo de 10 m: correlação de ranking | **0,91** | 0,54 |

**Ressalvas que valem tanto quanto os números:**
1. **Não é validação independente.** Os marcos da rede geodésica municipal podem ter servido de controle ao próprio aerolevantamento de 2010.
2. **A exatidão vertical (~0,6 a 0,8 m) é maior que a profundidade das depressões de rua.** Na área piloto (14 registros de alagamento num raio de 500 m), a profundidade mediana das depressões do MDT é de **0,11 m**, abaixo da incerteza vertical: só depressões bem mais fundas (de cerca de 1 m ou mais, como passagens inferiores) são interpretáveis. O microrrelevo de meio-fio e sarjeta continua fora do alcance.
3. O MDT reduzido a 30 m dá 16 depressões e 6.600 m³ de armazenamento potencial; o Copernicus, 39 e 118.000 m³. Os números do preenchimento de depressões **não são volume retido**: acusam ruído, canais e lagos, e uma depressão só retém se não tiver saída por drenagem.
4. Uma única área piloto de 1 km².
5. Para usar o MDT em todo o município é preciso confirmar a **licença**, exportar por blocos (1 m dá cerca de 500 milhões de células) e decidir a resolução.

**Decisão sobre o relevo:** manter o Copernicus no modelo atual. O MDT 2010 é candidato forte para microtopografia e para o fluxo em escala de rua, **dependente de confirmação formal de licença, precisão e aquisição em lote**. Não substituir o DEM atual antes de avaliar a consistência em mais áreas.

## 8. Risco de inundação, CPRM

| Medida | Resultado |
|---|---|
| Polígonos | 2.216; 26 com geometria inválida (precisam de reparo antes de qualquer sobreposição) |
| Classes | **Alto** (1.526; 234,8 km²), **Médio** (541; 12,8 km²), **Baixa** (149; 3,2 km²). **Não existe "Muito Alto"**, embora a descrição do serviço fale em alto e muito alto risco |
| Cobertura | 250,8 km² (**53% da área dos bairros**; só a classe Alto cobre cerca de metade da cidade) |
| Origem | Modelagem validada por trabalho de campo da CPRM entre 2012 e 2014; processo "Inundação"; escala e critérios dependem da nota técnica do projeto, que não está no serviço |
| Edição | A camada é **editável no servidor** (capacidades de criar, atualizar e apagar): o conteúdo pode mudar sem aviso; usar só a cópia coletada, com hash |
| Atributo `Shape__Area` | Está em graus quadrados: não usar para área |

Uso permitido: contextualização, comparação qualitativa, sobreposição com resultados e discussão de plausibilidade. **Não** usar como rótulo de alagamento observado, como prova de que uma rua alaga em um cenário, nem como profundidade ou duração. Risco mapeado, ocorrência histórica e simulação hidráulica são três coisas distintas. Como metade da cidade está na classe Alto, a camada discrimina pouco.

## 9. Problemas de qualidade a tratar na integração

- Coordenadas `NaN`: 7 poços de visita e 4 bocas de lobo (rejeitados na coleta e contados).
- Altitudes e declividades impossíveis na rede (3, 5 e 132 trechos), a tratar como ausentes.
- Zeros que parecem dado ausente (profundidade em 82% das bocas, inserção em 33% dos trechos, ambos sobre o total).
- 15% dos trechos com altitude de montante menor que a de jusante: o sentido de digitalização não é garantia de sentido de escoamento.
- Datas sentinela (0202-08-01; 1899-12-30).
- Rótulos com escrita inconsistente (ARROIO e Arroio; VALA e Vala; NATURAL e Natural).
- Códigos sem legenda (`TIPO` das bocas de lobo).
- Sem identificador estável: o `OBJECTID` pode mudar entre republicações.

## 10. O que esta auditoria não fez

- Não baixou os 605 mil polígonos de uso do solo; não mediu validade, sobreposição e lacunas no município inteiro.
- Não inspecionou a pedologia, as curvas de nível, os pontos cotados nem a camada "Relevo".
- Não confirmou licença, precisão vertical nem datas de produção do MDT (o serviço não as traz).
- Não avaliou a camada 48 (grupo) nem a de "Canal Pluvial sem Acesso" além da contagem.
- A conectividade é geométrica; nenhum grafo hidráulico foi construído.
