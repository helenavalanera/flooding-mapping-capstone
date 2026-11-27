# Sensibilidade hidrológica: a física simplificada acrescenta informação ao índice atual?

Experimento **exploratório**. Não altera o índice nem o modelo de produção, não prevê profundidade nem ocorrência de alagamento e não valida previsão condicionada à chuva.

## Conclusão

**Não há evidência de ganho incremental: nenhuma formulação física, sozinha ou combinada, atinge +10% de precisão média sobre a regra atual com limite inferior do intervalo acima de zero em todos os cenários de C. A regra atual permanece; nenhuma adoção é proposta.**

Amostra: 107.869 trechos, 124 rotulados (a até 100 m de um registro da Prefeitura, 2013–2014), taxa base 0,115%. Blocos espaciais de 1,5 km, 5 dobras, bootstrap pareado de 2000 réplicas sobre os positivos.

Distribuição espacial dos positivos (blocos de 1,5 km): 53 blocos com positivo, o maior com 18 (14,5%), número efetivo de blocos 21,0. Semente 7.

## Equações e unidades

```
A_i  = expm1(log_flow_acc_i) · 30²              [m²]  área a montante (D8, células de 30 m)
a_i  = A_i / 30                              [m]   área por metro de largura de fluxo
tanβ = max(tan(slope_i), 0,001)              [-]   slope em graus
V_i  = P · C_i · A_i                         [m³]  volume afluente potencial (não é profundidade)
B_i  = ln(a_i / tanβ_i)                      [-]   TWI: fluxo ajustado pela declividade
C_i  = ln(P · C_i · a_i / tanβ_i) = B_i + ln C_i + ln P    índice relativo (unidade arbitrária)
D1_i = ½·rank(regra atual) + ½·rank(C_i)    sem parâmetros ajustados
D2   = regressão logística (5 componentes + C_i) vs. (5 componentes), mesmas dobras
```

Com chuva uniforme e C constante, P e C deslocam B por uma constante: **a ordem dos trechos não muda**. Verificado nos 24 cenários: ordem independente da chuva = True. A precipitação uniforme só escala o volume; ela não diferencia ruas. Para C afetar a ordem ele precisa variar no espaço; os cenários `espacial_*` usam a densidade viária (250 m) como proxy de cenário, não como medida de impermeabilização.

## Cenários e hipóteses

