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
from manchas_base import ESTATICO, IMG_DIR, RAIZ, Quadro, carregar_agua, carregar_bairros, carregar_rede, desenhar  # noqa: E402

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
    "D": {"arquivo": "mapa-drenagem.webp", "bordas": [0, 50, 100, 200, 300, MAX], "cores": ["#d4ecd9", "#9fd4b0", "#5fb383", "#2d8a5d", "#0e5236"], "unidade": "metros de rede pluvial cadastrada por célula de 100 m, ou 1 hectare",
          "fonte": "Cadastro de drenagem pluvial: Prefeitura de Porto Alegre (GeoPOA)"},
}


def pt(x: float, casas: int = 0) -> str:
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rotulos(bordas: list[float]) -> list[str]:
    r = [f"{pt(a)} a {pt(b)} m³" for a, b in zip(bordas[1:-2], bordas[2:-1])]
    return [f"mais de 0 até {pt(bordas[1])} m³", *r, f"mais de {pt(bordas[-2])} m³"]


def base_30mm() -> pd.DataFrame:
    n2 = pd.read_parquet(RAIZ / "data/processed/fase3/trechos_nivel2_cenarios.parquet")
    n2 = n2[n2.p_mm == P_MM]
    n = n2[n2.pacote == "metodo1"]
    m2 = n2[n2.pacote == "referencia_analoga"][["segmento_id", "v_gerado_local_max_m3", "contrib_potencial_max_m3"]].rename(columns={"v_gerado_local_max_m3": "m2_v", "contrib_potencial_max_m3": "m2_contrib"})
    n = n.merge(m2, on="segmento_id", how="left")
    b = pd.read_parquet(RAIZ / "data/processed/fase3/trechos_contribuicao_base.parquet", columns=["segmento_id", "n_celulas_com_dados"])
    d = n.merge(b, on="segmento_id")
    sem = d["n_celulas_com_dados"] == 0                        # trecho sem nenhuma célula com dado de uso do solo: lacuna, não zero
    for c in ("v_gerado_local_max_m3", "contrib_potencial_max_m3"):
        d.loc[sem, c] = np.nan
    return d


MIN_TRECHOS = 200   # mínimo de trechos de rua com dados para um bairro entrar nas listas (resultados.py: MINIMO_DE_TRECHOS_POR_BAIRRO); vale para as quatro dimensões


def por_bairro(coluna: str, fator: float, n: int = 5, com_construido: bool = False) -> dict:
    """Maiores valores entre os bairros com trechos suficientes, só dentro da própria dimensão (valores de dimensões diferentes não se comparam)."""
    b = json.loads(RESULTADOS.read_text(encoding="utf-8"))["bairros"]
    ok = [x for x in b if x["suficiente"]]
    ordem = sorted(ok, key=lambda x: (-x[coluna], x["nome"]))[:n]
    return {"universo": f"{len(ok)} de {len(b)} bairros (os com menos de {MIN_TRECHOS} trechos de rua com dados ficam sem estimativa; o mesmo critério vale para as quatro dimensões)", "bairros_sem_estimativa": len(b) - len(ok),
            "itens": [{"bairro": x["nome"], "valor": round(x[coluna] * fator, 1), "trechos_com_dados": x["trechos_com_dados"],
                       **({"construido_pct": round(100 * x["fracao_impermeavel"], 1)} if com_construido else {})} for x in ordem]}


