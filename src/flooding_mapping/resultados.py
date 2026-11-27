"""Resultados executivos do estudo de Porto Alegre, calculados dos dados reais (Fase 2 e Fase 3) para o dashboard.

Responde: dada uma precipitação de referência, quais contextos territoriais têm maior geração potencial de escoamento, concentração de contribuição
e propensão topográfica à retenção? Quatro dimensões distintas (podem se sobrepor): A superfícies construídas e pavimentadas; B vegetação e demais coberturas;
C concentração topográfica; D infraestrutura de drenagem cadastrada.

Regras: nada é somado entre trechos (a contribuição de trechos vizinhos se sobrepõe). Totais só por célula de 30 m (disjuntas) ou por área; por trecho
só quantis, razões e contagens. Cada afirmação conclusiva é uma ``Afirmacao`` com uma condição calculada: se a condição não vale, o título muda para
uma formulação neutra. Cada indicador carrega fórmula, unidade, fonte, cenário, método, cobertura e limitações. A drenagem é contexto: nenhuma
capacidade, funcionamento ou conectividade é inferida, e nada dela entra no cálculo de escoamento.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from . import camada_drenagem

IBGE_POA = "4314902"
CLASSES_IMPERMEAVEIS = {"05": "Edificação", "12": "Vias Pavimentadas"}
FAIXAS_IMPERMEAVEL = [(0.0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.0001)]
LIMIARES_M3 = (100.0, 1000.0, 10000.0)     # contagens de trechos acima destes valores de contribuição, só para comparar cenários
PRECIPITACOES = (10.0, 20.0, 30.0)
DISTANCIA_BOCA_M, DISTANCIA_POCO_M, DISTANCIA_REDE_M = 50.0, 30.0, 30.0
MINIMO_DE_TRECHOS_POR_BAIRRO = 200


def br(x: float, c: int = 0) -> str:
    return f"{x:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def sig(x: float) -> str:
    """Duas ou três casas úteis: 0,8 · 12 · 232."""
    return br(x, 0 if abs(x) >= 10 else 1 if abs(x) >= 1 else 2)


def pct(x: float, c: int = 1) -> str:
    return br(100 * x, c) + "%"


# ------------------------------------------------------------------------------------------------------------------- chuva
def serie_diaria(cache: Path) -> pd.Series:
    """Total diário (mm) de Porto Alegre, reanálise (Open-Meteo, base ERA5), do cache local da ingestão. Não é pluviômetro."""
    partes = []
    for f in sorted(glob.glob(str(cache / "precipitation_sum_*.json"))):
        d = json.loads(Path(f).read_text())
        if IBGE_POA in d["ibge"]:
            i = d["ibge"].index(IBGE_POA)
            v = d["values"][i]
            partes.append((pd.Series(v, index=pd.date_range(d["start"], periods=len(v), freq="D"), dtype=float), d["grid"][i]))
    if not partes:
        raise FileNotFoundError("sem série diária de Porto Alegre no cache da ingestão")
    s = pd.concat([p for p, _ in partes]).sort_index()
    s.attrs["ponto_da_grade"] = partes[0][1]
    return s[~s.index.duplicated()].dropna()


def eventos(s: pd.Series, limiar_dia_mm: float = 1.0) -> pd.DataFrame:
    """Evento = sequência de dias consecutivos com pelo menos ``limiar_dia_mm``; total = soma dos dias do evento."""
    chuvoso = (s >= limiar_dia_mm).astype(int)
    grupo = (chuvoso.diff().fillna(0) != 0).cumsum()
    ev = s[chuvoso == 1].groupby(grupo[chuvoso == 1]).agg(total_mm="sum", dias="count", maximo_diario_mm="max")
    ev["inicio"] = s[chuvoso == 1].groupby(grupo[chuvoso == 1]).apply(lambda x: x.index.min())
    return ev.reset_index(drop=True)


def estatisticas_de_chuva(s: pd.Series) -> dict:
    ev = eventos(s)
    anos = len(s) / 365.25
    completos = s.groupby(s.index.year).count()
    completos = completos[completos >= 365].index
    q = lambda x, p: float(np.quantile(x, p))  # noqa: E731
    pos = {f"{int(p)}": {"percentil_do_total_por_evento": float((ev["total_mm"] < p).mean()), "eventos_por_ano_com_total_igual_ou_maior": float((ev["total_mm"] >= p).sum() / anos),
                         "percentil_do_total_diario_em_dias_de_chuva": float((s[s >= 1] < p).mean()), "dias_por_ano_com_total_diario_igual_ou_maior": float((s >= p).sum() / anos)} for p in PRECIPITACOES}
    return {
        "fonte": "Open-Meteo, arquivo de reanálise (base ERA5), total diário, ponto da grade de Porto Alegre", "ponto_da_grade_lat_lon": [round(float(v), 3) for v in s.attrs["ponto_da_grade"]],
        "periodo": [str(s.index.min().date()), str(s.index.max().date())], "dias": int(len(s)), "natureza": "modelada (reanálise), não é pluviômetro; a grade é suavizada e subestima extremos locais",
        "tratamento": "dia com chuva = total diário de 1 mm ou mais; evento = sequência de dias consecutivos com chuva; total do evento = soma dos dias",
        "media_anual_mm": float(s[s.index.year.isin(completos)].groupby(s[s.index.year.isin(completos)].index.year).sum().mean()), "anos_completos": [int(a) for a in completos],
        "media_mensal_mm": float(s.groupby([s.index.year, s.index.month]).sum().mean()), "media_diaria_todos_os_dias_mm": float(s.mean()),
        "dias_com_chuva_fracao": float((s >= 1).mean()), "media_por_dia_com_chuva_mm": float(s[s >= 1].mean()),
        "eventos": int(len(ev)), "eventos_por_ano": float(len(ev) / anos), "duracao_media_dias": float(ev["dias"].mean()),
        "total_por_evento_mm": {"media": float(ev["total_mm"].mean()), "mediana": q(ev["total_mm"], .5), "p75": q(ev["total_mm"], .75), "p90": q(ev["total_mm"], .9), "p95": q(ev["total_mm"], .95), "p99": q(ev["total_mm"], .99)},
        "total_diario_em_dias_de_chuva_mm": {"mediana": q(s[s >= 1], .5), "p90": q(s[s >= 1], .9), "p95": q(s[s >= 1], .95), "p99": q(s[s >= 1], .99)},
        "maximo_diario_anual_mm": {"media": float(s[s.index.year.isin(completos)].groupby(s[s.index.year.isin(completos)].index.year).max().mean()),
                                   "minimo": float(s[s.index.year.isin(completos)].groupby(s[s.index.year.isin(completos)].index.year).max().min()),
                                   "maximo": float(s[s.index.year.isin(completos)].groupby(s[s.index.year.isin(completos)].index.year).max().max())},
        "cenarios_na_distribuicao": pos,
    }


# ------------------------------------------------------------------------------------------------------------------- base
def carregar(raiz: Path) -> dict:
    f3 = raiz / "data/processed/fase3"
    base = pd.read_parquet(f3 / "trechos_contribuicao_base.parquet")
    topo = pd.read_parquet(f3 / "trechos_nivel1_propensao_topografica.parquet")[["segmento_id", "altura_de_preenchimento_max_m", "propensao_topografica_percentil"]]
    rede = pd.read_parquet(raiz / "data/processed/rede_poa.parquet", columns=["segmento_id", "comprimento_m", "lon0", "lat0", "lon1", "lat1"])
    seg = gpd.read_parquet(raiz / "data/interim/segments.parquet", columns=["segment_id", "geometry"]).rename(columns={"segment_id": "segmento_id"})
    t = base.merge(topo, on="segmento_id", validate="1:1").merge(rede, on="segmento_id", validate="1:1").merge(seg, on="segmento_id", validate="1:1")
    t = gpd.GeoDataFrame(t, geometry="geometry", crs=seg.crs)
    territorio = json.loads((raiz / "data/processed/territorio_poa.json").read_text())
    from shapely import contains as shapely_contains, points
    from shapely.geometry import shape
    from shapely.strtree import STRtree

    formas = [shape(b["geom"]) for b in territorio["bairros"]]
    arvore = STRtree(formas)
    meio = points((t["lon0"].to_numpy() + t["lon1"].to_numpy()) / 2, (t["lat0"].to_numpy() + t["lat1"].to_numpy()) / 2)
    i, j = arvore.query(meio, predicate="within")
    bairro = np.full(len(t), -1, dtype=np.int32)
    bairro[i] = j
    t["bairro"] = bairro
    # Recorte municipal (docs/recorte_municipal.md): a malha de ruas traz vias de cidades vizinhas, sem uso do solo da Prefeitura. Só os trechos com ponto médio DENTRO do município entram nos resultados.
    municipio = gpd.read_parquet(raiz / "data/processed/municipality.parquet").to_crs("EPSG:4326").geometry.union_all()
    dentro = np.asarray(shapely_contains(municipio, meio))
    t = t[dentro].reset_index(drop=True)
    celulas = pd.read_parquet(f3 / "celulas_30m.parquet")
    uso = pd.read_parquet(raiz / "data/processed/uso_solo/uso_solo_grade30m.parquet")
    c = celulas.merge(uso, on=["linha", "coluna"], validate="1:1")
    c = c.astype({k: "float64" for k in c.columns if k.startswith(("aeq_", "acum_", "area_"))})   # os Parquets guardam float32; somar em float64
    from pyproj import Transformer

    lon, lat = Transformer.from_crs("EPSG:31982", "EPSG:4326", always_xy=True).transform(c["x_centro"].to_numpy(dtype=float), c["y_centro"].to_numpy(dtype=float))
    ic, jc = arvore.query(points(lon, lat), predicate="within")
    cb = np.full(len(c), -1, dtype=np.int32)
    cb[ic] = jc
    c["bairro"] = cb
    return {"trechos": t, "celulas": c, "bairros": [b["nome"] for b in territorio["bairros"]], "territorio": territorio}


def indicador(**k) -> dict:
    obrig = {"id", "dimensao", "titulo", "valor", "unidade", "formula", "fonte", "cenario", "metodo", "cobertura", "limitacoes"}
    if set(k) != obrig:
        raise ValueError(f"indicador sem {sorted(obrig - set(k))} ou com campos a mais")
    return k


def afirmacao(id: str, verificada: bool, titulo_conclusivo: str, titulo_neutro: str, evidencia: dict, observado: str, estimado: str, contexto: str, relevancia: str, limitacao: str) -> dict:
    """Um achado executivo. ``verificada`` vem de uma condição calculada: sem ela vale o título neutro."""
    return {"id": id, "verificada": bool(verificada), "titulo": titulo_conclusivo if verificada else titulo_neutro, "titulo_conclusivo_se_verificada": titulo_conclusivo, "titulo_neutro": titulo_neutro,
            "evidencia": evidencia, "observado": observado, "estimado": estimado, "contexto": contexto, "relevancia": relevancia, "limitacao": limitacao}


FONTE_F3 = "data/processed/fase3/ (trechos_contribuicao_base, trechos_nivel1_propensao_topografica, celulas_30m)"
FORMULA_V = "V (m³) = P (mm) × aeq (m²) ÷ 1000, com aeq = Σ área da classe × C"


# ------------------------------------------------------------------------------------------------------------------- dimensão A
def dimensao_a(c: pd.DataFrame, uso_json: dict, P: float) -> tuple[dict, list[dict], list[dict]]:
    ok = c[c["area_classificada_m2"] > 0].copy()
    imp = sum(ok[f"area_m2__{k}"] for k in CLASSES_IMPERMEAVEIS)
    ok["frac_imp"] = imp / ok["area_classificada_m2"]
    linhas = []
    for lo, hi in FAIXAS_IMPERMEAVEL:
        g = ok[(ok["frac_imp"] >= lo) & (ok["frac_imp"] < hi)]
        area = float(g["area_classificada_m2"].sum())
        linha = {"faixa": [lo, min(hi, 1.0)], "celulas": int(len(g)), "area_km2": area / 1e6, "fracao_da_area_classificada": area / float(ok["area_classificada_m2"].sum())}
        for pac, col in (("metodo1", "aeq_m1"), ("analoga", "aeq_analoga"), ("limites", "aeq_limites")):
            for lim in ("min", "max"):
                linha[f"c_efetivo_{pac}_{lim}"] = float(g[f"{col}_{lim}"].sum() / area) if area else None
        linhas.append(linha)
    cresc = lambda k: all(linhas[i][k] < linhas[i + 1][k] for i in range(len(linhas) - 1))  # noqa: E731
    mono = {"metodo1_max": cresc("c_efetivo_metodo1_max"), "metodo1_min": cresc("c_efetivo_metodo1_min"), "analoga_max": cresc("c_efetivo_analoga_max"), "analoga_min": cresc("c_efetivo_analoga_min"),
            "limites_max": cresc("c_efetivo_limites_max")}
    verificada = bool(mono["metodo1_max"] and mono["metodo1_min"])      # só o Método 1 cobre as classes construídas e pavimentadas: os outros pacotes cobrem outras classes
    cls = uso_json["classes"]
    area_edif, area_vias = cls["Edificação"]["area_km2"], cls["Vias Pavimentadas"]["area_km2"]
    total_class = sum(v["area_km2"] for v in cls.values())
    totais = {pac: {lim: float(c[f"{col}_{lim}"].sum()) * P / 1000 for lim in ("min", "max")} for pac, col in (("metodo1", "aeq_m1"), ("analoga", "aeq_analoga"), ("limites", "aeq_limites"))}
    razao_m1 = totais["metodo1"]["max"] / totais["metodo1"]["min"]
    razao_an = totais["analoga"]["max"] / totais["analoga"]["min"]
    imp_total = (area_edif + area_vias) / total_class
    por_ha = lambda l: l["c_efetivo_metodo1_max"] * P * 10     # m³ por hectare: P (mm) × 10 × C
    a1 = afirmacao(
        "A1", verificada, f"Nas áreas com mais superfície construída e pavimentada o Método 1 estima mais escoamento potencial por hectare: de {sig(por_ha(linhas[0]))} m³/ha na faixa com menos construção a {sig(por_ha(linhas[-1]))} m³/ha na mais, para {br(P)} mm",
        "O Método 1 não estimou mais escoamento potencial por hectare nas faixas com mais superfície construída e pavimentada",
        {"crescimento_por_faixa": mono, "faixas": linhas, "volume_por_hectare_metodo1_max_m3": [por_ha(l) for l in linhas]},
        f"Edificação e vias pavimentadas somam {br(area_edif + area_vias, 1)} km² ({pct(imp_total)} da área classificada): {br(area_edif, 1)} km² de edificação e {br(area_vias, 1)} km² de vias. Agrupando as células de 30 m pela parcela construída e pavimentada (potencialmente impermeável), a faixa com menos construção (até 10%) reúne {br(linhas[0]['area_km2'], 0)} km² e a com mais construção (70% ou mais), {br(linhas[-1]['area_km2'], 0)} km².",
        f"O coeficiente efetivo médio do Método 1 (limite superior) vai de {br(linhas[0]['c_efetivo_metodo1_max'], 2)} a {br(linhas[-1]['c_efetivo_metodo1_max'], 2)} entre a primeira e a última faixa. Pela analogia, que cobre as classes de vegetação e similares, vai de {br(linhas[0]['c_efetivo_analoga_max'], 2)} a {br(linhas[-1]['c_efetivo_analoga_max'], 2)} e não é monotônico: na faixa com menos construção há muito campo e jardim, e na com mais construção pouca vegetação.",
        f"O município se divide entre áreas pouco construídas ({br(linhas[0]['area_km2'], 0)} km² com até 10% de superfície construída ou pavimentada) e áreas mais construídas; só {br(linhas[-1]['area_km2'], 0)} km² têm 70% ou mais.",
        "Mostra onde a superfície, sozinha, tende a gerar mais água; é um ponto de partida para investigar permeabilização, não uma medida de risco.",
        "O Método 1 só tem coeficiente nas classes construídas e pavimentadas, então que a geração cresça com a parcela construída é, em boa parte, o que a definição do pacote implica: o resultado mostra a distribuição territorial, não prova a hipótese. Os pacotes cobrem classes diferentes e não se somam.")
    a2 = afirmacao(
        "A2", razao_an > razao_m1, f"Os coeficientes por analogia deixam o volume potencial {br(razao_an, 1)} vezes mais incerto entre o limite inferior e o superior, contra {br(razao_m1, 1)} vez no Método 1, nas classes que cada pacote cobre",
        "A incerteza dos coeficientes por analogia não é maior que a do Método 1", {"razao_limite_superior_sobre_inferior": {"metodo1": razao_m1, "analoga": razao_an}, "totais_m3_por_pacote": totais},
        f"Para {br(P)} mm, o Método 1 (edificação e vias pavimentadas) gera de {br(totais['metodo1']['min'] / 1e6, 2)} a {br(totais['metodo1']['max'] / 1e6, 2)} milhões de m³; a analogia (as classes de vegetação e similares com valor de referência), de {br(totais['analoga']['min'] / 1e6, 2)} a {br(totais['analoga']['max'] / 1e6, 2)}; o envelope de limites físicos (as demais classes), de 0 a {br(totais['limites']['max'] / 1e6, 1)} milhões de m³. Cada pacote cobre classes diferentes.",
        f"O limite superior é {br(razao_m1, 2)} vez o inferior no Método 1 e {br(razao_an, 1)} vezes na analogia; no envelope físico o inferior é zero. Soma das células de 30 m, que não se sobrepõem.",
        "Em toda a cidade; a incerteza dos coeficientes pesa mais que a diferença entre as chuvas de 10 e 30 mm nas classes sem coeficiente fundamentado.",
        "Qualquer afirmação sobre volume gerado precisa citar o pacote, as classes que ele cobre e o intervalo. Um número único esconde a incerteza.",
        "Os pacotes são alternativas metodológicas sobre classes diferentes e nunca se somam; o intervalo é hipótese declarada, não erro estatístico.")
    ind = [
        indicador(id="A-imp-frac", dimensao="A", titulo="Área classificada construída ou pavimentada (edificação e via pavimentada; potencialmente impermeável)", valor=imp_total, unidade="fração da área classificada", formula="(área de Edificação + área de Vias Pavimentadas) ÷ área classificada",
                  fonte="reports/qa/qualidade_uso_solo_fase2.json · classes.*.area_km2", cenario="independe da chuva", metodo="soma de áreas dos polígonos de uso do solo (Profill 2022)", cobertura="95,1% do município classificado",
                  limitacoes="Escala 1:2.500 sobre ortoimagem de 2018 a 2021; passeios e pátios cimentados podem estar em 'Jardins, Passeios'."),
        indicador(id="A-ceff", dimensao="A", titulo="Coeficiente efetivo médio por faixa de parcela construída e pavimentada", valor=[{k: v for k, v in l.items() if k.startswith(("faixa", "c_efetivo", "celulas"))} for l in linhas], unidade="adimensional (fração da chuva que escoa)",
                  formula="Σ aeq ÷ Σ área classificada, por faixa de parcela construída e pavimentada da célula (aeq do pacote: só as classes que ele cobre)", fonte=FONTE_F3 + " e uso_solo_grade30m.parquet", cenario="independe da chuva", metodo="Método 1 (classes construídas e pavimentadas), analogia (vegetação e similares) e limites físicos (demais), limites inferior e superior",
                  cobertura="células de 30 m com área classificada", limitacoes="Cada pacote cobre classes diferentes; o Método 1 só tem coeficiente nas classes construídas e pavimentadas; o limite físico não discrimina."),
        indicador(id="A-vol-pacotes", dimensao="A", titulo="Volume potencial gerado pelas classes de cada pacote", valor=totais, unidade="m³ (limite inferior e superior por pacote)", formula=FORMULA_V + "; somado sobre as células (disjuntas)",
                  fonte=FONTE_F3, cenario=f"{br(P)} mm hipotéticos", metodo="soma das células de 30 m, por pacote (classes cobertas por ele)", cobertura="1.290.058 células com dados", limitacoes="Água potencialmente escoada, sem infiltração nem perdas; não é volume transportado; os pacotes não se somam."),
    ]
    return {"faixas": linhas, "totais_m3": totais, "razoes": {"metodo1": razao_m1, "analoga": razao_an}}, [a1, a2], ind


# ------------------------------------------------------------------------------------------------------------------- dimensão B
def dimensao_b(uso_json: dict, hip: dict, P: float) -> tuple[dict, list[dict], list[dict]]:
    cls = uso_json["classes"]
    total = sum(v["area_km2"] for v in cls.values())
    m1 = {r["classe"]: (r["c_min"], r["c_max"]) for r in hip["metodo1"]}
    an = {r["classe"]: (r["c_min"], r["c_max"]) for r in hip["referencia_analoga"]}
    linhas = []
    for nome, v in sorted(cls.items(), key=lambda kv: -kv[1]["area_km2"]):
        a = v["area_km2"]
        c_an = an.get(nome) or m1.get(nome)
        largura = a * (c_an[1] - c_an[0]) if c_an else None
        linhas.append({"classe": nome, "area_km2": a, "fracao": a / total, "fora_do_calculo": bool(v["fora_do_calculo_de_escoamento"]), "metodo1": list(m1[nome]) if nome in m1 else None,
                       "analoga": list(an[nome]) if nome in an else None, "limites_fisicos": None if v["fora_do_calculo_de_escoamento"] else [0.0, 1.0],
                       "volume_m3_analoga": None if not c_an else [a * 1e6 * c_an[0] * P / 1000, a * 1e6 * c_an[1] * P / 1000], "largura_do_intervalo_km2_equivalente": largura})
    soma_larg = sum(l["largura_do_intervalo_km2_equivalente"] or 0 for l in linhas)
    for l in linhas:
        l["parcela_da_incerteza_da_analogia"] = (l["largura_do_intervalo_km2_equivalente"] or 0) / soma_larg
    topo = max(linhas, key=lambda l: l["parcela_da_incerteza_da_analogia"])
    sem_fund = topo["classe"] not in m1
    jard = next(l for l in linhas if l["classe"].startswith("Jardins"))
    cen_j = hip["jardins_e_passeios"]["cenarios_de_fracao_de_piso"]
    veg = [l for l in linhas if not l["fora_do_calculo"] and l["classe"] not in m1]
    area_veg = sum(l["area_km2"] for l in veg)
    b1 = afirmacao(
        "B1", sem_fund, f"A maior parte da incerteza da geração potencial está em uma classe sem coeficiente fundamentado: {topo['classe']} ({pct(topo['parcela_da_incerteza_da_analogia'], 0)} da largura do intervalo)",
        "A incerteza da geração potencial está distribuída entre classes com e sem coeficiente fundamentado",
        {"classe_dominante": topo["classe"], "parcela": topo["parcela_da_incerteza_da_analogia"], "classes": linhas},
        f"{topo['classe']} ocupa {br(topo['area_km2'], 1)} km² ({pct(topo['fracao'])} da área classificada) e é a classe com maior parcela da largura do intervalo da analogia. As classes sem coeficiente fundamentado somam {br(area_veg, 1)} km² ({pct(area_veg / total)}) fora a água.",
        f"Na analogia, a classe vale C de {br(jard['analoga'][0], 3)} a {br(jard['analoga'][1], 3)}, o envelope de três hipóteses de fração de piso ({', '.join(str(c['fracao_de_piso']) + '%' for c in cen_j)}); nenhuma delas é tratada como verdade.",
        "É uma classe de transição entre o construído e o vegetado (jardins, passeios e áreas semi urbanizadas): a parcela de piso real é desconhecida.",
        "A melhor forma de reduzir a incerteza da cidade construída é medir a fração permeável dessa classe (por imagem ou levantamento), antes de refinar o modelo.",
        "As frações de piso são hipóteses; o resultado indica onde falta informação, não qual valor é o correto.")
    b2 = afirmacao(
        "B2", True, f"Edificação e vias pavimentadas, as únicas classes com coeficiente fundamentado, cobrem {pct(uso_json['cobertura_dos_metodos']['metodo1_fracao_da_area_classificada'])} da área classificada",
        "", {"metodo1": uso_json["cobertura_dos_metodos"]["metodo1_fracao_da_area_classificada"], "sem_coeficiente": uso_json["cobertura_dos_metodos"]["sem_coeficiente_fundamentado_fracao"]},
        f"{pct(uso_json['cobertura_dos_metodos']['sem_coeficiente_fundamentado_fracao'])} da área classificada não tem coeficiente em referência publicada e {pct(uso_json['cobertura_dos_metodos']['fora_do_calculo_fracao'])} é água ou fica fora do cálculo.",
        "O Método 1 usa só o que tem referência: edificação (C de 0,75 a 0,95) e via pavimentada (C de 0,70 a 0,95).",
        "Toda a cidade; a cobertura por trecho (área a montante com coeficiente fundamentado) tem mediana de 30% e fica em cada trecho do mapa.",
        "Define o que o Método 1 pode dizer: o escoamento das superfícies construídas e pavimentadas, e não o da cidade inteira.",
        "Coeficientes de manuais de outros países (TxDOT, San Diego County); a adaptação ao solo de Porto Alegre depende de pedologia e declividade.")
    ind = [indicador(id="B-classes", dimensao="B", titulo="Área e coeficientes por classe de uso do solo", valor=linhas, unidade="km² e adimensional", formula="área da classe (km²); C por pacote (tabelas do projeto)",
                     fonte="reports/qa/qualidade_uso_solo_fase2.json e config/uso_solo_*.csv", cenario="independe da chuva; volumes para a chuva de referência", metodo="Método 1, analogia e limites físicos", cobertura="15 classes, 95,1% do município",
                     limitacoes="Classe sem referência fica só com o envelope físico; jardins e passeios sempre em envelope."),
           indicador(id="B-incerteza", dimensao="B", titulo="Parcela da incerteza da geração (analogia) por classe", valor={l["classe"]: l["parcela_da_incerteza_da_analogia"] for l in linhas}, unidade="fração da largura do intervalo",
                     formula="área × (C máximo − C mínimo) da classe ÷ Σ das classes", fonte="idem", cenario="independe da chuva", metodo="analogia (jardins em envelope)", cobertura="classes com valor na analogia", limitacoes="Mede a largura de hipóteses, não um erro.")]
    return {"classes": linhas}, [b1, b2], ind


# ------------------------------------------------------------------------------------------------------------------- dimensão C
def dimensao_c(t: pd.DataFrame, nomes_bairros: list[str], c_cel: pd.DataFrame, P: float) -> tuple[dict, list[dict], list[dict], list[dict]]:
    d = t[t["contrib_aeq_m1_max_m2"].notna()].copy()
    q = lambda col: {k: float(d[col].quantile(p)) for k, p in (("p10", .1), ("p25", .25), ("p50", .5), ("p75", .75), ("p90", .9), ("p99", .99))}  # noqa: E731
    contrib, local, area = q("contrib_aeq_m1_max_m2"), q("local_aeq_m1_max_m2"), q("area_montante_m2")
    razao = contrib["p99"] / contrib["p50"]
    top10 = d["contrib_aeq_m1_max_m2"] >= d["contrib_aeq_m1_max_m2"].quantile(.9)
    com_fill = d["altura_de_preenchimento_max_m"] > 0
    rho = float(d["contrib_aeq_m1_max_m2"].rank().corr(d["propensao_topografica_percentil"].rank()))
    p_fill_top, p_fill_resto = float(com_fill[top10].mean()), float(com_fill[~top10].mean())
    if abs(rho) < 0.3:
        titulo, ver = f"Contribuição acumulada e propensão topográfica são dimensões quase independentes (correlação de postos de {br(rho, 2)})", True
    elif rho > 0:
        titulo, ver = f"Trechos de maior contribuição tendem a ter maior propensão topográfica à retenção (correlação de postos de {br(rho, 2)})", True
    else:
        titulo, ver = f"Trechos de maior contribuição tendem a ter menor propensão topográfica à retenção (correlação de postos de {br(rho, 2)})", True
    c1 = afirmacao(
        "C1", razao >= 10, f"A contribuição potencial é concentrada: o trecho do percentil 99 recebe {br(razao, 0)} vezes o da mediana",
        "A contribuição potencial não é fortemente concentrada em poucos trechos", {"razao_p99_p50": razao, "quantis_aeq_m2": contrib},
        f"Entre {br(len(d))} trechos com dados, a contribuição potencial acumulada (Método 1, limite superior) tem mediana de {br(contrib['p50'] * P / 1000, 1)} m³, percentil 90 de {br(contrib['p90'] * P / 1000, 0)} m³ e percentil 99 de {br(contrib['p99'] * P / 1000, 0)} m³ para {br(P)} mm.",
        f"A área contribuinte tem a mesma cauda: mediana de {br(area['p50'], 0)} m² e percentil 99 de {br(area['p99'] / 1e4, 0)} ha: os maiores valores estão onde o fluxo simulado junta áreas extensas a montante.",
        "A maioria dos trechos recebe quase só a água da sua vizinhança; poucos eixos, onde o fluxo simulado converge, recebem a de áreas extensas. A tabela por bairro mostra onde isso se concentra.",
        "Indica onde investigar primeiro a capacidade de drenagem e o entorno, porque é onde mais água pode passar.",
        "Contribuição não é volume que chegou, nem se soma entre trechos; o modelo de 30 m pode desviar caminhos em áreas densas.")
    c2 = afirmacao(
        "C2", ver, titulo, "", {"spearman_contribuicao_posto_topografico": rho, "parcela_com_preenchimento_no_decil_superior": p_fill_top, "parcela_com_preenchimento_nos_demais": p_fill_resto},
        f"{pct(com_fill.mean())} dos trechos com dados têm algum preenchimento de depressão; entre os 10% de maior contribuição são {pct(p_fill_top)}, e entre os demais {pct(p_fill_resto)}.",
        "O indicador topográfico posiciona cada trecho pela altura que o preenchimento soma ao relevo; é relativo e sem unidade física.",
        "Concentrar água (muita área a montante) e ter depressão local são situações diferentes: um trecho pode ter uma e não a outra.",
        "Por isso as duas leituras ficam separadas: investigar o primeiro grupo pede capacidade de drenagem; o segundo, levantamento topográfico fino.",
        "Modelo de elevação de 30 m (erro médio de 2,18 m): o indicador só compara trechos entre si, não indica profundidade, volume nem duração.")
    # contextos por bairro
    linhas = []
    cel = c_cel[c_cel["bairro"] >= 0]
    for i, nome in enumerate(nomes_bairros):
        g = d[d["bairro"] == i]
        cb = cel[cel["bairro"] == i]
        area_cl = float(cb["area_classificada_m2"].sum())
        if len(g) == 0 or area_cl == 0:
            continue
        imp = float(sum(cb[f"area_m2__{k}"].sum() for k in CLASSES_IMPERMEAVEIS))
        linhas.append({"nome": nome, "trechos_com_dados": int(len(g)), "area_classificada_km2": area_cl / 1e6, "fracao_impermeavel": imp / area_cl,
                       "geracao_m1_max_aeq_por_ha": float(cb["aeq_m1_max"].sum()) / (area_cl / 1e4), "geracao_analoga_max_aeq_por_ha": float(cb["aeq_analoga_max"].sum()) / (area_cl / 1e4),
                       "contribuicao_m1_max_aeq_mediana": float(g["contrib_aeq_m1_max_m2"].median()), "contribuicao_m1_max_aeq_p90": float(g["contrib_aeq_m1_max_m2"].quantile(.9)),
                       "parcela_no_decil_superior_da_cidade": float((g["contrib_aeq_m1_max_m2"] >= d["contrib_aeq_m1_max_m2"].quantile(.9)).mean()),
                       "parcela_com_preenchimento": float((g["altura_de_preenchimento_max_m"] > 0).mean()), "cobertura_m1_a_montante_mediana": float(g["fracao_montante_coberta_m1"].median()),
                       "km_de_ruas": float(g["comprimento_m"].sum() / 1000), "suficiente": bool(len(g) >= MINIMO_DE_TRECHOS_POR_BAIRRO)})
    ind = [
        indicador(id="C-contrib", dimensao="C", titulo="Contribuição potencial acumulada por trecho: quantis", valor=contrib, unidade="m² de área equivalente (multiplicar por P ÷ 1000 para m³)", formula="contrib = Σ aeq das áreas a montante das células de chegada da pegada; V = P × contrib ÷ 1000",
                  fonte=FONTE_F3, cenario="independe da chuva (aeq); m³ para a chuva escolhida", metodo="Método 1, limite superior", cobertura=f"{br(len(d))} trechos com dados de 176.836", limitacoes="Potencial, não transportado; valores por trecho não somáveis."),
        indicador(id="C-area", dimensao="C", titulo="Área contribuinte por trecho: quantis", valor=area, unidade="m²", formula="área a montante das células de chegada da pegada", fonte=FONTE_F3, cenario="independe da chuva", metodo="fluxo D8 sobre o Copernicus GLO-30 de 30 m",
                  cobertura=f"{br(len(d))} trechos", limitacoes="Depende do modelo de elevação; os caminhos podem se desviar em áreas densas."),
        indicador(id="C-razao", dimensao="C", titulo="Razão entre o percentil 99 e a mediana da contribuição", valor=razao, unidade="adimensional", formula="p99(contrib) ÷ p50(contrib)", fonte=FONTE_F3, cenario="independe da chuva", metodo="Método 1, limite superior",
                  cobertura=f"{br(len(d))} trechos", limitacoes="Medida de forma da distribuição, não de risco."),
        indicador(id="C-topo", dimensao="C", titulo="Trechos com algum preenchimento de depressão e correlação com a contribuição", valor={"parcela_com_preenchimento": float(com_fill.mean()), "spearman": rho}, unidade="fração; correlação de postos (−1 a 1)",
                  formula="parcela = trechos com altura de preenchimento > 0 ÷ trechos com dados; ρ = correlação de Spearman entre contribuição e posto topográfico", fonte=FONTE_F3, cenario="independe da chuva", metodo="indicador topográfico de retenção (priority-flood)", cobertura=f"{br(len(d))} trechos",
                  limitacoes="Altura do modelo de 30 m não é profundidade."),
    ]
    return {"quantis_contribuicao_aeq": contrib, "quantis_local_aeq": local, "quantis_area_m2": area}, [c1, c2], ind, linhas


# ------------------------------------------------------------------------------------------------------------------- dimensão D
def dimensao_d(raiz: Path, t: gpd.GeoDataFrame, nomes_bairros: list[str], territorio: dict) -> tuple[dict, list[dict], list[dict], dict]:
    pasta = raiz / "data/processed/drenagem"
    rede, pocos, bocas, bombas = (camada_drenagem.carregar(pasta, k) for k in ("rede", "pocos", "bocas", "bombas"))
    uteis = lambda g: g[g["usar_no_inventario"]]  # noqa: E731
    rede_u, pocos_u, bocas_u = uteis(rede), uteis(pocos), uteis(bocas)
    km = lambda g: float(g.geometry.length.sum() / 1000)  # noqa: E731
    por_cat = {k: {"trechos": int((rede_u["camada_origem"] == k).sum()), "km": km(rede_u[rede_u["camada_origem"] == k])} for k in ("rede_pluvial", "rede_pluvial_sem_acesso", "rede_pluvial_nao_interligada")}
    d = t[t["contrib_aeq_m1_max_m2"].notna()].copy()
    d["quintil"] = pd.qcut(d["contrib_aeq_m1_max_m2"].rank(method="first"), 5, labels=False)

    def perto(g, dist):
        j = gpd.sjoin_nearest(gpd.GeoDataFrame(geometry=d.geometry.values, crs=d.crs), gpd.GeoDataFrame(geometry=g.geometry.values, crs=g.crs), how="left", distance_col="dist")
        return j.groupby(level=0)["dist"].min().reindex(range(len(d))).to_numpy()
    d_boca, d_poco, d_rede = perto(bocas_u, DISTANCIA_BOCA_M), perto(pocos_u, DISTANCIA_POCO_M), perto(rede_u, DISTANCIA_REDE_M)
    linhas = []
    for qn in range(5):
        m = (d["quintil"] == qn).to_numpy()
        linhas.append({"quintil": qn + 1, "trechos": int(m.sum()), "contribuicao_m1_max_aeq_mediana": float(d.loc[m, "contrib_aeq_m1_max_m2"].median()),
                       "com_boca_de_lobo_ate_50m": float((d_boca[m] <= DISTANCIA_BOCA_M).mean()), "com_poco_ate_30m": float((d_poco[m] <= DISTANCIA_POCO_M).mean()),
                       "com_rede_ate_30m": float((d_rede[m] <= DISTANCIA_REDE_M).mean()), "distancia_mediana_a_boca_m": float(np.nanmedian(d_boca[m]))})
    bs = [l["com_boca_de_lobo_ate_50m"] for l in linhas]
    sobe = all(bs[i] < bs[i + 1] for i in range(4)) and bs[-1] - bs[0] >= 0.05
    desce = all(bs[i] > bs[i + 1] for i in range(4)) and bs[0] - bs[-1] >= 0.05
    if sobe:
        titulo = f"Há mais bocas de lobo cadastradas perto dos trechos de maior contribuição potencial ({pct(bs[0], 0)} no quintil inferior, {pct(bs[-1], 0)} no superior)"
    elif desce:
        titulo = f"Há menos bocas de lobo cadastradas perto dos trechos de maior contribuição potencial ({pct(bs[0], 0)} no quintil inferior, {pct(bs[-1], 0)} no superior)"
    else:
        titulo = f"Não há relação monotônica entre a contribuição potencial e a presença de bocas de lobo cadastradas por perto ({pct(min(bs), 0)} a {pct(max(bs), 0)} entre os quintis)"
    comp_total = km(rede_u)
    from shapely.geometry import shape as _shape

    _formas = gpd.GeoSeries([_shape(b["geom"]) for b in territorio["bairros"]], crs="EPSG:4326").to_crs("EPSG:31982")
    _dens = np.array([float(rede_u.geometry.intersection(f).length.sum() / 1000 / (f.area / 1e6)) for f in _formas if f.area > 0])
    dens_min, dens_med, dens_max = float(_dens.min()), float(np.median(_dens)), float(_dens.max())
    d1 = afirmacao(
        "D1", True, f"O cadastro registra {br(comp_total, 0)} km de rede pluvial, {br(len(pocos_u))} poços de visita e {br(len(bocas_u))} bocas de lobo; {pct(por_cat['rede_pluvial_sem_acesso']['km'] / comp_total)} da rede é registro sem acesso",
        "", {"rede_por_categoria": por_cat, "pocos": int(len(pocos_u)), "bocas": int(len(bocas_u)), "casas_de_bomba": int(len(uteis(bombas)))},
        f"Rede em {br(por_cat['rede_pluvial']['km'], 0)} km (cadastro existente), {br(por_cat['rede_pluvial_sem_acesso']['km'], 1)} km sem acesso e {br(por_cat['rede_pluvial_nao_interligada']['km'], 2)} km cadastrados como não interligados; {br(len(uteis(bombas)))} casas de bomba, das quais só o nome está preenchido.",
        "Contexto: o cadastro é independente do cálculo de escoamento e não entra em nenhum resultado das outras dimensões.",
        f"A densidade de rede cadastrada varia muito entre bairros (de {br(dens_min, 1)} a {br(dens_max, 1)} km de rede por km², mediana de {br(dens_med, 1)}), o que mostra onde o cadastro é denso e onde é esparso.",
        "Mostra onde há registro, o que orienta onde pedir informação de capacidade e de manutenção.",
        "O cadastro diz o que está registrado: não indica capacidade de vazão, funcionamento, conectividade hidráulica nem eficiência.")
    d2 = afirmacao(
        "D2", True, titulo, "", {"por_quintil": linhas, "limiares_m": {"boca": DISTANCIA_BOCA_M, "poco": DISTANCIA_POCO_M, "rede": DISTANCIA_REDE_M}},
        f"Dos trechos do quintil de menor contribuição, {pct(bs[0])} têm uma boca de lobo cadastrada a até {br(DISTANCIA_BOCA_M)} m; no quintil de maior contribuição, {pct(bs[-1])}. Para a rede a até {br(DISTANCIA_REDE_M)} m: {pct(linhas[0]['com_rede_ate_30m'])} e {pct(linhas[-1]['com_rede_ate_30m'])}.",
        "A contribuição potencial vem do cálculo; a infraestrutura vem do cadastro. A comparação é espacial e descritiva.",
        f"Os quintis são de contribuição entre os trechos com dados. No inferior, só {pct(linhas[0]['com_rede_ate_30m'], 0)} dos trechos têm rede cadastrada a até {br(DISTANCIA_REDE_M)} m (no superior, {pct(linhas[-1]['com_rede_ate_30m'], 0)}): a diferença reflete, em boa parte, onde há cadastro, e não necessariamente onde há infraestrutura suficiente.",
        "Onde há muita contribuição potencial e pouco registro de drenagem por perto, vale pedir informação à gestora: é uma hipótese de investigação.",
        "Associação espacial não é capacidade nem função: perto de uma boca de lobo não significa que a água seja captada. A cobertura do cadastro e a urbanização confundem a comparação.")
    # por bairro: km de rede por km² e bocas por km² (urbana)
    from shapely.geometry import shape

    formas = gpd.GeoSeries([shape(b["geom"]) for b in territorio["bairros"]], crs="EPSG:4326").to_crs("EPSG:31982")
    area_b = formas.area.to_numpy() / 1e6
    bairros = {}
    for nome, f, a in zip(nomes_bairros, formas, area_b):
        bairros[nome] = {"area_km2": float(a), "rede_km_por_km2": float(rede_u.geometry.intersection(f).length.sum() / 1000 / a) if a else None, "bocas_por_km2": float(bocas_u.within(f).sum() / a) if a else None}
    ind = [
        indicador(id="D-rede", dimensao="D", titulo="Rede pluvial cadastrada por categoria", valor=por_cat, unidade="trechos e km", formula="contagem e soma de comprimento (geometria em EPSG:31982) por camada de origem, sem duplicatas", fonte="data/processed/drenagem/rede_pluvial.parquet",
                  cenario="independe da chuva", metodo="cadastro da Prefeitura, camada de origem preservada", cobertura="Porto Alegre", limitacoes="Sem capacidade, conexões confirmadas nem funcionamento."),
        indicador(id="D-pontos", dimensao="D", titulo="Poços de visita, bocas de lobo e casas de bomba cadastrados", valor={"pocos": int(len(pocos_u)), "bocas": int(len(bocas_u)), "casas_de_bomba": int(len(uteis(bombas)))}, unidade="registros", formula="contagem sem duplicatas exatas",
                  fonte="data/processed/drenagem/*.parquet", cenario="independe da chuva", metodo="cadastro da Prefeitura", cobertura="Porto Alegre", limitacoes="Das casas de bomba só o nome está preenchido; capacidade ausente."),
        indicador(id="D-relacao", dimensao="D", titulo="Presença de infraestrutura cadastrada perto dos trechos, por quintil de contribuição", valor=linhas, unidade="fração dos trechos do quintil", formula="parcela dos trechos com elemento a até 50 m (boca), 30 m (poço) ou 30 m (rede)",
                  fonte=FONTE_F3 + " e data/processed/drenagem/", cenario="independe da chuva", metodo="distância geométrica mínima (EPSG:31982) entre o trecho e o elemento", cobertura=f"{br(len(d))} trechos com dados", limitacoes="Associação espacial, sem inferência de captação."),
    ]
    return {"rede_por_categoria": por_cat, "por_quintil": linhas, "por_bairro": bairros}, [d1, d2], ind, bairros


# ------------------------------------------------------------------------------------------------------------------- cenários
def cenarios(t: pd.DataFrame, c_cel: pd.DataFrame, raiz: Path) -> tuple[dict, list[dict], list[dict]]:
    d = t[t["contrib_aeq_m1_max_m2"].notna()]
    vol = {}
    for P in PRECIPITACOES:
        k = f"{int(P)}"
        vol[k] = {"trechos_com_dados": int(len(d)), "geracao_cidade_m3": {pac: {lim: float(c_cel[f"{col}_{lim}"].sum()) * P / 1000 for lim in ("min", "max")} for pac, col in (("metodo1", "aeq_m1"), ("analoga", "aeq_analoga"), ("limites", "aeq_limites"))},
                  "por_trecho_m1_max_m3": {"local": {q: float(d["local_aeq_m1_max_m2"].quantile(p)) * P / 1000 for q, p in (("p50", .5), ("p90", .9), ("p99", .99))},
                                           "contribuicao": {q: float(d["contrib_aeq_m1_max_m2"].quantile(p)) * P / 1000 for q, p in (("p50", .5), ("p90", .9), ("p99", .99))}},
                  "trechos_com_contribuicao_acima_de_m3": {f"{int(L)}": int((d["contrib_aeq_m1_max_m2"] * P / 1000 >= L).sum()) for L in LIMIARES_M3}}
    n2 = pd.read_parquet(raiz / "data/processed/fase3/trechos_nivel2_cenarios.parquet")
    n2 = n2[n2["pacote"] == "metodo1"].pivot(index="segmento_id", columns="p_mm", values="contrib_potencial_max_m3").dropna()
    ordem_igual = bool((n2[10.0].rank() == n2[30.0].rank()).all())          # saída do motor, não a conta feita aqui
    erro = float(((n2[30.0] / n2[10.0].where(n2[10.0] > 0)) - 3).abs().max())
    fator = vol["30"]["geracao_cidade_m3"]["metodo1"]["max"] / vol["10"]["geracao_cidade_m3"]["metodo1"]["max"]
    s1 = afirmacao(
        "S1", ordem_igual and abs(fator - 3) < 1e-9 and erro < 1e-9, "Mudar a chuva de 10 para 30 mm multiplica os volumes por 3, mas não muda quais trechos concentram mais contribuição",
        "A ordem dos trechos mudou com a chuva", {"ordem_dos_trechos_igual": ordem_igual, "erro_maximo_do_fator_3_por_trecho": erro, "fator_30_sobre_10": fator, "trechos_acima_de_m3": {k: v["trechos_com_contribuicao_acima_de_m3"] for k, v in vol.items()}},
        f"O volume gerado e a contribuição crescem na proporção da chuva (fator {br(fator, 3)} de 10 para 30 mm). Como a chuva é uniforme, a distribuição espacial das classes é a mesma nos três cenários; muda só a faixa em m³ de cada classe.",
        "Contagem de trechos com contribuição potencial acima de valores fixos: " + "; ".join(f"≥ {br(float(L))} m³: " + ", ".join(f"{br(vol[k]['trechos_com_contribuicao_acima_de_m3'][f'{int(L)}'])} a {k} mm" for k in ("10", "20", "30")) for L in LIMIARES_M3) + ".",
        "Em toda a cidade; a chuva uniforme não diferencia ruas.",
        "O cenário serve para comparar sensibilidade e dimensionar a ordem de grandeza da água potencialmente escoada, não para dizer onde alaga primeiro.",
        "Mais volume calculado não significa maior profundidade, extensão ou duração de alagamento: o modelo não tem infiltração, perdas, drenagem nem tempo.")
    ind = [indicador(id="S-cenarios", dimensao="S", titulo="Volumes e contagens por chuva de referência", valor=vol, unidade="m³; trechos", formula=FORMULA_V, fonte=FONTE_F3 + " e trechos_nivel2_cenarios.parquet", cenario="10, 20 e 30 mm hipotéticos e uniformes",
                     metodo="linearidade verificada contra a saída do motor", cobertura="1.290.058 células; trechos com dados", limitacoes="Chuva uniforme; sem tempo, infiltração nem drenagem.")]
    return vol, [s1], ind


# ------------------------------------------------------------------------------------------------------------------- síntese
def sintese(bairros_c: list[dict], bairros_d: dict, P: float, uso_json: dict, t: pd.DataFrame) -> dict:
    ok = [b for b in bairros_c if b["suficiente"]]
    top = sorted(ok, key=lambda b: -b["contribuicao_m1_max_aeq_mediana"])[:5]
    top_geracao = sorted(ok, key=lambda b: -b["geracao_analoga_max_aeq_por_ha"])[:5]
    top_decil = sorted(ok, key=lambda b: -b["parcela_no_decil_superior_da_cidade"])[:5]
    sem_dados = int(t["contrib_aeq_m1_max_m2"].isna().sum())
    for lista in (top, top_geracao, top_decil):
        for b in lista:
            b["rede_km_por_km2"] = bairros_d.get(b["nome"], {}).get("rede_km_por_km2")
            b["bocas_por_km2"] = bairros_d.get(b["nome"], {}).get("bocas_por_km2")
    cob = uso_json["cobertura_dos_metodos"]
    return {
        "contextos_prioritarios_hipoteses": {"por_contribuicao_mediana": top, "por_geracao_potencial_por_hectare_analogia": top_geracao, "por_parcela_no_decil_superior": top_decil, "criterio": f"bairros com ao menos {MINIMO_DE_TRECHOS_POR_BAIRRO} trechos com dados; ranking só por quantis e razões (nada somado entre trechos)"},
        "lacunas_de_dados": {"area_sem_coeficiente_fundamentado": cob["sem_coeficiente_fundamentado_fracao"], "trechos_sem_dados": sem_dados, "validacao": "124 registros de 2013 e 2014, sem horário nem chuva associada",
                             "drenagem": "sem capacidade, conexões confirmadas nem funcionamento; casas de bomba só com nome", "relevo": "modelo de superfície de 30 m com erro médio de 2,18 m"},
        "para_uma_analise_hidraulica": ["eventos de alagamento datados, com horário e chuva associada, para validar o motor", "capacidade e conexões confirmadas de galerias, bocas de lobo e casas de bomba (e o estado de manutenção)",
                                        "pedologia e declividade para fundamentar os coeficientes das classes sem referência", "fração permeável de jardins, passeios e áreas semi urbanizadas",
                                        "modelo de terreno de maior resolução (o MDT municipal de 1 m, hoje adiado) para depressões urbanas", "chuva no tempo e distribuída no espaço, em vez de uniforme"],
    }


# ------------------------------------------------------------------------------------------------------------------- montagem
def gerar(raiz: Path) -> dict:
    uso_json = json.loads((raiz / "reports/qa/qualidade_uso_solo_fase2.json").read_text())
    meta = json.loads((raiz / "data/processed/fase3_web/meta.json").read_text())
    hip = meta["hipoteses"]
    serie = serie_diaria(raiz / "data/raw/weather/archive")
    chuva = estatisticas_de_chuva(serie)
    P = 30.0
    chuva["referencia_operacional_mm"] = P
    chuva["leitura_da_referencia"] = (f"{br(P)} mm é um cenário operacional ilustrativo. Na série de {chuva['periodo'][0][:4]} a {chuva['periodo'][1][:4]} ele corresponde ao percentil {br(100 * chuva['cenarios_na_distribuicao']['30']['percentil_do_total_por_evento'], 0)} dos totais por evento "
                                      f"({br(chuva['cenarios_na_distribuicao']['30']['eventos_por_ano_com_total_igual_ou_maior'], 1)} eventos por ano o igualam ou superam). Não é a média histórica (média por evento de {br(chuva['total_por_evento_mm']['media'], 1)} mm; mediana de {br(chuva['total_por_evento_mm']['mediana'], 1)} mm).")
    base = carregar(raiz)
    t, c = base["trechos"], base["celulas"]
    A, ach_a, ind_a = dimensao_a(c, uso_json, P)
    B, ach_b, ind_b = dimensao_b(uso_json, hip, P)
    C, ach_c, ind_c, bairros_c = dimensao_c(t, base["bairros"], c, P)
    D, ach_d, ind_d, bairros_d = dimensao_d(raiz, t, base["bairros"], base["territorio"])
    cen, ach_s, ind_s = cenarios(t, c, raiz)
    sint = sintese(bairros_c, bairros_d, P, uso_json, t)
    return {"versao": 1, "pergunta": "Dada uma precipitação de referência em Porto Alegre, quais contextos territoriais apresentam maior geração potencial de escoamento, concentração de contribuição e propensão topográfica à retenção?",
            "precipitacao_de_referencia_mm": P, "chuva": chuva,
            "dimensoes": {"A": {"nome": "Superfícies construídas e pavimentadas", "dados": A, "achados": ach_a}, "B": {"nome": "Vegetação e demais coberturas", "dados": B, "achados": ach_b},
                          "C": {"nome": "Concentração do escoamento e propensão topográfica à retenção", "dados": C, "achados": ach_c}, "D": {"nome": "Drenagem cadastrada", "dados": D, "achados": ach_d}},
            "cenarios": {"dados": cen, "achados": ach_s}, "bairros": bairros_c, "sintese": sint, "indicadores": ind_a + ind_b + ind_c + ind_d + ind_s,
            "gerado_de": ["reports/qa/qualidade_uso_solo_fase2.json", "data/processed/fase3/", "data/processed/fase3_web/meta.json", "data/processed/uso_solo/uso_solo_grade30m.parquet", "data/processed/drenagem/", "data/raw/weather/archive/", "data/processed/territorio_poa.json"]}
