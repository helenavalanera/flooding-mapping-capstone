"""Frente A, Fase 2: inventário cadastral de drenagem de Porto Alegre em GeoParquet (EPSG:31982), a partir dos arquivos de data/raw/drenagem_poa/.

    PYTHONPATH=src python tools/processar_drenagem_poa.py [pasta_de_saida]

O que isto É: um inventário geoespacial, com os atributos originais preservados (valores NUNCA corrigidos: o que parece errado ganha uma coluna de sinalização) e evidências
geométricas rotuladas como tais.
O que isto NÃO é: capacidade, vazão, funcionamento, nem conectividade hidráulica.
  - `evidencia_geometrica_*` diz só que um extremo coincide (dentro da tolerância) com outro extremo ou com um poço de visita; o cadastro não traz nó nem trecho a montante/jusante;
  - `distancia_geometrica_a_rede_m` é uma distância, e NENHUM identificador de trecho é atribuído às bocas de lobo;
  - `ativo_no_cadastro` e `acesso` repetem campos do cadastro, não confirmam operação;
  - as casas de bomba não têm campo de capacidade: o texto original (vazio nos 24 registros) é preservado só para provar a ausência.
Os registros duplicados (mesma geometria, mesmo desenho) ficam na tabela, marcados com `duplicata_exata_de`; `usar_no_inventario` os exclui sem apagá-los.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auditar_drenagem_poa as aud  # noqa: E402
from flooding_mapping import ingest  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw" / "drenagem_poa"
SAIDA = RAIZ / "data" / "processed" / "drenagem"
MANIFESTO = RAIZ / "data" / "raw" / "manifest.json"
CRS = "EPSG:31982"
VERSAO = "fase2-1"
TOLERANCIA_EXTREMOS_M = 0.5
TOLERANCIA_POCO_M = 1.0
ANO_MIN, ANO_MAX = 1900, 2026

REDES = {"rede_pluvial": "rede_pluvial", "rede_pluvial_sem_acesso": "rede_pluvial_sem_acesso", "rede_pluvial_nao_interligada": "rede_pluvial_nao_interligada"}
# campo original -> (campo padronizado, unidade, de onde vem a unidade)
CAMPOS_REDE = {"OBJECTID": ("id_origem", None, None), "DIAMETRO": ("diametro", "mm", "inferida pelos valores (75 a 2.000); não declarada no serviço"), "MATERIAL": ("material", None, None),
               "CLASSE": ("classe_do_tubo", None, None), "EXTENSAO": ("extensao", "m", "inferida (confere com o comprimento da geometria); não declarada"), "JUNTA": ("junta", None, None),
               "ENCAIXE": ("encaixe", None, None), "ENVELOPADO": ("envelopado", None, None), "INSERCAOMONTANTE": ("insercao_montante", "m", "inferida pelos valores; não declarada"),
               "INSERCAOJUSANTE": ("insercao_jusante", "m", "inferida pelos valores; não declarada"), "DECLIVIDADE": ("declividade", "m/m", "inferida (bate com a calculada pelas altitudes); não declarada"),
               "ALTITUDE_MONTANTE": ("altitude_montante", "m", "inferida pelos valores; não declarada; referência vertical não documentada"),
               "ALTITUDE_JUSANTE": ("altitude_jusante", "m", "inferida pelos valores; não declarada; referência vertical não documentada"), "ATIVO": ("ativo_no_cadastro", None, None),
               "COLETORFUNDOS": ("coletor_de_fundos", None, None), "LOCALIZACAO": ("localizacao", None, None), "DATAIMPLANTACAO": ("data_implantacao", "data", "milissegundos desde 1970 no serviço"),
               "ACESSO": ("acesso", None, None), "AJUSTE": ("ajuste", None, None), "DATACRIACAO": ("data_criacao_no_cadastro", "data", "idem"), "DATAATUALIZACAO": ("data_atualizacao_no_cadastro", "data", "idem"),
               "ENABLED": ("enabled", None, None), "EXT_DIGITAL": ("extensao_digital", "m", "inferida; não declarada")}
CAMPOS_PONTO = {"OBJECTID": ("id_origem", None, None), "TIPO": ("tipo_codigo", None, "códigos sem legenda no serviço"), "ESPELHO": ("espelho", None, None), "MATERIAL": ("material", None, None),
                "PROFUNDIDADE": ("profundidade", "m", "inferida pelos valores; não declarada"), "ALTITUDETAMPA": ("altitude_da_tampa", "m", "inferida pelos valores; não declarada; referência vertical não documentada"),
                "TIPOTAMPA": ("tipo_de_tampa", None, None), "DATAIMPLANTACAO": ("data_implantacao", "data", "milissegundos desde 1970 no serviço"), "DATACRIACAO": ("data_criacao_no_cadastro", "data", "idem"),
                "DATAATUALIZACAO": ("data_atualizacao_no_cadastro", "data", "idem"), "ENABLED": ("enabled", None, None)}
CAMPOS_BOMBA = {"fid": "id_origem", "name": "nome", "local": "local", "f__rea_prot": "area_protegida", "f__rea_cont": "area_de_contribuicao", "se____o_re": "secao", "configura_": "configuracao",
                "endere__o": "endereco", "descri____": "descricao", "capacidade": "capacidade_texto_original"}


def _texto(s: pd.Series) -> pd.Series:
    """Blank strings and the literal '<Null>' become missing; everything else is kept as received."""
    s = s.astype("object")
    vazio = ~aud.preenchido(s) | s.astype(str).str.strip().isin(["<Null>", "None", "nan"])
    return s.where(~vazio, None)


def _data(s: pd.Series) -> pd.Series:
    return pd.to_datetime(pd.to_numeric(s, errors="coerce"), unit="ms", errors="coerce")


def _padronizar(df: pd.DataFrame, campos: dict) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for orig, (novo, unidade, _) in campos.items():
        if orig not in df:
            continue
        s = df[orig]
        out[novo] = _data(s) if unidade == "data" else pd.to_numeric(s, errors="coerce") if unidade not in (None, "data") or orig == "OBJECTID" else _texto(s)
    return out


def _sinais(out: pd.DataFrame) -> pd.DataFrame:
    """Flag-only columns: the original values are never changed."""
    for orig, novo in (("ALTITUDE_MONTANTE", "altitude_montante"), ("ALTITUDE_JUSANTE", "altitude_jusante"), ("ALTITUDETAMPA", "altitude_da_tampa"), ("DECLIVIDADE", "declividade"),
                       ("PROFUNDIDADE", "profundidade"), ("INSERCAOMONTANTE", "insercao_montante"), ("INSERCAOJUSANTE", "insercao_jusante"), ("DIAMETRO", "diametro")):
        if novo in out:
            lo, hi = aud.FAIXAS[orig]
            out[f"{novo}_fora_da_faixa_plausivel"] = ((out[novo] < lo) | (out[novo] > hi)).fillna(False)
    for c in ("insercao_montante", "insercao_jusante", "profundidade"):
        if c in out:
            out[f"{c}_zero_possivel_ausencia"] = (out[c] == 0).fillna(False)                    # zero não prova profundidade nula: em muitas camadas é o valor de "sem dado"
    if "data_implantacao" in out:
        ano = out["data_implantacao"].dt.year
        out["data_implantacao_suspeita"] = ((ano < ANO_MIN) | (ano > ANO_MAX)).fillna(False)
    return out


def _duplicatas(geoms: gpd.GeoSeries, ids: pd.Series) -> pd.Series:
    """Id of the first record with the same geometry (normalised, 1 cm), or missing. Reversed lines count as the same drawing."""
    vals = geoms.values.copy()
    ruins = ~shapely.is_valid(vals)
    if ruins.any():                                                                         # set_precision falha em geometria inválida
        vals[ruins] = shapely.make_valid(vals[ruins])
    norm = shapely.normalize(shapely.set_precision(vals, 0.01))
    chave = pd.Series(shapely.to_wkb(norm), index=geoms.index)
    primeiro = ids.groupby(chave).transform("min")
    return primeiro.where(ids != primeiro)


def _valida(geoms: gpd.GeoSeries) -> pd.Series:
    x = shapely.get_coordinates(geoms.values)
    return pd.Series(shapely.is_valid(geoms.values) & ~shapely.is_empty(geoms.values), index=geoms.index) & bool(np.isfinite(x).all())


def _extremos(g) -> tuple:
    partes = g.geoms if g.geom_type == "MultiLineString" else [g]
    return partes[0].coords[0], partes[-1].coords[-1]


def _municipio_bbox(margem_m: float = 5000):
    m = gpd.read_parquet(RAIZ / "data/processed/municipality.parquet").to_crs(CRS)
    x0, y0, x1, y1 = m.total_bounds
    return x0 - margem_m, y0 - margem_m, x1 + margem_m, y1 + margem_m


def _manifesto_da_camada(nome: str, manifesto: Path) -> dict:
    ult = {}
    for s in ingest.load_manifest(manifesto)["sources"]:
        ult[s["path"]] = s
    return ult.get(f"data/raw/drenagem_poa/{nome}.json", {})


def registrar(arquivo: Path, entrada_extra: dict, manifesto: Path) -> dict:
    entrada = {"url": None, "path": str(arquivo.relative_to(RAIZ)) if arquivo.is_relative_to(RAIZ) else str(arquivo), "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "sha256": ingest.sha256_file(arquivo), "size_bytes": arquivo.stat().st_size, "source_reference_date": None, "processing_version": VERSAO, "crs": CRS, **entrada_extra}
    entrada["registered"] = ingest.register(manifesto, entrada)
    return entrada


def construir_redes(raw: Path, bbox) -> tuple:
    partes, qual = [], {}
    for nome, camada in REDES.items():
        d = aud.ler(nome)
        df = aud.tabela(d)
        out = _sinais(_padronizar(df, CAMPOS_REDE))
        out.insert(1, "camada_origem", camada)
        geoms = gpd.GeoSeries(aud.linhas(d), crs=CRS)
        out = gpd.GeoDataFrame(out, geometry=geoms, crs=CRS)
        out["comprimento_pela_geometria"] = out.geometry.length
        out["valida"] = _valida(out.geometry)
        x0, y0, x1, y1 = bbox
        b = out.geometry.bounds
        out["dentro_da_caixa_do_municipio"] = (b.minx >= x0) & (b.maxx <= x1) & (b.miny >= y0) & (b.maxy <= y1)
        partes.append(out)
    todos = pd.concat(partes, ignore_index=True)
    todos = gpd.GeoDataFrame(todos, geometry="geometry", crs=CRS)
    todos["duplicata_exata_de"] = np.nan
    for camada, idx in todos.groupby("camada_origem").groups.items():
        todos.loc[idx, "duplicata_exata_de"] = _duplicatas(todos.loc[idx, "geometry"], todos.loc[idx, "id_origem"]).values
    todos["usar_no_inventario"] = todos.valida & todos.dentro_da_caixa_do_municipio & todos.duplicata_exata_de.isna()
    return todos, qual


def evidencia_geometrica(redes: gpd.GeoDataFrame, pocos: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Per segment end: another segment end within the tolerance, a manhole within its tolerance. Geometric evidence only."""
    ext = [_extremos(g) for g in redes.geometry]
    ini, fim = np.array([e[0] for e in ext]), np.array([e[1] for e in ext])
    todos = np.vstack([ini, fim])
    arv = cKDTree(todos)
    pv = cKDTree(np.c_[pocos.geometry.x, pocos.geometry.y])
    outros = np.array([len(x) - 1 for x in arv.query_ball_point(todos, TOLERANCIA_EXTREMOS_M)]) > 0
    poco = np.array([len(x) for x in pv.query_ball_point(todos, TOLERANCIA_POCO_M)]) > 0
    n = len(redes)
    redes["evidencia_geometrica_inicio_coincide_com_outro_extremo"], redes["evidencia_geometrica_fim_coincide_com_outro_extremo"] = outros[:n], outros[n:]
    redes["evidencia_geometrica_inicio_perto_de_poco_de_visita"], redes["evidencia_geometrica_fim_perto_de_poco_de_visita"] = poco[:n], poco[n:]
    redes["evidencia_geometrica_ambos_extremos_ligados"] = (outros[:n] | poco[:n]) & (outros[n:] | poco[n:])
    return redes


