"""Geração de escoamento por classe de uso do solo: a estrutura de cálculo que a Fase 3 vai usar. Nada aqui estima volume retido, profundidade nem duração.

    V = P x A x C / 1000        V em m³, P em mm, A em m², C adimensional (0 a 1)

(1 mm de chuva sobre 1 m² é 1 litro, ou 0,001 m³.) O resultado é ÁGUA POTENCIALMENTE ESCOADA DA SUPERFÍCIE, um limite superior do que chega a escoar: não desconta infiltração
nem perdas iniciais, não diz para onde a água vai e não é volume retido.

Dois métodos independentes, nunca somados em um número só:

* Método 1, coeficientes fundamentados (``config/uso_solo_coeficientes_metodo1_fundamentados.csv``): só as classes com referência direta (edificação e via pavimentada).
  Cada resultado é um INTERVALO [C_min, C_max] e as classes sem referência ficam como "não cobertas", nunca preenchidas.
* Método 2, cenários determinísticos (``config/uso_solo_cenarios_metodo2_hipoteticos.csv``): hipóteses declaradas para as classes que o Método 1 não cobre, cada uma com a natureza do
  valor (limite físico, referência externa por analogia ou mistura de referências com fração hipotética). São cenários, não medições.

As classes de Área Úmida e Corpo Hídrico não recebem coeficiente (``fora_do_calculo_de_escoamento``).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from .config import resolve

METODO1 = "config/uso_solo_coeficientes_metodo1_fundamentados.csv"
METODO2 = "config/uso_solo_cenarios_metodo2_hipoteticos.csv"
NATUREZAS = {"limite_fisico", "referencia_externa_por_analogia", "mistura_de_referencias_com_fracao_hipotetica", "fora_do_calculo_de_escoamento"}
AVISO = "Água potencialmente escoada da superfície (limite superior, sem infiltração nem perdas): não é volume retido, profundidade nem duração."


def volume_gerado_m3(precipitacao_mm, area_m2, c):
    """V = P x A x C / 1000, validated: P >= 0 mm, A >= 0 m², 0 <= C <= 1. Works element-wise on arrays."""
    p, a, k = (np.asarray(x, dtype=float) for x in (precipitacao_mm, area_m2, c))
    for nome, x in (("precipitação", p), ("área", a), ("coeficiente", k)):
        if not np.all(np.isfinite(x)):
            raise ValueError(f"{nome} deve ser finita")
    if np.any(p < 0):
        raise ValueError("a precipitação (mm) não pode ser negativa")
    if np.any(a < 0):
        raise ValueError("a área (m²) não pode ser negativa")
    if np.any((k < 0) | (k > 1)):
        raise ValueError("o coeficiente de escoamento é adimensional e fica entre 0 e 1")
    v = p * a * k / 1000.0
    return float(v) if v.ndim == 0 else v


def carregar_metodo1(caminho: str | Path | None = None) -> pd.DataFrame:
    t = pd.read_csv(caminho or resolve(METODO1))
    obrigatorias = {"classe_original", "c_min", "c_max", "referencia", "valor_citado", "justificativa", "grau_de_incerteza"}
    if not obrigatorias <= set(t.columns):
        raise ValueError(f"faltam colunas no Método 1: {sorted(obrigatorias - set(t.columns))}")
    if t.classe_original.duplicated().any():
        raise ValueError("classe repetida no Método 1")
    if not ((t.c_min >= 0) & (t.c_max <= 1) & (t.c_min <= t.c_max)).all():
        raise ValueError("coeficientes do Método 1 fora de 0 <= c_min <= c_max <= 1")
    if t.referencia.isna().any() or (t.referencia.astype(str).str.strip() == "").any():
        raise ValueError("coeficiente sem referência no Método 1")
    return t


def carregar_cenarios(caminho: str | Path | None = None) -> pd.DataFrame:
    t = pd.read_csv(caminho or resolve(METODO2))
    obrigatorias = {"cenario", "classe_original", "c_min", "c_max", "natureza_do_valor", "referencia", "hipotese_declarada", "grau_de_incerteza"}
    if not obrigatorias <= set(t.columns):
        raise ValueError(f"faltam colunas nos cenários: {sorted(obrigatorias - set(t.columns))}")
    if not set(t.natureza_do_valor) <= NATUREZAS:
        raise ValueError(f"natureza do valor desconhecida: {sorted(set(t.natureza_do_valor) - NATUREZAS)}")
    com_valor = t[t.natureza_do_valor != "fora_do_calculo_de_escoamento"]
    if not ((com_valor.c_min >= 0) & (com_valor.c_max <= 1) & (com_valor.c_min <= com_valor.c_max)).all():
        raise ValueError("coeficientes dos cenários fora de 0 <= c_min <= c_max <= 1")
    fora = t[t.natureza_do_valor == "fora_do_calculo_de_escoamento"]
    if fora.c_min.notna().any() or fora.c_max.notna().any():
        raise ValueError("classe fora do cálculo não pode ter coeficiente")
    if com_valor.hipotese_declarada.isna().any() or (com_valor.hipotese_declarada.astype(str).str.strip() == "").any():
        raise ValueError("cenário sem hipótese declarada")
    fis = t[t.natureza_do_valor == "limite_fisico"]
    if not fis.c_min.isin([0.0, 1.0]).all() or not (fis.c_min == fis.c_max).all():
        raise ValueError("limite físico só pode ser C = 0 ou C = 1")
    if t.duplicated(["cenario", "classe_original"]).any():
        raise ValueError("classe repetida dentro de um cenário")
    return t


def _por_classe(areas_m2: Mapping[str, float], faixas: Mapping[str, tuple], p_mm: float) -> tuple:
    por, vmin, vmax, coberta = {}, 0.0, 0.0, 0.0
    for classe, (lo, hi) in faixas.items():
        a = float(areas_m2.get(classe, 0.0))
        por[classe] = {"area_m2": a, "c": [lo, hi], "volume_m3": [volume_gerado_m3(p_mm, a, lo), volume_gerado_m3(p_mm, a, hi)]}
        vmin, vmax, coberta = vmin + por[classe]["volume_m3"][0], vmax + por[classe]["volume_m3"][1], coberta + a
    return por, vmin, vmax, coberta


def _resto(areas_m2: Mapping[str, float], usadas: set, fora: set) -> tuple:
    sem_valor = {c: float(a) for c, a in areas_m2.items() if c not in usadas and c not in fora}
    return sem_valor, float(sum(float(areas_m2.get(c, 0.0)) for c in fora))


def geracao_metodo1(areas_m2: Mapping[str, float], precipitacao_mm: float, metodo1: pd.DataFrame | None = None, fora_do_calculo: Sequence[str] = ("Área Úmida", "Corpo Hídrico")) -> dict:
    """Method 1: an interval of generated volume for the classes with a referenced coefficient. Everything else is reported as not covered, never filled."""
    m1 = carregar_metodo1() if metodo1 is None else metodo1
    faixas = {r.classe_original: (float(r.c_min), float(r.c_max)) for r in m1.itertuples()}
    por, vmin, vmax, coberta = _por_classe(areas_m2, faixas, precipitacao_mm)
    sem_valor, area_fora = _resto(areas_m2, set(faixas), set(fora_do_calculo))
    return {"metodo": 1, "natureza": "coeficientes fundamentados em referência", "precipitacao_mm": precipitacao_mm, "volume_m3": {"min": vmin, "max": vmax}, "area_coberta_m2": coberta,
            "area_nao_coberta_pelo_metodo_m2": float(sum(sem_valor.values())), "area_fora_do_calculo_m2": area_fora, "classes_nao_cobertas": sem_valor, "por_classe": por, "aviso": AVISO}


def geracao_cenario(areas_m2: Mapping[str, float], precipitacao_mm: float, cenarios: Sequence[str], tabela: pd.DataFrame | None = None, metodo1: pd.DataFrame | None = None) -> dict:
    """Method 2: one or more scenarios applied ONLY to the classes that Method 1 does not cover. Scenarios combined here must not give a value to the same class twice."""
    t = carregar_cenarios() if tabela is None else tabela
    m1 = carregar_metodo1() if metodo1 is None else metodo1
    escolhidos = t[t.cenario.isin(list(cenarios))]
    ausentes = set(cenarios) - set(escolhidos.cenario)
    if ausentes:
        raise ValueError(f"cenário desconhecido: {sorted(ausentes)}")
    com_valor = escolhidos[escolhidos.natureza_do_valor != "fora_do_calculo_de_escoamento"]
    if com_valor.classe_original.duplicated().any():
        raise ValueError("os cenários combinados dão valor duas vezes à mesma classe")
    if set(com_valor.classe_original) & set(m1.classe_original):
        raise ValueError("cenário não pode redefinir uma classe do Método 1: os métodos são independentes")
    faixas = {r.classe_original: (float(r.c_min), float(r.c_max)) for r in com_valor.itertuples()}
    fora = set(t[t.natureza_do_valor == "fora_do_calculo_de_escoamento"].classe_original)
    por, vmin, vmax, coberta = _por_classe(areas_m2, faixas, precipitacao_mm)
    sem_valor, area_fora = _resto({c: a for c, a in areas_m2.items() if c not in set(m1.classe_original)}, set(faixas), fora)
    return {"metodo": 2, "natureza": "cenários determinísticos com hipótese declarada (não são medições)", "cenarios": list(cenarios), "precipitacao_mm": precipitacao_mm,
            "volume_m3": {"min": vmin, "max": vmax}, "area_coberta_pelo_cenario_m2": coberta, "area_sem_valor_no_cenario_m2": float(sum(sem_valor.values())), "area_fora_do_calculo_m2": area_fora,
            "classes_sem_valor_no_cenario": sem_valor, "por_classe": por, "hipoteses": {c: h for c, h in zip(com_valor.classe_original, com_valor.hipotese_declarada)}, "aviso": AVISO}
