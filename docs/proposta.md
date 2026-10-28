# Proposta de Projeto Final — Future Tech Leaders Brasil · Space Tech Bootcamp 2026

**Projeto:** Flooding Mapping: quanto da mobilidade urbana Porto Alegre perde com chuvas de até 45 mm
**Candidata:** Helena de Oliveira Valanera — helena.valanera@gmail.com
**Repositório:** https://github.com/helenavalanera/flooding-mapping-capstone/tree/entrega

Versão em Word (2 páginas): `docs/Proposta_Projeto_Final.docx`.

## 1. Ideia do projeto

Alagamentos pluviais fecham cruzamentos e trechos de vias em Porto Alegre várias vezes por ano. O projeto mede **quanto da mobilidade urbana, a pé, de ônibus e de carro, deixa de ser alcançável com chuvas de até 45 mm em 24 horas**, diante das condições precárias de drenagem da cidade, quando trechos documentados são interditados. A ideia é tornar visível que **a cidade fica propensa ao caos e à instabilidade mesmo com chuvas comuns**, prejudicando o deslocamento e o acesso a tudo. Produto final: **cartografia** da mobilidade perdida por nível de chuva e um **dashboard de alerta** com componente de **machine learning**.

## 2. Relevância para os ODS e para o ecossistema espacial

**ODS 11 (11.2 e 11.5)** transporte acessível e redução dos impactos de desastres nas cidades; **ODS 13 (13.1)** resiliência a riscos climáticos; **ODS 9 (9.1)** infraestrutura resiliente. Contribuição prática: mostrar com que frequência e onde a chuva desorganiza a cidade, para priorizar drenagem e desvios, e antecipar trechos e linhas de ônibus expostos. O pipeline usa só dados geoespaciais abertos (OpenStreetMap, GTFS, IBGE e o modelo digital de elevação Copernicus, derivado de satélite), é reprodutível e replicável; a fase 2 incorpora imagens de radar Sentinel-1.

## 3. Exemplos de literatura

- Coles, D. et al. (2017). Beyond “flood hotspots”: modelling emergency service accessibility during flooding in York, UK. J. Hydrology 546:419–436. doi:10.1016/j.jhydrol.2016.12.013 — acopla alagamento e análise de redes para medir acessibilidade.
- Green, D. et al. (2017). City-scale accessibility of emergency responders operating during flood events. NHESS 17:1–16. doi:10.5194/nhess-17-1-2017 — alagamentos superficiais perturbam o deslocamento mais que cheias fluviais de magnitude similar.
- Pregnolato, M. et al. (2017). The impact of flooding on road transport: a depth-disruption function. Transp. Res. D 55:67–81. doi:10.1016/j.trd.2017.06.020.
- Latora, V.; Marchiori, M. (2001). Efficient behavior of small-world networks. Phys. Rev. Lett. 87:198701 — eficiência de redes, base da métrica de robustez.
- Fink, C. et al. (2022). r5py: Rapid Realistic Routing with R5 in Python. doi:10.5281/zenodo.7060437.

## 4. Dados

| Dado | Fonte e formato | Pré-processamento |
|---|---|---|
| Ônibus | GTFS da EPTC, portal de dados abertos (ZIP/CSV) | Vigência efetiva set–dez/2025 (feed vencido, único publicado): referência histórica em 30/10/2025; validador MobilityData sem erros |
| Vias e drenagem | OpenStreetMap/Geofabrik, 24/10/2026 (PBF) | Recorte municipal +3 km; 176.836 segmentos de via; arroios, valas e bueiros |
| População e limites | IBGE, Censo 2022, setores com agregados (GPKG) | Grade de 1 km com população por densidade uniforme (total conservado: 1.332.845) |
| Relevo | Copernicus DEM GLO-30 (GeoTIFF) | Mosaico a 30 m; elevação relativa, declividade, acúmulo de fluxo e índice de umidade |
| Interdições | EPTC/Prefeitura e imprensa citando a EPTC (CSV curado) | 24 bloqueios em 4 datas (2019–2025), 19 geocodificados por interseção de vias |
| Chuva | Open-Meteo: previsão ao vivo, arquivo de previsões e reanálise (JSON) | Chuva antes de cada bloqueio (limiares) e frequência anual 2015–2024 |

## 5. Metodologia (machine learning)

- **Cidade alcançável (r5py):** para cada célula da grade, a população da cidade alcançável em até 30 minutos, a pé, de ônibus e de carro (A0). **Mobilidade perdida** = redução, ponderada pela população, de todos os deslocamentos possíveis quando a chuva fecha vias (A_s).
- **Da chuva ao bloqueio:** abaixo de 26,2 mm em 24 h (menor acumulado com bloqueio registrado) nada fecha; a partir dele fecham os pontos documentados e mais N pontos apontados pelo modelo, com N vindo do ajuste entre chuva e número de bloqueios por data, e um fator de precariedade para simular drenagem pior.
- **ML preditivo, suscetibilidade:** regressão logística regularizada e random forest classificam 107.869 segmentos pela semelhança com locais já interditados (positivos e não rotulados), com variáveis de relevo, escoamento e drenagem; validação espacial (blocos de 2 km) e temporal (treino 2019–2022, teste 2025).
- **Dashboard de alerta:** com a localização do usuário e a previsão de chuva, indica trechos em atenção ou alerta alto, linhas expostas e quanto da cidade deixa de ser alcançável, explicando como a IA calcula. **Também:** robustez das redes (NetworkX), tipologia k-means e, na fase 2, deep learning (U-Net em Sentinel-1) para ampliar os rótulos.

**Justificativa:** há poucos eventos e nenhum registro de “chuva sem alagamento”; por isso o modelo supervisionado é tratado como problema de positivos e não rotulados e comparado a regras simples, e o deep learning só se justifica quando o satélite fornecer rótulos em escala.

**Resultados iniciais:** chuvas de 26 mm ou mais em 24 h, que já causam bloqueios, ocorrem em média **14 dias por ano**. Sem chuva, cada célula alcança em média 80% da cidade de carro, 14% de ônibus e 2,7% a pé. Com 26–35 mm, a cidade perde **3,5% da mobilidade de carro** e **81 mil pessoas** perdem ao menos 10% da cidade alcançável, com perdas locais de até 73%; com 40–45 mm, a perda dobra para **7,0%** e atinge **190 mil pessoas**, e há áreas que perdem 74% do que alcançam a pé. Na suscetibilidade, as variáveis de drenagem elevam a regressão logística do percentil 79 para 86 no teste temporal, empatando com a regra de terreno baixo.

**Limitações:** ajuste chuva × bloqueios com 3 datas; GTFS de 2025; bloqueio binário; eventos com viés de notificação; sem dados abertos de bocas de lobo e limpeza urbana; temporais curtos podem fechar vias abaixo do limiar; o alerta é nível heurístico, não probabilidade, e cobre só Porto Alegre.

