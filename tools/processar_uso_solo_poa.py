"""Frente B e D, Fase 2: uso e ocupação do solo (Profill 2022) de TODA Porto Alegre, validado e agregado na grade de 30 m do DEM do projeto.

    PYTHONPATH=src python tools/processar_uso_solo_poa.py [pasta_de_saida]

Entrada: partes de data/raw/uso_do_solo_profill_2022/ (jsonl.gz, EPSG:31982), baixadas por tools/baixar_drenagem_poa.py.
Nunca carrega a base inteira na memória (a máquina tem 9 GB):
  1. PARTICIONAR: lê parte por parte, valida e grava cada polígono em UM arquivo Parquet por bloco de 3 km (pela posição do centroide), com a geometria preservada em WKB.
     Polígonos com mais de 1,5 km de largura ou altura (podem atravessar mais de um bloco vizinho) vão para a partição "grandes", lida em todos os blocos.
  2. RASTERIZAR: bloco a bloco, pinta as classes numa grade de 3 m (10 x 10 por célula) e soma as áreas por classe dentro de cada célula de 30 m da MESMA grade do DEM
     (a do pipeline de relevo: tools usam susceptibility.build_dem). A mesma pintura conta quantos polígonos cobrem cada ponto: sobreposição (>= 2) e lacuna (0, dentro do município).
Medidas de validade, duplicidade e área vêm dos polígonos (exatas, no CRS métrico); as áreas por célula, da pintura (precisão de 9 m² por ponto, sem viés, mas com ruído em feições pequenas:
o relatório mede a diferença por classe). O Copernicus não é reamostrado para resolução mais fina: a grade de saída tem o mesmo passo de 30 m.
Não há coeficiente de escoamento aqui: a camada só prepara AS ÁREAS por classe; os coeficientes estão em config/uso_solo_*.csv e o cálculo em flooding_mapping.escoamento.
"""
import gzip
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio.features
import shapely
from rasterio.enums import MergeAlg
from rasterio.transform import Affine

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flooding_mapping import ingest  # noqa: E402
from processar_drenagem_poa import registrar  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw" / "uso_do_solo_profill_2022"
SAIDA = RAIZ / "data" / "processed" / "uso_solo"
MANIFESTO = RAIZ / "data" / "raw" / "manifest.json"
CRS = "EPSG:31982"
VERSAO = "fase2-1"
ESQUEMA = pa.schema([("objectid", pa.int64()), ("classe", pa.string()), ("fitofisionomia", pa.string()), ("estagio", pa.string()), ("regiao", pa.string()), ("area_m2_fonte", pa.float64()),
                     ("area_m2_geometria", pa.float64()), ("valida", pa.bool_()), ("motivo_invalidez", pa.string()), ("duplicata_exata_de", pa.int64()), ("geometria", pa.binary())])


