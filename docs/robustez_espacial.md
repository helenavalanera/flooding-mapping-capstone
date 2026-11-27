# Robustez da validação espacial

Teste de estabilidade metodológica do experimento de sensibilidade hidrológica ([relatório principal](sensibilidade_hidrologica.md)). Não escolhe a melhor configuração: mede se a conclusão depende de como o espaço foi dividido. Exploratório; não valida previsão condicionada à chuva.

## Conclusão

**Nenhuma configuração de blocos atende o critério de adoção (ganho de 10% com intervalo acima de zero) e nenhuma retirada de bloco atinge sequer a margem de 10% (maior ganho observado: +9,96%, sem intervalo de confiança nesta etapa). A decisão de não adotar não depende da divisão espacial testada. Mas há sensibilidade que impede ler qualquer ganho como evidência: o ganho do D1 troca de sinal ao retirar até 2 blocos, a ordem de precisão média entre os modelos assume 6 formas distintas, e o D2 varia de -18,6% a +0,8% conforme a grade.**

Amostra: 107.869 trechos, 124 positivos, semente 7, 1000 réplicas (bootstrap por conglomerados: blocos inteiros com seus negativos).

Modelos: B = fluxo ajustado pela declividade; D1 = média de postos regra + física; D2 = regressão logística (componentes + física). Sufixo `u` = C uniforme 0,50; `e` = C espacial 0,30–0,95 (os mesmos cenários do relatório principal, fixados antes). A = regra atual (referência).

## 1 e 2. Tamanho do bloco e origem da grade

16 configurações; 12 cumprem os pontos de estabilidade fixados de antemão (≥ 20 blocos com positivos, maior bloco ≤ 25% dos positivos, número efetivo ≥ 15). As demais ficam registradas, com a limitação.

| Bloco | Origem | Blocos c/ positivo | Maior bloco | N efetivo | Adequada | B | D1u | D1e | D2u | D2e |
|---|---|---|---|---|---|---|---|---|---|---|
| 1000 m | (0;0) | 62 | 14 (11%) | 30,5 | sim | -9,9% | +2,2% | +5,7% | -5,8% | -9,0% |
| 1000 m | (½;0) | 62 | 14 (11%) | 31,3 | sim | -9,9% | +2,2% | +5,7% | -5,7% | -10,6% |
| 1000 m | (0;½) | 64 | 11 (9%) | 31,8 | sim | -9,9% | +2,2% | +5,7% | +0,8% | -4,3% |
| 1000 m | (½;½) | 63 | 11 (9%) | 33,0 | sim | -9,9% | +2,2% | +5,7% | -2,4% | -7,3% |
| 1500 m (original) | (0;0) | 53 | 18 (14%) | 21,0 | sim | -9,9% | +2,2% | +5,7% | -6,5% | -8,5% |
| 1500 m | (½;0) | 50 | 19 (15%) | 19,2 | sim | -9,9% | +2,2% | +5,7% | -15,1% | -18,6% |
| 1500 m | (0;½) | 53 | 13 (10%) | 26,6 | sim | -9,9% | +2,2% | +5,7% | -8,4% | -11,7% |
| 1500 m | (½;½) | 53 | 12 (10%) | 25,0 | sim | -9,9% | +2,2% | +5,7% | -2,6% | -6,9% |
| 2000 m | (0;0) | 46 | 22 (18%) | 17,4 | sim | -9,9% | +2,2% | +5,7% | -9,5% | -15,7% |
| 2000 m | (½;0) | 45 | 19 (15%) | 19,3 | sim | -9,9% | +2,2% | +5,7% | -3,8% | -7,1% |
| 2000 m | (0;½) | 45 | 14 (11%) | 22,3 | sim | -9,9% | +2,2% | +5,7% | -4,0% | -6,0% |
| 2000 m | (½;½) | 41 | 15 (12%) | 20,4 | sim | -9,9% | +2,2% | +5,7% | -3,3% | -10,1% |
| 3000 m | (0;0) | 31 | 21 (17%) | 14,2 | não | -9,9% | +2,2% | +5,7% | -1,6% | -5,7% |
| 3000 m | (½;0) | 29 | 26 (21%) | 12,5 | não | -9,9% | +2,2% | +5,7% | -5,8% | -11,6% |
| 3000 m | (0;½) | 30 | 20 (16%) | 14,6 | não | -9,9% | +2,2% | +5,7% | -10,2% | -13,3% |
| 3000 m | (½;½) | 30 | 20 (16%) | 12,7 | não | -9,9% | +2,2% | +5,7% | -3,3% | -8,2% |

