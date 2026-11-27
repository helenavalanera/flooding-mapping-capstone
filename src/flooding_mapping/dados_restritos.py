"""Dados de terceiros que NÃO vão ao Git (licença ou redistribuição não confirmada) e onde procurá-los no disco local.

Hoje há um: as coordenadas dos alagamentos registrados pela Prefeitura de Porto Alegre (127 pontos, 2013 e 2014), usadas só na validação exploratória
do terreno. O arquivo fica em ``data/raw/prefeitura_poa/`` (ignorado pelo Git) ou no caminho dado por ``FM_ALAGAMENTOS_CSV``. Quem não o tem (um clone
limpo) roda os testes sintéticos, que não dependem dele, e vê os testes com dados reais ignorados com esta mensagem.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from .config import ROOT

ALAGAMENTOS_PMPA = Path(os.environ.get("FM_ALAGAMENTOS_CSV") or ROOT / "data/raw/prefeitura_poa/alagamentos_pmpa_coordenadas.csv")
MOTIVO_AUSENTE = ("falta a lista de alagamentos da Prefeitura (dado de terceiros, fora do Git, licença não confirmada): "
                  "data/raw/prefeitura_poa/alagamentos_pmpa_coordenadas.csv ou FM_ALAGAMENTOS_CSV")


def ler_alagamentos() -> pd.DataFrame:
    """As coordenadas dos alagamentos (colunas ``camada``, ``lon``, ``lat``); sai com uma mensagem clara quando o arquivo não está no disco."""
    if not ALAGAMENTOS_PMPA.exists():
        raise SystemExit(f"Dado ausente: {MOTIVO_AUSENTE}")
    return pd.read_csv(ALAGAMENTOS_PMPA)
