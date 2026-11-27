"""Avaliação PILOTO do MDT 2010 da Prefeitura de Porto Alegre contra o Copernicus GLO-30 já usado pelo projeto.

    PYTHONPATH=src python tools/avaliar_mdt_poa.py <RRCM_PMPA.kml> [saida.json]

1. Exatidão vertical: altitude de cada marco geodésico da Prefeitura (altitude ortométrica) contra o MDT 2010 (identify no serviço) e contra o Copernicus, nos MESMOS pontos.
2. Microrrelevo: numa área de 1 km² escolhida por critério objetivo (a vizinhança com mais registros de alagamento), preenchimento de depressões nos dois modelos:
   quantas depressões, que profundidade e que área ocupam. Isso mede a CAPACIDADE de enxergar depressões; NÃO é volume retido nem volume físico: o preenchimento também
   acusa buracos de ruído, lagos e canais, e uma depressão de modelo só é retenção se não tiver saída por drenagem, o que o relevo não diz.
Nada aqui substitui o DEM atual: é a medida para decidir se vale uma avaliação maior. Licença e precisão vertical do MDT NÃO constam no serviço: dependem de confirmação formal.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.io import MemoryFile
from scipy import ndimage
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flooding_mapping.dados_restritos import ler_alagamentos  # noqa: E402
from flooding_mapping.susceptibility import fill_depressions  # noqa: E402
from validar_altitude_rrcm import marcos  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
MDT = "https://gis-smamus.portoalegre.rs.gov.br/server/rest/services/C01_URBAN/urb_mdt_2010_102100/ImageServer"
SESSAO = requests.Session()
SESSAO.headers["User-Agent"] = "flooding-mapping-avaliacao/1.0 (projeto academico)"
R = 6378137.0


def mercator(lon, lat):
    return np.radians(lon) * R, np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)) * R


def identify(lon: float, lat: float):
    for t in range(3):
        try:
            r = SESSAO.get(MDT + "/identify", params={"geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}), "geometryType": "esriGeometryPoint",
                                                      "returnGeometry": "false", "returnCatalogItems": "false", "f": "json"}, timeout=60)
            v = r.json().get("value")
            return float(v) if v not in (None, "NoData", "") else None
        except (requests.RequestException, ValueError):
            time.sleep(1 + t)
    return None


def copernicus(lon: float, lat: float):
    tile = RAIZ / "data/raw/dem" / f"Copernicus_DSM_COG_10_S{int(np.ceil(-lat)):02d}_00_W{int(np.ceil(-lon)):03d}_00_DEM.tif"
    with rasterio.open(tile) as src:
        v = next(src.sample([(lon, lat)]))[0]
        return None if src.nodata is not None and v == src.nodata else float(v)


def erros(modelo: np.ndarray, ref: np.ndarray) -> dict:
    ok = ~np.isnan(modelo)
    e = modelo[ok] - ref[ok]
    return {"n": int(ok.sum()), "vies_m": round(float(e.mean()), 2), "mae_m": round(float(np.abs(e).mean()), 2), "rmse_m": round(float(np.sqrt((e ** 2).mean())), 2),
            "rmse_sem_vies_m": round(float(e.std()), 2), "spearman": round(float(spearmanr(modelo[ok], ref[ok])[0]), 3),
            "dentro_de_1m": round(float((np.abs(e) <= 1).mean()), 3), "dentro_de_2m": round(float((np.abs(e) <= 2).mean()), 3), "dentro_de_5m": round(float((np.abs(e) <= 5).mean()), 3)}


def exatidao_vertical(kml: str) -> dict:
    m = marcos(kml)
    m["mdt"] = [identify(a, b) for a, b in zip(m.lon, m.lat)]
    m["cop"] = [copernicus(a, b) for a, b in zip(m.lon, m.lat)]
    m["mdt"], m["cop"] = m.mdt.astype(float), m.cop.astype(float)
    ref = m.h_orto.to_numpy(float)
    comuns = ~m.mdt.isna() & ~m.cop.isna()
    baixos = comuns & (m.h_orto < 10)
    return {"marcos": int(len(m)), "marcos_sem_valor_no_mdt": int(m.mdt.isna().sum()), "marcos_sem_valor_no_copernicus": int(m.cop.isna().sum()), "marcos_nos_dois": int(comuns.sum()),
            "mdt_2010": erros(m.mdt.to_numpy(float), ref), "copernicus_glo30": erros(m.cop.to_numpy(float), ref),
            "mesmos_pontos": {"mdt_2010": erros(np.where(comuns, m.mdt, np.nan), ref), "copernicus_glo30": erros(np.where(comuns, m.cop, np.nan), ref)},
            "cotas_abaixo_de_10m": {"n": int(baixos.sum()), "mdt_2010": erros(np.where(baixos, m.mdt, np.nan), ref), "copernicus_glo30": erros(np.where(baixos, m.cop, np.nan), ref)}}


def recorte(lon: float, lat: float, lado: int = 1000):
    """1000 x 1000 pixels (1 unit of Web Mercator each) of the MDT around a point, as float32."""
    x, y = mercator(lon, lat)
    bbox = f"{x - lado / 2},{y - lado / 2},{x + lado / 2},{y + lado / 2}"
    r = SESSAO.get(MDT + "/exportImage", params={"bbox": bbox, "bboxSR": 3857, "imageSR": 3857, "size": f"{lado},{lado}", "format": "tiff", "pixelType": "F32", "noData": -9999,
                                                 "interpolation": "RSP_NearestNeighbor", "f": "image"}, timeout=180)
    r.raise_for_status()
    with MemoryFile(r.content) as mf, mf.open() as src:
        a = src.read(1).astype("float64")
    a[a <= -9000] = np.nan
    return a


def depressoes(dem: np.ndarray, pixel_m: float, minimo_m: float = 0.05) -> dict:
    cheio = fill_depressions(dem)
    prof = np.where(np.isnan(dem), 0, cheio - dem)
    mascara = prof > minimo_m
    rotulos, n = ndimage.label(mascara)
    areas = ndimage.sum(mascara, rotulos, range(1, n + 1)) * pixel_m ** 2 if n else np.array([])
    return {"depressoes_acima_de_5cm": int(n), "area_total_m2": round(float(mascara.sum() * pixel_m ** 2), 1), "maior_depressao_m2": round(float(areas.max()), 1) if n else 0.0,
            "profundidade_maxima_m": round(float(prof.max()), 2), "profundidade_mediana_nas_depressoes_m": round(float(np.median(prof[mascara])), 3) if mascara.any() else 0.0,
            "armazenamento_potencial_do_modelo_m3": round(float(prof[mascara].sum() * pixel_m ** 2), 1)}


def area_piloto(coords: pd.DataFrame) -> tuple:
    """Centre of the densest cluster of flood records (objective criterion, not chosen by the result)."""
    kx, ky = np.cos(np.radians(-30.05)) * 111320, 110574
    xy = np.c_[coords.lon * kx, coords.lat * ky]
    cont = [(np.hypot(*(xy - p).T) < 500).sum() for p in xy]
    i = int(np.argmax(cont))
    viz = np.hypot(*(xy - xy[i]).T) < 500
    return float(coords.lon[viz].mean()), float(coords.lat[viz].mean()), int(viz.sum())


def microrrelevo(coords: pd.DataFrame) -> dict:
    lon, lat, n = area_piloto(coords)
    mdt = recorte(lon, lat)
    pixel_m = 1.0 * np.cos(np.radians(lat))                      # one Web Mercator unit is cos(lat) metres on the ground
    x, y = mercator(lon, lat)
    # Copernicus on the same ground footprint (30 m cells)
    metade = 500 * np.cos(np.radians(lat))
    graus = metade / 111320
    tile = RAIZ / "data/raw/dem" / f"Copernicus_DSM_COG_10_S{int(np.ceil(-lat)):02d}_00_W{int(np.ceil(-lon)):03d}_00_DEM.tif"
    with rasterio.open(tile) as src:
        janela = rasterio.windows.from_bounds(lon - graus / np.cos(np.radians(lat)), lat - graus, lon + graus / np.cos(np.radians(lat)), lat + graus, src.transform)
        cop = src.read(1, window=janela, boundless=True, fill_value=np.nan).astype("float64")
        cop_pixel = abs(src.transform.a) * 111320 * np.cos(np.radians(lat))
    reduzido = mdt[:: int(round(cop_pixel / pixel_m)), :: int(round(cop_pixel / pixel_m))]
    return {"centro": {"lon": round(lon, 5), "lat": round(lat, 5)}, "registros_de_alagamento_na_vizinhanca_de_500m": n, "lado_m": round(1000 * np.cos(np.radians(lat))),
            "mdt_2010": {"pixel_m": round(pixel_m, 3), "pixels_validos": int((~np.isnan(mdt)).sum()), "altitude_min_max_m": [round(float(np.nanmin(mdt)), 1), round(float(np.nanmax(mdt)), 1)],
                         "desnivel_p5_p95_m": round(float(np.nanpercentile(mdt, 95) - np.nanpercentile(mdt, 5)), 2), **depressoes(mdt, pixel_m)},
            "copernicus_glo30": {"pixel_m": round(cop_pixel, 1), "pixels_validos": int((~np.isnan(cop)).sum()), "altitude_min_max_m": [round(float(np.nanmin(cop)), 1), round(float(np.nanmax(cop)), 1)],
                                 "desnivel_p5_p95_m": round(float(np.nanpercentile(cop, 95) - np.nanpercentile(cop, 5)), 2), **depressoes(cop, cop_pixel)},
            "mdt_reduzido_a_30m": {"pixel_m": round(pixel_m * int(round(cop_pixel / pixel_m)), 1), **depressoes(reduzido, pixel_m * int(round(cop_pixel / pixel_m)))},
            "leitura": "Capacidade de enxergar depressões, não volume retido: o preenchimento também acusa ruído, canais e lagos, e uma depressão só retém se não tiver saída por drenagem."}


if __name__ == "__main__":
    coords = ler_alagamentos()
    r = {"fonte_mdt": MDT, "exatidao_vertical": exatidao_vertical(sys.argv[1]), "microrrelevo_na_area_piloto": microrrelevo(coords),
         "limitacoes": ["Licença e precisão vertical declaradas do MDT não constam no serviço: exigem confirmação formal com a Prefeitura.",
                        "O MDT é de 2010 (aerolevantamento): não representa mudanças posteriores no terreno.",
                        "Uma única área piloto de 1 km² e 334 marcos geodésicos (concentrados em cotas e locais de levantamento): resultado indicativo, não validação geral.",
                        "O serviço é um Image Service (identify e exportImage), sem opção de download do arquivo: uma versão local exigiria exportar por blocos e confirmar a licença."]}
    saida = Path(sys.argv[2] if len(sys.argv) > 2 else RAIZ / "reports/qa/mdt_2010_piloto.json")
    saida.write_text(json.dumps(r, ensure_ascii=False, indent=2))
    print(json.dumps({"vertical": {k: r["exatidao_vertical"][k] for k in ("marcos", "marcos_nos_dois", "mesmos_pontos")}, "micro": r["microrrelevo_na_area_piloto"]}, ensure_ascii=False, indent=1))
