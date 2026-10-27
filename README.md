# Flooding Mapping

Avaliação de como interdições localizadas associadas a alagamentos pluviais alteram a
acessibilidade a serviços de saúde em Porto Alegre/RS, a pé, de automóvel e de ônibus, e
como afetam a conectividade das redes viária e de pedestres.

**Pergunta:** como interdições localizadas associadas a alagamentos pluviais alteram a
quantidade de destinos de saúde acessíveis em até 30 minutos, e como afetam a conectividade
das redes?

## Escopo e limitações

- **Ônibus:** GTFS oficial da EPTC com vigência set–dez/2025 (vencido; único publicado). Os
  resultados representam a oferta desse período, não o serviço atual. No R5 os ônibus seguem
  a grade do GTFS; o bloqueio de ruas afeta só as caminhadas de acesso, egresso e transferência.
- **Destinos:** estabelecimentos `amenity=hospital|clinic|doctors` do OSM — cobertura
  incompleta e heterogênea (rara na zona sul); não equivale ao CNES.
- **Eventos:** pontos de bloqueio informados pela EPTC (portal da Prefeitura e imprensa). Não
  são um inventário completo. Locais são transcritos e as coordenadas, derivadas no OSM.
- **Zonas:** o buffer (50/100/150 m) é uma zona de busca; não prova que todos os trechos nela
  foram interditados. Trechos ficam como `candidato` até validação humana.
- **Bloqueio:** binário (via livre ou fechada). Bloqueios parciais são registrados, mas não
  simulados. Primeira versão bloqueia o mesmo trecho para todos os modos; há modo `driving`
  para sensibilidade só para automóveis.
- **População:** alocada às células da grade por densidade uniforme dentro de cada setor.
- **ML:** tipologia descritiva (k-means) e protótipo de **suscetibilidade** de segmentos viários
  (positivos = locais de bloqueio informados; demais não rotulados). O modelo ordena trechos por
  semelhança de terreno com locais já interditados; **não prevê alagamento real** e herda o viés
  de notificação. O alerta operacional é determinístico e seu limiar de chuva é provisório.
  Deep Learning (Sentinel-1) é etapa futura.
- **Dashboard de alerta:** mostra **nível de alerta heurístico, não probabilidade**. Limiares de
  chuva calibrados com chuva *modelada* nas datas de bloqueio (limite inferior; a previsão não
  captou o temporal de 06/03/2022). Cobre só Porto Alegre; a localização fica no navegador.
- **Mapas HTML:** o mapa de fundo é embutido (terra dos setores do IBGE menos a água do OSM,
  vias principais do OSM), então abre de `file://` e offline. Os tiles de
  `tile.openstreetmap.org` ficam só como opção no seletor de camadas: o servidor bloqueia
  páginas sem Referer válido ("403 Access blocked"), o caso de arquivos abertos do disco.
  Para usá-los, sirva a pasta: `python -m http.server -d outputs/maps 8000`.

## Fontes de dados e atribuição