def dimensao_a_ou_b(dim: str, q: Quadro, d: pd.DataFrame, agua, bairros) -> dict:
    cfg = CONFIG[dim]
    col, col2 = ("v_gerado_local_max_m3", "m2_v") if dim == "A" else ("contrib_potencial_max_m3", "m2_contrib")
    na_malha = len(d)
    d = d[d["segmento_id"].isin(set(q.ids[q.no_municipio()]))]            # só ruas dentro de Porto Alegre (docs/recorte_municipal.md)
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
         "trechos_com_valor_zero": int((com == 0).sum()), "trechos_na_malha": int(na_malha), "trechos_fora_do_municipio": int(na_malha - len(d)),
         "zero_com_hipotese_metodo2": int(((v == 0) & (d[col2] > 0)).sum()), "zero_sem_classe_com_coeficiente_nem_hipotese": int(((v == 0) & ~(d[col2] > 0)).sum()), "mediana_m3": round(float(pos.median()), 1), "p90_m3": round(float(pos.quantile(0.9)), 1), "p99_m3": round(float(pos.quantile(0.99)), 1),
         "area_com_coeficiente_fundamentado_pct": round(100 * ind["A-imp-frac"]["valor"], 1), "fonte": cfg["fonte"],
         "bairros": por_bairro("geracao_m1_max_aeq_por_ha", P_MM / 1000, com_construido=True) if dim == "A" else por_bairro("contribuicao_m1_max_aeq_mediana", P_MM / 1000, com_construido=True)}
    if dim == "A":
        r["bairros"]["metrica"] = "m³ por hectare em 30 mm (geração potencial por área classificada do bairro)"
        tot = json.loads(RESULTADOS.read_text(encoding="utf-8"))["dimensoes"]["A"]["dados"]["totais_m3"]["metodo1"]
        r["total_cidade_m3"] = {"min": round(tot["min"]), "max": round(tot["max"])}
    else:
        r["bairros"]["metrica"] = "mediana, entre os trechos do bairro, do m³ de escoamento potencial que converge ao trecho em 30 mm"
        r["trechos_acima_de_1000_m3"] = int((pos > 1000).sum())
        r["trechos_acima_de_10000_m3"] = int((pos > 10000).sum())
    return r


def rede_por_celula(q: Quadro) -> np.ndarray:
    """Metros de rede pluvial cadastrada (sem duplicatas) que caem em cada célula de 100 m: o comprimento é repartido em pedaços de até 10 m, cada um na célula do seu centro."""
    import geopandas as gpd
    import shapely

    g = gpd.read_parquet(RAIZ / "data/processed/drenagem/rede_pluvial.parquet", columns=["geometry", "usar_no_inventario"])
    g = g[g["usar_no_inventario"]]
    co, ix = shapely.get_coordinates(shapely.segmentize(g.geometry.values, 10), return_index=True)
    mesma = ix[1:] == ix[:-1]
    a, b = co[:-1][mesma], co[1:][mesma]
    comp, m = np.hypot(*(b - a).T), (a + b) / 2
    iy, ixc = q.celula(m[:, 0], m[:, 1])
    ok = (iy >= 0) & (iy < q.ny) & (ixc >= 0) & (ixc < q.nx)
    grade = np.zeros((q.ny, q.nx))
    np.add.at(grade, (iy[ok], ixc[ok]), comp[ok])
    return grade


