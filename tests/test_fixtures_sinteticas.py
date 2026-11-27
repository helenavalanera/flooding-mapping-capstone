"""Fixtures SINTÉTICAS e isolamento dos dados de terceiros que ficam fora do Git.

Aqui se prova que um clone limpo (sem a lista de alagamentos da Prefeitura, sem a rede de ruas e sem os Parquets derivados) executa o processamento e os modelos
exploratórios sobre dados claramente sintéticos, e que os testes com dados reais são ignorados com uma mensagem, em vez de falhar.
Estes testes não usam, não copiam e não comparam resultados com os pontos reais.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
sys.path.insert(0, str(Path(__file__).parent))
import experimento_modelos_alagamentos as exp  # noqa: E402
import sinteticos  # noqa: E402

from flooding_mapping import dados_restritos  # noqa: E402

FIXTURE = RAIZ / "tests/dados/alagamentos_sinteticos.csv"


def test_the_synthetic_fixture_is_reproducible_from_its_generator_and_has_the_real_schema():
    f = pd.read_csv(FIXTURE)
    assert list(f.columns) == ["camada", "lon", "lat"] and set(f.camada) == {sinteticos.CAMADA}
    gerado = sinteticos.pontos_alagados(sinteticos.grade_com_sinal())
    pd.testing.assert_frame_equal(f, gerado, check_dtype=False)
    assert 30 <= len(f) <= 200


def test_the_synthetic_points_are_nowhere_near_porto_alegre_and_never_the_real_ones():
    f = pd.read_csv(FIXTURE)
    assert not ((f.lon.between(-51.4, -50.9)) & (f.lat.between(-30.35, -29.9))).any(), "ponto dentro de Porto Alegre"
    assert f.lon.between(0, 1).all() and f.lat.between(0, 1).all()                   # região sintética, fora do Brasil
    if dados_restritos.ALAGAMENTOS_PMPA.exists():                                    # só no disco de quem tem o dado real
        real = pd.read_csv(dados_restritos.ALAGAMENTOS_PMPA)
        assert not real[["lon", "lat"]].round(4).merge(f[["lon", "lat"]].round(4), on=["lon", "lat"]).shape[0]


def test_the_exploratory_models_run_end_to_end_from_the_synthetic_csv_without_any_restricted_data():
    g = sinteticos.grade_com_sinal()
    r = exp.rodar(g, pd.read_csv(FIXTURE), raio_m=50)           # a mesma entrada (arquivo CSV com camada, lon, lat) que a análise real recebe
    assert r["blocos_separados_entre_treino_e_teste"] and r["trechos_rotulados"] >= 30
    m = r["modelos"]
    assert set(m) == {"regra_de_terreno", "regressao_logistica", "gradient_boosting", "mlp"}
    assert m["regressao_logistica"]["precisao_media"] > 2 * m["regra_de_terreno"]["precisao_media"]    # o sinal plantado é encontrado; a regra de pesos iguais não
    # idêntico ao teste que gera os pontos no próprio código: o arquivo não muda o resultado
    r2 = exp.rodar(g, sinteticos.pontos_alagados(g), raio_m=50)
    assert r2["trechos_rotulados"] == r["trechos_rotulados"] and r2["modelos"]["regra_de_terreno"]["auc"] == pytest.approx(m["regra_de_terreno"]["auc"])


def test_the_real_flood_list_is_never_inside_the_repository_tree_that_git_tracks():
    assert dados_restritos.ALAGAMENTOS_PMPA.parts[-2:] == ("prefeitura_poa", "alagamentos_pmpa_coordenadas.csv") or "FM_ALAGAMENTOS_CSV" in __import__("os").environ
    assert not (RAIZ / "tests/dados/alagamentos_pmpa_coordenadas.csv").exists(), "o arquivo real não pode voltar para tests/dados (que o Git rastreia)"
    assert "licença não confirmada" in dados_restritos.MOTIVO_AUSENTE


def test_a_missing_restricted_file_stops_with_a_clear_message_not_a_traceback(monkeypatch, tmp_path):
    monkeypatch.setattr(dados_restritos, "ALAGAMENTOS_PMPA", tmp_path / "nao_existe.csv")
    with pytest.raises(SystemExit, match="Dado ausente.*licença não confirmada"):
        dados_restritos.ler_alagamentos()
    ok = tmp_path / "ok.csv"
    pd.read_csv(FIXTURE).to_csv(ok, index=False)
    monkeypatch.setattr(dados_restritos, "ALAGAMENTOS_PMPA", ok)
    assert list(dados_restritos.ler_alagamentos().columns) == ["camada", "lon", "lat"]


def test_every_test_that_needs_real_third_party_data_is_skipped_with_a_clear_reason_when_it_is_absent():
    import re
    for nome in ("test_experimento_modelos.py", "test_experimento_sensibilidade.py", "test_robustez_espacial.py"):
        texto = (Path(__file__).parent / nome).read_text(encoding="utf-8")
        marcas = re.findall(r"@pytest\.mark\.skipif\(([^\n]*)\)", texto)
        assert marcas and all("COORDS.exists()" in m and "MOTIVO_AUSENTE" in m for m in marcas), nome