def construir_pontos(nome: str, bbox) -> gpd.GeoDataFrame:
    d = aud.ler(nome)
    df = aud.tabela(d)
    out = _sinais(_padronizar(df, CAMPOS_PONTO))
    pts = aud.pontos(d)
    out = gpd.GeoDataFrame(out, geometry=gpd.points_from_xy(pts[:, 0], pts[:, 1]), crs=CRS)
    out["dentro_da_caixa_do_municipio"] = (out.geometry.x.between(bbox[0], bbox[2])) & (out.geometry.y.between(bbox[1], bbox[3]))
    out["valida"] = _valida(out.geometry)
    out["duplicata_exata_de"] = _duplicatas(out.geometry, out["id_origem"]).values
    out["usar_no_inventario"] = out.valida & out.dentro_da_caixa_do_municipio & out.duplicata_exata_de.isna()
    return out


def distancia_a_rede(pontos: gpd.GeoDataFrame, rede: gpd.GeoDataFrame) -> pd.Series:
    """Metres to the nearest segment of the operational network layer. A distance, never a connection: no segment id is attached."""
    ls = rede.geometry.values
    arv = STRtree(ls)
    idx = arv.nearest(pontos.geometry.values)
    return pd.Series(shapely.distance(pontos.geometry.values, ls[idx]), index=pontos.index)


