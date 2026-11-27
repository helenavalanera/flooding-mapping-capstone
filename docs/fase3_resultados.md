# Fase 3: resultados da execução

Relatório **gerado** por `tools/gerar_relatorio_fase3.py` a partir de `reports/qa/fase3_execucao.json`. Método, equações, hipóteses e limites em [fase3_motor.md](fase3_motor.md). Chuva uniforme e **hipotética** (10, 20 e 30 mm): são cenários, não previsões.

**Leia assim.** Os volumes são **água potencialmente escoada** (limite superior, sem infiltração nem perdas), em intervalos. **Não** são volume retido, profundidade, duração nem volume efetivamente transportado, que o motor não calcula. Os três pacotes de coeficientes **não se somam**.

## 1. Verificações do núcleo

| Verificação | Resultado |
|---|---|
| Acúmulo com peso 1 idêntico a `susceptibility.flow_accumulation` do projeto, no DEM real | sim (1.290.058 células) |
| Conservação de massa (gerado = saída pelos exutórios), erro relativo máximo em 13 colunas | 1.4e-14 |
| Células com dados na grade de 30 m | 1.290.058 |
| Exutórios (células sem receptor) | 3.873 |
| Células de corpo d'água grande tratadas como exutório | 25.225 (22,7 km²) |

## 2. Trechos viários

- 176.836 trechos; **173.917** com ao menos uma célula com dados na pegada.
- 2.728 ficam fora da grade (sem nenhuma célula) e 191 só em células sem dado ou de água mascarada: recebem valor **ausente**, nunca zero.
- Mediana de 2 células por pegada.

## 3. Total da cidade (soma das células, cada célula uma vez)

Em m³, mínimo a máximo. O total existe só como soma das células: **valores por trecho não são somáveis**, porque as bacias de trechos vizinhos se sobrepõem.

| Chuva (hipotética) | Pacote | Água potencialmente escoada (m³) |
|---|---|---|
| 10 mm | Método 1 (fundamentado) | 600.497 a 775.382 |
| 10 mm | Limites físicos (C = 0 a 1) | 0 a 3.539.172 |
| 10 mm | Referência por analogia (hipótese) | 225.392 a 1.151.569 |
| 20 mm | Método 1 (fundamentado) | 1.200.995 a 1.550.765 |
| 20 mm | Limites físicos (C = 0 a 1) | 0 a 7.078.343 |
| 20 mm | Referência por analogia (hipótese) | 450.785 a 2.303.138 |
| 30 mm | Método 1 (fundamentado) | 1.801.492 a 2.326.147 |
| 30 mm | Limites físicos (C = 0 a 1) | 0 a 10.617.515 |
| 30 mm | Referência por analogia (hipótese) | 676.177 a 3.454.707 |

O Método 1 cobre só edificação e via pavimentada (17,3% da área classificada). Os limites físicos (C = 0 a 1) são o envelope trivial que vale por definição; a referência por analogia é hipótese declarada, com Jardins sempre como envelope dos cenários de fração.

## 4. Valores por trecho com chuva de 30 mm (quantis entre os trechos, em m³, limite superior de cada pacote)

| Pacote | Grandeza | Mediana | Percentil 90 | Percentil 99 |
|---|---|---|---|---|
| Limites físicos (C = 0 a 1) | Volume potencial gerado (local) | 24,6 | 69,7 | 154 |
| Limites físicos (C = 0 a 1) | Contribuição potencial associada ao trecho | 66,4 | 1.957,4 | 132.055 |
| Método 1 (fundamentado) | Volume potencial gerado (local) | 12,6 | 48,5 | 109 |
| Método 1 (fundamentado) | Contribuição potencial associada ao trecho | 32,1 | 942,4 | 42.420 |
| Referência por analogia (hipótese) | Volume potencial gerado (local) | 13,6 | 41,3 | 87 |
| Referência por analogia (hipótese) | Contribuição potencial associada ao trecho | 35,0 | 963,4 | 53.381 |

### Cobertura a montante (o grau de confiança), mediana entre os trechos

Da área a montante de um trecho típico: **30,2%** tem coeficiente fundamentado (Método 1), 36,0% tem valor por analogia e **7,2%** fica sem valor nesse pacote; 0,0% é fora do cálculo e 0,0% é sem classe. Cada trecho traz as suas frações em `trechos_contribuicao_base.parquet`; um trecho cuja área a montante é quase toda sem valor não deve ser lido como estimativa.

## 5. Indicador topográfico (Nível 1)

