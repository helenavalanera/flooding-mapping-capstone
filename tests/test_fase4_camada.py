"""Fase 4: a camada de escoamento potencial na aplicação preserva os resultados da Fase 3.

Dois grupos. Os testes sintéticos rodam sempre (classes, ausência, tiles, servidor). Os de integridade conferem os arquivos distribuídos
contra os Parquets reais da Fase 3 e são ignorados se esses arquivos (derivados, fora do Git) não existirem neste ambiente.
"""

import json
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import requests

from flooding_mapping import camada_fase3 as c
from flooding_mapping import servidor as srv

RAIZ = Path(__file__).parent.parent
FASE3 = RAIZ / "data/processed/fase3"
WEB = RAIZ / "data/processed/fase3_web"
STATIC = RAIZ / "src/flooding_mapping/app/static"
real = pytest.mark.skipif(not ((WEB / "meta.json").exists() and (FASE3 / "trechos_nivel2_cenarios.parquet").exists() and (RAIZ / "data/interim/segments.parquet").exists()),
                          reason="camada da Fase 3 não gerada (tools/preparar_camada_fase3.py)")


# ------------------------------------------------------------------------------------------------ sintéticos: classes e ausência
def test_missing_is_not_zero_in_the_classes():
    v = pd.Series([np.nan, 0.0, 1.0, 2.0, 3.0, 4.0, 100.0])
    cortes = c.cortes_por_quantis(v)
    cl = c.classe_por_cortes(v, cortes)
    assert pd.isna(cl.iloc[0]) and cl.iloc[1] == 0                   # ausente fica sem classe; zero é a classe 0
    assert cl.iloc[2] >= 1 and list(cl.iloc[2:]) == sorted(cl.iloc[2:]) and cl.iloc[-1] == len(cortes) + 1
    assert pd.isna(c.classe_da_fracao(pd.Series([np.nan])).iloc[0]) and c.classe_da_fracao(pd.Series([0.0])).iloc[0] == 0


def test_the_coverage_classes_have_closed_upper_edges():
    f = pd.Series([0.0, 0.01, 0.25, 0.2501, 0.5, 0.75, 0.7501, 1.0])
    assert list(c.classe_da_fracao(f)) == [0, 1, 1, 2, 2, 3, 4, 4]


def test_the_topographic_class_never_turns_a_height_into_a_volume_or_depth():
    t = pd.DataFrame({"altura_de_preenchimento_max_m": [np.nan, 0.0, 3.0, 9.0], "propensao_topografica_percentil": [np.nan, 38.8, 86.0, 99.0]})
    for k in c.COLUNA_AEQ:
        for g in c.GRANDEZAS.values():
            for b in c.LIMITES:
                t[f"{g}_{c.COLUNA_AEQ[k]}_{b}_m2"] = 1.0
    for k in c.COLUNAS_DE_COBERTURA.values():
        t[k] = 0.5
    classes, _ = c.classes_visuais(t)
    assert pd.isna(classes["tp"].iloc[0]) and list(classes["tp"].iloc[1:]) == [0, 2, 4]
    assert not [k for k in c.COLUNAS_DO_DETALHE if re.search(r"profundidade|volume|retido|armazen", k)]    # nenhuma coluna chama o indicador de volume ou profundidade


def test_empty_tiles_inside_the_data_box_are_filled(tmp_path):
    criados = c.preencher_tiles_vazios(tmp_path, (-51.25, -30.12, -51.20, -30.08))
    arquivos = list(tmp_path.rglob("*.pbf"))
    assert criados == len(arquivos) > 0 and all(f.stat().st_size == 0 for f in arquivos) and {f.parts[len(tmp_path.parts)] for f in arquivos} == {"13", "14", "15"}
    assert c.preencher_tiles_vazios(tmp_path, (-51.25, -30.12, -51.20, -30.08)) == 0                      # idempotente e sem sobrescrever


def test_rounding_keeps_nine_significant_digits_and_absence():
    assert c.arredonda(np.nan) is None and c.arredonda(None) is None and c.arredonda(0.0) == 0.0
    for v in (123456789.123456, 1.0000000004e-3, 7.7e-5, 2.2546350000000003e4):
        assert abs(c.arredonda(v) - v) / v < 1e-8


