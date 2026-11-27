import pandas as pd

from flooding_mapping import demonstracao as dm


def test_the_synthetic_storm_is_pouring_now_so_that_leaving_now_crosses_it_and_it_is_declared():
    serie, meta = dm.serie_sintetica()
    agora = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).floor("h")
    assert "SINTÉTICA" in meta["fonte"] and "não é previsão" in meta["fonte"]
    assert serie[agora] == 14.0 and serie[agora - pd.Timedelta(hours=3)] == 14.0 and serie[agora + pd.Timedelta(hours=6)] == 14.0
    assert serie[agora + pd.Timedelta(hours=8)] == 4.0 and serie[agora + pd.Timedelta(hours=10)] == 0 and serie[agora - pd.Timedelta(hours=5)] == 0
    assert serie.index.min() < agora < serie.index.max()   # past (the model's analysis) and future (the "forecast")


def test_the_demonstration_credential_is_public_and_long_enough_to_pass_the_server_rule():
    from flooding_mapping.servidor import validar_token
    assert validar_token(dm.TOKEN_DEMO) == dm.TOKEN_DEMO
