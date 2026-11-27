"""Pipeline GeoAI da Fase 5, em etapas independentes e repetíveis.

    PYTHONPATH=src .venv/bin/python tools/executar_geoai.py cenas      # consulta o catálogo e mede a qualidade de cada cena no município (lê só a SCL)
    PYTHONPATH=src .venv/bin/python tools/executar_geoai.py baixar     # baixa o recorte das cenas escolhidas (cache fora do Git)
    PYTHONPATH=src .venv/bin/python tools/executar_geoai.py atributos  # composição mediana e atributos na grade de 30 m
    PYTHONPATH=src .venv/bin/python tools/executar_geoai.py aef-baixar     # Experimento B: recorte dos embeddings AlphaEarth (bucket público)
    PYTHONPATH=src .venv/bin/python tools/executar_geoai.py aef-atributos  # embeddings agregados à grade de 30 m
    PYTHONPATH=src .venv/bin/python tools/executar_geoai.py avaliar    # validação espacial, métricas, COG e manifesto

Entradas: config/geoai.yaml, data/processed/uso_solo/* (rótulos da Profill e grade), data/processed/municipality.parquet. Nada do motor é lido ou alterado.
"""
import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402

from flooding_mapping import config as cfgmod  # noqa: E402
from flooding_mapping.geoai import imagens as im  # noqa: E402

log = logging.getLogger("geoai")


def carregar() -> tuple[dict, dict, Path, Path]:
    cfg = cfgmod.load_config(RAIZ / "config/geoai.yaml")
    q = json.loads((RAIZ / "data/processed/uso_solo/qualidade_uso_solo.json").read_text())
    cache, saida = RAIZ / cfg["diretorios"]["cache"], RAIZ / cfg["diretorios"]["saida"]
    cache.mkdir(parents=True, exist_ok=True)
    saida.mkdir(parents=True, exist_ok=True)
    return cfg, q, cache, saida


def bbox_lonlat(q: dict) -> list[float]:
    from pyproj import Transformer
    g = q["grade"]
    x0, y0 = g["origem_x"], g["origem_y"]
    x1, y1 = x0 + g["colunas"] * g["celula_m"], y0 - g["linhas"] * g["celula_m"]
    t = Transformer.from_crs(q["crs"], 4326, always_xy=True)
    pts = [t.transform(x, y) for x in (x0, x1) for y in (y0, y1)]
    return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]


