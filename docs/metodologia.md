# Metodologia consolidada

Este documento descreve **o que foi de fato executado**, na ordem do pipeline, e aponta os documentos de detalhe. Termos conforme o [glossário](glossario.md); fontes e licenças em [`inventario_fontes.md`](inventario_fontes.md); referências em [`referencias_bibliograficas.md`](referencias_bibliograficas.md). Tudo o que não foi executado (validação independente, transferência da GeoAI, validação hidrológica, publicação) está dito como tal.

## 1. Pergunta e escopo

Dada uma chuva, como o escoamento superficial tende a se distribuir pelo território de Porto Alegre, e onde há condições mais favoráveis à concentração e à retenção de água? O estudo estima **geração**, **concentração** (contribuição acumulada) e **propensão topográfica à retenção** por trecho viário, com a **drenagem cadastrada** como contexto. Ele apoia a investigação territorial e o planejamento preventivo. **Não prevê alagamentos, profundidade nem duração da água, não é serviço em tempo real e não substitui a Defesa Civil.**

## 2. Princípio de reuso de dados abertos

O estudo utiliza dados geoespaciais públicos, provenientes de bases governamentais e iniciativas de dados abertos, reutilizados para fins de pesquisa, análise e desenvolvimento de produtos geoespaciais. As fontes originais são referenciadas na documentação técnica.

Isso descreve a abordagem do estudo, e não uma autorização geral de redistribuição: a licença de cada fonte, quando existe, e as fontes sem licença identificada estão no inventário. A licença MIT do repositório cobre o código, não os dados de terceiros.

## 3. Dados

| Insumo | Fonte (citação) | Papel |
|---|---|---|
| Relevo | Copernicus DEM GLO-30, 30 m (EUROPEAN SPACE AGENCY; AIRBUS, 2022) | Fluxo, depressões e contribuição |
| Uso e cobertura do solo | Profill 2022, 15 classes, 1:2.500 (PROFILL, 2023) | Área por classe em cada célula (geração) |
| Rede viária e água | OpenStreetMap, 176.836 trechos na malha, dos quais 143.149 dentro de Porto Alegre (recorte municipal: [`recorte_municipal.md`](recorte_municipal.md)) (OPENSTREETMAP CONTRIBUTORS, 2026) | Unidade de apresentação (trechos) e máscara de água |
| Coeficientes de escoamento C | Manuais públicos (TEXAS DEPARTMENT OF TRANSPORTATION, [s. d.]; COUNTY OF SAN DIEGO, [s. d.]) | Faixas por classe |
| Drenagem | Cadastro da Prefeitura (PORTO ALEGRE, [s. d.]b) | Contexto, fora do cálculo |
| Chuva | Série diária do Open-Meteo, 2017 a 2026, reanálise com base em ERA5 (ZIPPENFENIG, 2023; HERSBACH et al., 2020) | Posição dos cenários de 10, 20 e 30 mm na distribuição de eventos |
| Registros históricos | Alagamentos de 2013 e 2014 (PORTO ALEGRE, [s. d.]c); risco mapeado (SERVIÇO GEOLÓGICO DO BRASIL, [s. d.]) | Validação exploratória e contexto qualitativo |
| Mapa-base e relevo 3D | Protomaps e Mapzen (PROTOMAPS, 2026b; MAPZEN, [s. d.]) | Só visualização |

## 4. Processamento geoespacial

