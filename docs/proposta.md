# Proposta de Projeto Final — Future Tech Leaders Brasil · Space Tech Bootcamp 2026

**Projeto:** Flooding Mapping — interdições por alagamento pluvial e acesso à saúde em Porto Alegre
**Candidata:** Helena de Oliveira Valanera — helena.valanera@gmail.com
**Repositório:** https://github.com/helenavalanera/flooding-mapping-capstone

## 1. Ideia do projeto

Alagamentos pluviais fecham cruzamentos e trechos de vias em Porto Alegre várias vezes por ano.
O projeto mede **quantos serviços de saúde deixam de ser alcançáveis em até 30 minutos — a pé,
de carro e de ônibus — quando trechos documentados são interditados**, quanto essas interdições
reduzem a conectividade das redes e **quais trechos têm perfil de terreno semelhante aos já
interditados**, alimentando um alerta operacional a partir da chuva prevista. Produto final:
**cartografia** de acessibilidade, de perda e de suscetibilidade, com componente de ML.

## 2. Relevância para os ODS e para o ecossistema geoespacial

**ODS 3 (3.8)** acesso a serviços de saúde; **ODS 11 (11.2, 11.5)** transporte e redução de
impactos de desastres; **ODS 13 (13.1)** resiliência climática; **ODS 9 (9.1)** infraestrutura
resiliente. Aplicação prática: priorizar drenagem e desvios onde a perda de acesso é maior e
antecipar linhas de ônibus e serviços expostos em dias de chuva forte. Usa só dados abertos
(OSM, GTFS, IBGE, Copernicus DEM) e é replicável; a fase 2 incorpora imagens de satélite.

## 3. Exemplos de literatura

1. Coles et al. (2017). Beyond “flood hotspots”: modelling emergency service accessibility
   during flooding in York, UK. *J. Hydrology* 546:419–436. doi:10.1016/j.jhydrol.2016.12.013
2. Green et al. (2017). City-scale accessibility of emergency responders operating during flood
   events. *NHESS* 17:1–16. doi:10.5194/nhess-17-1-2017 — alagamento superficial perturba mais
   o acesso que cheias fluviais de magnitude similar.
3. Pregnolato et al. (2017). The impact of flooding on road transport: a depth-disruption
   function. *Transp. Res. D* 55:67–81. doi:10.1016/j.trd.2017.06.020
4. Latora & Marchiori (2001). Efficient behavior of small-world networks. *Phys. Rev. Lett.*
   87:198701. doi:10.1103/PhysRevLett.87.198701
5. Fink et al. (2022). r5py: Rapid Realistic Routing with R5 in Python. doi:10.5281/zenodo.7060437

## 4. Dados

| Dado | Fonte / formato | Pré-processamento |
|---|---|---|
| Ônibus | GTFS EPTC, portal de dados abertos (ZIP/CSV) | Vigência efetiva set–dez/2025 (feed vencido, único publicado): referência histórica, dia 30/10/2025; MobilityData Validator sem erros |
| Vias e destinos | OpenStreetMap/Geofabrik, 24/10/2026 (PBF) | Recorte municipal +3 km; 176.836 segmentos; 181 serviços de saúde |
| População | IBGE, Censo 2022, setores com agregados (GPKG) | Grade de 1 km, densidade uniforme por setor, total conservado (1.332.845) |
| Relevo | Copernicus DEM GLO-30 (GeoTIFF) | Mosaico reprojetado a 30 m; elevação relativa e declividade |
| Interdições | EPTC/Prefeitura e imprensa citando a EPTC (CSV curado) | 24 bloqueios em 4 datas (2019–2025), 19 geocodificados por interseção de vias no OSM |

## 5. Metodologia (ML preditivo + não supervisionado; DL na fase 2)

1. **Acessibilidade (r5py):** destinos alcançáveis em ≤ 30 min por origem e modo (A0); em cada
   cenário, os segmentos que cruzam zonas de 50/100/150 m em torno do bloqueio são removidos e
   A_s recalculada. Perdas L = A0 − A_s e P = L/A0. **Robustez** (NetworkX): eficiência global e
   local e maior componente conexa.
2. **ML preditivo — suscetibilidade:** regressão logística regularizada e random forest
   classificam segmentos viários pela semelhança com locais já interditados (positivos e não
   rotulados), com variáveis de relevo e hidrografia; validação espacial em blocos de 2 km e
   temporal (treino 2019–2022, teste 2025), contra regras de referência.
3. **Dashboard de alerta (determinístico):** a partir da localização do usuário e da previsão
   horária de chuva (Open-Meteo), atribui nível de alerta (médio/alto) aos trechos mais suscetíveis
   e lista linhas de ônibus e serviços de saúde expostos. Limiares calibrados com a chuva prevista
   nas datas de bloqueio (≥ 3,5 mm/h ou 26 mm/24 h: médio; ≥ 9 mm/h ou 56 mm/24 h: alto).
4. **ML não supervisionado:** k-means (k por silhueta) sobre acesso de base e perda máxima.
5. **Fase 2 — Deep Learning:** segmentação de áreas alagadas em Sentinel-1 (U-Net) para rotular
   eventos e ampliar a base de treino.

Escolha justificada pelos dados: há poucos eventos e nenhum registro de “chuva sem alagamento”,
então o modelo supervisionado é tratado como problema de positivos e não rotulados e comparado a
regras simples; DL só se justifica com rótulos em escala, o que o satélite pode prover.

**Resultados iniciais** (trechos ainda não validados por revisão humana):

- **A0:** média de 1,9 destinos a pé, 14,0 de ônibus e 100,2 de carro; 360, 297 e 29 das 563
  origens não alcançam nenhum destino em 30 min, respectivamente.
- **Interdição de 100 m em Dona Teodora × A. J. Renner** (bloqueio total em 2024 e 2025): 2
  origens perdem 83% do acesso a pé; 4 perdem acesso de ônibus; 5 de carro. Eficiência local
  da rede cai 17% (pedestres) e 8% (viária); a global, menos de 0,5%.
- **Bloqueios simultâneos de 18/06/2025 (100 m):** 153 origens perdem acesso de carro
  (≈ 374 mil pessoas estimadas nessas células).
- **Suscetibilidade:** os locais interditados estão em áreas baixas — a regra “elevação baixa”
  posiciona o evento típico no percentil 80 (espacial) e 85 (temporal); a logística atinge 73 e
  79 e o random forest sobreajusta. Com 17 locais, o ML ainda não supera a regra simples.
- **k-means:** dois grupos (centro com acesso alto; periferia com acesso baixo a pé e de
  ônibus); as perdas, muito localizadas, não diferenciam tipologias.

**Limitações:** destinos do OSM incompletos; GTFS de 2025; bloqueio binário; ônibus seguem a
grade do GTFS (o bloqueio afeta a caminhada de acesso); eventos não formam inventário completo
e refletem viés de notificação; DEM de superfície a 30 m; limiar de chuva e corte do alerta
calibrado só com chuva modelada (a previsão não captou o temporal de 06/03/2022); o alerta é
nível heurístico, não probabilidade, e cobre só Porto Alegre.
