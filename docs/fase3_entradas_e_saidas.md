# Fase 3: entradas e saídas (proposta original e o que foi implementado)

Estado: **implementada em 25/11/2026.** O método, as equações, as hipóteses e os limites estão em [fase3_motor.md](fase3_motor.md); os resultados da execução, em [fase3_resultados.md](fase3_resultados.md). Este documento guarda a proposta que precedeu a implementação, com as três decisões que a destravaram e as diferenças que ficaram.

**Decisões aprovadas (25/11/2026):**
1. **Unidade de agregação:** o trecho viário como unidade de apresentação e a célula de 30 m como unidade computacional; contribuição potencial acumulada a montante associada ao trecho por regra espacial determinística, sem somar células acumuladas indiscriminadamente nem duplicar volumes; três grandezas separadas (volume potencial gerado, contribuição potencial associada ao trecho, volume efetivamente transportado).
2. **Jardins e passeios:** sempre o envelope dos cenários, com limites e hipóteses explícitos; nenhum coeficiente central.
3. **Depressões:** o preenchimento só como indicador topográfico de propensão à retenção, nunca como volume armazenável nem profundidade.

**O que mudou em relação à proposta abaixo:**
- A regra de associação ao trecho ficou definida: só as **células de chegada** da pegada do trecho (as que não têm outra célula da pegada a jusante) entram na contribuição; as bacias delas são disjuntas por construção.
- Os arquivos de saída são `celulas_30m`, `trechos_nivel1_propensao_topografica`, `trechos_contribuicao_base` (independente da chuva, em m² equivalentes) e `trechos_nivel2_cenarios` (volumes em m³ para 10, 20 e 30 mm), e não `agua_gerada_celula` e `agua_que_chega_trecho`, porque o resultado é linear em P.
- Os pacotes de coeficientes são três (`metodo1`, `limites_fisicos`, `referencia_analoga`) e **nunca se somam**.
- O volume efetivamente transportado **não é calculado** e não vira coluna.

---

# Proposta original

## 1. Entradas (todas já existem)

| Entrada | Arquivo | Conteúdo usado | Natureza |
|---|---|---|---|
| Áreas por classe em cada célula de 30 m | `data/processed/uso_solo/uso_solo_grade30m.parquet` (554.807 células, EPSG:31982) | `linha`, `coluna`, `x_centro`, `y_centro`, `area_m2__01` a `area_m2__15` (por classe, código em `classes_e_codigos.json`), `area_classificada_m2`, `area_lacuna_m2`, `area_dentro_do_municipio_m2` | Observado (mapeamento municipal) |
| Coeficientes fundamentados | `config/uso_solo_coeficientes_metodo1_fundamentados.csv` | Intervalo de C para edificação e via pavimentada | Parâmetro fundamentado |
| Cenários | `config/uso_solo_cenarios_metodo2_hipoteticos.csv` | C por cenário para as classes que o Método 1 não cobre | **Hipótese declarada** |
| Fórmula e validação de unidades | `flooding_mapping.escoamento` (`volume_gerado_m3`, `geracao_metodo1`, `geracao_cenario`) | `V = P x A x C / 1000` | Já implementado e testado |
| Chuva | Parâmetro `P` em mm | Cenários 10, 20 e 30 mm, **uniformes e hipotéticos** | Hipótese (não é previsão) |
| Relevo | Copernicus GLO-30 pela `susceptibility.build_dem` (a mesma grade da entrada acima) | Altitude, direção D8, depressões preenchidas | Observado, com limites (DSM de ~30 m, erro médio de 2,18 m contra marcos) |
| Unidade espacial | `data/processed/rede_poa.parquet` (176.836 trechos) | Geometria e identificador do trecho | Observado (OpenStreetMap) |
| Contexto, **sem entrar no cálculo** | `data/processed/drenagem/*.parquet` e a camada de risco CPRM | Inventário de rede, poços, bocas, bombas; risco mapeado | Observado, só para contexto e comparação qualitativa |
| Referência de validação | 124 trechos alagados de 2013 a 2014 | Posição, sem horário e sem chuva | Referência inicial, **não** valida previsão |

## 2. Saídas propostas

Cada saída traz o **nível** (1, 2 ou 3), o **cenário de chuva**, o **método** e a **cobertura de dados**. Nenhuma mistura fundamentado e hipótese em um número só.

**A. Água gerada por célula** (`agua_gerada_celula.parquet`, Nível 2)

| Coluna | Unidade | Significado |
|---|---|---|
| `linha`, `coluna` | - | Célula da grade de 30 m |
| `p_mm` | mm | Chuva do cenário (hipotética) |
| `v_ger_m1_min_m3`, `v_ger_m1_max_m3` | m³ | Intervalo do Método 1 (edificação e via pavimentada) |
| `v_ger_<cenario>_min_m3`, `_max_m3` | m³ | Intervalo do cenário, **só** para as classes do cenário |
| `area_m1_m2`, `area_sem_valor_m2`, `area_fora_do_calculo_m2`, `area_sem_classe_m2` | m² | Quanto da célula cada tratamento cobre (a água do Guaíba e outras lacunas ficam em `area_sem_classe_m2`) |

