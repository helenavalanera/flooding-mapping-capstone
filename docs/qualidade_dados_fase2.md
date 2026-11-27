# Fase 2: qualidade dos dados integrados e cobertura territorial

Relatório **gerado** por `tools/gerar_relatorio_fase2.py` a partir de `reports/qa/qualidade_drenagem_fase2.json` e `reports/qa/qualidade_uso_solo_fase2.json` (cópias dos JSONs de `data/processed/`). Metodologia e decisões em [auditoria_fontes_drenagem_poa.md](auditoria_fontes_drenagem_poa.md), [inventario_fontes_poa.md](inventario_fontes_poa.md) e [modelo_retencao_viabilidade.md](modelo_retencao_viabilidade.md).

**O que isto é e o que não é.** Integração de dados: nada aqui estima volume retido, profundidade, duração, capacidade nem conectividade hidráulica. Três tipos de informação ficam separados: **observado** (o que o cadastro municipal diz), **parâmetro fundamentado** (coeficiente com referência) e **hipótese** (cenário declarado).

## 1. Camadas integradas (Frente A, inventário de drenagem)

Arquivos em `data/processed/drenagem/` (GeoParquet, EPSG:31982), todos com `id_origem` (o `OBJECTID`, que pode mudar se a Prefeitura republicar a camada), `valida`, `duplicata_exata_de` e `usar_no_inventario`.

| Camada | Na fonte | Processados | Rejeitados na coleta | Geometrias inválidas | Duplicatas exatas (marcadas) | Usados no inventário |
|---|---|---|---|---|---|---|
| `rede_pluvial` | 133.060 | 133.060 | 0 | 0 | 74 | 132.986 |
| `rede_pluvial_sem_acesso` | 2.775 | 2.775 | 0 | 0 | 3 | 2.772 |
| `rede_pluvial_nao_interligada` | 21 | 21 | 0 | 0 | 0 | 21 |
| `poco_de_visita` | 88.906 | 88.899 | 7 | 0 | 39 | 88.860 |
| `boca_de_lobo` | 44.872 | 44.868 | 4 | 0 | 106 | 44.761 |
| `casas_de_bomba_ebap` | 24 | 24 | 0 | 0 | 0 | 24 |

Rejeitados na coleta são registros sem geometria ou com coordenada `NaN`. Duplicata exata é a mesma geometria (1 cm, linha invertida conta como igual); ela **permanece** na tabela, marcada.

**Classificação operacional original, preservada** (valores do cadastro, sem interpretação):

- Rede pluvial (camada principal): `ativo_no_cadastro` = {"1": 129858, "(vazio)": 3202}
- Rede pluvial sem acesso: `acesso` = {"0": 2775} (tratada como **não operacional** pelo próprio cadastro)
- Rede pluvial não interligada: `ativo_no_cadastro` = {"0": 21} (cadastrada como **inativa**)

### Qualidade do inventário

| Camada | Sinalização (valor original mantido) | Registros | % da camada |
|---|---|---|---|
| `rede_pluvial` | `altitude_montante_fora_da_faixa_plausivel` | 3 | 0,00% |
| `rede_pluvial` | `altitude_jusante_fora_da_faixa_plausivel` | 5 | 0,00% |
| `rede_pluvial` | `declividade_fora_da_faixa_plausivel` | 132 | 0,10% |
| `rede_pluvial` | `insercao_montante_fora_da_faixa_plausivel` | 9 | 0,01% |
| `rede_pluvial` | `insercao_jusante_fora_da_faixa_plausivel` | 7 | 0,01% |
| `rede_pluvial` | `insercao_montante_zero_possivel_ausencia` | 43.820 | 32,93% |
| `rede_pluvial` | `insercao_jusante_zero_possivel_ausencia` | 17.305 | 13,01% |
| `rede_pluvial` | `data_implantacao_suspeita` | 13 | 0,01% |
| `rede_pluvial_sem_acesso` | `insercao_montante_zero_possivel_ausencia` | 4 | 0,14% |
| `rede_pluvial_sem_acesso` | `insercao_jusante_zero_possivel_ausencia` | 2 | 0,07% |
| `rede_pluvial_nao_interligada` | `declividade_fora_da_faixa_plausivel` | 1 | 4,76% |
| `rede_pluvial_nao_interligada` | `insercao_montante_zero_possivel_ausencia` | 1 | 4,76% |
| `rede_pluvial_nao_interligada` | `insercao_jusante_zero_possivel_ausencia` | 2 | 9,52% |
| `poco_de_visita` | `altitude_da_tampa_fora_da_faixa_plausivel` | 2 | 0,00% |
| `poco_de_visita` | `profundidade_fora_da_faixa_plausivel` | 1 | 0,00% |
| `poco_de_visita` | `profundidade_zero_possivel_ausencia` | 15 | 0,02% |
| `poco_de_visita` | `data_implantacao_suspeita` | 8 | 0,01% |
| `boca_de_lobo` | `profundidade_zero_possivel_ausencia` | 36.785 | 81,98% |

