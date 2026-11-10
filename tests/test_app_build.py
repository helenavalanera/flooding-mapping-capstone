import json
import re

import geopandas as gpd
import pandas as pd
import pytest
from pyproj import Transformer
from shapely.geometry import LineString

import test_inference as ti
from flooding_mapping.app import build

X0, Y0 = Transformer.from_crs("EPSG:4326", "EPSG:5880", always_xy=True).transform(-51.0, -30.0)

CARD = {"decisao": {"estado": "experimental: não passa em eventos detectados fora da amostra"},
        "gatilho_operacional": {
            "tipo": "regra", "descricao": "regra de chuva calibrada", "estado": "regra simples calibrada: o modelo ficou experimental",
            "motivo": "experimental: não passa em eventos detectados fora da amostra",
            "desempenho_teste": {"pr_auc": 0.0048, "roc_auc": 0.745, "prevalencia": 0.001,
                                 "orcamentos": {"alertas_2pct": {"recall_eventos": 0.39, "precisao": 0.0095, "dias_alerta_por_mil": 20.0}}}}}


def segment_index():
    return gpd.GeoDataFrame({"segmento_id": ["7-000", "7-001"], "objectid": [7, 7], "codigo_sre": ["001ERS0010"] * 2,
                             "nome": ["ERS-1"] * 2, "km_ini": [0.0, 4.5], "km_fim": [4.5, 9.0],
                             "geometry": [LineString([(X0, Y0), (X0 + 4500, Y0)]), LineString([(X0 + 4500, Y0), (X0 + 9000, Y0)])]},
                            crs="EPSG:5880")


def impact_table():
    return pd.DataFrame({"segmento_id": ["7-000", "7-001"], "ponte": [True, False], "pop_isolada": [12000.0, 0.0],
                         "desvio_km": [None, 35.0], "vdm": [None, 1800.0], "veiculos_km_dia": [None, 63000.0]})


def blockage_payload():
    p = Transformer.from_crs("EPSG:5880", "EPSG:4326", always_xy=True).transform(X0 + 1000, Y0)
    return {"atualizado": "2026-11-08T12:00:00Z", "bloqueios": [
        {"id": 1, "rodovia": "ERS-1", "municipio": "Aceguá", "km": 1, "km_fim": None, "tipo": "total",
         "data": "2026-11-08T10:00:00Z", "informacoes": "<script>alert(1)</script> ponte cedeu", "climatico": True,
         "lat": p[1], "lng": p[0]}]}


def make_site(tmp_path, blockages="default"):
    tw = ti.towns()
    s = ti.series()
    grid = pd.DataFrame({"ibge": ti.TOWNS, "altitude_m": [10.0, 300.0, 700.0]})
    art = ti.artifact(ti.history(), tw, grid)
    art["municipios"], art["grade"] = tw, grid
    meta = {"fonte": "https://api.open-meteo.com/v1/forecast", "emitido_em_utc": "2026-11-08T17:00:00Z",
            "primeira_data": "2026-09-29", "ultima_data": "2026-11-10"}
    out = tmp_path / "site"
    data = blockage_payload() if blockages == "default" else blockages
    published = build.build_site(out, art, CARD, s, meta, data, segment_index(), impact_table())
    return out, published


def test_site_has_the_page_the_data_and_no_jekyll_marker(tmp_path):
    out, published = make_site(tmp_path)
    for name in ("index.html", "app.js", "logic.js", "style.css", "previsao_72h.json", "bloqueios.json",
                 ".nojekyll", "data/municipios.geojson", "data/rodovias.geojson", "data/ocorrencias.json", "data/impacto_rs.json"):
        assert (out / name).exists(), name
    assert published["previsao"] and published["municipios"] == 3 and published["bloqueios"] == 1


def test_every_file_the_page_loads_exists_in_the_site(tmp_path):
    out, _ = make_site(tmp_path)
    html = (out / "index.html").read_text()
    local = [m for m in re.findall(r'(?:src|href)="([^"]+)"', html) if not m.startswith(("http", "data:"))]
    assert {"style.css", "logic.js", "app.js", "painel.js"} <= set(local) and all((out / m).exists() for m in local)
    js = (out / "app.js").read_text()
    for name in re.findall(r'getJson\((?:DATA \+ )?"([^"]+)"', js):
        assert (out / name).exists() or (out / "data" / name).exists(), name