def construir_bombas(bombas_projeto: list) -> gpd.GeoDataFrame:
    d = aud.ler("casas_de_bomba_ebap")
    df = aud.tabela(d)
    out = pd.DataFrame({novo: (pd.to_numeric(df[orig]) if novo == "id_origem" else _texto(df[orig])) for orig, novo in CAMPOS_BOMBA.items() if orig in df})
    pts = aud.pontos(d)
    out = gpd.GeoDataFrame(out, geometry=gpd.points_from_xy(pts[:, 0], pts[:, 1]), crs=CRS)
    out["capacidade_informada"] = out["capacidade_texto_original"].notna()
    para_utm = Transformer.from_crs(4674, 31982, always_xy=True).transform
    proj = {b["nome"]: para_utm(b["lon"], b["lat"]) for b in bombas_projeto}
    out["nome_no_projeto"] = out["nome"].isin(proj)
    out["distancia_ao_registro_do_projeto"] = [float(np.hypot(proj[n][0] - g.x, proj[n][1] - g.y)) if n in proj else np.nan for n, g in zip(out["nome"], out.geometry)]
    out["valida"] = _valida(out.geometry)
    out["duplicata_exata_de"] = _duplicatas(out.geometry, out["id_origem"]).values
    out["usar_no_inventario"] = out.valida & out.duplicata_exata_de.isna()
    return out


