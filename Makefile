# Pipeline completo:   make
# Uma etapa só:        make chuva   (veja `make help`)
# Outro Python:        make PY=python

PY ?= .venv/bin/python
M  := $(PY) -m flooding_mapping

.PHONY: all help downloads validar preparar cenarios suscetibilidade chuva \
        mobilidade robustez tipologia mapas criticidade abrir test coletar

all: downloads validar preparar cenarios suscetibilidade chuva mobilidade \
     robustez tipologia mapas  ## roda as etapas 1 a 10 em ordem

help:  ## lista as etapas
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

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
