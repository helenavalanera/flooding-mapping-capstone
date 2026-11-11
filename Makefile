# Pipeline completo:   make
# Uma etapa só:        make chuva   (veja `make help`)
# Outro Python:        make PY=python

PY ?= .venv/bin/python
M  := $(PY) -m flooding_mapping

.PHONY: all help downloads validar preparar cenarios suscetibilidade chuva \
        mobilidade robustez tipologia mapas criticidade abrir test coletar \
        estado-dados estado-chuva estado-modelo estado-avaliacao estado-site estado rede servir demo

all: downloads validar preparar cenarios suscetibilidade chuva mobilidade \
     robustez tipologia mapas  ## roda as etapas 1 a 10 em ordem

help:  ## lista as etapas
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

downloads:  ## 1. GTFS, OSM, setores IBGE e MDT (reaproveita o que já existe)
	$(M).ingest gtfs --source-date 2025-09-25
	$(M).ingest osm
	$(M).ingest ibge_setores
	$(M).ingest dem_s30
	$(M).ingest dem_s31

validar:  ## 2. vigência do GTFS -> reports/qa/gtfs_validation.md
	$(M).validate

preparar:  ## 3. recorte do OSM e grade de origens com população
	$(M).prepare

cenarios:  ## 4. geocodificação dos eventos e trechos candidatos
	$(M).scenarios geocode
	$(M).scenarios candidates --review E20250618-04

suscetibilidade:  ## 5. modelo de suscetibilidade dos trechos
	$(M).susceptibility

chuva:  ## 6. limiares calibrados e frequência anual
	$(M).rain

mobilidade:  ## 7. linha de base A0 e mobilidade perdida até 45 mm/24h
	$(M).accessibility
	$(M).mobility

robustez:  ## 8. robustez das redes (um bloqueio documentado)
	$(M).robustness --scenarios S-E20250618-04-100-all

tipologia:  ## 9. tipologia das áreas (k-means)
	$(M).clustering

mapas:  ## 10. mapa interativo e dashboard de alerta
	$(M).webmap
	$(M).dashboard

criticidade:  ## extra: ranking de trechos críticos -> outputs/web
	$(M).criticality screen
	$(M).criticality simulate
	$(M).criticality export

abrir:  ## abre o mapa e o dashboard no navegador
	open outputs/maps/mapa_interativo.html outputs/maps/dashboard_alerta.html

test:  ## roda os testes
	$(PY) -m pytest -q

coletar:  ## testa o coletor da CRBM sem gravar nada (não precisa de R2)
	$(M).collector --dry-run

# --- Escopo estadual (RS): dados -> chuva -> modelo -> avaliação -> site -------------------
estado-dados:  ## municípios, S2iD, malha DAER, segmentos de 1 km, impacto simulado e camadas
	$(M).ingestion.municipios
	$(M).ingestion.s2id build
	$(M).ingestion.daer build
	$(M).geospatial.segments
	$(M).geospatial.impact
	$(M).app.layers

estado-chuva:  ## chuva diária por município (Open-Meteo; retoma de onde parou, respeita a cota)
	$(M).ingestion.weather

estado-modelo:  ## treina e valida o gatilho municipal (rótulos estrito e amplo)
	$(M).models.gatilho --label estrito
	$(M).models.gatilho --label amplo

estado-avaliacao:  ## perda ao operar com previsão em vez de reanálise
	$(M).evaluation.skew --label estrito

estado-site:  ## monta o site local em site/ com o modelo mais recente (abre com: python -m http.server -d site)
	$(M).app.build --model $$(ls -t artifacts/models/gatilho-estrito-*/modelo.joblib | head -1) --card reports/ml/gatilho_estrito.json --out site

estado: estado-dados estado-chuva estado-modelo estado-avaliacao  ## fluxo estadual completo (sem publicar)

rede:  ## tabela de ruas de Porto Alegre para o servidor (data/processed/rede_poa.parquet)
	$(M).rede_poa

servir:  ## dashboard, PWA (/pwa/) e API em http://127.0.0.1:8000
	$(M).servidor

demo:  ## demonstração controlada (dados SINTÉTICOS em memória): painel em :8766 e PWA em :8766/pwa/
	$(PY) -W ignore tests/e2e/servidor_demo.py --porta 8766 --avisar