Altura de preenchimento de depressões na pegada: **134.941** dos 173.917 trechos com dados (77,6%) têm preenchimento zero; entre os trechos, mediana 0,00 m, percentil 90 0,68 m e percentil 99 2,69 m. Com o Copernicus (DSM de 30 m, erro médio de 2,18 m) a altura **não é interpretável em metros**, nem como volume ou profundidade: só o posto (`propensao_topografica_percentil`) serve, como índice relativo. Como a maioria dos trechos tem preenchimento zero, o posto só discrimina entre os que têm algum preenchimento.

## 6. Comparação exploratória com os registros de alagamento de 2013 a 2014

Mesma amostra do experimento de sensibilidade: 107.869 trechos, **124 positivos** (107.827 com valor no motor, 124 positivos); taxa base 0,115%. Critério: ganho de precisão média >= 10% e limite inferior do IC95% do ganho > 0, por trecho, por blocos de positivos e por blocos completos.

| Candidato | AUC | Precisão média | Ganho vs. regra | IC95 (trechos) | IC95 (blocos completos) | Atende o critério |
|---|---|---|---|---|---|---|
| `regra_atual_percentil` | 0,666 | 0,00205 | referência |  |  |  |
| `nivel1_altura_de_preenchimento_max` | 0,639 | 0,00231 | +12,6% | -21% a +63% | -23% a +68% | não |
| `nivel2_contribuicao_m1_max` | 0,636 | 0,00228 | +11,0% | -14% a +42% | -17% a +38% | não |
| `nivel2_contribuicao_analoga_max` | 0,592 | 0,00200 | -2,6% | -24% a +23% | -25% a +19% | não |
| `nivel2_contribuicao_limites_max` | 0,567 | 0,00184 | -10,3% | -29% a +12% | -30% a +9% | não |

Comparação exploratória: os registros são de 2013-2014, sem horário e sem chuva, e o motor é condicionado à chuva; serve para discutir plausibilidade, não valida o motor. Diferença pequena ou intervalo que inclui zero não é evidência de superioridade, e a regra atual não é substituída.

**Sobreposição qualitativa com o risco CPRM** (contexto, nunca rótulo). Percentil mediano da contribuição do Método 1 entre os trechos de cada classe de risco mapeado:

| Classe do CPRM | Trechos | Percentil mediano da contribuição (Método 1, máximo) |
|---|---|---|
| Alto | 47.009 | 62,9 |
| Médio | 2.991 | 58,0 |
| Baixa | 559 | 45,2 |
| fora de risco mapeado | 126.277 | 44,2 |

Risco mapeado (modelagem validada em campo, 2012-2014) é contexto: não é rótulo, ocorrência histórica nem simulação. A classe Alto cobre cerca da metade da cidade, então discrimina pouco.

## 7. Arquivos gerados (`data/processed/fase3/`, fora do Git)

| Arquivo | Linhas | MB | SHA-256 (início) |
|---|---|---|---|
| `data/processed/fase3/celulas_30m.parquet` | 1.290.058 | 7,0 | dbf48219391c |
| `data/processed/fase3/trechos_nivel1_propensao_topografica.parquet` | 176.836 | 2,2 | e08eb285bb65 |
| `data/processed/fase3/trechos_contribuicao_base.parquet` | 176.836 | 6,7 | 62f32109dfb9 |
| `data/processed/fase3/trechos_nivel2_cenarios.parquet` | 1.591.524 | 22,5 | 893269184be7 |

Todos registrados em `data/raw/manifest.json`, com os hashes das entradas.

## 8. Não calculado

- **volume efetivamente transportado:** não calculado: exigiria infiltração, perdas, capacidade de drenagem, rugosidade e condições de contorno, que não existem nos dados
- **volume retido ou armazenado:** não calculado: a altura de preenchimento é indicador topográfico, não volume armazenável
- **profundidade e duracao:** não calculadas: não há chuva no tempo, vazão de saída nem registros com início e fim
- **conectividade hidraulica:** não usada: o inventário de drenagem entra só como contexto, sem conexões confirmadas

## 9. Limitações

- Chuva uniforme e hipotética: ela escala o volume, mas não diferencia ruas. O resultado é condicionado ao cenário, não é previsão.
- Só 17,3% da área classificada tem coeficiente fundamentado (Método 1); o resto depende de cenários, e a fração a montante coberta por cada pacote vai em cada trecho.
- O volume efetivamente transportado, o retido, a profundidade e a duração NÃO são calculados.
- A altura de preenchimento é indicador topográfico: o Copernicus (DSM de 30 m, erro médio de 2,18 m contra marcos) não permite lê-la em metros nem como volume.
- Valores por trecho não são somáveis entre trechos (bacias vizinhas se sobrepõem); o total da cidade existe só como soma das células.
- A pegada do trecho (células atravessadas) pode perder células cortadas por cordas menores que o passo de amostragem.
- O inventário de drenagem não entra no cálculo: sem capacidade, sem conexões confirmadas.
