"""Mapa de manchas da propensão topográfica à retenção (dimensão C), pré-renderizado em WebP para a landing.

    PYTHONPATH=src .venv/bin/python tools/gerar_mapa_manchas.py

Dimensão C. Só reaproveita resultados que já existem (altura que o preenchimento de depressões soma ao relevo, por trecho de rua); nada reexecuta o motor.
Fontes do desenho: relevo Copernicus DEM GLO-30 (via o indicador por trecho), ruas e água do OpenStreetMap. Não usa a Profill (as dimensões A e B têm gerador próprio, ``gerar_mapas_dimensoes.py``) nem as coordenadas de alagamentos; os limites de bairros da Prefeitura
entram só como linhas de contexto (base_legal_dados.md). Cada mancha é o MÁXIMO da altura entre os trechos que caem
em uma célula de 100 m; escuro = depressão mais profunda estimada, o que não é ocorrência nem risco de alagamento.
Escreve: static/inicio/img/estudo/mapa-propensao.webp e static/data/mapa_manchas_poa.json (números e faixas da legenda, usados pela landing e conferidos por teste).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manchas_base import Quadro, carregar_agua, carregar_bairros, carregar_rede, desenhar  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
ESTATICO = RAIZ / "src/flooding_mapping/app/static"
IMG = ESTATICO / "inicio/img/estudo/mapa-propensao.webp"
DADOS = ESTATICO / "data/mapa_manchas_poa.json"
CELULA_M = 100                                                # igual a manchas_base.CELULA_M
FAIXAS_M = [0.0, 0.5, 1.0, 2.0, 1e9]                          # limites da legenda, em metros
CORES = ["#f1d9a8", "#dfa356", "#b3622a", "#6a2a12"]          # claro a escuro (tons de terra, como o indicador topográfico do mapa interativo)


def estatisticas(t: pd.DataFrame) -> dict:
    a = t["altura_de_preenchimento_max_m"]
    com_dado, pos = a.dropna(), a[a > 0]
    return {"trechos_total": int(len(t)), "trechos_com_dado_de_relevo": int(len(com_dado)), "trechos_sem_dado_de_relevo": int(a.isna().sum()),
            "cobertura_de_dado_pct": round(100 * len(com_dado) / len(t), 1), "trechos_com_depressao": int(len(pos)), "trechos_com_depressao_pct": round(100 * len(pos) / len(t), 1),
            "altura_mediana_m": round(float(pos.median()), 2), "altura_p90_m": round(float(pos.quantile(0.9)), 2), "altura_p99_m": round(float(pos.quantile(0.99)), 2),
            "altura_maxima_m": round(float(pos.max()), 2), "trechos_acima_de_8_m": int((pos > 8).sum())}


def main() -> None:
    t = pd.read_parquet(RAIZ / "data/processed/fase3/trechos_nivel1_propensao_topografica.parquet")
    rede = carregar_rede()
    q = Quadro(rede)
    h = q.valores_por_trecho(t, "altura_de_preenchimento_max_m")
    w, h_px = desenhar(q, q.grade_maximo(h), FAIXAS_M, CORES, ~np.isfinite(h), carregar_agua(), carregar_bairros(), IMG, "Relevo: Copernicus DEM GLO-30")
    h = h_px
    r = {"variavel": "altura que o preenchimento de depressões soma ao relevo (propensão topográfica à retenção, dimensão C), por trecho",
         "fontes": "Copernicus DEM GLO-30 (relevo), OpenStreetMap (ruas e água) e limites de bairros da Prefeitura de Porto Alegre (linhas de contexto). Esta dimensão não usa a Profill nem registros de alagamento",
         "imagem": {"arquivo": "img/estudo/mapa-propensao.webp", "largura_px": w, "altura_px": h, "bytes": IMG.stat().st_size, "celula_m": CELULA_M, "agregacao": "máximo entre os trechos de cada célula"},
         "faixas_m": [{"de": 0.0, "ate": 0.5, "cor": CORES[0]}, {"de": 0.5, "ate": 1.0, "cor": CORES[1]}, {"de": 1.0, "ate": 2.0, "cor": CORES[2]}, {"de": 2.0, "ate": None, "cor": CORES[3]}],
         **estatisticas(t)}
    DADOS.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"gravado: {IMG.name} {w}x{h}, {IMG.stat().st_size / 1024:.0f} KB; {DADOS.name}")


if __name__ == "__main__":
    main()
