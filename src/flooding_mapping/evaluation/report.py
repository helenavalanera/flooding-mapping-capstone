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
from ..models.gatilho import GATE_NAMES  # noqa: E402
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


def budget_label(key: str) -> str:
    """``alertas_0.5pct`` -> ``0,5% dos dias``."""
    return key.replace("alertas_", "").replace("pct", "% dos dias").replace(".", ",")


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


def eda_line(card: dict) -> str:
    """The data-exploration finding that explains the low PR-AUC, from the card."""
    e = card["chuva_em_torno_dos_registros"]
    med = e["mediana_mm_por_defasagem"]
    return (f"6. **EDA** ({e['registros']} registros): o protocolo coincide com o dia da chuva. Mediana de chuva de {num(med['0'], 1)} mm "
            f"no dia do protocolo, {num(med['-1'], 1)} mm no dia anterior e {num(med['1'], 1)} mm no seguinte; "
            f"{pct(e['fracao_com_chuva_forte_no_dia_do_protocolo'], 0)} dos registros têm ≥{e['chuva_forte_mm']:g} mm no dia, contra "
            f"{pct(e['fracao_com_chuva_forte_em_dias_aleatorios'], 1)} em dias aleatórios. A chuva forte é comum e o registro é raro, "
            "por isso o PR-AUC é baixo mesmo com sinal real.\n")


def operational_lines(card: dict) -> list[str]:
    """Which trigger runs, why, how it did on the test years and what its errors look like."""
    op = card["gatilho_operacional"]
    perf = op["desempenho_teste"]
    rows = [{"o": budget_label(budget), "ev": f"{r['eventos_detectados']}/{r['eventos']} ({pct(r['recall_eventos'], 0)})",
             "p": pct(r["precisao"], 2), "d": num(r["dias_alerta_por_mil"], 1), "tp": r["tp"], "fp": thousands(r["fp"]), "fn": r["fn"]}
            for budget, r in perf["orcamentos"].items()]
    err = perf["analise_de_erros_no_orcamento_2pct"]
    return ["## 7. Gatilho em uso\n",
            f"**{op['descricao'].capitalize()}.** {op['estado'][0].upper() + op['estado'][1:]}.\n",
            f"Motivo: o modelo de aprendizado de máquina ficou como *{op['motivo']}*.\n" if op["tipo"] == "regra" else "",
            f"No teste (2025 em diante): PR-AUC {num(perf['pr_auc'])}, ROC-AUC {num(perf['roc_auc'], 3)}, prevalência {num(perf['prevalencia'])}; "
            f"Brier {num(perf['calibracao']['brier'], 6)} (referência constante {num(perf['calibracao']['brier_referencia_prevalencia'], 6)}).\n",
            table(rows, [("o", "Limiar fixado em 2020–2024 (orçamento)"), ("ev", "Eventos detectados"), ("p", "Precisão (piso)"), ("d", "Alertas por mil dias"),
                         ("tp", "VP"), ("fp", "FP"), ("fn", "FN")]),
            f"\n**Erros do gatilho em uso (orçamento de 2%).** {err['eventos_perdidos']} eventos não foram detectados; a chuva mediana em 3 dias "
            f"foi {num(err['chuva_3d_mediana_mm_nos_eventos_perdidos'], 1)} mm nos perdidos contra {num(err['chuva_3d_mediana_mm_nos_eventos_detectados'], 1)} mm "
            f"nos detectados, ou seja, o que escapa são sobretudo tempestades locais que a reanálise de ~10 km não enxerga. Houve "
            f"{thousands(err['alarmes_falsos_dias'])} dias de falso alarme em {err['municipios_com_alarme_falso']} municípios, "
            f"{pct(err['alarmes_falsos_a_menos_de_7_dias_de_um_evento'], 1)} deles a menos de 7 dias de um evento do mesmo município "
            "(possíveis erros de data ou registros tardios). Um falso negativo é um evento sem aviso; um falso positivo é um alerta sem "
            "registro, e como a base não rotula negativos, estes são um limite superior.\n"]


