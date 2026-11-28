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
PYTHONPATH=src .venv/bin/python tools/preparar_para_r2.py --so-geoai --saida data/interim/r2_preparado   # só a camada E, no prefixo próprio geoai-<hash>/, e o manifesto em docs/manifestos/
```

## No produto
- **Mapa interativo:** checkbox *E. Fração construída estimada (GeoAI, experimental)*, selo Experimental, controle de opacidade, legenda de cinco classes e os avisos acima. A imagem só é baixada ao ligar a camada, fica logo acima do relevo e abaixo das ruas e das análises, e não carrega os dados de A a D. Exige WebGL.
- **Landing:** quinta aba do seletor de dimensões, com mapa, legenda, números, os cinco bairros de maior fração estimada (descrição da estimativa, e não ranking de risco), o que o mapa não mostra e as lacunas.
- **Dados de origem:** Sentinel-2 L2A (Copernicus, via AWS Open Data) e AlphaEarth (CC BY 4.0, só no experimento); referência Profill 2022 (Prefeitura de Porto Alegre).

## Compatibilidade com o mapa (conferida por testes)
`tests/test_camada_geoai.py` confere, com os dados reais:
- a imagem contém o raster de origem inteiro (cantos convertidos de EPSG:31982 para graus) e fica dentro da caixa do mapa-base `poa.pmtiles`;
- 3.000 pixels visíveis sorteados da imagem têm a classe (cor) da célula de origem que está embaixo, com menos de 2% de discordância (só as bordas da reamostragem);
- o raster está alinhado com dados independentes do OpenStreetMap: fração média de 0,014 sobre a água contra 0,246 fora dela, e a correlação com a fração de edificações do OSM é máxima sem deslocamento (0,597; qualquer deslocamento de uma célula, 30 m, a reduz).

`tests/e2e/mapa_integrado.js` confere no navegador: os cantos da fonte da imagem no MapLibre são exatamente os do `meta.json`, a camada é semitransparente (a base continua visível), fica abaixo das ruas e do sombreado fora de Porto Alegre, e ligar a E não desliga o escoamento nem a drenagem nem altera os filtros.

## Publicação (prefixo próprio, sem tocar a versão principal)
A camada E usa o prefixo `geoai-<12 hex do conteúdo>/geoai/` no mesmo bucket; a versão principal `d-b7f6f03555d9` não é lida nem alterada. O prefixo atual é `geoai-f11490d2ef1a` (2 objetos, 83 KB; hashes em `docs/manifestos/manifesto_geoai-f11490d2ef1a.json`).
```
# 1. conferir o pacote, sem rede (já feito: 0 erros)
PYTHONPATH=src .venv/bin/python tools/enviar_para_r2.py data/interim/r2_preparado/geoai-f11490d2ef1a --validar
# 2. enviar, no SEU terminal, com R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY e R2_BUCKET definidos
PYTHONPATH=src .venv/bin/python tools/enviar_para_r2.py data/interim/r2_preparado/geoai-f11490d2ef1a --enviar --esperar-versao geoai-f11490d2ef1a --esperar-objetos 2
# 3. verificar pela URL pública
python tools/verificar_publicacao.py https://pub-66f5a12eb6834ef2b736fc85c89ca28c.r2.dev --geoai-prefixo geoai-f11490d2ef1a
# 4. só com o passo 3 sem reprovação: ligar a camada em config/publicacao.json ("geoai_publicada": true) e reconstruir o site
```
O site só aponta para a camada E quando `geoai_publicada` é verdadeiro; antes disso a camada aparece desabilitada com o aviso "Camada experimental ainda não publicada neste ambiente", e as demais camadas não dependem dela.

## Interpretação
Leia a camada como uma estimativa da fração da célula de 30 m ocupada por construção, para comparar áreas entre si. Não é impermeabilidade medida, coeficiente de escoamento, risco nem previsão de alagamento, e não entra no motor nem em nenhum número do estudo.
