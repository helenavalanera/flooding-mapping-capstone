"""Confere o índice de terreno da rede com os alagamentos registrados pela Prefeitura de Porto Alegre (mapa "Áreas de Alagamento").

    python tools/validar_terreno_alagamentos_pmpa.py <mapa.kml> [saida.json]

Baixe o KML público em https://www.google.com/maps/d/kml?mid=1pJ6wqw8YJLxbG7q4IZGCRqP07Os&forcekml=1
Usa SÓ as coordenadas: a camada de ocorrências da Defesa Civil traz nome e telefone de solicitantes, que nunca são lidos nem gravados.
Mede o terreno (percentil da rede), não a chuva: os registros são de 2013-2014 e dizem onde alagou, não quando nem com quanto de chuva.
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.metrics import average_precision_score, roc_auc_score

NS = {"k": "http://www.opengis.net/kml/2.2"}
RAIZ = Path(__file__).resolve().parents[1]
CAMADAS = {"pontos_2014": ("Pontos de Alagamento", "Point"), "defesa_civil_2013": ("Ocorrências", "Point"), "trechos_2014": ("Trechos", "LineString")}


def coordenadas(doc, prefixo: str, geometria: str) -> np.ndarray:
    pasta = next(f for f in doc.findall("k:Folder", NS) if f.find("k:name", NS).text.startswith(prefixo))
    out = []
    for c in pasta.iterfind(f".//k:{geometria}/k:coordinates", NS):
        out += [list(map(float, t.split(",")[:2])) for t in c.text.split()]
    return np.array(out)


def avaliar(kml: str, rede: str, raio_m: float = 100) -> dict:
    doc = ET.parse(kml).getroot().find("k:Document", NS)
    g = pd.read_parquet(rede, columns=["lon0", "lat0", "lon1", "lat1", "percentil"])
    kx, ky = np.cos(np.radians(-30.05)) * 111320, 110574
    arvore = cKDTree(np.c_[(g.lon0 + g.lon1) / 2 * kx, (g.lat0 + g.lat1) / 2 * ky])
    pc, ok = g.percentil.to_numpy(), g.percentil.notna().to_numpy()
    total, saida = np.zeros(len(g), bool), {}
    for nome, (prefixo, geom) in CAMADAS.items():
        p = coordenadas(doc, prefixo, geom)
        d, i = arvore.query(np.c_[p[:, 0] * kx, p[:, 1] * ky], distance_upper_bound=raio_m)
        m = np.zeros(len(g), bool)
        m[i[d <= raio_m]] = True
        total |= m
        saida[nome] = _medidas(m, pc, ok, len(p))
    saida["todos"] = _medidas(total, pc, ok, None)
    return {"raio_m": raio_m, "camadas": saida}


def _medidas(m, pc, ok, n_geom) -> dict:
    rot = m & ok
    return {"coordenadas": n_geom, "trechos_rotulados": int(rot.sum()), "percentil_mediano": round(float(np.median(pc[rot])), 1),
            "no_quartil_mais_exposto": round(float((pc[rot] >= 75).mean()), 3), "no_decil_mais_exposto": round(float((pc[rot] >= 90).mean()), 3),
            "auc": round(float(roc_auc_score(m[ok], pc[ok])), 3), "precisao_media": round(float(average_precision_score(m[ok], pc[ok])), 5),
            "taxa_base": round(float(m[ok].mean()), 5)}


if __name__ == "__main__":
    r = avaliar(sys.argv[1], str(RAIZ / "data/processed/rede_poa.parquet"))
    saida = Path(sys.argv[2] if len(sys.argv) > 2 else RAIZ / "reports/qa/terreno_alagamentos_pmpa.json")
    saida.write_text(json.dumps(r, ensure_ascii=False, indent=2))
    print(json.dumps(r["camadas"]["todos"], ensure_ascii=False, indent=2))
