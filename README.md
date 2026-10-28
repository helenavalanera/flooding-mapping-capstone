# Flooding Mapping

Alagamentos pluviais fecham cruzamentos e trechos de vias em Porto Alegre várias vezes por ano.
O projeto mede **quanto da mobilidade urbana — a pé, de ônibus e de carro — deixa de ser
alcançável com até 45 mm de chuva em 24 horas**, diante das condições precárias de drenagem da
cidade, quando trechos documentados são interditados.

**Pergunta:** com chuvas de até 45 mm em 24 h, quanto da cidade (população alcançável em até
30 minutos) cada pessoa perde, a pé, de ônibus e de carro, quando os trechos documentados e os
mais propensos a alagar são interditados? Complementa-se com a perda de conectividade das redes
viária e de pedestres.

**Por que importa:** o menor acumulado que já coincidiu com bloqueios registrados (~26 mm em
24 h) ocorre em média **14 dias por ano** em Porto Alegre (`reports/qa/rain_frequency.json`):
chuvas comuns, não extremas, já desorganizam o deslocamento e o acesso a tudo na cidade.

**Como a chuva vira bloqueio:** abaixo do menor acumulado em que a EPTC já registrou bloqueio
(limiar calibrado em `reports/qa/rain_calibration.json`), nada fecha; a partir dele, fecham os
pontos documentados de bloqueio total e mais N pontos apontados pelo modelo de suscetibilidade,
com N vindo de um ajuste linear entre chuva acumulada e número de bloqueios registrados por data,
multiplicado por um fator de precariedade (1 = condição observada).

## Escopo e limitações

- **Ônibus:** GTFS oficial da EPTC com vigência set–dez/2025 (vencido; único publicado). Os
  resultados representam a oferta desse período, não o serviço atual. No R5 os ônibus seguem
  a grade do GTFS; o bloqueio de ruas afeta só as caminhadas de acesso, egresso e transferência.
- **Medida de mobilidade:** destinos = células da grade com população; cada origem "alcança"
  a população das células a até 30 min. Representa o acesso à cidade como um todo (pessoas,
  trabalho, serviços e comércio onde as pessoas estão), não a um tipo de destino.
- **Chuva → bloqueio:** regra explícita e configurável (`mobility` em `config/analysis.yaml`);
  o ajuste chuva × número de bloqueios usa só 3 datas e é provisório. Abaixo de ~26 mm em 24 h
  nenhum bloqueio é atribuído, embora temporais curtos possam fechar vias com acumulados menores
  (06/03/2022).
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
- **Mapa de fundo CARTO (opcional):** com uma chave, o CARTO Voyager vira o fundo padrão.
  Informe a chave **fora do git**, por uma das opções abaixo, e gere os HTML de novo:

  ```bash
  export CARTO_API_KEY="sua-chave"                 # opção 1: só nesta sessão do terminal
  printf '%s' "sua-chave" > config/carto_api_key.txt   # opção 2: arquivo local (no .gitignore)
  $PY -m flooding_mapping.webmap && $PY -m flooding_mapping.dashboard
  ```

  A chave fica **embutida nos HTML gerados** (tiles são pedidos pelo navegador): não publique
  esses arquivos sem restringir a chave a domínios no painel do CARTO. Uma restrição por
  domínio pode bloquear páginas abertas via `file://`, que não enviam Referer.

## Fontes de dados e atribuição

| Fonte | Uso | Licença / atribuição |
|---|---|---|
| GTFS EPTC — [dadosabertos.poa.br](https://dadosabertos.poa.br/dataset/gtfs) | Rede de ônibus | Creative Commons Atribuição (portal); © EPTC/Prefeitura de Porto Alegre |
| OpenStreetMap via [Geofabrik](https://download.geofabrik.de/south-america/brazil/sul.html) | Rede viária e drenagem | ODbL — © colaboradores do OpenStreetMap |
| IBGE — Censo 2022, malha de setores com agregados | Território e população | Fonte: IBGE, Censo Demográfico 2022 |
| Open-Meteo (previsão, arquivo de previsões e reanálise) | Chuva prevista, calibração e frequência | CC BY 4.0 — Open-Meteo.com |
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
  prepare.py                recorte OSM, grade de origens com população
  accessibility.py          cidade alcançável (A0 e A_s) com r5py
  network.py                segmentos OSM e PBF derivado por cenário
  scenarios.py              eventos, geocodificação, zonas e trechos candidatos
  metrics.py                perdas L e P e mobilidade perdida
  mobility.py               escala de chuva, cidade alcançável e mobilidade perdida
  robustness.py             eficiência e maior componente (NetworkX)
  clustering.py             tipologia k-means
  susceptibility.py         suscetibilidade (DEM + hidrografia) e alerta operacional
  webmap.py                 mapa interativo HTML (Leaflet) com todas as camadas
  rain.py                   limiares de chuva calibrados e frequência anual das chuvas
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
# 1. Downloads (registram no manifesto)
$PY -m flooding_mapping.ingest gtfs --source-date 2025-09-25
$PY -m flooding_mapping.ingest osm
$PY -m flooding_mapping.ingest ibge_setores
$PY -m flooding_mapping.ingest dem_s30 && $PY -m flooding_mapping.ingest dem_s31
# 2. Vigência do GTFS -> reports/qa/gtfs_validation.md (data_referencia em config)
$PY -m flooding_mapping.validate
# 3. Recorte do OSM e grade de origens com população
$PY -m flooding_mapping.prepare
# 4. Eventos: geocodificação e trechos candidatos (+ mapa de revisão)
$PY -m flooding_mapping.scenarios geocode
$PY -m flooding_mapping.scenarios candidates --review E20250618-04
# 5. Suscetibilidade dos trechos (modelo e validação)
$PY -m flooding_mapping.susceptibility
# 6. Chuva: limiares calibrados e frequência anual
$PY -m flooding_mapping.rain
# 7. Cidade alcançável sem chuva (A0) e mobilidade perdida na escala de chuva (até 45 mm/24h)
$PY -m flooding_mapping.accessibility
$PY -m flooding_mapping.mobility
# 8. Robustez das redes (exemplo: um bloqueio documentado)
$PY -m flooding_mapping.robustness --scenarios S-E20250618-04-100-all
# 9. Tipologia das áreas (k-means)
$PY -m flooding_mapping.clustering
# 10. Mapa interativo e dashboard de alerta
$PY -m flooding_mapping.webmap && open outputs/maps/mapa_interativo.html
$PY -m flooding_mapping.dashboard && open outputs/maps/dashboard_alerta.html
```

Testes: `.venv/bin/python -m pytest`.

## Indicadores

- **A0 / A_s:** população da cidade alcançável em até 30 min (inclusivo) a partir de cada origem,
  sem chuva e no cenário de chuva; mediana dos tempos numa janela de partida de 60 min a partir
  das 07:00 da data de referência. `status` diferencia `ok`, origem sem ligação à rede do modo
  (`not_linked`) e falha (`missing`).
- **L = A0 − A_s** (pessoas que deixam de ser alcançáveis) e **P = L / A0**.
- **Mobilidade perdida** (por modo e nível de chuva): 1 − Σ pop·A_s / Σ pop·A0, ou seja, a parte
  de todos os deslocamentos possíveis em 30 min que a chuva elimina. **Instabilidade local:**
  maior P entre as origens e população das células que perdem pelo menos 10% da cidade.
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