Colunas **sem nenhum preenchimento** por camada: `rede_pluvial`: extensao_digital; `rede_pluvial_sem_acesso`: junta, encaixe, extensao_digital; `rede_pluvial_nao_interligada`: junta, encaixe, extensao_digital, duplicata_exata_de; `poco_de_visita`: nenhuma; `boca_de_lobo`: nenhuma; `casas_de_bomba_ebap`: local, area_protegida, area_de_contribuicao, secao, configuracao, endereco, descricao, capacidade_texto_original, duplicata_exata_de.

**Evidência geométrica** na rede pluvial (camada principal, registros usados). É evidência, **não** conectividade hidráulica: o cadastro não traz nó nem trecho a montante ou a jusante.

| Evidência (tolerâncias de 0,5 m entre extremos e 1 m a poço de visita) | Fração dos trechos |
|---|---|
| `evidencia_geometrica_inicio_coincide_com_outro_extremo` | 62,0% |
| `evidencia_geometrica_fim_coincide_com_outro_extremo` | 97,0% |
| `evidencia_geometrica_inicio_perto_de_poco_de_visita` | 67,4% |
| `evidencia_geometrica_fim_perto_de_poco_de_visita` | 93,9% |
| `evidencia_geometrica_ambos_extremos_ligados` | 69,5% |

**Bocas de lobo:** mediana de 0,0 m à rede pluvial, 99,0% a até 2 m, 105 a mais de 50 m. Distância geométrica: **não** prova conexão nem funcionamento, e nenhum identificador de trecho é atribuído.

**Casas de bomba:** 24 registros; **0 com capacidade informada** (o campo está vazio em todos); 19 com o mesmo nome das do projeto, com diferença de posição de até 443,5 m; só no serviço: CB-11B, CB ASA BRANCA, CB TRINCHEIRA CEARÁ, CB SANTA TEREZINHA, CB-11A; só no projeto: CB-11.

## 2. Uso do solo, Profill 2022 (Frentes B e D)

- **605.245 polígonos** em 31 partes; 605.245 processados, 0 rejeitados por geometria vazia.
- **Geometrias inválidas:** 277 (Ring Self-intersection: 277); áreas e pintura usam a geometria reparada.
- **Duplicatas exatas:** 852 (ficam no arquivo, marcadas, e não entram nas somas de área nem na pintura).
- **Polígonos grandes** (mais de 1,5 km) em partição própria: 216; centroides fora da grade: 0.
- **Grade:** 1314 x 1004 células de 30 m, em EPSG:31982 e **a mesma do DEM do projeto** (origem 469.729,92; 6.689.715,87), sem reamostrar o Copernicus para resolução mais fina. A pintura interna é de 3 m.

### Cobertura territorial

| Medida | Valor |
|---|---|
| Área de referência (limite do município, `municipality.parquet`) | 495,00 km² |
| Área classificada (soma dos polígonos únicos) | 471,88 km² (95,3% da referência) |
| Município coberto pela pintura (dentro do limite) | 470,62 de 495,00 km² (95,1%) |
| Lacuna dentro do município (sem polígono) | 24,37 km² |
| Classificado fora do limite do município | 1,26 km² |
| Sobreposição entre polígonos (pintura de 3 m) | 0,000 km² |

A lacuna é a área do município sem polígono de uso do solo. Os blocos de 3 km (linha, coluna do bloco) com mais lacuna, em km²: (3,2) 5,47; (2,2) 3,89; (1,2) 2,67; (2,3) 2,25; (1,0) 1,14; (0,1) 1,12.

