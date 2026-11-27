"""Recorte municipal: os números por trecho que a landing mostra, só para as ruas DENTRO de Porto Alegre.

    PYTHONPATH=src .venv/bin/python tools/gerar_recorte_municipal.py

A malha de ruas do estudo (176.836 trechos do OpenStreetMap) vem de uma caixa em volta de Porto Alegre e inclui vias de cidades vizinhas, onde o uso do solo da Prefeitura
não existe. Este recorte NÃO muda o motor nem os parquets: define o universo de apresentação (trecho com ponto médio dentro do polígono do município) e recalcula, a partir
dos mesmos parquets e com as mesmas definições, os números por trecho. Para conferir o método, o mesmo cálculo SEM recorte reproduz os valores já publicados em
reports/qa/fase3_execucao.json (campo ``sem_recorte`` no JSON). Escreve static/data/recorte_municipal_poa.json. Critério documentado em docs/recorte_municipal.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manchas_base import RAIZ, Quadro, carregar_rede  # noqa: E402

SAIDA = RAIZ / "src/flooding_mapping/app/static/data/recorte_municipal_poa.json"
F3 = RAIZ / "data/processed/fase3"


def calcular(q: Quadro, mascara: np.ndarray, base: pd.DataFrame, topo: pd.DataFrame, n2: pd.DataFrame, bocas_ate_50m: pd.Series) -> dict:
    ids = set(q.ids[mascara])
    b = base[base["segmento_id"].isin(ids)]
    com = b[b["n_celulas_com_dados"] > 0]
    t = topo[topo["segmento_id"].isin(ids)]
    tv = t[t["altura_de_preenchimento_max_m"].notna()]
    c = n2[n2["segmento_id"].isin(set(com["segmento_id"]))]["contrib_potencial_max_m3"]
    qu = pd.qcut(com["contrib_aeq_m1_max_m2"].rank(method="first"), 5, labels=False)
    perto = bocas_ate_50m.reindex(com["segmento_id"]).to_numpy()
    return {"trechos": int(len(b)), "com_dados": int(len(com)), "sem_dado": int(len(b) - len(com)),
            "montante_coberta_m1_mediana": round(float(com["fracao_montante_coberta_m1"].median()), 4),
            "contrib_m1_max_30mm_m3": {"q50": round(float(c.quantile(.5)), 1), "q90": round(float(c.quantile(.9)), 1), "q99": round(float(c.quantile(.99)), 1)},
            "preenchimento": {"com_valor": int(len(tv)), "zero": int((tv["altura_de_preenchimento_max_m"] == 0).sum()), "positivo": int((tv["altura_de_preenchimento_max_m"] > 0).sum())},
            "boca_de_lobo_ate_50m_por_quintil_de_contribuicao_pct": [round(100 * float(perto[(qu == k).to_numpy()].mean()), 1) for k in range(5)]}


def main() -> None:
    import geopandas as gpd
    import shapely

    q = Quadro(carregar_rede())
    base = pd.read_parquet(F3 / "trechos_contribuicao_base.parquet", columns=["segmento_id", "n_celulas_com_dados", "fracao_montante_coberta_m1", "contrib_aeq_m1_max_m2"])
    topo = pd.read_parquet(F3 / "trechos_nivel1_propensao_topografica.parquet", columns=["segmento_id", "altura_de_preenchimento_max_m"])
    n2 = pd.read_parquet(F3 / "trechos_nivel2_cenarios.parquet")
    n2 = n2[(n2.p_mm == 30) & (n2.pacote == "metodo1")]
    bocas = gpd.read_parquet(RAIZ / "data/processed/drenagem/bocas_de_lobo.parquet")
    bocas = bocas[bocas["usar_no_inventario"]] if "usar_no_inventario" in bocas else bocas
    linhas = shapely.linestrings(np.stack([np.c_[q.x0, q.y0], np.c_[q.x1, q.y1]], axis=1))
    arv = shapely.STRtree(bocas.to_crs("EPSG:31982").geometry.values)
    perto = np.zeros(len(linhas), dtype=bool)
    idx = arv.query(shapely.buffer(linhas, 50), predicate="intersects")
    perto[np.unique(idx[0])] = True
    perto = pd.Series(perto, index=q.ids)
    dentro = q.no_municipio()
    r = {"criterio": "ponto médio do trecho dentro do polígono do município (data/processed/municipality.parquet, 495,0 km²)", "trechos_na_malha": int(len(q.ids)),
         "trechos_no_municipio": int(dentro.sum()), "trechos_fora_do_municipio": int((~dentro).sum()),
         "no_municipio": calcular(q, dentro, base, topo, n2, perto), "sem_recorte": calcular(q, np.ones(len(dentro), dtype=bool), base, topo, n2, perto)}
    SAIDA.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("trechos_na_malha", "trechos_no_municipio", "trechos_fora_do_municipio")}), "\n dentro:", r["no_municipio"], "\n sem recorte:", r["sem_recorte"])


if __name__ == "__main__":
    main()
