"""Application service shared by the dashboard and the PWA: one source of data and rules.

The two interfaces never talk to each other. Both call this service (through the HTTP layer in
``servidor``), so a closure confirmed here is the next thing a route analysis sees.

Nature of what comes out, kept apart everywhere:
    observado   rain up to now; occurrences with their status
    previsto    rain after now and the risk estimated from it
    simulado    effect of closing a segment on the mapped network
    confirmado  a closure confirmed by an operator with written evidence

Personal data: origins, destinations and favourite places are used to compute and then forgotten
(an analysis lives in memory for ``TTL_ANALISE_S`` and can be deleted). Nothing about a person is
stored; the occurrence store has no user identifier.
"""

from __future__ import annotations

import secrets
import threading
import time

import numpy as np
import pandas as pd

from . import ocorrencias as oc
from . import rotas as rt
from .chuva_horaria import ChuvaHoraria
from .linguagem import ferramentas
from .linguagem.explicar import ROTULOS, Explicador, alerta, comparar, resumo_rota
from .risco_trecho import LOCAL, agora_local, classe, fator_em, natureza, pesos, tabela_de_chuva

TTL_ANALISE_S = 1800
MAX_ANALISES = 200
MAX_TEXTO_RELATO = 600
MAX_FEICOES = 8000
METODO = ("Escore = fator de chuva (0-1) x peso do trecho (0-1). O fator vem da chuva horária da cidade (total em 24 h e hora "
          "mais intensa, ancorados nos níveis observados em dias com bloqueios em Porto Alegre, mais a condição antecedente, com recuo de poucas horas depois que a chuva para). O peso é uma "
          "rampa sobre o percentil de um índice físico relativo (cota baixa, depressão local, proximidade da água, acumulação de fluxo, terreno plano): "
          "só os trechos mais suscetíveis têm peso, para sinalizar uma parcela pequena da malha mesmo com chuva forte. "
          "Uma ocorrência próxima e ativa eleva o peso a um piso.")
LIMITES = [
    "Baseline determinístico: não foi ajustado nem validado contra alagamentos em vias.",
    "Os cortes de classe e os pesos de condição antecedente e de ocorrência são provisórios.",
    "A chuva é uma série única para a cidade (grade de cerca de 10 km): diz quando chove, não onde.",
    "Trechos sem dado de terreno ficam sem estimativa; isso não significa risco baixo.",
    "O modelo municipal por dia (registros do S2iD) não é usado e não prevê alagamento em vias.",
    "Velocidades de fluxo livre, sem trânsito, semáforos ou restrições de conversão; sem ônibus.",
]


def iso_local(ts) -> str | None:
    """ISO 8601 with the Brasilia offset, from a naive local timestamp (or its string)."""
    if ts is None:
        return None
    return pd.Timestamp(ts).tz_localize(LOCAL).isoformat()


def ponto(dados, campo: str, limites: tuple[float, float, float, float]) -> tuple[float, float]:
    try:
        lon, lat = float(dados[campo]["lon"]), float(dados[campo]["lat"])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"{campo}: informe lon e lat") from None
    if not (limites[0] <= lon <= limites[1] and limites[2] <= lat <= limites[3]):
        raise ValueError(f"{campo}: fora da área coberta (Porto Alegre)")
    return lon, lat


