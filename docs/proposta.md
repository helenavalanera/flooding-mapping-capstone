# Proposta de Projeto Final — Future Tech Leaders Brasil · Space Tech Bootcamp 2026 (estudo preliminar)

**Projeto:** Flooding Mapping: estimar o quanto a mobilidade de Porto Alegre é afetada pela chuva com dados públicos defasados
**Candidata:** Helena de Oliveira Valanera — helena.valanera@gmail.com
**Repositório:** https://github.com/helenavalanera/flooding-mapping-capstone/tree/entrega

Versão em Word (2 páginas): `docs/Proposta_Projeto_Final.docx`.

## 1. Ideia do projeto

Alagamentos pluviais fecham cruzamentos e trechos de vias em Porto Alegre várias vezes por ano, e a cidade perde mobilidade mesmo com chuvas comuns. Já existem peças desse quadro: bloqueios informados pela EPTC, relevo, hidrografia e rede viária abertos, população do Censo e horários de ônibus. Mas os dados são parciais e defasados: o último feed de ônibus publicado venceu em 12/12/2025, os bloqueios documentados vão até 06/2025 e não há dados abertos de bocas de lobo nem de limpeza urbana. A proposta é **treinar modelos que estimem o quanto a mobilidade urbana, a pé, de ônibus e de carro, é afetada por chuvas de até 45 mm em 24 horas**, aprendendo com o que já se sabe e podendo ser reajustados quando dados novos chegarem. Produto: **cartografia** da mobilidade perdida e **dashboard de alerta** com a chuva prevista. Este documento é o “pré”: o que já existe e o que será estudado.

## 2. Relevância para os ODS e para o ecossistema espacial

**ODS 11 (11.2 e 11.5)** transporte acessível e redução dos impactos de desastres nas cidades; **ODS 13 (13.1)** resiliência a riscos climáticos; **ODS 9 (9.1)** infraestrutura resiliente. Contribuição prática: estimar onde e quanto a chuva desorganiza a cidade mesmo onde faltam dados, para priorizar drenagem e desvios e antecipar trechos e linhas de ônibus expostos. Usa só dados geoespaciais abertos (OpenStreetMap, GTFS, IBGE e o modelo de elevação Copernicus, derivado de satélite) e é replicável em outras cidades; a fase 2 incorpora radar Sentinel-1.

## 3. Exemplos de literatura

- Coles, D. et al. (2017). Beyond “flood hotspots”: modelling emergency service accessibility during flooding in York, UK. J. Hydrology 546:419–436. doi:10.1016/j.jhydrol.2016.12.013 — acopla alagamento e análise de redes para medir acessibilidade.
- Green, D. et al. (2017). City-scale accessibility of emergency responders operating during flood events. NHESS 17:1–16. doi:10.5194/nhess-17-1-2017 — alagamentos superficiais perturbam o deslocamento mais que cheias fluviais de magnitude similar.
- Pregnolato, M. et al. (2017). The impact of flooding on road transport: a depth-disruption function. Transp. Res. D 55:67–81. doi:10.1016/j.trd.2017.06.020.
- Latora, V.; Marchiori, M. (2001). Efficient behavior of small-world networks. Phys. Rev. Lett. 87:198701 — eficiência de redes, base da métrica de robustez.
- Fink, C. et al. (2022). r5py: Rapid Realistic Routing with R5 in Python. doi:10.5281/zenodo.7060437.

## 4. Dados: o que já existe e sua defasagem

| Dado | O que existe hoje | Defasagem ou lacuna |
|---|---|---|
| Ônibus | GTFS da EPTC (ZIP/CSV), vigência até 12/12/2025; único publicado | Cerca de 10 meses vencido; oferta atual desconhecida |
| Vias e drenagem | OpenStreetMap/Geofabrik de 24/10/2026 (PBF): 176.836 segmentos, arroios e valas | Atual, mas sem bocas de lobo nem microdrenagem |
| População | IBGE, Censo 2022, setores (GPKG): 1.332.845 pessoas | Quatro anos; densidade uniforme dentro do setor |
| Relevo | Copernicus DEM 30 m (GeoTIFF) | Superfície, sem meio-fio nem microrrelevo |
| Bloqueios | 24 pontos da EPTC em 4 datas (2019–2025), 19 geocodificados (CSV curado) | Poucos, com viés de notificação e sem dias de chuva sem bloqueio |
| Chuva | Open-Meteo: previsão, arquivo de previsões e reanálise 2015–2024 (JSON) | Dado modelado; não captou o temporal de 06/03/2022 |

**O que já sabemos (estudo preliminar com esses dados):** a chuva mínima que coincidiu com bloqueios registrados, 26 mm em 24 h, ocorre em média **14 dias por ano**. Sem chuva, uma célula alcança em 30 minutos 80% da cidade de carro, 14% de ônibus e 2,7% a pé. Fechando os pontos documentados e os trechos que um modelo de terreno aponta como mais propensos, a cidade perde **3,5% da mobilidade de carro** com 26–35 mm e **7,0%** com 40–45 mm (190 mil pessoas perdem ao menos 10% do que alcançam), com perdas locais de até 79%. O modelo de terreno, treinado com 17 locais e variáveis de drenagem, atinge o percentil 86 no teste temporal, empatando com a regra “terreno mais baixo” (85).

## 5. Metodologia (machine learning)

- **Modelo 1, suscetibilidade (protótipo pronto):** regressão logística regularizada e random forest ordenam os trechos viários pela semelhança de terreno com locais já interditados (positivos e não rotulados), com validação espacial e temporal.
- **Modelo 2, estimador de impacto (a treinar):** a partir de simulações de roteamento (r5py) com conjuntos variados de trechos fechados, amostrados conforme a suscetibilidade e a chuva (10–45 mm), um modelo de gradient boosting, com regressão regularizada como base, aprende a prever a mobilidade perdida por célula e modo usando chuva, suscetibilidade dos trechos vizinhos, conectividade e redundância de rotas, acesso de base e população. Permite estimar o impacto sem recalcular o roteamento e reestimá-lo quando os dados mudarem. Hoje há só 6 conjuntos distintos de fechamentos; o custo de ~3 min por simulação limita quantas gerar.
- **Validação e incerteza:** os rótulos do modelo 2 vêm da simulação, não da realidade; por isso valida-se deixando de fora um nível de chuva ou uma região (blocos de 2 km), comparando com as regras simples e confrontando o resultado com os dias de bloqueio reais e, quando houver, com GTFS e eventos atualizados. A incerteza vem da sensibilidade ao fator de precariedade da drenagem (1 a 3 vezes os pontos extras).
- **Dashboard e fase 2:** o dashboard cruza a previsão de chuva com os modelos e explica como a IA calcula. Na fase 2, deep learning (U-Net em Sentinel-1) para rotular áreas alagadas e ampliar os eventos.

**Justificativa:** com poucos eventos, sem registros de “chuva sem alagamento” e dados defasados, regras fixas envelhecem rápido; um modelo treinado reaprende com novos dados e mede o quanto supera regras simples. O deep learning só se justifica quando o satélite fornecer rótulos em escala.

**Limitações:** ajuste chuva × bloqueios com 3 datas; GTFS de 2025; bloqueio binário; viés de notificação; sem bocas de lobo; temporais curtos podem fechar vias abaixo de 26 mm; o alerta é nível heurístico, não probabilidade, e cobre só Porto Alegre.