def etapa_cenas(cfg: dict, q: dict, cache: Path) -> None:
    ci = cfg["imagens"]
    itens = im.consultar_stac(ci["stac_url"], ci["colecao"], bbox_lonlat(q), ci["inicio"], ci["fim"])
    unicos = im.deduplicar(itens)
    candidatos = [i for i in unicos if i["properties"]["eo:cloud_cover"] <= ci["nuvem_maxima_do_tile_pct"]]
    tiles = sorted({i["properties"]["grid:code"] for i in itens})
    log.info("catálogo: %d itens, %d aquisições distintas, %d com nuvem do tile <= %s%%; tiles %s", len(itens), len(unicos), len(candidatos), ci["nuvem_maxima_do_tile_pct"], tiles)
    if len(tiles) != 1:
        raise SystemExit(f"mais de um tile cobre o município: {tiles}")
    red = candidatos[0]["assets"]["red"]
    forma, transf, crs = red["proj:shape"], red["proj:transform"], f"EPSG:{candidatos[0]['properties']['proj:epsg']}"
    j = im.janela_do_municipio(q["grade"], q["crs"], crs, transf, tuple(forma), ci["margem_m"])
    mun = gpd.read_parquet(cfgmod.resolve("data/processed/municipality.parquet")).to_crs(crs).union_all()
    mascara = im.mascara_do_municipio(mun, j, transf)
    avaliadas, t0 = [], time.time()
    for k, it in enumerate(candidatos):
        try:
            scl = im.ler_janela(it["assets"][ci["banda_scl"]]["href"], j, 2)
        except Exception as e:  # noqa: BLE001  cena indisponível: registra e segue
            log.warning("SCL ilegível em %s: %s", it["id"], e)
            continue
        v = im.pixels_validos(scl, ci["scl_validas"], ci["scl_nuvem_e_sombra"], ci["dilatar_nuvem_px_20m"])
        p = it["properties"]
        avaliadas.append({"id": it["id"], "datetime": p["datetime"], "nuvem_tile_pct": p["eo:cloud_cover"], "linha_de_processamento": p.get("s2:processing_baseline"),
                          "valido_no_municipio": float((v & mascara).sum() / mascara.sum()), "sem_dado_no_municipio": float(((scl == 0) & mascara).sum() / mascara.sum())})
        if k % 25 == 0:
            log.info("%d/%d cenas medidas (%.0f s)", k + 1, len(candidatos), time.time() - t0)
    escolhidas = im.escolher_cenas(avaliadas, ci["valido_minimo_no_municipio"], ci["maximo_de_cenas"])
    ids = {c["id"] for c in escolhidas}
    por_id = {i["id"]: i for i in candidatos}
    out = {"tile": tiles[0], "crs": crs, "proj_transform": transf, "proj_shape": forma, "janela": j.__dict__, "periodo": [ci["inicio"], ci["fim"]], "consulta_em": time.strftime("%Y-%m-%d"),
           "itens_no_catalogo": len(itens), "aquisicoes_distintas": len(unicos), "candidatas": len(candidatos), "medidas": len(avaliadas), "avaliadas": avaliadas,
           "escolhidas": [c["id"] for c in escolhidas], "itens_escolhidos": [por_id[i] for i in ids]}
    (cache / "cenas.json").write_text(json.dumps(out, indent=1))
    v = np.array([a["valido_no_municipio"] for a in avaliadas])
    log.info("cenas medidas %d | válido >= %.0f%%: %d | escolhidas %d", len(avaliadas), 100 * ci["valido_minimo_no_municipio"], int((v >= ci["valido_minimo_no_municipio"]).sum()), len(escolhidas))


def etapa_baixar(cfg: dict, q: dict, cache: Path) -> None:
    ci = cfg["imagens"]
    cat = json.loads((cache / "cenas.json").read_text())
    j = im.Janela(**cat["janela"])
    pasta = cache / "cenas"
    regs, t0 = [], time.time()
    for k, it in enumerate(sorted(cat["itens_escolhidos"], key=lambda i: i["properties"]["datetime"])):
        regs.append(im.baixar_cena(it, j, ci, pasta))
        log.info("%d/%d %s (%.0f s)", k + 1, len(cat["itens_escolhidos"]), it["id"], time.time() - t0)
    (cache / "registros.json").write_text(json.dumps(regs, indent=1))
    tam = sum(f.stat().st_size for f in pasta.rglob("*.npy"))
    log.info("%d cenas em %s, %.2f GB em disco", len(regs), pasta, tam / 1e9)


def etapa_atributos(cfg: dict, q: dict, cache: Path, saida: Path) -> None:
    from pyproj import Transformer
    from flooding_mapping.geoai import atributos as at
    cat = json.loads((cache / "cenas.json").read_text())
    regs = im.calibrar_deslocamentos(cache / "cenas", json.loads((cache / "registros.json").read_text()))
    (cache / "registros.json").write_text(json.dumps(regs, indent=1))
    log.info("deslocamento radiométrico efetivo por cena: %s (declarado: %s)", sorted({r["deslocamento_conferido"]["efetivo"] for r in regs}), sorted({r["deslocamento_conferido"]["declarado"] for r in regs}))
    j = im.Janela(**cat["janela"])
    g = q["grade"]
    x, y = Transformer.from_crs(q["crs"], cat["crs"], always_xy=True).transform(g["origem_x"], g["origem_y"])
    desloc = (x - g["origem_x"], y - g["origem_y"])
    if max(abs(desloc[0]), abs(desloc[1])) > 2.0:
        raise SystemExit(f"o CRS do tile difere do da grade em mais de 2 m ({desloc}); reprojetar antes de agregar")
    log.info("deslocamento entre %s e %s na origem da grade: %.3f m, %.3f m (desprezível, aplicado)", q["crs"], cat["crs"], *desloc)
    t0 = time.time()
    atrib, resumo = at.compor_e_agregar(cache / "cenas", regs, j, cat["proj_transform"], g, desloc, cfg["imagens"])
    resumo.update({"tile": cat["tile"], "crs_das_imagens": cat["crs"], "crs_da_grade": q["crs"], "deslocamento_crs_m": list(desloc), "segundos": round(time.time() - t0, 1),
                   "cenas_ids": [r["id"] for r in regs], "linhas_de_processamento": sorted({r["linha_de_processamento"] for r in regs})})
    destino = at.salvar(saida, atrib, resumo)
    cob = np.isfinite(atrib[..., at.NOMES.index("red")]).mean()
    log.info("atributos %s %s gravados em %s (%.0f s); células com imagem: %.1f%%", atrib.shape, atrib.dtype, destino, time.time() - t0, 100 * cob)


