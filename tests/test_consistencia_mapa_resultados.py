"""O mapa e a aba Resultados leem as mesmas execuções do motor: mesmas chuvas, mesmos pacotes, mesmos valores por trecho.

Os fragmentos do mapa (data/processed/fase3_web) e o JSON da aba Resultados nascem dos mesmos Parquets da Fase 3. Aqui se confere que
o valor que o painel do trecho calcula (P x área equivalente / 1000) é o valor que o motor gravou, e que as definições coincidem.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "data/processed/fase3_web"
F3 = ROOT / "data/processed/fase3"
RES = ROOT / "src/flooding_mapping/app/static/data/resultados_poa.json"
pytestmark = pytest.mark.skipif(not (WEB / "meta.json").exists() or not (F3 / "trechos_nivel2_cenarios.parquet").exists(), reason="dados derivados da Fase 3 ausentes")


def test_map_and_results_share_the_same_rain_scenarios_and_packages():
    from flooding_mapping import resultados
    meta = json.loads((WEB / "meta.json").read_text())
    assert tuple(int(p) for p in meta["precipitacoes_mm"]) == resultados.PRECIPITACOES
    res = json.loads(RES.read_text())
    assert res["precipitacao_de_referencia_mm"] == 30
    assert set(meta["pacotes"].values()) == {"metodo1", "limites_fisicos", "referencia_analoga"}
    js = (ROOT / "src/flooding_mapping/app/static/fase3-dados.js").read_text()
    for chave in meta["pacotes"]:
        assert f"{chave}:" in js or f'"{chave}"' in js, f"pacote {chave} sem definição no mapa"


def test_map_detail_values_equal_engine_output_for_every_scenario():
    import pandas as pd
    meta = json.loads((WEB / "meta.json").read_text())
    frag = json.loads((WEB / "detalhe/0000.json").read_text())
    cols = frag["colunas"]
    linhas = [dict(zip(cols, l)) for l in frag["linhas"][:300]]
    cen = pd.read_parquet(F3 / "trechos_nivel2_cenarios.parquet")
    ids = [l["id"] for l in linhas if l["l_m1_max"] is not None]
    assert ids
    sub = cen[cen["segmento_id"].isin(ids)]
    idx = {(r.segmento_id, int(r.p_mm), r.pacote): r for r in sub.itertuples()}
    pacote = {"m1": "metodo1", "li": "limites_fisicos", "an": "referencia_analoga"}
    conferidos = 0
    for l in linhas:
        if l["l_m1_max"] is None:
            continue
        for p in meta["precipitacoes_mm"]:
            for k, nome in pacote.items():
                r = idx.get((l["id"], int(p), nome))
                if r is None or l[f"l_{k}_max"] is None:
                    continue
                for campo, col, saida in (("l", "v_gerado_local", "local"), ("c", "contrib_potencial", "contrib")):
                    for lim in ("min", "max"):
                        painel = p * l[f"{campo}_{k}_{lim}"] / 1000
                        motor = getattr(r, f"{col}_{lim}_m3")
                        assert painel == pytest.approx(motor, rel=2e-6, abs=1e-6), (l["id"], p, k, campo, lim)
                        conferidos += 1
    assert conferidos > 1000


def test_missing_data_is_never_shown_as_zero_in_the_map_detail():
    meta = json.loads((WEB / "meta.json").read_text())
    frag = json.loads((WEB / "detalhe/0000.json").read_text())
    cols = frag["colunas"]; sem = [dict(zip(cols, l)) for l in frag["linhas"] if l[cols.index("l_m1_max")] is None]
    for l in sem[:50]:
        assert all(v is None for k, v in l.items() if k.startswith(("l_", "c_")))
    assert meta["trechos"] == meta["trechos_com_dados"] + meta["trechos_sem_dados"]
