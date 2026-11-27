# Resultados do experimento GeoAI (Fase 5)

Relatório **gerado** por `tools/gerar_relatorio_geoai.py` a partir de `reports/qa/geoai_resultados.json` e do manifesto `data/processed/geoai/manifesto_geoai-fase5-f082089c4c59.json` (ambos fora do Git). Interpretação, limites e decisão: [`geoai_fase5.md`](geoai_fase5.md).

- **Experimento:** `geoai-fase5-f082089c4c59`. executado em 2026-11-26; 407.574 células de 30 m (79 blocos de 3 km em 5 dobras; 5 blocos de borda excluídos por terem poucas células).
- **Imagens:** Sentinel-2 L2A, tile MGRS-22JDM, 30 cenas de 2019-01-01 a 2021-12-31, linha(s) de processamento 05.00; mediana por pixel após máscara SCL.
- **Referência:** Profill 2022 (interpretação visual de ortoimagem de 30 cm, 2018 a 2021). Ela é o rótulo de treino **e** a referência de avaliação: os números abaixo medem a **concordância com a Profill em blocos não vistos**, não a exatidão contra a verdade de campo.
- **Alvo:** fração da célula em cada grupo, sobre a área que a Profill classifica fora da classe mista "Jardins, Passeios ou Áreas semi urbanizadas". Construído = Edificação + Vias Pavimentadas.
- Intervalos entre colchetes: 95% por reamostragem de **blocos** (bootstrap), não de células.

## 1. Protocolo P1: validação espacial por blocos (5 dobras, buffer de 5 células)

| Modelo | MAE fração construída | RMSE | Viés | Macro F1 | IoU construído | F1 construído |
|---|---|---|---|---|---|---|
| `media_do_treino` | 0,270 [0,241; 0,303] | 0,347 [0,304; 0,390] | 0,000 [-0,059; 0,052] | 0,220 [0,210; 0,228] | 0,000 [0,000; 0,000] | 0,000 [0,000; 0,000] |
| `linear_ndvi_ndbi_mndwi` | 0,116 [0,101; 0,132] | 0,190 [0,173; 0,206] | 0,013 [-0,008; 0,033] | 0,444 [0,433; 0,452] | 0,688 [0,631; 0,733] | 0,815 [0,774; 0,846] |
| `rf_S1_bandas` | 0,055 [0,046; 0,065] | 0,121 [0,106; 0,136] | 0,003 [-0,006; 0,012] | 0,643 [0,609; 0,668] | 0,803 [0,759; 0,833] | 0,891 [0,863; 0,909] |
| `rf_S2_indices` | 0,054 [0,045; 0,064] | 0,122 [0,107; 0,137] | 0,004 [-0,005; 0,012] | 0,653 [0,619; 0,678] | 0,802 [0,758; 0,833] | 0,890 [0,862; 0,909] |
| `rf_S3_temporais` | 0,051 [0,043; 0,060] | 0,113 [0,101; 0,125] | 0,002 [-0,005; 0,008] | 0,652 [0,615; 0,679] | 0,815 [0,778; 0,841] | 0,898 [0,875; 0,914] |
| `rf_S4_intra_celula` | 0,049 [0,041; 0,058] | 0,111 [0,099; 0,124] | 0,001 [-0,005; 0,006] | 0,659 [0,624; 0,684] | 0,818 [0,783; 0,844] | 0,900 [0,878; 0,915] |
| `linear_AEF` | 0,062 [0,053; 0,073] | 0,118 [0,104; 0,133] | 0,007 [0,002; 0,010] | 0,575 [0,536; 0,601] | 0,820 [0,779; 0,848] | 0,901 [0,876; 0,918] |
| `rf_AEF` | 0,048 [0,039; 0,058] | 0,109 [0,095; 0,123] | -0,000 [-0,003; 0,002] | 0,624 [0,585; 0,658] | 0,824 [0,783; 0,852] | 0,903 [0,878; 0,920] |

`media_do_treino` e `linear_ndvi_ndbi_mndwi` são controles ingênuos. `rf_S1` a `rf_S4` são o Random Forest com conjuntos crescentes de atributos; `rf_AEF` e `linear_AEF` usam os embeddings AlphaEarth de 2020 (64 dimensões) com o mesmo protocolo.

### Escolha do conjunto de atributos do Random Forest

Regra fixada antes de rodar: partir de S1 e só adotar o conjunto seguinte se o intervalo de 95% (blocos) da redução de MAE exclui zero. **Escolhido: `rf_S4_intra_celula`.**

| De | Para | MAE(anterior) − MAE(seguinte) | IC 95% | Adotado |
|---|---|---|---|---|
| S1_bandas | S2_indices | 0,0013 | [0,0008; 0,0018] | sim |
| S2_indices | S3_temporais | 0,0033 | [0,0005; 0,0067] | sim |
| S3_temporais | S4_intra_celula | 0,0018 | [0,0011; 0,0029] | sim |

### Comparação pareada com o modelo primário (`rf_S4_intra_celula`)

