# -*- coding: utf-8 -*-
"""Gera a apresentação curta do capstone sobre o template oficial do Future Tech Leaders, e o roteiro em Markdown.

    python tools/gerar_apresentacao_ftl.py <template.pptx> [saida.pptx]

O template não é versionado (documentos de escritório ficam fora do Git). Ferramenta só de escritório: precisa de python-pptx e pillow,
que não fazem parte dos requisitos do produto. Figuras: docs/figuras (capturas reais, figuras do pipeline e os esquemas de
tools/gerar_figuras_apresentacao.py). Capturas com dados da demonstração levam a etiqueta SINTÉTICO.
Grava também docs/roteiro_apresentacao_curta.md com o texto de cada slide e a fala, a partir da mesma lista (SLIDES).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.util import Emu, Pt

RAIZ = Path(__file__).resolve().parents[1]
FIG = RAIZ / "docs" / "figuras"
SAIDA_PADRAO = RAIZ / "docs" / "apresentacao" / "Flooding_Mapping_Capstone_FTL.pptx"
ROTEIRO = RAIZ / "docs" / "roteiro_apresentacao_curta.md"
ALERTA, MUDO = RGBColor(0xB3, 0x20, 0x2A), RGBColor(0x5A, 0x68, 0x72)

# Colunas do template (EMU): texto à esquerda, figura à direita; ou texto curto no alto e figura larga embaixo.
TX, TY, TW = 640_854, 2_951_018, 8_007_631
DIR = dict(x=8_650_000, y=1_550_000, w=3_450_000, h=4_950_000)

# fig: (arquivo, posição, legenda, sintético). posição: "dir" (coluna direita), "baixo" (faixa larga), ou (x, y, w, h)
SLIDES = [
    dict(titulo="Por que isto importa para Porto Alegre", tam=17,
         texto=[
             "Chuva comum já fecha ruas na cidade: o menor acumulado em 24 h associado a bloqueios da EPTC é 26,2 mm, e isso se repete em média 14 dias por ano.",
             "Falta um número para decidir: quanto acesso a cidade perde quando isso acontece, e onde. Sem ele, desvios, alertas e obras ficam sem medida.",
         ],
         figs=[("apresentacao_numeros_chave.png", (700_000, 4_050_000, 10_800_000, 2_500_000), None, False)],
         fala="Porto Alegre sabe que alaga. O que a cidade não tem é uma medida de quanto isso custa em deslocamento. O menor acumulado de chuva em 24 horas que já coincidiu com bloqueios registrados pela EPTC é 26,2 milímetros, e, pela reanálise de 2015 a 2024, esse nível é igualado ou superado em média em 14 dias por ano. Ou seja, não é só evento extremo. Quando isso acontece, quem decide um desvio, um alerta ou uma obra de drenagem faz isso sem saber quanta gente perde acesso e em quais áreas. Essa é a lacuna que o projeto ataca."),
    dict(titulo="Propósito e valor para a cidade", tam=16,
         texto=["Propósito: uma plataforma para quem mora na cidade, que mostra o que a chuva pode afetar perto de cada pessoa e aprende com o que a comunidade confirma."],
         figs=[("apresentacao_valor_por_publico.png", (1_100_000, 3_650_000, 10_000_000, 2_950_000), None, False)],
         fala="O propósito do Flooding Mapping é ser uma plataforma para o cidadão, não mais uma ferramenta de gestão. Quem sai de casa vê se as ruas ao redor dos lugares que salvou entram em exposição estimada nas próximas horas, com os hospitais e escolas que ficam dentro de cada área. Quem viu uma rua alagada diz se ainda está alagado ou se já secou, e esse apoio ajuda a priorizar onde verificar primeiro, sem interditar rua nenhuma. E quem cuida da cidade enxerga, com a mesma informação aberta, onde a perda de acesso é maior, com áreas em que chega a 79 por cento. Esse é o valor potencial do desenho; eu não validei o uso com moradores nem com órgãos"),
    dict(titulo="Como funciona: da chuva à decisão", tam=16,
         texto=["Seis etapas, cada uma dizendo o que é observado, estimado ou confirmado por gente. O apoio da comunidade nunca interdita uma via."],
         figs=[("apresentacao_fluxo_chuva_decisao.png", (700_000, 3_650_000, 10_800_000, 2_900_000), None, False)],
         fala="O caminho é este. Entram a chuva, com previsão horária e histórico, e o terreno e as ruas. Uma regra explícita define que nada fecha abaixo de 26,2 milímetros. Os trechos em exposição se juntam em áreas, que são cruzadas com 1.720 pontos de interesse do OpenStreetMap e com os lugares que a pessoa salvou. A comunidade confirma ou diz que secou, e cada confirmação vira um rótulo. Com isso o sistema aprende e sugere onde verificar primeiro, mas só troca a regra de terreno por um modelo se ele mostrar ganho em validação por blocos espaciais. É um ranking de prioridade, não uma previsão de alagamento, e nenhuma rota é apresentada como segura"),
    dict(titulo="Relação com os ODS", tam=15,
         texto=[
             "ODS 11, Cidades e comunidades sustentáveis (metas 11.2 e 11.5): quantifica a perda de acesso a deslocamentos em desastres urbanos.",
             "ODS 13, Ação contra a mudança do clima (meta 13.1): relaciona chuvas frequentes à vulnerabilidade da cidade.",
             "ODS 9, Indústria, inovação e infraestrutura (meta 9.1): aponta onde uma infraestrutura resiliente traria mais ganho de acesso.",
         ],
         figs=[("cidade_alcancavel_sem_chuva.png", "dir", "Cidade alcançável em 30 min, sem chuva (grade de 1 km)", False)],
         fala="O projeto se relaciona com três ODS. O 11, cidades sustentáveis, nas metas 11.2 e 11.5: ele mede a perda de acesso a deslocamentos em desastres urbanos. O 13, ação climática, na meta 13.1: ele relaciona chuvas frequentes à vulnerabilidade da cidade. E o 9, infraestrutura resiliente, na meta 9.1: ele indica onde uma obra traria mais ganho de acesso. A contribuição é de informação para a decisão, não uma solução de engenharia."),
    dict(titulo="Metodologia e dados", tam=15,
         texto=[
             "Dados abertos: OpenStreetMap (176 mil trechos), Censo IBGE 2022, relevo Copernicus GLO-30 (DSM de ~30 m), GTFS de Porto Alegre, bloqueios da EPTC e chuva de reanálise (grade de ~10 km).",
             "Mobilidade perdida: população alcançável em 30 min (r5py), a pé, de ônibus e de carro, com e sem trechos fechados.",
             "Trechos fechados por regra explícita: nada abaixo de 26,2 mm; acima, os bloqueios documentados e pontos de maior suscetibilidade do terreno.",
             "Avisos e laço: bolsões de exposição com 1.720 pontos de interesse do OpenStreetMap; relatos apoiados pela comunidade viram rótulos para um modelo que só substitui a regra se mostrar ganho.",
         ],
         figs=[("painel_proveniencia.png", "dir", "Tela de proveniência: o que é observado e o que é estimado", True)],
         fala="Todas as fontes são abertas: OpenStreetMap, Censo do IBGE, relevo do Copernicus, o GTFS de Porto Alegre, os bloqueios da EPTC e a chuva de reanálise, em grade de cerca de 10 quilômetros. A medida central é a população que se alcança em 30 minutos, calculada com o r5py. A mobilidade perdida é a diferença entre a cidade com e sem os trechos fechados, e os trechos fechados vêm de uma regra explícita, não de um modelo treinado. A tela de proveniência da plataforma diz, para cada informação, de onde vem e o que não se pode afirmar."),
    dict(titulo="Resultados: quanto a cidade perde", tam=15,
         texto=[
             "Abaixo de 26,2 mm: nenhum bloqueio atribuído.",
             "De 26 a 35 mm, a cidade perde 3,5% da mobilidade de carro; de 40 a 45 mm o valor dobra, para 7%, e 190 mil pessoas perdem ao menos 10% do que alcançam.",
             "A média esconde o local: em algumas áreas a perda chega a 79%.",
             "Ressalva: o ajuste chuva-bloqueios usa só 3 datas.",
         ],
         figs=[("curva_mobilidade_perdida.png", (8_450_000, 1_550_000, 3_700_000, 2_300_000), "Mobilidade perdida por faixa de chuva", False),
               ("mobilidade_perdida_mapa_45mm.png", (8_450_000, 4_100_000, 3_700_000, 2_300_000), "Perda por área, 45 mm", False)],
         fala="O resultado central: com chuva abaixo de 26,2 milímetros, nenhum bloqueio é atribuído. Entre 26 e 35 milímetros, a cidade perde 3,5 por cento da mobilidade de carro. Entre 40 e 45, o valor dobra, para 7 por cento, e 190 mil pessoas perdem ao menos 10 por cento do que alcançam. A média esconde o local: em algumas áreas a perda chega a 79 por cento, e é isso que ajuda a priorizar. A ressalva é que o ajuste entre chuva e número de bloqueios usa só três datas."),
    dict(titulo="A plataforma em uso", tam=15,
         texto=[
             "Aba Avisos: as ruas ao redor dos lugares salvos, hora a hora, e as áreas em exposição com os pontos de interesse dentro.",
             "O laço: relatos que a comunidade confirma ou diz que secaram, e áreas sugeridas para verificar, com a fonte (regra ou modelo) à vista.",
             "Privacidade: lugares enviados sem nome e sem registro; apoio guardado só como código irreversível; sem rastreamento nem notificação.",
         ],
         figs=[("../../src/flooding_mapping/app/arquivo/inicio/img/app-avisos.png", (8_550_000, 1_450_000, 1_850_000, 4_000_000), "Avisos", True),
               ("../../src/flooding_mapping/app/arquivo/inicio/img/app-mapa.png", (10_450_000, 1_450_000, 1_850_000, 4_000_000), "Área no mapa", True)],
         fala="Isso está entregue no aplicativo para o celular. A aba Avisos mostra, para os lugares que a pessoa salvou, a exposição estimada hora a hora, e as áreas em exposição com os pontos de interesse dentro delas. O laço da comunidade permite confirmar ou dizer que secou, e há uma lista de áreas sugeridas para verificar, que diz se a fonte é a regra de terreno ou o modelo aprendido. Na demonstração o modelo não superou a regra, e a tela diz isso. Os lugares vão ao servidor sem nome e sem registro, o apoio é guardado só como código irreversível, e não há rastreamento nem notificação. As telas usam chuva e relatos sintéticos e estão identificadas."),
    dict(titulo="Conclusão: valor entregue e o que falta", tam=15,
         texto=[
             "Valor entregue: uma plataforma para o cidadão, com avisos por lugar, áreas e pontos de interesse afetados, e um laço em que a comunidade confirma; a cidade ganha uma medida da perda (3,5% a 7% do carro; até 79% em áreas).",
             "Limites: o baseline detectou 4 de 19 bloqueios em algum horário do dia (2 na hora do relato); o terreno tem sinal modesto e nem o modelo treinado nem a física simplificada superaram a regra; os relatos têm o viés de quem reporta; sem teste em celular físico nem com moradores.",
             "Próximos passos: um piloto com moradores para gerar confirmações reais, chuva medida em resolução melhor que 10 km, e renda do Censo para medir equidade.",
         ],
         figs=[],
         fala="Concluindo. O valor entregue é que a cidade passa a ter uma medida: de 3,5 a 7 por cento da mobilidade de carro perdida com chuvas de até 45 milímetros, e até 79 por cento em algumas áreas, junto com uma ferramenta que leva isso à decisão. Os limites precisam ficar claros: o baseline de risco por trecho detectou 4 de 19 bloqueios em algum horário do dia, e só 2 na hora do relato, um modelo treinado não superou regras simples, e não houve teste em celular físico nem validação com os órgãos. Por isso o próximo passo é mais dados, com ocorrências georreferenciadas e chuva medida, e um piloto com a Defesa Civil e a EPTC. Obrigada."),
]


def _relatorios() -> dict:
    """Os números dos slides de validação vêm dos relatórios finais, nunca digitados: sem eles, a geração para."""
    import json
    arquivos = {"sens": "reports/qa/sensibilidade_hidrologica.json", "rob": "reports/qa/robustez_espacial.json", "alt": "reports/qa/altitude_rrcm.json"}
    out = {}
    for chave, rel in arquivos.items():
        caminho = RAIZ / rel
        if not caminho.exists():
            sys.exit(f"falta {rel}: gere os relatórios (tools/experimento_sensibilidade_hidrologica.py, tools/robustez_espacial_validacao.py, tools/validar_altitude_rrcm.py)")
        out[chave] = json.loads(caminho.read_text())
    return out


def _br(x: float, casas: int = 3) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def _pct(x: float, casas: int = 1) -> str:
    return f"{100 * x:+.{casas}f}%".replace(".", ",").replace("-", "\u2212")


def _faixa(vals, fmt) -> str:
    lo, hi = min(vals), max(vals)
    return fmt(lo) if fmt(lo) == fmt(hi) else f"{fmt(lo)} a {fmt(hi)}"


def slides_de_validacao() -> list:
    r = _relatorios()
    s, a = r["sens"], r["alt"]
    m, am = s["modelos"], s["amostra"]
    regra = m["A_regra_atual"]
    base = f"{_br(100 * am['taxa_base'], 3)}%"
    nome = {"C_com_coeficientes_de_escoamento": "Fluxo + declividade + C (8 cenários)", "D1_media_de_postos_regra_e_fisica": "Média de postos: regra e física",
            "D2_componentes_mais_fisica": "Componentes atuais + física (logística)"}
    cen = lambda g: list(m[g]["por_cenario_de_C"].values())
    linhas = [["Formulação", "AUC", "Precisão média", "Ganho vs. regra", "Decisão"],
              ["Regra atual (referência)", _br(regra["auc"]), _br(regra["precisao_media"], 5), "referência", "Mantida"],
              ["Fluxo acumulado + declividade", _br(m["B_fluxo_ajustado_pela_declividade"]["auc"]), _br(m["B_fluxo_ajustado_pela_declividade"]["precisao_media"], 5),
               _pct(m["B_fluxo_ajustado_pela_declividade"]["ganho_sobre_a_referencia"]), "Não adotada"]]
    for g, decisao in (("C_com_coeficientes_de_escoamento", "Não adotada"), ("D1_media_de_postos_regra_e_fisica", "Sem evidência"), ("D2_componentes_mais_fisica", "Não adotada")):
        xs = cen(g)
        linhas.append([nome[g], _faixa([x["auc"] for x in xs], _br), _faixa([x["precisao_media"] for x in xs], lambda v: _br(v, 5)),
                       _faixa([x["ganho_sobre_a_referencia"] for x in xs], _pct), decisao])
    rob = s["amostra"]["distribuicao_espacial_dos_positivos_bloco_1500m"]
    return [
        dict(titulo="Validação: o que os dados permitem afirmar", tam=14,
             texto=[
                 f"Altitude: o Copernicus GLO-30 é um DSM de ~30 m (inclui prédios e árvores; sem meio-fio nem microrrelevo). Contra {a['comparados']} marcos da Prefeitura, a ordem das cotas bate "
                 f"(Spearman {_br(a['spearman'], 2)}) com viés de +{_br(a['vies_m'], 1)} m: serve para ordenar trechos, não para medir a cota da rua.",
                 f"Terreno contra {am['trechos_rotulados']} trechos alagados registrados pela Prefeitura (2013–2014): AUC {_br(regra['auc'])} e precisão média {_br(regra['precisao_media'], 5)}, "
                 f"com taxa base de {base}. Sinal real, porém modesto.",
                 "Esses registros não têm data, hora nem chuva: não validam previsão. A validação é espacial, por blocos, com intervalos de confiança; a decisão não mudou ao variar o tamanho dos blocos, "
                 "a origem da grade e ao retirar blocos.",
                 "Conceitos distintos: suscetibilidade do terreno (fixa), exposição estimada (terreno e chuva prevista), ocorrência observada (relato ou registro) e previsão de alagamento, que o produto não oferece.",
             ],
             figs=[], largo=True, corpo_h=3_500_000,
             fala=f"Antes de mostrar o que testamos, o que os dados permitem afirmar. O relevo vem do Copernicus GLO-30, um modelo de superfície de cerca de 30 metros: enxerga prédios e árvores e não enxerga meio-fio nem sarjeta. "
                  f"Contra {a['comparados']} marcos geodésicos da Prefeitura, a ordem das altitudes bate, correlação {_br(a['spearman'], 2)}, mas com viés de {_br(a['vies_m'], 1)} metros. Então serve para ordenar trechos, não para medir a cota da rua. "
                  f"Contra {am['trechos_rotulados']} trechos que a Prefeitura registrou como alagados em 2013 e 2014, o índice de terreno tem AUC {_br(regra['auc'])}: um sinal real, mas modesto. "
                  "Esses registros não têm data, hora nem chuva, então não validam previsão. Por isso usamos validação espacial por blocos, com intervalos de confiança. "
                  "E é importante separar quatro coisas: a suscetibilidade do terreno, que é fixa; a exposição estimada, que junta terreno e chuva prevista; a ocorrência observada; e a previsão de alagamento, que o produto não oferece."),
        dict(titulo="Experimento complementar: modelagem hidrológica", tam=14,
             texto=[
                 f"Testamos fluxo acumulado, declividade, chuva uniforme (10, 30 e 60 mm) e coeficientes de escoamento hipotéticos contra a regra atual, nos mesmos {am['trechos_rotulados']} trechos, com validação por blocos espaciais.",
                 "Resultado: nenhuma formulação atingiu o critério de adoção (ganho de 10% com intervalo de confiança acima de zero). Decisão: manter a regra e priorizar ocorrências datadas com chuva associada.",
             ],
             tabela=dict(linhas=linhas, x=700_000, y=4_300_000, w=10_800_000, h=1_700_000, tam=11),
             legenda_rodape="Experimento exploratório: registros de 2013–2014, sem horário nem chuva associada. Não valida previsão condicionada à chuva.",
             figs=[], largo=True, corpo_h=1_250_000,
             fala="Também testamos se uma formulação física simplificada acrescentava informação à regra atual: fluxo acumulado ajustado pela declividade, com chuva uniforme de 10, 30 e 60 milímetros e coeficientes de escoamento hipotéticos. "
                  f"Comparamos nos mesmos {am['trechos_rotulados']} trechos, com validação por blocos espaciais. Nenhuma formulação atingiu o critério de adoção, que exige ganho de 10% com o intervalo de confiança acima de zero. "
                  "A média de postos entre a regra e a física ficou um pouco acima, mas com intervalo muito largo: é uma hipótese, não uma evidência. "
                  "Chuva uniforme não diferencia ruas: ela só escala o volume. O que comprovamos é restrito: as formulações simplificadas testadas não demonstraram ganho incremental com os dados disponíveis; não que a física não ajude. "
                  "A decisão é manter a regra e priorizar ocorrências datadas, com chuva associada."),
    ]


def preencher(placeholder, itens, tam):
    tf = placeholder.text_frame
    tf.word_wrap = True
    for p in list(tf.paragraphs)[1:]:
        p._p.getparent().remove(p._p)
    for i, item in enumerate(itens):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        for r in list(p.runs)[1:]:
            r._r.getparent().remove(r._r)
        run = p.runs[0] if p.runs else p.add_run()
        run.text = item
        run.font.size = Pt(tam)
        p.space_after = Pt(6)


def figura(slide, nome, pos, legenda, sintetico):
    caminho = FIG / nome
    iw, ih = Image.open(caminho).size
    x, y, w, h = (DIR["x"], DIR["y"], DIR["w"], DIR["h"]) if pos == "dir" else pos
    if pos == "dir":  # na coluna direita a figura larga fica no alto, sem ocupar a altura toda
        h = min(h, int(w * ih / iw)) if iw > ih else h
    esc = min(w / iw, h / ih)
    pw, ph = int(iw * esc), int(ih * esc)
    px, py = x + (w - pw) // 2, y + (h - ph) // 2 if pos != "dir" else y
    slide.shapes.add_picture(str(caminho), px, py, pw, ph)
    linhas = ([legenda] if legenda else []) + (["DADOS SINTÉTICOS (demonstração)"] if sintetico else [])
    if linhas:
        caixa = slide.shapes.add_textbox(x, py + ph + 30_000, w, 380_000)
        tf = caixa.text_frame
        tf.word_wrap = True
        for i, t in enumerate(linhas):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            r = p.add_run()
            r.text = t
            r.font.size = Pt(10)
            r.font.bold = t.startswith("DADOS")
            r.font.color.rgb = ALERTA if t.startswith("DADOS") else MUDO


def tabela(slide, linhas, x, y, w, h, tam=11):
    forma = slide.shapes.add_table(len(linhas), len(linhas[0]), Emu(x), Emu(y), Emu(w), Emu(h))
    tb = forma.table
    pesos = [3.6, 1.1, 1.7, 2.0, 1.6]
    for j, pj in enumerate(pesos):
        tb.columns[j].width = Emu(int(w * pj / sum(pesos)))
    for i, lin in enumerate(linhas):
        for j, txt in enumerate(lin):
            c = tb.cell(i, j)
            c.text = txt
            for p in c.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(tam)
                    r.font.bold = i == 0


def rodape(slide, texto, y):
    caixa = slide.shapes.add_textbox(Emu(700_000), Emu(y), Emu(10_800_000), Emu(330_000))
    caixa.text_frame.word_wrap = True
    r = caixa.text_frame.paragraphs[0].add_run()
    r.text = texto
    r.font.size = Pt(10)
    r.font.color.rgb = ALERTA


def achar(slide, nome):
    return next(s for s in slide.shapes if s.name.startswith(nome))


def trocar_texto(forma, textos):
    for p, t in zip(forma.text_frame.paragraphs, textos):
        p.runs[0].text = t
        for r in p.runs[1:]:
            r.text = ""


def clonar(prs, base):
    """Cópia do slide-base do template (barra, logotipos, título e corpo), religando as imagens."""
    novo = prs.slides.add_slide(base.slide_layout)
    for sh in list(novo.shapes):
        sh._element.getparent().remove(sh._element)
    for sh in base.shapes:
        el = copy.deepcopy(sh._element)
        novo.shapes._spTree.append(el)
        for blip in el.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
            rid = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
            if rid:
                blip.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed",
                         novo.part.relate_to(base.part.related_part(rid), RT.IMAGE))
    return novo


def escrever_roteiro():
    linhas = ["# Roteiro da apresentação curta (template FTL)", "",
              "Gerado por `tools/gerar_apresentacao_ftl.py`, a partir do mesmo texto dos slides e das notas do apresentador do `.pptx`. "
              "Fala a 150 palavras por minuto.", ""]
    total = 0
    lista_slides = todos_os_slides()
    for i, s in enumerate(lista_slides, start=3):
        pal = len(s["fala"].split())
        total += pal
        linhas += [f"## Slide {i}: {s['titulo']} (~{round(pal / 150 * 60)} s)", "", "**No slide**", ""]
        linhas += [f"- {t}" for t in s["texto"]] + ["", "**Fala**", "", s["fala"], ""]
    linhas.insert(4, f"Duração estimada da fala dos slides 3 a {len(lista_slides) + 2}: **cerca de {str(round(total / 150, 1)).replace(".", ",")} min**, além de capa e encerramento.\n")
    linhas += ["## Cuidados de honestidade", "",
               "- As telas marcadas SINTÉTICO vêm da demonstração (chuva e ocorrências inventadas); não são evidência de eventos reais.",
               "- O valor para Defesa Civil, EPTC, planejamento e cidadãos é o valor potencial do desenho; não houve validação de uso com esses públicos.",
               "- Não dizer que o sistema prevê alagamentos, que uma rota é segura ou que o modelo treinado superou as regras simples.", ""]
    ROTEIRO.write_text("\n".join(linhas), encoding="utf-8")


def todos_os_slides() -> list:
    """Os slides, com os de validação (números dos relatórios finais) depois dos resultados de mobilidade."""
    i = next(k for k, s in enumerate(SLIDES) if s["titulo"].startswith("Resultados"))
    return SLIDES[:i + 1] + slides_de_validacao() + SLIDES[i + 1:]


def main(template: Path, saida: Path) -> None:
    prs = Presentation(str(template))
    orig = list(prs.slides)

    for sh in [s for s in orig[1].shapes if s.has_text_frame]:
        t = sh.text_frame.text.strip()
        if t == "Nome do projeto":
            trocar_texto(sh, ["Flooding Mapping"])
            for r in sh.text_frame.paragraphs[0].runs:
                r.font.size = Pt(30)
        elif t == "Autor":
            trocar_texto(sh, ["Helena de Oliveira Valanera"])

    base = orig[4]
    novos = []
    for s in todos_os_slides():
        sl = clonar(prs, base)
        tit = sl.shapes.title.text_frame.paragraphs[0]
        tit.runs[0].text = s["titulo"]
        for r in tit.runs[1:]:
            r.text = ""
        corpo = achar(sl, "Content Placeholder")
        corpo.left, corpo.top = Emu(TX), Emu(TY)
        larga = s.get("largo") or any(f[1] != "dir" and f[1][3] > 2_400_000 and f[1][2] > 9_000_000 for f in s["figs"])
        corpo.width = Emu(TW if not larga else 10_800_000)
        corpo.height = Emu(s.get("corpo_h") or (1_100_000 if larga else 3_300_000))
        preencher(corpo, s["texto"], s["tam"])
        if s.get("tabela"):
            tabela(sl, **s["tabela"])
        if s.get("legenda_rodape"):
            rodape(sl, s["legenda_rodape"], 6_080_000)
        for nome, pos, leg, sint in s["figs"]:
            figura(sl, nome, pos, leg, sint)
        sl.notes_slide.notes_text_frame.text = s["fala"]
        novos.append(sl)

    lista = prs.slides._sldIdLst
    ids = list(lista)
    por_slide = {id(sl.part): el for sl, el in zip(prs.slides, ids)}
    manter = [orig[0], orig[1]] + novos + [orig[8]]
    descartar = [sl for sl in orig if sl not in manter]
    for el in ids:
        lista.remove(el)
    for sl in manter:
        lista.append(por_slide[id(sl.part)])
    for sl in descartar:
        for rel_id, rel in list(prs.part.rels.items()):
            if rel.reltype == RT.SLIDE and rel.target_part is sl.part:
                prs.part.drop_rel(rel_id)

    saida.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(saida))
    escrever_roteiro()
    print(f"gravado: {saida} ({len(prs.slides)} slides) e {ROTEIRO}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else SAIDA_PADRAO)