def dimensao_d(q: Quadro, agua, bairros) -> dict:
    cfg = CONFIG["D"]
    grade = rede_por_celula(q)
    dentro = q.no_municipio()
    iy, ix = q.celula(q.xm, q.ym)
    com_rede = (grade[iy.clip(0, q.ny - 1), ix.clip(0, q.nx - 1)] > 0)[dentro]            # só trechos de rua dentro de Porto Alegre
    w, hpx = desenhar(q, grade, cfg["bordas"], cfg["cores"], None, agua, bairros, IMG_DIR / cfg["arquivo"], cfg["fonte"])
    cel = grade[grade > 0]
    res = json.loads(RESULTADOS.read_text(encoding="utf-8"))
    ind = {i["id"]: i["valor"] for i in res["indicadores"]}
    rede, pontos = ind["D-rede"], ind["D-pontos"]
    rec = json.loads((ESTATICO / "data/recorte_municipal_poa.json").read_text(encoding="utf-8"))["no_municipio"]["boca_de_lobo_ate_50m_por_quintil_de_contribuicao_pct"]
    q_nulos = json.loads((RAIZ / "data/processed/drenagem/qualidade_drenagem.json").read_text(encoding="utf-8"))["rede_pluvial"]["rede_pluvial"]["fracao_de_nulos_por_coluna"]
    pb = res["dimensoes"]["D"]["dados"]["por_bairro"]
    ok = {b["nome"] for b in res["bairros"] if b["suficiente"]}
    ordem = sorted(((n, v) for n, v in pb.items() if n in ok), key=lambda t: (-t[1]["rede_km_por_km2"], t[0]))[:5]
    km = sum(v["km"] for v in rede.values())
    return {"nome": "Drenagem cadastrada", "unidade": cfg["unidade"], "natureza": "cadastro municipal: registro, não funcionamento nem capacidade",
            "imagem": {"arquivo": f"img/estudo/{cfg['arquivo']}", "largura_px": w, "altura_px": hpx, "bytes": (IMG_DIR / cfg["arquivo"]).stat().st_size, "celula_m": 100, "agregacao": "soma do comprimento de rede em cada célula"},
            "faixas": [{"de": float(a), "ate": None if b >= MAX else float(b), "rotulo": r, "cor": c, "celulas": int(((cel > a) & (cel <= b)).sum())}
                       for (a, b), r, c in zip(zip(cfg["bordas"][:-1], cfg["bordas"][1:]), [f"mais de 0 até 50 m", "50 a 100 m", "100 a 200 m", "200 a 300 m", "mais de 300 m"], cfg["cores"])],
            "rede_km": round(km), "rede_trechos": sum(v["trechos"] for v in rede.values()), "rede_sem_acesso_km": round(rede["rede_pluvial_sem_acesso"]["km"]), "pocos_de_visita": pontos["pocos"], "bocas_de_lobo": pontos["bocas"],
            "casas_de_bomba": pontos["casas_de_bomba"], "celulas_com_rede": int(len(cel)), "mediana_m_por_celula": round(float(np.median(cel))), "p90_m_por_celula": round(float(np.quantile(cel, 0.9))),
            "trechos_de_rua_total": int(len(com_rede)), "trechos_de_rua_em_celula_com_rede": int(com_rede.sum()), "trechos_de_rua_em_celula_com_rede_pct": round(100 * float(com_rede.mean()), 1),
            "campos_sem_preenchimento_pct": {"material": round(100 * q_nulos["material"]), "declividade": round(100 * q_nulos["declividade"]), "classe_do_tubo": round(100 * q_nulos["classe_do_tubo"])},
            "perto_de_boca_de_lobo_por_quintil_de_concentracao_pct": {"menor": round(rec[0]), "maior": round(rec[-1])},
            "fonte": cfg["fonte"], "bairros": {"metrica": "km de rede pluvial cadastrada (parte urbana) por km² do bairro", "universo": f"{len(ok)} de {len(res['bairros'])} bairros (mesmo critério das outras dimensões: os com menos de {MIN_TRECHOS} trechos de rua com dados ficam de fora; a rede cadastrada destes dois não é avaliada aqui)",
                                               "bairros_sem_estimativa": len(res["bairros"]) - len(ok), "itens": [{"bairro": n, "valor": round(v["rede_km_por_km2"], 1), "bocas_por_km2": round(v["bocas_por_km2"])} for n, v in ordem]}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", nargs="+", default=["A", "B", "D"], choices=["A", "B", "D"])
    args = ap.parse_args()
    q, agua, bairros = Quadro(carregar_rede()), carregar_agua(), carregar_bairros()
    saida = json.loads(DADOS.read_text(encoding="utf-8")) if DADOS.exists() else {}
    d = base_30mm() if ({"A", "B"} & set(args.so)) else None
    for dim in args.so:
        saida[dim] = dimensao_d(q, agua, bairros) if dim == "D" else dimensao_a_ou_b(dim, q, d, agua, bairros)
        print("gerado:", dim, saida[dim]["imagem"]["arquivo"], f"{saida[dim]['imagem']['bytes'] / 1024:.0f} KB")
    DADOS.write_text(json.dumps(dict(sorted(saida.items())), ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