@dataclass(frozen=True)
class Grade:
    origem_x: float
    origem_y: float
    linhas: int
    colunas: int
    celula: float = 30.0
    bloco: int = 100        # células por lado de um bloco (3 km)
    sub: int = 10           # pontos por lado de uma célula na pintura (3 m)

    @property
    def transform(self) -> Affine:
        return Affine(self.celula, 0, self.origem_x, 0, -self.celula, self.origem_y)

    def indice(self, x, y):
        return np.floor((self.origem_y - np.asarray(y)) / self.celula).astype(int), np.floor((np.asarray(x) - self.origem_x) / self.celula).astype(int)

    @property
    def blocos(self):
        return [(i, j) for i in range(-(-self.linhas // self.bloco)) for j in range(-(-self.colunas // self.bloco))]


def grade_do_dem() -> Grade:
    """The grid of the project's terrain features: the transform that susceptibility.build_dem computes for the municipality."""
    import geopandas as gpd

    from flooding_mapping import config as c
    from flooding_mapping import susceptibility as s
    cfg = c.load_config()
    area = gpd.read_parquet(c.resolve("data/processed/municipality.parquet"))
    dem, tr = s.build_dem([c.resolve(cfg["sources"][k]["destino"]) for k in ("dem_s30", "dem_s31")], area, cfg["crs_metric"])
    return Grade(origem_x=tr.c, origem_y=tr.f, linhas=dem.shape[0], colunas=dem.shape[1], celula=abs(tr.a))


# ---------- leitura e geometria ----------
def ler_parte(caminho: Path):
    with gzip.open(caminho, "rt", encoding="utf-8") as f:
        for linha in f:
            yield json.loads(linha)


def poligono(aneis: list):
    """Esri rings -> shapely geometry. Clockwise rings are exteriors and counter-clockwise ones are holes; a feature with no clockwise ring keeps every ring as an exterior."""
    ext, bur = [], []
    for a in aneis:
        if len(a) < 4:
            continue
        xy = np.asarray(a, dtype=float)[:, :2]
        area = 0.5 * float(np.sum(xy[:-1, 0] * xy[1:, 1] - xy[1:, 0] * xy[:-1, 1]))
        (ext if area < 0 else bur).append(xy)
    if not ext:
        ext, bur = bur, []
    partes = [shapely.Polygon(e) for e in ext]
    for b in bur:
        pb = shapely.Polygon(b)
        ponto = pb.representative_point()
        for i, p in enumerate(partes):
            if p.contains(ponto):
                partes[i] = p.difference(pb)
                break
    partes = [p for g in partes for p in (g.geoms if g.geom_type == "MultiPolygon" else [g]) if not p.is_empty]
    return None if not partes else partes[0] if len(partes) == 1 else shapely.MultiPolygon(partes)


def _chave(g) -> bytes:
    return hashlib.blake2b(shapely.to_wkb(shapely.normalize(shapely.set_precision(g, 0.01))), digest_size=16).digest()


# ---------- passo 1: validar e particionar ----------
def particionar(partes: list, destino: Path, grade: Grade) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    for velho in destino.glob("bloco_*.parquet"):
        velho.unlink()
    escritores, primeiro = {}, {}
    est = {"lidos": 0, "sem_geometria_util": 0, "invalidos": 0, "motivos_de_invalidez": {}, "duplicatas_exatas": 0, "fora_da_grade": 0, "grandes": 0, "classes": {}, "por_parte": {}}
    limite_grande = grade.bloco * grade.celula / 2
    for parte in partes:
        linhas = []
        for f in ler_parte(parte):
            a, est["lidos"] = f["a"], est["lidos"] + 1
            g = poligono(f["g"].get("rings") or [])
            if g is None or g.is_empty:
                est["sem_geometria_util"] += 1
                continue
            valida = bool(shapely.is_valid(g))
            motivo = None if valida else str(shapely.is_valid_reason(g)).split("[")[0].strip()
            if not valida:
                est["invalidos"] += 1
                est["motivos_de_invalidez"][motivo] = est["motivos_de_invalidez"].get(motivo, 0) + 1
            reparada = g if valida else shapely.make_valid(g)                        # set_precision falha em geometria inválida: a chave e a área vêm da geometria reparada
            oid, chave = int(a["objectid"]), _chave(reparada)
            dup = primeiro.setdefault(chave, oid)
            dup = None if dup == oid else dup
            est["duplicatas_exatas"] += dup is not None
            classe = (a.get("classe") or "").strip() or "(sem classe)"
            area = float(reparada.area)                                              # a área de um polígono inválido vem da geometria reparada, a mesma que é pintada
            c = est["classes"].setdefault(classe, {"poligonos": 0, "area_m2_geometria": 0.0, "area_m2_fonte": 0.0, "invalidos": 0, "duplicatas_excluidas": 0, "area_m2_duplicatas_excluidas": 0.0})
            if dup is not None:                                                      # duplicata exata: fica no arquivo, marcada, mas não entra nas somas de área nem na pintura
                c["duplicatas_excluidas"] += 1
                c["area_m2_duplicatas_excluidas"] += area
            else:
                c["poligonos"] += 1
                c["area_m2_geometria"] += area
                c["area_m2_fonte"] += float(a.get("area_m2") or 0.0)
                c["invalidos"] += not valida
            x0, y0, x1, y1 = g.bounds
            if max(x1 - x0, y1 - y0) > limite_grande:
                bloco, est["grandes"] = "grandes", est["grandes"] + 1
            else:
                cx, cy = g.centroid.x, g.centroid.y
                i, j = grade.indice(cx, cy)
                bloco = f"bloco_{int(i) // grade.bloco:+03d}_{int(j) // grade.bloco:+03d}"
                if not (0 <= i < grade.linhas and 0 <= j < grade.colunas):
                    est["fora_da_grade"] += 1
            linhas.append((bloco, {"objectid": oid, "classe": classe, "fitofisionomia": (a.get("fitofision") or "").strip() or None, "estagio": (a.get("estagio") or "").strip() or None,
                                   "regiao": (a.get("regiao") or "").strip() or None, "area_m2_fonte": a.get("area_m2"), "area_m2_geometria": area, "valida": valida, "motivo_invalidez": motivo,
                                   "duplicata_exata_de": dup, "geometria": shapely.to_wkb(g)}))
        por_bloco = {}
        for bloco, reg in linhas:
            por_bloco.setdefault(bloco, []).append(reg)
        for bloco in sorted(por_bloco):
            if bloco not in escritores:
                escritores[bloco] = pq.ParquetWriter(destino / f"{bloco}.parquet", ESQUEMA, compression="zstd")
            escritores[bloco].write_table(pa.Table.from_pylist(por_bloco[bloco], schema=ESQUEMA))
        est["por_parte"][parte.name] = len(linhas)
    for w in escritores.values():
        w.close()
    est["arquivos_de_bloco"] = len(escritores)
    return est


# ---------- passo 2: rasterizar bloco a bloco ----------
def _candidatos(destino: Path, grade: Grade, i: int, j: int, janela: tuple) -> pd.DataFrame:
    quadros = []
    nomes = [f"bloco_{(i + di):+03d}_{(j + dj):+03d}" for di in (-1, 0, 1) for dj in (-1, 0, 1)] + ["grandes"]
    for n in nomes:
        arq = destino / f"{n}.parquet"
        if arq.exists():
            quadros.append(pq.read_table(arq, columns=["objectid", "classe", "valida", "duplicata_exata_de", "geometria"]).to_pandas())
    if not quadros:
        return pd.DataFrame(columns=["objectid", "classe", "valida", "duplicata_exata_de", "geometria", "g"])
    df = pd.concat(quadros, ignore_index=True)
    df = df[df["duplicata_exata_de"].isna()].reset_index(drop=True)                 # duplicatas exatas não são pintadas: contariam como sobreposição e como área em dobro
    g = shapely.from_wkb(df["geometria"].to_numpy())
    x0, y0, x1, y1 = janela
    b = shapely.bounds(g)
    ok = (b[:, 0] < x1) & (b[:, 2] > x0) & (b[:, 1] < y1) & (b[:, 3] > y0)
    df = df[ok].copy()
    df["g"] = g[ok]
    return df.sort_values("objectid").reset_index(drop=True)


def rasterizar(destino_blocos: Path, grade: Grade, municipio, codigos: dict) -> tuple:
    """Per 30 m cell: area of each class, overlapped area and gap area inside the municipality. Returns (cells table, city totals)."""
    S, n = grade.sub, grade.bloco
    ncl = len(codigos)
    linhas = []
    tot = {"area_por_classe_m2": np.zeros(ncl + 1), "sobreposicao_m2": 0.0, "lacuna_dentro_do_municipio_m2": 0.0, "area_do_municipio_m2": 0.0, "classificada_dentro_do_municipio_m2": 0.0,
           "classificada_fora_do_municipio_m2": 0.0, "blocos_com_lacuna": {}}
    pixel = (grade.celula / S) ** 2
    for i, j in grade.blocos:
        r0, c0 = i * n, j * n
        R, C = min(n, grade.linhas - r0), min(n, grade.colunas - c0)
        tr = Affine(grade.celula / S, 0, grade.origem_x + c0 * grade.celula, 0, -grade.celula / S, grade.origem_y - r0 * grade.celula)
        x0, y1 = tr.c, tr.f
        janela = (x0, y1 - R * grade.celula, x0 + C * grade.celula, y1)
        shp = (R * S, C * S)
        dentro = rasterio.features.rasterize([(municipio, 1)], out_shape=shp, transform=tr, fill=0, dtype="uint8").astype(bool)
        cand = _candidatos(destino_blocos, grade, i, j, janela)
        cod = np.zeros(shp, "uint8")
        cont = np.zeros(shp, "uint8")
        if len(cand):
            geoms = [g if v else shapely.make_valid(g) for g, v in zip(cand.g, cand.valida)]
            cod = rasterio.features.rasterize([(g, codigos.get(c, 0)) for g, c in zip(geoms, cand.classe)], out_shape=shp, transform=tr, fill=0, dtype="uint8")
            cont = rasterio.features.rasterize([(g, 1) for g in geoms], out_shape=shp, transform=tr, fill=0, merge_alg=MergeAlg.add, dtype="uint8")
        tot["area_do_municipio_m2"] += dentro.sum() * pixel
        tot["sobreposicao_m2"] += float((cont >= 2).sum() * pixel)
        lac = dentro & (cont == 0)
        tot["lacuna_dentro_do_municipio_m2"] += float(lac.sum() * pixel)
        tot["classificada_dentro_do_municipio_m2"] += float((dentro & (cont >= 1)).sum() * pixel)
        tot["classificada_fora_do_municipio_m2"] += float((~dentro & (cont >= 1)).sum() * pixel)
        if lac.any():
            tot["blocos_com_lacuna"][f"{i},{j}"] = float(lac.sum() * pixel)
        por_celula = lambda m: m.reshape(R, S, C, S).sum(axis=(1, 3))
        contagens = np.stack([por_celula(cod == k) for k in range(1, ncl + 1)], axis=-1)       # R x C x classes
        for k in range(ncl + 1):
            tot["area_por_classe_m2"][k] += float((cod == k).sum() * pixel) if k else 0.0
        a_dentro, a_sobre, a_lac = por_celula(dentro), por_celula(cont >= 2), por_celula(lac)
        usa = (a_dentro > 0) | (contagens.sum(axis=-1) > 0)
        rr, cc = np.nonzero(usa)
        if len(rr):
            tab = {"linha": rr + r0, "coluna": cc + c0, "x_centro": grade.origem_x + (cc + c0 + 0.5) * grade.celula, "y_centro": grade.origem_y - (rr + r0 + 0.5) * grade.celula,
                   "area_dentro_do_municipio_m2": a_dentro[rr, cc] * pixel, "area_classificada_m2": contagens[rr, cc].sum(axis=-1) * pixel, "area_sobreposta_m2": a_sobre[rr, cc] * pixel,
                   "area_lacuna_m2": a_lac[rr, cc] * pixel}
            for nome, k in codigos.items():
                tab[f"area_m2__{k:02d}"] = (contagens[rr, cc, k - 1] * pixel).astype("float32")
            linhas.append(pd.DataFrame(tab))
    celulas = pd.concat(linhas, ignore_index=True) if linhas else pd.DataFrame()
    celulas = celulas.astype({c: "float32" for c in celulas.columns if c.startswith(("area_", "x_", "y_"))}, errors="ignore")
    return celulas, tot


# ---------- orquestração ----------
def codigos_das_classes(classes) -> dict:
    return {c: k for k, c in enumerate(sorted(classes), start=1)}


def tratamento(classe: str, m1, m2) -> dict:
    return {"metodo1_fundamentado": bool(classe in set(m1.classe_original)),
            "cenarios_do_metodo2": sorted(set(m2[(m2.classe_original == classe) & (m2.natureza_do_valor != "fora_do_calculo_de_escoamento")].cenario)),
            "fora_do_calculo_de_escoamento": bool(((m2.classe_original == classe) & (m2.natureza_do_valor == "fora_do_calculo_de_escoamento")).any())}


def lacunas_contra_agua(celulas: pd.DataFrame, agua: "gpd.GeoDataFrame") -> dict:
    """How much of the unclassified area inside the municipality sits on known water (OSM polygons): the cell centre decides. Evidence, not proof of the cause."""
    lac = celulas[celulas.area_lacuna_m2 > 0]
    if lac.empty:
        return {"lacuna_m2": 0.0}
    agua = agua.to_crs(CRS)
    uni = agua[agua.geom_type.isin(["Polygon", "MultiPolygon"])].union_all()
    dentro = shapely.contains_xy(uni, lac.x_centro.to_numpy(), lac.y_centro.to_numpy())
    a = lac.area_lacuna_m2.to_numpy(dtype=float)
    resto = shapely.points(lac.x_centro.to_numpy()[~dentro], lac.y_centro.to_numpy()[~dentro])
    d = shapely.distance(resto, uni) if len(resto) else np.array([])
    ar = a[~dentro]
    return {"lacuna_m2": float(a.sum()), "celulas_com_lacuna": int(len(lac)), "lacuna_sobre_agua_osm_m2": float(a[dentro].sum()), "fracao_da_lacuna_sobre_agua_osm": round(float(a[dentro].sum() / a.sum()), 4),
            "lacuna_fora_da_agua_m2": float(ar.sum()), "fracao_da_lacuna_fora_da_agua_a_ate_100m_da_agua": round(float(ar[d <= 100].sum() / ar.sum()), 4) if len(ar) else None,
            "fonte_da_agua": "data/interim/water.parquet (polígonos de água do OpenStreetMap)",
            "leitura": "A maior parte da lacuna é água (o limite do município inclui parte do Guaíba, que o mapa de uso do solo não classifica). O restante não foi explicado: pendência de conferência visual."}


def complementar(saida: Path = SAIDA, agua: Path | None = None) -> dict:
    """Adds the gap-versus-water check to an already processed output, without redoing the 9-minute processing."""
    import geopandas as gpd
    q = json.loads((saida / "qualidade_uso_solo.json").read_text())
    celulas = pd.read_parquet(saida / "uso_solo_grade30m.parquet", columns=["x_centro", "y_centro", "area_lacuna_m2"])
    q["lacunas_contra_agua_osm"] = lacunas_contra_agua(celulas, gpd.read_parquet(agua or RAIZ / "data/interim/water.parquet"))
    (saida / "qualidade_uso_solo.json").write_text(json.dumps(q, ensure_ascii=False, indent=2, default=str))
    return q["lacunas_contra_agua_osm"]


def main(saida: Path = SAIDA, raw: Path = RAW, manifesto: Path = MANIFESTO) -> dict:
    import geopandas as gpd

    from flooding_mapping import escoamento
    grade = grade_do_dem()
    muni = gpd.read_parquet(RAIZ / "data/processed/municipality.parquet").to_crs(CRS)
    municipio = muni.union_all()
    partes = sorted(raw.glob("parte_*.jsonl.gz"))
    if not partes:
        sys.exit(f"nenhuma parte em {raw}: rode tools/baixar_drenagem_poa.py uso_do_solo_profill_2022")
    blocos = saida / "poligonos_por_bloco"
    est = particionar(partes, blocos, grade)
    codigos = codigos_das_classes(est["classes"])
    celulas, tot = rasterizar(blocos, grade, municipio, codigos)
    celulas = celulas.sort_values(["linha", "coluna"]).reset_index(drop=True)
    arq_grade = saida / "uso_solo_grade30m.parquet"
    celulas.to_parquet(arq_grade, index=False, compression="zstd")
    m1, m2 = escoamento.carregar_metodo1(), escoamento.carregar_cenarios()
    area_ref = float(muni.area.sum())
    area_poligonos = sum(c["area_m2_geometria"] for c in est["classes"].values())
    por_classe = {}
    for c, k in codigos.items():
        d = est["classes"][c]
        raster = float(tot["area_por_classe_m2"][k])
        por_classe[c] = {"codigo": k, **d, "area_km2": round(d["area_m2_geometria"] / 1e6, 3), "fracao_da_area_classificada": round(d["area_m2_geometria"] / area_poligonos, 5),
                         "area_m2_pintura_3m": raster, "diferenca_relativa_pintura_x_poligonos": round(raster / d["area_m2_geometria"] - 1, 4) if d["area_m2_geometria"] else None,
                         "diferenca_relativa_fonte_x_geometria": round(d["area_m2_fonte"] / d["area_m2_geometria"] - 1, 5) if d["area_m2_geometria"] else None, **tratamento(c, m1, m2)}
    cobertura_m1 = sum(v["area_m2_geometria"] for c, v in por_classe.items() if v["metodo1_fundamentado"])
    fora = sum(v["area_m2_geometria"] for v in por_classe.values() if v["fora_do_calculo_de_escoamento"])
    sem_nada = [c for c, v in por_classe.items() if not (v["metodo1_fundamentado"] or v["fora_do_calculo_de_escoamento"] or v["cenarios_do_metodo2"])]
    gerais = sorted(tot["blocos_com_lacuna"].items(), key=lambda kv: -kv[1])[:6]
    q = {"versao_do_processamento": VERSAO, "crs": CRS, "grade": {"origem_x": grade.origem_x, "origem_y": grade.origem_y, "linhas": grade.linhas, "colunas": grade.colunas, "celula_m": grade.celula,
                                                              "origem": "a mesma grade que susceptibility.build_dem calcula para o município (DEM Copernicus GLO-30 reprojetado a 30 m), sem reamostrar para resolução mais fina",
                                                              "pintura_m": grade.celula / grade.sub, "bloco_celulas": grade.bloco},
         "partes_lidas": len(partes), "poligonos_lidos": est["lidos"], "poligonos_processados": est["lidos"] - est["sem_geometria_util"], "rejeitados_sem_geometria_util": est["sem_geometria_util"],
         "geometrias_invalidas": est["invalidos"], "motivos_de_invalidez": est["motivos_de_invalidez"], "duplicatas_exatas": est["duplicatas_exatas"], "poligonos_grandes_em_particao_propria": est["grandes"],
         "centroides_fora_da_grade": est["fora_da_grade"], "classes": por_classe, "classes_sem_nenhum_tratamento": sem_nada, "classes_inesperadas": [c for c in por_classe if c == "(sem classe)"],
         "area_de_referencia_municipio_m2": area_ref, "area_classificada_pelos_poligonos_m2": area_poligonos, "fracao_da_referencia_classificada": round(area_poligonos / area_ref, 4),
         "pela_pintura": {"area_do_municipio_m2": tot["area_do_municipio_m2"], "classificada_dentro_do_municipio_m2": tot["classificada_dentro_do_municipio_m2"], "classificada_fora_do_municipio_m2": tot["classificada_fora_do_municipio_m2"],
                          "lacuna_dentro_do_municipio_m2": tot["lacuna_dentro_do_municipio_m2"], "sobreposicao_m2": tot["sobreposicao_m2"], "fracao_do_municipio_coberta": round(tot["classificada_dentro_do_municipio_m2"] / tot["area_do_municipio_m2"], 4),
                          "blocos_com_mais_lacuna_linha_coluna_m2": gerais},
         "cobertura_dos_metodos": {"metodo1_area_m2": cobertura_m1, "metodo1_fracao_da_area_classificada": round(cobertura_m1 / area_poligonos, 4), "fora_do_calculo_area_m2": fora,
                                   "fora_do_calculo_fracao": round(fora / area_poligonos, 4), "sem_coeficiente_fundamentado_area_m2": area_poligonos - cobertura_m1 - fora,
                                   "sem_coeficiente_fundamentado_fracao": round((area_poligonos - cobertura_m1 - fora) / area_poligonos, 4)},
         "grade_de_saida": {"arquivo": str(arq_grade.relative_to(RAIZ)) if arq_grade.is_relative_to(RAIZ) else str(arq_grade), "celulas": len(celulas), "colunas_de_area_por_classe": {f"area_m2__{k:02d}": c for c, k in codigos.items()}},
         "limitacoes": ["A escala 1:2.500 é a de produção do mapa (interpretação visual de ortoimagem de 2018 a 2021, 30 cm), não uma resolução nem uma garantia de precisão dos limites.",
                        "As áreas por célula vêm de uma pintura de 3 m: sem viés, mas com ruído nas feições pequenas; a diferença por classe contra a soma dos polígonos está em 'classes'.",
                        "Sobreposição e lacuna são medidas na pintura de 3 m, não por interseção exata de polígonos.",
                        "Nenhum coeficiente de escoamento é aplicado aqui, e a classe 'Jardins, Passeios ou Áreas semi urbanizadas' segue sem coeficiente único."]}
    water = RAIZ / "data/interim/water.parquet"
    if water.exists():
        q["lacunas_contra_agua_osm"] = lacunas_contra_agua(celulas, gpd.read_parquet(water))
    (saida / "classes_e_codigos.json").write_text(json.dumps({"codigos": codigos, "tratamento": {c: tratamento(c, m1, m2) for c in codigos}}, ensure_ascii=False, indent=2))
    (saida / "qualidade_uso_solo.json").write_text(json.dumps(q, ensure_ascii=False, indent=2, default=str))
    ultimas = {s["path"]: s for s in ingest.load_manifest(manifesto)["sources"]}
    entradas = [{"path": str(p.relative_to(RAIZ)) if p.is_relative_to(RAIZ) else str(p), "sha256": ultimas.get(str(p.relative_to(RAIZ)) if p.is_relative_to(RAIZ) else str(p), {}).get("sha256")} for p in partes]
    registrar(arq_grade, {"format": "Parquet (uma linha por célula de 30 m da grade do DEM)", "feature_count": len(celulas), "inputs": entradas,
                          "origin": "derivado de data/raw/uso_do_solo_profill_2022 por tools/processar_uso_solo_poa.py"}, manifesto)
    return q


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--complementar":
        print(json.dumps(complementar(), ensure_ascii=False, indent=1))
        sys.exit(0)
    q = main(Path(sys.argv[1]) if len(sys.argv) > 1 else SAIDA)
    print(json.dumps({k: q[k] for k in ("poligonos_lidos", "geometrias_invalidas", "duplicatas_exatas", "fracao_da_referencia_classificada", "cobertura_dos_metodos")}, ensure_ascii=False, indent=1))