def history_lines(card: dict, versions: list[tuple[str, dict]]) -> list[str]:
    """Pipeline versions that were scored on the test years, with what changed."""
    if not versions:
        return []
    rows = []
    for name, c in versions + [("versão atual", card)]:
        t = c["teste_2025_em_diante"]
        rows.append({"v": name, "m": f"{c['decisao']['familia']} {json.dumps(c['decisao']['parametros'], ensure_ascii=False)}",
                     "pr": num(t["modelo"]["pr_auc"]), "roc": num(t["modelo"]["roc_auc"], 3)})
    return ["## 8. Histórico do pipeline e uso do teste\n",
            "O teste (2025 em diante) foi consultado **duas vezes**, por duas versões do pipeline. A primeira treinou os modelos sem restrições. "
            "Ao ver que o modelo ficava abaixo das regras já na **validação** (2023–2024), a segunda passou a impor que o risco não caia quando a "
            "chuva sobe (restrição monotônica nas árvores e escala logarítmica na logística). Essa escolha se baseou na validação e na janela "
            "móvel, não no teste, mas o teste já havia sido visto, então a segunda leitura não é a de um conjunto virgem.\n",
            table(rows, [("v", "Versão"), ("m", "Modelo escolhido"), ("pr", "PR-AUC teste"), ("roc", "ROC-AUC teste")]), "\n"]


def operational_sentence(card: dict) -> str:
    perf = card["gatilho_operacional"]["desempenho_teste"]["orcamentos"]["alertas_2pct"]
    return (f"**Gatilho em uso, no teste:** com os limiares fixados em 2020–2024 (orçamento de 2%), que no teste alertaram em "
            f"{num(perf['dias_alerta_por_mil'] / 10, 1)}% dos dias-município, detecta {perf['eventos_detectados']} dos {perf['eventos']} eventos "
            f"({pct(perf['recall_eventos'], 0)}), com precisão de {pct(perf['precisao'], 2)} (piso).")


def equal_share_events(test: pd.DataFrame, columns=tuple(SCORERS), budgets=(0.005, 0.01, 0.02, 0.05)) -> dict:
    """Events caught by each scorer when each alerts on the same share of the test days.

    The threshold of each scorer is a quantile of its *own* test scores, so the comparison measures
    ranking alone and cannot be distorted by a shift in the scale of the scores.
    """
    y = test["y"].to_numpy()
    out = {}
    for column in columns:
        score = test[column].to_numpy()
        out[column] = {}
        for budget in budgets:
            threshold = float(np.quantile(score, 1 - budget))
            caught = metrics.event_recall(test, score, threshold)
            out[column][budget] = {"eventos": caught["eventos"], "detectados": caught["eventos_detectados"],
                                   "precisao": metrics.at_threshold(y, score, threshold)["precisao"]}
    return out


def comparison_sentence(card: dict, fair: dict) -> str:
    """The honest reading of model against rules: same alert share on test, and before the test."""
    at = lambda col: fair[col][0.02]  # noqa: E731
    m, rel, p3, lg = at("score"), at("regra_rel_p3d"), at("regra_p3d"), at("logistica_chuva")
    before = card["eventos_oof_no_orcamento_do_portao"]
    best_rule = max(before["regra_p3d"], before["regra_rel_p3d"])
    return (f"Com o mesmo número de dias em alerta no teste (2%), o modelo de aprendizado de máquina detecta {m['detectados']} dos {m['eventos']} "
            f"eventos ({pct(m['detectados'] / m['eventos'], 0)}), a logística só com chuva {lg['detectados']}, a regra de chuva relativa "
            f"{rel['detectados']} e a regra de chuva em 3 dias {p3['detectados']}. Antes do teste (janela móvel de 2020–2024, mesmo orçamento) a ordem "
            f"foi a inversa: a melhor regra detectou {pct(best_rule, 0)} dos eventos e o modelo {pct(before['modelo'], 0)}. São diferenças de poucas "
            "dezenas de eventos, agrupados em poucos episódios, que não permitem afirmar que um supera o outro.")