def test_the_hypotheses_come_from_the_engine_tables_and_keep_the_garden_envelope():
    h = c.hipoteses()
    assert h["jardins_e_passeios"]["envelope"] == [0.225, 0.8]
    assert [x["fracao_de_piso"] for x in h["jardins_e_passeios"]["cenarios_de_fracao_de_piso"]] == [25, 50, 75]
    assert h["limites_fisicos"]["c_min"] == 0.0 and h["limites_fisicos"]["c_max"] == 1.0
    assert {r["classe"] for r in h["metodo1"]} == {"Edificação", "Vias Pavimentadas"}
    assert not {r["classe"] for r in h["metodo1"]} & {r["classe"] for r in h["referencia_analoga"]}      # um cenário nunca redefine o Método 1


@pytest.mark.skipif(shutil.which("ogr2ogr") is None, reason="GDAL não instalado")
def test_tiles_carry_only_the_index_and_classes_and_absent_means_no_property(tmp_path):
    from shapely.geometry import LineString

    import geopandas as gpd

    linhas = [LineString([(-51.2 + i * 0.001, -30.03), (-51.2 + i * 0.001 + 0.0005, -30.031)]) for i in range(3)]
    t = gpd.GeoDataFrame({"segmento_id": list("abc")}, geometry=linhas, crs="EPSG:4326").to_crs("EPSG:31982")
    classes = pd.DataFrame({"c_m1_max": pd.array([3, 0, pd.NA], dtype="Int8"), "tp": pd.array([pd.NA, 1, 2], dtype="Int8")})
    g = tmp_path / "t.geojson"
    c.escrever_geojson(t, classes, g)
    c.gerar_tiles(g, tmp_path / "tiles")
    achados = {}
    for f in (tmp_path / "tiles" / str(c.ZOOM_MAXIMO)).rglob("*.pbf"):
        for p in c.ler_tile(f.read_bytes()):
            achados[p["n"]] = p
    assert achados == {0: {"n": 0, "c_m1_max": 3}, 1: {"n": 1, "c_m1_max": 0, "tp": 1}, 2: {"n": 2, "tp": 2}}


# ------------------------------------------------------------------------------------------------ servidor
@pytest.fixture
def camada(tmp_path, monkeypatch):
    import threading
    from http.server import ThreadingHTTPServer

    from test_servico import montar

    pasta = tmp_path / "web"
    (pasta / "detalhe").mkdir(parents=True)
    (pasta / "meta.json").write_text('{"ok":true}')
    (pasta / "detalhe" / "0000.json").write_text('{"linhas":[]}')
    (pasta / "x.txt").write_text("não")
    (tmp_path / "fora.json").write_text('{"fora":true}')
    monkeypatch.setattr(srv, "FASE3_RAIZ", pasta)
    servico, _ = montar()
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), srv.criar_handler(servico, "", srv.Limitador()))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield "127.0.0.1", servidor.server_address[1]
    servidor.shutdown()


def test_the_server_serves_only_the_layer_files_and_nothing_outside_the_folder(camada):
    import http.client

    def pega(caminho):
        con = http.client.HTTPConnection(*camada)
        con.request("GET", caminho)
        r = con.getresponse()
        return r.status, r.read(), r.getheader("Content-Type")

    assert pega("/fase3/meta.json") == (200, b'{"ok":true}', "application/json")
    assert pega("/fase3/detalhe/0000.json")[0] == 200
    assert pega("/fase3/tiles/13/1/1.pbf")[0] == 204 and pega("/fase3/tiles/13/1/1.pbf")[1] == b""         # tile sem trechos: vazio
    assert pega("/fase3/detalhe/9999.json")[0] == 404 and pega("/fase3/tiles/../meta2.pbf")[0] == 404          # só tile ausente é vazio
    for caminho in ("/fase3/x.txt", "/fase3/nao-existe.json", "/fase3/detalhe", "/fase3/../fora.json", "/fase3/%2e%2e/fora.json", "/fase3/..%2ffora.json", "/fase3/detalhe/../../fora.json"):
        status, corpo, _ = pega(caminho)
        assert status == 404 and b"fora" not in corpo, caminho


