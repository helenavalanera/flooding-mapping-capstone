"""Auditoria de qualidade e cobertura das camadas de drenagem pluvial e contexto hídrico de Porto Alegre (fonte: serviços GIS da Prefeitura).

    PYTHONPATH=src python tools/auditar_drenagem_poa.py [saida.json]

Lê os arquivos de data/raw/drenagem_poa/ (gerados por tools/baixar_drenagem_poa.py, em SIRGAS 2000 / UTM 22S, EPSG:31982) e mede, sem corrigir nada:
preenchimento e valores sentinela dos atributos, validade e duplicidade de geometrias, conectividade GEOMÉTRICA da rede (extremos coincidentes), distância das bocas de lobo
à rede, comparação das casas de bomba com as do projeto, e das camadas hídricas com os 679 arroios do projeto.
Proximidade ou coincidência de extremos NÃO é conectividade hidráulica: é só evidência geométrica, e a auditoria a chama assim.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiLineString, Point, shape
from shapely.ops import transform
from shapely.strtree import STRtree

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw" / "drenagem_poa"
PARA_UTM = Transformer.from_crs(4674, 31982, always_xy=True).transform


def ler(nome: str) -> dict:
    return json.loads((RAW / f"{nome}.json").read_text(encoding="utf-8"))


def tabela(d: dict) -> pd.DataFrame:
    return pd.DataFrame([f["atributos"] for f in d["feicoes"]])


def linhas(d: dict) -> list:
    out = []
    for f in d["feicoes"]:
        caminhos = [LineString(p) for p in f["geometria"]["paths"] if len(p) >= 2]
        out.append(None if not caminhos else caminhos[0] if len(caminhos) == 1 else MultiLineString(caminhos))
    return out


def pontos(d: dict) -> np.ndarray:
    return np.array([[f["geometria"]["x"], f["geometria"]["y"]] for f in d["feicoes"]])


def poligonos(d: dict) -> list:
    """Esri rings -> shapely polygons (clockwise rings are exteriors, counter-clockwise are holes)."""
    out = []
    for f in d["feicoes"]:
        ext, bur = [], []
        for anel in f["geometria"]["rings"]:
            if len(anel) < 4:
                continue
            area = 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(anel, anel[1:]))
            (ext if area < 0 else bur).append(anel)
        partes = [shapely.Polygon(e) for e in ext]
        for b in bur:
            pb = shapely.Polygon(b)
            for i, p in enumerate(partes):
                if p.contains(pb.representative_point()):
                    partes[i] = p.difference(pb)
                    break
        out.append(shapely.MultiPolygon([p for p in partes if p.geom_type == "Polygon"]) if len(partes) > 1 else (partes[0] if partes else None))
    return out


def preenchido(s: pd.Series) -> pd.Series:
    """Not null and, for text, not blank. pandas 3 uses its own string dtype, so the test is on the dtype family, not on ``object``."""
    if pd.api.types.is_string_dtype(s) or s.dtype == object:
        return s.notna() & (s.astype(str).str.strip() != "")
    return s.notna()


FAIXAS = {"ALTITUDE_MONTANTE": (-5.0, 320.0), "ALTITUDE_JUSANTE": (-5.0, 320.0), "ALTITUDETAMPA": (-5.0, 320.0), "ALTITUDEMONTANTE": (-5.0, 320.0), "ALTITUDEJUSANTE": (-5.0, 320.0),
          "DECLIVIDADE": (-1.0, 1.0), "DIAMETRO": (0.0, 5000.0), "PROFUNDIDADE": (0.0, 60.0), "INSERCAOMONTANTE": (0.0, 60.0), "INSERCAOJUSANTE": (0.0, 60.0)}   # fisicamente plausíveis em Porto Alegre (maior altitude ~311 m)


def perfil(df: pd.DataFrame, numericos=(), categoricos=()) -> dict:
    n = len(df)
    out = {"n": n, "preenchimento": {c: round(float(preenchido(df[c]).mean()), 4) for c in df.columns if c.upper() not in ("OBJECTID", "FID")}}
    out["numericos"] = {}
    for c in numericos:
        v = pd.to_numeric(df[c], errors="coerce").dropna()
        out["numericos"][c] = {"preenchido": round(len(v) / n, 4), "zeros": int((v == 0).sum()), "negativos": int((v < 0).sum()), "fora_da_faixa_plausivel": int(((v < FAIXAS[c][0]) | (v > FAIXAS[c][1])).sum()) if c in FAIXAS else None, "faixa_plausivel": list(FAIXAS[c]) if c in FAIXAS else None,
                               "minimo": float(v.min()) if len(v) else None,
                               "mediana": float(v.median()) if len(v) else None, "maximo": float(v.max()) if len(v) else None}
    out["categoricos"] = {c: df[c].where(preenchido(df[c])).value_counts(dropna=False).head(12).rename(lambda k: "(vazio)" if pd.isna(k) else str(k)).to_dict() for c in categoricos}
    return out


def datas(df: pd.DataFrame, campos) -> dict:
    out = {}
    for c in campos:
        if c in df:
            v = pd.to_datetime(pd.to_numeric(df[c], errors="coerce"), unit="ms", errors="coerce").dropna()
            out[c] = {"preenchido": round(len(v) / len(df), 4), "minimo": str(v.min().date()) if len(v) else None, "maximo": str(v.max().date()) if len(v) else None}
    return out


def geometrias(geoms: list) -> dict:
    validas = [g for g in geoms if g is not None]
    invalidas = int(sum(not g.is_valid for g in validas))
    chaves = [shapely.to_wkb(shapely.set_precision(g, 0.01)) for g in validas]
    return {"sem_geometria": len(geoms) - len(validas), "invalidas": invalidas, "comprimento_zero": int(sum(g.length == 0 for g in validas)),
            "duplicadas_exatas": int(len(chaves) - len(set(chaves)))}


def conectividade(d: dict, pvs: np.ndarray) -> dict:
    """Geometric evidence only: how many segment ends coincide (within a tolerance) with another segment end or a manhole."""
    ls = linhas(d)
    ok = [i for i, g in enumerate(ls) if g is not None]
    p0 = np.array([ls[i].geoms[0].coords[0] if ls[i].geom_type == "MultiLineString" else ls[i].coords[0] for i in ok])
    p1 = np.array([ls[i].geoms[-1].coords[-1] if ls[i].geom_type == "MultiLineString" else ls[i].coords[-1] for i in ok])
    todos = np.vstack([p0, p1])
    arv, arv_pv = cKDTree(todos), cKDTree(pvs)
    n, saida = len(ok), {}
    for tol in (0.1, 0.5, 2.0):
        cont = np.array([len(x) - 1 for x in arv.query_ball_point(todos, tol)])           # other segment ends (the end itself is excluded)
        pv = np.array([len(x) for x in arv_pv.query_ball_point(todos, 1.0)]) if tol >= 0.5 else np.zeros(len(todos), int)
        liga = (cont > 0) | (pv > 0)
        a, b = liga[:n], liga[n:]
        saida[f"tolerancia_{tol}m"] = {"ambos_extremos_ligados": round(float((a & b).mean()), 4), "um_extremo_ligado": round(float((a ^ b).mean()), 4), "nenhum_extremo_ligado": round(float((~a & ~b).mean()), 4),
                                       "extremos_ligados_a_poco_de_visita_em_1m": round(float((pv > 0).mean()), 4) if tol >= 0.5 else None}
    return {"segmentos": n, "evidencia_geometrica_de_conexao_por_tolerancia": saida,
            "leitura": "Coincidência de extremos é evidência geométrica, não conectividade hidráulica confirmada: a camada não traz identificador de nó nem de trecho a montante/jusante."}


def consistencia_altitudes(df: pd.DataFrame) -> dict:
    mon, jus = pd.to_numeric(df["ALTITUDE_MONTANTE"], errors="coerce"), pd.to_numeric(df["ALTITUDE_JUSANTE"], errors="coerce")
    ext, decl = pd.to_numeric(df["EXTENSAO"], errors="coerce"), pd.to_numeric(df["DECLIVIDADE"], errors="coerce")
    ok = mon.notna() & jus.notna() & (mon != 0) & (jus != 0)
    desnivel = (mon - jus)[ok]
    calc = (desnivel / ext[ok]).replace([np.inf, -np.inf], np.nan)
    comp = pd.concat([calc, decl[ok]], axis=1).dropna()
    return {"com_as_duas_altitudes_validas": int(ok.sum()), "montante_maior_ou_igual_a_jusante": round(float((desnivel >= 0).mean()), 4) if ok.any() else None,
            "altitudes_iguais": round(float((desnivel == 0).mean()), 4) if ok.any() else None,
            "correlacao_declividade_informada_x_calculada": round(float(comp.corr().iloc[0, 1]), 3) if len(comp) > 10 else None,
            "razao_mediana_informada_sobre_calculada": round(float((comp.iloc[:, 1] / comp.iloc[:, 0].replace(0, np.nan)).median()), 2) if len(comp) > 10 else None,
            "altitude_montante_min_max": [float(mon[ok].min()), float(mon[ok].max())] if ok.any() else None}


def rede(nome: str, pvs: np.ndarray) -> dict:
    d = ler(nome)
    df = tabela(d)
    ls = linhas(d)
    comp = float(sum(g.length for g in ls if g is not None)) / 1000
    out = {"camada": nome, "feicoes": len(df), "extensao_pela_geometria_km": round(comp, 1), "extensao_pelo_campo_EXTENSAO_km": round(float(pd.to_numeric(df.get("EXTENSAO"), errors="coerce").sum()) / 1000, 1) if "EXTENSAO" in df else None,
           "identificador_de_origem": d["campo_de_identificador"], "campos_de_no_ou_trecho_a_montante_jusante": [c for c in df.columns if any(k in c.upper() for k in ("NO_", "NODE", "MONTANTE_ID", "TRECHO", "ID_"))],
           "geometria": geometrias(ls), "atributos": perfil(df, ("DIAMETRO", "EXTENSAO", "INSERCAOMONTANTE", "INSERCAOJUSANTE", "DECLIVIDADE", "ALTITUDE_MONTANTE", "ALTITUDE_JUSANTE", "EXT_DIGITAL"),
                                                            ("MATERIAL", "CLASSE", "ATIVO", "ACESSO", "ENABLED", "COLETORFUNDOS", "JUNTA", "ENCAIXE", "ENVELOPADO")),
           "datas": datas(df, ("DATAIMPLANTACAO", "DATACRIACAO", "DATAATUALIZACAO")), "consistencia_das_altitudes": consistencia_altitudes(df)}
    if nome == "rede_pluvial":
        out["conectividade"] = conectividade(d, pvs)
        dia = pd.to_numeric(df["DIAMETRO"], errors="coerce")
        out["diametro_valores_mais_comuns"] = dia[dia > 0].value_counts().head(10).to_dict()
    return out


def comparar_rede_consulta_publica() -> dict:
    a, b = ler("rede_pluvial"), ler("publica_rede_pluvial")

    def chaves(d):
        out = {}
        for f, g in zip(d["feicoes"], linhas(d)):
            if g is None:
                continue
            c0 = g.geoms[0].coords[0] if g.geom_type == "MultiLineString" else g.coords[0]
            c1 = g.geoms[-1].coords[-1] if g.geom_type == "MultiLineString" else g.coords[-1]
            k = tuple(sorted([(round(c0[0]), round(c0[1])), (round(c1[0]), round(c1[1]))])) + (round(g.length),)
            out.setdefault(k, f["atributos"])
        return out
    ka, kb = chaves(a), chaves(b)
    comuns = set(ka) & set(kb)
    iguais_diam = sum(1 for k in comuns if str(ka[k].get("DIAMETRO")) == str(kb[k].get("diametro")))
    iguais_mat = sum(1 for k in comuns if str(ka[k].get("MATERIAL")).strip().lower() == str(kb[k].get("material")).strip().lower())
    return {"consulta_trechos": len(a["feicoes"]), "publica_trechos": len(b["feicoes"]), "campos_so_na_consulta": sorted(set(c.upper() for c in a["campos"]) - set(c.upper() for c in b["campos"]) - {"COLETORFUNDOS", "DATAIMPLANTACAO"})[:20],
            "campos_so_na_publica": sorted(set(b["campos"]) - set(c.lower() for c in a["campos"]))[:10], "trechos_com_mesma_geometria_em_1m": len(comuns), "so_na_consulta": len(ka) - len(comuns), "so_na_publica": len(kb) - len(comuns),
            "entre_os_comuns_mesmo_diametro": round(iguais_diam / max(1, len(comuns)), 4), "entre_os_comuns_mesmo_material": round(iguais_mat / max(1, len(comuns)), 4),
            "leitura": "A camada pública não traz altitudes, inserção nem declividade; a de consulta traz. As duas têm contagens diferentes: são cópias de datas distintas."}


def bocas(bairros: list) -> dict:
    d = ler("boca_de_lobo")
    df = tabela(d)
    pts = pontos(d)
    rede_ls = [g for g in linhas(ler("rede_pluvial")) if g is not None]
    arv = STRtree(rede_ls)
    pt_geo = shapely.points(pts)
    idx = arv.nearest(pt_geo)
    dist = shapely.distance(pt_geo, np.array(rede_ls, dtype=object)[idx])
    limites = {f"ate_{t}m": round(float((dist <= t).mean()), 4) for t in (2, 5, 10, 25, 50)}
    formas = [transform(PARA_UTM, shape(b["geom"])) for b in bairros]
    arv_b = STRtree(formas)
    pares = arv_b.query(pt_geo, predicate="within")
    por_bairro = np.bincount(pares[1], minlength=len(formas))
    area_km2 = np.array([f.area for f in formas]) / 1e6
    dens = pd.DataFrame({"bairro": [b["nome"] for b in bairros], "bocas": por_bairro, "area_km2": area_km2})
    dens["por_km2"] = dens.bocas / dens.area_km2
    dens = dens[dens.area_km2 > 0.2]
    pub = ler("publica_boca_de_lobo")
    return {"bocas_de_lobo": len(df), "publica_bocas_de_lobo": len(pub["feicoes"]), "atributos": perfil(df, ("PROFUNDIDADE", "ALTITUDETAMPA"), ("TIPO", "ESPELHO", "ENABLED")), "datas": datas(df, ("DATAIMPLANTACAO", "DATACRIACAO", "DATAATUALIZACAO")),
            "capacidade_declarada": False, "campos_de_relacao_com_a_rede": [c for c in df.columns if any(k in c.upper() for k in ("TRECHO", "REDE", "CONDUTO", "NO_", "ID_"))],
            "distancia_a_rede_pluvial_mais_proxima": {"mediana_m": round(float(np.median(dist)), 1), "p90_m": round(float(np.percentile(dist, 90)), 1), "p99_m": round(float(np.percentile(dist, 99)), 1), **limites,
                                                      "sem_rede_em_50m": round(float((dist > 50).mean()), 4)},
            "bocas_dentro_de_algum_bairro": int(len(set(pares[0]))), "densidade_por_bairro_bocas_por_km2": {"mediana": round(float(dens.por_km2.median()), 1), "minimo": round(float(dens.por_km2.min()), 1), "maximo": round(float(dens.por_km2.max()), 1),
                                                                                                                  "bairros_com_menos_de_5_por_km2": dens[dens.por_km2 < 5].bairro.tolist()},
            "leitura": "Distância geométrica à rede NÃO é conexão hidráulica; a camada não diz a que trecho cada boca descarrega, nem se está funcional."}


def casas_de_bomba(bombas_projeto: list) -> dict:
    d = ler("casas_de_bomba_ebap")
    df = tabela(d)
    pts = pontos(d)
    proj = {b["nome"]: PARA_UTM(b["lon"], b["lat"]) for b in bombas_projeto}
    nomes = df["name"].astype(str).str.strip().tolist()
    casadas, so_servico = [], []
    for nome, p in zip(nomes, pts):
        melhor = min(proj.items(), key=lambda kv: np.hypot(kv[1][0] - p[0], kv[1][1] - p[1])) if proj else None
        mesma = nome in proj
        dist = float(np.hypot(proj[nome][0] - p[0], proj[nome][1] - p[1])) if mesma else None
        (casadas if mesma else so_servico).append({"nome": nome, "distancia_ao_registro_do_projeto_m": round(dist, 1) if dist is not None else None,
                                                   "mais_proximo_no_projeto": None if mesma or melhor is None else {"nome": melhor[0], "distancia_m": round(float(np.hypot(melhor[1][0] - p[0], melhor[1][1] - p[1])), 1)}})
    so_projeto = sorted(set(proj) - set(nomes))
    campos = {c: round(float(preenchido(df[c]).mean()), 3) for c in ("name", "local", "f__rea_prot", "se____o_re", "descri____", "f__rea_cont", "capacidade", "configura_", "endere__o")}
    return {"unidades": len(df), "preenchimento_dos_campos": campos, "capacidade_valores_distintos": sorted(set(df["capacidade"].astype(str).str.strip())), "unidade_da_capacidade": "não identificável: o campo está vazio em todos os registros",
            "no_projeto": len(bombas_projeto), "mesmo_nome_no_servico_e_no_projeto": len(casadas), "distancia_maxima_entre_os_registros_de_mesmo_nome_m": max([c["distancia_ao_registro_do_projeto_m"] for c in casadas], default=None),
            "somente_no_servico": so_servico, "somente_no_projeto": so_projeto, "casadas": casadas}


def amostrar(g, passo: float = 25.0) -> list:
    partes = g.geoms if g.geom_type == "MultiLineString" else [g]
    return [p.interpolate(d) for p in partes for d in np.arange(0, p.length, passo)] or [partes[0].interpolate(0)]


def hidrografia(arroios: list, extremos_livres: np.ndarray) -> dict:
    d = ler("recurso_hidrico")
    df = tabela(d)
    ls = linhas(d)
    validos = [g for g in ls if g is not None]
    arr = [transform(PARA_UTM, shape(a["geom"])) for a in arroios]
    arv_h, arv_a = STRtree(validos), STRtree(arr)
    pa = [p for g in arr for p in amostrar(g)]
    ph = [p for g in validos for p in amostrar(g)]
    da = shapely.distance(pa, np.array(validos, dtype=object)[arv_h.nearest(pa)])
    dh = shapely.distance(ph, np.array(arr, dtype=object)[arv_a.nearest(ph)])
    pe = shapely.points(extremos_livres)
    de = shapely.distance(pe, np.array(validos, dtype=object)[arv_h.nearest(pe)]) if len(pe) else np.array([])
    app = ler("hidrografia_2014")
    pol = poligonos(app)
    return {"recurso_hidrico_feicoes": len(df), "extensao_km": round(float(sum(g.length for g in validos)) / 1000, 1), "geometria": geometrias(ls),
            "atributos": perfil(df, ("EXTENSAO", "LARGURACANAL", "ALTURACANAL"), ("TIPO", "LEITO", "ACESSO", "ENABLED")), "datas": datas(df, ("DATACAMPO", "DATACRIACAO", "DATAATUALIZACAO")),
            "arroios_do_projeto": len(arr), "extensao_arroios_do_projeto_km": round(float(sum(g.length for g in arr)) / 1000, 1),
            "arroios_do_projeto_a_ate_25m_do_recurso_hidrico": round(float((da <= 25).mean()), 3), "arroios_do_projeto_a_ate_50m": round(float((da <= 50).mean()), 3),
            "recurso_hidrico_a_ate_25m_de_um_arroio_do_projeto": round(float((dh <= 25).mean()), 3),
            "extremos_livres_da_rede_pluvial": int(len(pe)), "extremos_livres_a_ate_25m_de_recurso_hidrico": round(float((de <= 25).mean()), 3) if len(de) else None,
            "app_hidrografia_2014": {"poligonos": len(pol), "area_km2": round(float(sum(p.area for p in pol if p is not None)) / 1e6, 2), "nome_preenchido": round(float(preenchido(tabela(app)["nome"]).mean()), 3),
                                     "fonte_declarada": "Projeto DMWeb, com base no aerolevantamento de 1982 (Áreas de Preservação Permanente), não curso d'água"},
            "leitura": "Recurso hídrico (cadastro da drenagem), arroios do projeto (mapa da Prefeitura) e APP são três coisas diferentes; proximidade não prova que o arroio recebe a rede."}


def risco_cprm(bairros: list) -> dict:
    d = ler("risco_inundacao_cprm")
    df = tabela(d)
    pol = poligonos(d)
    pol_utm = [p for p in pol if p is not None]
    # coordenadas do arquivo já estão em EPSG:31982
    areas = pd.Series([p.area for p in pol_utm]) / 1e6
    classes = df["classe"].astype(str).tolist()
    por_classe = pd.DataFrame({"classe": classes, "km2": areas}).groupby("classe").agg(poligonos=("km2", "size"), area_km2=("km2", "sum")).round(3).to_dict("index")
    uniao = shapely.union_all(pol_utm)
    municipio = shapely.union_all([transform(PARA_UTM, shape(b["geom"])) for b in bairros])
    return {"poligonos": len(df), "classes": por_classe, "classe_muito_alto_presente": "Muito Alto" in set(classes), "area_total_km2": round(float(areas.sum()), 2), "area_da_uniao_km2": round(uniao.area / 1e6, 2),
            "sobreposicao_entre_poligonos_km2": round(float(areas.sum()) - uniao.area / 1e6, 3), "fracao_da_area_dos_bairros": round(uniao.area / municipio.area, 4), "geometria": geometrias(pol_utm),
            "fonte_declarada": sorted(set(df["fonte"].astype(str).str.strip())), "processo": sorted(set(df["processo"].astype(str))),
            "camada_editavel_no_servidor": True, "leitura": "Risco mapeado por modelagem validada em campo (2012–2014): não é ocorrência histórica, nem simulação hidráulica, nem profundidade; só contexto e comparação qualitativa."}


def uso_do_solo_piloto(lon: float = -51.21772, lat: float = -30.05771, meio_lado_graus: float = 0.0045) -> dict:
    """Geometry quality of the land-use polygons in the pilot box (the same 1 km² area as the MDT pilot): validity, area field vs geometry, overlaps and gaps."""
    import requests
    url = "https://gis-smamus.portoalegre.rs.gov.br/server/rest/services/01_PUBLICACOES/uso_solo_profill_2022/MapServer/0"
    s = requests.Session()
    s.headers["User-Agent"] = "flooding-mapping-auditoria/1.0 (projeto academico)"
    env = json.dumps({"xmin": lon - meio_lado_graus, "ymin": lat - meio_lado_graus, "xmax": lon + meio_lado_graus, "ymax": lat + meio_lado_graus, "spatialReference": {"wkid": 4326}})
    base = {"geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "f": "json"}
    ids = s.get(url + "/query", params={**base, "returnIdsOnly": "true"}, timeout=120).json()["objectIds"] or []
    feicoes = []
    for i in range(0, len(ids), 500):
        r = s.post(url + "/query", data={"objectIds": ",".join(map(str, ids[i:i + 500])), "outFields": "classe,area_m2", "returnGeometry": "true", "outSR": 31982, "f": "json"}, timeout=180).json()
        feicoes += r["features"]
    pol = poligonos({"feicoes": [{"geometria": f["geometry"]} for f in feicoes]})
    classe = [f["attributes"]["classe"] for f in feicoes]
    campo = np.array([f["attributes"]["area_m2"] or np.nan for f in feicoes], float)
    x0, y0 = PARA_UTM(lon - meio_lado_graus, lat - meio_lado_graus)
    x1, y1 = PARA_UTM(lon + meio_lado_graus, lat + meio_lado_graus)
    caixa = shapely.box(x0, y0, x1, y1)
    invalidas = int(sum((p is not None) and (not p.is_valid) for p in pol))
    reparadas = [shapely.make_valid(p) if (p is not None and not p.is_valid) else p for p in pol]
    recortes = [p.intersection(caixa) for p in reparadas if p is not None]
    uniao = shapely.union_all(recortes)
    soma = float(sum(p.area for p in recortes))
    area_geo = np.array([p.area if p is not None else np.nan for p in reparadas])
    dif = np.abs(area_geo - campo) / campo
    por_classe = pd.DataFrame({"classe": classe, "area": [p.intersection(caixa).area if p is not None else 0 for p in reparadas]}).groupby("classe").area.sum().sort_values(ascending=False)
    return {"centro": {"lon": lon, "lat": lat}, "poligonos_que_tocam_a_caixa": len(feicoes), "area_da_caixa_m2": round(caixa.area), "geometrias_invalidas": invalidas,
            "cobertura_da_caixa_pelos_poligonos": round(uniao.area / caixa.area, 4), "lacunas_m2": round(caixa.area - uniao.area, 1), "sobreposicao_m2": round(soma - uniao.area, 1),
            "sobreposicao_fracao_da_area_somada": round((soma - uniao.area) / soma, 5), "campo_area_m2_x_area_pela_geometria": {"mediana_da_diferenca_relativa": round(float(np.nanmedian(dif)), 5), "p95_da_diferenca_relativa": round(float(np.nanpercentile(dif, 95)), 4)},
            "area_por_classe_na_caixa_fracao": (por_classe / por_classe.sum()).round(4).to_dict(),
            "leitura": "Escala cartográfica 1:2.500 é a escala de produção do mapa, não uma resolução de 2.500 m nem uma garantia de precisão dos limites dos polígonos."}


def rotulos_uso_do_solo() -> dict:
    return {"fonte": "estatísticas do servidor (agrupamento por classe) em 25/11/2026; polígonos não baixados nesta etapa", "poligonos": 605245, "area_classificada_km2": 472.5,
            "classes": {"Vegetação Nativa": 137.92, "Jardins, Passeios ou Áreas semi urbanizadas": 87.89, "Edificação": 58.38, "Campo": 48.08, "Área Úmida": 32.52, "Vias Pavimentadas": 23.31, "Cultivo não Irrigado": 17.16,
                        "Vegetação Mista": 15.05, "Cultivo Irrigado": 14.13, "Reflorestamento ou Vegetação Exótica": 11.55, "Pastagem": 8.32, "Solo Exposto": 7.95, "Corpo Hídrico": 3.59, "Área Degradada": 3.33, "Vias não Pavimentadas": 3.31}}


def main(saida: Path) -> dict:
    territorio = json.loads((RAIZ / "data/processed/territorio_poa.json").read_text())
    pvs = pontos(ler("poco_de_visita"))
    r57 = rede("rede_pluvial", pvs)
    resultado = {"coleta": "ver data/raw/manifest.json (entradas de data/raw/drenagem_poa/)", "srid_dos_arquivos": 31982,
                 "rede_pluvial": r57, "rede_pluvial_sem_acesso": rede("rede_pluvial_sem_acesso", pvs), "rede_pluvial_nao_interligada": rede("rede_pluvial_nao_interligada", pvs),
                 "rede_publica_x_consulta": comparar_rede_consulta_publica(), "poco_de_visita": {"feicoes": len(pvs), "atributos": perfil(tabela(ler("poco_de_visita")), ("PROFUNDIDADE", "ALTITUDETAMPA"), ("TIPO", "MATERIAL", "ENABLED"))},
                 "grelha": perfil(tabela(ler("grelha")), ("PROFUNDIDADE", "ALTITUDETAMPA"), ("TIPO", "MATERIAL")), "coletor_de_fundo": {"feicoes": len(ler("coletor_de_fundo")["feicoes"])},
                 "canal_pluvial": perfil(tabela(ler("canal_pluvial")), ("LARGURA", "ALTURA", "ALTITUDEMONTANTE", "ALTITUDEJUSANTE", "DECLIVIDADE", "EXTENSAO"), ("TIPOSECAO", "MATERIALPAREDE", "ACESSO")),
                 "conduto_forcado": perfil(tabela(ler("conduto_forcado")), ("DIAMETRO", "ALTURA", "LARGURA"), ("TIPOSECAO", "MATERIAL")),
                 "bocas_de_lobo": bocas(territorio["bairros"]), "casas_de_bomba": casas_de_bomba(territorio["bombas"]), "risco_cprm": risco_cprm(territorio["bairros"]), "uso_do_solo_profill_2022": rotulos_uso_do_solo()}
    # extremos livres da rede (sem outro extremo ou poço de visita a 0,5 m): candidatos a pontos de descarga, só por geometria
    ls = [g for g in linhas(ler("rede_pluvial")) if g is not None]
    p0 = np.array([g.geoms[0].coords[0] if g.geom_type == "MultiLineString" else g.coords[0] for g in ls])
    p1 = np.array([g.geoms[-1].coords[-1] if g.geom_type == "MultiLineString" else g.coords[-1] for g in ls])
    todos = np.vstack([p0, p1])
    arv, arv_pv = cKDTree(todos), cKDTree(pvs)
    livre = np.array([(len(a) - 1 == 0) and (len(b) == 0) for a, b in zip(arv.query_ball_point(todos, 0.5), arv_pv.query_ball_point(todos, 1.0))])
    resultado["hidrografia"] = hidrografia(territorio["arroios"], todos[livre])
    resultado["uso_do_solo_profill_2022"]["piloto_de_geometria_1km2"] = uso_do_solo_piloto()
    saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    return resultado


if __name__ == "__main__":
    r = main(Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "reports/qa/auditoria_drenagem_poa.json"))
    print("ok:", ", ".join(r))
