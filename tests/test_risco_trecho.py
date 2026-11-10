import numpy as np
import pandas as pd
import pytest
from rede_sintetica import PR, chuva, rede, tabela, tres_caminhos, aresta

from flooding_mapping import risco_trecho as rt


def test_rain_factor_hits_the_documented_anchor_levels():
    # one hour at the "medio" intensity inside the window gives the medium factor, "alto" gives 1
    medio = rt.tabela_de_chuva(chuva("2026-11-09 12:00", PR["chuva_medio"]["max_1h_mm"], 1), PR)
    alto = rt.tabela_de_chuva(chuva("2026-11-09 12:00", PR["chuva_alto"]["max_1h_mm"], 1), PR)
    t = pd.Timestamp("2026-11-09 12:00")
    assert medio.loc[t, "fator"] == pytest.approx(PR["fator_no_medio"])
    assert alto.loc[t, "fator"] == pytest.approx(1.0)
    assert rt.tabela_de_chuva(chuva(mm_h=0), PR).loc[t, "fator"] == 0.0


def test_the_factor_uses_only_rain_up_to_the_hour():
    base = tabela()
    future = chuva()
    future[pd.Timestamp("2026-11-09 18:00"):] = 40.0  # a later storm must not change earlier hours
    mudou = rt.tabela_de_chuva(future, PR)
    antes = base.index <= pd.Timestamp("2026-11-09 17:00")
    assert np.allclose(base.loc[antes, "fator"].fillna(-1), mudou.loc[antes, "fator"].fillna(-1))


def test_antecedent_rain_raises_the_factor_but_never_above_one():
    seco = rt.tabela_de_chuva(chuva("2026-11-09 12:00", 5.0, 1), PR)
    umida = chuva("2026-11-09 12:00", 5.0, 1)
    umida[pd.Timestamp("2026-11-06 12:00"):pd.Timestamp("2026-11-08 06:00")] = 1.0  # wet 72 h before the window
    molhado = rt.tabela_de_chuva(umida, PR)
    t = pd.Timestamp("2026-11-09 12:00")
    assert molhado.loc[t, "antecedente_umido"] and molhado.loc[t, "fator"] > seco.loc[t, "fator"]
    assert rt.tabela_de_chuva(chuva(mm_h=60), PR)["fator"].max() == 1.0


def test_hours_without_a_full_window_have_no_estimate_not_zero():
    tab = tabela()
    assert np.isnan(tab["fator"].iloc[0]) and np.isnan(rt.fator_em(tab, pd.Timestamp("2026-01-01")))


def test_factor_is_interpolated_between_hours():
    tab = tabela()
    a, b = tab.loc["2026-11-09 11:00", "fator"], tab.loc["2026-11-09 12:00", "fator"]
    assert rt.fator_em(tab, pd.Timestamp("2026-11-09 11:30")) == pytest.approx((a + b) / 2)


def test_missing_terrain_has_no_estimate_and_is_not_read_as_safe():
    r = rede(tres_caminhos())
    pct = r.pct.copy()
    pct[0] = np.nan
    p = rt.pesos(pct, r, [], PR)
    assert np.isnan(p["peso"][0]) and np.isnan(p["confiabilidade"][0])
    assert rt.classe(np.array([np.nan, 0.7, 0.3, 0.01]), PR).tolist() == [None, "alto", "atencao", "baixo"]


def occ(r, situacao, confiab="media", **kw):
    return {"id": "o1", "situacao": situacao, "confiabilidade": confiab, "segmento_ids": [], "lon": r.no_lon[r.u[0]],
            "lat": r.no_lat[r.u[0]], **kw}


def test_a_nearby_occurrence_sets_a_weight_floor_scaled_by_status_and_reliability():
    df = tres_caminhos(pct_curto=0.0)  # lowest terrain susceptibility on the short path
    r = rede(df)
    base = rt.pesos(r.pct, r, [], PR)["peso"][0]
    rep = rt.pesos(r.pct, r, [occ(r, "reportada")], PR)
    conf = rt.pesos(r.pct, r, [occ(r, "confirmada")], PR)
    assert base == 0.0
    assert rep["peso"][0] == pytest.approx(PR["piso_ocorrencia"]["reportada"] * PR["fator_confiabilidade_ocorrencia"]["media"])
    assert conf["peso"][0] > rep["peso"][0] and conf["confiabilidade"][0] == PR["confiabilidade"]["confirmada"]
    assert rep["ocorrencia"][0] == "o1"
    assert rt.pesos(r.pct, r, [occ(r, "descartada")], PR)["peso"][0] == 0.0  # a discarded record counts for nothing


def test_the_physical_index_is_a_percentile_and_ranks_low_wet_flat_ground_highest():
    f = pd.DataFrame({"elev": [2.0, 30.0, 80.0, 5.0], "rel_elev_250": [-2.0, 1.0, 5.0, -1.0],
                      "height_above_water": [1.0, 20.0, 60.0, 3.0], "log_flow_acc": [6.0, 2.0, 1.0, 5.0],
                      "slope": [0.2, 5.0, 12.0, 0.5]})
    out = rt.indice_fisico(f)
    assert out["percentil"].between(0, 100).all()
    assert out["percentil"].idxmax() == 0 and out["percentil"].idxmin() == 2
    assert list(out.columns[:5]) == rt.COMPONENTES


def test_the_weight_ramp_gives_weight_only_to_the_most_susceptible_streets():
    r = rede(tres_caminhos())
    pct = np.array([0.0, 50.0, PR["corte_fisico"], 92.5, 100.0, np.nan])
    peso = rt.pesos(np.resize(pct, r.n), r, [], PR)["peso"][:6]
    assert peso[:3].tolist() == [0.0, 0.0, 0.0] and peso[3] == pytest.approx(0.5) and peso[4] == 1.0 and np.isnan(peso[5])


def test_even_in_the_heaviest_rain_only_a_small_share_of_the_network_is_flagged():
    pct = np.linspace(0, 100, 10_001)
    peso = np.clip((pct - PR["corte_fisico"]) / (100 - PR["corte_fisico"]), 0, 1)
    for fator, maximo in ((0.4, 0.07), (1.0, 0.16)):
        marcado = (fator * peso >= PR["classes"]["atencao"]).mean()
        assert 0 < marcado <= maximo, (fator, marcado)
    assert (0.4 * peso >= PR["classes"]["alto"]).sum() == 0   # "alto" needs heavy rain, not the documented lower bound


def test_the_factor_recedes_after_the_rain_stops_and_never_looks_ahead():
    tab = rt.tabela_de_chuva(chuva("2026-11-09 12:00", 15.0, 3), PR)       # rains 12:00-14:00
    f = lambda hora: tab.loc[pd.Timestamp(f"2026-11-09 {hora}"), "fator"]  # noqa: E731
    assert f("14:00") == 1.0 and f("15:00") == pytest.approx(1 - 1 / PR["recuo_h"])
    assert f("14:00") > f("16:00") > f("19:00") and f("14:00") + 0 == 1.0
    assert f(f"{14 + PR['recuo_h']}:00") == 0.0 and f("23:00") == 0.0      # the 24 h windows are still high, the factor is not
    outra = chuva("2026-11-09 12:00", 15.0, 3)
    outra[pd.Timestamp("2026-11-09 17:00"):] = 30.0                          # later rain cannot change earlier hours
    assert rt.tabela_de_chuva(outra, PR).loc[pd.Timestamp("2026-11-09 16:00"), "fator"] == f("16:00")