Diferença de MAE (modelo − primário) nos mesmos blocos reamostrados; negativa = o modelo é melhor que o primário; intervalo que contém zero = sem diferença demonstrada.

| Modelo | Diferença de MAE | IC 95% | Leitura |
|---|---|---|---|
| `media_do_treino` | 0,2211 | [0,1985; 0,2463] | pior que o primário |
| `linear_ndvi_ndbi_mndwi` | 0,0674 | [0,0584; 0,0763] | pior que o primário |
| `rf_S1_bandas` | 0,0064 | [0,0029; 0,0109] | pior que o primário |
| `rf_S2_indices` | 0,0052 | [0,0017; 0,0093] | pior que o primário |
| `rf_S3_temporais` | 0,0018 | [0,0011; 0,0029] | pior que o primário |
| `linear_AEF` | 0,0136 | [0,0108; 0,0165] | pior que o primário |
| `rf_AEF` | -0,0009 | [-0,0029; 0,0013] | sem diferença demonstrada |

## 2. Protocolo P2: deixar um quadrante inteiro de fora

Quatro quadrantes (norte/sul × oeste/leste); cada um é previsto por um modelo treinado nos outros três, com buffer. É o teste mais próximo de "aplicar onde o modelo não viu nada parecido".

| Modelo | MAE fração construída | Viés | Macro F1 | MAE por quadrante (0 a 3) |
|---|---|---|---|---|
| `media_do_treino` | 0,289 [0,259; 0,323] | 0,003 [-0,069; 0,063] | 0,220 [0,210; 0,228] | 0: 0,340; 1: 0,308; 2: 0,230; 3: 0,260 |
| `linear_ndvi_ndbi_mndwi` | 0,125 [0,109; 0,144] | 0,007 [-0,020; 0,030] | 0,440 [0,429; 0,449] | 0: 0,159; 1: 0,159; 2: 0,096; 3: 0,090 |
| `rf_S4_intra_celula` | 0,052 [0,044; 0,062] | -0,002 [-0,011; 0,004] | 0,651 [0,617; 0,677] | 0: 0,075; 1: 0,063; 2: 0,053; 3: 0,025 |
| `linear_AEF` | 0,064 [0,055; 0,074] | 0,009 [0,004; 0,013] | 0,560 [0,529; 0,585] | 0: 0,076; 1: 0,082; 2: 0,068; 3: 0,040 |
| `rf_AEF` | 0,050 [0,042; 0,060] | -0,000 [-0,003; 0,003] | 0,616 [0,578; 0,650] | 0: 0,069; 1: 0,065; 2: 0,054; 3: 0,023 |

## 3. Classes duras do modelo primário (`rf_S4_intra_celula`, P1)

Classe dura = maior fração. Linhas = Profill, colunas = estimativa.

| | construído | vegetação | solo exposto | água | Suporte | Precisão | Recall | F1 | IoU |
|---|---|---|---|---|---|---|---|---|---|
| **construído** | 66.677 | 6.003 | 287 | 53 | 73.020 | 0,888 | 0,913 | 0,900 | 0,818 |
| **vegetação** | 5.655 | 311.969 | 1.974 | 222 | 319.820 | 0,955 | 0,975 | 0,965 | 0,932 |
| **solo exposto** | 2.457 | 7.087 | 1.746 | 24 | 11.314 | 0,435 | 0,154 | 0,228 | 0,129 |
| **água** | 334 | 1.696 | 9 | 1.381 | 3.420 | 0,822 | 0,404 | 0,542 | 0,371 |

Macro F1: 0,659. Água e solo exposto têm poucas células e, a 10 m, se confundem com o construído e entre si: os números dessas duas classes têm pouco peso e não sustentam uso.

## 4. Onde o modelo erra: estrato de classe mista

Fração da célula em "Jardins, Passeios ou Áreas semi urbanizadas", que a Profill não permite tratar como construída nem como permeável.

| Fração mista | Células | MAE | Viés |
|---|---|---|---|
| 0,00 a 0,10 | 310.512 | 0,029 | 0,014 |
| 0,10 a 0,30 | 53.347 | 0,103 | -0,026 |
| 0,30 a 1,00 | 43.715 | 0,123 | -0,059 |

## 5. Estabilidade entre blocos

79 blocos de 3 km: MAE mediano 0,038; percentis 10 e 90: 0,006 e 0,119; pior bloco 0,156. **83,5% dos blocos** têm MAE de até 0,10.

_Figura gerada só localmente, em `data/interim/geoai/figuras_locais/` (fora do Git, por tamanho), por `tools/gerar_relatorio_geoai.py` e `tools/executar_geoai.py`. A fração construída estimada está publicada como a camada E do mapa interativo e como o mapa de manchas da landing (`docs/geoai_camada_e.md`)._

## 6. Erro da área construída por bairro

94 bairros com ao menos 200 células. Erro relativo total: 2,84%. Erro relativo absoluto mediano: 8,2%. **57,4% dos bairros** ficam dentro de 10%.

