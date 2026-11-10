"""Contextual assistant: the questions a person can ask about what is selected, and the answers the backend can give alone.

Every context (a street segment, an analysed route, a municipality or a highway) becomes a structured summary with no
coordinates, together with the information that is MISSING (``lacunas``). Each suggested question has a deterministic answer
built from that summary, so the assistant works without the language provider; the provider only rephrases and contextualises
what the summary already says, and what it writes is validated like any other text.
"""

from __future__ import annotations

PERGUNTAS = {
    "por_que_atencao": "Por que este trecho está em atenção?",
    "o_que_explica": "O que explica esta classificação?",
    "o_que_muda": "O que muda entre estas rotas?",
    "indisponivel": "Quais informações estão indisponíveis?",
}
POR_CONTEXTO = {
    "trecho": ["por_que_atencao", "o_que_explica", "indisponivel"],
    "rota": ["o_que_muda", "por_que_atencao", "o_que_explica", "indisponivel"],
    "municipio": ["o_que_explica", "indisponivel"],
    "rodovia": ["o_que_explica", "indisponivel"],
}
MAX_PERGUNTA = 200
ESCOPO_CHUVA = "Chuva: estimativa regional (uma série para a cidade inteira, grade de cerca de 10 km), não medição neste trecho."
FORMULA = ("O escore é o fator de chuva (0 a 1) vezes o peso do trecho (0 a 1). O fator vem da chuva horária da cidade (total em 24 h e hora mais "
           "intensa, com recuo em horas secas). O peso é uma rampa sobre o percentil do índice físico do terreno: só os trechos mais suscetíveis "
           "têm peso. Atenção a partir de 0,25 e Alto a partir de 0,60. É um baseline sem validação contra alagamentos em vias.")
LIMITE_GERAL = "Os resultados são estimativas de um baseline experimental, sem validação em vias."


def sugeridas(tipo: str) -> list[dict]:
    return [{"id": i, "rotulo": PERGUNTAS[i]} for i in POR_CONTEXTO[tipo]]


def _classe(c) -> str:
    return {"alto": "Alto", "atencao": "Atenção"}.get(c, "sem classe")


def _hora(iso) -> str:
    return iso[11:16] if iso else "—"


# ---------------------------------------------------------------- trecho
def contexto_trecho(t: dict) -> dict:
    f, pk = t["caracteristicas_fisicas"], t["hora_de_maior_exposicao"]
    lacunas = []
    if f.get("percentil") is None:
        lacunas.append("Índice físico do terreno indisponível para este trecho: ele fica sem estimativa de risco (isso não significa risco baixo).")
    if pk is None:
        lacunas.append("Sem estimativa de risco nas próximas 24 h.")
    if not t["ocorrencias_proximas"]:
        lacunas.append("Nenhuma ocorrência ativa a 100 m: não há observação local que confirme ou afaste o risco.")
    lacunas.append(ESCOPO_CHUVA)
    return {"tipo": "trecho", "nome": t["nome"] or "via sem nome", "classe_da_via": t["classe_via"], "comprimento_m": t["comprimento_m"],
            "interditado_por_confirmacao": t["interditado"], "peso_do_trecho": t["peso"], "percentil_do_indice_fisico": f.get("percentil"),
            "terreno": {"cota_m": f.get("elev"), "relevo_local_m": f.get("rel_elev_250"), "declividade_graus": f.get("slope"), "altura_sobre_a_agua_m": f.get("height_above_water")},
            "maior_exposicao": None if pk is None else {"hora": pk["hora"], "escore": pk["escore"], "classe": pk["classe"]},
            "ocorrencias_proximas": [{k: o[k] for k in ("tipo", "situacao", "confiabilidade", "fonte")} for o in t["ocorrencias_proximas"]],
            "se_o_trecho_fechasse": t["impacto_simulado_do_fechamento"], "lacunas": lacunas, "metodo": FORMULA}


def _terreno(c: dict) -> str:
    t, partes = c["terreno"], []
    if t.get("relevo_local_m") is not None and t["relevo_local_m"] < 0:
        partes.append("fica numa depressão local")
    if t.get("altura_sobre_a_agua_m") is not None and t["altura_sobre_a_agua_m"] < 2:
        partes.append("está muito próximo da altura da água mais próxima")
    if t.get("declividade_graus") is not None and t["declividade_graus"] < 1:
        partes.append("é praticamente plano")
    return ", ".join(partes) if partes else "tem um perfil de terreno que o índice físico pontua como suscetível"


def resposta_trecho(pergunta: str, c: dict) -> str:
    nome, pk = c["nome"], c["maior_exposicao"]
    if pergunta == "por_que_atencao":
        if c["percentil_do_indice_fisico"] is None:
            return f"{nome} está sem estimativa: falta o índice físico do terreno. Isso não significa que não haja risco, só que o baseline não tem dados para avaliá-lo."
        if pk is None or pk["classe"] not in ("alto", "atencao"):
            return (f"{nome} não aparece em atenção nas próximas 24 h. O escore combina a chuva estimada com o peso do trecho (percentil {round(c['percentil_do_indice_fisico'])}); "
                    "só os trechos mais suscetíveis recebem peso, e a chuva estimada não o eleva a Atenção neste horizonte.")
        extra = " Há ocorrência próxima registrada, que eleva o peso." if c["ocorrencias_proximas"] else ""
        return (f"{nome} fica em {_classe(pk['classe'])} por volta de {_hora(pk['hora'])} (escore {pk['escore']:.2f}). O terreno pesa: o trecho {_terreno(c)} "
                f"(percentil {round(c['percentil_do_indice_fisico'])} do índice físico). A chuva estimada é regional, não medida neste trecho.{extra}")
    if pergunta == "o_que_explica":
        return FORMULA + " " + ESCOPO_CHUVA
    return _lacunas(c)


