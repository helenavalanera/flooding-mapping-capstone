# Fase 3: o motor de contribuição potencial e o indicador topográfico

Estado: **implementado e testado** em 25/11/2026. Código: `src/flooding_mapping/fluxo.py`, `motor_acumulo.py` e `escoamento.py`; execução: `tools/executar_fase3.py`; parâmetros: `config/fase3_motor.yaml`; testes: `tests/test_fase3_motor.py`. Resultados da execução em [fase3_resultados.md](fase3_resultados.md).

## A pergunta e o que o motor responde

> Dada uma chuva, onde a água tende a se acumular?

O motor responde **uma parte**, com os dados que existem:

1. **Quanta água a superfície pode gerar** em cada ponto, segundo o uso do solo (Método 1 e cenários).
2. **Quanta pode chegar a cada trecho viário**, por onde o relevo a conduz.
3. **Onde o relevo favorece retê-la** (indicador topográfico, sem unidade física).

Ele **não** calcula volume retido, volume efetivamente transportado, profundidade, duração, capacidade de drenagem nem conectividade hidráulica. Não há chuva no tempo, infiltração, perdas, vazão de saída nem registros com início e fim. Isso aparece em `relatorio["nao_calculado"]` de cada execução.

## Decisões que o motor implementa

1. **Unidade computacional: a célula de 30 m** (a mesma grade do DEM do projeto). **Unidade de apresentação: o trecho viário**, associado por uma regra espacial determinística (abaixo).
2. **Jardins e passeios: sempre o envelope.** A classe recebe o intervalo que cobre os três cenários de fração de piso (25%, 50% e 75%): `[0,225; 0,800]`. Nenhum valor central é usado, nem o cenário do meio.
3. **Depressões: só indicador topográfico.** A altura que o preenchimento soma à célula (`preenchido - dem`) mede a propensão do relevo à retenção. **Não** é volume armazenável nem profundidade de alagamento.

## Três grandezas distintas

| Grandeza | Definição | Calculada? |
|---|---|---|
| **Volume potencial gerado** (local) | `V = P x A x C / 1000` somado nas células da pegada do trecho, cada célula uma vez | Sim, em intervalo |
| **Contribuição potencial associada ao trecho** | Volume potencial gerado sobre a **união das bacias a montante** das células da pegada | Sim, em intervalo |
| **Volume efetivamente transportado** | O que de fato chega, descontados infiltração, perdas e drenagem | **Não** (faltam dados) |

`P` em mm, `A` em m², `C` adimensional, `V` em m³. É **água potencialmente escoada**: um limite superior do que pode escoar, sem infiltração nem perdas.

## Como se calcula

**Geração por célula.** Para cada classe de uso do solo, a área na célula vezes o coeficiente. Como o resultado é linear em `P`, o motor calcula uma só vez a **área equivalente** `aeq = soma(A x C)` em m², e o volume de qualquer chuva é `P x aeq / 1000`. Os coeficientes têm três pacotes que **nunca se somam entre si**:

| Pacote | Classes | Coeficiente | Natureza |
|---|---|---|---|
| `metodo1` | Edificação, Vias Pavimentadas | Intervalo `[C_min, C_max]` da tabela de referência (TxDOT) | Parâmetro fundamentado |
| `limites_fisicos` | As 11 classes que o Método 1 não cobre | `C = 0` (inferior) e `C = 1` (superior) | Limite físico, não é estimativa |
| `referencia_analoga` | Campo, Pastagem (faixa da TxDOT por analogia) e Jardins (envelope) | Intervalos declarados | Hipótese declarada |

Área Úmida e Corpo Hídrico ficam fora do cálculo de escoamento. Classes sem valor em um pacote ficam como **sem valor** (nunca preenchidas) e entram na cobertura.

**Roteamento.** Fluxo D8 sobre o relevo com as depressões preenchidas (a mesma `susceptibility.fill_depressions`). O fluxo forma uma **floresta**: cada célula tem um único receptor, as raízes são os exutórios. O acúmulo de qualquer grandeza é a soma da sub-árvore de cada célula, calculada por soma de prefixos sobre a ordem de uma busca em profundidade. Isso conserva a massa (o que sai pelos exutórios é igual ao gerado) e **reproduz exatamente** `susceptibility.flow_accumulation` com peso 1 (verificado a cada execução, no DEM real). As células de corpo d'água grande (sem classe de uso e dentro de polígono de água do OpenStreetMap) viram **exutório**: a água sai ali, em vez de o preenchimento transformar o Guaíba numa bacia alagada.