- Chuva uniforme hipotética: 10, 30 e 60 mm (não são limiares de risco).
- Coeficientes de escoamento C: faixas típicas do método racional conferidas em manuais de agências ([TxDOT, Hydraulic Design Manual](https://www.txdot.gov/manuals/des/hyd/chapter-4--hydrology/section-12--rational-method/runoff-coefficients.html); [San Diego County, Hydrology Manual](https://www.sandiegocounty.gov/content/dam/sdc/dpw/FLOOD_CONTROL/floodcontroldocuments/hydro-evalcvalues.pdf)): asfalto e concreto 0,70–0,95; residencial unifamiliar 0,30–0,50 (outras fontes citam 0,30–0,75 para áreas residenciais em geral); gramado 0,05–0,35 conforme solo e declividade. A tabela do livro de Chow, Maidment & Mays (1988) **não foi consultada diretamente**. Nenhum valor é calibrado para Porto Alegre.
- Cenários de C: `uniforme_0,30`, `uniforme_0,50`, `uniforme_0,70`, `uniforme_0,90`, `espacial_0,30-0,50`, `espacial_0,50-0,70`, `espacial_0,70-0,95`, `espacial_0,30-0,95`.

## Comparação de métricas (precipitação base 30 mm; o ranking não depende de P)

| Modelo | AUC | Precisão média | IC95 da precisão média | Positivos no top 10% | Ganho vs. regra | IC95 do ganho (trechos) | IC95 do ganho (blocos de positivos) | IC95 do ganho (blocos completos) | Atende o critério |
|---|---|---|---|---|---|---|---|---|---|
| A. Regra atual | 0.666 | 0.00205 | 0.001677–0.002902 | 0.169 | referência | | | | |
| B. Fluxo ajustado pela declividade | 0.607 | 0.00185 | 0.001493–0.002563 | 0.21 | -9.9% | -25.2% a +6.3% | -33.4% a +13.3% | -33.8% a +14.7% | não |
| C · uniforme_0,30 | 0.607 | 0.00185 | 0.001493–0.002563 | 0.21 | -9.9% | -25.2% a +6.3% | -33.4% a +13.3% | -33.8% a +14.7% | não |
| C · uniforme_0,50 | 0.607 | 0.00185 | 0.001493–0.002563 | 0.21 | -9.9% | -25.2% a +6.3% | -33.4% a +13.3% | -33.8% a +14.7% | não |
| C · uniforme_0,70 | 0.607 | 0.00185 | 0.001493–0.002563 | 0.21 | -9.9% | -25.2% a +6.3% | -33.4% a +13.3% | -33.8% a +14.7% | não |
| C · uniforme_0,90 | 0.607 | 0.00185 | 0.001493–0.002563 | 0.21 | -9.9% | -25.2% a +6.3% | -33.4% a +13.3% | -33.8% a +14.7% | não |
| C · espacial_0,30-0,50 | 0.611 | 0.00189 | 0.001522–0.002657 | 0.21 | -8.2% | -23.6% a +11.1% | -33.0% a +15.7% | -32.5% a +17.7% | não |
| C · espacial_0,50-0,70 | 0.61 | 0.00187 | 0.001512–0.00262 | 0.21 | -8.8% | -24.0% a +9.5% | -33.1% a +14.4% | -33.0% a +16.1% | não |
| C · espacial_0,70-0,95 | 0.61 | 0.00187 | 0.00151–0.002609 | 0.21 | -8.9% | -24.1% a +9.0% | -33.1% a +14.1% | -33.1% a +16.0% | não |
| C · espacial_0,30-0,95 | 0.615 | 0.00193 | 0.001545–0.002783 | 0.218 | -6.1% | -22.1% a +16.1% | -32.2% a +20.7% | -31.4% a +22.2% | não |
| D1 · uniforme_0,30 | 0.64 | 0.0021 | 0.001628–0.003816 | 0.21 | +2.2% | -12.0% a +60.0% | -17.6% a +78.5% | -16.7% a +77.5% | não |
| D1 · uniforme_0,50 | 0.64 | 0.0021 | 0.001628–0.003816 | 0.21 | +2.2% | -12.0% a +60.0% | -17.6% a +78.5% | -16.7% a +77.5% | não |
| D1 · uniforme_0,70 | 0.64 | 0.0021 | 0.001628–0.003816 | 0.21 | +2.2% | -12.0% a +60.0% | -17.6% a +78.5% | -16.7% a +77.5% | não |
| D1 · uniforme_0,90 | 0.64 | 0.0021 | 0.001628–0.003816 | 0.21 | +2.2% | -12.0% a +60.0% | -17.6% a +78.5% | -16.7% a +77.5% | não |
| D1 · espacial_0,30-0,50 | 0.642 | 0.00212 | 0.001632–0.003895 | 0.218 | +3.0% | -11.6% a +63.6% | -17.5% a +82.8% | -16.5% a +85.8% | não |
| D1 · espacial_0,50-0,70 | 0.642 | 0.00211 | 0.00163–0.003891 | 0.21 | +2.9% | -11.6% a +63.4% | -17.4% a +82.7% | -16.6% a +85.6% | não |
| D1 · espacial_0,70-0,95 | 0.642 | 0.00211 | 0.00163–0.00389 | 0.21 | +2.8% | -11.7% a +63.4% | -17.5% a +82.7% | -16.7% a +85.5% | não |
| D1 · espacial_0,30-0,95 | 0.645 | 0.00217 | 0.001641–0.004237 | 0.218 | +5.7% | -10.9% a +79.1% | -16.9% a +102.9% | -16.2% a +111.3% | não |
| D2 · uniforme_0,30 | 0.698 | 0.00192 | 0.001718–0.002269 | 0.137 | -6.5% | -33.4% a +18.2% | -42.8% a +25.9% | -41.5% a +22.9% | não |
| D2 · uniforme_0,50 | 0.698 | 0.00192 | 0.001718–0.002269 | 0.137 | -6.5% | -33.4% a +18.2% | -42.8% a +25.9% | -41.5% a +22.9% | não |
| D2 · uniforme_0,70 | 0.698 | 0.00192 | 0.001718–0.002269 | 0.137 | -6.5% | -33.4% a +18.2% | -42.8% a +25.9% | -41.5% a +22.9% | não |
| D2 · uniforme_0,90 | 0.698 | 0.00192 | 0.001718–0.002269 | 0.137 | -6.5% | -33.4% a +18.2% | -42.8% a +25.9% | -41.5% a +22.9% | não |
| D2 · espacial_0,30-0,50 | 0.695 | 0.0019 | 0.001697–0.002231 | 0.129 | -7.6% | -33.4% a +15.3% | -42.7% a +21.4% | -41.3% a +19.6% | não |
| D2 · espacial_0,50-0,70 | 0.696 | 0.0019 | 0.001702–0.00224 | 0.137 | -7.3% | -33.5% a +16.1% | -42.9% a +22.9% | -41.5% a +20.8% | não |
| D2 · espacial_0,70-0,95 | 0.696 | 0.00191 | 0.001704–0.002244 | 0.129 | -7.2% | -33.5% a +16.3% | -42.8% a +23.3% | -41.6% a +20.8% | não |
| D2 · espacial_0,30-0,95 | 0.691 | 0.00188 | 0.001677–0.002216 | 0.153 | -8.5% | -32.4% a +12.0% | -41.5% a +18.0% | -40.9% a +17.0% | não |

## Testes de sensibilidade

- **Monotonicidade:** o volume afluente potencial cresce com a chuva em todos os cenários (True) e com C uniforme (True).
- **Estabilidade do ranking espacial:** Spearman entre cenários de C: mínimo 0.9886, médio 0.9972.
- **Sensibilidade a C:** a precisão média do modelo C varia 4.3% (amplitude relativa) entre os cenários.
- **Correlação de postos entre modelos** (cenário `espacial_0,30-0,95`, escolhido por ser o mais distante de B, não por desempenho):

| | A | B | C | D1 | D2 |
|---|---|---|---|---|---|
| A | 1.0 | 0.892 | 0.885 | 0.971 | 0.766 |
| B | 0.892 | 1.0 | 0.989 | 0.968 | 0.568 |
| C | 0.885 | 0.989 | 1.0 | 0.971 | 0.569 |
| D1 | 0.971 | 0.968 | 0.971 | 1.0 | 0.689 |
| D2 | 0.766 | 0.568 | 0.569 | 0.689 | 1.0 |

- **Contribuição incremental** (ganho relativo de precisão média): D1 sobre a regra atual: uniforme_0,30 +2.2%, uniforme_0,50 +2.2%, uniforme_0,70 +2.2%, uniforme_0,90 +2.2%, espacial_0,30-0,50 +3.0%, espacial_0,50-0,70 +2.9%, espacial_0,70-0,95 +2.8%, espacial_0,30-0,95 +5.7%. D2 sobre a regressão logística só com os componentes: uniforme_0,30 +1.1%, uniforme_0,50 +1.1%, uniforme_0,70 +1.1%, uniforme_0,90 +1.1%, espacial_0,30-0,50 -0.1%, espacial_0,50-0,70 +0.2%, espacial_0,70-0,95 +0.3%, espacial_0,30-0,95 -1.2%.

## Limitações obrigatórias

- Os 124 registros são de 2013-2014 e não têm horário nem precipitação associada: o experimento não valida previsão condicionada à chuva.
- A chuva é uniforme e hipotética (10, 30 e 60 mm): ela escala o volume, mas não diferencia ruas.
- O Copernicus GLO-30 é um DSM de 30 m, com viés de altitude (+2,1 m contra marcos da Prefeitura) e sem microrrelevo urbano (meio-fio, sarjeta).
- Não há dados suficientes de capacidade da drenagem (bueiros, galerias): o volume afluente potencial não é volume retido nem profundidade.
- Os coeficientes de escoamento são hipóteses de cenário; o proxy espacial (densidade viária) não mede impermeabilização.
- O fluxo acumulado e a declividade já são componentes do índice atual: a formulação física reaproveita parte da mesma informação.
- Os escores do D2 vêm de modelos diferentes em cada dobra e são agrupados para calcular AP e AUC; calibrações distintas entre dobras podem afetar a AP.
- O bootstrap de percentis da AP é assimétrico (poucos positivos muito bem posicionados dominam a métrica); os intervalos descrevem a fragilidade, não um erro padrão.
- Resultado exploratório com ~124 trechos positivos e rótulos enviesados para onde a Prefeitura registrou; não escolhe modelo de produção.

## Como ler

A regra atual só seria substituída com ganho de 10% e limite inferior do intervalo acima de zero, por trecho, por blocos de positivos e por blocos completos (com seus negativos), em todos os cenários de C. Intervalos que se sobrepõem não são evidência de superioridade. Os 124 positivos estão em 53 blocos de 1,5 km e um só bloco concentra 18 deles, por isso o bootstrap por blocos é o mais conservador. A amplitude do intervalo do D1 (−12% a +81%) é real e estável (não muda com a semente nem com 20.000 réplicas): a precisão média depende de poucos positivos muito bem posicionados (os 5 melhores respondem por 16% da AP do D1 e 8% da AP da regra), então um único trecho entrar ou sair da amostra muda o resultado. É uma hipótese, não uma evidência. 
## Correções da auditoria

- O ganho relativo passou a usar a precisão média sem arredondamento (antes, 5 casas: erro de até ~0,25%).
- O bootstrap por blocos, que só reamostrava blocos com positivos e mantinha os negativos fixos, ganhou a versão completa (blocos inteiros com seus negativos, conglomerados). A anterior continua nas tabelas como sensibilidade; o critério exige as três formas. A versão anterior do relatório está em `reports/qa/sensibilidade_hidrologica_v1_antes_da_auditoria.json`.
- Robustez da divisão espacial (tamanho do bloco, origem da grade, leave-one-block-out): [robustez_espacial.md](robustez_espacial.md).
- Empates de escore passaram a ser tratados como no scikit-learn (descoberto na Fase 3, quando 78% dos trechos tinham o mesmo escore e o bootstrap antigo inflava a precisão média). Aqui os escores são contínuos: os limites dos intervalos mudaram na terceira ou quarta casa decimal e nenhuma conclusão mudou.

Reprodução: `PYTHONPATH=src python tools/experimento_sensibilidade_hidrologica.py`.