**B. Água que chega a cada trecho viário** (`agua_que_chega_trecho.parquet`, Nível 2)

| Coluna | Unidade | Significado |
|---|---|---|
| `segmento_id` | - | Identificador do trecho |
| `v_chega_m1_min_m3`, `v_chega_m1_max_m3` | m³ | Soma de `v_ger_m1` das células a montante (fluxo D8 ponderado por volume, cada célula contada uma vez) |
| `v_chega_<cenario>_min_m3`, `_max_m3` | m³ | Idem por cenário |
| `fracao_a_montante_m1`, `fracao_a_montante_sem_valor` | - | Parte da área a montante coberta pelo Método 1 e parte em classes sem valor: **o grau de confiança** do resultado |

`v_chega` é **água potencialmente escoada que chega**: não desconta infiltração, perdas nem drenagem, e **não é volume retido**.

**C. Indicador topográfico de depressões** (Nível 1)

`preenchimento_m` (altura que o preenchimento de depressões soma à célula), por célula e por trecho. É um **índice relativo de relevo, não volume**: com o Copernicus (erro médio de 2,18 m, DSM, 30 m), depressões de rua não são interpretáveis em metros nem em m³. **Não se produz `S_pot` em m³ como resultado físico** nesta fase; isso só voltaria com um modelo de terreno de melhor qualidade vertical (decisão de adiar o MDT em vigor).

**D. Relatório de cada execução** (`relatorio_execucao.json`): cenário, método, `P`, versão dos dados (hashes do manifesto), cobertura, conferências de conservação e as limitações.

## 3. Invariantes que os testes devem garantir

1. **Dimensões:** `V = P x A x C / 1000` em m³ com P em mm e A em m² (já testado), e o resultado linear em P, em A e em C.
2. **Conservação:** a soma de `v_ger` das células é igual ao volume que sai pelos exutórios do relevo mais o que fica em depressões preenchidas, com tolerância numérica declarada. Nenhuma água criada nem perdida.
3. **Sem dupla contagem:** cada célula contribui uma única vez a cada trecho a jusante.
4. **Monotonicidade:** `v_chega` cresce com `P` e com `C`.
5. **Independência dos métodos:** o Método 1 não muda quando o cenário muda; um cenário não redefine classe do Método 1.
6. **Cobertura declarada:** toda saída carrega a fração em classes sem valor; sem isso, falha.
7. **Reprodutibilidade:** mesma entrada, mesmos hashes, mesmo arquivo.
8. **Sinal de não promessa:** nenhuma coluna chamada profundidade, duração, volume retido, capacidade ou probabilidade.

Validação compatível com o nível: consistência física, **cenários sintéticos controlados** (rotulados como sintéticos, não como validação empírica), sensibilidade a `P`, ao cenário de C e à agregação, e comparação **qualitativa** com os 124 trechos e com a camada CPRM (nunca como rótulo).

## 4. O que a Fase 3 não fará

Profundidade, duração, volume retido, capacidade de drenagem, conectividade hidráulica, funcionamento de bocas de lobo, vazão de bombas, previsão de alagamento, chuva espacialmente distribuída (não há dado), uso do MDT 2010 (adiado).

## 5. Decisões e pendências

**Bloqueiam o início da Fase 3**

1. **Unidade de agregação da água que chega ao trecho.** Proposta: a área contribuinte pelo fluxo D8 nas células do trecho, coerente com as variáveis de terreno já existentes. Alternativa: zona fixa ao redor do trecho. Precisa de aprovação.
2. **Apresentação do Método 2 na classe "Jardins, Passeios ou Áreas semi urbanizadas"** (18,6% da área classificada, a maior incerteza): mostrar o envelope dos três cenários de fração (25%, 50%, 75%, que são hipóteses) ou um deles? Proposta: sempre o envelope, nunca um valor único.
3. **Conservação com preenchimento total de depressões.** O fluxo atual usa o preenchimento completo (nenhuma depressão retém). Confirmar que a Fase 3 mantém isso e trata o preenchimento só como indicador (item C), e não como armazenamento.

**Não bloqueiam**

4. MDT municipal (decisão: adiar; Copernicus segue como referência).
5. Capacidade de drenagem e bombas (a drenagem fica como inventário e contexto).
6. Chuva espacial e eventos datados (necessários para validar, não para construir o motor).
7. Onde guardar a grade de uso do solo no deploy: o arquivo tem 1,7 MB, cabe na imagem; os polígonos (279 MB) não são necessários na aplicação.

## 6. Riscos conhecidos

- A cobertura é desigual: 75,1% da área classificada fica sem coeficiente fundamentado, então boa parte do resultado da cidade dependerá de cenários. O relatório de cada execução precisa tornar isso visível.
- O DSM do Copernicus inclui edificações e copa de árvores, e isso distorce o escoamento por célula em áreas densas.
- A grade de 30 m mistura classes dentro da célula; a água gerada é correta em soma, mas o caminho dentro da célula não é representado.
