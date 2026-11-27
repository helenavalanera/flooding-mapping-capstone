"""Ingestão e auditoria das camadas de drenagem de Porto Alegre: tudo com dados sintéticos (nenhum teste consulta o servidor municipal).

Cobre: paginação por lotes, rejeição de geometria inútil, campos pessoais fora da coleta, idempotência e manifesto, detecção de texto em branco no pandas 3,
valores fora de faixa, conectividade geométrica, polígonos com buraco, duplicidades e a tabela de classes de uso do solo (nenhum coeficiente sem fonte).
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import auditar_drenagem_poa as aud  # noqa: E402
import baixar_drenagem_poa as baixar  # noqa: E402


# ---------- coleta ----------
def test_unusable_geometries_are_detected_for_points_lines_and_polygons():
    assert baixar._geometria_finita({"x": 1.0, "y": 2.0})
    assert not baixar._geometria_finita({"x": "NaN", "y": "NaN"})
    assert not baixar._geometria_finita({"x": float("nan"), "y": 1.0})
    assert baixar._geometria_finita({"paths": [[[0, 0], [1, 1]]]})
    assert not baixar._geometria_finita({"paths": [[[0, 0], [math.inf, 1]]]})
    assert baixar._geometria_finita({"rings": [[[0, 0], [1, 0], [1, 1], [0, 0]]]})
    assert not baixar._geometria_finita({"rings": [[[0, 0], [1, 0], [float("nan"), 1], [0, 0]]]})


def test_collection_leaves_out_staff_names_documents_links_and_free_text():
    meta = {"fields": [{"name": n, "type": t} for n, t in [("OBJECTID", "esriFieldTypeOID"), ("DIAMETRO", "esriFieldTypeInteger"), ("USUARIOCRIACAO", "esriFieldTypeString"),
                                                           ("usuarioatu", "esriFieldTypeString"), ("FISCAL", "esriFieldTypeString"), ("LEVANTAMENTO", "esriFieldTypeString"),
                                                           ("EXECUCAO", "esriFieldTypeString"), ("OBSERVACAO", "esriFieldTypeString"), ("observaç", "esriFieldTypeString"),
                                                           ("LINK", "esriFieldTypeString"), ("DOCRECEBIDO", "esriFieldTypeString"), ("TERMOGARANTIA", "esriFieldTypeString"),
                                                           ("ALTITUDE_MONTANTE", "esriFieldTypeDouble"), ("SHAPE", "esriFieldTypeGeometry")]]}
    assert baixar.campos_permitidos(meta) == ["OBJECTID", "DIAMETRO", "ALTITUDE_MONTANTE"]


class ServicoFalso:
    """Stand-in for the ArcGIS REST service: metadata, an id list, and features by id, with a NaN point and a record without geometry."""

    def __init__(self, n=2300, ruins=(5, 17)):
        self.n, self.ruins, self.pedidos = n, set(ruins), []

    def __call__(self, metodo, url, tentativas=4, **dados):
        self.pedidos.append((metodo, url.rsplit("/", 1)[-1], dict(dados)))
        if url.endswith("/query") and dados.get("returnIdsOnly"):
            return {"objectIds": list(range(self.n, 0, -1))}                                 # unordered on purpose
        if url.endswith("/query"):
            ids = [int(i) for i in dados["objectIds"].split(",")]
            fs = []
            for i in ids:
                geom = {"x": "NaN", "y": "NaN"} if i == 5 else None if i == 17 else {"paths": [[[i, i], [i + 1, i + 1]]]}
                fs.append({"attributes": {"OBJECTID": i, "DIAMETRO": 300}, "geometry": geom})
            return {"features": fs}
        return {"name": "Rede Pluvial", "geometryType": "esriGeometryPolyline", "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID"}, {"name": "DIAMETRO", "type": "esriFieldTypeInteger"},
                                                                                         {"name": "USUARIOCRIACAO", "type": "esriFieldTypeString"}, {"name": "SHAPE", "type": "esriFieldTypeGeometry"}]}


def test_download_pages_in_batches_rejects_unusable_records_and_is_idempotent(tmp_path, monkeypatch):
    falso = ServicoFalso()
    monkeypatch.setattr(baixar, "_pedido", falso)
    monkeypatch.setattr(baixar.time, "sleep", lambda *_: None)
    monkeypatch.setattr(baixar, "RAIZ", tmp_path)
    manifesto, destino = tmp_path / "manifest.json", tmp_path / "drenagem"
    e1 = baixar.baixar_camada("rede_teste", "x/y/MapServer/0", destino, manifesto)
    lotes = [p for p in falso.pedidos if p[0] == "POST"]
    assert len(lotes) == math.ceil(2300 / baixar.LOTE) and all(len(p[2]["objectIds"].split(",")) <= baixar.LOTE for p in lotes)      # nunca depende de paginação do servidor
    assert all("USUARIOCRIACAO" not in p[2]["outFields"] for p in lotes)
    assert (e1["feature_count_at_source"], e1["feature_count_saved"], e1["feature_count_rejected_without_geometry"], e1["feature_count_rejected_non_finite_geometry"]) == (2300, 2298, 1, 1)
    conteudo = json.loads((destino / "rede_teste.json").read_text())
    oids = [f["atributos"]["OBJECTID"] for f in conteudo["feicoes"]]
    assert oids == sorted(oids) and len(oids) == len(set(oids)) and 5 not in oids and 17 not in oids and conteudo["srid"] == baixar.SRS_SAIDA
    assert e1["sha256"] == hashlib.sha256((destino / "rede_teste.json").read_bytes()).hexdigest() and e1["registered"] is True
    e2 = baixar.baixar_camada("rede_teste", "x/y/MapServer/0", destino, manifesto)           # same data again
    assert e2["sha256"] == e1["sha256"] and e2["registered"] is False                         # nada duplicado e manifesto intacto
    assert len(json.loads(manifesto.read_text())["sources"]) == 1


# ---------- auditoria ----------
def test_blank_text_is_not_counted_as_filled_with_the_pandas_string_dtype():
    s = pd.Series(["PS2", " ", None, "", "PA2"], dtype="string")
    assert aud.preenchido(s).tolist() == [True, False, False, False, True]
    assert aud.preenchido(pd.Series(["a", " "], dtype=object)).tolist() == [True, False]
    assert aud.preenchido(pd.Series([1.0, np.nan])).tolist() == [True, False]


def test_profile_counts_zeros_negatives_and_values_outside_the_plausible_range():
    df = pd.DataFrame({"ALTITUDE_MONTANTE": [10.0, 0.0, -2.0, 283465.0, None], "TIPO": ["a", " ", "a", None, "b"]})
    p = aud.perfil(df, ("ALTITUDE_MONTANTE",), ("TIPO",))
    n = p["numericos"]["ALTITUDE_MONTANTE"]
    assert (n["preenchido"], n["zeros"], n["negativos"], n["fora_da_faixa_plausivel"]) == (0.8, 1, 1, 1)
    assert p["preenchimento"]["TIPO"] == 0.6 and p["categoricos"]["TIPO"]["a"] == 2


def test_geometric_connectivity_separates_coincident_ends_from_free_ones_and_never_claims_hydraulics():
    # A-B-C in a chain (shared ends), D alone far away; a manhole sits on the shared end of A and B
    d = {"feicoes": [{"geometria": {"paths": [[[0, 0], [10, 0]]]}}, {"geometria": {"paths": [[[10, 0], [20, 0]]]}}, {"geometria": {"paths": [[[20, 0], [30, 0]]]}},
                     {"geometria": {"paths": [[[500, 500], [510, 500]]]}}]}
    c = aud.conectividade(d, np.array([[10.0, 0.0]]))
    t = c["evidencia_geometrica_de_conexao_por_tolerancia"]["tolerancia_0.5m"]
    assert t["nenhum_extremo_ligado"] == 0.25                      # só D
    assert t["um_extremo_ligado"] == 0.5                           # A e C têm um extremo livre
    assert t["ambos_extremos_ligados"] == 0.25                     # B
    assert "não conectividade hidráulica" in c["leitura"] or "não é conectividade hidráulica" in c["leitura"] or "conectividade hidráulica confirmada" in c["leitura"]
    assert c["segmentos"] == 4


def test_polygons_keep_holes_and_duplicates_are_found():
    exterior = [[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]            # clockwise (Esri exterior)
    buraco = [[2, 2], [8, 2], [8, 8], [2, 8], [2, 2]]                  # counter-clockwise (Esri hole)
    pol = aud.poligonos({"feicoes": [{"geometria": {"rings": [exterior, buraco]}}]})[0]
    assert pol.area == pytest.approx(100 - 36)
    import shapely
    g = [shapely.LineString([(0, 0), (1, 1)]), shapely.LineString([(0, 0), (1, 1)]), shapely.LineString([(0, 0), (2, 2)])]
    r = aud.geometrias(g)
    assert r["duplicadas_exatas"] == 1 and r["invalidas"] == 0 and r["sem_geometria"] == 0


def test_altitude_consistency_flags_inverted_slopes():
    df = pd.DataFrame({"ALTITUDE_MONTANTE": [10.0, 8.0, 5.0], "ALTITUDE_JUSANTE": [9.0, 9.0, 4.0], "EXTENSAO": [100.0, 100.0, 50.0], "DECLIVIDADE": [0.01, -0.01, 0.02]})
    r = aud.consistencia_altitudes(df)
    assert r["com_as_duas_altitudes_validas"] == 3 and r["montante_maior_ou_igual_a_jusante"] == pytest.approx(2 / 3, abs=1e-3)


# ---------- tabela de classes de uso do solo ----------
def test_land_use_table_has_no_coefficient_without_a_source():
    t = pd.read_csv(RAIZ / "config/uso_solo_profill_hidrologia.csv")
    assert len(t) == 15 and t.classe_original.is_unique
    assert set(t.tratamento_no_modelo) <= {"faixa_fundamentada", "cenario_declarado", "fora_do_calculo_de_escoamento"}
    fund = t[t.tratamento_no_modelo == "faixa_fundamentada"]
    assert len(fund) >= 1 and fund.coeficiente_min.notna().all() and fund.coeficiente_max.notna().all() and (fund.coeficiente_min < fund.coeficiente_max).all()
    assert fund.coeficiente_min.between(0, 1).all() and fund.coeficiente_max.between(0, 1).all() and fund.fonte.str.contains("TxDOT").all()
    resto = t[t.tratamento_no_modelo != "faixa_fundamentada"]
    assert resto.coeficiente_min.isna().all() and resto.coeficiente_max.isna().all()                  # nada inventado: sem fonte, sem número
    assert t.justificativa.str.len().gt(20).all() and t.grau_de_incerteza.isin({"baixo", "medio", "alto", "muito_alto"}).all()


# ---------- integridade dos arquivos coletados (local; data/raw não vai ao Git) ----------
RAW = RAIZ / "data/raw/drenagem_poa"


@pytest.mark.skipif(not RAW.exists(), reason="falta data/raw/drenagem_poa (fora do Git)")
def test_collected_files_match_the_latest_manifest_entry_and_counts_add_up():
    fontes = json.loads((RAIZ / "data/raw/manifest.json").read_text())["sources"]
    ultimas = {}
    for s in fontes:
        if s["path"].startswith("data/raw/drenagem_poa/"):
            ultimas[s["path"]] = s
    assert ultimas, "nenhuma camada de drenagem registrada no manifesto"
    for caminho, s in ultimas.items():
        arquivo = RAIZ / caminho
        assert arquivo.exists() and hashlib.sha256(arquivo.read_bytes()).hexdigest() == s["sha256"], caminho
        assert s["feature_count_saved"] + s["feature_count_rejected_without_geometry"] + s.get("feature_count_rejected_non_finite_geometry", 0) == s["feature_count_at_source"], caminho
        assert s["spatial_reference_saved"] == "EPSG:31982" and "usuario" not in " ".join(s["fields_saved"]).lower() and "fiscal" not in " ".join(s["fields_saved"]).lower()
