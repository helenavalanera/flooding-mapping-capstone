import geopandas as gpd
import pandas as pd
import pytest
import yaml
from shapely.geometry import LineString, Polygon

from flooding_mapping import cobertura as cb
from flooding_mapping.config import ROOT

MINIMOS = {"indice_fisico_minimo": 0.8, "vdm_minimo": 0.8}
CONFIG = yaml.safe_load((ROOT / "config" / "territorios.yaml").read_text(encoding="utf-8"))


def test_a_region_is_available_only_when_every_dimension_meets_its_minimum():
    ok = cb.classificar(10, 9, 9, 3, MINIMOS)
    assert ok["classe"] == "disponivel" and all(ok["dimensoes"].values())
    sem_trafego = cb.classificar(10, 10, 2, 3, MINIMOS)
    assert sem_trafego["classe"] == "parcial" and "tráfego (VDM) em 20% do km" in sem_trafego["motivo"] and sem_trafego["dimensoes"]["vdm"] is False
    sem_registro = cb.classificar(10, 10, 10, 0, MINIMOS)
    assert sem_registro["classe"] == "parcial" and "S2iD" in sem_registro["motivo"]


def test_without_network_and_without_records_only_the_weather_is_left():
    r = cb.classificar(0, 0, 0, 0, MINIMOS)
    assert r["classe"] == "insuficiente" and r["classe_rotulo"] == "Dados insuficientes" and "meteorologia" in r["motivo"]
    com_registro = cb.classificar(0, 0, 0, 4, MINIMOS)       # a record of the municipality is some data, but no road
    assert com_registro["classe"] == "parcial" and com_registro["dimensoes"]["malha"] is False


def test_a_highway_has_no_s2id_dimension_and_zero_traffic_is_missing_not_low():
    r = cb.classificar(5, 5, 0, None, MINIMOS)
    assert "ocorrencias_s2id" not in r["dimensoes"] and r["classe"] == "parcial" and "tráfego (VDM) em 0% do km" in r["motivo"]


def mundo():
    """Two municipalities side by side, two highways, five segments (one planned, one without terrain index)."""
    A, B = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]), Polygon([(10, 0), (20, 0), (20, 10), (10, 10)])
    towns = gpd.GeoDataFrame({"ibge": ["1", "2", "3"], "geometry": [A, B, Polygon([(30, 0), (40, 0), (40, 10), (30, 10)])]}, crs="EPSG:3857")
    def seg(i, x0, x1, objectid, comp):
        return {"segmento_id": i, "objectid": objectid, "codigo_sre": f"C{objectid}", "comprimento_m": comp, "geometry": LineString([(x0, 5), (x1, 5)])}
    segmentos = gpd.GeoDataFrame([seg("a", 1, 3, 1, 1000), seg("b", 4, 6, 1, 1000), seg("c", 11, 13, 2, 2000), seg("d", 14, 16, 2, 1000), seg("e", 17, 19, 3, 500)], crs="EPSG:3857")
    trechos = pd.DataFrame({"objectid": [1, 2, 3], "vdm": [5000.0, None, 800.0], "nome": ["ERS-1", "BR-2", "ERS-9"], "rede": ["RODOVIAS ESTADUAIS"] * 3,
                            "situacao_fisica": ["PAVIMENTADA", "PAVIMENTADA", "PLANEJADA"]})
    impacto = pd.DataFrame({"segmento_id": ["a", "c"], "ponte": [True, False]})
    records = pd.DataFrame({"ibge": ["1", "1", "2"], "cobrade": [1, 1, 1], "data_evento": pd.to_datetime(["2026-10-01", "2020-01-01", "2026-09-01"])})
    return segmentos, trechos, towns, impacto, records