def caixa_em_utm(q: dict, crs_alvo: str, margem_m: float) -> tuple[float, float, float, float]:
    from pyproj import Transformer
    g = q["grade"]
    x0, y0 = g["origem_x"], g["origem_y"]
    x1, y1 = x0 + g["colunas"] * g["celula_m"], y0 - g["linhas"] * g["celula_m"]
    t = Transformer.from_crs(q["crs"], crs_alvo, always_xy=True)
    pts = [t.transform(x, y) for x in (x0, x1) for y in (y0, y1)]
    return (min(p[0] for p in pts) - margem_m, min(p[1] for p in pts) - margem_m, max(p[0] for p in pts) + margem_m, max(p[1] for p in pts) + margem_m)


def etapa_aef_baixar(cfg: dict, q: dict, cache: Path) -> None:
    ca = cfg["alphaearth"]
    caixa = caixa_em_utm(q, "EPSG:32722", ca["margem_m"])
    lista = im.listar_arquivos_aef(ca["ano"], ca["zona"])
    cobrem = im.arquivos_aef_que_cobrem(lista, caixa)
    log.info("AlphaEarth %s %s: %d arquivos no bucket, %d cobrem o município: %s", ca["ano"], ca["zona"], len(lista), len(cobrem), [(c["nome"].split("/")[-1], round(c["bytes"] / 1e9, 2)) for c in cobrem])
    if not cobrem or any(c["dtype"] != "int8" or c["bandas"] != 64 or c["crs"] != "EPSG:32722" for c in cobrem):
        raise SystemExit("arquivos do bucket fora do formato esperado (64 bandas int8, EPSG:32722)")
    pasta = cache / "alphaearth"
    pasta.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    meta = im.baixar_embeddings([c["nome"] for c in cobrem], caixa, pasta / f"embeddings_{ca['ano']}.npy")
    meta.update({"ano": ca["ano"], "zona": ca["zona"], "crs": "EPSG:32722", "caixa_utm": list(caixa), "consulta_em": time.strftime("%Y-%m-%d"), "segundos": round(time.time() - t0, 1), "atribuicao": im.AEF_ATRIBUICAO,
                 "licenca": "CC-BY 4.0", "bytes_dos_arquivos_de_origem": {c["nome"]: c["bytes"] for c in cobrem}})
    (pasta / f"embeddings_{ca['ano']}.json").write_text(json.dumps(meta, indent=1))
    log.info("embeddings %s gravados (%.0f s): %d x %d x 64", ca["ano"], time.time() - t0, meta["altura"], meta["largura"])


def etapa_aef_atributos(cfg: dict, q: dict, cache: Path, saida: Path) -> None:
    from pyproj import Transformer
    from flooding_mapping.geoai import atributos as at
    ca = cfg["alphaearth"]
    meta = json.loads((cache / "alphaearth" / f"embeddings_{ca['ano']}.json").read_text())
    g = q["grade"]
    x, y = Transformer.from_crs(q["crs"], meta["crs"], always_xy=True).transform(g["origem_x"], g["origem_y"])
    desloc = (x - g["origem_x"], y - g["origem_y"])
    if max(abs(desloc[0]), abs(desloc[1])) > 2.0:
        raise SystemExit(f"o CRS do bucket difere do da grade em mais de 2 m ({desloc})")
    t0 = time.time()
    emb = at.agregar_embeddings(cache / "alphaearth" / f"embeddings_{ca['ano']}.npy", meta, g, desloc)
    np.save(saida / f"aef_30m_{ca['ano']}.npy", emb)
    log.info("embeddings por célula %s gravados (%.0f s); células com dado: %.1f%%", emb.shape, time.time() - t0, 100 * float(np.isfinite(emb[..., 0]).mean()))