**Verificação da causa:** 92,9% da lacuna (22,63 km²) cai sobre polígonos de água do OpenStreetMap, isto é, o Guaíba: o limite do município inclui a água, que o mapa de uso do solo não classifica. Do restante (1,74 km², 0,35% do município), 75,8% está a até 100 m da água (margens); o resto não foi explicado e depende de conferência visual.

**Sobreposição:** a pintura não encontrou nenhum ponto coberto por dois polígonos (duplicatas exatas excluídas): os polígonos formam uma partição sem sobreposição. **Campo `area_m2` da fonte:** é uniformemente cerca de 0,08% maior que a área calculada em EPSG:31982, em todas as classes; o padrão uniforme aponta diferença de escala de projeção, não erro de dado (as áreas deste relatório vêm da geometria).

### Distribuição das classes

| Classe | Polígonos | Área (km²) | % da área classificada | Duplicatas excluídas | Inválidos | Pintura 3 m x polígonos | Campo `area_m2` x geometria | Tratamento |
|---|---|---|---|---|---|---|---|---|
| Vegetação Nativa | 6.910 | 137,84 | 29,2% | 40 | 6 | 0,00% | 0,055% | cenários (Método 2) |
| Jardins, Passeios ou Áreas semi urbanizadas | 21.243 | 87,70 | 18,6% | 152 | 91 | -0,01% | 0,079% | cenários (Método 2) |
| Edificação | 526.005 | 58,33 | 12,4% | 328 | 8 | 0,01% | 0,079% | fundamentada (Método 1) |
| Campo | 2.994 | 48,03 | 10,2% | 26 | 10 | 0,00% | 0,079% | cenários (Método 2) |
| Área Úmida | 1.579 | 32,49 | 6,9% | 2 | 1 | 0,00% | 0,079% | fora do cálculo |
| Vias Pavimentadas | 4.071 | 23,29 | 4,9% | 67 | 1 | 0,02% | 0,079% | fundamentada (Método 1) |
| Cultivo não Irrigado | 1.563 | 17,14 | 3,6% | 6 | 6 | 0,00% | 0,079% | cenários (Método 2) |
| Vegetação Mista | 18.899 | 14,98 | 3,2% | 33 | 21 | -0,04% | 0,079% | cenários (Método 2) |
| Cultivo Irrigado | 149 | 14,11 | 3,0% | 1 | 1 | 0,00% | 0,079% | cenários (Método 2) |
| Reflorestamento ou Vegetação Exótica | 1.115 | 11,53 | 2,4% | 2 | 1 | -0,02% | 0,079% | cenários (Método 2) |
| Pastagem | 344 | 8,28 | 1,8% | 4 | 0 | -0,01% | 0,079% | cenários (Método 2) |
| Solo Exposto | 15.615 | 7,93 | 1,7% | 79 | 103 | 0,01% | 0,079% | cenários (Método 2) |
| Corpo Hídrico | 1.540 | 3,58 | 0,8% | 5 | 0 | 0,02% | 0,079% | fora do cálculo |
| Área Degradada | 525 | 3,33 | 0,7% | 4 | 5 | -0,03% | 0,079% | cenários (Método 2) |
| Vias não Pavimentadas | 1.841 | 3,30 | 0,7% | 103 | 20 | 0,00% | 0,079% | cenários (Método 2) |

As duas últimas colunas medem a consistência: a área da pintura de 3 m contra a soma dos polígonos, e o campo `area_m2` da fonte contra a área calculada em EPSG:31982.

## 3. Coeficientes fundamentados (Método 1)

Só o que a referência sustenta diretamente. **Não se extrapola** para outras classes. Referência: TxDOT Hydraulic Design Manual, cap. 4, seção 12, Tabela 4-10 (txdot.gov/manuals/des/hyd/chapter-4--hydrology/section-12--rational-method/runoff-coefficients.html), consultada em 25/11/2026.

