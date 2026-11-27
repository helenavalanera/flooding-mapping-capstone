"""Robustez da validação espacial: a conclusão do experimento de sensibilidade hidrológica depende de como o espaço foi dividido?

    PYTHONPATH=src python tools/robustez_espacial_validacao.py [saida.json] [relatorio.md]

Mantém a amostra, os rótulos e os escores de tools/experimento_sensibilidade_hidrologica.py e varia SÓ a divisão espacial:
  1. tamanho do bloco: 1, 1,5 (configuração original), 2 e 3 km;
  2. origem da grade: deslocamentos de meio bloco em x e/ou y;
  3. leave-one-block-out: retira-se da AVALIAÇÃO um bloco com positivos por vez (os escores já foram gerados fora do bloco), e também os k maiores.
O objetivo é medir estabilidade, não escolher a configuração com o melhor resultado: nenhuma é privilegiada. Os pontos de estabilidade foram fixados antes de ver os
resultados: >= 20 blocos com positivos, maior bloco <= 25% dos positivos e número efetivo de blocos >= 15; fora disso a configuração é registrada com a limitação.
Os escores A, B e D1 não têm parâmetros ajustados: o tamanho do bloco muda só os intervalos. O D2 é treinado com blocos inteiros fora do treino e muda também o valor.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experimento_modelos_alagamentos as exp  # noqa: E402
import experimento_sensibilidade_hidrologica as sens  # noqa: E402
from flooding_mapping.dados_restritos import ler_alagamentos  # noqa: E402
from flooding_mapping.risco_trecho import COMPONENTES  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
LADOS_M = (1000, 1500, 2000, 3000)
ORIGENS = {"(0;0)": (0.0, 0.0), "(½;0)": (0.5, 0.0), "(0;½)": (0.0, 0.5), "(½;½)": (0.5, 0.5)}   # deslocamento da grade, em fração do lado do bloco
LADO_ORIGINAL, ORIGEM_ORIGINAL = 1500, "(0;0)"
CENARIO_UNIFORME, CENARIO_ESPACIAL = "uniforme_0,50", "espacial_0,30-0,95"                      # os mesmos do experimento principal, fixados de antemão
MIN_BLOCOS, MAX_PARTICIPACAO, MIN_EFETIVO = 20, 0.25, 15


def blocos_deslocados(g: pd.DataFrame, lado_m: float, fx: float = 0.0, fy: float = 0.0) -> np.ndarray:
    """Spatial block of each segment; (fx, fy) shift the grid origin by a fraction of the block side. (0, 0) equals ``exp.blocos``."""
    x, y = (g.lon0 + g.lon1) / 2 * exp.KX, (g.lat0 + g.lat1) / 2 * exp.KY
    return (np.floor(x / lado_m - fx) * 100003 + np.floor(y / lado_m - fy)).to_numpy().astype(np.int64)


def estabilidade(dist: dict) -> dict:
    motivos = []
    if dist["blocos_com_positivo"] < MIN_BLOCOS:
        motivos.append(f"só {dist['blocos_com_positivo']} blocos com positivo (mínimo {MIN_BLOCOS})")
    if dist["participacao_do_maior_bloco"] > MAX_PARTICIPACAO:
        motivos.append(f"o maior bloco concentra {dist['participacao_do_maior_bloco']:.0%} dos positivos (máximo {MAX_PARTICIPACAO:.0%})")
    if dist["numero_efetivo_de_blocos"] < MIN_EFETIVO:
        motivos.append(f"número efetivo de blocos {dist['numero_efetivo_de_blocos']} (mínimo {MIN_EFETIVO})")
    return {"adequada": not motivos, "limitacoes": motivos}


def _escores(d: dict, folds_grupos, semente: int, dobras: int) -> dict:
    y, X5, regra, b, q = d["y"], d["X5"], d["regra"], d["b"], d["q"]
    folds = sens._folds(y, folds_grupos, np.random.default_rng(semente), min(dobras, len(np.unique(folds_grupos[y]))))
    out = {"A": regra, "B": b}
    for sufixo, nome in (("u", CENARIO_UNIFORME), ("e", CENARIO_ESPACIAL)):
        c = sens.escore_fisico(b, sens.coeficiente(q, *sens.CONFIGS_C[nome]), sens.P_BASE_MM)
        out[f"D1{sufixo}"] = 0.5 * sens._rank01(regra) + 0.5 * sens._rank01(c)
        out[f"D2{sufixo}"] = sens._oof_logistico(np.c_[X5, c], y, folds, regra / 100)
    return out


def _medidas_bloco(y, escores: dict, manter) -> dict:
    out = {}
    for k, v in escores.items():
        out[k] = (float(average_precision_score(y[manter], v[manter])), float(roc_auc_score(y[manter], v[manter])))
    ap_a = out["A"][0]
    return {k: {"ap": round(ap, 6), "auc": round(auc, 4), **({"ganho": round(ap / ap_a - 1, 4)} if k != "A" else {})} for k, (ap, auc) in out.items()}


def por_configuracao(d: dict, semente: int, replicas: int, dobras: int = 5) -> list:
    saida, g, y = [], d["g"], d["y"]
    for i, (lado, (nome_o, (fx, fy))) in enumerate((l, o) for l in LADOS_M for o in ORIGENS.items()):
        grupos = blocos_deslocados(g, lado, fx, fy)
        dist = sens.distribuicao_positivos(y, grupos)
        original = lado == LADO_ORIGINAL and nome_o == ORIGEM_ORIGINAL
        sem = semente if original else semente + 1 + i           # a configuração original usa a semente do experimento principal: resultados rastreáveis
        esc = _escores(d, grupos, sem, dobras)
        cmp_ = sens.comparar(y, esc, "A", np.random.default_rng(sem), replicas, grupos, completo=True)
        saida.append({"lado_m": lado, "origem": nome_o, "original": original, "distribuicao_dos_positivos": dist,
                      "estabilidade": estabilidade(dist), "blocos_totais": int(len(np.unique(grupos))),
                      "modelos": {k: {"precisao_media": v["precisao_media"], "auc": v["auc"], **({"ganho_sobre_a_regra": v["ganho_sobre_a_referencia"], "ic95_ganho_blocos_completos": v["ic95_ganho"],
                                                                                              "atende_criterio": v["atende_criterio"]} if k != "A" else {})} for k, v in cmp_.items()}})
    return saida


def leave_one_block_out(d: dict, semente: int, dobras: int = 5) -> dict:
    y, grupos = d["y"], d["grupos"]
    esc = _escores(d, grupos, semente, dobras)
    todos = np.ones(len(y), bool)
    completo = _medidas_bloco(y, esc, todos)
    contagem = pd.Series(grupos[y]).value_counts()
    linhas = []
    for bloco, n in contagem.items():
        m = _medidas_bloco(y, esc, grupos != bloco)
        linhas.append({"bloco": int(bloco), "positivos_removidos": int(n), "positivos_restantes": int(y.sum() - n), **{k: v for k, v in m.items()}})
    modelos = [k for k in completo if k != "A"]
    resumo = {}
    for k in modelos:
        g_ = np.array([l[k]["ganho"] for l in linhas])
        base = completo[k]["ganho"]
        resumo[k] = {"ganho_com_todos_os_blocos": base, "ganho_minimo": round(float(g_.min()), 4), "ganho_mediano": round(float(np.median(g_)), 4), "ganho_maximo": round(float(g_.max()), 4),
                     "blocos_que_invertem_o_sinal_do_ganho": int((np.sign(g_) != np.sign(base)).sum()), "blocos_com_ganho_acima_da_margem": int((g_ >= sens.MARGEM).sum())}
    ordens = {" > ".join(sorted(completo, key=lambda k: -(l[k]["ap"] if k in l else completo[k]["ap"]))) for l in linhas}
    maior = max(linhas, key=lambda l: l["positivos_removidos"])
    top_k = []
    for k in (1, 2, 3):
        sair = contagem.index[:k]
        top_k.append({"blocos_removidos": k, "positivos_restantes": int(y.sum() - contagem.iloc[:k].sum()), **_medidas_bloco(y, esc, ~np.isin(grupos, sair))})
    return {"com_todos_os_blocos": completo, "maior_bloco": {"bloco": maior["bloco"], "positivos": maior["positivos_removidos"], **{k: maior[k] for k in completo}},
            "resumo_por_modelo": resumo, "ordens_de_ap_distintas_entre_os_blocos": sorted(ordens), "remocao_dos_k_maiores_blocos": top_k,
            "por_bloco": linhas, "nota": "Os escores do D2 são fixos (gerados com a grade original): a retirada afeta a avaliação, não o treino."}


def rodar(rede: pd.DataFrame, coords: pd.DataFrame, semente: int = 7, replicas: int = 1000, raio_m: float = 100) -> dict:
    d = sens.preparar(rede, coords, raio_m)
    cfgs = por_configuracao(d, semente, replicas)
    lobo = leave_one_block_out(d, semente)
    modelos = ["B", "D1u", "D1e", "D2u", "D2e"]
    resumo = {}
    for k in modelos:
        gs = [c["modelos"][k]["ganho_sobre_a_regra"] for c in cfgs]
        resumo[k] = {"ganho_minimo": min(gs), "ganho_maximo": max(gs), "configuracoes_que_atendem_o_criterio": int(sum(c["modelos"][k]["atende_criterio"] for c in cfgs)),
                     "configuracoes_com_ganho_positivo": int(sum(x > 0 for x in gs))}
    adequadas = [c for c in cfgs if c["estabilidade"]["adequada"]]
    lobo_res = lobo["resumo_por_modelo"]
    nenhum = all(v["configuracoes_que_atendem_o_criterio"] == 0 for v in resumo.values()) and all(v["blocos_com_ganho_acima_da_margem"] == 0 for v in lobo_res.values())
    inversoes = max(v["blocos_que_invertem_o_sinal_do_ganho"] for k, v in lobo_res.items() if k.startswith("D1"))
    d2 = [resumo[k] for k in ("D2u", "D2e")]
    teto = max(v["ganho_maximo"] for v in lobo_res.values())
    f = lambda x: f"{x:+.1%}".replace(".", ",")
    f2 = lambda x: f"{100 * x:+.2f}%".replace(".", ",")
    texto = (f"Nenhuma configuração de blocos atende o critério de adoção (ganho de 10% com intervalo acima de zero) e nenhuma retirada de bloco atinge sequer a margem de 10% "
             f"(maior ganho observado: {f2(teto)}, sem intervalo de confiança nesta etapa). A decisão de não adotar não depende da divisão espacial testada. "
             f"Mas há sensibilidade que impede ler qualquer ganho como evidência: o ganho do D1 troca de sinal ao retirar até {inversoes} blocos, a ordem de precisão média entre "
             f"os modelos assume {len(lobo['ordens_de_ap_distintas_entre_os_blocos'])} formas distintas, e o D2 varia de {f(min(v['ganho_minimo'] for v in d2))} a "
             f"{f(max(v['ganho_maximo'] for v in d2))} conforme a grade."
             if nenhum else
             "A conclusão é sensível à divisão espacial: pelo menos uma configuração ou retirada de bloco atende o critério ou a margem; os detalhes estão nas tabelas e exigem cautela.")
    return {"amostra": {"trechos": int(len(d["y"])), "trechos_rotulados": int(d["y"].sum()), "semente": semente, "replicas_bootstrap": replicas},
            "criterios_de_estabilidade": {"minimo_de_blocos_com_positivo": MIN_BLOCOS, "maior_bloco_maximo": MAX_PARTICIPACAO, "numero_efetivo_minimo": MIN_EFETIVO},
            "cenarios_de_C": {"u": CENARIO_UNIFORME, "e": CENARIO_ESPACIAL}, "configuracoes": cfgs,
            "resumo_das_configuracoes": {"total": len(cfgs), "adequadas": len(adequadas), "por_modelo": resumo}, "leave_one_block_out": lobo,
            "conclusao": {"conclusao_depende_da_divisao_espacial": not nenhum, "texto": texto}}


def relatorio_md(r: dict) -> str:
    c, lo = r["resumo_das_configuracoes"], r["leave_one_block_out"]
    f = lambda x: f"{x:+.1%}".replace(".", ",")
    L = ["# Robustez da validação espacial", "", "Teste de estabilidade metodológica do experimento de sensibilidade hidrológica ([relatório principal](sensibilidade_hidrologica.md)). "
         "Não escolhe a melhor configuração: mede se a conclusão depende de como o espaço foi dividido. Exploratório; não valida previsão condicionada à chuva.", "",
         "## Conclusão", "", f"**{r['conclusao']['texto']}**", "",
         f"Amostra: {r['amostra']['trechos']:,} trechos, {r['amostra']['trechos_rotulados']} positivos, semente {r['amostra']['semente']}, {r['amostra']['replicas_bootstrap']} réplicas (bootstrap por conglomerados: blocos inteiros com seus negativos).".replace(",", ".", 1), "",
         "Modelos: B = fluxo ajustado pela declividade; D1 = média de postos regra + física; D2 = regressão logística (componentes + física). Sufixo `u` = C uniforme 0,50; `e` = C espacial 0,30–0,95 "
         "(os mesmos cenários do relatório principal, fixados antes). A = regra atual (referência).", "",
         "## 1 e 2. Tamanho do bloco e origem da grade", "",
         f"{c['total']} configurações; {c['adequadas']} cumprem os pontos de estabilidade fixados de antemão (≥ {r['criterios_de_estabilidade']['minimo_de_blocos_com_positivo']} blocos com positivos, maior bloco ≤ "
         f"{r['criterios_de_estabilidade']['maior_bloco_maximo']:.0%} dos positivos, número efetivo ≥ {r['criterios_de_estabilidade']['numero_efetivo_minimo']}). As demais ficam registradas, com a limitação.", "",
         "| Bloco | Origem | Blocos c/ positivo | Maior bloco | N efetivo | Adequada | B | D1u | D1e | D2u | D2e |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in r["configuracoes"]:
        d, m = x["distribuicao_dos_positivos"], x["modelos"]
        L.append(f"| {x['lado_m']} m{' (original)' if x['original'] else ''} | {x['origem']} | {d['blocos_com_positivo']} | {d['positivos_no_maior_bloco']} ({d['participacao_do_maior_bloco']:.0%}) | "
                 f"{str(d['numero_efetivo_de_blocos']).replace('.', ',')} | {'sim' if x['estabilidade']['adequada'] else 'não'} | " + " | ".join(f(m[k]["ganho_sobre_a_regra"]) for k in ("B", "D1u", "D1e", "D2u", "D2e")) + " |")
    L += ["", "Células de modelos: ganho relativo de precisão média sobre a regra atual.", "", "| Modelo | Ganho mínimo | Ganho máximo | Configurações que atendem o critério | Com ganho positivo |", "|---|---|---|---|---|"]
    for k, v in c["por_modelo"].items():
        L.append(f"| {k} | {f(v['ganho_minimo'])} | {f(v['ganho_maximo'])} | {v['configuracoes_que_atendem_o_criterio']} de {c['total']} | {v['configuracoes_com_ganho_positivo']} de {c['total']} |")
    inad = [x for x in r["configuracoes"] if not x["estabilidade"]["adequada"]]
    if inad:
        L += ["", "Configurações com limitação:", ""] + [f"- {x['lado_m']} m, origem {x['origem']}: " + "; ".join(x["estabilidade"]["limitacoes"]).replace(".", ",") for x in inad]
    L += ["", "## 3. Leave-one-block-out (grade original, 1,5 km)", "",
          f"Retira-se da avaliação um bloco com positivos por vez ({len(lo['por_bloco'])} blocos). {lo['nota']}", "",
          "| Modelo | Ganho com todos os blocos | Mínimo | Mediano | Máximo | Blocos que invertem o sinal | Blocos com ganho ≥ 10% |", "|---|---|---|---|---|---|---|"]
    for k, v in lo["resumo_por_modelo"].items():
        L.append(f"| {k} | {f(v['ganho_com_todos_os_blocos'])} | {f(v['ganho_minimo'])} | {f(v['ganho_mediano'])} | {f(v['ganho_maximo'])} | {v['blocos_que_invertem_o_sinal_do_ganho']} | {v['blocos_com_ganho_acima_da_margem']} |")
    mb = lo["maior_bloco"]
    L += ["", f"Bloco que concentra {mb['positivos']} positivos (id {mb['bloco']}): ganho sem ele " + ", ".join(f"{k} {f(mb[k]['ganho'])}" for k in ("B", "D1u", "D1e", "D2u", "D2e")) + ".", "",
          "Retirada dos k maiores blocos:", "", "| k | Positivos restantes | " + " | ".join(("B", "D1u", "D1e", "D2u", "D2e")) + " |", "|---|---|---|---|---|---|---|"]
    for t in lo["remocao_dos_k_maiores_blocos"]:
        L.append(f"| {t['blocos_removidos']} | {t['positivos_restantes']} | " + " | ".join(f(t[k]["ganho"]) for k in ("B", "D1u", "D1e", "D2u", "D2e")) + " |")
    L += ["", f"Ordens distintas de precisão média entre modelos ao retirar um bloco: {len(lo['ordens_de_ap_distintas_entre_os_blocos'])}.", ""]
    for o in lo["ordens_de_ap_distintas_entre_os_blocos"]:
        L.append(f"- {o}")
    L += ["", "## Como ler", "", "Estabilidade não é superioridade. Um resultado que muda de sinal com a retirada de um bloco não é interpretável; um que não muda continua exploratório "
          "(rótulos de 2013–2014, sem chuva associada, ~124 positivos). Reprodução: `PYTHONPATH=src python tools/robustez_espacial_validacao.py`.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    coords = ler_alagamentos()
    rede = pd.read_parquet(RAIZ / "data/processed/rede_poa.parquet", columns=["lon0", "lat0", "lon1", "lat1", "percentil", "slope", "log_flow_acc", *COMPONENTES])
    r = rodar(rede, coords)
    Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "reports/qa/robustez_espacial.json").write_text(json.dumps(r, ensure_ascii=False, indent=2))
    Path(sys.argv[2] if len(sys.argv) > 2 else RAIZ / "docs/robustez_espacial.md").write_text(relatorio_md(r))
    print(r["conclusao"]["texto"])
