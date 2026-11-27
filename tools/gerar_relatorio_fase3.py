"""Gera docs/fase3_resultados.md a partir de reports/qa/fase3_execucao.json: nenhum número é digitado à mão.

    PYTHONPATH=src python tools/gerar_relatorio_fase3.py [saida.md]
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BR = lambda x, c=1: f"{x:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")
PCT = lambda x, c=1: f"{100 * x:.{c}f}%".replace(".", ",")
NOME_PACOTE = {"metodo1": "Método 1 (fundamentado)", "limites_fisicos": "Limites físicos (C = 0 a 1)", "referencia_analoga": "Referência por analogia (hipótese)"}


def tabela(cab, linhas):
    return ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)] + ["| " + " | ".join(str(c) for c in l) + " |" for l in linhas]


def gerar() -> str:
    r = json.loads((RAIZ / "reports/qa/fase3_execucao.json").read_text())
    m, v, d, pg = r["motor"], r["verificacoes_do_nucleo"], r["descricao"], r["pegadas_dos_trechos"]
    L = ["# Fase 3: resultados da execução", "",
         "Relatório **gerado** por `tools/gerar_relatorio_fase3.py` a partir de `reports/qa/fase3_execucao.json`. Método, equações, hipóteses e limites em [fase3_motor.md](fase3_motor.md). "
         "Chuva uniforme e **hipotética** (10, 20 e 30 mm): são cenários, não previsões.", "",
         "**Leia assim.** Os volumes são **água potencialmente escoada** (limite superior, sem infiltração nem perdas), em intervalos. **Não** são volume retido, profundidade, duração nem volume efetivamente transportado, "
         "que o motor não calcula. Os três pacotes de coeficientes **não se somam**.", "",
         "## 1. Verificações do núcleo", ""]
    L += tabela(["Verificação", "Resultado"], [
        ["Acúmulo com peso 1 idêntico a `susceptibility.flow_accumulation` do projeto, no DEM real", f"{'sim' if v['acumulo_com_peso_1_identico_a_susceptibility_flow_accumulation'] else 'NÃO'} ({BR(v['celulas_comparadas'], 0)} células)"],
        ["Conservação de massa (gerado = saída pelos exutórios), erro relativo máximo em 13 colunas", f"{v['conservacao_de_massa_erro_relativo_maximo']:.1e}"],
        ["Células com dados na grade de 30 m", BR(m["celulas_com_dados"], 0)], ["Exutórios (células sem receptor)", BR(m["exutorios"], 0)],
        ["Células de corpo d'água grande tratadas como exutório", f"{BR(m['celulas_mascaradas_como_exutorio'], 0)} ({BR(m['celulas_mascaradas_como_exutorio'] * 900 / 1e6, 1)} km²)"]])
    L += ["", "## 2. Trechos viários", "",
          f"- {BR(pg['trechos'], 0)} trechos; **{BR(pg['com_celulas_com_dados'], 0)}** com ao menos uma célula com dados na pegada.",
          f"- {BR(pg['fora_da_grade_sem_nenhuma_celula'], 0)} ficam fora da grade (sem nenhuma célula) e {BR(pg['so_em_celulas_sem_dado_ou_agua_mascarada'], 0)} só em células sem dado ou de água mascarada: recebem valor **ausente**, nunca zero.",
          f"- Mediana de {BR(m['celulas_da_pegada_por_trecho_mediana'], 0)} células por pegada.", "",
          "## 3. Total da cidade (soma das células, cada célula uma vez)", "", "Em m³, mínimo a máximo. O total existe só como soma das células: **valores por trecho não são somáveis**, porque as bacias de trechos vizinhos se sobrepõem.", ""]
    linhas = []
    for p, x in m["totais_da_cidade_soma_das_celulas_m3"].items():
        for pk, t in x.items():
            linhas.append([f"{p} mm", NOME_PACOTE[pk], f"{BR(t['min_m3'], 0)} a {BR(t['max_m3'], 0)}"])
    L += tabela(["Chuva (hipotética)", "Pacote", "Água potencialmente escoada (m³)"], linhas)
    L += ["", "O Método 1 cobre só edificação e via pavimentada (17,3% da área classificada). Os limites físicos (C = 0 a 1) são o envelope trivial que vale por definição; a referência por analogia é hipótese declarada, com Jardins sempre como envelope dos cenários de fração.", "",
          "## 4. Valores por trecho com chuva de 30 mm (quantis entre os trechos, em m³, limite superior de cada pacote)", ""]
    linhas = []
    for pk, x in d["nivel2_p30"].items():
        for c, nome in (("v_gerado_local_max_m3", "Volume potencial gerado (local)"), ("contrib_potencial_max_m3", "Contribuição potencial associada ao trecho")):
            q = x[c]
            linhas.append([NOME_PACOTE[pk], nome, BR(q["q50"], 1), BR(q["q90"], 1), BR(q["q99"], 0)])
    L += tabela(["Pacote", "Grandeza", "Mediana", "Percentil 90", "Percentil 99"], linhas)
    f = d["fracoes_a_montante_medianas"]
    L += ["", "### Cobertura a montante (o grau de confiança), mediana entre os trechos", "",
          f"Da área a montante de um trecho típico: **{PCT(f['fracao_montante_coberta_m1'])}** tem coeficiente fundamentado (Método 1), {PCT(f['fracao_montante_com_valor_analoga'])} tem valor por analogia e **{PCT(f['fracao_montante_sem_valor_analoga'])}** fica sem valor nesse pacote; "
          f"{PCT(f['fracao_montante_fora_do_calculo'])} é fora do cálculo e {PCT(f['fracao_montante_sem_classe'])} é sem classe. Cada trecho traz as suas frações em `trechos_contribuicao_base.parquet`; um trecho cuja área a montante é quase toda sem valor não deve ser lido como estimativa.", "",
          "## 5. Indicador topográfico (Nível 1)", "", f"Altura de preenchimento de depressões na pegada: **{BR(d['nivel1']['trechos_com_preenchimento_zero'], 0)}** dos {BR(d['nivel1']['trechos_com_valor'], 0)} trechos com dados ({PCT(d['nivel1']['trechos_com_preenchimento_zero'] / d['nivel1']['trechos_com_valor'])}) têm "
          f"preenchimento zero; entre os trechos, mediana {BR(d['nivel1']['altura_de_preenchimento_max_m_quantis']['q50'], 2)} m, percentil 90 {BR(d['nivel1']['altura_de_preenchimento_max_m_quantis']['q90'], 2)} m e percentil 99 {BR(d['nivel1']['altura_de_preenchimento_max_m_quantis']['q99'], 2)} m. "
          "Com o Copernicus (DSM de 30 m, erro médio de 2,18 m) a altura **não é interpretável em metros**, nem como volume ou profundidade: só o posto (`propensao_topografica_percentil`) serve, como índice relativo. "
          "Como a maioria dos trechos tem preenchimento zero, o posto só discrimina entre os que têm algum preenchimento.", "",
          "## 6. Comparação exploratória com os registros de alagamento de 2013 a 2014", ""]
    c = r["comparacao_exploratoria_com_os_registros"]
    L += [f"Mesma amostra do experimento de sensibilidade: {BR(c['amostra_do_experimento_anterior']['trechos'], 0)} trechos, **{c['amostra_do_experimento_anterior']['positivos']} positivos** ({BR(c['segmentos_comparados'], 0)} com valor no motor, {c['positivos_com_valor']} positivos); taxa base {PCT(c['taxa_base'], 3)}. "
          f"Critério: {c['criterio']}.", ""]
    linhas = []
    for nome, x in c["metricas"].items():
        g = x.get("ganho_sobre_a_regra")
        linhas.append([f"`{nome}`", BR(x["auc"], 3), BR(x["precisao_media"], 5), "referência" if g is None else f"{100 * g:+.1f}%".replace(".", ","),
                       "" if g is None else f"{100 * x['ic95_ganho_por_trecho'][0]:+.0f}% a {100 * x['ic95_ganho_por_trecho'][1]:+.0f}%", "" if g is None else f"{100 * x['ic95_ganho_por_blocos_completos'][0]:+.0f}% a {100 * x['ic95_ganho_por_blocos_completos'][1]:+.0f}%",
                       "" if g is None else "sim" if x["atende_criterio"] else "não"])
    L += tabela(["Candidato", "AUC", "Precisão média", "Ganho vs. regra", "IC95 (trechos)", "IC95 (blocos completos)", "Atende o critério"], linhas)
    L += ["", c["leitura"], "", "**Sobreposição qualitativa com o risco CPRM** (contexto, nunca rótulo). Percentil mediano da contribuição do Método 1 entre os trechos de cada classe de risco mapeado:", ""]
    cp = r["sobreposicao_qualitativa_com_cprm"]
    L += tabela(["Classe do CPRM", "Trechos", "Percentil mediano da contribuição (Método 1, máximo)"], [[k, BR(x["segmentos"], 0), BR(x["percentil_mediano_da_contribuicao_m1_max"], 1) if x["percentil_mediano_da_contribuicao_m1_max"] is not None else "-"] for k, x in cp["por_classe"].items()])
    L += ["", cp["leitura"], "", "## 7. Arquivos gerados (`data/processed/fase3/`, fora do Git)", ""]
    L += tabela(["Arquivo", "Linhas", "MB", "SHA-256 (início)"], [[f"`{a['path']}`", BR(a["linhas"], 0), BR(a["bytes"] / 1e6, 1), a["sha256"][:12]] for a in r["arquivos"].values()])
    L += ["", "Todos registrados em `data/raw/manifest.json`, com os hashes das entradas.", "", "## 8. Não calculado", ""] + [f"- **{k.replace('_', ' ')}:** {x}" for k, x in m["nao_calculado"].items()]
    L += ["", "## 9. Limitações", ""] + [f"- {x}" for x in r["limitacoes"]] + [""]
    return "\n".join(L)


if __name__ == "__main__":
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "fase3_resultados.md"
    saida.write_text(gerar(), encoding="utf-8")
    print(f"gravado: {saida}")