| Classe | C (adimensional) | Linha da tabela de referência | Enquadramento | Área (km²) | % da área classificada | Incerteza |
|---|---|---|---|---|---|---|
| Edificação | 0,75 a 0,95 | Roofs | direto | 58,33 | 12,4% | baixo |
| Vias Pavimentadas | 0,70 a 0,95 | Streets: Asphaltic 0.85-0.95; Concrete 0.90-0.95; Brick 0.70-0.85 | envelope | 23,29 | 4,9% | medio |

**Cobertura do Método 1:** 81,62 km², ou **17,3%** da área classificada do município. Fora do cálculo de escoamento (área úmida e corpo hídrico): 36,07 km² (7,6%). **Sem coeficiente fundamentado:** 354,20 km² (**75,1%**).

(O percentual de 17,3% citado na auditoria anterior vale para o município inteiro, medido nas estatísticas do servidor. No piloto urbano de 1 km² as duas classes somam 49,3%; não é uma estimativa da cidade.)

## 4. Cenários determinísticos (Método 2), com hipótese declarada

Aplicam-se **só** às classes que o Método 1 não cobre. Cada valor tem natureza declarada: **limite físico** (C = 0 ou 1, vale por definição, não é estimativa), **referência externa por analogia** (faixa da mesma tabela da TxDOT aplicada por analogia, com a hipótese de enquadramento escrita) ou **mistura de referências com fração hipotética**. São cenários, **não medições**.

| Cenário | Classe afetada | C | Natureza do valor | Área afetada (km²) | Incerteza |
|---|---|---|---|---|---|
| `fisico_inferior` | Vegetação Nativa | 0,00 | limite_fisico | 137,84 | não é estimativa |
| `fisico_superior` | Vegetação Nativa | 1,00 | limite_fisico | 137,84 | não é estimativa |
| `fisico_inferior` | Jardins, Passeios ou Áreas semi urbanizadas | 0,00 | limite_fisico | 87,70 | não é estimativa |
| `fisico_superior` | Jardins, Passeios ou Áreas semi urbanizadas | 1,00 | limite_fisico | 87,70 | não é estimativa |
| `fisico_inferior` | Campo | 0,00 | limite_fisico | 48,03 | não é estimativa |
| `fisico_superior` | Campo | 1,00 | limite_fisico | 48,03 | não é estimativa |
| `fisico_inferior` | Cultivo não Irrigado | 0,00 | limite_fisico | 17,14 | não é estimativa |
| `fisico_superior` | Cultivo não Irrigado | 1,00 | limite_fisico | 17,14 | não é estimativa |
| `fisico_inferior` | Vegetação Mista | 0,00 | limite_fisico | 14,98 | não é estimativa |
| `fisico_superior` | Vegetação Mista | 1,00 | limite_fisico | 14,98 | não é estimativa |
| `fisico_inferior` | Cultivo Irrigado | 0,00 | limite_fisico | 14,11 | não é estimativa |
| `fisico_superior` | Cultivo Irrigado | 1,00 | limite_fisico | 14,11 | não é estimativa |
| `fisico_inferior` | Reflorestamento ou Vegetação Exótica | 0,00 | limite_fisico | 11,53 | não é estimativa |
| `fisico_superior` | Reflorestamento ou Vegetação Exótica | 1,00 | limite_fisico | 11,53 | não é estimativa |
| `fisico_inferior` | Pastagem | 0,00 | limite_fisico | 8,28 | não é estimativa |
| `fisico_superior` | Pastagem | 1,00 | limite_fisico | 8,28 | não é estimativa |
| `fisico_inferior` | Solo Exposto | 0,00 | limite_fisico | 7,93 | não é estimativa |
| `fisico_superior` | Solo Exposto | 1,00 | limite_fisico | 7,93 | não é estimativa |
| `fisico_inferior` | Área Degradada | 0,00 | limite_fisico | 3,33 | não é estimativa |
| `fisico_superior` | Área Degradada | 1,00 | limite_fisico | 3,33 | não é estimativa |
| `fisico_inferior` | Vias não Pavimentadas | 0,00 | limite_fisico | 3,30 | não é estimativa |
| `fisico_superior` | Vias não Pavimentadas | 1,00 | limite_fisico | 3,30 | não é estimativa |
| `referencia_analoga` | Campo | 0,050 a 0,800 | referencia_externa_por_analogia | 48,03 | alto |
| `referencia_analoga` | Pastagem | 0,050 a 0,800 | referencia_externa_por_analogia | 8,28 | alto |
| `referencia_analoga_jardins_f25` | Jardins, Passeios ou Áreas semi urbanizadas | 0,225 a 0,500 | mistura_de_referencias_com_fracao_hipotetica | 87,70 | muito alto |
| `referencia_analoga_jardins_f50` | Jardins, Passeios ou Áreas semi urbanizadas | 0,400 a 0,650 | mistura_de_referencias_com_fracao_hipotetica | 87,70 | muito alto |
| `referencia_analoga_jardins_f75` | Jardins, Passeios ou Áreas semi urbanizadas | 0,575 a 0,800 | mistura_de_referencias_com_fracao_hipotetica | 87,70 | muito alto |
| `todos` | Área Úmida | sem coeficiente | fora_do_calculo_de_escoamento | 32,49 | alto |
| `todos` | Corpo Hídrico | sem coeficiente | fora_do_calculo_de_escoamento | 3,58 | alto |

