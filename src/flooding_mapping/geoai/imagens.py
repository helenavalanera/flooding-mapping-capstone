"""Obtenção e preparação das imagens Sentinel-2 L2A: consulta ao catálogo STAC, qualidade por cena, janelas em cache e composição.

Só lê metadados e janelas de COG públicos (AWS Open Data, sem credencial). Nada é gravado fora de ``cache``.
A reflectância é ``DN * escala + deslocamento``. A escala e o deslocamento vêm dos metadados STAC, mas o deslocamento declarado é CONFERIDO contra os próprios
valores (``deslocamento_efetivo``): nas 30 cenas reprocessadas (linha 05.00) deste experimento os metadados declaram -0,1 e os DN não trazem o +1000
correspondente (mediana do azul em DN ~ 450 e 87 a 97% dos pixels abaixo de 1.000), de modo que aplicar o deslocamento daria reflectância negativa.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
import shapely
from pyproj import Transformer
from scipy import ndimage

log = logging.getLogger(__name__)
GDAL_ENV = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif", "GDAL_HTTP_MAX_RETRY": "4", "GDAL_HTTP_RETRY_DELAY": "2"}


@dataclass(frozen=True)
class Janela:
    """Recorte em pixels de 10 m do tile; começa e termina em pixel par para que o recorte de 20 m coincida exatamente."""
    linha: int
    coluna: int
    linhas: int
    colunas: int


def consultar_stac(url: str, colecao: str, bbox: list[float], inicio: str, fim: str, limite: int = 100) -> list[dict]:
    """Todas as cenas da coleção que intersectam ``bbox`` (lon/lat) no período; segue a paginação do catálogo."""
    corpo = {"collections": [colecao], "bbox": bbox, "datetime": f"{inicio}T00:00:00Z/{fim}T23:59:59Z", "limit": limite}
    itens, resp = [], requests.post(url, json=corpo, timeout=60)
    while True:
        resp.raise_for_status()
        dados = resp.json()
        itens += dados.get("features", [])
        prox = [lk for lk in dados.get("links", []) if lk.get("rel") == "next"]
        if not prox:
            return itens
        lk = prox[0]
        resp = requests.post(lk["href"], json=lk.get("body", {}), timeout=60) if lk.get("method", "GET") == "POST" else requests.get(lk["href"], timeout=60)


def deduplicar(itens: list[dict]) -> list[dict]:
    """A mesma aquisição aparece reprocessada várias vezes (``_0_``, ``_1_``...): fica a de geração mais recente."""
    por_data: dict[str, dict] = {}
    for it in itens:
        p = it["properties"]
        atual = por_data.get(p["datetime"])
        if atual is None or p.get("s2:generation_time", "") > atual["properties"].get("s2:generation_time", ""):
            por_data[p["datetime"]] = it
    return sorted(por_data.values(), key=lambda i: i["properties"]["datetime"])


def janela_do_municipio(grade: dict, crs_grade: str, crs_cena: str, transform_cena: list[float], forma_cena: tuple[int, int], margem_m: float) -> Janela:
    """Menor janela par de pixels de 10 m que contém a caixa da grade do projeto mais a margem."""
    x0, y0 = grade["origem_x"], grade["origem_y"]
    x1, y1 = x0 + grade["colunas"] * grade["celula_m"], y0 - grade["linhas"] * grade["celula_m"]
    t = Transformer.from_crs(crs_grade, crs_cena, always_xy=True)
    pts = [t.transform(x, y) for x in (x0, x1) for y in (y0, y1)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    tamanho, ox, oy = transform_cena[0], transform_cena[2], transform_cena[5]
    c0 = int(np.floor((min(xs) - margem_m - ox) / tamanho)) // 2 * 2
    c1 = -(-int(np.ceil((max(xs) + margem_m - ox) / tamanho)) // 2) * 2
    l0 = int(np.floor((oy - (max(ys) + margem_m)) / tamanho)) // 2 * 2
    l1 = -(-int(np.ceil((oy - (min(ys) - margem_m)) / tamanho)) // 2) * 2
    if c0 < 0 or l0 < 0 or c1 > forma_cena[1] or l1 > forma_cena[0]:
        raise ValueError(f"o município não cabe no tile: colunas {c0}-{c1} de {forma_cena[1]}, linhas {l0}-{l1} de {forma_cena[0]}")
    return Janela(l0, c0, l1 - l0, c1 - c0)


def transform_da_janela(transform_cena: list[float], j: Janela, passo: int = 1) -> tuple[float, float, float]:
    """(origem x, origem y, tamanho do pixel em m) da janela; ``passo`` 2 para as bandas de 20 m."""
    return transform_cena[2] + j.coluna * transform_cena[0], transform_cena[5] - j.linha * transform_cena[0], transform_cena[0] * passo


def ler_janela(href: str, j: Janela, passo: int = 1) -> np.ndarray:
    import rasterio
    from rasterio.windows import Window
    with rasterio.Env(**GDAL_ENV), rasterio.open(href) as src:
        return src.read(1, window=Window(j.coluna // passo, j.linha // passo, j.colunas // passo, j.linhas // passo))


def mascara_do_municipio(poligono_utm: shapely.Geometry, j: Janela, transform_cena: list[float], passo: int = 2) -> np.ndarray:
    from rasterio import features
    from rasterio.transform import from_origin
    ox, oy, tam = transform_da_janela(transform_cena, j, passo)
    return features.rasterize([(poligono_utm, 1)], out_shape=(j.linhas // passo, j.colunas // passo), transform=from_origin(ox, oy, tam, tam), fill=0, dtype="uint8").astype(bool)


def pixels_validos(scl: np.ndarray, validas: list[int], nuvem_e_sombra: list[int], dilatar: int) -> np.ndarray:
    """Válido = classe aceita pela SCL e longe (``dilatar`` pixels) de nuvem, sombra e cirro."""
    ruim = ndimage.binary_dilation(np.isin(scl, nuvem_e_sombra), iterations=dilatar) if dilatar else np.isin(scl, nuvem_e_sombra)
    return np.isin(scl, validas) & ~ruim


def escolher_cenas(avaliadas: list[dict], minimo_valido: float, maximo: int) -> list[dict]:
    """Cenas com fração válida suficiente, no máximo ``maximo``, repartidas por ano (cada ano com no máximo um terço) e então pelas mais limpas."""
    boas = sorted((c for c in avaliadas if c["valido_no_municipio"] >= minimo_valido), key=lambda c: -c["valido_no_municipio"])
    anos = sorted({c["datetime"][:4] for c in boas})
    teto = max(1, -(-maximo // max(len(anos), 1)))
    contagem: dict[str, int] = {}
    escolhidas = []
    for c in boas:
        a = c["datetime"][:4]
        if contagem.get(a, 0) < teto and len(escolhidas) < maximo:
            contagem[a] = contagem.get(a, 0) + 1
            escolhidas.append(c)
    return sorted(escolhidas, key=lambda c: c["datetime"])


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def baixar_cena(item: dict, j: Janela, cfg: dict, pasta: Path) -> dict:
    """Grava as seis bandas e a SCL do recorte em ``pasta/<id>/*.npy`` (uint16/uint8) e devolve o registro com hashes. Cena já baixada é reaproveitada."""
    destino = pasta / item["id"]
    destino.mkdir(parents=True, exist_ok=True)
    reg_path = destino / "registro.json"
    if reg_path.exists():
        return json.loads(reg_path.read_text())
    bandas = {}
    for nome, passo in [(b, 1) for b in cfg["bandas_10m"]] + [(b, 2) for b in cfg["bandas_20m"]] + [(cfg["banda_scl"], 2)]:
        ativo = item["assets"][nome]
        rb = (ativo.get("raster:bands") or [{}])[0]
        a = ler_janela(ativo["href"], j, passo)
        np.save(destino / f"{nome}.npy", a)
        bandas[nome] = {"arquivo": f"{nome}.npy", "forma": list(a.shape), "passo": passo, "dtype": str(a.dtype), "escala": rb.get("scale", 1.0) if nome != cfg["banda_scl"] else None,
                        "deslocamento": rb.get("offset", 0.0) if nome != cfg["banda_scl"] else None, "nodata": rb.get("nodata"), "fonte": ativo["href"], "sha256": _sha256(destino / f"{nome}.npy")}
    p = item["properties"]
    reg = {"id": item["id"], "datetime": p["datetime"], "linha_de_processamento": p.get("s2:processing_baseline"), "gerado_em": p.get("s2:generation_time"), "janela": j.__dict__, "bandas": bandas}
    reg_path.write_text(json.dumps(reg, indent=1))
    return reg


def deslocamento_efetivo(dn_validos: np.ndarray, escala: float, deslocamento: float) -> float:
    """Deslocamento a aplicar: o declarado, só se os DN o contêm.

    Com deslocamento declarado de -0,1 e escala 1e-4, o DN de reflectância zero é 1.000: se o 1º percentil dos DN válidos está abaixo da metade disso,
    os DN não têm o +1000 e o deslocamento efetivo é zero.
    """
    if deslocamento == 0:
        return 0.0
    piso = -deslocamento / escala
    return float(deslocamento) if np.percentile(dn_validos, 1) >= 0.5 * piso else 0.0


def calibrar_deslocamentos(pasta_cenas: Path, registros: list[dict], banda: str = "blue") -> list[dict]:
    """Grava ``deslocamento_efetivo`` em todas as bandas de reflectância de cada cena, decidido pela banda ``banda`` (subamostra de 1 em 8)."""
    for reg in registros:
        b = reg["bandas"][banda]
        dn = np.load(pasta_cenas / reg["id"] / b["arquivo"], mmap_mode="r")[::8, ::8]
        dn = np.asarray(dn[dn != b["nodata"]])
        efetivo = deslocamento_efetivo(dn, b["escala"], b["deslocamento"])
        reg["deslocamento_conferido"] = {"banda": banda, "dn_p1": float(np.percentile(dn, 1)), "dn_mediana": float(np.median(dn)), "declarado": b["deslocamento"], "efetivo": efetivo}
        for nome, bb in reg["bandas"].items():
            if bb["escala"] is not None:
                bb["deslocamento_efetivo"] = efetivo
    return registros


def refletancia(cena_dir: Path, reg: dict, banda: str, linhas: tuple[int, int] | None = None) -> np.ndarray:
    """Reflectância (float32) da banda, na grade de 10 m; nodata vira NaN. ``linhas`` (início, fim) em pixels de 10 m lê só esse trecho (memória de 8 GB)."""
    b = reg["bandas"][banda]
    dn = np.load(cena_dir / b["arquivo"], mmap_mode="r")
    if b["passo"] == 2:
        a, f = (0, dn.shape[0]) if linhas is None else (linhas[0] // 2, -(-linhas[1] // 2))
        dn = np.repeat(np.repeat(np.asarray(dn[a:f]), 2, axis=0), 2, axis=1)[(0 if linhas is None else linhas[0] - 2 * a):][: (dn.shape[0] * 2 if linhas is None else linhas[1] - linhas[0])]
    else:
        dn = np.asarray(dn if linhas is None else dn[linhas[0]:linhas[1]])
    return np.where(dn == b["nodata"], np.nan, dn.astype("float32") * b["escala"] + b.get("deslocamento_efetivo", b["deslocamento"])).astype("float32")


def scl_10m(cena_dir: Path, reg: dict, linhas: tuple[int, int] | None = None) -> np.ndarray:
    a = np.load(cena_dir / reg["bandas"]["scl"]["arquivo"], mmap_mode="r")
    if linhas is None:
        return np.repeat(np.repeat(np.asarray(a), 2, axis=0), 2, axis=1)
    i, f = linhas[0] // 2, -(-linhas[1] // 2)
    return np.repeat(np.repeat(np.asarray(a[i:f]), 2, axis=0), 2, axis=1)[linhas[0] - 2 * i:][: linhas[1] - linhas[0]]


# ------------------------------------------------------------------------------------------------ embeddings AlphaEarth (Experimento B)
AEF_BUCKET = "https://storage.googleapis.com/alphaearth_foundations/"
AEF_PREFIXO = "satellite_embedding/v1/annual/{ano}/{zona}/"
AEF_ATRIBUICAO = "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and Google DeepMind."   # exigida pela licença CC-BY 4.0


def descontar_quantizacao(v: np.ndarray) -> np.ndarray:
    """int8 -> embedding em [-1, 1] (documentação oficial): dividir por 127,5, elevar ao quadrado e devolver o sinal. -128 é "sem dado" e vira NaN."""
    f = (v.astype("float32") / 127.5) ** 2 * np.sign(v)
    return np.where(v == -128, np.nan, f).astype("float32")


def listar_arquivos_aef(ano: int, zona: str) -> list[tuple[str, int]]:
    """(nome, bytes) dos GeoTIFF do ano e da zona UTM no bucket público (só metadados)."""
    url = "https://storage.googleapis.com/storage/v1/b/alphaearth_foundations/o"
    saida, token = [], None
    while True:
        r = requests.get(url, params={"prefix": AEF_PREFIXO.format(ano=ano, zona=zona), "maxResults": 1000, **({"pageToken": token} if token else {})}, timeout=60)
        r.raise_for_status()
        d = r.json()
        saida += [(i["name"], int(i["size"])) for i in d.get("items", []) if i["name"].endswith(".tiff")]
        token = d.get("nextPageToken")
        if not token:
            return saida


def baixar_embeddings(arquivos: list[str], caixa_utm: tuple[float, float, float, float], destino: Path) -> dict:
    """Recorta ``caixa_utm`` (xmin, ymin, xmax, ymax, no CRS do bucket) dos arquivos que a intersectam e grava ``destino`` (.npy int8, (linhas, colunas, 64), norte no topo).

    Os arquivos do bucket são COG de 10 m com 64 bandas int8; a leitura é por janelas de 1.024 linhas. Devolve origem do recorte e hashes.
    """
    import rasterio
    from rasterio.windows import Window
    xmin, ymin, xmax, ymax = caixa_utm
    xs0, xs1 = int(np.floor(xmin / 10)) * 10, int(np.ceil(xmax / 10)) * 10
    ys0, ys1 = int(np.floor(ymin / 10)) * 10, int(np.ceil(ymax / 10)) * 10
    W, H = (xs1 - xs0) // 10, (ys1 - ys0) // 10
    out = np.lib.format.open_memmap(destino, mode="w+", dtype="int8", shape=(H, W, 64))
    out[:] = -128
    usados = []
    with rasterio.Env(**{**GDAL_ENV, "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tiff", "GDAL_CACHEMAX": 512}):
        for nome in arquivos:
            with rasterio.open(AEF_BUCKET + nome) as src:
                b = src.bounds
                y_sul, y_norte = min(b.bottom, b.top), max(b.bottom, b.top)      # com pixel de altura positivo o rasterio troca bottom e top
                ax0, ax1, ay0, ay1 = max(xs0, b.left), min(xs1, b.right), max(ys0, y_sul), min(ys1, y_norte)
                if ax0 >= ax1 or ay0 >= ay1:
                    continue
                norte_acima = src.transform.e < 0      # o bucket tem rasters com o norte embaixo (e positivo): os dois casos são tratados
                lin_ini = int((y_norte - ay1) / 10) if norte_acima else int((ay0 - y_sul) / 10)
                n_lin, n_col = int((ay1 - ay0) / 10), int((ax1 - ax0) / 10)
                col_ini = int((ax0 - b.left) / 10)
                for l in range(0, n_lin, 1024):
                    h = min(1024, n_lin - l)
                    bloco = src.read(window=Window(col_ini, lin_ini + l, n_col, h))               # (64, h, n_col)
                    if not norte_acima:
                        bloco = bloco[:, ::-1, :]
                    if norte_acima:
                        topo_dest = int((ys1 - (ay1 - l * 10)) / 10)
                    else:
                        topo_dest = int((ys1 - (ay0 + (l + h) * 10)) / 10)
                    out[topo_dest:topo_dest + h, int((ax0 - xs0) / 10):int((ax0 - xs0) / 10) + n_col] = np.transpose(bloco, (1, 2, 0))
                usados.append(nome)
    out.flush()
    return {"arquivos": usados, "origem_x": xs0, "topo_y": ys1, "largura": W, "altura": H, "sha256": _sha256(destino)}


def arquivos_aef_que_cobrem(arquivos: list[tuple[str, int]], caixa_utm: tuple[float, float, float, float], threads: int = 8) -> list[dict]:
    """Lê só o cabeçalho de cada arquivo e devolve os que intersectam a caixa (xmin, ymin, xmax, ymax) com nome, bytes e extensão."""
    import rasterio
    from concurrent.futures import ThreadPoolExecutor

    def cabecalho(par: tuple[str, int]) -> dict | None:
        try:
            with rasterio.Env(**{**GDAL_ENV, "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tiff"}), rasterio.open(AEF_BUCKET + par[0]) as s:
                b = s.bounds
                return {"nome": par[0], "bytes": par[1], "xmin": b.left, "xmax": b.right, "ymin": min(b.bottom, b.top), "ymax": max(b.bottom, b.top), "crs": s.crs.to_string(), "bandas": s.count, "dtype": s.dtypes[0]}
        except Exception as e:  # noqa: BLE001
            log.warning("cabeçalho ilegível em %s: %s", par[0], e)
            return None

    with ThreadPoolExecutor(threads) as ex:
        todos = [c for c in ex.map(cabecalho, arquivos) if c]
    x0, y0, x1, y1 = caixa_utm
    return [c for c in todos if c["xmin"] < x1 and c["xmax"] > x0 and c["ymin"] < y1 and c["ymax"] > y0]