def test_forecast_file_states_what_it_is_and_what_it_is_not(tmp_path):
    out, _ = make_site(tmp_path)
    f = json.loads((out / "previsao_72h.json").read_text())
    assert f["tipo"].startswith("estimativa") and f["emitido_para"] == "2026-11-08"
    assert f["modelo"]["tipo"] == "regra" and f["modelo"]["estado_do_modelo_de_aprendizado_de_maquina"].startswith("experimental")
    assert f["modelo"]["treinado_ate"]
    assert len(f["municipios"][0]["dias"]) == 3 and f["fonte_chuva"]["ultima_data"] == "2026-11-10"
    assert any("Defesa Civil" in a for a in f["avisos"]) and f["municipios_sem_dados"] == []


def test_blockage_is_matched_to_its_segment_with_the_simulated_impact(tmp_path):
    out, _ = make_site(tmp_path)
    b = json.loads((out / "bloqueios.json").read_text())["bloqueios"][0]
    assert b["casamento"]["status"] == "ok" and b["casamento"]["codigo_sre"] == "001ERS0010"
    assert b["impacto"]["natureza"] == "simulado" and b["impacto"]["ponte"] is True
    assert b["impacto"]["pop_isolada"] == 12000.0 and b["impacto"]["vdm"] is None  # missing VDM stays missing


def test_site_is_built_without_the_blockage_layer_when_the_source_is_down(tmp_path):
    out, published = make_site(tmp_path, blockages=None)
    assert not (out / "bloqueios.json").exists() and "bloqueios" not in published and (out / "previsao_72h.json").exists()


def test_nothing_secret_reaches_the_published_site(tmp_path):
    out, _ = make_site(tmp_path)
    pattern = re.compile(r"R2_[A-Z_]+|SECRET|access[_-]?key|api[_-]?key|token|cb1_[A-Za-z0-9_]{10,}", re.I)
    leaks = [p.name for p in out.rglob("*") if p.is_file() and pattern.search(p.read_text(errors="ignore"))]
    assert leaks == []
    assert not list(out.rglob("*.joblib")) and not list(out.rglob("*.parquet"))  # the model never ships


def test_free_text_from_the_source_is_escaped_by_the_page_not_trusted():
    js = (build.STATIC / "app.js").read_text()
    assert "Lg.esc(b.informacoes" in js and "innerHTML" in js
    assert "Lg.esc(" in js and js.count("Lg.esc(") > 20


def test_the_site_refuses_a_model_that_its_card_does_not_document():
    artifact = {"versao": "gatilho-estrito-20261108"}
    build.check_card(artifact, {"artefato": {"versao": "gatilho-estrito-20261108"}})
    with pytest.raises(SystemExit, match="does not|not the one"):
        build.check_card(artifact, {"artefato": {"versao": "gatilho-estrito-20260101"}})


def test_roads_layer_carries_the_physical_index_as_a_percentile_and_keeps_missing_vdm_missing():
    from flooding_mapping.app import layers

    line = LineString([(-51.0, -30.0), (-51.0, -29.9)])
    trechos = gpd.GeoDataFrame({"objectid": [1, 2], "codigo_sre": ["a", "b"], "nome": ["ERS-1", "ERS-2"], "rede": "R",
                                "vdm": [1500.0, None], "km_inicio": 0.0, "km_final": 5.0,
                                "situacao_fisica": ["PAVIMENTADA", "PLANEJADA"], "geometry": [line, line]}, crs="EPSG:4674")
    stretches = pd.DataFrame({"objectid": [1], "ponte": [True], "pop_isolada": [900.0], "desvio_km": [float("inf")]})
    out = layers.roads(trechos, stretches, pd.Series({1: 83.4}))
    assert list(out["codigo_sre"]) == ["a"]                       # planned roads are not drawn
    assert out["indice_fisico"].iloc[0] == 83.0 and out["ponte"].iloc[0] and pd.isna(out["desvio_km"].iloc[0])


def test_the_files_the_build_needs_in_a_clean_clone_exist_and_are_not_git_ignored():
    """The Actions runner only has what is committed: a Parquet hidden by `*.parquet` breaks the site."""
    import shutil
    import subprocess

    needed = [build.BUILD_DATA / "segmentos_indice.parquet", build.BUILD_DATA / "impacto_segmentos.parquet",
              *[build.STATIC_DATA / n for n in ("municipios.geojson", "rodovias.geojson", "ocorrencias.json", "impacto_rs.json")]]
    assert all(p.exists() for p in needed)
    if shutil.which("git"):
        ignored = subprocess.run(["git", "check-ignore", "-q", *map(str, needed)], cwd=build.BUILD_DATA, capture_output=True)
        if ignored.returncode in (0, 1):  # 128 means "not a git repository": nothing to check
            assert ignored.returncode == 1, "a file the site build needs is ignored by .gitignore"