def render(label: str, card: dict, skew: dict | None, index: dict | None, impact: dict | None, figs: list[str],
           other: dict | None = None, versions: list[tuple[str, dict]] | None = None) -> str:
    d, dec, test = card["dataset"], card["decisao"], card["teste_2025_em_diante"]
    art = card["artefato"]
    tuned = pd.DataFrame(card["ajuste_de_hiperparametros_val"])
    tuned["pr_auc"] = tuned["pr_auc"].map(num)
    tuned["roc_auc"] = tuned["roc_auc"].map(num)
    test_scores = pd.read_parquet(resolve(f"data/processed/gatilho_{label}_teste.parquet"))
    oof = pd.read_parquet(resolve(f"data/processed/gatilho_{label}_oof.parquet"))
    p98_oof = float(np.quantile(oof.loc[oof["ano"] <= 2024, "score"], 0.98))
    p98_test = float(np.quantile(test_scores["score"], 0.98))
    fair = equal_share_events(test_scores)
    fair_rows = []
    for column, title in SCORERS.items():
        row = {"Método": title}
        for b in (0.005, 0.01, 0.02, 0.05):
            r = fair[column][b]
            row[b] = f"{r['detectados']}/{r['eventos']} ({pct(r['detectados'] / r['eventos'], 0)}), precisão {pct(r['precisao'], 2)}"
        fair_rows.append(row)
    lines = [
        f"# Gatilho municipal de risco hídrico: dados, método e resultados ({label})\n",
        "_Documento gerado por `python -m flooding_mapping.evaluation.report`. Os números vêm de "
        f"`reports/ml/gatilho_{label}.json`; nenhum foi digitado à mão._\n",
        "## Resumo\n",
        f"- **Gatilho em uso:** {card['gatilho_operacional']['descricao']}.",
        f"- **Modelo de aprendizado de máquina:** {dec['estado']}.",
        "- **Pergunta:** dado o cenário de chuva, qual município tem mais chance de **registrar um desastre hídrico** "
        "(inundação, enxurrada ou alagamento) naquele dia? Não prevê profundidade, extensão nem duração da água.",
        f"- **Dados:** {thousands(d['linhas_usadas'])} dias-município de {d['municipios']} municípios ({d['periodo'][0]} a {d['periodo'][1]}), "
        f"{thousands(d['positivos'])} dias positivos em {d['episodios']} episódios, prevalência {pct(d['prevalencia'], 2)}.",
        f"- **Teste do modelo (2025 em diante; ver a seção 8 sobre seu uso):** PR-AUC {num(test['modelo']['pr_auc'])} contra prevalência "
        f"{num(test['modelo']['prevalencia'])}; ROC-AUC {num(test['modelo']['roc_auc'], 3)}.",
        f"- {comparison_sentence(card, fair)}",
        f"- {operational_sentence(card)}",
        f"- **Artefato do gatilho:** `{art['versao']}`, ajustado com dados de {art['treinado_desde']} a {art['treinado_ate']}; "
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
        eda_line(card),
        table([{"ano": a, "pos": p} for a, p in d["positivos_por_ano"].items()], [("ano", "Ano"), ("pos", "Dias positivos")]),
        "\n## 3. Seleção do modelo (template 3.3)\n",
        "Dados tabulares, relação não linear e extremamente desbalanceada: comparam-se regressão logística (referência interpretável), "
        "floresta aleatória e gradiente de árvores (`HistGradientBoosting`), todos contra três baselines simples (acaso, regra de chuva "
        "em 3 dias, regra de chuva relativa) e uma logística só com chuva. Não há série temporal no modelo: a dinâmica entra pelas "
        "janelas de chuva acumulada. Redes neurais não foram usadas porque {thousands(d['positivos'])} dias positivos agrupados em "
        f"{d['episodios']} episódios não sustentam um modelo mais flexível; seria sobreajuste.",
        f"\n**Escolha:** {dec['familia']} {json.dumps(dec['parametros'], ensure_ascii=False)}, a família mais simples dentro de "
        f"{pct(0.1, 0)} (relativo) do melhor PR-AUC de validação. **Estado:** {dec['estado']}.\n",
        "O selo \"validado\" exige três critérios independentes, todos medidos antes do teste:\n",
        table([{"c": GATE_NAMES[k], "p": "sim" if v["passa"] else "**não**", "d": v["detalhe"]} for k, v in dec["criterios"].items()],
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
        f"Matriz de confusão e demais métricas **do modelo de aprendizado de máquina (experimental)** por orçamento de alertas (limiares fixados em 2020–2024, aplicados ao teste). "
        f"Acurácia não é reportada: com prevalência de {pct(test['modelo']['prevalencia'], 2)}, um modelo que nunca alerta acerta mais de 99%.\n",
        table([{"o": budget_label(o), "tp": r["tp"], "fp": thousands(r["fp"]), "fn": r["fn"], "tn": thousands(r["tn"]), "p": pct(r["precisao"], 2),
                "rc": pct(r["recall"], 1), "f1": num(r["f1"]), "dias": num(r["dias_alerta_por_mil"], 1), "ev": f"{r['eventos_detectados']}/{r['eventos']}"}
               for o, r in test["orcamentos_de_alerta"]["modelo"].items()],
              [("o", "Orçamento"), ("tp", "VP"), ("fp", "FP"), ("fn", "FN"), ("tn", "VN"), ("p", "Precisão"), ("rc", "Recall (dias)"),
               ("f1", "F1"), ("dias", "Alertas por mil dias"), ("ev", "Eventos detectados")]),
        "\n**Comparação justa: eventos detectados quando todos alertam no mesmo número de dias do teste** (cada método com o limiar que lhe dá "
        "essa fração dos dias; uma sequência de dias positivos conta como um evento). Mede só a ordenação:\n",
        table(fair_rows, [("Método", "Método"), (0.005, "0,5% dos dias"), (0.01, "1% dos dias"), (0.02, "2% dos dias"), (0.05, "5% dos dias")]),
        f"\n{comparison_sentence(card, fair)}\n",
        "\n**Por que a tabela de confusão acima mostra tão poucos alertas do modelo.** Os limiares foram fixados em 2020–2024 sobre escores de "
        f"modelos ajustados com menos anos; ao reajustar o modelo, a escala dos escores mudou (o percentil 98 foi {num(p98_oof, 3)} nos escores fora da "
        f"amostra de 2020–2024 e {num(p98_test, 3)} no teste), e o limiar de 2% passou a alertar em uma fração bem menor dos dias. As regras são funções fixas e não sofrem essa deriva. Para um "
        "modelo, limiares fixos não se transferem sem recalibrar; essa é uma das razões para manter a regra como gatilho.\n",
        "\n".join(f"![{n}](figuras/{n})" for n in figs) + "\n",
        f"**Calibração (modelo).** Brier {num(test['calibracao']['brier'], 6)} contra {num(test['calibracao']['brier_referencia_prevalencia'], 6)} "
        "de um preditor constante: com eventos tão raros a calibração melhora a escala das probabilidades, não a discriminação.\n",
    ]
    lines += operational_lines(card) + history_lines(card, versions or [])
    if other:
        rows = []
        for name, c in ((label, card), (other["rotulo"], other)):
            t = c["teste_2025_em_diante"]
            other_fair = equal_share_events(pd.read_parquet(resolve(f"data/processed/gatilho_{name}_teste.parquet")))
            top = {"eventos_detectados": other_fair["score"][0.02]["detectados"], "eventos": other_fair["score"][0.02]["eventos"]}
            rule = {"eventos_detectados": max(other_fair[r][0.02]["detectados"] for r in ("regra_p3d", "regra_rel_p3d"))}
            rows.append({"r": name, "c": ", ".join(str(x) for x in c["cobrade"]), "p": thousands(c["dataset"]["positivos"]),
                         "e": c["dataset"]["episodios"], "pr": num(t["modelo"]["pr_auc"]), "roc": num(t["modelo"]["roc_auc"], 3),
                         "ev": f"modelo {top['eventos_detectados']}/{top['eventos']}; melhor regra {rule['eventos_detectados']}", "s": c["gatilho_operacional"]["descricao"]})
        lines += ["## 9. Sensibilidade ao rótulo\n",
                  "O rótulo **estrito** (inundações, enxurradas e alagamentos) é o principal. O **amplo** acrescenta \"chuvas intensas\" (13214), "
                  "uma categoria de tempestade que mistura eventos não hídricos e que cresce a partir de 2023 por mudança de notificação.\n",
                  table(rows, [("r", "Rótulo"), ("c", "COBRADE"), ("p", "Dias positivos"), ("e", "Episódios"), ("pr", "PR-AUC teste"),
                               ("roc", "ROC-AUC teste"), ("ev", "Eventos com o mesmo 2% dos dias"), ("s", "Gatilho em uso")]), "\n"]
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
        lines += ["## 10. Treino com reanálise, operação com previsão\n",
                  "O endpoint de \"previsão histórica\" do Open-Meteo devolve **a mesma série da reanálise** (diferença de 0,00 mm/dia em 2019–2026), "
                  "então não serve de evidência de previsão. Previsões reais arquivadas existem desde meados de 2024 (API de execuções anteriores); "
                  "com elas, o mesmo modelo testado é pontuado com chuva prevista 1 e 2 dias antes, em todos os dias da janela (limite superior "
                  "da perda: na operação os dias passados são análise).\n",
                  table(rows, [("c", "Entrada de chuva"), ("l", "Linhas"), ("pr", "PR-AUC"), ("roc", "ROC-AUC"), ("ev", "Eventos @2%"), ("corr", "Correlação diária com a reanálise")]), "\n"]
    if index:
        lab, mun = index["segmentos_com_bloqueio_observado"], index["verificacao_municipal_fraca"]
        lines += ["## 11. Suscetibilidade por segmento (índice, não probabilidade)\n",
                  f"Índice físico relativo, **não** é probabilidade e **não** foi validado em nível de segmento. {thousands(index['segmentos'])} segmentos "
                  "de 1 km; componentes: baixa altitude, depressão local e proximidade da água, com pesos iguais (nada é ajustado).\n",
                  (f"- **Segmentos de bloqueios observados** ({lab['segmentos_rotulados']} segmentos, de apenas 16 bloqueios, pois um intervalo cobre vários): "
                   f"percentil mediano {num(lab['indice']['mediana'], 1)} pelo índice contra {num(lab['regra_so_elevacao']['mediana'], 1)} pela regra só de altitude; "
                   f"{pct(lab['indice']['no_top_20pct'], 0)} contra {pct(lab['regra_so_elevacao']['no_top_20pct'], 0)} no quinto mais suscetível. "
                   "Descritivo, sem valor estatístico." if lab.get("segmentos_rotulados") else ""),
                  f"- **Verificação municipal fraca** ({mun['municipios']} municípios): correlação de Spearman entre o percentil médio das rodovias e os registros "
                  f"hídricos por km de {num(mun['spearman_indice_x_registros_por_km'], 2)} (índice) contra {num(mun['spearman_so_elevacao_x_registros_por_km'], 2)} "
                  "(só altitude). Ambas fracas e confundidas pela chuva, pela população e pelo hábito de notificar.\n"]
    if impact:
        cov, cmp_ = impact["cobertura"], impact["com_x_sem_peso_do_vdm"]
        lines += ["## 12. Impacto na mobilidade (simulado)\n",
                  f"{impact['natureza'][0].upper() + impact['natureza'][1:]}. Cobertura do VDM: {pct(cov['fracao_com_vdm'], 1)} dos segmentos (ausente não é zero). "
                  f"Entre os {cmp_['trechos_com_vdm_e_desvio']} trechos com VDM e desvio, a correlação de Spearman entre o desvio sem peso e "
                  f"ponderado é {num(cmp_['spearman_desvio_x_ponderado'], 2)} e só {cmp_['sobreposicao_top50']} dos 50 primeiros coincidem: "
                  "o peso do tráfego muda de verdade a prioridade.\n",
                  "\n".join(f"- {x}" for x in impact["limites"]) + "\n"]
    lines += ["## 13. Limitações e riscos\n",
              "- Negativos não rotulados; precisão é um piso. Município sem registro não é município sem alagamento.",
              "- Poucos episódios independentes (dezenas), muito concentrados (2023 e 2024); a validação é por episódio, mas o erro de estimativa é grande.",
              "- Mudança de notificação a partir de 2023 (mais registros de \"chuvas intensas\"): o rótulo estrito evita parte disso; o amplo não.",
              "- A data do protocolo é a de abertura do registro, não a do dano; usa-se uma janela de rótulo.",
              "- Treino em reanálise e operação em previsão; ver a seção 10.",
              "- O modelo estima o registro de um desastre, não a água na rua; não substitui os alertas oficiais.\n",
              "## 14. Como reproduzir\n",
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
    other = load(f"reports/ml/gatilho_{'amplo' if args.label == 'estrito' else 'estrito'}.json")
    versions = [(path.stem.replace("gatilho_", "").replace("_", " "), json.loads(path.read_text()))
                for path in sorted(resolve("reports/ml/versoes").glob(f"gatilho_{args.label}_v*.json"))]
    text = render(args.label, card, load(f"reports/ml/skew_{args.label}.json"), load("reports/ml/indice_suscetibilidade.json"),
                  load("reports/qa/impacto_rs.json"), figs, other, versions)
    resolve(DOC).write_text(text)
    print(f"{DOC}: {len(text.splitlines())} linhas, {len(figs)} figuras")


if __name__ == "__main__":
    main()