def sha256(p: Path) -> str:
    return im._sha256(p)


def versoes() -> dict:
    from importlib.metadata import version
    return {n: version(n) for n in ("numpy", "scipy", "scikit-learn", "rasterio", "geopandas", "shapely", "pyproj", "pandas", "pyarrow", "matplotlib", "pyrosm")} | {"python": sys.version.split()[0]}


def gravar_cog(destino: Path, bandas: list[tuple[str, np.ndarray]], grade: dict, crs: str, tags: dict) -> None:
    import rasterio
    import rasterio.shutil
    from rasterio.transform import from_origin
    tmp = destino.with_suffix(".tmp.tif")
    perfil = {"driver": "GTiff", "height": grade["linhas"], "width": grade["colunas"], "count": len(bandas), "dtype": "float32", "crs": crs, "nodata": np.nan,
              "transform": from_origin(grade["origem_x"], grade["origem_y"], grade["celula_m"], grade["celula_m"])}
    with rasterio.open(tmp, "w", **perfil) as dst:
        for i, (nome, a) in enumerate(bandas, 1):
            dst.write(a.astype("float32"), i)
            dst.set_band_description(i, nome)
        dst.update_tags(**tags)
    rasterio.shutil.copy(tmp, destino, driver="COG", compress="DEFLATE", blocksize=256, overview_resampling="nearest")
    tmp.unlink()


