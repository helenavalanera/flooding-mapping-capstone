"""Confere a altitude da rede de ruas (Copernicus DSM) com os marcos da RRCM com altitude ortométrica (nivelados, RNs e marcos principais/azimutais) da Prefeitura de Porto Alegre.

    python tools/validar_altitude_rrcm.py <RRCM_PMPA.kml> [saida.json]

Esses marcos trazem altitude ortométrica medida em campo (algumas com vírgula decimal): é a primeira verdade de terreno do projeto.
Não valida alagamento; só diz quanto a coluna ``elev`` da rede erra a cota do chão.
"""
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

NS = {"k": "http://www.opengis.net/kml/2.2"}
RAIZ = Path(__file__).resolve().parents[1]


def marcos(kml: str) -> pd.DataFrame:
    linhas = []
    for p in ET.parse(kml).getroot().iterfind(".//k:Placemark", NS):
        pt, d = p.find(".//k:Point/k:coordinates", NS), p.find("k:description", NS)
        if pt is None or d is None:
            continue
        h = re.search(r"Altitude ortom[ée]trica:\s*([-\d.,]+)", html.unescape(d.text or ""))
        if h:
            lon, lat, _ = map(float, pt.text.strip().split(","))
            linhas.append({"nome": p.find("k:name", NS).text, "lon": lon, "lat": lat, "h_orto": float(h.group(1).replace(",", "."))})
    return pd.DataFrame(linhas)


def comparar(kml: str, rede: str, raio_m: float = 100) -> dict:
    g = pd.read_parquet(rede, columns=["lon0", "lat0", "lon1", "lat1", "elev"])
    m = marcos(kml)
    kx, ky = np.cos(np.radians(-30.05)) * 111320, 110574
    arvore = cKDTree(np.c_[(g.lon0 + g.lon1) / 2 * kx, (g.lat0 + g.lat1) / 2 * ky])
    d, i = arvore.query(np.c_[m.lon * kx, m.lat * ky])
    m["dist_m"], m["elev"] = d, g.elev.to_numpy()[i]
    ok = m[(m.dist_m <= raio_m) & m.elev.notna()].copy()
    ok["erro"] = ok.elev - ok.h_orto
    baixos = ok[ok.h_orto < 10]
    return {"marcos_com_altitude_ortometrica": len(m), "comparados": len(ok), "sem_altitude_na_rede": int(m.elev.isna().sum()), "raio_m": raio_m,
            "vies_m": round(ok.erro.mean(), 2), "mae_m": round(ok.erro.abs().mean(), 2), "rmse_m": round(float(np.sqrt((ok.erro**2).mean())), 2),
            "erro_sem_vies_rmse_m": round(float(ok.erro.sub(ok.erro.mean()).pow(2).mean() ** .5), 2),
            "spearman": round(float(ok[["elev", "h_orto"]].corr("spearman").iloc[0, 1]), 3),
            "dentro_de_5m": round(float((ok.erro.abs() <= 5).mean()), 3),
            "cotas_abaixo_de_10m": {"n": len(baixos), "vies_m": round(baixos.erro.mean(), 2), "mae_m": round(baixos.erro.abs().mean(), 2)}}


if __name__ == "__main__":
    r = comparar(sys.argv[1], str(RAIZ / "data/processed/rede_poa.parquet"))
    saida = Path(sys.argv[2] if len(sys.argv) > 2 else RAIZ / "reports/qa/altitude_rrcm.json")
    saida.write_text(json.dumps(r, ensure_ascii=False, indent=2))
    print(json.dumps(r, ensure_ascii=False, indent=2))