def qualidade(nome: str, gdf: gpd.GeoDataFrame, manifesto_camada: dict) -> dict:
    n = len(gdf)
    vazios = [c for c in gdf.columns if c != "geometry" and not (gdf[c].notna() & (gdf[c].astype(str).str.strip() != "")).any()]
    nulos = {c: round(float(gdf[c].isna().mean()), 4) for c in gdf.columns if c != "geometry" and gdf[c].dtype != bool and gdf[c].isna().any()}
    return {"camada": nome, "registros_na_fonte": manifesto_camada.get("feature_count_at_source"), "rejeitados_na_coleta_sem_geometria": manifesto_camada.get("feature_count_rejected_without_geometry"),
            "rejeitados_na_coleta_coordenada_nao_finita": manifesto_camada.get("feature_count_rejected_non_finite_geometry"), "registros_processados": n, "geometrias_validas": int(gdf.valida.sum()),
            "geometrias_invalidas": int((~gdf.valida).sum()), "fora_da_caixa_do_municipio": int((~gdf.get("dentro_da_caixa_do_municipio", pd.Series(True, index=gdf.index))).sum()),
            "duplicatas_exatas": int(gdf.duplicata_exata_de.notna().sum()), "usados_no_inventario": int(gdf.usar_no_inventario.sum()),
            "colunas_sem_nenhum_preenchimento": vazios, "fracao_de_nulos_por_coluna": nulos,
            "sinalizacoes": {c: int(gdf[c].sum()) for c in gdf.columns if c.endswith(("_fora_da_faixa_plausivel", "_zero_possivel_ausencia", "_suspeita"))}}


