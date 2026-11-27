#!/usr/bin/env bash
# Gera o mapa-base do RS (Protomaps, derivado do OpenStreetMap) como um único arquivo PMTiles, só com a caixa do estado.
# O build do Protomaps é lido por faixas de bytes (o planeta tem ~140 GB, mas só ~220 MB são baixados). Requer o CLI: brew install pmtiles
#
#   tools/gerar_mapa_base.sh [AAAAMMDD]        # padrão: o build abaixo; o resultado fica em data/raw/basemap/rs.pmtiles (fora do Git)
#
# Depois de gerar: shasum -a 256 data/raw/basemap/rs.pmtiles, enviar o arquivo ao R2 e atualizar VERSAO_ARQUIVO em
# src/flooding_mapping/app/static/mapa-base.js (é a chave do cache offline do PWA). Ver docs/mapa_base.md.
set -euo pipefail
BUILD="${1:-20261115}"
DESTINO="$(cd "$(dirname "$0")/.." && pwd)/data/raw/basemap/rs.pmtiles"
mkdir -p "$(dirname "$DESTINO")"
pmtiles extract "https://build.protomaps.com/${BUILD}.pmtiles" "$DESTINO" --bbox=-57.7,-33.8,-49.6,-27.0 --maxzoom=14
pmtiles show "$DESTINO" | head -8
shasum -a 256 "$DESTINO"
