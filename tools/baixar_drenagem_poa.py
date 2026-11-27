"""Baixa as camadas de drenagem pluvial dos serviços GIS da Prefeitura de Porto Alegre para data/raw/drenagem_poa/ e registra a procedência.

    PYTHONPATH=src python tools/baixar_drenagem_poa.py [camada ...]        # sem argumentos, todas

É um processo de ATUALIZAÇÃO DE DADOS: a aplicação nunca consulta o servidor municipal ao carregar. Cada camada é pedida em lotes de OBJECTID (não depende de
paginação do servidor), com a geometria em SIRGAS 2000 / UTM 22S (EPSG:31982, métrica). Os registros são gravados ordenados por OBJECTID e em JSON compacto, então
rodar de novo sobre os mesmos dados dá o mesmo arquivo e o mesmo SHA-256 (idempotente: nada é duplicado, e o manifesto não muda).

Privacidade: NÃO são pedidos os campos com nomes de servidores ou de empresas (usuários de criação e atualização, fiscal, levantamento, execução), os de documentos e
links e o texto livre de observação: não servem ao projeto. O OBJECTID é o único identificador de origem (as camadas não trazem outro): ele é preservado, mas pode mudar
se a Prefeitura republicar a camada, por isso o manifesto guarda também a data e o hash da coleta.
"""
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from flooding_mapping import ingest

RAIZ = Path(__file__).resolve().parents[1]
BASE = "https://gis-smamus.portoalegre.rs.gov.br/server/rest/services/"
DESTINO = RAIZ / "data" / "raw" / "drenagem_poa"
MANIFESTO = RAIZ / "data" / "raw" / "manifest.json"
SRS_SAIDA = 31982
LOTE = 1000
VERSAO_PROCESSAMENTO = "1"
CONSULTA = "POA___Consultas_MIL1/MapServer/"
CAMADAS = {   # nome -> caminho no serviço (camadas de consulta: com altitudes e inserção; as públicas: sem esses campos)
    "rede_pluvial": CONSULTA + "57", "rede_pluvial_sem_acesso": CONSULTA + "58", "rede_pluvial_nao_interligada": CONSULTA + "59",
    "poco_de_visita": CONSULTA + "50", "boca_de_lobo": CONSULTA + "51", "grelha": CONSULTA + "52", "coletor_de_fundo": CONSULTA + "49",
    "canal_pluvial": CONSULTA + "53", "canal_pluvial_sem_acesso": CONSULTA + "54", "conduto_forcado": CONSULTA + "55", "recurso_hidrico": CONSULTA + "56",
    "publica_rede_pluvial": "01_PUBLICACOES/rede_pluvial/FeatureServer/0", "publica_boca_de_lobo": "01_PUBLICACOES/bocas_de_lobo/MapServer/0",
    "casas_de_bomba_ebap": "Hosted/Casas_de_Bomba___EBAP_210126/FeatureServer/0", "hidrografia_2014": "01_PUBLICACOES/ram_hidrografia_2014/MapServer/0",
    "risco_inundacao_cprm": "01_PUBLICACOES/inundacoes_cprm/FeatureServer/0",
}
# Registradas mas fora do conjunto padrão: o uso do solo (605 mil polígonos, estimados em centenas de MB) só é baixado quando o modelo precisar da geometria completa;
# até lá a auditoria usa as estatísticas do próprio servidor e um recorte piloto. Peça-a pelo nome: tools/baixar_drenagem_poa.py uso_do_solo_profill_2022
CAMADAS_SOB_DEMANDA = {"uso_do_solo_profill_2022": "01_PUBLICACOES/uso_solo_profill_2022/MapServer/0"}
EXCLUIDOS = ("usuario", "fiscal", "link", "docrecebid", "doc_recebid", "termogaran", "levantamen", "execucao", "observa", "gx_media", "street_vie", "saiba_mais")
SESSAO = requests.Session()
SESSAO.headers["User-Agent"] = "flooding-mapping-ingestao/1.0 (projeto academico; atualizacao de dados)"


def _pedido(metodo: str, url: str, tentativas: int = 4, **dados):
    for t in range(tentativas):
        try:
            r = SESSAO.request(metodo, url, timeout=120, **({"params": dados} if metodo == "GET" else {"data": dados}))
            r.raise_for_status()
            corpo = r.json()
            if "error" in corpo:
                raise RuntimeError(corpo["error"].get("message", "erro do servidor"))
            return corpo
        except (requests.RequestException, RuntimeError, ValueError) as erro:
            if t == tentativas - 1:
                raise SystemExit(f"falha ao consultar {url}: {type(erro).__name__}") from None
            time.sleep(2 ** t)