class Servico:
    def __init__(self, rede: rt.Rede, chuva: ChuvaHoraria, store: oc.Ocorrencias, explicador: Explicador, params_risco: dict,
                 relogio=agora_local, token_operador: str = "", meta_dados: dict | None = None):
        self.rede, self.chuva, self.store, self.explicador, self.pr = rede, chuva, store, explicador, params_risco
        self.relogio, self.token_operador, self.meta_dados = relogio, token_operador, meta_dados or {}
        self._tabela: tuple[int, pd.DataFrame] | None = None
        self._analises: dict[str, tuple[float, rt.Analise, dict, dict]] = {}
        self._lock = threading.Lock()
        margem = 0.05
        self.limites = (float(rede.no_lon.min()) - margem, float(rede.no_lon.max()) + margem,
                        float(rede.no_lat.min()) - margem, float(rede.no_lat.max()) + margem)

    # ------------------------------------------------------------------ estado comum
    def _estado(self) -> dict:
        serie, meta = self.chuva.obter()
        with self._lock:
            if self._tabela is None or self._tabela[0] != id(serie):
                self._tabela = (id(serie), tabela_de_chuva(serie, self.pr))
            tabela = self._tabela[1]
        agora = self.relogio()
        em = agora.tz_localize(LOCAL).tz_convert("UTC").to_pydatetime()
        ativas = self.store.ativas(self.pr["validade_ocorrencia_h"], em)
        bloqueada = np.zeros(self.rede.n, bool)
        interdicoes = self.store.interdicoes(self.pr["validade_ocorrencia_h"], em)
        for r in interdicoes:
            idx = self.rede.indices(r["segmento_ids"]) or self.rede.proximos(r["lon"], r["lat"], self.pr["raio_interdicao_m"])
            bloqueada[idx] = True
        return {"serie": serie, "meta": meta, "tabela": tabela, "agora": agora, "ativas": ativas, "interdicoes": interdicoes,
                "bloqueada": bloqueada, "risco": pesos(self.rede.pct, self.rede, ativas, self.pr)}

    def _janela(self, serie: pd.Series, ini: pd.Timestamp, fim: pd.Timestamp, agora: pd.Timestamp, horas: int = 12) -> dict:
        """Rain around a trip: total in the window and the next hours, each marked observed or forecast."""
        dentro = serie[(serie.index > ini.floor("h")) & (serie.index <= fim.ceil("h"))]
        base = ini.floor("h")
        proximas = serie[(serie.index > base) & (serie.index <= base + pd.Timedelta(hours=horas))]
        return {"total_na_janela_mm": round(float(dentro.sum()), 1), "maximo_hora_mm": round(float(dentro.max()), 1) if len(dentro) else 0.0,
                "horas": [{"hora": iso_local(t), "mm": round(float(v), 1), "natureza": natureza(t, agora)} for t, v in proximas.items()]}

    # ------------------------------------------------------------------ visão geral, previsão e mapa
    def _classes_na_hora(self, e: dict, t: pd.Timestamp) -> dict:
        fator = fator_em(e["tabela"], t)
        if np.isnan(fator):
            return {"fator": None, "km_atencao": None, "km_alto": None, "n_atencao": None, "n_alto": None}
        escore = fator * e["risco"]["peso"]
        km = self.rede.comp_m / 1000
        alto, atencao = escore >= self.pr["classes"]["alto"], (escore >= self.pr["classes"]["atencao"]) & (escore < self.pr["classes"]["alto"])
        return {"fator": round(float(fator), 3), "km_atencao": round(float(km[atencao].sum()), 1), "km_alto": round(float(km[alto].sum()), 1),
                "n_atencao": int(atencao.sum()), "n_alto": int(alto.sum())}

    def previsao(self, horas: int = 48) -> dict:
        """Hour by hour: rain, factor and kilometres of street at each estimated class."""
        e = self._estado()
        horas = max(1, min(int(horas), 72))
        inicio = e["agora"].floor("h")
        linhas = []
        for t in pd.date_range(inicio, periods=horas + 1, freq="h"):
            if t not in e["tabela"].index:
                continue
            ln = e["tabela"].loc[t]
            linhas.append({"hora": iso_local(t), "natureza": natureza(t, e["agora"]), "chuva_hora_mm": round(float(ln["chuva_hora_mm"]), 1),
                           "total_24h_mm": None if np.isnan(ln["total_24h_mm"]) else round(float(ln["total_24h_mm"]), 1),
                           **self._classes_na_hora(e, t)})
        validos = [x for x in linhas if x["km_alto"] is not None]
        pico = max(validos, key=lambda x: (x["km_alto"], x["km_atencao"]), default=None)
        return {"natureza": "estimativa (baseline determinístico, sem validação em vias)", "horas": linhas, "hora_de_maior_exposicao": pico,
                "fonte_chuva": e["meta"], "metodo": METODO, "limites": LIMITES}

    def visao_geral(self) -> dict:
        e = self._estado()
        prev = self.previsao(48)
        proximas = e["serie"][(e["serie"].index > e["agora"].floor("h")) & (e["serie"].index <= e["agora"].floor("h") + pd.Timedelta(hours=24))]
        pico_chuva = proximas.idxmax() if len(proximas) else None
        pico = prev["hora_de_maior_exposicao"]
        indicativos = []
        if pico and pico["km_alto"]:
            indicativos.append({"nivel": "alto", "hora": pico["hora"], "km": pico["km_alto"], "criterio": f"escore >= {self.pr['classes']['alto']}"})
        elif pico and pico["km_atencao"]:
            indicativos.append({"nivel": "atencao", "hora": pico["hora"], "km": pico["km_atencao"], "criterio": f"escore >= {self.pr['classes']['atencao']}"})
        contagem = {s: sum(1 for r in self.store.listar() if r["situacao"] == s) for s in oc.SITUACOES}
        return {"agora": iso_local(e["agora"]), "chuva_proximas_24h_mm": round(float(proximas.sum()), 1),
                "pico_de_chuva": None if pico_chuva is None else {"hora": iso_local(pico_chuva), "mm": round(float(proximas.max()), 1)},
                "maior_exposicao": pico, "indicativos": indicativos,
                "aviso": "Indicativos de atenção calculados por critério explícito; não são alertas operacionais nem interdições.",
                "ocorrencias_por_situacao": contagem, "interdicoes_confirmadas_ativas": len(e["interdicoes"]),
                "fonte_chuva": e["meta"]}

    def risco_mapa(self, deslocamento_h: float = 0) -> dict:
        """Streets at ``atencao`` or ``alto`` at ``agora + deslocamento_h``, strongest first (capped)."""
        e = self._estado()
        t = e["agora"].floor("h") + pd.Timedelta(hours=max(0, min(float(deslocamento_h), 48)))
        fator = fator_em(e["tabela"], t)
        base = {"hora": iso_local(t), "natureza": natureza(t, e["agora"]), "fator": None if np.isnan(fator) else round(float(fator), 3),
                "metodo": METODO}
        if np.isnan(fator):
            return {**base, "sem_estimativa": True, "geojson": {"type": "FeatureCollection", "features": []}}
        escore = fator * e["risco"]["peso"]
        cls = classe(escore, self.pr)
        marcados = np.flatnonzero(np.isin(cls, ["atencao", "alto"]))
        fortes = marcados[np.argsort(-escore[marcados])][:MAX_FEICOES]
        r, a = self.rede, self.rede.arestas
        feicoes = [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[round(float(a["lon0"].iat[i]), 5), round(float(a["lat0"].iat[i]), 5)],
                                                                                          [round(float(a["lon1"].iat[i]), 5), round(float(a["lat1"].iat[i]), 5)]]},
                    "properties": {"id": str(r.ids[i]), "nome": a["nome"].iat[i] or None, "classe": cls[i], "escore": round(float(escore[i]), 3),
                                   "km": round(float(r.comp_m[i]) / 1000, 3),
                                   "ocorrencia": e["risco"]["ocorrencia"][i], "interditado": bool(e["bloqueada"][i])}} for i in fortes]
        return {**base, "sem_estimativa": False, "total_atencao_ou_alto": int(len(marcados)), "exibidos": len(feicoes),
                "geojson": {"type": "FeatureCollection", "features": feicoes}}

    def trecho(self, segmento_id: str) -> dict:
        """One segment: terrain facts, risk by hour, nearby occurrences and the simulated closure impact."""
        e = self._estado()
        idx = self.rede.indices([segmento_id])
        if not idx:
            raise KeyError(segmento_id)
        i = idx[0]
        a = self.rede.arestas.iloc[i]
        peso = e["risco"]["peso"][i]
        horas = []
        for t in pd.date_range(e["agora"].floor("h"), periods=25, freq="h"):
            f = fator_em(e["tabela"], t)
            horas.append({"hora": iso_local(t), "natureza": natureza(t, e["agora"]), "fator": None if np.isnan(f) else round(float(f), 3),
                          "escore": None if np.isnan(f) or np.isnan(peso) else round(float(f * peso), 3),
                          "classe": None if np.isnan(f) or np.isnan(peso) else classe(f * peso, self.pr)})
        validas = [h for h in horas if h["escore"] is not None]
        proximas = [{k: r[k] for k in ("tipo", "situacao", "confiabilidade", "fonte", "impacto_circulacao", "data_hora")}
                    for r in e["ativas"] if i in set(self.rede.proximos(r["lon"], r["lat"], self.pr["raio_ocorrencia_m"]))]
        fisicas = {k: (None if pd.isna(a.get(k)) else round(float(a[k]), 2)) for k in
                   ("elev", "rel_elev_250", "slope", "height_above_water", "log_flow_acc", "percentil")}
        return {"id": segmento_id, "nome": a["nome"] or None, "classe_via": a["highway"], "comprimento_m": round(float(a["comprimento_m"]), 1),
                "interditado": bool(e["bloqueada"][i]), "caracteristicas_fisicas": fisicas, "peso": None if np.isnan(peso) else round(float(peso), 3),
                "confiabilidade_do_dado": None if np.isnan(e["risco"]["confiabilidade"][i]) else float(e["risco"]["confiabilidade"][i]),
                "risco_por_hora": horas, "hora_de_maior_exposicao": max(validas, key=lambda h: h["escore"]) if validas else None,
                "ocorrencias_proximas": proximas,
                "impacto_simulado_do_fechamento": {m: rt.impacto_fechamento(self.rede, m, i) for m in rt.MODOS},
                "metodo": METODO, "limites": LIMITES}

    # ------------------------------------------------------------------ rotas e explicação
    def rotas(self, dados: dict) -> dict:
        if not isinstance(dados, dict):
            raise ValueError("corpo inválido")
        origem, destino = ponto(dados, "origem", self.limites), ponto(dados, "destino", self.limites)
        modal = dados.get("modal", "carro")
        e = self._estado()
        try:
            saida = pd.Timestamp(dados["saida"]) if dados.get("saida") else e["agora"].ceil("5min")
        except (ValueError, TypeError):
            raise ValueError("saida: data/hora inválida") from None
        if saida.tzinfo is not None:
            saida = saida.tz_convert(LOCAL).tz_localize(None)
        if not (e["agora"] - pd.Timedelta(hours=1) <= saida <= e["agora"] + pd.Timedelta(hours=48)):
            raise ValueError("saida: informe um horário entre agora e as próximas 48 horas")
        analise = rt.Analise(self.rede, modal, origem, destino, saida, e["tabela"], e["risco"], e["bloqueada"], e["agora"])
        brutas = analise.comparar()
        comparacao = comparar(brutas)
        meteo = self._janela(e["serie"], saida, pd.Timestamp(brutas["habitual"]["chegada"]), e["agora"])
        identificador = secrets.token_urlsafe(12)
        with self._lock:
            agora_m = time.monotonic()
            self._analises = {k: v for k, v in self._analises.items() if v[0] > agora_m}
            while len(self._analises) >= MAX_ANALISES:
                self._analises.pop(next(iter(self._analises)))
            self._analises[identificador] = (agora_m + TTL_ANALISE_S, analise, brutas, {"meteo": meteo, "comparacao": comparacao})
        return {"analise_id": identificador, "natureza": "estimativa de risco por trecho (baseline sem validação em vias)", "modal": modal,
                "saida": iso_local(saida), "meteo": meteo, "alerta": alerta(brutas, meteo), "comparacao": comparacao,
                "rotas": {n: self._publica(r, n) for n, r in brutas.items()}, "interdicoes_consideradas": int(e["bloqueada"].sum()),
                "fonte_chuva": e["meta"], "avisos": [
                    "Valores são estimativas, não garantias: nenhuma rota é apresentada como segura.",
                    "A escolha da rota é sua; o trajeto não é alterado automaticamente.",
                    "Trechos sem dado de terreno aparecem como 'sem estimativa'; isso não significa risco baixo."]}

    def _publica(self, rota: dict, nome: str) -> dict:
        trechos = [{**{k: t[k] for k in ("nome", "classe", "km", "escore", "peso", "fator", "segmentos")}, "inicio": iso_local(t["inicio"]),
                    "fim": iso_local(t["fim"]), "ocorrencia": t["ocorrencia"]} for t in rota["trechos_de_risco"]]
        return {"rotulo": ROTULOS[nome], "coordenadas": rota["coordenadas"], "tempo_min": round(rota["tempo_s"] / 60, 1),
                "distancia_km": round(rota["distancia_km"], 2), "exposicao_km_risco": round(rota["exposicao_km_risco"], 3),
                "km_atencao_ou_alto": round(rota["km_atencao_ou_alto"], 2), "km_alto": round(rota["km_alto"], 2),
                "km_sem_estimativa": round(rota["km_sem_estimativa"], 2), "escore_maximo": rota["escore_maximo"],
                "instante_do_pico": iso_local(rota["instante_do_pico"]), "chegada": iso_local(rota["chegada"]), "trechos_de_risco": trechos}

    def _analise(self, identificador: str):
        with self._lock:
            achado = self._analises.get(identificador)
        if not achado or achado[0] < time.monotonic():
            raise KeyError(identificador)
        return achado

    def apagar_analise(self, identificador: str) -> bool:
        with self._lock:
            return self._analises.pop(identificador, None) is not None

    def explicacao(self, identificador: str, contextualizar: bool = False) -> dict:
        """Deterministic alert always; the language provider only when asked and when there is risk to explain."""
        _, analise, brutas, extra = self._analise(identificador)
        det = alerta(brutas, extra["meteo"])
        if not contextualizar or det["nivel"] == "sem_risco_estimado":
            return {"texto": det["texto"], "origem": "deterministico", "motivo": "nao_solicitado" if not contextualizar else "sem_risco_estimado",
                    "alerta": det}
        e = self._estado()
        resumos = {"saida": iso_local(analise.saida), "modal": analise.modo, "chuva_na_janela_mm": extra["meteo"]["total_na_janela_mm"],
                   "rotas": {n: resumo_rota(r, n, extra["comparacao"]) for n, r in brutas.items()}}
        man = self._manipuladores(analise, brutas, extra, e)
        saida = self.explicador.explicar(resumos, det, lambda nome, args: ferramentas.executar(nome, args, man), ferramentas.DECLARACOES)
        return {**saida, "alerta": det}

    def _manipuladores(self, analise: rt.Analise, brutas: dict, extra: dict, e: dict) -> dict:
        """Operations the provider may call, bound to this analysis (the provider cannot name another)."""
        def escolher(nome):
            if nome not in brutas:
                raise ferramentas.FerramentaInvalida(f"a análise não tem a rota {nome}")
            return brutas[nome]

        def clima(horas=12):
            proximas = e["serie"][(e["serie"].index > e["agora"].floor("h")) & (e["serie"].index <= e["agora"].floor("h") + pd.Timedelta(hours=horas))]
            return {"fonte": "modelo de previsão Open-Meteo, uma série para a cidade", "obsoleta": bool(e["meta"].get("obsoleta")),
                    "total_mm": round(float(proximas.sum()), 1), "pico": None if proximas.empty else {"hora": iso_local(proximas.idxmax())[11:16],
                                                                                                        "mm": round(float(proximas.max()), 1)},
                    "horas": [{"hora": iso_local(t)[11:16], "mm": round(float(v), 1), "natureza": natureza(t, e["agora"])} for t, v in proximas.head(24).items()]}

        def risco_da_rota(rota):
            return resumo_rota(escolher(rota), rota, extra["comparacao"])

        def alternativas(aversao=None):
            if aversao is None:
                return {"comparacao": extra["comparacao"]}
            novo = analise.caminho(float(aversao))
            return {"recalculada_com_aversao": aversao, "tempo_min": round(novo["tempo_s"] / 60), "exposicao_km_risco": round(novo["exposicao_km_risco"], 2),
                    "km_atencao_ou_alto": round(novo["km_atencao_ou_alto"], 2),
                    "acrescimo_min_vs_habitual": round((novo["tempo_s"] - brutas["habitual"]["tempo_s"]) / 60)} if novo else {"erro": "sem rota"}

        def incidentes(rota):
            do_caminho = set(escolher(rota)["arestas"])
            em = e["agora"]
            itens = []
            for r in e["ativas"]:
                if do_caminho & set(self.rede.proximos(r["lon"], r["lat"], self.pr["raio_ocorrencia_m"])):
                    idade = (em.tz_localize(LOCAL).tz_convert("UTC") - pd.Timestamp(r["data_hora"])).total_seconds() / 3600
                    itens.append({"tipo": r["tipo"], "situacao": r["situacao"], "confiabilidade": r["confiabilidade"],
                                  "impacto_circulacao": r["impacto_circulacao"], "idade_h": round(max(idade, 0), 1), "fonte": r["fonte"]})
            return {"quantidade": len(itens), "ocorrencias": itens[:10]}

        def explicacao_do_risco(rota):
            trechos = sorted(escolher(rota)["trechos_de_risco"], key=lambda t: -t["escore"])[:3]
            return {"fatores_dos_trechos_mais_expostos": [{"nome": t["nome"] or "via sem nome", "fator_de_chuva": round(t["fator"], 2),
                                                           "peso_do_trecho": round(t["peso"], 2), "ocorrencia_proxima": bool(t["ocorrencia"])} for t in trechos],
                    "metodo": METODO, "limites": LIMITES[:4]}
        return {"get_weather_forecast": clima, "analyze_route_risk": risco_da_rota, "calculate_alternative_routes": alternativas,
                "get_nearby_incidents": incidentes, "get_risk_explanation": explicacao_do_risco}

    # ------------------------------------------------------------------ ocorrências
    def relato(self, dados: dict) -> dict:
        """A user report becomes a ``reportada`` record; the location comes from the app, never from the text."""
        if not isinstance(dados, dict):
            raise ValueError("corpo inválido")
        texto = str(dados.get("texto") or "")
        if len(texto) > MAX_TEXTO_RELATO:
            raise ValueError(f"texto: no máximo {MAX_TEXTO_RELATO} caracteres")
        campos = self.explicador.interpretar_relato(texto) if texto.strip() else {
            "tipo": dados.get("tipo", "outro"), "severidade": "desconhecida", "impacto_circulacao": "desconhecido", "descricao": "", "interpretado": False}
        registro = self.store.relato({"lon": dados.get("lon"), "lat": dados.get("lat"), **{k: campos[k] for k in
                                      ("tipo", "severidade", "impacto_circulacao", "descricao")}},
                                     origem="relato do usuário; campos estruturados por provedor de linguagem" if campos["interpretado"] else "relato do usuário")
        return {"id": registro["id"], "situacao": registro["situacao"], "confiabilidade": registro["confiabilidade"],
                "mensagem": "Relato recebido como reportado. Ele não interdita vias: só uma confirmação com evidência o faz."}

    def listar_ocorrencias(self, situacao: str | None = None, completo: bool = False) -> dict:
        """The public list leaves out the free text: an unverified report may carry personal data typed by a stranger.
        Only an authenticated operator (``completo``) sees it."""
        if situacao and situacao not in oc.SITUACOES:
            raise ValueError(f"situacao: use um de {', '.join(oc.SITUACOES)}")
        itens = self.store.listar(situacao)[:500]
        if not completo:
            itens = [{k: v for k, v in r.items() if k != "descricao"} for r in itens]
        return {"total": len(self.store.listar(situacao)), "ocorrencias": itens, "texto_livre_incluido": completo,
                "natureza": "reportada = relato sem verificação; confirmada = validada por operador com evidência; descartada = refutada"}

    def autorizado(self, token: str) -> bool:
        import hmac
        return bool(self.token_operador) and hmac.compare_digest(token or "", self.token_operador)

    def mudar_situacao(self, id_: str, dados: dict) -> dict:
        return self.store.mudar_situacao(id_, dados.get("situacao"), por=str(dados.get("por") or "operador")[:40],
                                         evidencia=dados.get("evidencia", ""), confiabilidade=dados.get("confiabilidade"))

    # ------------------------------------------------------------------ proveniência e saúde
    def proveniencia(self) -> dict:
        e = self._estado()
        r = self.rede
        return {"fontes": [
            {"nome": "Open-Meteo", "uso": "chuva horária observada recente e prevista", **e["meta"]},
            {"nome": "OpenStreetMap (Geofabrik)", "uso": "rede viária e nomes de vias", "licenca": "ODbL"},
            {"nome": "Copernicus DEM GLO-30", "uso": "elevação, declividade, depressão local e acumulação de fluxo"},
            {"nome": "Ocorrências", "uso": "relatos de usuários (reportada) e confirmações de operadores", "criterio": oc.SITUACOES},
        ], "cobertura": {"segmentos": r.n, "com_indice_fisico": int(np.isfinite(r.pct).sum()),
                         "fracao_com_indice_fisico": round(float(np.isfinite(r.pct).mean()), 3)},
            "parametros_provisorios": ["fator_no_medio", "antecedente_fator", "classes", "piso_ocorrencia", "confiabilidade", "penalidade_s_por_km_risco"],
            "metodo": METODO, "limites": LIMITES, "dados_da_rede": self.meta_dados,
            "natureza": {"observado": "chuva até agora; ocorrências com status", "previsto": "chuva futura e o risco estimado a partir dela",
                         "simulado": "efeito do fechamento de um trecho na rede mapeada", "confirmado": "interdição confirmada por operador com evidência"}}

    def saude(self) -> dict:
        try:
            _, meta = self.chuva.obter()
            chuva = {"ok": True, "obsoleta": bool(meta.get("obsoleta"))}
        except Exception:
            chuva = {"ok": False, "obsoleta": None}
        return {"status": "ok" if chuva["ok"] else "degradado", "chuva": chuva, "segmentos": self.rede.n,
                "provedor_de_linguagem": self.explicador.provedor is not None,
                "confirmacao_de_ocorrencias": bool(self.token_operador)}