Células de modelos: ganho relativo de precisão média sobre a regra atual.

| Modelo | Ganho mínimo | Ganho máximo | Configurações que atendem o critério | Com ganho positivo |
|---|---|---|---|---|
| B | -9,9% | -9,9% | 0 de 16 | 0 de 16 |
| D1u | +2,2% | +2,2% | 0 de 16 | 16 de 16 |
| D1e | +5,7% | +5,7% | 0 de 16 | 16 de 16 |
| D2u | -15,1% | +0,8% | 0 de 16 | 1 de 16 |
| D2e | -18,6% | -4,3% | 0 de 16 | 0 de 16 |

Configurações com limitação:

- 3000 m, origem (0;0): número efetivo de blocos 14,2 (mínimo 15)
- 3000 m, origem (½;0): número efetivo de blocos 12,5 (mínimo 15)
- 3000 m, origem (0;½): número efetivo de blocos 14,6 (mínimo 15)
- 3000 m, origem (½;½): número efetivo de blocos 12,7 (mínimo 15)

## 3. Leave-one-block-out (grade original, 1,5 km)

Retira-se da avaliação um bloco com positivos por vez (53 blocos). Os escores do D2 são fixos (gerados com a grade original): a retirada afeta a avaliação, não o treino.

| Modelo | Ganho com todos os blocos | Mínimo | Mediano | Máximo | Blocos que invertem o sinal | Blocos com ganho ≥ 10% |
|---|---|---|---|---|---|---|
| B | -9,9% | -18,7% | -9,8% | -5,2% | 0 | 0 |
| D1u | +2,2% | -4,5% | +2,3% | +5,9% | 2 | 0 |
| D2u | -6,5% | -12,3% | -6,7% | +3,0% | 1 | 0 |
| D1e | +5,7% | -3,2% | +5,8% | +10,0% | 1 | 0 |
| D2e | -8,5% | -13,2% | -8,8% | +0,7% | 1 | 0 |

Bloco que concentra 18 positivos (id -329112089): ganho sem ele B -18,7%, D1u -0,0%, D1e +4,2%, D2u -4,9%, D2e -8,3%.

Retirada dos k maiores blocos:

| k | Positivos restantes | B | D1u | D1e | D2u | D2e |
|---|---|---|---|---|---|---|
| 1 | 106 | -18,7% | -0,0% | +4,2% | -4,9% | -8,3% |
| 2 | 94 | -20,8% | +0,9% | +5,2% | -12,7% | -14,5% |
| 3 | 86 | -21,0% | +2,6% | +7,5% | -16,5% | -18,2% |

Ordens distintas de precisão média entre modelos ao retirar um bloco: 6.

- A > D2u > D1e > D1u > D2e > B
- D1e > A > D1u > D2u > D2e > B
- D1e > D1u > A > B > D2u > D2e
- D1e > D1u > A > D2u > B > D2e
- D1e > D1u > A > D2u > D2e > B
- D1e > D1u > D2u > D2e > A > B

## Como ler

Estabilidade não é superioridade. Um resultado que muda de sinal com a retirada de um bloco não é interpretável; um que não muda continua exploratório (rótulos de 2013–2014, sem chuva associada, ~124 positivos). Reprodução: `PYTHONPATH=src python tools/robustez_espacial_validacao.py`.