def campos_permitidos(meta: dict) -> list:
    """Technical fields only: names of staff, contractors, documents, links and free text are left out."""
    return [f["name"] for f in meta["fields"] if f["type"] != "esriFieldTypeGeometry" and not f["name"].lower().startswith(EXCLUIDOS)]


def _geometria_finita(g: dict) -> bool:
    """False for a geometry whose coordinates are NaN or infinite: the service sends it as present, but it cannot be used."""
    def ok(c):
        return all(isinstance(v, (int, float)) and math.isfinite(v) for v in c[:2])
    if "x" in g:
        return ok((g.get("x"), g.get("y")))
    return all(ok(c) for parte in (g.get("paths") or g.get("rings") or []) for c in parte)


def baixar_camada(nome: str, caminho: str, destino: Path = DESTINO, manifesto: Path = MANIFESTO) -> dict:
    url = BASE + caminho
    meta = _pedido("GET", url, f="json")
    campos = campos_permitidos(meta)
    oid = next(f["name"] for f in meta["fields"] if f["type"] == "esriFieldTypeOID")
    ids = sorted(_pedido("GET", url + "/query", where="1=1", returnIdsOnly="true", f="json")["objectIds"] or [])
    feicoes, rejeitadas, nao_finitas = [], 0, 0
    for i in range(0, len(ids), LOTE):
        lote = ids[i:i + LOTE]
        corpo = _pedido("POST", url + "/query", objectIds=",".join(map(str, lote)), outFields=",".join(campos), returnGeometry="true", outSR=SRS_SAIDA, f="json")
        for f in corpo.get("features", []):
            if f.get("geometry") is None:
                rejeitadas += 1
                continue
            if not _geometria_finita(f["geometry"]):
                nao_finitas += 1
                continue
            feicoes.append({"atributos": f["attributes"], "geometria": f["geometry"]})
        time.sleep(0.15)
    feicoes.sort(key=lambda f: f["atributos"][oid])
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"{nome}.json"
    conteudo = {"camada": nome, "fonte": url, "nome_na_fonte": meta.get("name"), "tipo_de_geometria": meta.get("geometryType"), "srid": SRS_SAIDA,
                "campo_de_identificador": oid, "campos": campos, "feicoes": feicoes}
    arquivo.write_text(json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    entrada = {"url": url + "/query", "path": str(arquivo.relative_to(RAIZ)), "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "sha256": ingest.sha256_file(arquivo), "size_bytes": arquivo.stat().st_size, "source_reference_date": None, "origin": "serviço ArcGIS REST da Prefeitura de Porto Alegre",
               "layer": meta.get("name"), "feature_count_at_source": len(ids), "feature_count_saved": len(feicoes), "feature_count_rejected_without_geometry": rejeitadas, "feature_count_rejected_non_finite_geometry": nao_finitas,
               "spatial_reference_saved": f"EPSG:{SRS_SAIDA}", "fields_saved": campos, "processing_version": VERSAO_PROCESSAMENTO}
    entrada["registered"] = ingest.register(manifesto, entrada)
    return entrada


def baixar_camada_em_partes(nome: str, caminho: str, por_parte: int = 20000, destino: Path | None = None, manifesto: Path = MANIFESTO) -> list:
    """Camadas grandes (uso do solo: ~605 mil polígonos): grava em partes de ``por_parte`` registros, em JSON por linha comprimido, sem nunca guardar a camada inteira na memória.

    Cada parte é uma fatia contígua da lista de OBJECTID ordenada e tem o próprio hash no manifesto. Se a parte já existe, o hash confere com o manifesto e a fatia de
    identificadores da fonte é a mesma, ela é PULADA: nada é baixado de novo (retomada após interrupção e atualização idempotente). O gzip é gravado sem data, então o mesmo
    conteúdo dá o mesmo hash.
    """
    import gzip
    destino = destino or (RAIZ / "data" / "raw" / nome)
    url = BASE + caminho
    meta = _pedido("GET", url, f="json")
    campos = [c for c in campos_permitidos(meta) if "(" not in c]      # st_area(shape) e st_length(shape) são calculados pelo servidor, não são dados da Prefeitura
    oid = next(f["name"] for f in meta["fields"] if f["type"] == "esriFieldTypeOID")
    ids = sorted(_pedido("GET", url + "/query", where="1=1", returnIdsOnly="true", f="json")["objectIds"] or [])
    registrados = {}
    for s in ingest.load_manifest(manifesto)["sources"]:
        registrados[s["path"]] = s                                      # a última entrada de cada caminho vale
    destino.mkdir(parents=True, exist_ok=True)
    partes = []
    for k, ini in enumerate(range(0, len(ids), por_parte), start=1):
        fatia = ids[ini:ini + por_parte]
        arquivo = destino / f"parte_{k:04d}.jsonl.gz"
        rel = str(arquivo.relative_to(RAIZ))
        antigo = registrados.get(rel)
        if (antigo and arquivo.exists() and antigo.get("slice_first_id") == fatia[0] and antigo.get("slice_last_id") == fatia[-1] and antigo.get("slice_ids") == len(fatia)
                and antigo.get("fields_saved") == campos and ingest.sha256_file(arquivo) == antigo["sha256"]):
            partes.append({**antigo, "pulada": True})
            print(f"{nome} parte {k}: já válida ({len(fatia)} ids), pulada", flush=True)
            continue
        salvas, sem_geometria, nao_finitas = 0, 0, 0
        with open(arquivo, "wb") as bruto, gzip.GzipFile(filename="", mode="wb", fileobj=bruto, compresslevel=6, mtime=0) as gz:
            for i in range(0, len(fatia), LOTE):
                lote = fatia[i:i + LOTE]
                corpo = _pedido("POST", url + "/query", objectIds=",".join(map(str, lote)), outFields=",".join(campos), returnGeometry="true", outSR=SRS_SAIDA, f="json")
                for f in sorted(corpo.get("features", []), key=lambda f: f["attributes"][oid]):
                    if f.get("geometry") is None:
                        sem_geometria += 1
                        continue
                    if not _geometria_finita(f["geometry"]):
                        nao_finitas += 1
                        continue
                    gz.write((json.dumps({"a": f["attributes"], "g": f["geometry"]}, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
                    salvas += 1
                time.sleep(0.1)
        entrada = {"url": url + "/query", "path": rel, "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sha256": ingest.sha256_file(arquivo), "size_bytes": arquivo.stat().st_size,
                   "source_reference_date": None, "origin": "serviço ArcGIS REST da Prefeitura de Porto Alegre", "layer": meta.get("name"), "format": "jsonl.gz (uma feição por linha: a=atributos, g=geometria Esri)",
                   "part": k, "slice_first_id": fatia[0], "slice_last_id": fatia[-1], "slice_ids": len(fatia), "feature_count_at_source_total": len(ids), "feature_count_saved": salvas,
                   "feature_count_rejected_without_geometry": sem_geometria, "feature_count_rejected_non_finite_geometry": nao_finitas, "spatial_reference_saved": f"EPSG:{SRS_SAIDA}",
                   "fields_saved": campos, "processing_version": VERSAO_PROCESSAMENTO}
        entrada["registered"] = ingest.register(manifesto, entrada)
        partes.append(entrada)
        print(f"{nome} parte {k}: {salvas} de {len(fatia)} salvos ({sem_geometria} sem geometria, {nao_finitas} não finitos), {entrada['size_bytes'] / 1e6:.1f} MB", flush=True)
    return partes


if __name__ == "__main__":
    todas = {**CAMADAS, **CAMADAS_SOB_DEMANDA}
    nomes = sys.argv[1:] or list(CAMADAS)
    desconhecidas = [n for n in nomes if n not in todas]
    if desconhecidas:
        sys.exit(f"camadas desconhecidas: {desconhecidas}. Disponíveis: {list(todas)}")
    for n in nomes:
        if n in CAMADAS_SOB_DEMANDA:          # camadas grandes: em partes e com retomada
            baixar_camada_em_partes(n, todas[n])
            continue
        e = baixar_camada(n, todas[n])
        print(f"{n}: {e['feature_count_saved']} de {e['feature_count_at_source']} feições (rejeitadas: {e['feature_count_rejected_without_geometry']} sem geometria, {e['feature_count_rejected_non_finite_geometry']} com coordenada não finita), {e['size_bytes'] / 1e6:.1f} MB, sha256 {e['sha256'][:12]}, manifesto {'atualizado' if e['registered'] else 'sem mudança'}", flush=True)
