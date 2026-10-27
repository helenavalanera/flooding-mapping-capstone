# Contrato de dados: eventos e cenários

## `data/events/events.csv`

Um registro por ponto de interdição observado (um mesmo temporal gera vários eventos).

| Campo | Descrição |
|---|---|
| `event_id` | `E<AAAAMMDD>-<nn>`, único |
| `event_date` | Data do registro (AAAA-MM-DD) |
| `event_type` | Ex.: `bloqueio_total_acumulo_agua` |
| `location_text` | Local **transcrito literalmente** da fonte |
| `osm_street_a`, `osm_street_b` | Nomes exatos das vias no OSM, resolvidos manualmente; alternativas separadas por `\|`. Para o método de marco, `osm_street_b` é o nome do marco |
| `geocode_method` | `osm_intersection`, `osm_segment_between`, `osm_street_midpoint`, `osm_street_nearest_landmark` ou `pendente` |
| `latitude`, `longitude` | WGS84, **derivadas** por `python -m flooding_mapping.scenarios`; vazias se pendentes ou não resolvidas |
| `source_name`, `source_url`, `source_url_2` | Origem da informação e URLs consultadas |
| `accessed_on` | Data de acesso às fontes |
| `confidence` | `alta`, `media` ou `baixa` (critérios abaixo) |
| `description` | Interpretações, ressalvas e recorrência |
| `verification_status` | `observado_fonte_secundaria` (imprensa citando a EPTC), `observado_fonte_oficial` ou `sintetico` |

### Regras de geocodificação

- `osm_intersection`: centroide dos nós OSM compartilhados pelas duas vias; recusado se os
  nós distarem mais de 150 m entre si (casamento ambíguo).
- `osm_segment_between`: trecho “entre B e C” (`osm_street_b` = `B;C`); ponto da via mais próximo
  do meio entre os dois cruzamentos.
- `osm_street_midpoint`: ponto médio do maior trecho contínuo da via (a fonte não indica trecho).
- `osm_street_nearest_landmark`: ponto da via mais próximo do marco, recusado se a via
  estiver a mais de 300 m dele.
- Endereços por número de porta não são geocodificados.
- Bloqueios parciais (`bloqueio_parcial_acumulo_agua`) são registrados, mas o roteamento só
  representa bloqueio total; parciais não entram como bloqueio nos cenários principais.
- Ficam fora: pontos “em atenção sem bloqueio”, comunicados só com contagens e cheias do
  Guaíba (inundação fluvial, ex.: 27/09/2023 e maio/2024).

### Confiança

- **alta**: ponto listado pela EPTC e local inequívoco (cruzamento nomeado).
- **media**: local interpretado (trecho reduzido a um ponto, nome divergente do OSM).
- **baixa**: local impreciso ou não confirmado nos dados.

Notícias reproduzindo listas da EPTC **não são um inventário completo** de ocorrências:
registram o que foi informado em certo horário.

## `data/events/scenarios.csv`

Um registro por cenário (evento × raio × rede), preenchido após revisão humana.

| Campo | Descrição |
|---|---|
| `scenario_id` | `S-<event_id>-<raio>-<rede>` |
| `event_id` | Evento de origem (ou id sintético) |
| `radius_m` | 50, 100 ou 150 |
| `network_type` | `driving`, `walking` ou `all` |
| `affected_edge_ids` | Ids das arestas bloqueadas, separados por `;` |
| `validation_status` | `candidato`, `validado`, `hipotetico` ou `limite_superior` |
| `validated_by`, `validation_date` | Quem validou os trechos e quando |
| `notes` | Critério de seleção e observações |

O buffer define uma **zona de busca**: não prova que todas as arestas nela foram interditadas.