def _lacunas(c: dict) -> str:
    return "Informações indisponíveis ou limitadas: " + " ".join(c["lacunas"]) + " " + LIMITE_GERAL


# ---------------------------------------------------------------- rota
def contexto_rota(a: dict, brutas: dict, interdicoes: int) -> dict:
    from .explicar import ROTULOS, hora, motivos

    rotas = {}
    for linha in a["comparacao"]:
        n = linha["rota"]
        r = brutas[n]
        rotas[n] = {"rotulo": ROTULOS[n], "tempo_min": linha["tempo_min"], "acrescimo_min": linha["acrescimo_min"], "distancia_km": linha["distancia_km"], "exposicao_estimada": linha["rotulo"],
                    "reducao_da_exposicao_pct": linha["reducao_exposicao_pct"], "km_em_atencao_ou_alto": linha["km_atencao_ou_alto"], "pct_do_trajeto_sem_dado": linha["pct_sem_estimativa"],
                    "trechos_mais_expostos": [{"nome": t["nome"] or "via sem nome", "classe": t["classe"], "passagem_entre": f"{hora(t['inicio'])} e {hora(t['fim'])}"}
                                              for t in sorted(r["trechos_de_risco"], key=lambda t: -t["escore"])[:4]], "motivos": motivos(r)}
    meteo = a["meteo"]
    lacunas = [ESCOPO_CHUVA]
    if meteo.get("indisponivel"):
        lacunas.insert(0, "Meteorologia indisponível: as rotas mostram só tempo e distância, sem estimativa de risco.")
    for n, r in rotas.items():
        if r["pct_do_trajeto_sem_dado"] >= 10:
            lacunas.append(f"{r['rotulo']}: {r['pct_do_trajeto_sem_dado']}% do trajeto não tem índice físico (trechos sem estimativa, que não são risco baixo).")
    if "menor_exposicao" not in rotas:
        lacunas.append("Não foi encontrada alternativa com menor exposição estimada.")
    return {"tipo": "rota", "modal": a["modal"], "chuva_na_janela_mm": meteo.get("total_na_janela_mm"), "interdicoes_confirmadas_consideradas": interdicoes, "rotas": rotas,
            "lacunas": lacunas, "metodo": FORMULA}


def resposta_rota(pergunta: str, c: dict, alerta: dict) -> str:
    rotas = c["rotas"]
    if pergunta == "o_que_muda":
        linhas = [f"{r['rotulo']}: {r['tempo_min']} min, {r['distancia_km']} km, {r['exposicao_estimada']}" + (f" ({r['acrescimo_min']:+d} min)" if n != "habitual" else "") for n, r in rotas.items()]
        return "Comparação das rotas calculadas: " + "; ".join(linhas) + ". " + alerta["texto"]
    if pergunta == "por_que_atencao":
        hab = rotas["habitual"]
        if not hab["trechos_mais_expostos"]:
            return "A rota habitual não tem trechos em atenção no horário estimado de passagem."
        nomes = ", ".join(f"{t['nome']} ({_classe(t['classe'])}, passagem entre {t['passagem_entre']})" for t in hab["trechos_mais_expostos"])
        return f"Trechos em atenção na rota habitual: {nomes}. Motivos: " + "; ".join(hab["motivos"]) + ". " + ESCOPO_CHUVA
    if pergunta == "o_que_explica":
        return FORMULA + " O risco é avaliado no horário estimado de passagem por cada trecho. " + ESCOPO_CHUVA
    return _lacunas(c)


# ---------------------------------------------------------------- município e rodovia
def contexto_territorio(tipo: str, nome: str, linha: dict, capacidades: dict) -> dict:
    rot = {"malha": "malha rodoviária DAER", "indice_fisico": "índice físico", "vdm": "tráfego (VDM)", "ocorrencias_s2id": "registros hidrológicos do S2iD"}
    lacunas = [f"{rot[k].capitalize()} abaixo do mínimo ou ausente." for k, ok in linha["dimensoes"].items() if not ok]
    lacunas += [f"{k.replace('_', ' ').capitalize()}: indisponível. {c['motivo']}" for k, c in capacidades.items() if c["estado"] == "indisponivel"]
    return {"tipo": tipo, "nome": nome, "classe_de_cobertura": linha["classe_rotulo"], "motivo_da_classe": linha["motivo"], "dimensoes": linha["dimensoes"],
            "malha_km": linha["km"], "km_com_indice_fisico": linha["km_com_indice_fisico"], "km_com_vdm": linha["km_com_vdm"], "segmentos": linha["segmentos"],
            "registros_s2id_2017_2026": linha.get("s2id_hidrologicos_2017_2026"), "lacunas": lacunas,
            "metodo": "A classe de cobertura descreve a existência de dados (malha, índice físico, tráfego e registros do S2iD), não a validade de nenhuma análise."}


def resposta_territorio(pergunta: str, c: dict) -> str:
    if pergunta == "o_que_explica":
        return f"{c['nome']}: {c['classe_de_cobertura']}. {c['motivo_da_classe']} {c['metodo']}"
    return _lacunas(c)


def resposta(tipo: str, pergunta: str, contexto: dict, alerta: dict | None = None) -> str:
    if tipo == "trecho":
        return resposta_trecho(pergunta, contexto)
    if tipo == "rota":
        return resposta_rota(pergunta, contexto, alerta)
    return resposta_territorio(pergunta, contexto)
