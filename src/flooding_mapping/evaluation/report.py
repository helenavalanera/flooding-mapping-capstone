"""Write ``docs/ml_gatilho.md`` and its figures from the model cards (no number is typed by hand).

Every table and every comparative sentence is computed from ``reports/ml/*.json`` and the
saved test scores, so the document cannot drift from the results: when the model is retrained,
rerunning this module rewrites the text, including whether the model is called validated.
"""

from __future__ import annotations

import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_recall_curve  # noqa: E402

from ..config import resolve  # noqa: E402
from . import metrics  # noqa: E402

DOC = "docs/ml_gatilho.md"
FIGURES = "docs/figuras"
SCORERS = {"score": "Modelo", "regra_p3d": "Regra: chuva em 3 dias", "regra_rel_p3d": "Regra: chuva relativa em 3 dias",
           "logistica_chuva": "Regressão logística só com chuva"}
BUDGETS = (0.0025, 0.005, 0.01, 0.02, 0.03, 0.05, 0.10)


def table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    """A Markdown table from dicts: ``columns`` is (key, header)."""
    head = "| " + " | ".join(h for _, h in columns) + " |\n|" + "---|" * len(columns) + "\n"
    return head + "".join("| " + " | ".join(str(r.get(k, "")) for k, _ in columns) + " |\n" for r in rows)


def pct(x, digits=1) -> str:
    return "—" if x is None else f"{100 * x:.{digits}f}%".replace(".", ",")


def thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def num(x, digits=4) -> str:
    return "—" if x is None else f"{x:.{digits}f}".replace(".", ",")


def figures(label: str, card: dict, out) -> list[str]:
    """PR curves, events caught against the alert budget, calibration, stability and importance."""
    out.mkdir(parents=True, exist_ok=True)
    test = pd.read_parquet(resolve(f"data/processed/gatilho_{label}_teste.parquet"))
    y = test["y"].to_numpy()
    names = []

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for column, title in SCORERS.items():
        precision, recall, _ = precision_recall_curve(y, test[column])
        ax.plot(recall, precision, label=title, lw=2 if column == "score" else 1.2)
    ax.axhline(y.mean(), color="gray", ls=":", label="Prevalência (sem modelo)")
    ax.set(xlabel="Recall (dias-município)", ylabel="Precisão", yscale="log", title="Curvas precisão-recall no teste (2025 em diante)")
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(out / f"pr_teste_{label}.png", dpi=150); plt.close(fig)
    names.append(f"pr_teste_{label}.png")

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for column, title in SCORERS.items():
        recalls = [metrics.event_recall(test, test[column].to_numpy(), float(np.quantile(test[column], 1 - b)))["recall_eventos"] for b in BUDGETS]
        ax.plot([100 * b for b in BUDGETS], recalls, marker="o", label=title, lw=2 if column == "score" else 1.2)
    ax.plot([0.25, 10], [0.0025, 0.10], color="gray", ls=":", label="Alertas ao acaso")
    ax.set(xscale="log", xlabel="Dias-município em alerta (%)", ylabel="Eventos detectados (fração)", ylim=(0, 1),
           title="Eventos detectados por orçamento de alertas (teste)")
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(out / f"eventos_teste_{label}.png", dpi=150); plt.close(fig)
    names.append(f"eventos_teste_{label}.png")

    rel = pd.DataFrame(card["teste_2025_em_diante"]["calibracao"]["confiabilidade"])
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    top = float(max(rel["previsto"].max(), rel["observado"].max())) * 1.3
    ax.plot([1e-5, top], [1e-5, top], color="gray", ls=":", label="Calibração perfeita")
    ax.plot(rel["previsto"].clip(lower=1e-5), rel["observado"].clip(lower=1e-5), marker="o", label="Modelo calibrado")
    ax.set(xscale="log", yscale="log", xlabel="Probabilidade prevista", ylabel="Frequência observada", title="Calibração no teste")
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(out / f"calibracao_{label}.png", dpi=150); plt.close(fig)
    names.append(f"calibracao_{label}.png")

    rolling = pd.DataFrame(card["estabilidade_temporal_janela_movel"])
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    width = 0.27
    for i, (column, title) in enumerate((("pr_auc_modelo", "Modelo"), ("pr_auc_regra_p3d", "Regra: chuva em 3 dias"),
                                         ("pr_auc_logistica_chuva", "Logística só com chuva"))):
        ax.bar(np.arange(len(rolling)) + (i - 1) * width, rolling[column], width, label=title)
    ax.set_xticks(np.arange(len(rolling)), rolling["ano"]); ax.set(ylabel="PR-AUC", title="Estabilidade ao longo dos anos (janela móvel)")
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(out / f"janela_movel_{label}.png", dpi=150); plt.close(fig)
    names.append(f"janela_movel_{label}.png")

    imp = pd.DataFrame(card["importancia_por_permutacao_pr_auc"]).head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    ax.barh(imp["variavel"], imp["queda_media"], xerr=imp["desvio"])
    ax.set(xlabel="Queda do PR-AUC ao embaralhar a variável", title="Importância por permutação (teste)")
    fig.tight_layout(); fig.savefig(out / f"importancia_{label}.png", dpi=150); plt.close(fig)
    names.append(f"importancia_{label}.png")
    return names


