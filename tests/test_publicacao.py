"""Configuração de produção: URLs do R2, versão, hashes de integridade de fonte verificável, CSP com a origem do R2 e a configuração local intacta."""
import json
import re
import shutil
from pathlib import Path

import pytest

from flooding_mapping.app import build

RAIZ = Path(__file__).resolve().parents[1]
VERSAO = "d-b7f6f03555d9"
MANIFESTO = RAIZ / "docs/manifestos" / f"manifesto_{VERSAO}.json"
PACOTE = RAIZ / "data/interim/r2_preparado" / VERSAO / "cabecalhos.json"
URL = "https://pub-0123456789abcdef0123456789abcdef.r2.dev"


def pub(tmp_path, **extra):
    c = json.loads((RAIZ / "config/publicacao.json").read_text(encoding="utf-8"))
    c.update({"r2_url": URL, **extra})
    arq = tmp_path / "publicacao.json"
    arq.write_text(json.dumps(c), encoding="utf-8")
    return build.carregar_publicacao(arq)


def test_the_committed_configuration_points_to_the_expected_version_and_manifest_and_is_local_until_the_url_is_set():
    c = json.loads((RAIZ / "config/publicacao.json").read_text(encoding="utf-8"))
    assert c["versao"] == VERSAO and c["camadas_publicadas"] == ["fase3", "drenagem"] and c["geoai_publicada"] is True and c["mapa_arquivo"] == "mapa/poa.pmtiles"
    assert c["pages_origem"] == "https://flooding-mapping-capstone.pages.dev"
    assert json.loads(MANIFESTO.read_text(encoding="utf-8"))["versao_dos_dados"] == VERSAO
    if c["r2_url"] is None:
        assert build.carregar_publicacao() is None                                       # sem URL, o build é o local de sempre


def test_the_integrity_hashes_come_from_two_independent_sources_that_agree():
    man = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    for camada in ("fase3", "drenagem"):
        assert re.fullmatch(r"[0-9a-f]{64}", man["camadas"][camada]["meta_sha256"])
    assert man["mapa"]["bytes"] > 1_000_000 and re.fullmatch(r"[0-9a-f]{64}", man["mapa"]["sha256"]) and man["geoai"] is None
    if PACOTE.exists():
        cab = json.loads(PACOTE.read_text(encoding="utf-8"))["objetos"]
        for camada in ("fase3", "drenagem"):
            assert cab[f"{camada}/meta.json"]["sha256_do_original"] == man["camadas"][camada]["meta_sha256"]
        assert cab["mapa/poa.pmtiles"]["sha256_do_original"] == man["mapa"]["sha256"] and not any(k.startswith("geoai/") for k in cab)


def test_the_production_build_has_the_r2_urls_the_version_the_hashes_and_the_csp_origin(tmp_path):
    p = pub(tmp_path, geoai_publicada=False)
    out = tmp_path / "site"
    r = build.build_site(out, publicacao=p)
    cfg = (out / "config-dados.js").read_text(encoding="utf-8")
    man = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    assert f'fase3: "{URL}/{VERSAO}/fase3/"' in cfg and f'drenagem: "{URL}/{VERSAO}/drenagem/"' in cfg and f'mapa: "{URL}/{VERSAO}/mapa/poa.pmtiles"' in cfg and f'versao: "{VERSAO}"' in cfg
    assert f'fase3: "{man["camadas"]["fase3"]["meta_sha256"]}"' in cfg and f'drenagem: "{man["camadas"]["drenagem"]["meta_sha256"]}"' in cfg
    assert "geoai: null" in cfg and 'meta_sha256: { fase3: "' in cfg and "fase3: null" not in cfg                           # com hash esperado, a página recusa meta.json que não confere
    assert "lerMeta" in cfg and r["producao"] == {"versao": VERSAO, "r2_url": URL, "geoai": False, "geoai_prefixo": None}
    csp = dict(re.findall(r"([a-z-]+) ([^;]+)", re.search(r"/\*\n  Content-Security-Policy: ([^\n]+)", (out / "_headers").read_text()).group(1)))
    assert URL in csp["connect-src"].split() and URL in csp["img-src"].split() and URL not in csp["script-src"] and URL not in csp["default-src"]
    assert "frame-ancestors 'none'" in (out / "_headers").read_text()