# ------------------------------------------------------------------------------------------------ integridade com a Fase 3 real
@pytest.fixture(scope="module")
def dados():
    t = c.carregar(FASE3, RAIZ / "data/interim/segments.parquet", RAIZ / "data/processed/rede_poa.parquet")
    meta = json.loads((WEB / "meta.json").read_text())
    frags = [json.loads(p.read_text()) for p in sorted((WEB / "detalhe").glob("*.json"))]
    linhas = [l for f in frags for l in f["linhas"]]
    return t, meta, frags, pd.DataFrame(linhas, columns=meta["colunas_do_detalhe"])


@real
def test_the_distributed_files_correspond_to_the_phase_3_parquets(dados):
    t, meta, frags, d = dados
    assert meta["trechos"] == len(t) == len(d) == 176836 and meta["trechos_com_dados"] == 173917 and meta["trechos_sem_dados"] == 2919
    assert meta["entradas_sha256"] == {p.name: c.sha256(p) for p in sorted(FASE3.glob("*.parquet"))}   # os arquivos de entrada não mudaram desde a preparação
    assert all(f["primeiro_n"] == i * meta["tamanho_do_fragmento"] for i, f in enumerate(frags))


@real
def test_identifiers_are_preserved_unique_and_in_the_order_of_the_index(dados):
    t, _, _, d = dados
    base = pd.read_parquet(FASE3 / "trechos_contribuicao_base.parquet", columns=["segmento_id"])
    assert d["id"].is_unique and list(d["id"]) == sorted(base["segmento_id"]) and list(d["id"]) == list(t["segmento_id"])


@real
def test_values_equal_the_parquets_and_absence_stays_absence(dados):
    _, _, _, d = dados
    b = pd.read_parquet(FASE3 / "trechos_contribuicao_base.parquet").set_index("segmento_id").loc[d["id"]]
    t1 = pd.read_parquet(FASE3 / "trechos_nivel1_propensao_topografica.parquet").set_index("segmento_id").loc[d["id"]]
    pares = {f"{g}_{p}_{x}": f"{n}_{col}_{x}_m2" for g, n in c.GRANDEZAS.items() for p, col in c.COLUNA_AEQ.items() for x in c.LIMITES}
    pares.update({"area_montante_m2": "area_montante_m2", "f_m1": "fracao_montante_coberta_m1", "f_li": "fracao_montante_com_valor_limites", "f_an": "fracao_montante_com_valor_analoga",
                  "f_an_sem": "fracao_montante_sem_valor_analoga", "f_fora": "fracao_montante_fora_do_calculo", "f_sem_classe": "fracao_montante_sem_classe"})
    for k, col in pares.items():
        original, mostrado = b[col].to_numpy(float), d[k].astype(float).to_numpy()
        assert (np.isnan(original) == np.isnan(mostrado)).all(), k            # ausência é ausência, nunca zero
        ok = ~np.isnan(original)
        assert np.all(np.abs(mostrado[ok] - original[ok]) <= 1e-8 * np.abs(original[ok])), k
    for k, col in {"topo_altura_max_m": "altura_de_preenchimento_max_m", "topo_altura_media_m": "altura_de_preenchimento_media_m", "topo_posto": "propensao_topografica_percentil"}.items():
        original, mostrado = t1[col].to_numpy(float), d[k].astype(float).to_numpy()
        assert (np.isnan(original) == np.isnan(mostrado)).all() and np.allclose(original, mostrado, rtol=1e-8, equal_nan=True), k
    assert d["l_m1_max"].isna().sum() == 2919 and (d["l_m1_max"] == 0).sum() > 0                # zero e ausência são coisas diferentes
    assert (d["n_cel"].to_numpy() == b["n_celulas_com_dados"].to_numpy()).all()


