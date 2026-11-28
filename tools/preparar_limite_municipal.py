"""Limite do município de Porto Alegre para o mapa interativo: um GeoJSON simplificado (cerca de 11 m de tolerância), usado só para sombrear o que está fora do município e para
avisar, no clique, que o trecho é de uma cidade vizinha. NÃO muda nenhum dado nem resultado.

    PYTHONPATH=src .venv/bin/python tools/preparar_limite_municipal.py

Fonte: data/processed/municipality.parquet, a união dos setores censitários do IBGE (Censo 2022) do município, a mesma que define o recorte municipal (docs/recorte_municipal.md).
Escreve src/flooding_mapping/app/static/data/limite_poa.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import shapely

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "src/flooding_mapping/app/static/data/limite_poa.json"
TOLERANCIA_GRAUS = 0.0001   # cerca de 11 m


def arredonda(coords, casas=5):
    return [arredonda(c, casas) for c in coords] if isinstance(coords[0], (list, tuple)) else [round(coords[0], casas), round(coords[1], casas)]


def main() -> None:
    g = gpd.read_parquet(RAIZ / "data/processed/municipality.parquet")
    area_km2 = round(float(g.to_crs("EPSG:31982").area.sum() / 1e6), 1)
    poligono = g.to_crs("EPSG:4326").geometry.union_all()
    simples = shapely.simplify(poligono, TOLERANCIA_GRAUS, preserve_topology=True)
    geom = shapely.geometry.mapping(simples)
    geom = {"type": geom["type"], "coordinates": arredonda(list(geom["coordinates"]))}
    razao = float(shapely.area(simples) / shapely.area(poligono))
    rec = json.loads((SAIDA.parent / "recorte_municipal_poa.json").read_text(encoding="utf-8"))      # contagens oficiais do recorte (tools/gerar_recorte_municipal.py)
    out = {"type": "Feature", "properties": {"nome": "Porto Alegre", "trechos_malha": rec["trechos_na_malha"], "trechos_dentro": rec["trechos_no_municipio"], "trechos_fora": rec["trechos_fora_do_municipio"], "area_km2": area_km2, "fonte": "união dos setores censitários do IBGE (Censo 2022), data/processed/municipality.parquet",
                                             "simplificacao_graus": TOLERANCIA_GRAUS, "razao_de_area_apos_simplificar": round(razao, 5), "uso": "sombrear o que está fora do município e avisar no clique; não altera dados nem resultados"}, "geometry": geom}
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"gravado: {SAIDA.name}, {SAIDA.stat().st_size / 1024:.0f} KB, área {area_km2} km², razão de área {razao:.5f}")


if __name__ == "__main__":
    main()
