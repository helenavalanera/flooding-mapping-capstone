# Fase 4: a camada de escoamento potencial na aplicação

Estado: **implementada e testada** em 25/11/2026, sem commit, push nem deploy. Os resultados da Fase 3 não foram alterados: a camada só lê os Parquets e distribui o que eles contêm. Método e limites do motor em [fase3_motor.md](fase3_motor.md); resultados em [fase3_resultados.md](fase3_resultados.md).

## O que o usuário encontra

Em **Mapa → Porto Alegre → Camadas → "Escoamento potencial por trecho (motor da Fase 3)"** (desligada por padrão; no RS aparece indisponível, com o motivo). Ao ligar, o mapa se aproxima até o zoom 13, onde os trechos passam a ser desenhados, e o painel oferece:

| Controle | Opções | Observação |
|---|---|---|
| O que mostrar | Contribuição potencial acumulada · Geração potencial local · Indicador topográfico de retenção · Cobertura dos dados | cada grandeza tem **a sua escala e a sua legenda**; a mesma cor nunca vale duas grandezas |
| Pacote de coeficientes | Método 1 (fundamentado) · Método 2 (analogia) · Limites físicos | alternativas, nunca somadas; cada uma mostra natureza, nota e os coeficientes e hipóteses usados |
| Limite do intervalo no mapa | superior · inferior | o painel do trecho mostra sempre o intervalo inteiro |
| Chuva de referência | 10 · 20 · 30 mm | **seleciona entre execuções que já existem**; não há controle livre de precipitação |

Ao clicar num trecho, o painel de seleção mostra: identificador e nome; contribuição potencial estimada (intervalo, m³); volume potencial gerado localmente (intervalo, m³); área contribuinte; cobertura do pacote selecionado e as três coberturas lado a lado, com as frações sem valor, fora do cálculo e sem classe; indicador topográfico; número de células. Cada indicador traz unidade, "o que é" e "como ler". Trecho sem dados diz "Trecho sem dados disponíveis" e que isso **não** significa contribuição zero; no mapa aparece tracejado e na legenda como "não é valor zero". A seção **Metodologia e limitações** tem as oito explicações pedidas, alinhadas a este diretório de documentos.

Nada na tela apresenta volume efetivamente transportado, profundidade, duração, capacidade de retenção ou volume armazenável. O indicador topográfico aparece como **posto de 0 a 100** (ou "sem preenchimento de depressão no modelo") e a altura de preenchimento só aparece como grandeza técnica do modelo, com o aviso de que não é profundidade.

## Arquitetura encontrada e decisões

**Encontrado.** Site estático (HTML e JavaScript sem build) servido pelo `servidor.py` ou publicado por `app/build.py`; mapa com MapLibre GL 4.7.1 (3D) e Leaflet (fallback sem WebGL); mapa-base em PMTiles próprio; camadas declaradas por território em `config/territorios.yaml` → `territorios.json`; controlador único em `mapa.js` sobre dois motores; lógica pura em `logic.js` testada em Node.

**Decisões.**

1. **Tiles vetoriais em diretório + fragmentos JSON por trecho**, não GeoJSON nem endpoint. Medido: um GeoJSON só com geometria, número e classes já tem 58,5 MB (3,7 MB comprimido, mas o navegador o descomprime e o mantém em memória, e 176 mil feições forçam um parse inicial longo). Os tiles baixam só o que a tela cobre. Um endpoint exigiria servidor ativo e não funcionaria no site estático. Nenhuma dependência nova: MapLibre e o GDAL local (`ogr2ogr`, só na preparação).
2. **Os tiles não carregam valores físicos**, só `n` (número de ordem) e classes inteiras de 0 a 6. Os valores vêm do fragmento do trecho, buscado ao clicar (173 fragmentos de ~220 KB; um clique baixa um). Assim a precisão dos números não depende da simplificação dos tiles.
3. **As classes são por quantis dos trechos com valor positivo** (cortes em 20, 40, 60, 80 e 95%), guardadas em m² de área equivalente. Como o volume é linear em P, a classe vale para qualquer chuva; só a legenda em m³ muda (P × corte ÷ 1000). Zero é a classe 0; ausência é a **falta** da propriedade (o trecho vai para uma camada tracejada).
4. **Valores em m² de área equivalente** (`aeq`), como no Parquet; a tela calcula V = P × aeq ÷ 1000. O teste confere essa conta, para 10, 20 e 30 mm, 3 pacotes e 4 colunas, contra `trechos_nivel2_cenarios.parquet` (a saída do motor), com tolerância de 1e-8 relativa (os números têm 9 algarismos significativos).
5. **Chuva:** a proporcionalidade foi validada por teste (V(60) = 2 V(30), V(30) = 3 V(10)), mas o controle continua restrito às três execuções do motor, que é o que foi calculado e documentado.
6. **Sem soma entre trechos.** Nenhum código da tela soma valores de trechos (conferido por teste sobre o código) e não há total da cidade.
7. **Geometria:** a real do `segments.parquet` (a que a Fase 3 usou), reprojetada para WGS84 com precisão de 0,1 m; o gerador de tiles simplifica com tolerância de 2 unidades de tile até o zoom 13. Os dados originais não mudam.
8. **Camada só de 3D (WebGL).** No mapa 2D simples (Leaflet) ela aparece como indisponível, com a mesma mensagem das demais camadas que exigem WebGL.

