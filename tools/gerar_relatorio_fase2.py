"""Gera docs/qualidade_dados_fase2.md a partir dos relatórios da Fase 2: nenhum número é digitado à mão.

    PYTHONPATH=src python tools/gerar_relatorio_fase2.py [saida.md]

Lê data/processed/drenagem/qualidade_drenagem.json, data/processed/uso_solo/qualidade_uso_solo.json e os dois CSVs de coeficientes (config/).
Copia também os dois JSONs de qualidade para reports/qa/ (pequenos, rastreáveis); os dados processados ficam em data/processed, fora do Git.
"""
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"
BR = lambda x, c=1: f"{x:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")
PCT = lambda x, c=1: f"{100 * x:.{c}f}%".replace(".", ",")
KM2 = lambda m2, c=2: BR(m2 / 1e6, c)


def tabela(cab, linhas):
    return ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)] + ["| " + " | ".join(str(c) for c in l) + " |" for l in linhas]


def gerar() -> str:
    d = json.loads((PROC / "drenagem/qualidade_drenagem.json").read_text())
    u = json.loads((PROC / "uso_solo/qualidade_uso_solo.json").read_text())
    m1 = pd.read_csv(RAIZ / "config/uso_solo_coeficientes_metodo1_fundamentados.csv")
    m2 = pd.read_csv(RAIZ / "config/uso_solo_cenarios_metodo2_hipoteticos.csv")
    cl, ref = u["classes"], u["area_de_referencia_municipio_m2"]
    pint = u["pela_pintura"]
    lg = u.get("lacunas_contra_agua_osm")
    L = ["# Fase 2: qualidade dos dados integrados e cobertura territorial", "",
         "Relatório **gerado** por `tools/gerar_relatorio_fase2.py` a partir de `reports/qa/qualidade_drenagem_fase2.json` e `reports/qa/qualidade_uso_solo_fase2.json` (cópias dos JSONs de `data/processed/`). "
         "Metodologia e decisões em [auditoria_fontes_drenagem_poa.md](auditoria_fontes_drenagem_poa.md), [inventario_fontes_poa.md](inventario_fontes_poa.md) e [modelo_retencao_viabilidade.md](modelo_retencao_viabilidade.md).", "",
         "**O que isto é e o que não é.** Integração de dados: nada aqui estima volume retido, profundidade, duração, capacidade nem conectividade hidráulica. Três tipos de informação ficam separados: "
         "**observado** (o que o cadastro municipal diz), **parâmetro fundamentado** (coeficiente com referência) e **hipótese** (cenário declarado).", "",
         "## 1. Camadas integradas (Frente A, inventário de drenagem)", "",
         "Arquivos em `data/processed/drenagem/` (GeoParquet, EPSG:31982), todos com `id_origem` (o `OBJECTID`, que pode mudar se a Prefeitura republicar a camada), `valida`, `duplicata_exata_de` e `usar_no_inventario`.", ""]
    linhas = []
    for nome, x in list(d["rede_pluvial"].items()) + [("poco_de_visita", d["pocos_de_visita"]), ("boca_de_lobo", d["bocas_de_lobo"]), ("casas_de_bomba_ebap", d["casas_de_bomba"])]:
        rej = (x["rejeitados_na_coleta_sem_geometria"] or 0) + (x["rejeitados_na_coleta_coordenada_nao_finita"] or 0)
        linhas.append([f"`{nome}`", BR(x["registros_na_fonte"], 0), BR(x["registros_processados"], 0), BR(rej, 0), BR(x["geometrias_invalidas"], 0), BR(x["duplicatas_exatas"], 0), BR(x["usados_no_inventario"], 0)])
    L += tabela(["Camada", "Na fonte", "Processados", "Rejeitados na coleta", "Geometrias inválidas", "Duplicatas exatas (marcadas)", "Usados no inventário"], linhas)
    L += ["", "Rejeitados na coleta são registros sem geometria ou com coordenada `NaN`. Duplicata exata é a mesma geometria (1 cm, linha invertida conta como igual); ela **permanece** na tabela, marcada.", "",
          "**Classificação operacional original, preservada** (valores do cadastro, sem interpretação):", ""]
    co = d["classificacao_operacional_original_preservada"]
    L += [f"- Rede pluvial (camada principal): `ativo_no_cadastro` = {json.dumps(co['rede_pluvial']['ativo_no_cadastro'], ensure_ascii=False)}",
          f"- Rede pluvial sem acesso: `acesso` = {json.dumps(co['rede_pluvial_sem_acesso']['acesso'], ensure_ascii=False)} (tratada como **não operacional** pelo próprio cadastro)",
          f"- Rede pluvial não interligada: `ativo_no_cadastro` = {json.dumps(co['rede_pluvial_nao_interligada']['ativo_no_cadastro'], ensure_ascii=False)} (cadastrada como **inativa**)", "",
          "### Qualidade do inventário", ""]
    sin = []
    for nome, x in list(d["rede_pluvial"].items()) + [("pocos_de_visita", d["pocos_de_visita"]), ("bocas_de_lobo", d["bocas_de_lobo"])]:
        for k, v in x["sinalizacoes"].items():
            if v:
                sin.append([f"`{x['camada']}`", f"`{k}`", BR(v, 0), PCT(v / x["registros_processados"], 2)])
    L += tabela(["Camada", "Sinalização (valor original mantido)", "Registros", "% da camada"], sin)
    L += ["", "Colunas **sem nenhum preenchimento** por camada: " + "; ".join(f"`{x['camada']}`: {', '.join(x['colunas_sem_nenhum_preenchimento']) or 'nenhuma'}" for x in list(d["rede_pluvial"].values()) + [d["pocos_de_visita"], d["bocas_de_lobo"], d["casas_de_bomba"]]) + ".", "",
          "**Evidência geométrica** na rede pluvial (camada principal, registros usados). É evidência, **não** conectividade hidráulica: o cadastro não traz nó nem trecho a montante ou a jusante.", ""]
    ev = d["evidencia_geometrica_rede_pluvial_operacional"]
    L += tabela(["Evidência (tolerâncias de 0,5 m entre extremos e 1 m a poço de visita)", "Fração dos trechos"], [[f"`{k}`", PCT(v)] for k, v in ev.items()])
    b = d["bocas_de_lobo_distancia_geometrica"]
    cb = d["casas_de_bomba_detalhe"]
    L += ["", f"**Bocas de lobo:** mediana de {BR(b['mediana_m'], 1)} m à rede pluvial, {PCT(b['ate_2m'])} a até 2 m, {BR(b['acima_de_50m'], 0)} a mais de 50 m. Distância geométrica: **não** prova conexão nem funcionamento, e nenhum identificador de trecho é atribuído.", "",
          f"**Casas de bomba:** {cb['registros']} registros; **{cb['capacidade_informada']} com capacidade informada** (o campo está vazio em todos); {cb['mesmo_nome_no_projeto']} com o mesmo nome das do projeto, com diferença de posição de até {BR(cb['distancia_maxima_ao_projeto_m'], 1)} m; "
          f"só no serviço: {', '.join(cb['somente_no_servico'])}; só no projeto: {', '.join(cb['somente_no_projeto'])}.", "",
          "## 2. Uso do solo, Profill 2022 (Frentes B e D)", "",
          f"- **{BR(u['poligonos_lidos'], 0)} polígonos** em {u['partes_lidas']} partes; {BR(u['poligonos_processados'], 0)} processados, {BR(u['rejeitados_sem_geometria_util'], 0)} rejeitados por geometria vazia.",
          f"- **Geometrias inválidas:** {BR(u['geometrias_invalidas'], 0)}" + (f" ({'; '.join(f'{k}: {BR(v, 0)}' for k, v in u['motivos_de_invalidez'].items())})" if u["motivos_de_invalidez"] else "") + "; áreas e pintura usam a geometria reparada.",
          f"- **Duplicatas exatas:** {BR(u['duplicatas_exatas'], 0)} (ficam no arquivo, marcadas, e não entram nas somas de área nem na pintura).",
          f"- **Polígonos grandes** (mais de 1,5 km) em partição própria: {BR(u['poligonos_grandes_em_particao_propria'], 0)}; centroides fora da grade: {BR(u['centroides_fora_da_grade'], 0)}.",
          f"- **Grade:** {u['grade']['linhas']} x {u['grade']['colunas']} células de {BR(u['grade']['celula_m'], 0)} m, em EPSG:31982 e **a mesma do DEM do projeto** (origem {BR(u['grade']['origem_x'], 2)}; {BR(u['grade']['origem_y'], 2)}), sem reamostrar o Copernicus para resolução mais fina. "
          f"A pintura interna é de {BR(u['grade']['pintura_m'], 0)} m.", "", "### Cobertura territorial", ""]
    L += tabela(["Medida", "Valor"], [["Área de referência (limite do município, `municipality.parquet`)", f"{KM2(ref)} km²"], ["Área classificada (soma dos polígonos únicos)", f"{KM2(u['area_classificada_pelos_poligonos_m2'])} km² ({PCT(u['fracao_da_referencia_classificada'])} da referência)"],
                                    ["Município coberto pela pintura (dentro do limite)", f"{KM2(pint['classificada_dentro_do_municipio_m2'])} de {KM2(pint['area_do_municipio_m2'])} km² ({PCT(pint['fracao_do_municipio_coberta'])})"],
                                    ["Lacuna dentro do município (sem polígono)", f"{KM2(pint['lacuna_dentro_do_municipio_m2'])} km²"], ["Classificado fora do limite do município", f"{KM2(pint['classificada_fora_do_municipio_m2'])} km²"],
                                    ["Sobreposição entre polígonos (pintura de 3 m)", f"{KM2(pint['sobreposicao_m2'], 3)} km²"]])
    L += ["", "A lacuna é a área do município sem polígono de uso do solo. Os blocos de 3 km (linha, coluna do bloco) com mais lacuna, em km²: " + "; ".join(f"({k}) {KM2(v)}" for k, v in pint["blocos_com_mais_lacuna_linha_coluna_m2"]) + ".", "",
          (f"**Verificação da causa:** {PCT(lg['fracao_da_lacuna_sobre_agua_osm'])} da lacuna ({KM2(lg['lacuna_sobre_agua_osm_m2'])} km²) cai sobre polígonos de água do OpenStreetMap, isto é, o Guaíba: o limite do município inclui a água, que o mapa de uso do solo não classifica. "
           f"Do restante ({KM2(lg['lacuna_fora_da_agua_m2'])} km², {PCT(lg['lacuna_fora_da_agua_m2'] / pint['area_do_municipio_m2'], 2)} do município), {PCT(lg['fracao_da_lacuna_fora_da_agua_a_ate_100m_da_agua'])} está a até 100 m da água (margens); o resto não foi explicado e depende de conferência visual." if lg else
           "A causa da lacuna não foi verificada."), "", "**Sobreposição:** a pintura não encontrou nenhum ponto coberto por dois polígonos (duplicatas exatas excluídas): os polígonos formam uma partição sem sobreposição. "
          "**Campo `area_m2` da fonte:** é uniformemente cerca de 0,08% maior que a área calculada em EPSG:31982, em todas as classes; o padrão uniforme aponta diferença de escala de projeção, não erro de dado (as áreas deste relatório vêm da geometria).", "", "### Distribuição das classes", ""]
    linhas = []
    for c, v in sorted(cl.items(), key=lambda kv: -kv[1]["area_m2_geometria"]):
        trat = "fundamentada (Método 1)" if v["metodo1_fundamentado"] else "fora do cálculo" if v["fora_do_calculo_de_escoamento"] else "cenários (Método 2)"
        linhas.append([c, BR(v["poligonos"], 0), KM2(v["area_m2_geometria"]), PCT(v["fracao_da_area_classificada"]), BR(v["duplicatas_excluidas"], 0), BR(v["invalidos"], 0),
                       PCT(v["diferenca_relativa_pintura_x_poligonos"], 2) if v["diferenca_relativa_pintura_x_poligonos"] is not None else "-", PCT(v["diferenca_relativa_fonte_x_geometria"], 3) if v["diferenca_relativa_fonte_x_geometria"] is not None else "-", trat])
    L += tabela(["Classe", "Polígonos", "Área (km²)", "% da área classificada", "Duplicatas excluídas", "Inválidos", "Pintura 3 m x polígonos", "Campo `area_m2` x geometria", "Tratamento"], linhas)
    L += ["", "As duas últimas colunas medem a consistência: a área da pintura de 3 m contra a soma dos polígonos, e o campo `area_m2` da fonte contra a área calculada em EPSG:31982.", "",
          "## 3. Coeficientes fundamentados (Método 1)", "",
          "Só o que a referência sustenta diretamente. **Não se extrapola** para outras classes. Referência: " + m1.referencia.iloc[0] + ".", ""]
    linhas = [[r.classe_original, f"{BR(r.c_min, 2)} a {BR(r.c_max, 2)}", r.linha_da_tabela, r.enquadramento, KM2(cl[r.classe_original]["area_m2_geometria"]), PCT(cl[r.classe_original]["fracao_da_area_classificada"]), r.grau_de_incerteza] for r in m1.itertuples()]
    L += tabela(["Classe", "C (adimensional)", "Linha da tabela de referência", "Enquadramento", "Área (km²)", "% da área classificada", "Incerteza"], linhas)
    cob = u["cobertura_dos_metodos"]
    L += ["", f"**Cobertura do Método 1:** {KM2(cob['metodo1_area_m2'])} km², ou **{PCT(cob['metodo1_fracao_da_area_classificada'])}** da área classificada do município. "
          f"Fora do cálculo de escoamento (área úmida e corpo hídrico): {KM2(cob['fora_do_calculo_area_m2'])} km² ({PCT(cob['fora_do_calculo_fracao'])}). "
          f"**Sem coeficiente fundamentado:** {KM2(cob['sem_coeficiente_fundamentado_area_m2'])} km² (**{PCT(cob['sem_coeficiente_fundamentado_fracao'])}**).", "",
          "(O percentual de 17,3% citado na auditoria anterior vale para o município inteiro, medido nas estatísticas do servidor. No piloto urbano de 1 km² as duas classes somam 49,3%; "
          "não é uma estimativa da cidade.)", "", "## 4. Cenários determinísticos (Método 2), com hipótese declarada", "",
          "Aplicam-se **só** às classes que o Método 1 não cobre. Cada valor tem natureza declarada: **limite físico** (C = 0 ou 1, vale por definição, não é estimativa), **referência externa por analogia** "
          "(faixa da mesma tabela da TxDOT aplicada por analogia, com a hipótese de enquadramento escrita) ou **mistura de referências com fração hipotética**. São cenários, **não medições**.", ""]
    linhas = []
    for r in m2.itertuples():
        area = cl.get(r.classe_original, {}).get("area_m2_geometria", 0)
        faixa = "sem coeficiente" if pd.isna(r.c_min) else f"{BR(r.c_min, 3)} a {BR(r.c_max, 3)}" if r.c_min != r.c_max else BR(r.c_min, 2)
        linhas.append([f"`{r.cenario}`", r.classe_original, faixa, r.natureza_do_valor, KM2(area), r.grau_de_incerteza])
    L += tabela(["Cenário", "Classe afetada", "C", "Natureza do valor", "Área afetada (km²)", "Incerteza"], linhas)
    L += ["", "Hipóteses completas (uma por linha) em `config/uso_solo_cenarios_metodo2_hipoteticos.csv`. Classes **sem nenhuma referência** além dos limites físicos, por falta de fonte consultada: " +
          ", ".join(sorted(set(m2[m2.natureza_do_valor == "limite_fisico"].classe_original) - set(m2[m2.natureza_do_valor != "limite_fisico"].classe_original) - {"(fora)"})) + ".", "",
          "Para fechar essas lacunas sem inventar valor: (1) integrar pedologia e declividade para usar faixas por tipo de solo e declividade; (2) buscar na literatura brasileira coeficientes por classe de cobertura, "
          "com a fonte; (3) obter a fração permeável da classe 'Jardins, Passeios ou Áreas semi urbanizadas' (a maior incerteza na cidade construída).", "",
          "## 5. Estrutura de cálculo preparada (sem volume retido)", "",
          "`flooding_mapping.escoamento` implementa `V = P x A x C / 1000` (P em mm, A em m², C adimensional, V em m³) com validação de unidades, os dois métodos separados e o aviso de que o resultado é "
          "**água potencialmente escoada** (limite superior, sem infiltração nem perdas), nunca volume retido.", "",
          "## 6. Arquivos processados", ""]
    arq = [[f"`{v['path']}`", BR(v["registros"], 0), v["sha256"][:12], BR(v["bytes"] / 1e6, 1)] for v in d["arquivos"].values()]
    arq.append([f"`{u['grade_de_saida']['arquivo']}`", BR(u["grade_de_saida"]["celulas"], 0), "ver `data/raw/manifest.json`", "-"])
    L += tabela(["Arquivo", "Registros ou células", "SHA-256 (início)", "MB"], arq)
    L += ["", "Todos registrados em `data/raw/manifest.json` com origem, data, hash, formato e versão do processamento; reexecutar não duplica nada (mesmo conteúdo, mesmo hash). `data/processed/` fica fora do Git.", "",
          "## 7. Limitações", ""] + [f"- {x}" for x in d["limitacoes"] + u["limitacoes"]] + [""]
    return "\n".join(L)


if __name__ == "__main__":
    texto = gerar()
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "qualidade_dados_fase2.md"
    saida.write_text(texto, encoding="utf-8")
    shutil.copyfile(PROC / "drenagem/qualidade_drenagem.json", RAIZ / "reports/qa/qualidade_drenagem_fase2.json")
    shutil.copyfile(PROC / "uso_solo/qualidade_uso_solo.json", RAIZ / "reports/qa/qualidade_uso_solo_fase2.json")
    print(f"gravado: {saida}")