def gravar(gdf: gpd.GeoDataFrame, destino: Path, extra: dict, manifesto: Path) -> dict:
    destino.parent.mkdir(parents=True, exist_ok=True)
    gdf = gdf.sort_values([c for c in ("camada_origem", "id_origem") if c in gdf.columns]).reset_index(drop=True)
    gdf.to_parquet(destino, index=False)
    return registrar(destino, {"format": "GeoParquet", "feature_count": len(gdf), "origin": "derivado de data/raw/drenagem_poa por tools/processar_drenagem_poa.py", **extra}, manifesto)


def dicionario() -> dict:
    d = {}
    for rotulo, campos in (("rede_pluvial", CAMPOS_REDE), ("pontos", CAMPOS_PONTO)):
        d[rotulo] = {novo: {"campo_original": orig, "unidade": u, "origem_da_unidade": o} for orig, (novo, u, o) in campos.items()}
    d["casas_de_bomba"] = {novo: {"campo_original": orig, "unidade": None} for orig, novo in CAMPOS_BOMBA.items()}
    d["observacao"] = "Nenhum serviço da Prefeitura declara unidades nem referência vertical: as unidades acima são INFERIDAS pelos valores e pela consistência interna, e estão marcadas como tal."
    return d


def main(saida: Path = SAIDA, manifesto: Path = MANIFESTO) -> dict:
    bbox = _municipio_bbox()
    territorio = json.loads((RAIZ / "data/processed/territorio_poa.json").read_text())
    redes, _ = construir_redes(RAW, bbox)
    pocos = construir_pontos("poco_de_visita", bbox)
    bocas = construir_pontos("boca_de_lobo", bbox)
    redes = evidencia_geometrica(redes, pocos[pocos.usar_no_inventario])
    bocas["distancia_geometrica_a_rede_pluvial_m"] = distancia_a_rede(bocas, redes[(redes.camada_origem == "rede_pluvial") & redes.usar_no_inventario])
    bombas = construir_bombas(territorio["bombas"])
    entradas = {}
    for nome, gdf in (("rede_pluvial", redes), ("pocos_de_visita", pocos), ("bocas_de_lobo", bocas), ("casas_de_bomba", bombas)):
        fontes = {"rede_pluvial": ["rede_pluvial", "rede_pluvial_sem_acesso", "rede_pluvial_nao_interligada"], "pocos_de_visita": ["poco_de_visita"], "bocas_de_lobo": ["boca_de_lobo"], "casas_de_bomba": ["casas_de_bomba_ebap"]}[nome]
        entradas[nome] = gravar(gdf, saida / f"{nome}.parquet", {"inputs": [{"path": f"data/raw/drenagem_poa/{f}.json", "sha256": _manifesto_da_camada(f, manifesto).get("sha256")} for f in fontes]}, manifesto)
    q = {"versao_do_processamento": VERSAO, "crs": CRS, "tolerancias_m": {"extremos": TOLERANCIA_EXTREMOS_M, "poco_de_visita": TOLERANCIA_POCO_M},
         "rede_pluvial": {camada: qualidade(camada, redes[redes.camada_origem == camada].reset_index(drop=True), _manifesto_da_camada(camada, manifesto)) for camada in REDES},
         "pocos_de_visita": qualidade("poco_de_visita", pocos, _manifesto_da_camada("poco_de_visita", manifesto)), "bocas_de_lobo": qualidade("boca_de_lobo", bocas, _manifesto_da_camada("boca_de_lobo", manifesto)),
         "casas_de_bomba": qualidade("casas_de_bomba_ebap", bombas, _manifesto_da_camada("casas_de_bomba_ebap", manifesto)),
         "evidencia_geometrica_rede_pluvial_operacional": {c: round(float(redes.loc[(redes.camada_origem == "rede_pluvial") & redes.usar_no_inventario, c].mean()), 4)
                                                          for c in redes.columns if c.startswith("evidencia_geometrica_")},
         "bocas_de_lobo_distancia_geometrica": {"mediana_m": round(float(bocas.distancia_geometrica_a_rede_pluvial_m.median()), 2), "ate_2m": round(float((bocas.distancia_geometrica_a_rede_pluvial_m <= 2).mean()), 4),
                                                "acima_de_50m": int((bocas.distancia_geometrica_a_rede_pluvial_m > 50).sum()), "aviso": "distância geométrica; não é conexão hidráulica nem funcionamento"},
         "casas_de_bomba_detalhe": {"capacidade_informada": int(bombas.capacidade_informada.sum()), "registros": len(bombas), "mesmo_nome_no_projeto": int(bombas.nome_no_projeto.sum()),
                                    "distancia_maxima_ao_projeto_m": round(float(bombas.distancia_ao_registro_do_projeto.max()), 1), "somente_no_servico": bombas.loc[~bombas.nome_no_projeto, "nome"].tolist(),
                                    "somente_no_projeto": sorted(set(b["nome"] for b in territorio["bombas"]) - set(bombas["nome"]))},
         "classificacao_operacional_original_preservada": {"rede_pluvial": {"ativo_no_cadastro": redes.loc[redes.camada_origem == "rede_pluvial", "ativo_no_cadastro"].fillna("(vazio)").astype(str).value_counts().to_dict()},
                                                           "rede_pluvial_sem_acesso": {"acesso": redes.loc[redes.camada_origem == "rede_pluvial_sem_acesso", "acesso"].fillna("(vazio)").astype(str).value_counts().to_dict()},
                                                           "rede_pluvial_nao_interligada": {"ativo_no_cadastro": redes.loc[redes.camada_origem == "rede_pluvial_nao_interligada", "ativo_no_cadastro"].fillna("(vazio)").astype(str).value_counts().to_dict()}},
         "arquivos": {k: {"path": v["path"], "sha256": v["sha256"], "bytes": v["size_bytes"], "registros": v["feature_count"]} for k, v in entradas.items()},
         "limitacoes": ["Inventário cadastral: nenhuma capacidade, vazão, operação ou conectividade hidráulica é atribuída.", "A rede sem acesso e a não interligada não são tratadas como operacionais ou ativas.",
                        "Bocas de lobo não recebem identificador de trecho, e a distância geométrica não prova conexão nem funcionamento.", "Casas de bomba: só nome e posição; o campo de capacidade está vazio.",
                        "Unidades inferidas pelos valores; os serviços não as declaram nem documentam a referência vertical das altitudes."]}
    (saida / "dicionario_de_campos.json").write_text(json.dumps(dicionario(), ensure_ascii=False, indent=2))
    (saida / "qualidade_drenagem.json").write_text(json.dumps(q, ensure_ascii=False, indent=2, default=str))
    return q


if __name__ == "__main__":
    q = main(Path(sys.argv[1]) if len(sys.argv) > 1 else SAIDA)
    print(json.dumps({"arquivos": q["arquivos"]}, ensure_ascii=False, indent=1))