**Associação célula a trecho, sem dupla contagem.** A pegada do trecho é o conjunto de células que a reta do trecho atravessa (amostrada a cada 6 m). O acumulado de uma célula já inclui todo o fluxo a montante; somar células de uma pegada que estão no mesmo caminho contaria a mesma água várias vezes. Por isso entram na contribuição só as **células de chegada**: as da pegada que **não têm outra célula da pegada a jusante**. Como cada célula tem um único receptor, as bacias de duas células de chegada são **disjuntas**, e a soma de seus acumulados é exatamente o volume gerado sobre a união das bacias. Dois caminhos independentes que o trecho cruza somam-se; dois pontos do mesmo caminho contam uma vez. Um teste de força bruta confere isso contra uma busca explícita.

**Indicador topográfico (Nível 1).** `altura_de_preenchimento_max_m` e `_media_m` sobre a pegada, e `propensao_topografica_percentil` (posto entre os trechos, 0 a 100). Com o Copernicus (DSM de 30 m, erro médio de 2,18 m contra marcos), a altura **não é interpretável em metros**; só o posto é útil, como índice relativo.

## Saídas (`data/processed/fase3/`, fora do Git)

| Arquivo | Conteúdo |
|---|---|
| `celulas_30m.parquet` | Por célula: altura de preenchimento, `aeq_*` (m²) e o acumulado a montante `acum_aeq_*` (m²), por pacote e limite |
| `trechos_nivel1_propensao_topografica.parquet` | Indicador topográfico por trecho (Nível 1) |
| `trechos_contribuicao_base.parquet` | Por trecho, independente da chuva: `local_aeq_*` e `contrib_aeq_*` (m²), `area_montante_m2`, `fracao_montante_*` (**o grau de confiança**), contagens da pegada |
| `trechos_nivel2_cenarios.parquet` | Por trecho, chuva (10, 20 e 30 mm) e pacote: `v_gerado_local_*` e `contrib_potencial_*`, mínimo e máximo, em m³ |
| `relatorio_execucao.json` | Parâmetros, hashes das entradas, verificações, totais, comparações exploratórias, limitações |

**Cobertura como grau de confiança.** Cada trecho traz a parte da área a montante coberta pelo Método 1 (`fracao_montante_coberta_m1`), a que tem valor por analogia, a **sem valor**, a fora do cálculo e a sem classe; somam 1. Um resultado cuja área a montante é quase toda "sem valor" não deve ser lido como estimativa.

## Hipóteses e o que é real

| Elemento | Natureza |
|---|---|
| Uso e ocupação do solo (Profill 2022) | Observado (mapeamento municipal, 2018 a 2021) |
| Coeficientes do Método 1 | Parâmetro fundamentado (TxDOT, tabela 4-10) |
| Pacotes `limites_fisicos` e `referencia_analoga` | Hipótese declarada (cenários) |
| Chuva de 10, 20 e 30 mm, uniforme | Hipótese (não é previsão, nem categoria de chuva) |
| Relevo (Copernicus GLO-30) | Observado, com limites (DSM de 30 m) |
| Exutório por corpo d'água | Escolha de método declarada (`config/fase3_motor.yaml`) |

## O que a Fase 3 não faz, e por quê

- **Volume efetivamente transportado e retido:** exigem infiltração, perdas, capacidade de drenagem, rugosidade e condições de contorno.
- **Profundidade e duração:** exigem chuva no tempo, vazão de saída e registros com início e fim.
- **Inventário de drenagem no cálculo:** as bocas de lobo, a rede e as bombas não têm capacidade nem conexões confirmadas; ficam como contexto.
- **Chuva espacialmente distribuída:** não há dado. A função aceita `P` como parâmetro; um campo espacial exigiria acumular `P_i x aeq_i` em vez de escalar.

## Limitações conhecidas

- A chuva uniforme só escala o volume; não diferencia ruas.
- 75,1% da área classificada fica sem coeficiente fundamentado: o resultado da cidade depende de cenários, e a cobertura por trecho mostra quanto.
- O DSM do Copernicus inclui edificações e copa de árvores, o que distorce o caminho da água em áreas densas.
- Valores por trecho **não são somáveis** entre trechos; só a soma das células dá o total da cidade.
- A pegada pode perder células cortadas por cordas menores que o passo de 6 m.
- A célula de 30 m mistura classes; a água gerada é correta em soma, mas o caminho dentro da célula não é representado.

## Reproduzir

```
PYTHONPATH=src python tools/baixar_drenagem_poa.py uso_do_solo_profill_2022   # se os brutos não estiverem em data/raw
PYTHONPATH=src python tools/processar_uso_solo_poa.py                        # Fase 2
PYTHONPATH=src python tools/executar_fase3.py                                # esta fase
PYTHONPATH=src python tools/gerar_relatorio_fase3.py                         # docs/fase3_resultados.md
```

Os hashes das entradas e dos arquivos gerados ficam no manifesto (`data/raw/manifest.json`) e no relatório de execução; reexecutar com as mesmas entradas dá os mesmos arquivos.
