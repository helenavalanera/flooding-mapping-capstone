import numpy as np
import pandas as pd
from rede_sintetica import LAT0, LON0, rede, tres_caminhos

from flooding_mapping import bolsoes


def pois():
    return pd.DataFrame([
        {"poi_id": "n1", "nome": "Hospital Teste", "categoria": "saude", "tipo": "hospital", "lon": LON0 + 0.015, "lat": LAT0 + 0.004},
        {"poi_id": "n2", "nome": None, "categoria": "educacao", "tipo": "escola", "lon": LON0 + 0.0151, "lat": LAT0 + 0.0041},
        {"poi_id": "n3", "nome": "Longe", "categoria": "saude", "tipo": "farmácia", "lon": LON0 + 0.5, "lat": LAT0 + 0.5}])


def test_a_pocket_groups_the_flagged_stretches_and_lists_only_the_places_inside_it():
    r = rede(tres_caminhos())
    curto = [i for i, s in enumerate(r.ids) if str(s).startswith("S")]
    escore = np.zeros(r.n)
    escore[curto] = 0.8
    lista = bolsoes.formar(r, curto, escore, pois(), raio_m=200)
    assert len(lista) == 1
    b = lista[0]
    assert b["n_trechos"] == 2 and b["km"] == 2.0 and b["geometria"]["type"] == "Polygon"
    assert {p["poi_id"] for p in b["pois"]} == {"n1", "n2"} and b["pois_por_categoria"] == {"saude": 1, "educacao": 1}
    assert next(p for p in b["pois"] if p["poi_id"] == "n2")["nome"] is None      # a POI with no name stays None, never NaN


def test_distant_stretches_make_separate_pockets_ranked_by_priority_with_places_counting():
    r = rede(tres_caminhos())
    curto = [i for i, s in enumerate(r.ids) if str(s).startswith("S")]
    longo = [i for i, s in enumerate(r.ids) if str(s) == "M1"]     # the middle stretch of the medium path: far from the short one
    escore = np.zeros(r.n)
    escore[curto], escore[longo] = 0.7, 0.7
    lista = bolsoes.formar(r, curto + longo, escore, pois(), raio_m=100)
    assert len(lista) == 2
    assert lista[0]["n_pois"] == 2 and lista[0]["prioridade"] > lista[1]["prioridade"] == lista[1]["escore_medio"]   # no POI: priority is the plain score


def test_without_a_poi_layer_or_flagged_stretches_it_still_answers():
    r = rede(tres_caminhos())
    assert bolsoes.formar(r, [], np.zeros(r.n), None) == []
    lista = bolsoes.formar(r, [0, 1], np.full(r.n, 0.5), None)
    assert lista and lista[0]["pois"] == [] and lista[0]["n_pois"] == 0


def test_the_sentence_is_always_an_estimate_and_never_calls_anything_safe_or_flooded():
    r = rede(tres_caminhos())
    b = bolsoes.formar(r, [0, 1], np.full(r.n, 0.5), pois(), raio_m=2000)[0]
    t = bolsoes.texto(b, "16:00", "previsto")
    assert "estimativa" in t and "não um alerta oficial" in t
    assert not any(w in t.lower() for w in ("segur", "alagad", "inundad"))
