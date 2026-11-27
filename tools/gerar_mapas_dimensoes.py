"""Mapas de manchas pré-renderizados das dimensões A (geração), B (concentração) e D (drenagem cadastrada), em WebP, e os números que a landing mostra.

    PYTHONPATH=src .venv/bin/python tools/gerar_mapas_dimensoes.py [--so A B D]

A dimensão C (propensão topográfica) tem gerador próprio: ``gerar_mapa_manchas.py``. Aqui só se reaproveitam resultados que já existem (Fase 3: Profill, coeficientes de
escoamento, DEM, OSM; cadastro de drenagem da Prefeitura); nada reexecuta o motor. A chuva é a de referência de 30 mm (percentil 75 dos totais por evento, 2017 a 2026) e o
pacote é o Método 1 (coeficientes fundamentados), no limite superior do intervalo, o mesmo critério dos resultados por bairro. Valores em m³ de escoamento POTENCIAL de um
evento de 30 mm: não são vazão, nem profundidade, nem alagamento. Escreve static/inicio/img/estudo/mapa-<dimensao>.webp e static/data/mapa_dimensoes_poa.json.
Base legal e origem dos dados: docs/base_legal_dados.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manchas_base import IMG_DIR, RAIZ, Quadro, carregar_agua, carregar_bairros, carregar_rede, desenhar  # noqa: E402

DADOS = RAIZ / "src/flooding_mapping/app/static/data/mapa_dimensoes_poa.json"
RESULTADOS = RAIZ / "src/flooding_mapping/app/static/data/resultados_poa.json"
P_MM = 30
MAX = 1e12
# Paletas distintas por dimensão (claro a escuro); a C usa tons de terra no seu gerador
CONFIG = {
    "A": {"arquivo": "mapa-geracao.webp", "bordas": [0, 10, 20, 40, 80, MAX], "cores": ["#f7d6e6", "#eca3c8", "#d95f9f", "#a8266f", "#5e0f45"], "unidade": "m³ de escoamento potencial gerado, por trecho, em um evento de 30 mm",
          "fonte": "Escoamento potencial (Método 1): uso do solo Profill 2022, Prefeitura de Porto Alegre"},
    "B": {"arquivo": "mapa-concentracao.webp", "bordas": [0, 10, 100, 1000, 10000, MAX], "cores": ["#dcd9f2", "#b3aee0", "#857bc7", "#5547a3", "#2d2166"], "unidade": "m³ de escoamento potencial que converge ao trecho, em um evento de 30 mm",
          "fonte": "Escoamento potencial (Método 1): Profill 2022, Copernicus DEM"},
}


def pt(x: float, casas: int = 0) -> str:
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rotulos(bordas: list[float]) -> list[str]:
    r = [f"{pt(a)} a {pt(b)} m³" for a, b in zip(bordas[1:-2], bordas[2:-1])]
    return [f"mais de 0 até {pt(bordas[1])} m³", *r, f"mais de {pt(bordas[-2])} m³"]


def base_30mm() -> pd.DataFrame:
    n = pd.read_parquet(RAIZ / "data/processed/fase3/trechos_nivel2_cenarios.parquet")
    n = n[(n.p_mm == P_MM) & (n.pacote == "metodo1")]
    b = pd.read_parquet(RAIZ / "data/processed/fase3/trechos_contribuicao_base.parquet", columns=["segmento_id", "n_celulas_com_dados"])
    d = n.merge(b, on="segmento_id")
    sem = d["n_celulas_com_dados"] == 0                        # trecho sem nenhuma célula com dado de uso do solo: lacuna, não zero
    for c in ("v_gerado_local_max_m3", "contrib_potencial_max_m3"):
        d.loc[sem, c] = np.nan
    return d


def por_bairro(coluna: str, fator: float, n: int = 5) -> dict:
    """Maiores valores entre os bairros com trechos suficientes, só dentro da própria dimensão (valores de dimensões diferentes não se comparam)."""
    b = json.loads(RESULTADOS.read_text(encoding="utf-8"))["bairros"]
    ok = [x for x in b if x["suficiente"]]
    ordem = sorted(ok, key=lambda x: (-x[coluna], x["nome"]))[:n]
    return {"universo": f"{len(ok)} de {len(b)} bairros (os demais têm poucos trechos com dados e ficam sem estimativa)", "bairros_sem_estimativa": len(b) - len(ok),
            "itens": [{"bairro": x["nome"], "valor": round(x[coluna] * fator, 1), "trechos_com_dados": x["trechos_com_dados"]} for x in ordem]}


def dimensao_a_ou_b(dim: str, q: Quadro, d: pd.DataFrame, agua, bairros) -> dict:
    cfg = CONFIG[dim]
    col = "v_gerado_local_max_m3" if dim == "A" else "contrib_potencial_max_m3"
    v = d[col]
    h = q.valores_por_trecho(d, col)
    w, hpx = desenhar(q, q.grade_maximo(h), cfg["bordas"], cfg["cores"], ~np.isfinite(h), agua, bairros, IMG_DIR / cfg["arquivo"], cfg["fonte"])
    com, pos = v.dropna(), v[v > 0]
    nomes = rotulos(cfg["bordas"])
    faixas = [{"de": float(a), "ate": None if b >= MAX else float(b), "rotulo": r, "cor": c, "trechos": int(((pos > a) & (pos <= b)).sum())} for (a, b), r, c in zip(zip(cfg["bordas"][:-1], cfg["bordas"][1:]), nomes, cfg["cores"])]
    ind = {i["id"]: i for i in json.loads(RESULTADOS.read_text(encoding="utf-8"))["indicadores"]}
    r = {"nome": "Geração de escoamento" if dim == "A" else "Concentração do escoamento", "unidade": cfg["unidade"], "chuva_mm": P_MM, "pacote": "Método 1 (coeficientes fundamentados), limite superior do intervalo",
         "imagem": {"arquivo": f"img/estudo/{cfg['arquivo']}", "largura_px": w, "altura_px": hpx, "bytes": (IMG_DIR / cfg["arquivo"]).stat().st_size, "celula_m": 100, "agregacao": "máximo entre os trechos de cada célula"},
         "faixas": faixas, "trechos_total": int(len(v)), "trechos_com_dado": int(len(com)), "trechos_sem_dado": int(v.isna().sum()), "trechos_com_valor_positivo": int(len(pos)),
         "trechos_com_valor_zero": int((com == 0).sum()), "mediana_m3": round(float(pos.median()), 1), "p90_m3": round(float(pos.quantile(0.9)), 1), "p99_m3": round(float(pos.quantile(0.99)), 1),
         "area_com_coeficiente_fundamentado_pct": round(100 * ind["A-imp-frac"]["valor"], 1), "fonte": cfg["fonte"],
         "bairros": por_bairro("geracao_m1_max_aeq_por_ha", P_MM / 1000) if dim == "A" else por_bairro("contribuicao_m1_max_aeq_mediana", P_MM / 1000)}
    if dim == "A":
        r["bairros"]["metrica"] = "m³ por hectare em 30 mm (geração potencial por área classificada do bairro)"
        tot = json.loads(RESULTADOS.read_text(encoding="utf-8"))["dimensoes"]["A"]["dados"]["totais_m3"]["metodo1"]
        r["total_cidade_m3"] = {"min": round(tot["min"]), "max": round(tot["max"])}
    else:
        r["bairros"]["metrica"] = "mediana, entre os trechos do bairro, do m³ de escoamento potencial que converge ao trecho em 30 mm"
        r["trechos_acima_de_1000_m3"] = int((pos > 1000).sum())
        r["trechos_acima_de_10000_m3"] = int((pos > 10000).sum())
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", nargs="+", default=["A", "B"], choices=["A", "B"])
    args = ap.parse_args()
    q, agua, bairros = Quadro(carregar_rede()), carregar_agua(), carregar_bairros()
    saida = json.loads(DADOS.read_text(encoding="utf-8")) if DADOS.exists() else {}
    d = base_30mm() if ({"A", "B"} & set(args.so)) else None
    for dim in args.so:
        if dim in ("A", "B"):
            saida[dim] = dimensao_a_ou_b(dim, q, d, agua, bairros)
        print("gerado:", dim, saida[dim]["imagem"]["arquivo"], f"{saida[dim]['imagem']['bytes'] / 1024:.0f} KB")
    DADOS.write_text(json.dumps(dict(sorted(saida.items())), ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
