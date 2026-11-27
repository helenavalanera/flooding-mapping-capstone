"""Executa o motor da Fase 3 sobre Porto Alegre inteira e grava as saídas em data/processed/fase3/.

    PYTHONPATH=src python tools/executar_fase3.py [pasta_de_saida]

Entradas (todas da Fase 2 ou já existentes): grade de uso do solo de 30 m, tabelas de coeficientes (config/), DEM Copernicus pela mesma ``susceptibility.build_dem``, rede viária ``rede_poa.parquet``.
Saídas, todas com a natureza declarada em docs/fase3_motor.md:
  celulas_30m.parquet                          áreas equivalentes e acumulado a montante por célula (Nível 2, em m², independentes da chuva) e altura de preenchimento (Nível 1)
  trechos_nivel1_propensao_topografica.parquet indicador topográfico por trecho (altura de preenchimento: NÃO é volume nem profundidade)
  trechos_contribuicao_base.parquet            por trecho, em m² equivalentes: local e contribuição, e a cobertura a montante (grau de confiança)
  trechos_nivel2_cenarios.parquet              por trecho, chuva e pacote: volume potencial gerado (local) e contribuição potencial associada, em m³
O volume efetivamente transportado NÃO é calculado. Verificações antes de gravar: o acúmulo da floresta com peso 1 é idêntico a ``susceptibility.flow_accumulation`` no DEM real, e a massa se conserva.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from sklearn.metrics import average_precision_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auditar_drenagem_poa as aud  # noqa: E402
import experimento_modelos_alagamentos as exp  # noqa: E402
import experimento_sensibilidade_hidrologica as sens  # noqa: E402
from flooding_mapping.dados_restritos import ler_alagamentos  # noqa: E402
from flooding_mapping import config as cfgmod  # noqa: E402
from flooding_mapping import escoamento, ingest  # noqa: E402
from flooding_mapping import motor_acumulo as motor  # noqa: E402
from flooding_mapping.risco_trecho import COMPONENTES  # noqa: E402
from flooding_mapping import susceptibility as sus  # noqa: E402
from processar_drenagem_poa import registrar  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"
SAIDA = PROC / "fase3"
MANIFESTO = RAIZ / "data" / "raw" / "manifest.json"
VERSAO = "fase3-1"


def carregar_dem_e_grade() -> tuple:
    cfg = cfgmod.load_config()
    area = gpd.read_parquet(cfgmod.resolve("data/processed/municipality.parquet"))
    dem, tr = sus.build_dem([cfgmod.resolve(cfg["sources"][k]["destino"]) for k in ("dem_s30", "dem_s31")], area, cfg["crs_metric"])
    return dem.astype("float64"), motor.GradeRaster(origem_x=tr.c, origem_y=tr.f, linhas=dem.shape[0], colunas=dem.shape[1], celula=abs(tr.a))


def mascara_de_agua(celulas: pd.DataFrame, grade: motor.GradeRaster, par: dict) -> np.ndarray:
    """Cells that are at least half unclassified AND whose centre falls on OSM water: a large water body is an outlet, not a bowl the depression filling would flood."""
    m = np.zeros((grade.linhas, grade.colunas), bool)
    sel = celulas[celulas.area_lacuna_m2 >= par["lacuna_minima_m2"]]
    ok = np.ones(len(sel), bool)
    agua = PROC.parent / "interim" / "water.parquet"
    if par.get("exigir_agua_osm") and agua.exists():
        w = gpd.read_parquet(agua).to_crs(31982)
        ok = shapely.contains_xy(w[w.geom_type.isin(["Polygon", "MultiPolygon"])].union_all(), sel.x_centro.to_numpy(), sel.y_centro.to_numpy())
    m[sel.linha.to_numpy()[ok], sel.coluna.to_numpy()[ok]] = True
    return m


def trechos_em_utm(rede: pd.DataFrame) -> pd.DataFrame:
    para_utm = Transformer.from_crs(4326, 31982, always_xy=True).transform
    x0, y0 = para_utm(rede.lon0.to_numpy(), rede.lat0.to_numpy())
    x1, y1 = para_utm(rede.lon1.to_numpy(), rede.lat1.to_numpy())
    return pd.DataFrame({"segmento_id": rede.segmento_id.to_numpy(), "x0": x0, "y0": y0, "x1": x1, "y1": y1})


def comparar_com_registros(rede: pd.DataFrame, nivel1: pd.DataFrame, base: pd.DataFrame, raio: float) -> dict:
    """EXPLORATORY and qualitative: where do the flooded segments of 2013-2014 (no hour, no rain) sit in the rankings? Not a validation: the engine is conditioned on rain, the records are not.

    Uses the SAME sample as tools/experimento_modelos_alagamentos.py (segments with the five terrain components, labels on that subset), so the numbers can sit beside the earlier ones.
    """
    coords = ler_alagamentos()
    amostra = (~rede[COMPONENTES].isna().any(axis=1) & rede.percentil.notna()).to_numpy()
    g = rede[amostra].reset_index(drop=True)
    y_amostra = exp.rotular(g, coords, raio)
    candidatos = {"regra_atual_percentil": g.percentil.to_numpy(float), "nivel1_altura_de_preenchimento_max": nivel1.altura_de_preenchimento_max_m.to_numpy()[amostra],
                  "nivel2_contribuicao_m1_max": base.contrib_aeq_m1_max_m2.to_numpy()[amostra], "nivel2_contribuicao_analoga_max": base.contrib_aeq_analoga_max_m2.to_numpy()[amostra],
                  "nivel2_contribuicao_limites_max": base.contrib_aeq_limites_max_m2.to_numpy()[amostra]}
    comum = np.all([np.isfinite(v) for v in candidatos.values()], axis=0)
    y = y_amostra[comum]
    escores = {k: v[comum] for k, v in candidatos.items()}
    grupos = exp.blocos(g)[comum]
    # a mesma régua do experimento de sensibilidade: ganho de precisão média sobre a regra atual, bootstrap pareado por trecho, por blocos de positivos e por blocos completos
    r1 = sens.comparar(y, escores, "regra_atual_percentil", np.random.default_rng(7), 2000)
    r2 = sens.comparar(y, escores, "regra_atual_percentil", np.random.default_rng(7), 2000, grupos)
    r3 = sens.comparar(y, escores, "regra_atual_percentil", np.random.default_rng(7), 2000, grupos, completo=True)
    res = sens._conservador(r1, r2, "regra_atual_percentil", r3)
    out = {"amostra_do_experimento_anterior": {"trechos": int(amostra.sum()), "positivos": int(y_amostra.sum())}, "segmentos_comparados": int(comum.sum()), "positivos_com_valor": int(y.sum()),
           "positivos_sem_valor_no_motor": int(y_amostra.sum() - y.sum()), "taxa_base": round(float(y.mean()), 5), "criterio": "ganho de precisão média >= 10% e limite inferior do IC95% do ganho > 0, por trecho, por blocos de positivos e por blocos completos",
           "metricas": {}}
    for nome in candidatos:
        x = res[nome]
        out["metricas"][nome] = {"auc": x["auc"], "precisao_media": x["precisao_media"], "ic95_precisao_media": x["ic95_precisao_media"],
                                 **({"ganho_sobre_a_regra": x["ganho_sobre_a_referencia"], "ic95_ganho_por_trecho": x["ic95_ganho"], "ic95_ganho_por_blocos": x["ic95_ganho_por_blocos"],
                                     "ic95_ganho_por_blocos_completos": x["ic95_ganho_por_blocos_completo"], "atende_criterio": x["atende_criterio"]} if nome != "regra_atual_percentil" else {})}
    out["leitura"] = ("Comparação exploratória: os registros são de 2013-2014, sem horário e sem chuva, e o motor é condicionado à chuva; serve para discutir plausibilidade, não valida o motor. "
                      "Diferença pequena ou intervalo que inclui zero não é evidência de superioridade, e a regra atual não é substituída.")
    return out


def sobrepor_cprm(rede: pd.DataFrame, base: pd.DataFrame) -> dict:
    """Qualitative overlay on the CPRM mapped flood risk (context only, never a label): where do the segments inside each risk class sit in the contribution ranking?"""
    d = aud.ler("risco_inundacao_cprm")
    pol = [shapely.make_valid(p) if not p.is_valid else p for p in aud.poligonos(d)]
    classe = tabela_classe = aud.tabela(d)["classe"].astype(str).tolist()
    meio = Transformer.from_crs(4326, 31982, always_xy=True).transform
    mx, my = meio(((rede.lon0 + rede.lon1) / 2).to_numpy(), ((rede.lat0 + rede.lat1) / 2).to_numpy())
    pts = shapely.points(mx, my)
    arv = shapely.STRtree(pol)
    par = arv.query(pts, predicate="within")
    rotulo = np.full(len(rede), "fora de risco mapeado", dtype=object)
    ordem = {"Baixa": 0, "Médio": 1, "Alto": 2}
    nivel = np.full(len(rede), -1)
    for i, j in zip(par[0], par[1]):
        k = ordem.get(classe[j], -1)
        if k > nivel[i]:
            nivel[i], rotulo[i] = k, classe[j]
    v = base.contrib_aeq_m1_max_m2.to_numpy()
    pct = pd.Series(v).rank(pct=True).to_numpy() * 100
    out = {"segmentos": int(len(rede)), "por_classe": {}}
    for r in ["Alto", "Médio", "Baixa", "fora de risco mapeado"]:
        m = rotulo == r
        ok = m & np.isfinite(pct)
        out["por_classe"][r] = {"segmentos": int(m.sum()), "percentil_mediano_da_contribuicao_m1_max": round(float(np.median(pct[ok])), 1) if ok.any() else None}
    out["leitura"] = "Risco mapeado (modelagem validada em campo, 2012-2014) é contexto: não é rótulo, ocorrência histórica nem simulação. A classe Alto cobre cerca da metade da cidade, então discrimina pouco."
    return out


def descrever(base: pd.DataFrame, nivel2: pd.DataFrame, nivel1: pd.DataFrame) -> dict:
    q = [0.5, 0.9, 0.99]
    sel = nivel2[(nivel2.p_mm == 30)]
    out = {"nivel2_p30": {}}
    for pk, g in sel.groupby("pacote"):
        out["nivel2_p30"][pk] = {c: {f"q{int(100 * k)}": float(np.nanquantile(g[c], k)) for k in q} for c in ("v_gerado_local_max_m3", "contrib_potencial_max_m3")}
    out["fracoes_a_montante_medianas"] = {c: round(float(np.nanmedian(base[c])), 4) for c in base.columns if c.startswith("fracao_montante_")}
    out["nivel1"] = {"trechos_com_valor": int(nivel1.altura_de_preenchimento_max_m.notna().sum()), "altura_de_preenchimento_max_m_quantis": {f"q{int(100 * k)}": round(float(np.nanquantile(nivel1.altura_de_preenchimento_max_m, k)), 4) for k in (0.5, 0.9, 0.99)},
                     "trechos_com_preenchimento_zero": int((nivel1.altura_de_preenchimento_max_m == 0).sum())}
    return out


def main(saida: Path = SAIDA, manifesto: Path = MANIFESTO) -> dict:
    cfg = json.loads(json.dumps(cfgmod.load_config(RAIZ / "config/fase3_motor.yaml")))
    saida.mkdir(parents=True, exist_ok=True)
    dem, grade = carregar_dem_e_grade()
    grade_uso = PROC / "uso_solo" / "uso_solo_grade30m.parquet"
    celulas = pd.read_parquet(grade_uso)
    classes = json.loads((PROC / "uso_solo" / "classes_e_codigos.json").read_text())["codigos"]
    rede = pd.read_parquet(PROC / "rede_poa.parquet", columns=["segmento_id", "lon0", "lat0", "lon1", "lat1", "percentil", "drive", "walk", *COMPONENTES])
    mascara = mascara_de_agua(celulas, grade, cfg["exutorio_por_agua"])
    r = motor.executar(dem, grade, celulas, classes, escoamento.carregar_metodo1(), escoamento.carregar_cenarios(), trechos_em_utm(rede), precipitacoes_mm=cfg["precipitacoes_mm"],
                       mascara_exutorio=mascara, passo_m=cfg["passo_da_pegada_m"])
    arv = r["arvore"]
    ref = sus.flow_accumulation(r["preenchido"]).ravel()
    unidade = arv.acumular(np.ones(grade.n))
    verif = {"acumulo_com_peso_1_identico_a_susceptibility_flow_accumulation": bool(np.array_equal(unidade[arv.valida], ref[arv.valida])), "celulas_comparadas": int(arv.valida.sum()),
             "conservacao_de_massa_erro_relativo_maximo": r["relatorio"]["conservacao_de_massa"]["erro_relativo_maximo"]}
    if not verif["acumulo_com_peso_1_identico_a_susceptibility_flow_accumulation"] or verif["conservacao_de_massa_erro_relativo_maximo"] > 1e-9:
        raise SystemExit(f"verificação do núcleo de fluxo falhou: {verif}")
    seg_p, cel_p = r["pegada"]
    com_par = np.bincount(seg_p, minlength=len(rede)) > 0
    com_dado = np.bincount(seg_p[arv.valida[cel_p]], minlength=len(rede)) > 0
    diag_pegada = {"trechos": int(len(rede)), "com_celulas_com_dados": int(com_dado.sum()), "fora_da_grade_sem_nenhuma_celula": int((~com_par).sum()),
                   "so_em_celulas_sem_dado_ou_agua_mascarada": int((com_par & ~com_dado).sum())}
    for nome, tab in (("celulas_30m", r["celulas"]), ("trechos_nivel1_propensao_topografica", r["nivel1"]), ("trechos_contribuicao_base", r["base"]), ("trechos_nivel2_cenarios", r["nivel2"])):
        tab.to_parquet(saida / f"{nome}.parquet", index=False, compression="zstd")
    entradas = {"uso_solo_grade30m": ingest.sha256_file(grade_uso), "rede_poa": ingest.sha256_file(PROC / "rede_poa.parquet"),
                "metodo1": ingest.sha256_file(RAIZ / escoamento.METODO1), "metodo2": ingest.sha256_file(RAIZ / escoamento.METODO2), "config": ingest.sha256_file(RAIZ / "config/fase3_motor.yaml")}
    arquivos = {}
    for nome, tab in (("celulas_30m", r["celulas"]), ("trechos_nivel1_propensao_topografica", r["nivel1"]), ("trechos_contribuicao_base", r["base"]), ("trechos_nivel2_cenarios", r["nivel2"])):
        e = registrar(saida / f"{nome}.parquet", {"format": "Parquet", "feature_count": len(tab), "origin": "gerado por tools/executar_fase3.py (motor flooding_mapping.motor_acumulo)", "inputs": entradas, "processing_version": VERSAO}, manifesto)
        arquivos[nome] = {"path": e["path"], "sha256": e["sha256"], "linhas": len(tab), "bytes": e["size_bytes"]}
    rel = {"versao": VERSAO, "crs": "EPSG:31982", "entradas_sha256": entradas, "config": cfg, "verificacoes_do_nucleo": verif, "pegadas_dos_trechos": diag_pegada, "motor": {k: v for k, v in r["relatorio"].items()},
           "descricao": descrever(r["base"], r["nivel2"], r["nivel1"]), "comparacao_exploratoria_com_os_registros": comparar_com_registros(rede, r["nivel1"], r["base"], cfg["comparacao_exploratoria"]["raio_do_rotulo_m"]),
           "sobreposicao_qualitativa_com_cprm": sobrepor_cprm(rede, r["base"]), "arquivos": arquivos,
           "limitacoes": ["Chuva uniforme e hipotética: ela escala o volume, mas não diferencia ruas. O resultado é condicionado ao cenário, não é previsão.",
                          "Só 17,3% da área classificada tem coeficiente fundamentado (Método 1); o resto depende de cenários, e a fração a montante coberta por cada pacote vai em cada trecho.",
                          "O volume efetivamente transportado, o retido, a profundidade e a duração NÃO são calculados.", "A altura de preenchimento é indicador topográfico: o Copernicus (DSM de 30 m, erro médio de 2,18 m contra marcos) não permite lê-la em metros nem como volume.",
                          "Valores por trecho não são somáveis entre trechos (bacias vizinhas se sobrepõem); o total da cidade existe só como soma das células.",
                          "A pegada do trecho (células atravessadas) pode perder células cortadas por cordas menores que o passo de amostragem.", "O inventário de drenagem não entra no cálculo: sem capacidade, sem conexões confirmadas."]}
    (saida / "relatorio_execucao.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2, default=str))
    (RAIZ / "reports/qa/fase3_execucao.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2, default=str))
    return rel


if __name__ == "__main__":
    rel = main(Path(sys.argv[1]) if len(sys.argv) > 1 else SAIDA)
    print(json.dumps({"verificacoes": rel["verificacoes_do_nucleo"], "trechos": rel["motor"]["trechos"], "com_pegada_valida": rel["motor"]["trechos_com_pegada_valida"]}, ensure_ascii=False, indent=1))
