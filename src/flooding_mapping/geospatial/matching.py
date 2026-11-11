"""Match CRBM blockage records to DAER stretches and ~1 km segments.

Rule: the road name and the km window pick the candidate segments; the record's own
latitude/longitude then picks the closest one and doubles as a check on the km. CRBM km
values are whole numbers, so the window is widened by ``KM_TOLERANCE``.

``status`` tells how far each match can be trusted:

* ``ok``: km and coordinates agree (closest candidate within ``DIST_OK_M``);
* ``ok_sem_coordenada``: matched by road and km alone (the record has no coordinates);
* ``distante_da_coordenada``: road and km found a segment, but the coordinates are far from
  it: either the km or the point is wrong, and the match is kept only as a suggestion;
* ``ambiguo``: two different official stretches of the same road are about equally close
  to the point (within ``AMBIGUITY_MARGIN_M`` of each other), so the coordinates cannot choose;
  a blockage near the boundary of two stretches is not ambiguous when the point is on one;
* ``km_fora_da_faixa``: the road exists but no stretch covers that km (``sugestao_*`` has
  the segment closest to the coordinates);
* ``apenas_coordenada``: the road is not in the DAER layer under that name but a segment lies
  within ``DIST_COORD_ONLY_M`` of the point (lower confidence);
* ``rodovia_ausente``: neither the name nor the coordinates match anything.

A blockage is ``pontual`` without ``km_fim`` (or with the same value) and ``intervalo``
otherwise; an interval maps to every segment that overlaps it.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import STRtree

from ..config import resolve

KM_TOLERANCE = 1.0
DIST_OK_M = 1000.0
DIST_COORD_ONLY_M = 300.0
AMBIGUITY_MARGIN_M = 100.0
MATCHED = ("ok", "ok_sem_coordenada", "distante_da_coordenada", "ambiguo", "apenas_coordenada")


def normalize_road(name) -> str:
    """``br 116`` -> ``BRS-116``; ``ers401`` -> ``ERS-401``; DAER names pass unchanged."""
    text = re.sub(r"[\s_]+", "-", str(name or "").strip().upper())
    text = re.sub(r"^BR-?(\d)", r"BRS-\1", text)
    return re.sub(r"^([A-Z]{2,3})-?(\d{3})$", r"\1-\2", text)


def _nearest(tree: STRtree, point):
    index, distance = tree.query_nearest(point, return_distance=True)
    return int(index[0]), float(distance[0])


def match_one(rec: dict, point, by_road: dict, segments: gpd.GeoDataFrame, tree: STRtree) -> dict:
    road = normalize_road(rec.get("rodovia"))
    km, km_fim = float(rec["km"]), rec.get("km_fim")
    notes = []
    if km_fim is not None and float(km_fim) < km:
        km, km_fim = float(km_fim), km
        notes.append("km invertido")
    interval = km_fim is not None and float(km_fim) > km
    lo, hi = km, float(km_fim) if interval else km
    out = {"id": rec["id"], "municipio": rec.get("municipio"), "rodovia": rec.get("rodovia"),
           "rodovia_normalizada": road, "km": km, "km_fim": km_fim,
           "tipo_bloqueio": "intervalo" if interval else "pontual", "status": None,
           "codigo_sre": None, "objectid": None, "segmento_principal": None, "segmentos": "",
           "n_segmentos": 0, "dist_coord_m": None, "concorda_coordenada": None,
           "n_trechos_candidatos": 0, "sugestao_segmento": None, "observacao": "; ".join(notes)}
    nearest = _nearest(tree, point) if point is not None else None

    pool = by_road.get(road)
    candidates = (pool[(pool["km_ini"] <= hi + KM_TOLERANCE) & (pool["km_fim"] >= lo - KM_TOLERANCE)]
                  if pool is not None else segments.iloc[0:0])
    if len(candidates):
        if point is not None:
            distance = candidates.geometry.distance(point)
            best = candidates.loc[distance.idxmin()]
            by_code = distance.groupby(candidates["codigo_sre"]).min().sort_values()
            out["dist_coord_m"] = round(float(distance.min()), 1)
            ambiguous = len(by_code) > 1 and by_code.iloc[1] - by_code.iloc[0] <= AMBIGUITY_MARGIN_M
            out["status"] = ("ambiguo" if ambiguous
                             else "ok" if distance.min() <= DIST_OK_M else "distante_da_coordenada")
            near = segments.iloc[nearest[0]]
            out["concorda_coordenada"] = bool(near["objectid"] in set(candidates["objectid"])
                                              or (near["nome"] == road and nearest[1] <= DIST_OK_M))
        else:
            middle = (lo + hi) / 2
            inside = candidates[(candidates["km_ini"] <= middle) & (candidates["km_fim"] >= middle)]
            best = (inside if len(inside) else candidates).iloc[0]
            out["status"] = "ok_sem_coordenada"
        chosen = candidates[(candidates["km_ini"] < hi) & (candidates["km_fim"] > lo)] if interval else None
        if chosen is None or chosen.empty:
            chosen = candidates.loc[[best.name]]
        out.update(codigo_sre=best["codigo_sre"], objectid=int(best["objectid"]),
                   segmento_principal=best["segmento_id"], segmentos=";".join(chosen["segmento_id"]),
                   n_segmentos=len(chosen), n_trechos_candidatos=int(candidates["codigo_sre"].nunique()))
    elif pool is not None:
        out["status"] = "km_fora_da_faixa"
    elif nearest is not None and nearest[1] <= DIST_COORD_ONLY_M:
        near = segments.iloc[nearest[0]]
        out.update(status="apenas_coordenada", codigo_sre=near["codigo_sre"], objectid=int(near["objectid"]),
                   segmento_principal=near["segmento_id"], segmentos=near["segmento_id"], n_segmentos=1,
                   dist_coord_m=round(nearest[1], 1))
    else:
        out["status"] = "rodovia_ausente"
    if out["status"] in ("km_fora_da_faixa", "rodovia_ausente") and nearest is not None:
        out["sugestao_segmento"] = f"{segments.iloc[nearest[0]]['segmento_id']} a {nearest[1]:.0f} m"
    return out


def match_records(records: list[dict], segments: gpd.GeoDataFrame) -> pd.DataFrame:
    """One audit row per record. ``segments`` must be in a metric CRS."""
    by_road = {name: group for name, group in segments.groupby("nome")}
    tree = STRtree(segments.geometry.values)
    rows = []
    for rec in records:
        point = None
        if rec.get("lat") is not None and rec.get("lng") is not None:
            point = gpd.GeoSeries(gpd.points_from_xy([rec["lng"]], [rec["lat"]]),
                                  crs="EPSG:4326").to_crs(segments.crs).iloc[0]
        rows.append(match_one(rec, point, by_road, segments, tree))
    return pd.DataFrame(rows)


def summarize(matches: pd.DataFrame) -> dict:
    """Coverage and quality figures for the audit report."""
    n = len(matches)
    matched = matches["status"].isin(MATCHED)
    dist = matches["dist_coord_m"].dropna()
    return {
        "registros": n,
        "por_status": matches["status"].value_counts().to_dict(),
        "por_tipo": matches["tipo_bloqueio"].value_counts().to_dict(),
        "associados": int(matched.sum()),
        "cobertura_associados": round(float(matched.mean()), 3) if n else None,
        "associados_confiaveis": int(matches["status"].isin(("ok", "ok_sem_coordenada")).sum()),
        "distancia_coordenada_m": ({"mediana": round(float(dist.median()), 1),
                                    "p90": round(float(dist.quantile(0.9)), 1),
                                    "max": round(float(dist.max()), 1)} if len(dist) else None),
        "rodovias_sem_correspondencia": sorted(
            matches.loc[matches["status"] == "rodovia_ausente", "rodovia_normalizada"].unique()),
        "problemas": matches.loc[~matches["status"].isin(("ok", "ok_sem_coordenada")),
                                 ["id", "rodovia", "km", "km_fim", "status", "sugestao_segmento"]
                                 ].astype(object).where(lambda d: d.notna(), None).to_dict("records"),
    }


def load_records(source: str) -> tuple[list[dict], str]:
    """Records from the live endpoint, a JSON file, or the R2 history (needs credentials)."""
    from ..collector import fetch, read_events, records_from_events
    from ..r2 import OpBudget, R2Store

    if source == "live":
        payload = fetch()
        raw = resolve("data/raw/crbm")
        raw.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (raw / f"ativos_{stamp}.json").write_text(json.dumps(payload, ensure_ascii=False))
        return payload["bloqueios"], f"live {stamp}"
    if source == "r2":
        store = R2Store.from_env(OpBudget(max_class_a=50, max_class_b=20000))
        return records_from_events(read_events(store)), "r2"
    path = Path(source.removeprefix("file:"))
    data = json.loads(path.read_text())
    return (data["bloqueios"] if isinstance(data, dict) else data), f"file {path.name}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Match CRBM blockages to DAER segments")
    parser.add_argument("--source", default="live", help="live | r2 | file:<path.json>")
    args = parser.parse_args()
    segments = gpd.read_parquet(resolve("data/interim/daer_segmentos.parquet"))
    records, origin = load_records(args.source)
    matches = match_records(records, segments)
    matches.to_parquet(resolve("data/interim/crbm_segmentos.parquet"))
    report = {"gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "fonte": origin,
              "parametros": {"km_tolerancia": KM_TOLERANCE, "dist_ok_m": DIST_OK_M,
                             "dist_so_coordenada_m": DIST_COORD_ONLY_M},
              **summarize(matches)}
    out = resolve("reports/qa/crbm_casamento.json")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n")
    print(f"{report['registros']} registros de {origin}: {report['por_status']}; "
          f"distância à coordenada {report['distancia_coordenada_m']}")


if __name__ == "__main__":
    main()