def test_the_pwa_ships_with_everything_it_loads_and_never_caches_the_api(tmp_path):
    out, _ = make_site(tmp_path)
    pwa = out / "pwa"
    html = (pwa / "index.html").read_text()
    local = [m for m in re.findall(r'(?:src|href)="([^"]+)"', html) if not m.startswith(("http", "data:"))]
    assert {"pwa.js", "dados.js", "pwa.css", "manifest.webmanifest", "../logic.js"} <= set(local)
    assert all((pwa / m).exists() for m in local), [m for m in local if not (pwa / m).exists()]
    manifest = json.loads((pwa / "manifest.webmanifest").read_text())
    assert manifest["display"] == "standalone" and manifest["start_url"] == "./" and manifest["lang"] == "pt-BR"
    assert all((pwa / i["src"]).exists() for i in manifest["icons"]) and {"192x192", "512x512"} <= {i["sizes"] for i in manifest["icons"]}
    sw = (pwa / "sw.js").read_text()
    shell = re.search(r"var CASCA = \[(.*?)\];", sw, re.S).group(1)
    assert all((pwa / n).exists() for n in re.findall(r'"([^"h][^"]*)"', shell))     # every cached shell file exists
    assert 'url.pathname.indexOf("/api/") >= 0) return;' in sw                          # API requests are left to the network


def test_the_pwa_escapes_what_it_shows_and_never_watches_the_position():
    js = (build.STATIC / "pwa" / "pwa.js").read_text()
    assert "geolocation.watchPosition" not in js and js.count("geolocation.getCurrentPosition") == 1   # one position, foreground only
    assert "Lg.esc" in js and js.count("esc(") > 30
    assert not re.search(r"(api[_-]?key|token|secret)", js + (build.STATIC / "pwa" / "dados.js").read_text(), re.I)


def test_the_site_ships_the_territory_files_and_the_map_modules(tmp_path):
    out, _ = make_site(tmp_path)
    for name in ("territorio.js", "mapa.js", "data/territorios.json", "data/cobertura_rs.json"):
        assert (out / name).exists(), name
    territorios = json.loads((out / "data/territorios.json").read_text())
    assert set(territorios["territorios"]) == {"rs", "poa"} and territorios["territorios"]["rs"]["cobertura"]["municipios"] == 497
    cobertura = json.loads((out / "data/cobertura_rs.json").read_text())
    assert len(cobertura["municipios"]) == 497 and cobertura["metodo"] and cobertura["estado"]["municipios_por_classe"]["parcial"] > 0


def test_the_map_library_is_pinned_with_an_integrity_hash_and_no_other_3d_engine_is_loaded():
    html = (build.STATIC / "index.html").read_text()
    tag = re.search(r'<script src="https://cdnjs\.cloudflare\.com/ajax/libs/maplibre-gl/(\d+\.\d+\.\d+)/maplibre-gl\.js"([^>]*)>', html)
    assert tag and re.fullmatch(r"\d+\.\d+\.\d+", tag.group(1)) and 'integrity="sha384-' in tag.group(2) and 'crossorigin="anonymous"' in tag.group(2)
    assert not re.search(r"three(\.min)?\.js|cesium|deck\.gl", html, re.I)


def test_every_layer_the_configuration_names_is_drawn_by_the_map_or_is_a_colouring_mode():
    import yaml

    from flooding_mapping.config import ROOT
    js = (build.STATIC / "mapa.js").read_text()
    desenhadas = set(re.findall(r"^    (\w+): \{ rotulo:", js, re.M)) | {"risco_municipal", "indice_fisico"}   # the last two are colouring modes
    config = yaml.safe_load((ROOT / "config" / "territorios.yaml").read_text(encoding="utf-8"))
    prometidas = {c for t in config["territorios"].values() for cap in t["capacidades"].values() for c in cap.get("camadas", [])}
    assert prometidas <= desenhadas, sorted(prometidas - desenhadas)
    assert {"municipios", "rodovias", "risco_trecho", "rotas", "interdicoes"} <= desenhadas


def test_the_page_policy_lets_the_map_work_and_nothing_more():
    from flooding_mapping import servidor
    csp = dict(p.strip().split(" ", 1) for p in servidor.CSP.split(";") if p.strip())
    assert "blob:" in csp["worker-src"] and "https://s3.amazonaws.com" in csp["connect-src"] and "https://tile.openstreetmap.org" in csp["connect-src"]
    assert "'unsafe-eval'" not in servidor.CSP and csp["frame-ancestors"] == "'none'" and csp["script-src"] == "'self' https://cdnjs.cloudflare.com"
