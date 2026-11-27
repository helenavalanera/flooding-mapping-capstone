"""Review queue and the training-label export.

Append-only JSON lines (the latest line per id wins), the same convention as the occurrence store. A candidate becomes a label only after a
named person accepts or corrects it. Accepted events go to a *separate* label file, never to the live occurrence store: they are history for
training and for validation, and must not raise the risk of a street today.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from .. import ocorrencias as oc
from .esquema import validar_evento

SITUACOES = ("pendente", "aceito", "corrigido", "rejeitado")
# How much a label weighs in training: an official bulletin is not a newspaper line, and a corrected event was verified by a person.
PESO_POR_TIPO_DE_FONTE = {"boletim": 1.0, "noticia": 0.5, "relato": 0.3}


class Fila:
    def __init__(self, caminho: str | Path):
        self.caminho, self._lock, self._itens = Path(caminho), threading.Lock(), {}
        if self.caminho.exists():
            for linha in self.caminho.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    item = json.loads(linha)
                    self._itens[item["id"]] = item
                except (ValueError, KeyError, TypeError):
                    continue

    def _gravar(self, item: dict) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.caminho.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def documentos_vistos(self) -> set[str]:
        return {i["doc_id"] for i in self._itens.values()}

    def adicionar(self, candidatos: list[dict]) -> int:
        novos = 0
        with self._lock:
            for c in candidatos:
                if c["id"] in self._itens:
                    continue
                self._itens[c["id"]] = c
                self._gravar(c)
                novos += 1
        return novos

    def listar(self, situacao: str | None = None) -> list[dict]:
        return [i for i in self._itens.values() if situacao is None or i["status"] == situacao]

    def revisar(self, id_: str, acao: str, por: str, corrigido: dict | None = None, nota: str = "", texto_original: str | None = None) -> dict:
        """``acao``: aceitar | corrigir | rejeitar. A correction is validated again (against the original text, when given)."""
        if acao not in ("aceitar", "corrigir", "rejeitar"):
            raise ValueError("ação inválida")
        if not (por or "").strip():
            raise ValueError("a revisão exige o nome de quem revisou")
        with self._lock:
            item = self._itens.get(id_)
            if item is None:
                raise KeyError(id_)
            if item["status"] != "pendente":
                raise ValueError(f"já revisado: {item['status']}")
            novo = {**item, "revisado_por": por.strip()[:80], "revisado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "nota": nota[:280]}
            if acao == "corrigir":
                if not corrigido:
                    raise ValueError("a correção exige o evento corrigido")
                ev, motivo = validar_evento({**item["evento"], **corrigido}, texto_original if texto_original is not None else item["evento"]["trecho_fonte"])
                if ev is None:
                    raise ValueError(f"correção inválida: {motivo}")
                novo.update(status="corrigido", evento_original=item["evento"], evento=ev)
            else:
                novo["status"] = "aceito" if acao == "aceitar" else "rejeitado"
            self._itens[id_] = novo
            self._gravar(novo)
            return novo

    def exportar_rotulos(self, geocodificador=None, tipos_de_fonte: dict[str, str] | None = None) -> list[dict]:
        """Reviewed events as labels: only ``aceito`` and ``corrigido``, with a weight, the quote and the geocoding precision."""
        tipos_de_fonte = tipos_de_fonte or {}
        saida = []
        for i in self._itens.values():
            if i["status"] not in ("aceito", "corrigido"):
                continue
            tipo_fonte = tipos_de_fonte.get(i["fonte_id"], "noticia")
            peso = PESO_POR_TIPO_DE_FONTE.get(tipo_fonte, 0.3) * (1.0 if i["status"] == "corrigido" else 0.9)
            saida.append({"id": i["id"], "fonte_id": i["fonte_id"], "url": i["url"], "evento": i["evento"], "revisao": i["status"],
                          "revisado_por": i.get("revisado_por", ""), "peso": round(peso, 3),
                          "geo": geocodificador.localizar(i["evento"]) if geocodificador else None,
                          "tipo_valido": i["evento"]["tipo"] in oc.TIPOS})
        return saida