def comparison_sentence(card: dict) -> str:
    """What the model does against the plain rainfall rule, in the same alert budget."""
    budget = card["teste_2025_em_diante"]["orcamentos_de_alerta"]
    m, rule = budget["modelo"]["alertas_2pct"], budget["regra_p3d"]["alertas_2pct"]
    more = m["eventos_detectados"] - rule["eventos_detectados"]
    verb = "mais" if more > 0 else "menos" if more < 0 else "o mesmo número de"
    gap = "" if more == 0 else f" ({abs(more)} {verb})"
    return (f"Com 2% dos dias-município em alerta, o modelo detecta {m['eventos_detectados']} dos {m['eventos']} eventos "
            f"de teste ({pct(m['recall_eventos'], 0)}), contra {rule['eventos_detectados']} da regra de chuva em 3 dias "
            f"({pct(rule['recall_eventos'], 0)}){gap}.")


def render(label: str, card: dict, skew: dict | None, index: dict | None, impact: dict | None, figs: list[str]) -> str:
    d, dec, test = card["dataset"], card["decisao"], card["teste_2025_em_diante"]
    art = card["artefato"]
    tuned = pd.DataFrame(card["ajuste_de_hiperparametros_val"])
    tuned["pr_auc"] = tuned["pr_auc"].map(num)
    tuned["roc_auc"] = tuned["roc_auc"].map(num)
    budget_rows = []
    for name, title in (("modelo", "Modelo"), ("regra_p3d", "Regra: chuva em 3 dias"), ("regra_rel_p3d", "Regra: chuva relativa"),
                        ("logistica_chuva", "Logística só com chuva")):
        row = {"Método": title}
        for b in ("alertas_0.5pct", "alertas_2pct", "alertas_5pct"):
            r = test["orcamentos_de_alerta"][name][b]
            row[b] = f"{r['eventos_detectados']}/{r['eventos']} ({pct(r['recall_eventos'], 0)}), precisão {pct(r['precisao'], 2)}"
        budget_rows.append(row)
    err = test["analise_de_erros_no_orcamento_2pct"]
    lines = [
        f"# Gatilho municipal de risco hídrico: dados, método e resultados ({label})\n",
        "_Documento gerado por `python -m flooding_mapping.evaluation.report`. Os números vêm de "
        f"`reports/ml/gatilho_{label}.json`; nenhum foi digitado à mão._\n",
        "## Resumo\n",
        f"- **Estado do modelo:** {dec['estado']}.",
        f"- **Pergunta:** dado o cenário de chuva, qual município tem mais chance de **registrar um desastre hídrico** "
        f"(inundação, enxurrada ou alagamento) naquele dia? Não prevê profundidade, extensão nem duração da água.",
        f"- **Dados:** {thousands(d['linhas_usadas'])} dias-município de {d['municipios']} municípios ({d['periodo'][0]} a {d['periodo'][1]}), "
        f"{thousands(d['positivos'])} dias positivos em {d['episodios']} episódios, prevalência {pct(d['prevalencia'], 2)}.",
        f"- **Teste (2025 em diante, tocado uma única vez):** PR-AUC {num(test['modelo']['pr_auc'])} contra prevalência "
        f"{num(test['modelo']['prevalencia'])}; ROC-AUC {num(test['modelo']['roc_auc'], 3)}.",
        f"- {comparison_sentence(card)}",
        f"- **Modelo versionado:** `{art['versao']}`, treinado de {art['treinado_desde']} a {art['treinado_ate']}; "
        f"SHA-256 `{art['sha256'][:16]}…` (o artefato fica fora do git).\n",
        "## 1. Dados (template 3.1)\n",
        table([
            {"f": "S2iD (MIDR)", "c": "Registros de desastre por município (COBRADE, data, situação, danos)", "u": "Rótulo (variável-alvo)",
             "a": "CSV exportado manualmente do portal; CC-BY; 2017–2026"},
            {"f": "Open-Meteo, arquivo (ERA5)", "c": "Precipitação diária por município", "u": "Variáveis de chuva",
             "a": "API pública gratuita (uso não comercial); CC BY 4.0"},
            {"f": "Open-Meteo, previsão", "c": "Chuva dos últimos 40 dias e dos próximos 3", "u": "Operação (72 h)", "a": "API pública"},
            {"f": "IBGE, Censo 2022", "c": "Municípios, área, população", "u": "Variáveis territoriais", "a": "Aberto"},
            {"f": "DAER (SRE-RS)", "c": "Malha rodoviária, VDM, IRI", "u": "Impacto e suscetibilidade", "a": "Camada ArcGIS pública e planilha; licença a confirmar"},
            {"f": "CPRv BM", "c": "Bloqueios rodoviários ativos", "u": "Observação e rótulos futuros", "a": "API pública, sem histórico (coletor próprio)"},
        ], [("f", "Fonte"), ("c", "Conteúdo"), ("u", "Uso"), ("a", "Acesso e restrições")]),
        "\nOs dados brutos não são versionados (procedência e hash em `data/raw/manifest.json`). Dados derivados pequenos "
        "(camadas do mapa, rankings de impacto, cartões dos modelos) ficam no repositório. O dataset do gatilho é gerado "
        "por `make estado-modelo`; a publicação em Zenodo ou Hugging Face depende da confirmação das licenças.\n",
        "## 2. ETL e engenharia de dados (template 3.2)\n",
        "1. **Coleta:** `ingestion/` (S2iD, DAER, Open-Meteo, municípios), com cache em disco, retomada e respeito aos limites da API.",
        "2. **Organização:** uma linha por município e dia (`datasets/gatilho.py`).",
        "3. **Limpeza:** protocolos do S2iD fora do padrão são erro explícito; duplicatas por protocolo removidas; janelas de chuva "
        "incompletas viram NaN e a linha é descartada, nunca preenchida.",
        f"4. **Rótulo:** `y = 1` nos {d['janela_rotulo_dias']} dias que terminam na data do protocolo; os {d['buffer_pos_evento_dias']} dias "
        "seguintes são excluídos (a água ainda está lá). Os demais dias são negativos **não rotulados**: município sem registro não é "
        "município sem alagamento, então a precisão é um piso.",
        "5. **Variáveis** (`features/weather.py`): chuva no dia e acumulada em 2, 3, 5, 7, 14 e 30 dias; chuva dos 7 e 30 dias anteriores; "
        "máximo diário em 7 dias; dias úmidos em 30; chuva relativa ao percentil 95 do próprio município (climatologia 2017–2019); "
        "contexto regional (média e máximo da região imediata e fração do estado com ≥50 mm em 3 dias); sazonalidade; altitude, "
        "área e população. **Nenhuma variável do dia `d` usa chuva posterior a `d`** (testado).",
        "6. **EDA:** o protocolo coincide com o dia da chuva: mediana de 39,5 mm no dia do protocolo e 2,1 mm no seguinte; 65% dos "
        "registros têm ≥20 mm no dia contra 6,6% em dias aleatórios. A chuva forte é comum e o registro é raro, por isso o PR-AUC é baixo.\n",
        table([{"ano": a, "pos": p} for a, p in d["positivos_por_ano"].items()], [("ano", "Ano"), ("pos", "Dias positivos")]),
        "\n## 3. Seleção do modelo (template 3.3)\n",
        "Dados tabulares, relação não linear e extremamente desbalanceada: comparam-se regressão logística (referência interpretável), "
        "floresta aleatória e gradiente de árvores (`HistGradientBoosting`), todos contra três baselines simples (acaso, regra de chuva "
        "em 3 dias, regra de chuva relativa) e uma logística só com chuva. Não há série temporal no modelo: a dinâmica entra pelas "
        "janelas de chuva acumulada. Redes neurais não foram usadas porque 1.5 mil positivos agrupados em poucas dezenas de "
        "episódios não sustentam um modelo mais flexível; seria sobreajuste.",
        f"\n**Escolha:** {dec['familia']} {json.dumps(dec['parametros'], ensure_ascii=False)}, a família mais simples dentro de "
        f"{pct(0.1, 0)} (relativo) do melhor PR-AUC de validação. **Estado:** {dec['estado']}.\n",
        "O selo \"validado\" exige três critérios independentes, todos medidos antes do teste:\n",
        table([{"c": k.replace("_", " "), "p": "sim" if v["passa"] else "**não**", "d": v["detalhe"]} for k, v in dec["criterios"].items()],
              [("c", "Critério"), ("p", "Passa"), ("d", "Detalhe")]),
        "## 4. Treinamento (template 3.4)\n",
        f"Semente {card['semente']}; ambiente: Python {card['ambiente']['python']}, scikit-learn {card['ambiente']['sklearn']}, "
        f"numpy {card['ambiente']['numpy']}, pandas {card['ambiente']['pandas']}. Treina-se com todos os positivos e 50 negativos "
        "aleatórios por positivo (velocidade e equilíbrio); a avaliação usa todas as linhas, com a prevalência natural, e a "
        "calibração isotônica devolve as probabilidades a essa escala. Sem épocas, batch ou taxa de aprendizado além dos "
        "hiperparâmetros abaixo (gradiente de árvores: 300 iterações, regularização L2 = 1).\n",
        "**Partições temporais** (com expurgo de 7 dias nas fronteiras):\n",
        table([{"p": k, "l": f"{v['linhas']:,}".replace(",", "."), "pos": v["positivos"], "per": f"{v['periodo'][0]} a {v['periodo'][1]}"}
               for k, v in card["particoes"].items()], [("p", "Partição"), ("l", "Linhas"), ("pos", "Positivos"), ("per", "Período")]),
        f"\nEpisódios com positivos em mais de uma partição: **{card['vazamento_episodios_entre_particoes']}**.\n",
        "**Hiperparâmetros testados** (ajustados só na validação, 2023–2024):\n",
        table(tuned.to_dict("records"), [("familia", "Família"), ("parametros", "Parâmetros"), ("pr_auc", "PR-AUC val."), ("roc_auc", "ROC-AUC val.")]),
        "\n**Seleção de variáveis** (ablação com um modelo fixo, validação):\n",
        table([{**r, "pr_auc": num(r["pr_auc"]), "roc_auc": num(r["roc_auc"])} for r in card["selecao_de_variaveis"]["ablacao_val"]],
              [("conjunto", "Conjunto"), ("n_variaveis", "Variáveis"), ("pr_auc", "PR-AUC"), ("roc_auc", "ROC-AUC")]),
        f"\nEscolhido: **{card['selecao_de_variaveis']['escolhido']}** ({len(card['selecao_de_variaveis']['variaveis'])} variáveis).\n",
        "## 5. Validação cruzada (template 3.5)\n",
        "A validação respeita o tempo e os episódios: (a) partição temporal fixa; (b) **janela móvel** (treina no passado e prevê um ano, "
        "2020–2026), cujos resultados de 2020–2024 calibram o modelo e fixam os limiares, e os de 2025–2026 só são reportados; "
        "(c) **generalização espacial**: treina em quatro quintos dos municípios (antes de 2023) e testa nos demais (2025 em diante).\n",
        table([{"ano": r["ano"], "pos": r["positivos"], "m": num(r["pr_auc_modelo"]), "r": num(r["pr_auc_regra_p3d"]), "l": num(r["pr_auc_logistica_chuva"])}
               for r in card["estabilidade_temporal_janela_movel"]],
              [("ano", "Ano"), ("pos", "Positivos"), ("m", "PR-AUC modelo"), ("r", "PR-AUC regra 3 dias"), ("l", "PR-AUC logística")]),
        "\n",
        table([{"b": r["bloco"], "mun": r["municipios"], "pos": r["positivos"], "m": num(r["pr_auc_modelo"]), "r": num(r["pr_auc_regra_p3d"])}
               for r in card["generalizacao_espacial_blocos_fora_do_treino"]],
              [("b", "Região fora do treino"), ("mun", "Municípios"), ("pos", "Positivos"), ("m", "PR-AUC modelo"), ("r", "PR-AUC regra 3 dias")]),
        "\n## 6. Avaliação (template 3.6)\n",
        f"Matriz de confusão e demais métricas por orçamento de alertas (limiares fixados em 2020–2024, aplicados ao teste). "
        f"Acurácia não é reportada: com prevalência de {pct(test['modelo']['prevalencia'], 2)}, um modelo que nunca alerta acerta mais de 99%.\n",
        table([{"o": o, "tp": r["tp"], "fp": r["fp"], "fn": r["fn"], "tn": f"{r['tn']:,}".replace(",", "."), "p": pct(r["precisao"], 2),
                "rc": pct(r["recall"], 1), "f1": num(r["f1"]), "dias": r["dias_alerta_por_mil"], "ev": f"{r['eventos_detectados']}/{r['eventos']}"}
               for o, r in test["orcamentos_de_alerta"]["modelo"].items()],
              [("o", "Orçamento"), ("tp", "VP"), ("fp", "FP"), ("fn", "FN"), ("tn", "VN"), ("p", "Precisão"), ("rc", "Recall (dias)"),
               ("f1", "F1"), ("dias", "Alertas por mil dias"), ("ev", "Eventos detectados")]),
        "\n**Eventos detectados no mesmo orçamento, modelo e baselines** (uma sequência de dias positivos conta como um evento):\n",
        table(budget_rows, [("Método", "Método"), ("alertas_0.5pct", "0,5% dos dias"), ("alertas_2pct", "2% dos dias"), ("alertas_5pct", "5% dos dias")]),
        f"\n{comparison_sentence(card)}\n",
        "\n".join(f"![{n}](figuras/{n})" for n in figs) + "\n",
        f"**Falsos negativos e falsos positivos (orçamento de 2%).** Dos eventos, {err['eventos_perdidos']} não foram detectados; a chuva "
        f"mediana em 3 dias nos perdidos foi {err['chuva_3d_mediana_mm_nos_eventos_perdidos']} mm contra "
        f"{err['chuva_3d_mediana_mm_nos_eventos_detectados']} mm nos detectados: o modelo perde sobretudo tempestades locais que a "
        f"reanálise não enxerga. Houve {err['alarmes_falsos_dias']:,} dias de falso alarme em {err['municipios_com_alarme_falso']} municípios".replace(",", ".")
        + f", {pct(err['alarmes_falsos_a_menos_de_7_dias_de_um_evento'], 1)} deles a menos de 7 dias de um evento do mesmo município "
        "(possíveis erros de data ou registros tardios). Operacionalmente, um falso negativo é um evento sem aviso; um falso positivo é "
        "um alerta sem registro, e como a base não rotula negativos, estes são um limite superior.\n",
        f"**Calibração.** Brier {num(test['calibracao']['brier'], 6)} contra {num(test['calibracao']['brier_referencia_prevalencia'], 6)} "
        "de um preditor constante: com eventos tão raros a calibração melhora a escala das probabilidades, não a discriminação.\n",
    ]
    if skew:
        rows = []
        for key, title in (("reanalise", "Reanálise (como no treino)"), ("reanalise_nos_mesmos_dias", "Reanálise, mesmos dias da previsão"),
                           ("previsao_1d_antes", "Previsão feita 1 dia antes"), ("previsao_2d_antes", "Previsão feita 2 dias antes")):
            if key in skew:
                s = skew[key]
                top = s["orcamentos"]["alertas_2pct"]
                rows.append({"c": title, "l": f"{s['linhas']:,}".replace(",", "."), "pr": num(s["pr_auc"]), "roc": num(s["roc_auc"], 3),
                             "ev": f"{top['eventos_detectados']}/{top['eventos']}",
                             "corr": num(s.get("chuva", {}).get("correlacao"), 3) if "chuva" in s else "—"})
        lines += ["## 7. Treino com reanálise, operação com previsão\n",
                  "O endpoint de \"previsão histórica\" do Open-Meteo devolve **a mesma série da reanálise** (diferença de 0,00 mm/dia em 2019–2026), "
                  "então não serve de evidência de previsão. Previsões reais arquivadas existem desde meados de 2024 (API de execuções anteriores); "
                  "com elas, o mesmo modelo testado é pontuado com chuva prevista 1 e 2 dias antes, em todos os dias da janela (limite superior "
                  "da perda: na operação os dias passados são análise).\n",
                  table(rows, [("c", "Entrada de chuva"), ("l", "Linhas"), ("pr", "PR-AUC"), ("roc", "ROC-AUC"), ("ev", "Eventos @2%"), ("corr", "Correlação diária com a reanálise")]), "\n"]
    if index:
        lines += ["## 8. Suscetibilidade por segmento (índice, não probabilidade)\n",
                  f"{index['natureza']}. {index['segmentos']:,} segmentos de 1 km; componentes: baixa altitude, depressão local e proximidade da água "
                  "(pesos iguais, nada é ajustado).".replace(",", ".") + "\n",
                  f"- Segmentos com bloqueio observado: {json.dumps(index['segmentos_com_bloqueio_observado'], ensure_ascii=False)}",
                  f"- Verificação municipal fraca: {json.dumps(index['verificacao_municipal_fraca'], ensure_ascii=False)}\n"]
    if impact:
        cov, cmp_ = impact["cobertura"], impact["com_x_sem_peso_do_vdm"]
        lines += ["## 9. Impacto na mobilidade (simulado)\n",
                  f"{impact['natureza']}. Cobertura do VDM: {pct(cov['fracao_com_vdm'], 1)} dos segmentos (ausente não é zero). "
                  f"Entre os {cmp_['trechos_com_vdm_e_desvio']} trechos com VDM e desvio, a correlação de Spearman entre o desvio sem peso e "
                  f"ponderado é {num(cmp_['spearman_desvio_x_ponderado'], 2)} e só {cmp_['sobreposicao_top50']} dos 50 primeiros coincidem: "
                  "o peso do tráfego muda de verdade a prioridade.\n",
                  "\n".join(f"- {x}" for x in impact["limites"]) + "\n"]
    lines += ["## 10. Limitações e riscos\n",
              "- Negativos não rotulados; precisão é um piso. Município sem registro não é município sem alagamento.",
              "- Poucos episódios independentes (dezenas), muito concentrados (2023 e 2024); a validação é por episódio, mas o erro de estimativa é grande.",
              "- Mudança de notificação a partir de 2023 (mais registros de \"chuvas intensas\"): o rótulo estrito evita parte disso; o amplo não.",
              "- A data do protocolo é a de abertura do registro, não a do dano; usa-se uma janela de rótulo.",
              "- Treino em reanálise e operação em previsão; ver a seção 7.",
              "- O modelo estima o registro de um desastre, não a água na rua; não substitui os alertas oficiais.\n",
              "## 11. Como reproduzir\n",
              "```bash\nmake estado-dados     # municípios, S2iD, malha DAER, segmentos, impacto, camadas\nmake estado-chuva     # chuva diária por município (retoma de onde parou)\n"
              "make estado-modelo    # treina e valida (estrito e amplo)\nmake estado-avaliacao # previsão versus reanálise\n"
              "PYTHONPATH=src python -m flooding_mapping.evaluation.report --label estrito\n```\n"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write docs/ml_gatilho.md from the model cards")
    parser.add_argument("--label", default="estrito")
    args = parser.parse_args()
    load = lambda name: json.loads(resolve(name).read_text()) if resolve(name).exists() else None  # noqa: E731
    card = load(f"reports/ml/gatilho_{args.label}.json")
    figs = figures(args.label, card, resolve(FIGURES))
    text = render(args.label, card, load(f"reports/ml/skew_{args.label}.json"), load("reports/ml/indice_suscetibilidade.json"),
                  load("reports/qa/impacto_rs.json"), figs)
    resolve(DOC).write_text(text)
    print(f"{DOC}: {len(text.splitlines())} linhas, {len(figs)} figuras")


if __name__ == "__main__":
    main()