## Distribuição dos dados

`python tools/preparar_camada_fase3.py` (cerca de 75 s) lê `data/processed/fase3/*.parquet`, `data/interim/segments.parquet` e `data/processed/rede_poa.parquet` e escreve em **`data/processed/fase3_web/`** (derivado, fora do Git, como todo dado processado):

| Parte | Conteúdo | Tamanho |
|---|---|---|
| `tiles/{13,14,15}/x/y.pbf` | geometria real + `n` + 17 classes inteiras | 33,4 MB em 1.067 tiles com trechos (mediana 9,9 KB, p95 134 KB, máximo 817 KB) + 817 tiles vazios dentro da caixa dos dados |
| `detalhe/NNNN.json` | 27 colunas por trecho, 1.024 trechos por arquivo | 173 arquivos, 36,4 MB no total, ≤ 237 KB cada (cerca de 52 KB comprimidos) |
| `meta.json` | chuvas, cortes das classes, hipóteses e coeficientes, contagens, SHA-256 dos Parquets de entrada | poucos KB |

O servidor serve `/fase3/` a partir dessa pasta (`FM_FASE3` a muda), só `.pbf` e `.json` e nunca fora dela; tile ausente responde 204. O site estático só inclui a camada com `python -m flooding_mapping.app.build ... --fase3 data/processed/fase3_web`. Publicar esses 70 MB (Render, R2 ou Pages) é uma decisão de implantação que **não** foi tomada.

## Verificações

`tests/test_fase4_camada.py` (18), `tests/test_fase4_js.py` (14) e `tests/e2e/fase3.js` (navegador):

- **Integridade:** totais, SHA-256 das entradas, identificadores únicos, na mesma ordem do índice e iguais aos dos Parquets; cada coluna igual ao Parquet de origem; ausência em exatamente as mesmas posições (2.919 trechos), zero distinto de ausência; os três pacotes nunca misturados (limite inferior físico é zero, nenhuma coluna igual à de outro pacote, contribuição ≥ geração local).
- **Cálculo:** conversão P × aeq ÷ 1000 igual à saída do motor; proporcionalidade; formatação só na exibição (3 algarismos, sem notação científica); nenhuma coluna chama o indicador de volume ou profundidade; nenhuma soma entre trechos no código.
- **Tiles:** todos os trechos presentes no zoom máximo exceto os com menos de 1 m (8 colapsam a um ponto); classes dos tiles iguais às recalculadas dos dados; sem classe só onde não há dado.
- **Interface:** seleção de trecho, mudança de pacote, limite, grandeza e chuva, atualização de legenda e do painel do trecho, trecho sem dados, hipóteses do Método 2 (envelope 0,225 a 0,8), metodologia, ausência de erros de console e de 4xx/5xx, sem transbordo horizontal em 360, 768 e 1.280 px, termos proibidos ausentes em todos os textos.

## Desempenho observado

Medido em Chrome (WebGL por **software**, sem GPU, mapa 3D com relevo), portanto pessimista: desktop 1.400×900, 38 tiles e 7,0 MB até desenhar cerca de 72 mil trechos em 12 s, memória JS 154 MB, clique até o painel em 0,2 a 0,3 s; celular 390×844, 13 tiles e 3,6 MB, 5 s, 27 mil trechos, 91 a 103 MB. Trocar de pacote repinta sem baixar tiles novos, mas leva de 6 a 25 s nesse modo de renderização; com GPU deve ser bem menor, o que **não foi medido**. A camada só desenha do zoom 13: abaixo disso os tiles passam de 1,9 MB e perdem milhares de trechos curtos.

## Limitações

- Não há visão da cidade inteira de uma vez: de longe o mapa não mostra trechos (são 176.836).
- Nos zooms 13 e 14, trechos de poucos metros podem não ser desenhados (263 e 52 trechos, medidos); no 15 faltam 8 (menos de 30 cm).
- 2.919 trechos não têm dados (2.728 fora da grade e 191 só em células sem dado ou de água): aparecem tracejados e sem valor.
- Os cortes das classes são relativos (quantis): cor igual significa posição parecida entre os trechos, não volume igual; a legenda traz a faixa em m³.
- Camada indisponível sem WebGL; sem os arquivos gerados o painel explica que faltam.
- Desempenho com GPU e em celulares reais não foi medido; a camada não foi publicada, então não há medição remota.
- Todas as limitações do motor continuam valendo ([fase3_motor.md](fase3_motor.md)): chuva uniforme e hipotética, 75,1% da área sem coeficiente fundamentado, modelo de elevação de 30 m, drenagem fora do cálculo, nenhum volume transportado.
