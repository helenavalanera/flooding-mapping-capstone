"""Prepara o território de Porto Alegre a partir dos mapas públicos da Prefeitura: bairros, arroios, casas de bombas e aglomerados.

    python tools/preparar_territorio_poa.py <drenagem.kml> [saida.json]

Baixe o KML em https://www.google.com/maps/d/kml?mid=1hKUlnRnx2aRiH3NBYnlLt4qXBUo&forcekml=1 (mapa "Drenagem Pluvial", PMPA).
Só entram geometrias e atributos de equipamento ou de território. As ocorrências da Defesa Civil (com nome e telefone) não são lidas.
Aglomerados subnormais (IBGE 2010) entram só como número de domicílios e de pessoas por bairro, nunca como polígono.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from shapely.geometry import LineString, Polygon, mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree

NS = {"k": "http://www.opengis.net/kml/2.2"}
RAIZ = Path(__file__).resolve().parents[1]


def _coords(txt):
    return [tuple(map(float, c.split(",")[:2])) for c in txt.split()]


def _dados(p):
    e = p.find("k:ExtendedData", NS)
    return {d.get("name"): (d.find("k:value", NS).text or "").strip() for d in e} if e is not None else {}


def _num(t, padrao=None):
    try:
        return float(re.sub(r"[^\d,.\-]", "", t).replace(",", "."))
    except ValueError:
        return padrao


def _titulo(nome):
    peq = {"de", "da", "do", "das", "dos", "e"}
    return " ".join(w.lower() if i and w.lower() in peq else w.capitalize() for i, w in enumerate(nome.split()))


def pasta(doc, prefixo):
    return next(f for f in doc.iter(f"{{{NS['k']}}}Folder") if (f.find("k:name", NS).text or "").startswith(prefixo))


def preparar(kml: str) -> dict:
    doc = ET.parse(kml).getroot().find("k:Document", NS)
    bairros, achados = [], {}
    for p in pasta(doc, "Bairros").findall("k:Placemark", NS):
        nome = _dados(p).get("NOME") or (p.find("k:name", NS).text or "").strip()
        poli = [Polygon(_coords(c.text)) for c in p.iterfind(".//k:Polygon/k:outerBoundaryIs//k:coordinates", NS)]
        if nome and poli:
            achados.setdefault(_titulo(nome), []).extend(poli)
    for nome, poli in achados.items():   # o mapa repete bairros em mais de um polígono: une por nome
        bairros.append({"nome": nome, "geom": unary_union([q.buffer(0) for q in poli]).simplify(0.0002), "pop_aglomerados": 0, "domicilios_aglomerados": 0, "aglomerados": 0})
    arvore = STRtree([b["geom"] for b in bairros])
    for p in pasta(doc, "Aglomerados").findall("k:Placemark", NS):
        d, c = _dados(p), p.find(".//k:Polygon/k:outerBoundaryIs//k:coordinates", NS)
        if c is None:
            continue
        ponto = Polygon(_coords(c.text)).representative_point()
        for i in arvore.query(ponto, predicate="within"):
            b = bairros[i]
            b["aglomerados"] += 1
            b["pop_aglomerados"] += int(_num(d.get("População em DPO", "0"), 0))
            b["domicilios_aglomerados"] += int(_num(d.get("Domicílios Ocupados", "0"), 0))
    arroios = []
    for p in pasta(doc, "Arroios").findall("k:Placemark", NS):
        d = _dados(p)
        for c in p.iterfind(".//k:LineString/k:coordinates", NS):
            arroios.append({"ordem": int(_num(d.get("ORDEM", "1"), 1)), "nome": (d.get("NOME") or "").strip() or None,
                            "geom": LineString(_coords(c.text)).simplify(0.00005)})
    bombas = []
    for p in pasta(doc, "DEP Casa").findall("k:Placemark", NS):
        c = p.find(".//k:Point/k:coordinates", NS)
        if c is None:
            continue
        d, (lon, lat) = _dados(p), _coords(c.text)[0]
        bombas.append({"nome": (p.find("k:name", NS).text or "").strip(), "local": d.get("Local") or d.get("Endereço"), "area_protegida": d.get("Área Protegida"),
                       "capacidade_m3s": _num(d.get("Capacidade (m3 /s)", ""), None), "area_km2": _num(d.get("Área Contribuinte (km2)", ""), None),
                       "lon": round(lon, 6), "lat": round(lat, 6)})
    return {"fonte": "Prefeitura Municipal de Porto Alegre (mapa Drenagem Pluvial) e IBGE 2010 (aglomerados subnormais, via ObservaPOA)",
            "bairros": [{**b, "geom": mapping(b["geom"])} for b in bairros], "arroios": [{**a, "geom": mapping(a["geom"])} for a in arroios], "bombas": bombas}


if __name__ == "__main__":
    t = preparar(sys.argv[1])
    saida = Path(sys.argv[2] if len(sys.argv) > 2 else RAIZ / "data/processed/territorio_poa.json")
    saida.write_text(json.dumps(t, ensure_ascii=False, separators=(",", ":")))
    print(f"{len(t['bairros'])} bairros, {len(t['arroios'])} trechos de arroio, {len(t['bombas'])} casas de bombas -> {saida} ({saida.stat().st_size // 1024} KB)")
    print("aglomerados atribuídos:", sum(b["aglomerados"] for b in t["bairros"]), "de 111")