def test_the_local_development_configuration_is_untouched_by_the_production_build(tmp_path):
    antes = (build.STATIC / "config-dados.js").read_text(encoding="utf-8")
    build.build_site(tmp_path / "prod", publicacao=pub(tmp_path))
    assert (build.STATIC / "config-dados.js").read_text(encoding="utf-8") == antes
    assert 'fase3: "fase3/", drenagem: "drenagem/", geoai: "geoai/"' in antes and 'mapa: "/mapa/rs.pmtiles"' in antes
    build.build_site(tmp_path / "local")
    assert (tmp_path / "local/config-dados.js").read_text(encoding="utf-8") == antes and "r2" not in (tmp_path / "local/_headers").read_text().lower()


@pytest.mark.parametrize("ruim", ["http://pub-x.r2.dev", "https://pub-x.r2.dev/", "pub-x.r2.dev", "https://", "https://pub-x.r2.dev/a b"])
def test_malformed_or_insecure_r2_urls_stop_the_build(tmp_path, ruim):
    c = json.loads((RAIZ / "config/publicacao.json").read_text(encoding="utf-8"))
    c["r2_url"] = ruim
    (tmp_path / "p.json").write_text(json.dumps(c), encoding="utf-8")
    with pytest.raises(SystemExit):
        build.carregar_publicacao(tmp_path / "p.json")


def test_a_version_that_does_not_match_the_manifest_or_a_malformed_geoai_prefix_stops_the_build(tmp_path):
    c = json.loads((RAIZ / "config/publicacao.json").read_text(encoding="utf-8"))
    (tmp_path / "p.json").write_text(json.dumps({**c, "r2_url": URL, "versao": "d-000000000000"}), encoding="utf-8")
    with pytest.raises(SystemExit):
        build.carregar_publicacao(tmp_path / "p.json")
    (tmp_path / "q.json").write_text(json.dumps({**c, "r2_url": URL, "geoai_publicada": True, "geoai": {"prefixo": "d-b7f6f03555d9", "manifesto": c["geoai"]["manifesto"]}}), encoding="utf-8")
    with pytest.raises(SystemExit):
        build.carregar_publicacao(tmp_path / "q.json")                                           # a camada E não pode usar o prefixo da versão principal
    (tmp_path / "r.json").write_text(json.dumps({**c, "r2_url": URL, "geoai_publicada": True, "geoai": {"prefixo": "geoai-000000000000", "manifesto": c["geoai"]["manifesto"]}}), encoding="utf-8")
    with pytest.raises(SystemExit):
        build.carregar_publicacao(tmp_path / "r.json")                                           # o manifesto é de outro prefixo


def test_the_geoai_layer_gets_its_own_prefix_and_hash_without_touching_the_main_version(tmp_path):
    c = json.loads((RAIZ / "config/publicacao.json").read_text(encoding="utf-8"))
    assert c["geoai"]["prefixo"].startswith("geoai-") and c["geoai"]["prefixo"] != c["versao"]
    gman = json.loads((RAIZ / c["geoai"]["manifesto"]).read_text(encoding="utf-8"))
    assert gman["versao_dos_dados"] == c["geoai"]["prefixo"] and re.fullmatch(r"[0-9a-f]{64}", gman["geoai"]["meta_sha256"]) and "não a substitui" in gman["observacao"]
    p = pub(tmp_path, geoai_publicada=True)
    out = tmp_path / "site"
    build.build_site(out, publicacao=p)
    cfg = (out / "config-dados.js").read_text(encoding="utf-8")
    assert f'geoai: "{URL}/{c["geoai"]["prefixo"]}/geoai/"' in cfg and f'geoai: "{gman["geoai"]["meta_sha256"]}"' in cfg
    assert f'fase3: "{URL}/{VERSAO}/fase3/"' in cfg and f'drenagem: "{URL}/{VERSAO}/drenagem/"' in cfg and f'mapa: "{URL}/{VERSAO}/mapa/poa.pmtiles"' in cfg      # a versão principal não muda
    assert "geoai: null" not in cfg


def test_the_geoai_layer_is_not_a_requirement_of_the_other_layers():
    mapa = (build.STATIC / "mapa.js").read_text(encoding="utf-8")
    assert 'dado: "geoai"' in mapa and "function semDados" in mapa and "Camada experimental ainda não publicada neste ambiente" in mapa