Hipóteses completas (uma por linha) em `config/uso_solo_cenarios_metodo2_hipoteticos.csv`. Classes **sem nenhuma referência** além dos limites físicos, por falta de fonte consultada: Cultivo Irrigado, Cultivo não Irrigado, Reflorestamento ou Vegetação Exótica, Solo Exposto, Vegetação Mista, Vegetação Nativa, Vias não Pavimentadas, Área Degradada.

Para fechar essas lacunas sem inventar valor: (1) integrar pedologia e declividade para usar faixas por tipo de solo e declividade; (2) buscar na literatura brasileira coeficientes por classe de cobertura, com a fonte; (3) obter a fração permeável da classe 'Jardins, Passeios ou Áreas semi urbanizadas' (a maior incerteza na cidade construída).

## 5. Estrutura de cálculo preparada (sem volume retido)

`flooding_mapping.escoamento` implementa `V = P x A x C / 1000` (P em mm, A em m², C adimensional, V em m³) com validação de unidades, os dois métodos separados e o aviso de que o resultado é **água potencialmente escoada** (limite superior, sem infiltração nem perdas), nunca volume retido.

## 6. Arquivos processados

| Arquivo | Registros ou células | SHA-256 (início) | MB |
|---|---|---|---|
| `data/processed/drenagem/rede_pluvial.parquet` | 135.856 | 958e8b20e409 | 9,0 |
| `data/processed/drenagem/pocos_de_visita.parquet` | 88.899 | 3f2fd89233e3 | 3,0 |
| `data/processed/drenagem/bocas_de_lobo.parquet` | 44.868 | 5e67b6587d31 | 1,5 |
| `data/processed/drenagem/casas_de_bomba.parquet` | 24 | cec3ed5b5db2 | 0,0 |
| `data/processed/uso_solo/uso_solo_grade30m.parquet` | 554.807 | ver `data/raw/manifest.json` | - |

Todos registrados em `data/raw/manifest.json` com origem, data, hash, formato e versão do processamento; reexecutar não duplica nada (mesmo conteúdo, mesmo hash). `data/processed/` fica fora do Git.

## 7. Limitações

- Inventário cadastral: nenhuma capacidade, vazão, operação ou conectividade hidráulica é atribuída.
- A rede sem acesso e a não interligada não são tratadas como operacionais ou ativas.
- Bocas de lobo não recebem identificador de trecho, e a distância geométrica não prova conexão nem funcionamento.
- Casas de bomba: só nome e posição; o campo de capacidade está vazio.
- Unidades inferidas pelos valores; os serviços não as declaram nem documentam a referência vertical das altitudes.
- A escala 1:2.500 é a de produção do mapa (interpretação visual de ortoimagem de 2018 a 2021, 30 cm), não uma resolução nem uma garantia de precisão dos limites.
- As áreas por célula vêm de uma pintura de 3 m: sem viés, mas com ruído nas feições pequenas; a diferença por classe contra a soma dos polígonos está em 'classes'.
- Sobreposição e lacuna são medidas na pintura de 3 m, não por interseção exata de polígonos.
- Nenhum coeficiente de escoamento é aplicado aqui, e a classe 'Jardins, Passeios ou Áreas semi urbanizadas' segue sem coeficiente único.