@real
def test_the_three_packages_are_never_mixed(dados):
    _, _, _, d = dados
    assert (d["l_li_min"].dropna() == 0).all() and (d["c_li_min"].dropna() == 0).all()          # limite físico inferior: C = 0 em todas as classes
    assert not np.allclose(d["c_m1_max"].fillna(-1), d["c_an_max"].fillna(-1)) and not np.allclose(d["c_li_max"].fillna(-1), d["c_an_max"].fillna(-1))
    com = d["c_m1_max"].notna()
    assert ((d["c_m1_min"][com] <= d["c_m1_max"][com]) & (d["c_an_min"][com] <= d["c_an_max"][com]) & (d["c_li_min"][com] <= d["c_li_max"][com])).all()
    assert (d["c_m1_max"][com] >= d["l_m1_max"][com] - 1e-6).all()                                  # contribuição inclui o volume local


@real
def test_the_unit_conversion_reproduces_the_engine_output_for_every_rainfall(dados):
    """V (m³) = P (mm) x aeq (m²) / 1000 sobre o que o navegador recebe == o Parquet de cenários do motor."""
    _, meta, _, d = dados
    n2 = pd.read_parquet(FASE3 / "trechos_nivel2_cenarios.parquet")
    d = d.set_index("id")
    nome = {"m1": "metodo1", "li": "limites_fisicos", "an": "referencia_analoga"}
    assert sorted(n2["p_mm"].unique()) == meta["precipitacoes_mm"]
    for p in meta["precipitacoes_mm"]:
        for k, pacote in nome.items():
            m = n2[(n2.p_mm == p) & (n2.pacote == pacote)].set_index("segmento_id").loc[d.index]
            for g, col in (("l", "v_gerado_local"), ("c", "contrib_potencial")):
                for x in ("min", "max"):
                    calc, motor = p * d[f"{g}_{k}_{x}"].astype(float).to_numpy() / 1000, m[f"{col}_{x}_m3"].to_numpy(float)
                    assert (np.isnan(calc) == np.isnan(motor)).all()
                    ok = ~np.isnan(motor)
                    assert np.all(np.abs(calc[ok] - motor[ok]) <= 1e-8 * np.maximum(np.abs(motor[ok]), 1e-12)), (p, k, g, x)


@real
def test_the_rainfall_scales_every_volume_linearly(dados):
    """Se houvesse um controle livre de chuva, a proporcionalidade seria exata: V(2P) = 2 V(P). A tela só oferece as execuções do motor."""
    _, meta, _, d = dados
    v = lambda p: p * d["c_m1_max"].astype(float).to_numpy() / 1000  # noqa: E731
    assert np.allclose(v(20), 2 * v(10), equal_nan=True) and np.allclose(v(30), 3 * v(10), equal_nan=True)


@real
def test_tiles_have_every_stretch_and_the_classes_of_the_data(dados):
    t, meta, _, d = dados
    classes, cortes = c.classes_visuais(t)
    assert cortes == meta["cortes_das_classes_aeq_m2"]
    vistos = {}
    for f in (WEB / "tiles" / str(meta["zoom"][1])).rglob("*.pbf"):
        for p in c.ler_tile(f.read_bytes()):
            vistos[p["n"]] = p
    curtos = set(np.flatnonzero(t.geometry.length.to_numpy() < 1.0).tolist())
    faltam = set(range(len(t))) - set(vistos)
    assert faltam <= curtos and len(faltam) <= 20 and meta["trechos_menores_que_1_m"] == len(curtos)   # só os de poucos decímetros somem no zoom máximo
    amostra = list(vistos)[::37]
    for n in amostra:
        esperado = {"n": n, **{k: int(classes[k].iloc[n]) for k in classes.columns if not pd.isna(classes[k].iloc[n])}}
        assert vistos[n] == esperado, n
    sem_dados = [n for n in vistos if "c_m1_max" not in vistos[n]]
    assert sem_dados and all(pd.isna(t["local_aeq_m1_max_m2"].iloc[n]) for n in sem_dados)             # sem classe = sem dados, e só eles