1. **Grade.** Todas as camadas vão para a grade de 30 m do modelo de elevação (EPSG:31982, 1.314 × 1.004 células, a mesma do DEM). O uso do solo é pintado a 3 m e vira área por classe em cada célula; 277 polígonos inválidos foram reparados e 852 duplicatas, excluídas das somas.
2. **Depressões.** O modelo de elevação é preenchido por priority-flood com um gradiente mínimo (BARNES; LEHMAN; MULLA, 2014), implementação própria. A altura que o preenchimento soma a cada célula é o **indicador topográfico**.
3. **Direção de fluxo.** Receptor único D8 (O'CALLAGHAN; MARK, 1984): cada célula tem no máximo um vizinho a jusante, e o fluxo forma árvores cujas raízes são exutórios. Células de água grande viram exutório (a água sai do modelo).

## 5. Geração, concentração e propensão

- **Geração de escoamento (potencial).** Em cada célula, V = P × A × C ÷ 1000 (P em mm, A em m², C coeficiente, V em m³), em intervalo [C mínimo, C máximo]. Três **pacotes de coeficientes**, que cobrem classes diferentes e nunca se somam: **Método 1** (Edificação 0,75 a 0,95; Vias Pavimentadas 0,70 a 0,95, a partir de TEXAS DEPARTMENT OF TRANSPORTATION, [s. d.]); **referência por analogia** (Campo, Pastagem e Jardins, em faixas declaradas); **limites físicos** (C = 0 e C = 1, por definição). O coeficiente fundamentado cobre 17,3% da área classificada; o resto é cenário declarado. É um limite superior: sem infiltração, perdas, evaporação nem tempo.
- **Concentração do escoamento (contribuição acumulada).** A geração das células é somada sobre a sub-árvore a montante de cada célula, com a massa conservada (erro relativo máximo de 1,4 × 10⁻¹⁴). O trecho é amostrado a cada 6 m e só as células da pegada sem outra a jusante entram, para cada área a montante ser contada uma vez. **Não é vazão, e não se soma entre trechos.**
- **Propensão topográfica à retenção.** O indicador topográfico, em posto relativo entre trechos; só uma minoria dos trechos tem depressão a preencher no modelo de 30 m. **Não é profundidade, volume nem duração.**
- **Dados ausentes.** Trecho sem dado fica "sem dado", nunca zero.

Equações, unidades e verificações: [`fase3_motor.md`](fase3_motor.md); entradas e saídas: [`fase3_entradas_e_saidas.md`](fase3_entradas_e_saidas.md); qualidade das bases: [`qualidade_dados_fase2.md`](qualidade_dados_fase2.md).

## 6. Chuva de referência e cenários

Os cenários são **10, 20 e 30 mm**, uniformes em toda a cidade e sem distribuição no tempo: entrada do motor, não previsão. Na série diária de 2017-01-01 a 2026-11-02 (3.593 dias), um **evento** é a sequência de dias seguidos com pelo menos 1 mm. 30 mm fica no percentil 75 dos totais por evento (29,9 mm; média de 22,8 mm; mediana de 12,7 mm), e 10 mm no percentil 43. O resultado é linear em P (o volume de 30 mm é 3 vezes o de 10 mm, conferido por trecho). A série é de reanálise, não de pluviômetro; o modelo efetivo do Open-Meteo por período não está registrado, porque o projeto não fixou o parâmetro de modelo.

## 7. Verificação e validação

- **Verificações do motor:** conservação de massa, equivalência com a acumulação de fluxo da biblioteca própria de suscetibilidade e consistência entre o mapa, os resultados e o Parquet (testes automatizados).
- **Validação histórica exploratória.** Os 124 trechos alagados de 2013 e 2014 (PORTO ALEGRE, [s. d.]c) **não têm horário nem chuva associada**; o motor é condicionado à chuva. A comparação, com validação por blocos espaciais de 1,5 km em 5 dobras, discute plausibilidade: nenhum modelo superou a regra de terreno em uso, e **isso não é validação preditiva**.
- **Risco mapeado** (SERVIÇO GEOLÓGICO DO BRASIL, [s. d.]): só contexto qualitativo; a classe Alto cobre cerca da metade da área e discrimina pouco.
- **Não realizado:** validação hidrológica com chuva e nível observados, e qualquer calibração do coeficiente C.

## 8. GeoAI (frente experimental)

**Objetivo.** Testar se imagens de satélite e aprendizado de máquina estimam a **fração construída** (Edificação e Vias Pavimentadas) por célula de 30 m. É classificação da cobertura do solo, **não** previsão de alagamentos, de impermeabilidade, de coeficiente C, de vazão ou de volume, e **não alimenta o motor**. Detalhes: [`geoai_fase5.md`](geoai_fase5.md) e [`geoai_resultados.md`](geoai_resultados.md).

| Elemento | O que foi executado |
|---|---|
| Imagens | Sentinel-2 L2A, tile MGRS 22JDM, 30 cenas de 2019 a 2021, mediana por pixel após máscara de nuvem e sombra (EUROPEAN SPACE AGENCY, [s. d.]; DRUSCH et al., 2012) |
| Variáveis | 6 bandas, 4 índices (NDVI, NDBI, MNDWI, BSI), 3 atributos temporais e 2 de mistura intra-célula; agregadas a 3 × 3 pixels de 10 m por célula |
| Rótulo e referência | Profill 2022 (PROFILL, 2023): fração do grupo "construído" sobre a área classificada fora da classe mista "Jardins, Passeios ou Áreas semi urbanizadas", em 407.574 células |
| Modelo treinado | `RandomForestRegressor` multissaída do scikit-learn 1.9.1 (BREIMAN, 2001; PEDREGOSA et al., 2011) |
| Hiperparâmetros | 200 árvores, `min_samples_leaf` 5, `max_features` 0,33, 150.000 células por dobra, semente 20261126; **sem ajuste** |
| Modelo comparado | Embeddings AlphaEarth de 2020, 64 dimensões (GOOGLE; GOOGLE DEEPMIND, [s. d.]; BROWN et al., 2025), com o mesmo protocolo |
| Validação espacial | P1: 5 dobras de blocos de 3 km, faixa de exclusão de 150 m; P2: um quadrante inteiro fora; intervalos de 95% por bootstrap de blocos (ROBERTS et al., 2017) |

**Resultados.** Erro absoluto médio da fração construída de 0,049 (intervalo de 95%: 0,041 a 0,058) em P1 e 0,052 (0,044 a 0,062) em P2; macro F1 de 0,659. **O AlphaEarth empatou com o Random Forest** (diferença de erro de −0,0009, intervalo de −0,0029 a +0,0013, que inclui zero; macro F1 de 0,624): não há ganho demonstrado. Só 57,4% dos bairros ficaram dentro de 10% de erro na área construída (meta proposta: 80%).

**Limitações explícitas.**

- A concordância com os rótulos da Profill **não constitui validação independente em campo**: a Profill é rótulo e referência ao mesmo tempo, é interpretação visual de ortoimagem de 2018 a 2021 e tem erros próprios.
- **Solo exposto (F1 de 0,23) e água (F1 de 0,54) têm desempenho insuficiente** e não devem ser usados.
- Não houve amostra independente (OLOFSSON et al., 2014, planejada) nem teste em outro município: a generalização é hipótese. O desempenho piora onde há muita mistura (jardins e passeios).
- A seleção das cenas não incluiu janeiro a março, e as imagens (2019 a 2021) não coincidem exatamente com a referência (2018 a 2021).
- Fração construída não é impermeabilidade, e impermeabilidade não é o coeficiente C: o resultado não se converte em volume.
- O raster experimental (COG) **não é publicado**: a redistribuição de derivados da Profill não foi esclarecida.
- O Prithvi-EO-2.0 (SZWARCMAN et al., 2024) foi avaliado e **não executado**.

## 9. O que o estudo não faz

Não prevê alagamentos, profundidade nem duração; não calcula vazão, volume efetivamente transportado nem retido; não usa chuva real distribuída no espaço e no tempo; não valida contra observações de campo; não integra a GeoAI ao motor; não opera em tempo real. A drenagem cadastrada é contexto: sua presença não comprova capacidade nem funcionamento.

## 10. Reprodução

`README.md` (seção "Escoamento superficial e GeoAI") lista os comandos. Os dados derivados ficam fora do Git e se regeneram com `tools/executar_fase3.py`, `tools/preparar_camada_fase3.py` e `tools/executar_geoai.py`; as entradas têm SHA-256 em `data/raw/manifest.json`. Os números da landing são gerados dos relatórios (`tools/gerar_landing.py`) e conferidos por testes.
