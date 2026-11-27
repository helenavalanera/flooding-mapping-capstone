# Glossário oficial de nomenclaturas

Um termo, um sentido. Este glossário vale para a landing, o WebGIS, o simulador, os resultados, o README e os relatórios. Quando o público lê primeiro o nome compreensível, o termo técnico vem entre parênteses.

## Grandezas do estudo

| Nome na interface | Termo técnico | O que representa | O que **não** é |
|---|---|---|---|
| **Geração de escoamento** (A) | geração de escoamento superficial (volume potencial local) | Estimativa do volume potencial de água que pode virar escoamento superficial, a partir da chuva de referência e das características da superfície sob o trecho (V = P × A × C ÷ 1000, em m³, em intervalo). Limite superior: sem infiltração nem perdas | Volume que de fato escoou, nem vazão, nem volume que chegou ao trecho |
| **Concentração do escoamento** (B) | contribuição acumulada a montante | Como a contribuição potencial de diferentes áreas converge e se distribui ao longo das trajetórias de fluxo (D8). Em cada trecho, é a geração somada sobre toda a área a montante | Vazão, volume efetivamente transportado, capacidade hidráulica; **não se soma entre trechos** (áreas a montante vizinhas se sobrepõem) |
| **Propensão topográfica à retenção** (C) | indicador topográfico (altura que o preenchimento de depressões soma a uma célula; posto relativo entre trechos) | Condições do relevo relativamente favoráveis à concentração ou à retenção de água, em um modelo de 30 m | Profundidade de alagamento, volume retido, duração; é relativo e sem unidade física |
| **Drenagem cadastrada** (D) | infraestrutura de drenagem cadastrada | Infraestrutura identificada nas bases da Prefeitura (rede pluvial, poços, bocas de lobo, casas de bomba). Camada de **contexto**, fora do cálculo | Prova de capacidade, funcionamento, conectividade hidráulica ou eficiência; a presença geométrica não comprova nada disso |
| **GeoAI** | aplicação de inteligência artificial e aprendizado de máquina a dados geoespaciais | Frente **experimental** de classificação de cobertura do solo (fração construída por célula) | Previsão de alagamentos, estimador de impermeabilidade, de coeficiente C, de vazão ou de volume; não entra no motor |
| **Alagamento** | (termo de comunicação com o público) | Usado só com a ressalva: o estudo **não prevê** a ocorrência de alagamentos nem determina profundidade ou duração da água | Resultado do estudo |

As letras A a D da aplicação (Geração, Concentração, Topografia, Drenagem) são independentes e **não formam índice composto**. Na aba Resultados, as cinco seções agrupam os mesmos conteúdos por contexto territorial: "Superfícies construídas e pavimentadas" e "Vegetação e demais coberturas" (geração), "Concentração do escoamento e propensão topográfica à retenção" (B e C) e "Drenagem cadastrada" (D).

## Termos de método

| Termo | Definição |
|---|---|
| **Chuva de referência (cenário de cálculo)** | Precipitação hipotética de 10, 20 ou 30 mm, **uniforme** em toda a cidade e sem distribuição no tempo. É entrada do motor, não previsão meteorológica. 30 mm é cerca do percentil 75 dos totais por evento da série de 2017 a 2026 (29,9 mm), não a média |
| **Evento** | Sequência de dias seguidos com pelo menos 1 mm de chuva na série diária. Um evento de dois dias **não** equivale a uma chuva de 24 horas |
| **Série de chuva** | Série diária de Porto Alegre do Open-Meteo, uma reanálise baseada em ERA5 (HERSBACH et al., 2020; ZIPPENFENIG, 2023). É modelada, não é pluviômetro |
| **Pacote de coeficientes** | Conjunto de valores do coeficiente de escoamento C: **Método 1** (fundamentado: Edificação e Vias Pavimentadas, faixas do TEXAS DEPARTMENT OF TRANSPORTATION, [s. d.]), **referência por analogia** (Campo, Pastagem, Jardins, em faixas declaradas) e **limites físicos** (C = 0 e C = 1). Cada pacote cobre classes diferentes e **nunca se somam** |
| **Coeficiente de escoamento (C)** | Fração da chuva que escoa. Valores de manuais de outros países, usados como faixas declaradas, não como calibração local |
| **Superfície construída ou pavimentada** | Classes Edificação e Vias Pavimentadas da Profill (PROFILL, 2023). Chamadas de "potencialmente impermeáveis" só em contexto: a impermeabilidade **não é medida** e o coeficiente dessas classes é menor que 1 |
| **Fração construída** (GeoAI) | Parcela da célula de 30 m em Edificação ou Vias Pavimentadas, estimada a partir de imagens. É concordância com a Profill, não impermeabilidade |
| **Concordância com a referência × validação independente** | Concordância é o acordo com os rótulos da Profill em blocos não vistos. **Validação independente** exigiria uma amostra de campo ou interpretada à parte (OLOFSSON et al., 2014), que não foi feita |
| **Trecho** | Segmento da rede viária do OpenStreetMap (OPENSTREETMAP CONTRIBUTORS, 2026): 176.836 trechos, a unidade de apresentação |
| **Célula** | Quadrado de 30 m da grade do modelo digital de elevação (EUROPEAN SPACE AGENCY; AIRBUS, 2022) |
| **Dados ausentes** | Trecho ou célula sem dado fica "sem dado", **nunca zero** |
| **Versão estática** | Publicação sem servidor: resultados, mapa de análise e simulador. As funções que dependem de servidor não fazem parte dela |
| **Frente arquivada** | Mobilidade, previsão de 72 h, ocorrências e o PWA, guardados em `src/flooding_mapping/app/arquivo/` para uma futura frente de monitoramento. **Não são funcionalidades atuais** |

## Termos a evitar

| Evitar | Usar | Por quê |
|---|---|---|
| "vazão" para um indicador do estudo | contribuição acumulada (potencial) | O estudo não calcula vazão. "Vazão" só aparece para dizer que a **capacidade de vazão** da drenagem não é conhecida |
| "área de alagamento", "risco de alagamento" para os resultados | geração, concentração ou propensão, conforme o caso | O estudo não prevê alagamentos |
| "impermeável" ou "impermeabilização" para as classes Edificação e Vias Pavimentadas | construída e pavimentada (potencialmente impermeável) | Construído não é impermeável, e impermeável não é C |
| "tempo real", "monitoramento", "alerta" | estudo, cenário de cálculo | Não há serviço em tempo real |
| "validado em campo" | concordância com a referência (Profill) em blocos espaciais não vistos | Não houve validação de campo |
| "o AlphaEarth supera o Random Forest" | empate, sem ganho demonstrado | Diferença de erro com intervalo que inclui zero |
| "volume retido" ou "profundidade" | propensão topográfica à retenção (indicador relativo) | Nenhum dos dois é calculado |