def test_municipal_and_highway_coverage_are_computed_by_length_and_leave_planned_roads_out(monkeypatch):
    from flooding_mapping.ingestion import s2id
    monkeypatch.setattr(s2id, "HYDRO_BROAD", (1,))
    segmentos, trechos, towns, impacto, records = mundo()
    tabela = cb.tabela_de_segmentos(segmentos, trechos, {"a", "c"}, impacto, towns)
    assert set(tabela["segmento_id"]) == {"a", "b", "c", "d"}                          # "e" is planned
    m = cb.por_municipio(tabela, towns, records, MINIMOS, pd.Timestamp("2026-11-01"))
    assert m["1"]["km"] == 2.0 and m["1"]["km_com_indice_fisico"] == 1.0 and m["1"]["km_com_vdm"] == 2.0 and m["1"]["pontes"] == 1
    assert m["1"]["s2id_hidrologicos_2017_2026"] == 2 and m["1"]["s2id_hidrologicos_90_dias"] == 1
    assert m["2"]["km"] == 3.0 and m["2"]["km_com_vdm"] == 0.0 and m["2"]["classe"] == "parcial"
    assert m["3"]["segmentos"] == 0 and m["3"]["classe"] == "insuficiente"            # no network, no record: only weather
    r = cb.por_rodovia(tabela, MINIMOS)
    assert set(r) == {"ERS-1", "BR-2"} and r["ERS-1"]["municipios_atravessados"] == 1 and r["BR-2"]["km_com_vdm"] == 0.0
    total = cb.resumo(m, r, tabela)
    assert total["municipios_por_classe"] == {"disponivel": 0, "parcial": 2, "insuficiente": 1} and total["fracao_km_com_indice_fisico"] == 0.6 and total["segmentos"] == 4


def test_the_real_configuration_is_valid_and_never_offers_street_level_risk_in_the_state():
    cb.validar_capacidades(CONFIG)
    rs, poa = CONFIG["territorios"]["rs"]["capacidades"], CONFIG["territorios"]["poa"]["capacidades"]
    assert rs["risco_por_trecho"]["estado"] == "indisponivel" and rs["rotas"]["estado"] == "indisponivel"
    assert poa["risco_por_trecho"]["estado"] != "disponivel" and poa["rotas"]["requer_servidor"] is True
    assert all(c["estado"] != "indisponivel" or c["motivo"] for t in CONFIG["territorios"].values() for c in t["capacidades"].values())
    assert set(rs) == set(poa)                      # the same capabilities are described for both regions


@pytest.mark.parametrize("cap, estado", [("risco_por_trecho", "disponivel"), ("rotas", "talvez")])
def test_a_configuration_that_over_claims_or_is_malformed_is_refused(cap, estado):
    ruim = yaml.safe_load(yaml.safe_dump(CONFIG))
    ruim["territorios"]["poa"]["capacidades"][cap]["estado"] = estado
    with pytest.raises(ValueError):
        cb.validar_capacidades(ruim)
    sem_motivo = yaml.safe_load(yaml.safe_dump(CONFIG))
    sem_motivo["territorios"]["rs"]["capacidades"]["rotas"].pop("motivo")
    with pytest.raises(ValueError, match="motivo"):
        cb.validar_capacidades(sem_motivo)


def test_the_territories_file_carries_capabilities_coverage_and_the_method():
    t = cb.montar(CONFIG, {"municipios": 497}, {"dirigivel": {"km": 1}}, "2026-11-10")
    assert t["territorios"]["rs"]["cobertura"] == {"municipios": 497} and t["territorios"]["poa"]["cobertura"] == {"dirigivel": {"km": 1}}
    assert t["metodo_de_cobertura"] and t["rotulos_de_classe"]["parcial"] == "Cobertura parcial" and t["minimos"]["vdm_minimo"] == 0.8
    assert cb.montar(CONFIG, None, None)["territorios"]["poa"]["cobertura"] is None      # no data is None, not zero


def test_the_poa_coverage_separates_what_is_walkable_from_what_is_drivable():
    rede = pd.DataFrame({"comprimento_m": [1000.0, 1000.0, 1000.0], "percentil": [50.0, None, None], "drive": [True, True, False], "walk": [True, True, True]})
    c = cb.cobertura_poa(rede)
    assert c["dirigivel"]["fracao_com_indice"] == 0.5 and c["somente_a_pe"]["fracao_com_indice"] == 0.0 and c["nenhum_modal"]["fracao_com_indice"] is None
