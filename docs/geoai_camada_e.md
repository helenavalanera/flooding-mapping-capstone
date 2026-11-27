# Camada E: fração construída estimada (GeoAI, experimental)

Registro de 27/11/2026. A camada E publica, no mapa interativo e na landing, o resultado do experimento GeoAI da Fase 5 ([`geoai_fase5.md`](geoai_fase5.md), números em [`geoai_resultados.md`](geoai_resultados.md)). É **experimental e independente** das dimensões A (geração), B (contribuição acumulada), C (retenção topográfica) e D (drenagem cadastrada): não entra em nenhum cálculo, não usa o motor e o motor não a usa. Não houve retreino nem novo experimento.

## O que é
A fração construída (Edificação mais Vias Pavimentadas da Profill) estimada por célula de 30 m por um Random Forest (`rf_S4_intra_celula`) treinado com 30 cenas Sentinel-2 L2A de 2019 a 2021 (tile 22JDM, mediana por pixel após máscara SCL). A Profill 2022 foi a referência e a fonte dos rótulos.

## O que NÃO é
Não é impermeabilidade medida, coeficiente de escoamento, vazão nem ocorrência de alagamento.

## Resultados documentados
- MAE da fração construída: **0,049** em blocos de 3 km e **0,052** no quadrante externo.
- AlphaEarth 2020: **sem ganho** sobre o Random Forest (diferença de MAE de −0,0009, com intervalo de 95% que inclui zero).
- Critério de bairros (80% dos bairros com erro de área de até 10%): **não atingido**, 57,4%.
- Prithvi (modelo de fundação): **não executado**, por incompatibilidade entre as dependências e necessidade de GPU.

## Limitações obrigatórias
1. A Profill foi referência **e** fonte dos rótulos: os números medem concordância com ela, e não exatidão contra a verdade de campo.
2. Não existe validação independente contra dados de campo.
3. A transferência para outras áreas não foi testada.
4. Nas células de Porto Alegre, 26,1% são previsão do modelo final em células sem rótulo utilizável da Profill, sem validação.
5. A camada não representa impermeabilidade medida, coeficiente de escoamento, vazão nem ocorrência de alagamento.

## Arquivos
| Arquivo | O que é | Onde |
|---|---|---|
| `fracao_construida_30m_geoai-fase5-f082089c4c59.tif` | COG do experimento: 7 bandas float32, EPSG:31982, 30 m, 1004 × 1314, 28 MB; banda 1 = fração construída. SHA-256 conferido contra o manifesto | `data/processed/geoai/` (fora do Git) |
| `fracao_construida.webp` | Imagem da camada para o mapa: Web Mercator, cinco classes de 0,2, transparente fora do município, 81 KB | `data/processed/geoai_web/` (fora do Git); publicada no R2 |
| `meta.json` da camada | Cantos em graus, origem com hash, classes, métricas lidas de `reports/qa/geoai_resultados.json`, limitações | idem |
| `mapa-geoai.webp` | Mapa de manchas da landing: média da fração em células de 100 m, só dentro do município, 134 KB | `src/flooding_mapping/app/static/inicio/img/estudo/` (no Git) |

## Como gerar
```
PYTHONPATH=src .venv/bin/python tools/preparar_camada_geoai.py          # imagem e meta.json do mapa interativo
PYTHONPATH=src .venv/bin/python tools/gerar_mapas_dimensoes.py --so E   # mapa de manchas da landing
PYTHONPATH=src .venv/bin/python tools/preparar_para_r2.py --mapa-poa    # objetos do R2, com o GeoAI
```

## No produto
- **Mapa interativo:** checkbox *E. Fração construída estimada (GeoAI, experimental)*, selo Experimental, controle de opacidade, legenda de cinco classes e os avisos acima. A imagem só é baixada ao ligar a camada, fica logo acima do relevo e abaixo das ruas e das análises, e não carrega os dados de A a D. Exige WebGL.
- **Landing:** quinta aba do seletor de dimensões, com mapa, legenda, números, os cinco bairros de maior fração estimada (descrição da estimativa, e não ranking de risco), o que o mapa não mostra e as lacunas.
- **Dados de origem:** Sentinel-2 L2A (Copernicus, via AWS Open Data) e AlphaEarth (CC BY 4.0, só no experimento); referência Profill 2022 (Prefeitura de Porto Alegre).
