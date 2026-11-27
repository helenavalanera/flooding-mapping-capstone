"""Measured quality of the extraction, against a hand-annotated sample.

Gold file (JSON lines), one document per line::

    {"doc": {"fonte_id": "...", "texto": "...", "url": "...", "publicado_em": "AAAA-MM-DD"},
     "eventos": [{"via": "...", "bairro": "", "municipio": "...", "data": "AAAA-MM-DD", "tipo": "alagamento_via", "severidade": "...", "impacto_circulacao": "..."}]}

A candidate matches an annotated event when they name the same place and, if both give a date, the same date. Matching is one to one.
Precision = matched / extracted; recall = matched / annotated. Fields are scored only on matched pairs. A source enters training only when
its precision, on enough annotated events, reaches the threshold (``fontes_aprovadas``). Numbers are valid for the prompt version in the report.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from .esquema import VERSAO, normalizar
from .extrator import Documento, extrair
from .geocodificador import chave_da_via

LIMIAR_PRECISAO = 0.85   # provisional: to be agreed with the author before any label is used
MINIMO_EVENTOS_POR_FONTE = 20
CAMPOS_AVALIADOS = ("data", "tipo", "severidade", "impacto_circulacao")


def _lugar(ev: dict) -> str:
    return chave_da_via(ev.get("via") or "") or normalizar(ev.get("bairro") or "") or normalizar(ev.get("local_texto") or "") or normalizar(ev.get("municipio") or "")


def casam(a: dict, b: dict) -> bool:
    la, lb = _lugar(a), _lugar(b)
    if not la or not lb or not (la == lb or la in lb or lb in la):
        return False
    return not (a.get("data") and b.get("data") and a["data"] != b["data"])


def comparar(extraidos: list[dict], anotados: list[dict]) -> dict:
    """Greedy one-to-one match; returns the counts and the matched pairs."""
    livres, pares = list(range(len(anotados))), []
    for e in extraidos:
        for j in livres:
            if casam(e, anotados[j]):
                pares.append((e, anotados[j]))
                livres.remove(j)
                break
    return {"extraidos": len(extraidos), "anotados": len(anotados), "acertos": len(pares), "pares": pares}


def _razao(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def avaliar(documentos: list[dict], provedor, limiar: float = LIMIAR_PRECISAO) -> dict:
    por_fonte = defaultdict(lambda: {"extraidos": 0, "anotados": 0, "acertos": 0})
    campos = {c: [0, 0] for c in CAMPOS_AVALIADOS}
    rejeitados = defaultdict(int)
    falhas = 0
    for item in documentos:
        d = item["doc"]
        doc = Documento(d["fonte_id"], d["texto"], d.get("url", ""), date.fromisoformat(d["publicado_em"]) if d.get("publicado_em") else None)
        try:
            r = extrair(doc, provedor)
        except Exception:   # a model failure is a failure of the run, counted, never a silent zero
            falhas += 1
            continue
        for rej in r["rejeitados"]:
            rejeitados[rej["motivo"]] += 1
        c = comparar([x["evento"] for x in r["candidatos"]], item.get("eventos", []))
        s = por_fonte[doc.fonte_id]
        s["extraidos"] += c["extraidos"]; s["anotados"] += c["anotados"]; s["acertos"] += c["acertos"]
        for e, g in c["pares"]:
            for campo in CAMPOS_AVALIADOS:
                if g.get(campo):
                    campos[campo][1] += 1
                    campos[campo][0] += int(e.get(campo) == g[campo])
    total = {k: sum(s[k] for s in por_fonte.values()) for k in ("extraidos", "anotados", "acertos")}
    fontes = {f: {**s, "precisao": _razao(s["acertos"], s["extraidos"]), "cobertura": _razao(s["acertos"], s["anotados"]),
                  "aprovada": bool(s["anotados"] >= MINIMO_EVENTOS_POR_FONTE and s["extraidos"] and s["acertos"] / s["extraidos"] >= limiar)}
              for f, s in sorted(por_fonte.items())}
    return {"versao": VERSAO, "modelo": getattr(provedor, "modelo", "desconhecido"), "limiar_precisao": limiar,
            "minimo_eventos_por_fonte": MINIMO_EVENTOS_POR_FONTE, "documentos": len(documentos), "falhas_do_modelo": falhas,
            "precisao": _razao(total["acertos"], total["extraidos"]), "cobertura": _razao(total["acertos"], total["anotados"]), **total,
            "acerto_por_campo": {c: {"certos": v[0], "avaliados": v[1], "taxa": _razao(v[0], v[1])} for c, v in campos.items()},
            "rejeitados_pelo_validador": dict(rejeitados), "fontes": fontes}


def fontes_aprovadas(relatorio: dict) -> set[str]:
    return {f for f, v in relatorio["fontes"].items() if v["aprovada"]}


def carregar_anotacoes(caminho: str | Path) -> list[dict]:
    return [json.loads(linha) for linha in Path(caminho).read_text(encoding="utf-8").splitlines() if linha.strip()]


def em_markdown(r: dict) -> str:
    pct = lambda x: "—" if x is None else f"{x * 100:.1f}%"
    linhas = [f"# Precisão da extração de eventos ({r['versao']})", "",
              f"Modelo: `{r['modelo']}`. Documentos anotados: {r['documentos']}; falhas do modelo: {r['falhas_do_modelo']}.", "",
              f"**Precisão {pct(r['precisao'])}** ({r['acertos']} acertos de {r['extraidos']} extraídos) e **cobertura {pct(r['cobertura'])}** "
              f"({r['acertos']} de {r['anotados']} anotados). Limiar de precisão para uma fonte entrar no treino: {pct(r['limiar_precisao'])}, "
              f"com ao menos {r['minimo_eventos_por_fonte']} eventos anotados.", "", "| Campo (nos pares certos) | Certos | Avaliados | Taxa |", "|---|---|---|---|"]
    linhas += [f"| {c} | {v['certos']} | {v['avaliados']} | {pct(v['taxa'])} |" for c, v in r["acerto_por_campo"].items()]
    linhas += ["", "| Fonte | Extraídos | Anotados | Acertos | Precisão | Cobertura | Aprovada |", "|---|---|---|---|---|---|---|"]
    linhas += [f"| {f} | {v['extraidos']} | {v['anotados']} | {v['acertos']} | {pct(v['precisao'])} | {pct(v['cobertura'])} | {'sim' if v['aprovada'] else 'não'} |" for f, v in r["fontes"].items()]
    linhas += ["", f"Rejeitados pelo validador (antes da revisão): {r['rejeitados_pelo_validador'] or 'nenhum'}.", "",
               "Leitura: a precisão mede a extração de texto contra anotação manual, não a verdade sobre o alagamento. Notícias cobrem mais o centro e os grandes eventos (viés de notificação)."]
    return "\n".join(linhas) + "\n"