def etapa_avaliar(cfg: dict, q: dict, cache: Path, saida: Path, sufixo: str = "") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from flooding_mapping.geoai import atributos as at, avaliacao as av, modelos as md, referencia as rf
    cv, g, crs = cfg["validacao"], q["grade"], q["crs"]
    t0 = time.time()
    alvos = rf.alvos_da_profill(RAIZ / "data/processed/uso_solo/uso_solo_grade30m.parquet", RAIZ / "data/processed/uso_solo/classes_e_codigos.json", g, cfg["rotulos"])
    atrib = np.load(saida / "atributos_30m.npy")
    Y = np.stack([alvos[f"frac_{k}"] for k in rf.GRUPOS], -1)
    tem_imagem = np.isfinite(atrib[..., at.NOMES.index("red")]) & (np.nan_to_num(atrib[..., at.NOMES.index("n_cenas")]) >= 3)
    valida = alvos["valida"] & tem_imagem & np.isfinite(Y).all(-1)
    blocos = rf.identificador_de_blocos(valida.shape, cv["bloco_celulas"])
    dobras, reg_dobras = rf.dobras_por_blocos(blocos, valida, Y[..., 0], cv["dobras"], cv["semente"])
    n_col_blocos = -(-g["colunas"] // cv["bloco_celulas"])
    dentro = valida & (dobras >= 0)
    log.info("células: grade %d | Profill utilizável %d | com imagem %d | no experimento %d", valida.size, int(alvos["valida"].sum()), int(tem_imagem.sum()), int(dentro.sum()))
    aef_f = saida / f"aef_30m_{cfg['alphaearth']['ano']}.npy"
    aef = np.load(aef_f) if aef_f.exists() else None
    if aef is not None:           # o experimento B usa exatamente as mesmas células, dobras e protocolo
        valida &= np.isfinite(aef[..., 0])
        dobras, reg_dobras = rf.dobras_por_blocos(blocos, valida, Y[..., 0], cv["dobras"], cv["semente"])
        dentro = valida & (dobras >= 0)
        log.info("com os embeddings, o experimento comum tem %d células", int(dentro.sum()))
    modelos = {"media_do_treino": ("media", [], atrib, None), "linear_ndvi_ndbi_mndwi": ("linear", ["ndvi", "ndbi", "mndwi"], atrib, None)} | {f"rf_{k}": ("rf", v, atrib, None) for k, v in at.CONJUNTOS.items()}
    if aef is not None:
        modelos |= {"linear_AEF": ("linear", at.NOMES_AEF, aef, at.NOMES_AEF), "rf_AEF": ("rf", at.NOMES_AEF, aef, at.NOMES_AEF)}
    res, oof = {}, {}
    for nome, (tipo, cols, fonte, ordem) in modelos.items():
        t1 = time.time()
        oof[nome] = md.validar_espacialmente(fonte, Y, valida, dobras, cols, cv["buffer_celulas"], cfg["modelo"]["rf"], cv["semente"], tipo, ordem)
        log.info("P1 %-26s %.0f s", nome, time.time() - t1)
    idx = oof["rf_S1_bandas"]["indices"]
    ref = Y.reshape(-1, 4)[idx]
    bl = blocos.ravel()[idx]
    ev = {n: av.estatisticas_por_bloco(ref, o["pred"], bl) for n, o in oof.items()}
    res["P1_blocos"] = {n: {"fracao_construida": av.erros_da_fracao(ref[:, 0], o["pred"][:, 0]), "bootstrap_por_blocos": av.bootstrap_por_blocos(ev[n], cv["bootstrap"], cv["semente"]),
                            "erros_por_grupo": {k: av.erros_da_fracao(ref[:, i], o["pred"][:, i]) for i, k in enumerate(rf.GRUPOS)}} for n, o in oof.items()}
    ordem = list(at.CONJUNTOS)
    escolha, passos = ordem[0], []
    for ant, prox in zip(ordem[:-1], ordem[1:]):
        d = av.diferenca_pareada(ev[f"rf_{ant}"], ev[f"rf_{prox}"], cv["bootstrap"], cv["semente"])
        melhora = d["ic95"][0] > 0     # MAE(anterior) - MAE(seguinte) positivo em todo o intervalo: o seguinte é melhor
        passos.append({"de": ant, "para": prox, **d, "adotado": bool(melhora)})
        if melhora and escolha == ant:
            escolha = prox
    res["escolha_do_conjunto_de_atributos"] = {"regra": "parte de S1 e só passa ao conjunto seguinte se o intervalo de 95% (blocos) da redução de MAE exclui zero", "escolhido": escolha, "passos": passos}
    primario = f"rf_{escolha}"
    res["comparacao_pareada_com_o_primario"] = {n: av.diferenca_pareada(ev[n], ev[primario], cv["bootstrap"], cv["semente"]) for n in ev if n != primario}
    o, e = oof[primario], ev[primario]
    pred = o["pred"]
    cm = av.matriz_de_confusao(ref.argmax(1), pred.argmax(1))
    res["primario"] = {"modelo": primario, "matriz_de_confusao_ref_x_prev": cm.tolist(), "ordem_das_classes": rf.GRUPOS, "classes_duras": av.f1_e_iou(cm),
                       "estabilidade_entre_blocos": av.estabilidade_entre_blocos(e, cfg["validacao"]["limiares_operacionais"]["mae_fracao_construida"]),
                       "por_estrato_de_jardins": av.por_estrato(ref, pred, alvos["jardins_frac"].ravel()[idx], cv["estratos_jardins"])}
    nao_mista = alvos["nao_mista_m2"].ravel()[idx]
    bairro, nomes_b = rf.bairro_de_cada_celula(RAIZ / "data/processed/territorio_poa.json", g, crs)
    res["primario"]["erro_de_area_por_bairro"] = av.erro_de_area_por_bairro(ref, pred, nao_mista, bairro.ravel()[idx], nomes_b, cv["limiares_operacionais"]["erro_de_area_por_bairro"])
    erro_abs = np.abs(pred[:, 0] - ref[:, 0])
    inc = av.incerteza(o["sd"], erro_abs, erro_abs)
    cob = []
    for k in sorted(set(o["dobra"].tolist())):
        qk = float(np.quantile(erro_abs[o["dobra"] != k], 0.90))
        cob.append({"dobra": int(k), "meio_intervalo": qk, "cobertura": float((erro_abs[o["dobra"] == k] <= qk).mean())})
    inc["cobertura_por_dobra"], inc["nota"] = cob, "intervalo conforme de 90% com resíduos das outras dobras (modelos dessas dobras viram a dobra testada no treino: calibração aproximada)"
    inc.pop("cobertura_observada"), inc.pop("meio_intervalo_conforme_90")
    res["primario"]["incerteza"] = inc
    # protocolo mais duro: leave-one-quadrant-out
    reg4 = md.regioes_por_quadrante(blocos, dobras, n_col_blocos)
    res["P2_quadrantes"] = {}
    p2 = [("media_do_treino", "media", [], atrib, None), ("linear_ndvi_ndbi_mndwi", "linear", ["ndvi", "ndbi", "mndwi"], atrib, None), (primario, "rf", at.CONJUNTOS[escolha], atrib, None)]
    if aef is not None:
        p2 += [("linear_AEF", "linear", at.NOMES_AEF, aef, at.NOMES_AEF), ("rf_AEF", "rf", at.NOMES_AEF, aef, at.NOMES_AEF)]
    for nome, tipo, cols, fonte, ordem in p2:
        o2 = md.validar_espacialmente(fonte, Y, valida, reg4, cols, cv["buffer_celulas"], cfg["modelo"]["rf"], cv["semente"], tipo, ordem)
        ref2, bl2 = Y.reshape(-1, 4)[o2["indices"]], blocos.ravel()[o2["indices"]]
        e2 = av.estatisticas_por_bloco(ref2, o2["pred"], bl2)
        res["P2_quadrantes"][nome] = {"bootstrap_por_blocos": av.bootstrap_por_blocos(e2, cv["bootstrap"], cv["semente"]), "fracao_construida": av.erros_da_fracao(ref2[:, 0], o2["pred"][:, 0]),
                                      "por_quadrante": {int(r): av.erros_da_fracao(ref2[o2["dobra"] == r][:, 0], o2["pred"][o2["dobra"] == r][:, 0]) for r in sorted(set(o2["dobra"].tolist()))}}
    # verificação cruzada com o OpenStreetMap (não é independente da Profill)
    osm_f = saida / "osm_edificacoes_30m.npy"
    if not osm_f.exists():
        mun = gpd.read_parquet(cfgmod.resolve("data/processed/municipality.parquet")).to_crs(crs).union_all()
        np.save(osm_f, rf.fracao_de_edificacoes_osm(RAIZ / "data/interim/poa.osm.pbf", g, crs, mun))
    osm = np.load(osm_f).ravel()[idx]
    A = g["celula_m"] ** 2
    p_ed = alvos["edificacao_m2"].ravel()[idx] / A
    p_c = alvos["construido_m2"].ravel()[idx] / A
    r_c = pred[:, 0] * nao_mista / A
    cor = lambda a, b: float(np.corrcoef(a, b)[0, 1])  # noqa: E731
    res["verificacao_osm"] = {"nota": "OSM de edificações não é independente da Profill (origem das importações desconhecida); só indica coerência", "celulas": int(len(idx)),
                              "soma_osm_km2": float(osm.sum() * A / 1e6), "soma_profill_edificacao_km2": float(p_ed.sum() * A / 1e6), "razao_osm_sobre_profill_edificacao": float(osm.sum() / p_ed.sum()),
                              "corr_osm_x_profill_edificacao": cor(osm, p_ed), "mae_osm_x_profill_edificacao": float(np.abs(osm - p_ed).mean()),
                              "corr_osm_x_profill_construido": cor(osm, p_c), "corr_osm_x_previsto_construido": cor(osm, r_c), "corr_profill_construido_x_previsto": cor(p_c, r_c)}
    # produto: fora da dobra nas células com rótulo; modelo final nas demais células com imagem
    X_all_cols = at.CONJUNTOS[escolha]
    final = md.ajustar_rf(md.matriz(atrib, X_all_cols, dentro), Y[dentro], cfg["modelo"]["rf"], cv["semente"], cfg["modelo"]["rf"]["amostras_de_treino"])
    resto = tem_imagem.copy().ravel()
    resto[idx] = False
    pf, sf = md.prever_rf(final, md.matriz(atrib, X_all_cols, resto.reshape(valida.shape)))
    H, W = valida.shape
    frac = np.full((H * W, 4), np.nan, "float32")
    desv = np.full(H * W, np.nan, "float32")
    origem = np.zeros(H * W, "float32")
    frac[idx], desv[idx], origem[idx] = pred, o["sd"], 1
    r_idx = np.flatnonzero(resto)
    frac[r_idx], desv[r_idx], origem[r_idx] = pf, sf, 2
    classe = np.where(np.isfinite(frac).all(1), frac.argmax(1) + 1, np.nan).astype("float32")
    bandas = [(f"fracao_{k}", frac[:, i].reshape(H, W)) for i, k in enumerate(rf.GRUPOS)] + [("desvio_entre_arvores_construido", desv.reshape(H, W)), ("classe_predominante", classe.reshape(H, W)), ("origem_da_previsao", np.where(origem == 0, np.nan, origem).reshape(H, W))]
    atr_meta = json.loads((saida / "atributos_30m.json").read_text())
    exp_hash = hashlib.sha256(json.dumps([cfg, atr_meta["cenas_ids"], escolha], sort_keys=True, default=str).encode()).hexdigest()[:12]
    exp_id = f"geoai-fase5-{exp_hash}"
    tags = {"experimento": exp_id, "fonte_da_imagem": f"Sentinel-2 L2A (Copernicus), tile {atr_meta['tile']}, COG da AWS Open Data via {cfg['imagens']['stac_url']}", "periodo": f"{cfg['imagens']['inicio']} a {cfg['imagens']['fim']}",
            "composicao": f"mediana de {atr_meta['cenas']} cenas válidas (SCL)", "resolucao": "30 m (média de 3x3 pixels de 10 m)", "modelo": f"RandomForestRegressor ({escolha}); sklearn {versoes()['scikit-learn']}", "versao_do_modelo": cfg["versao"],
            "natureza": "EXPERIMENTAL: estimativa de fração construída (Edificação + Vias Pavimentadas da Profill), não impermeabilidade nem coeficiente de escoamento", "referencia": "Profill 2022 (interpretação visual de ortoimagem 2018-2021)",
            "origem_da_previsao": "1 = fora da dobra espacial (célula com rótulo); 2 = modelo final em célula sem rótulo utilizável (sem validação)"}
    cog = saida / f"fracao_construida_30m_{exp_id}{sufixo}.tif"
    gravar_cog(cog, bandas, g, crs, tags)
    # figuras (todas leem os resultados; nenhuma é decorativa)
    fig_dir = RAIZ / "data/interim/geoai/figuras_locais" if not sufixo else saida / "figuras_rapido"   # as figuras derivam da Profill: ficam fora do Git e da publicação
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
    h = ax[0].hexbin(ref[:, 0], pred[:, 0], gridsize=45, bins="log", cmap="viridis", mincnt=1)
    ax[0].plot([0, 1], [0, 1], "r--", lw=1)
    ax[0].set(xlabel="Fração construída na Profill", ylabel="Fração construída estimada (fora da dobra)", title=f"{primario}: MAE {res['P1_blocos'][primario]['fracao_construida']['mae']:.3f}")
    fig.colorbar(h, ax=ax[0], label="células (log)")
    ax[1].bar(range(len(inc["erro_por_quintil_de_desvio"])), [d["erro_abs_medio"] for d in inc["erro_por_quintil_de_desvio"]], color="#0b5d8f")
    ax[1].set(xlabel="Quintil do desvio entre as árvores (1 = menor)", ylabel="Erro absoluto médio", title=f"Incerteza x erro (Spearman {inc['spearman_desvio_x_erro']:.2f})", xticks=range(5), xticklabels=range(1, 6))
    fig.tight_layout(); fig.savefig(fig_dir / "geoai_dispersao_incerteza.png", dpi=130); plt.close(fig)
    mae_b = np.full(blocos.max() + 1, np.nan); mae_b[e["ids"]] = e["abs"] / e["n"]
    fig, ax = plt.subplots(figsize=(5.5, 5))
    im_ = ax.imshow(mae_b[blocos], cmap="YlOrRd", vmin=0, vmax=0.3); ax.axis("off"); ax.set_title("MAE da fração construída por bloco de 3 km (P1)", fontsize=9); fig.colorbar(im_, fraction=0.04)
    fig.tight_layout(); fig.savefig(fig_dir / "geoai_erro_por_bloco.png", dpi=130); plt.close(fig)
    # manifesto e resultados
    ref_files = {"uso_solo_grade30m.parquet": RAIZ / "data/processed/uso_solo/uso_solo_grade30m.parquet", "classes_e_codigos.json": RAIZ / "data/processed/uso_solo/classes_e_codigos.json",
                 "poa.osm.pbf": RAIZ / "data/interim/poa.osm.pbf", "territorio_poa.json": RAIZ / "data/processed/territorio_poa.json"}
    manifesto = {"experimento": exp_id, "versao": cfg["versao"], "executado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "imagens": {"fonte": "Sentinel-2 L2A (Copernicus; AWS Open Data / Element 84 Earth Search)", "tile": atr_meta["tile"], "periodo": [cfg["imagens"]["inicio"], cfg["imagens"]["fim"]],
                 "cenas": atr_meta["cenas_ids"], "linhas_de_processamento": atr_meta["linhas_de_processamento"], "registros_sha256": sha256(cache / "registros.json")},
                 "sistema_de_referencia": crs, "resolucao_m": g["celula_m"], "grade": g, "modelo": {"nome": "RandomForestRegressor", "biblioteca": "scikit-learn", "versao_do_pipeline": cfg["versao"], "conjunto_de_atributos": escolha, "parametros": cfg["modelo"]["rf"], "pesos_pre_treinados": None},
                 "validacao": {"dobras": reg_dobras, "buffer_celulas": cv["buffer_celulas"], "semente": cv["semente"], "protocolos": ["P1 blocos de 3 km, 5 dobras com buffer", "P2 deixar um quadrante de fora"]},
                 "dados_de_referencia": {n: {"arquivo": str(p.relative_to(RAIZ)), "sha256": sha256(p)} for n, p in ref_files.items()}, "atributos_sha256": sha256(saida / "atributos_30m.npy"), "produto": {"arquivo": str(cog.relative_to(RAIZ)), "sha256": sha256(cog), "formato": "COG (GDAL driver COG, DEFLATE)", "bandas": [b for b, _ in bandas]},
                 "metricas": f"reports/qa/geoai_resultados{sufixo}.json", "dependencias": versoes(), "limiares_operacionais": cv["limiares_operacionais"], "segundos": round(time.time() - t0, 1)}
    (saida / f"manifesto_{exp_id}{sufixo}.json").write_text(json.dumps(manifesto, indent=1, ensure_ascii=False))
    res["meta"] = {"experimento": exp_id, "celulas_no_experimento": int(dentro.sum()), "blocos": reg_dobras, "limiares_operacionais": cv["limiares_operacionais"], "segundos": round(time.time() - t0, 1)}
    destino = RAIZ / cfg["diretorios"]["relatorios"] / f"geoai_resultados{sufixo}.json"
    destino.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    log.info("resultados em %s; manifesto %s; COG %s (%.0f s)", destino, saida / f"manifesto_{exp_id}.json", cog, time.time() - t0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("etapa", choices=["cenas", "baixar", "atributos", "aef-baixar", "aef-atributos", "avaliar"])
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--rapido", action="store_true", help="avaliar com parâmetros mínimos (10 árvores, bootstrap 20): só para checar o código; não gera resultado do experimento")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg, q, cache, saida = carregar()
    if a.rapido:
        cfg["modelo"]["rf"].update(n_estimators=10, amostras_de_treino=20000)
        cfg["validacao"]["bootstrap"] = 20
    if a.etapa == "cenas":
        etapa_cenas(cfg, q, cache)
    elif a.etapa == "baixar":
        etapa_baixar(cfg, q, cache)
    elif a.etapa == "atributos":
        etapa_atributos(cfg, q, cache, saida)
    elif a.etapa == "aef-baixar":
        etapa_aef_baixar(cfg, q, cache)
    elif a.etapa == "aef-atributos":
        etapa_aef_atributos(cfg, q, cache, saida)
    else:
        etapa_avaliar(cfg, q, cache, saida, sufixo="_rapido" if a.rapido else "")


if __name__ == "__main__":
    main()