| Fonte | Uso | Licença / atribuição |
|---|---|---|
| GTFS EPTC — [dadosabertos.poa.br](https://dadosabertos.poa.br/dataset/gtfs) | Rede de ônibus | Creative Commons Atribuição (portal); © EPTC/Prefeitura de Porto Alegre |
| OpenStreetMap via [Geofabrik](https://download.geofabrik.de/south-america/brazil/sul.html) | Rede viária e destinos | ODbL — © colaboradores do OpenStreetMap |
| IBGE — Censo 2022, malha de setores com agregados | Território e população | Fonte: IBGE, Censo Demográfico 2022 |
| Open-Meteo (previsão e arquivo de previsões) | Chuva prevista e calibração | CC BY 4.0 — Open-Meteo.com |
| Copernicus DEM GLO-30 (AWS Open Data) | Relevo | © DLR e.V. 2010–2014 e © Airbus Defence and Space GmbH 2014–2018, fornecido no âmbito do COPERNICUS pela União Europeia e ESA |
| EPTC / Prefeitura de Porto Alegre; Jornal do Comércio; Sul21 | Eventos de bloqueio | Citados por URL em `data/events/events.csv` |

URLs, hashes SHA-256, tamanhos e datas ficam em `data/raw/manifest.json`. Os dados externos
permanecem sujeitos às suas licenças; o código está sob licença MIT (`LICENSE`).

## Estrutura

```text
config/analysis.yaml        parâmetros (CRS, data/horário, limite, grade, raios, semente)
data/raw/manifest.json      proveniência dos downloads (dados brutos não versionados)
data/events/                events.csv e scenarios.csv (contrato em docs/events_contract.md)
src/flooding_mapping/
  ingest.py                 download atômico + manifesto
  validate.py               vigência efetiva do GTFS
  prepare.py                recorte OSM, grade de origens, população, destinos
  accessibility.py          A0 e A_s com r5py
  network.py                segmentos OSM e PBF derivado por cenário
  scenarios.py              eventos, geocodificação, zonas e trechos candidatos
  metrics.py                perdas L e P
  robustness.py             eficiência e maior componente (NetworkX)
  clustering.py             tipologia k-means
  susceptibility.py         suscetibilidade (DEM + hidrografia) e alerta operacional
  webmap.py                 mapa interativo HTML (Leaflet) com todas as camadas
  rain.py                   calibração dos limiares de chuva (previsões históricas Open-Meteo)
  dashboard.py              dashboard de alerta: localização, previsão ao vivo, nível por trecho
tests/                      pytest com dados sintéticos
reports/qa/                 relatórios de qualidade e registros de execução
outputs/                    tabelas e mapas (não versionados)
```

## Instalação

Requisitos: Python 3.12 (a cadeia r5py/pyrosm não tem wheels para 3.13+), Java 21 (r5py 1.1),
`osmium-tool` e [uv](https://docs.astral.sh/uv/). No macOS:

```bash
brew install openjdk@21 osmium-tool
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
# versões exatas testadas: requirements.lock.txt
export JAVA_HOME=/opt/homebrew/opt/openjdk@21   # obrigatório para o r5py
```

## Execução

```bash
PY=.venv/bin/python
# 1. Downloads (registra no manifesto)
$PY -m flooding_mapping.ingest gtfs --source-date 2025-09-25
$PY -m flooding_mapping.ingest osm
$PY -m flooding_mapping.ingest ibge_setores
# 2. Vigência do GTFS -> reports/qa/gtfs_validation.md (data_referencia em config)
$PY -m flooding_mapping.validate
# 3. Recorte do OSM, origens e destinos
$PY -m flooding_mapping.prepare
# 4. Linha de base A0 (três modos)
$PY -m flooding_mapping.accessibility
# 5. Eventos: geocodificação e trechos candidatos (+ mapa de revisão)
$PY -m flooding_mapping.scenarios geocode
$PY -m flooding_mapping.scenarios candidates --review E20250618-04
# 6. Um cenário: A_s, perdas e robustez
$PY -m flooding_mapping.accessibility --scenarios S-E20250618-04-100-all
$PY -m flooding_mapping.robustness --scenarios S-E20250618-04-100-all
# 7. Perdas consolidadas e mapas de perda
$PY -m flooding_mapping.accessibility --consolidate --maps S-D20250618-100-all
# 8. Mapa interativo (abre no navegador; estado na URL, ex.: #indicador=L&modo=car)
$PY -m flooding_mapping.webmap && open outputs/maps/mapa_interativo.html
# 9. Tipologia (após calcular os cenários)
$PY -m flooding_mapping.clustering
# 10. Suscetibilidade, validação e alerta (chuva prevista em mm/h)
$PY -m flooding_mapping.ingest dem_s30 && $PY -m flooding_mapping.ingest dem_s31
$PY -m flooding_mapping.susceptibility --alert-rain 40
# 11. Limiares de chuva e dashboard de alerta (previsão ao vivo no navegador)
$PY -m flooding_mapping.rain
$PY -m flooding_mapping.dashboard && open outputs/maps/dashboard_alerta.html
```

Testes: `.venv/bin/python -m pytest`.

## Indicadores

- **A0 / A_s:** destinos de saúde alcançáveis em até 30 min (inclusivo), mediana dos tempos
  numa janela de partida de 60 min a partir das 07:00 da data de referência. `status`
  diferencia zero destinos (`ok`), origem sem ligação à rede do modo (`not_linked`) e falha
  (`missing`).
- **L = A0 − A_s** e **P = L / A0** (ausente quando A0 = 0).
- **Eficiência:** média de 1/d (d = caminho mínimo ponderado pelo comprimento) numa amostra
  fixa de pares (semente em config); pares sem caminho contribuem 0. **R_E = E_s / E_0**,
  global e local (nós a até 1 km da zona).
- **Maior componente:** proporção de nós na maior componente (fracamente) conexa.
- **Tipologia:** k-means sobre log(1 + A0) e perda relativa máxima por modo; k por silhueta,
  exigindo ao menos 2% das origens por grupo.
- **Suscetibilidade:** avaliada pelo percentil, na cidade, do segmento mais próximo de cada
  evento retido (aleatório ≈ 0,5), em blocos espaciais de 2 km e no teste temporal (2025).

## Versões relevantes

Python 3.12.13 · Java OpenJDK 21.0.13 · r5py 1.1.7 · GeoPandas 1.1.4 · Pyrosm 0.24.0 ·
NetworkX 3.7 · pyosmium 4.3.2 · osmium-tool 1.19.1 · scikit-learn 1.9.1 · rasterio 1.5.2