@real
def test_the_stretches_without_data_are_the_same_for_every_property(dados):
    """O mapa usa filtros fixos (só 'c_m1_max'): isso só é correto se a ausência for idêntica em todas as propriedades dos tiles."""
    _, meta, _, _ = dados
    chaves = None
    ausentes = {}
    for f in (WEB / "tiles" / str(meta["zoom"][1])).rglob("*.pbf"):
        for p in c.ler_tile(f.read_bytes()):
            for k in ("c_m1_max", "c_m1_min", "c_li_max", "c_an_min", "l_m1_max", "l_an_max", "tp", "cb_m1", "cb_li", "cb_an"):
                ausentes.setdefault(k, set())
                if k not in p:
                    ausentes[k].add(p["n"])
    assert len({frozenset(v) for v in ausentes.values()}) == 1 and ausentes["c_m1_max"]


@real
def test_the_detail_fragments_are_small_enough_to_fetch_per_click():
    tamanhos = [p.stat().st_size for p in (WEB / "detalhe").glob("*.json")]
    assert max(tamanhos) < 400_000                                                                  # um clique baixa um fragmento de ~210 KB, nunca os 36 MB
    maior = max(f.stat().st_size for f in (WEB / "tiles").rglob("*.pbf"))
    assert maior < 1_000_000


# ------------------------------------------------------------------------------------------------ o código da tela
def test_the_screen_code_never_sums_across_stretches_and_uses_no_forbidden_words():
    fonte = {n: (STATIC / n).read_text(encoding="utf-8") for n in ("fase3.js", "fase3-dados.js")}
    for n, js in fonte.items():
        assert ".reduce(" not in js and not re.search(r"\w\s*\+=\s*(?:r|linha|row)\b", js), n          # nenhuma soma de valores entre trechos na tela
    dados_js = fonte["fase3-dados.js"]
    proibidas = re.search(r"TERMOS_PROIBIDOS = (\[.*?\]);", dados_js, re.S)
    termos = json.loads(proibidas.group(1).replace("\n", " "))
    visivel = fonte["fase3.js"] + (STATIC / "index.html").read_text(encoding="utf-8")
    for termo in termos:
        assert termo.lower() not in visivel.lower(), termo
    assert "motor da Fase 3" in (STATIC / "mapa.js").read_text(encoding="utf-8")


def test_derived_layer_files_are_compressed_cached_and_revalidated_like_a_cdn_would(tmp_path, monkeypatch):
    import gzip
    import http.client
    import threading
    from http.server import ThreadingHTTPServer

    from test_servico import montar

    pasta = tmp_path / "web"
    (pasta / "tiles" / "13" / "1").mkdir(parents=True)
    grande = b"abcdefgh" * 4000
    (pasta / "tiles" / "13" / "1" / "1.pbf").write_bytes(grande)
    (pasta / "meta.json").write_text('{"ok":true}' + " " * 2000)
    monkeypatch.setattr(srv, "FASE3_RAIZ", pasta)
    servico, _ = montar()
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), srv.criar_handler(servico, "", srv.Limitador()))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        def pega(caminho, **cab):
            con = http.client.HTTPConnection("127.0.0.1", servidor.server_address[1])
            con.request("GET", caminho, headers=cab)
            r = con.getresponse()
            return r.status, r.read(), {k.lower(): v for k, v in r.getheaders()}

        st, corpo, h = pega("/fase3/tiles/13/1/1.pbf", **{"Accept-Encoding": "gzip"})
        assert st == 200 and h["content-encoding"] == "gzip" and gzip.decompress(corpo) == grande and len(corpo) < len(grande) / 5
        assert "max-age=3600" in h["cache-control"] and "must-revalidate" in h["cache-control"] and "accept-encoding" in h["vary"].lower()
        assert pega("/fase3/tiles/13/1/1.pbf", **{"If-None-Match": h["etag"]})[0] == 304                       # revalidação sem baixar de novo
        st, corpo, h = pega("/fase3/tiles/13/1/1.pbf")
        assert st == 200 and "content-encoding" not in h and corpo == grande                                    # sem Accept-Encoding, sem compressão
        st, _, h = pega("/fase3/meta.json", **{"Accept-Encoding": "gzip"})
        assert st == 200 and h["cache-control"] == "no-cache" and "etag" not in h                               # o meta.json decide a versão: sempre revalidado
    finally:
        servidor.shutdown()