Os cinco maiores erros relativos:

| Bairro | Células | Área construída Profill (km²) | Estimada (km²) | Erro relativo |
|---|---|---|---|---|
| Boa Vista do Sul | 25525 | 0,186 | 0,668 | 259,8% |
| São Caetano | 8467 | 0,058 | 0,130 | 123,4% |
| Arquipélago | 46848 | 0,409 | 0,779 | 90,8% |
| Extrema | 25364 | 0,197 | 0,369 | 87,6% |
| Pitinga | 8485 | 0,091 | 0,143 | 57,1% |

## 7. Incerteza

Indicador: desvio entre as 200 árvores na fração construída (incerteza do **modelo**, não intervalo de confiança). Correlação de Spearman com o erro absoluto: **0,96**.

| Quintil do desvio (1 = menor) | Desvio de | Desvio até | Erro absoluto médio |
|---|---|---|---|
| 1 | 0,000 | 0,002 | 0,000 |
| 2 | 0,002 | 0,011 | 0,002 |
| 3 | 0,011 | 0,036 | 0,012 |
| 4 | 0,036 | 0,109 | 0,053 |
| 5 | 0,109 | 0,417 | 0,176 |

Intervalo conforme de 90% (resíduos das outras dobras): cobertura observada por dobra de 87,7% a 91,2% (alvo: 90%). Calibração aproximada: intervalo conforme de 90% com resíduos das outras dobras (modelos dessas dobras viram a dobra testada no treino: calibração aproximada).

_Figura gerada só localmente, em `data/interim/geoai/figuras_locais/` (fora do Git, por tamanho), por `tools/gerar_relatorio_geoai.py` e `tools/executar_geoai.py`. A fração construída estimada está publicada como a camada E do mapa interativo e como o mapa de manchas da landing (`docs/geoai_camada_e.md`)._

_Figura gerada só localmente, em `data/interim/geoai/figuras_locais/` (fora do Git, por tamanho), por `tools/gerar_relatorio_geoai.py` e `tools/executar_geoai.py`. A fração construída estimada está publicada como a camada E do mapa interativo e como o mapa de manchas da landing (`docs/geoai_camada_e.md`)._

## 8. Verificação cruzada com edificações do OpenStreetMap

OSM de edificações não é independente da Profill (origem das importações desconhecida); só indica coerência.

- Área de edificações do OSM nas 407.574 células: 33.0 km²; Profill (Edificação): 35.7 km² (razão 0.925).
- Correlação célula a célula: OSM × Profill-Edificação 0,959 (MAE 0,0122); OSM × Profill-construído 0,843; OSM × estimativa 0,817; Profill-construído × estimativa 0,931.
- Leitura: a coerência entre OSM e Profill é alta, o que **não** prova independência (as importações do OSM podem ter vindo de mapas municipais). A estimativa correlaciona menos com o OSM do que a própria Profill, como esperado: o OSM só tem edificações, e o alvo inclui vias pavimentadas.

## 9. Critérios operacionais propostos no relatório de viabilidade

Critérios **operacionais** definidos antes da execução, sem fundamento normativo; servem para decidir o uso neste projeto, não como padrão científico.

| Critério | Limite | Resultado | Situação |
|---|---|---|---|
| MAE da fração construída, P1 | ≤ 0,10 | 0,049 [0,041; 0,058] | cumprido |
| Viés absoluto, P1 | ≤ 0,03 | 0,001 [-0,005; 0,006] | cumprido |
| MAE da fração construída, P2 (quadrante fora) | ≤ 0,10 | 0,052 [0,044; 0,062] | cumprido |
| Bairros com erro de área ≤ 10% | ≥ 80% dos bairros | 57,4% | não cumprido |
| Blocos com MAE ≤ 0,10 | ≥ 80% dos blocos | 83,5% | cumprido |
| Ganho do foundation model (AlphaEarth) sobre o Random Forest | MAE menor com IC que exclui zero, ou +0,03 de macro F1 | MAE -0,0009 [-0,0029; 0,0013]; macro F1 -0,035 | sem ganho demonstrado |

## 10. Produto e rastreabilidade

- COG: `data/processed/geoai/fracao_construida_30m_geoai-fase5-f082089c4c59.tif` (fracao_construido, fracao_vegetacao, fracao_solo_exposto, fracao_agua, desvio_entre_arvores_construido, classe_predominante, origem_da_previsao), SHA-256 `04b968a90ed7ccd9…`. Fora do Git.
- Modelo: RandomForestRegressor (scikit-learn), conjunto `S4_intra_celula`, sem pesos pré-treinados.
- Dependências: numpy 2.5.4, scipy 1.18.1, scikit-learn 1.9.1, rasterio 1.5.2, geopandas 1.1.4, shapely 2.2.0, pyproj 3.6.1, pandas 3.1.0, pyarrow 26.0.0, matplotlib 3.11.2, pyrosm 0.24.0, python 3.12.13.

