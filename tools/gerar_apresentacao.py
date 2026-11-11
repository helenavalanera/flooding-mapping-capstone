# -*- coding: utf-8 -*-
"""Gera a apresentação do capstone (.pptx) a partir de capturas e números que já existem no repositório.

    pip install python-pptx            # dependência só desta ferramenta; não entra nos requirements do produto
    python tools/gerar_apresentacao.py # grava docs/apresentacao/Flooding_Mapping_Capstone.pptx (ignorado pelo Git, como os demais documentos de escritório)

Nenhuma imagem é desenhada para simular telas: as figuras vêm de docs/figuras (capturas reais e figuras do pipeline). Capturas feitas com a demonstração
(chuva e ocorrências sintéticas) recebem a etiqueta "DADOS SINTÉTICOS". Os gráficos usam só números dos relatórios citados em cada slide.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

RAIZ = Path(__file__).resolve().parents[1]
FIG = RAIZ / "docs" / "figuras"
SAIDA = RAIZ / "docs" / "apresentacao" / "Flooding_Mapping_Capstone.pptx"

TINTA, MUDO, FUNDO, CARD = RGBColor(0x1B, 0x26, 0x30), RGBColor(0x5A, 0x68, 0x72), RGBColor(0xF6, 0xF8, 0xF9), RGBColor(0xFF, 0xFF, 0xFF)
PETROLEO, AZUL, ALERTA, VERDE, VERMELHO, LINHA = (RGBColor(0x0F, 0x3F, 0x4A), RGBColor(0x0B, 0x5D, 0x8F), RGBColor(0xC2, 0x7A, 0x00),
                                                   RGBColor(0x1B, 0x7F, 0x5C), RGBColor(0xB3, 0x20, 0x2A), RGBColor(0xD5, 0xDD, 0xE2))
FONTE = "Arial"
L, A = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width, prs.slide_height = L, A
VAZIO = prs.slide_layouts[6]
_n = [0]


def texto(slide, x, y, w, h, linhas, tam=16, cor=TINTA, negrito=False, alinhar=PP_ALIGN.LEFT, ancora=MSO_ANCHOR.TOP, espaco=6):
    """linhas: str ou lista de str / (str, dict). Cada item vira um parágrafo."""
    caixa = slide.shapes.add_textbox(x, y, w, h)
    tf = caixa.text_frame; tf.word_wrap = True; tf.vertical_anchor = ancora
    tf.margin_left = tf.margin_right = Inches(0.05); tf.margin_top = tf.margin_bottom = Inches(0.03)
    itens = [linhas] if isinstance(linhas, str) else linhas
    for i, item in enumerate(itens):
        t, op = (item, {}) if isinstance(item, str) else item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = op.get("alinhar", alinhar); p.space_after = Pt(op.get("espaco", espaco))
        r = p.add_run(); r.text = t
        r.font.name = FONTE; r.font.size = Pt(op.get("tam", tam)); r.font.bold = op.get("negrito", negrito)
        r.font.color.rgb = op.get("cor", cor)
    return caixa


def marcadores(slide, x, y, w, h, itens, tam=17, cor=TINTA):
    return texto(slide, x, y, w, h, [("•  " + t, {"espaco": 9}) for t in itens], tam=tam, cor=cor)


def retangulo(slide, x, y, w, h, cor=CARD, borda=LINHA, raio=True):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if raio else MSO_SHAPE.RECTANGLE, x, y, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = cor
    if borda is None: s.line.fill.background()
    else: s.line.color.rgb = borda; s.line.width = Pt(1)
    if raio: s.adjustments[0] = 0.06
    s.shadow.inherit = False
    return s


def caixa_texto(slide, x, y, w, h, titulo, corpo, cor_fundo=CARD, cor_titulo=AZUL, tam=13):
    retangulo(slide, x, y, w, h, cor_fundo)
    texto(slide, x + Inches(0.12), y + Inches(0.08), w - Inches(0.24), Inches(0.4), titulo, tam=tam + 1, cor=cor_titulo, negrito=True)
    texto(slide, x + Inches(0.12), y + Inches(0.5), w - Inches(0.24), h - Inches(0.55), corpo, tam=tam, cor=TINTA)


def foto(slide, caminho, x, y, w, h, legenda=None, sintetico=False):
    """Insere a imagem inteira, sem distorcer, centralizada na caixa (x, y, w, h)."""
    cam = FIG / caminho
    iw, ih = Image.open(cam).size
    esc = min(w / iw, h / ih)
    pw, ph = int(iw * esc), int(ih * esc)
    px, py = x + (w - pw) // 2, y + (h - ph) // 2
    slide.shapes.add_picture(str(cam), px, py, pw, ph)
    ln = slide.shapes[-1].line; ln.color.rgb = LINHA; ln.width = Pt(1)
    if sintetico: etiqueta(slide, px + Inches(0.1), py + Inches(0.1), "DADOS SINTÉTICOS DE DEMONSTRAÇÃO")
    if legenda: texto(slide, x, py + ph + Inches(0.03), w, Inches(0.5), legenda, tam=10, cor=MUDO, alinhar=PP_ALIGN.CENTER)


def etiqueta(slide, x, y, t, cor=ALERTA, larg=Inches(3.3)):
    s = retangulo(slide, x, y, larg, Inches(0.3), cor, None)
    texto(slide, x, y, larg, Inches(0.3), t, tam=10, cor=RGBColor(255, 255, 255), negrito=True, alinhar=PP_ALIGN.CENTER, ancora=MSO_ANCHOR.MIDDLE)


def seta(slide, x1, y1, x2, y2, cor=MUDO):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = cor; c.line.width = Pt(2)
    ln = c.line._get_or_add_ln()
    from lxml import etree
    etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", type="triangle")


def novo(titulo, subtitulo=None, fonte=None, notas="", secao=None):
    s = prs.slides.add_slide(VAZIO); _n[0] += 1
    fundo = s.background.fill; fundo.solid(); fundo.fore_color.rgb = FUNDO
    faixa = retangulo(s, 0, 0, L, Inches(1.05), PETROLEO, None, raio=False)
    texto(s, Inches(0.55), Inches(0.14), Inches(11.6), Inches(0.6), titulo, tam=28, cor=RGBColor(255, 255, 255), negrito=True)
    if subtitulo: texto(s, Inches(0.55), Inches(0.62), Inches(11.8), Inches(0.4), subtitulo, tam=14, cor=RGBColor(0xB9, 0xD4, 0xDA))
    rodape = "Flooding Mapping · capstone" + (f" · {secao}" if secao else "")
    texto(s, Inches(0.55), Inches(7.08), Inches(8), Inches(0.3), rodape, tam=9, cor=MUDO)
    if fonte: texto(s, Inches(0.55), Inches(6.78), Inches(12.2), Inches(0.3), "Fonte: " + fonte, tam=9, cor=MUDO)
    texto(s, Inches(12.2), Inches(7.08), Inches(0.7), Inches(0.3), str(_n[0]), tam=9, cor=MUDO, alinhar=PP_ALIGN.RIGHT)
    s.notes_slide.notes_text_frame.text = notas
    return s


# ======================================================================================================= 1. capa
s = prs.slides.add_slide(VAZIO); _n[0] += 1
f = s.background.fill; f.solid(); f.fore_color.rgb = PETROLEO
texto(s, Inches(0.8), Inches(2.0), Inches(11.5), Inches(1.2), "Flooding Mapping", tam=54, cor=RGBColor(255, 255, 255), negrito=True)
texto(s, Inches(0.8), Inches(3.2), Inches(11.5), Inches(1.0), "Inteligência territorial e mobilidade preventiva diante de alagamentos pluviais em Porto Alegre/RS", tam=24, cor=RGBColor(0xB9, 0xD4, 0xDA))
texto(s, Inches(0.8), Inches(5.0), Inches(11.5), Inches(1.2),
      ["Helena de Oliveira Valanera", ("Future Tech Leaders Brasil · Space Tech Bootcamp 2026", {"tam": 16, "cor": RGBColor(0xB9, 0xD4, 0xDA)}),
       ("Novembro de 2026 · projeto de código aberto, sem substituir os alertas oficiais da Defesa Civil", {"tam": 13, "cor": RGBColor(0xB9, 0xD4, 0xDA)})], tam=20, cor=RGBColor(255, 255, 255))
s.notes_slide.notes_text_frame.text = ("Boa tarde. Eu sou a Helena e vou apresentar o Flooding Mapping: uma plataforma que combina dados territoriais, meteorologia, ocorrências e roteamento "
                                       "para ajudar a entender como os alagamentos afetam a mobilidade em Porto Alegre. Vou mostrar o que foi construído, o que foi medido e, com a mesma ênfase, o que o trabalho não demonstra.")

# ======================================================================================================= 2. contexto
s = novo("A chuva que desorganiza a cidade não é só a extrema", "Contextualização do problema",
         "reports/qa/rain_frequency.json (reanálise ERA5, centro da cidade, média de 2015–2024; dado modelado) · Documentação técnica, seção 6.1",
         "Os alagamentos pluviais fecham cruzamentos e trechos de vias em Porto Alegre várias vezes por ano. O menor acumulado em 24 horas que já coincidiu com bloqueios registrados pela EPTC é 26,2 milímetros. "
         "Pela reanálise de 2015 a 2024, esse nível é igualado ou superado em média em 14 dias por ano, com variação de 8 a 21. Ou seja, chuvas comuns, não só eventos extremos, já desorganizam o deslocamento. "
         "Atenção: é dado modelado, não medição de pluviômetro.", "contexto")
cd = CategoryChartData(); cd.categories = ["≥ 20 mm", "≥ 26,2 mm\n(menor com bloqueio)", "≥ 30 mm", "≥ 45 mm"]; cd.add_series("Dias por ano", (21.8, 14.1, 10.3, 4.3))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.4), Inches(7.4), Inches(5.2), cd); ch = gf.chart
ch.has_legend = False; ch.has_title = True; ch.chart_title.text_frame.text = "Dias por ano com chuva diária acima do nível"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14); ch.chart_title.text_frame.paragraphs[0].runs[0].font.name = FONTE
pl = ch.plots[0]; pl.has_data_labels = True; pl.data_labels.font.size = Pt(14); pl.data_labels.font.bold = True; pl.data_labels.number_format = '0.0'; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END; pl.gap_width = 70
pl.series[0].format.fill.solid(); pl.series[0].format.fill.fore_color.rgb = AZUL
ch.category_axis.tick_labels.font.size = Pt(12); ch.value_axis.tick_labels.font.size = Pt(11); ch.value_axis.has_major_gridlines = False
marcadores(s, Inches(8.4), Inches(1.6), Inches(4.5), Inches(4.5), [
    "Bloqueios totais e parciais por acúmulo de água em vias de Porto Alegre, várias vezes por ano.",
    "26,2 mm em 24 h é o menor acumulado associado a bloqueio registrado: ocorre em média 14 dias por ano (entre 8 e 21).",
    "Cada bloqueio é pontual, mas somados alongam rotas e isolam bairros."], tam=16)
etiqueta(s, Inches(8.45), Inches(5.6), "Reanálise: dado modelado, não pluviômetro", MUDO, Inches(4.4))

# ======================================================================================================= 3. problema e oportunidade
s = novo("Problema e oportunidade", "Os dados abertos existem, mas são parciais e defasados", "Proposta, seção 4 (Tabela 1) e docs/produto_preventivo.md",
         "O problema tem duas camadas. Primeiro, o fenômeno: chuvas comuns bloqueiam vias. Segundo, a informação: os dados públicos são parciais. O GTFS de ônibus perdeu a vigência em dezembro de 2025; "
         "os bloqueios documentados são 24 pontos em 4 datas; não há dados abertos de bocas de lobo; a chuva disponível é modelada. A oportunidade é integrar o que existe, reprodutivelmente, e deixar explícito o que é "
         "observado, o que é estimado e o que falta.", "problema")
caixa_texto(s, Inches(0.6), Inches(1.45), Inches(5.9), Inches(4.9), "O problema", [
    "• Chuva comum já fecha vias e alonga deslocamentos.",
    "• GTFS de ônibus vencido em 12/12/2025 (único publicado).",
    "• Bloqueios documentados: 24 pontos em 4 datas (2019–2025); 19 geocodificados.",
    "• Sem dados abertos de bocas de lobo ou limpeza urbana.",
    "• Chuva modelada; a previsão não captou o temporal de 06/03/2022."], cor_titulo=VERMELHO, tam=15)
caixa_texto(s, Inches(6.8), Inches(1.45), Inches(5.9), Inches(4.9), "A oportunidade", [
    "• Integrar dados abertos (OSM, IBGE, Copernicus, Open-Meteo, EPTC, S2iD, CPRv BM, DAER) de forma reprodutível.",
    "• Medir o efeito na mobilidade e orientar o deslocamento antes de sair.",
    "• Separar com clareza observado, previsto, simulado e confirmado.",
    "• Declarar o que os dados não sustentam."], cor_titulo=VERDE, tam=15)

# ======================================================================================================= 4. objetivos
s = novo("Objetivos do projeto", "Proposta original e situação final", "docs/proposta.md, seções 1 e 6",
         "O objetivo geral da proposta era um modelo de aprendizado de máquina que estimasse a mobilidade perdida com chuvas de até 45 milímetros. Os objetivos específicos eram quatro. "
         "Três foram entregues, de forma completa ou como protótipo; o estimador de impacto, o chamado Modelo 2, não foi treinado: a perda é calculada por simulação de roteamento com regra explícita. "
         "A hipótese, de que um modelo treinado supera regras simples, não foi confirmada: a logística empata com a regra de terreno baixo, e o random forest sobreajusta. Isso é um resultado do trabalho.", "objetivos")
texto(s, Inches(0.6), Inches(1.3), Inches(12.2), Inches(0.9), "Estimar a mobilidade urbana perdida com chuvas de até 45 mm em 24 h e entregar o resultado em cartografia e em ferramentas de apoio ao deslocamento.", tam=17, cor=PETROLEO, negrito=True)
linhas = [("(a) Mobilidade de base por modo", "Entregue", VERDE), ("(b) Suscetibilidade por trecho viário", "Entregue como protótipo; sem validação em vias", ALERTA),
          ("(c) Estimador da mobilidade perdida (Modelo 2)", "Não treinado; simulação com regra explícita", VERMELHO), ("(d) Cartografia e painel de alerta", "Entregue e ampliado: painel + aplicativo web (PWA)", VERDE),
          ("Hipótese: modelo treinado supera regras simples", "Não confirmada (logística 0,86 × regra 0,85; poucos eventos)", VERMELHO)]
y = Inches(2.3)
for a, b, c in linhas:
    retangulo(s, Inches(0.6), y, Inches(12.2), Inches(0.78), CARD)
    s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), y, Inches(0.12), Inches(0.78)).fill.solid()
    barra = s.shapes[-1]; barra.fill.fore_color.rgb = c; barra.line.fill.background()
    texto(s, Inches(0.9), y, Inches(5.6), Inches(0.78), a, tam=16, negrito=True, ancora=MSO_ANCHOR.MIDDLE)
    texto(s, Inches(6.6), y, Inches(6.1), Inches(0.78), b, tam=15, cor=MUDO, ancora=MSO_ANCHOR.MIDDLE)
    y += Inches(0.88)

# ======================================================================================================= 5. área de estudo
s = novo("Área de estudo: Porto Alegre/RS", "Porto Alegre em detalhe; Rio Grande do Sul em monitoramento regional", "Documentação técnica, seções 5.1 e 6.2 (figura: pipeline de pesquisa, Open-Meteo/OSM/IBGE) · reports/ml/rotas_auditoria.json",
         "A área de estudo é Porto Alegre: 1 milhão 333 mil habitantes no Censo de 2022, e 176 mil segmentos de via no OpenStreetMap. A figura mostra a cidade alcançável: a parcela da população que uma pessoa alcança em 30 minutos, "
         "sem chuva, a pé, de carro e de ônibus, em uma grade de 1 quilômetro. Na plataforma, o Rio Grande do Sul entra como monitoramento regional, com 497 municípios e a malha de rodovias do DAER, mas rotas e risco por trecho existem só em Porto Alegre.", "área")
foto(s, "cidade_alcancavel_sem_chuva.png", Inches(0.5), Inches(1.3), Inches(8.2), Inches(5.3), "Parcela da população da cidade alcançável em até 30 minutos, sem chuva (grade de 1 km; a pé, carro e ônibus)")
marcadores(s, Inches(9.0), Inches(1.5), Inches(3.9), Inches(5), [
    "Porto Alegre: 1.332.845 habitantes (Censo 2022); 176.836 segmentos de via (OSM, 24/10/2026).",
    "Rotas de carro e a pé e risco por trecho: só Porto Alegre.",
    "Rio Grande do Sul: monitoramento regional (497 municípios, malha do DAER).",
    "Ônibus: fora da plataforma (GTFS vencido)."], tam=15)

# ======================================================================================================= 6. arquitetura
s = novo("Arquitetura da solução", "Um serviço de análise, duas interfaces e um assistente que só reformula", "docs/produto_preventivo.md e docs/hospedagem.md",
         "A arquitetura é deliberadamente simples. À esquerda, as fontes de dados. No centro, um serviço de análise em Python, um único processo, que concentra as regras: meteorologia, risco por trecho, roteamento, ocorrências e interdições. "
         "À direita, o painel de análise para desktop e o aplicativo web para celular, ambos consumindo a mesma API. O assistente com Gemini reformula textos que o sistema já calculou; ele não calcula, não classifica e não cria interdições. "
         "Há também o operador humano, que confirma ocorrências.", "arquitetura")
def bloco(x, y, w, h, t, sub, cor):
    retangulo(s, x, y, w, h, cor, None); texto(s, x, y + Inches(0.05), w, h - Inches(0.1), [(t, {"tam": 15, "negrito": True, "cor": RGBColor(255, 255, 255)}), (sub, {"tam": 11, "cor": RGBColor(0xE3, 0xEE, 0xF1)})], alinhar=PP_ALIGN.CENTER, ancora=MSO_ANCHOR.MIDDLE, espaco=2)
bloco(Inches(0.5), Inches(1.5), Inches(3.0), Inches(4.6), "Fontes abertas", "Open-Meteo (chuva)\nOpenStreetMap (ruas)\nCopernicus DEM (relevo)\nIBGE (território)\nEPTC, S2iD, CPRv BM, DAER (eventos e rodovias)", MUDO)
bloco(Inches(4.3), Inches(1.5), Inches(4.4), Inches(3.0), "Serviço de análise (Python, 1 processo)", "meteorologia · risco por trecho (baseline)\nroteamento carro e a pé · ocorrências e interdições\nAPI + arquivos estáticos", PETROLEO)
bloco(Inches(4.3), Inches(4.8), Inches(4.4), Inches(1.3), "Persistência", "arquivo de ocorrências (um processo) · reinício preserva", AZUL)
bloco(Inches(9.5), Inches(1.5), Inches(3.3), Inches(1.3), "Painel (desktop)", "mapa 3D/2D · proveniência", AZUL)
bloco(Inches(9.5), Inches(3.0), Inches(3.3), Inches(1.3), "PWA (celular)", "rotas · alternativas · relato", AZUL)
bloco(Inches(9.5), Inches(4.5), Inches(3.3), Inches(1.6), "Assistente (Gemini)", "só reformula textos já calculados;\nsem ele há texto padrão", ALERTA)
for (x1, y1, x2, y2) in [(Inches(3.5), Inches(3.8), Inches(4.3), Inches(3.0)), (Inches(8.7), Inches(2.4), Inches(9.5), Inches(2.1)), (Inches(8.7), Inches(3.0), Inches(9.5), Inches(3.6)), (Inches(8.7), Inches(3.9), Inches(9.5), Inches(5.0)), (Inches(6.5), Inches(4.5), Inches(6.5), Inches(4.8))]:
    seta(s, x1, y1, x2, y2)

# ======================================================================================================= 7. fontes
s = novo("Fontes e integração dos dados", "Todas abertas, com atribuição e limite declarados", "Documentação técnica, seção 4.3; docs/ml_gatilho.md; tela de Proveniência do painel",
         "Todas as fontes são abertas. Para cada uma, a tabela diz o uso, a referência temporal e o limite. Destaco três: o GTFS está vencido; os eventos de bloqueio são poucos e enviesados pela notificação; e a chuva é modelada, "
         "em grade de cerca de 10 quilômetros. A plataforma mostra isso na tela de proveniência. A licença dos dados do DAER ainda precisa ser confirmada.", "dados")
linhas = [("Fonte", "Uso", "Limite"),
          ("OpenStreetMap (24/10/2026)", "Rede de ruas e hidrografia", "Sem bocas de lobo nem microdrenagem; qualidade da malha não validada"),
          ("Copernicus DEM GLO-30", "Relevo e atributos físicos", "Superfície; sem meio-fio nem microrrelevo"),
          ("IBGE, Censo 2022", "Território e população", "Densidade uniforme no setor; quatro anos"),
          ("Open-Meteo", "Chuva: previsão, análise do modelo e reanálise", "Dado modelado, grade de cerca de 10 km; não é pluviômetro"),
          ("EPTC / Prefeitura", "Bloqueios de via (2019–2025)", "24 pontos em 4 datas; 19 geocodificados; viés de notificação"),
          ("S2iD, CPRv BM, DAER (RS)", "Registros, bloqueios ativos, malha rodoviária", "S2iD municipal e sem geometria; CPRv sem histórico; licença do DAER a confirmar"),
          ("GTFS EPTC", "Ônibus no pipeline de pesquisa", "Vencido em 12/12/2025; fora da plataforma")]
tb = s.shapes.add_table(len(linhas), 3, Inches(0.6), Inches(1.4), Inches(12.2), Inches(5.0)).table
for j, w in enumerate((3.2, 3.9, 5.1)): tb.columns[j].width = Inches(w)
for i, lin in enumerate(linhas):
    for j, t in enumerate(lin):
        c = tb.cell(i, j); c.text = t; p = c.text_frame.paragraphs[0]; p.runs[0].font.size = Pt(13 if i else 14); p.runs[0].font.name = FONTE; p.runs[0].font.bold = (i == 0)
        c.fill.solid(); c.fill.fore_color.rgb = PETROLEO if i == 0 else (CARD if i % 2 else RGBColor(0xEE, 0xF2, 0xF4))
        p.runs[0].font.color.rgb = RGBColor(255, 255, 255) if i == 0 else TINTA

# ======================================================================================================= 8. metodologia geoespacial
s = novo("Metodologia geoespacial", "Cidade alcançável, bloqueio por segmento e índice físico do terreno", "Documentação técnica, seções 5.1 a 5.4; reports/qa/susceptibility_run.json",
         "A medida central é a cidade alcançável: a população das células de uma grade de 1 quilômetro que se alcança em 30 minutos, a pé, de ônibus e de carro, calculada com o r5py. "
         "A mobilidade perdida compara essa população com e sem o fechamento de trechos. Os trechos que fecham vêm de uma regra explícita: abaixo de 26,2 milímetros nada fecha; a partir daí fecham os bloqueios documentados "
         "e alguns pontos que o modelo de suscetibilidade indica. Esse modelo ordena segmentos pela semelhança de terreno com os locais já bloqueados; ele não prevê alagamento.", "método")
caixa_texto(s, Inches(0.6), Inches(1.4), Inches(4.0), Inches(5.1), "Cidade alcançável", [
    "Grade de 1 km: 579 células com população (1.332.845 pessoas conservadas).",
    "A0: população alcançável em 30 min, sem chuva; A_s com os trechos fechados.",
    "Mobilidade perdida = 1 − Σ pop·A_s / Σ pop·A0.",
    "Roteamento multimodal com r5py."], tam=14)
caixa_texto(s, Inches(4.8), Inches(1.4), Inches(4.0), Inches(5.1), "Da chuva ao bloqueio", [
    "Abaixo de 26,2 mm em 24 h nada fecha (menor acumulado com bloqueio registrado).",
    "Acima, fecham os bloqueios documentados e N pontos do modelo de suscetibilidade.",
    "N vem de um ajuste com 3 datas: provisório.",
    "Fator de precariedade como sensibilidade."], tam=14)
caixa_texto(s, Inches(9.0), Inches(1.4), Inches(3.8), Inches(5.1), "Suscetibilidade (protótipo)", [
    "107.869 segmentos; positivos: a 50 m de um bloqueio.",
    "Variáveis físicas: cota, relevo local, declividade, distância e altura da água, fluxo, TWI.",
    "Validação espacial e temporal com 17 locais: ordena, não prevê."], tam=14, cor_titulo=ALERTA)

# ======================================================================================================= 9. meteorologia
s = novo("Meteorologia e suas limitações", "Série regional, validade declarada e estados de falha tratados", "Open-Meteo; docs/produto_preventivo.md (Meteorologia). Captura do PWA: dados sintéticos de demonstração",
         "A chuva do produto é uma única série horária para a cidade inteira, de uma grade de cerca de 10 quilômetros. O passado recente é análise do modelo, não medição de pluviômetro; as horas à frente são previsão. "
         "Os dados valem 6 horas. Se a fonte falhar, o último valor segue marcado como defasado até as 6 horas; depois disso o sistema diz que a chuva está indisponível, mostra só tempo e distância das rotas e avisa que isso não significa rota sem risco. "
         "A captura é da demonstração, com chuva sintética, e está identificada.", "meteorologia")
foto(s, "pwa_navegacao_detalhes_390.png", Inches(0.6), Inches(1.2), Inches(3.3), Inches(5.5), "PWA, detalhes da rota: fonte, idade e escopo da chuva", sintetico=False)
etiqueta(s, Inches(0.7), Inches(1.3), "SINTÉTICO", ALERTA, Inches(1.4))
marcadores(s, Inches(4.4), Inches(1.5), Inches(8.4), Inches(5.1), [
    "Uma série horária para a cidade inteira (grade de cerca de 10 km): diz quando chove, não onde.",
    "Passado recente = análise do modelo, não pluviômetro. Futuro = previsão.",
    "Validade de 6 h; renovação a cada 30 min; depois disso, indisponível, com a última atualização conhecida.",
    "Sem chuva: só tempo e distância; sem estimativa de risco. Isso não significa rota sem risco.",
    "Demonstrações usam chuva sintética, sempre identificada na tela.",
    "Parâmetros meteorológicos não foram ajustados sem evidência."], tam=16)

# ======================================================================================================= 10. risco
s = novo("Avaliação experimental de risco por trecho", "Um baseline explícito, auditado contra os eventos documentados", "reports/ml/risco_trecho_auditoria.json (19 bloqueios geocodificados em 4 datas; 2.863 dias avaliados)",
         "O risco por trecho é um baseline determinístico: o escore é o fator de chuva vezes o peso do trecho, e o peso vem do percentil do índice físico do terreno. Eu o confrontei com os 19 bloqueios documentados. "
         "O resultado é honesto e negativo: o baseline sinalizou 4 dos 19 em algum horário do dia, e só 2 na hora do reporte. Nenhum corte do índice detecta os eventos sem sinalizar uma parcela grande da malha, "
         "então não há ajuste de parâmetro que resolva isso, e eu não ajustei nenhum. Também importa: em 2.863 dias, alguma via ficou em Atenção em 682, mas só 4 dias têm registro. "
         "Ausência de registro não é exemplo negativo.", "risco")
cd = CategoryChartData(); cd.categories = ["Detectados na hora\ndo reporte", "Detectados em algum\nhorário do dia", "Não detectados\nno dia"]; cd.add_series("Bloqueios documentados", (2, 4, 15))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.4), Inches(6.3), Inches(5.0), cd); ch = gf.chart
ch.has_legend = False; ch.has_title = True; ch.chart_title.text_frame.text = "Dos 19 bloqueios documentados"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14); ch.chart_title.text_frame.paragraphs[0].runs[0].font.name = FONTE
pl = ch.plots[0]; pl.has_data_labels = True; pl.data_labels.font.size = Pt(16); pl.data_labels.font.bold = True; pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END; pl.gap_width = 60
pl.series[0].format.fill.solid(); pl.series[0].format.fill.fore_color.rgb = AZUL
ch.category_axis.tick_labels.font.size = Pt(12); ch.value_axis.has_major_gridlines = False; ch.value_axis.maximum_scale = 18
caixa_texto(s, Inches(7.2), Inches(1.4), Inches(5.6), Inches(2.45), "Três conceitos, separados", [
    "Suscetibilidade espacial: índice físico relativo, não é probabilidade.",
    "Previsão temporal: só a chuva futura e uma regra explícita.",
    "Impacto na mobilidade: rotas e simulação de fechamento."], tam=13)
caixa_texto(s, Inches(7.2), Inches(4.0), Inches(5.6), Inches(2.4), "O que isso significa", [
    "Dos 15 não detectados: 9 com peso zero, 6 com chuva abaixo do nível.",
    "682 de 2.863 dias com via em Atenção; só 4 dias com registro.",
    "Experimental, sem validação em vias. Nenhum parâmetro foi ajustado."], tam=13, cor_titulo=VERMELHO)

# ======================================================================================================= 11. roteamento
s = novo("Roteamento e mobilidade", "Carro e a pé; o tempo e a exposição estimada no horário de passagem", "reports/ml/rotas_auditoria.json; docs/produto_preventivo.md. Captura do PWA: dados sintéticos de demonstração",
         "O roteamento usa o algoritmo de Dijkstra sobre a rede do OpenStreetMap. O custo é o tempo mais uma penalidade que depende do risco estimado no horário em que a pessoa passaria por cada trecho. "
         "Uma interdição confirmada remove o trecho do cálculo nos dois modais. Eu comparei o algoritmo com um caminho mínimo de referência, o NetworkX, em 100 pares por modal: nenhuma diferença. "
         "Isso valida o cálculo, não a qualidade da malha do OpenStreetMap nem o tempo real de viagem. Nenhuma rota é apresentada como segura: o produto fala em menor exposição estimada.", "roteamento")
foto(s, "pwa_navegacao_compacta_390.png", Inches(0.6), Inches(1.2), Inches(3.4), Inches(5.5), "PWA: rota, alternativas e interdição considerada", sintetico=False)
etiqueta(s, Inches(0.7), Inches(1.3), "SINTÉTICO", ALERTA, Inches(1.4))
marcadores(s, Inches(4.4), Inches(1.5), Inches(8.4), Inches(5.1), [
    "Custo = tempo + penalidade (risco × confiabilidade × aversão), no horário de passagem.",
    "Rota habitual, menor exposição estimada e alternativa distinta, com os trade-offs de tempo e distância.",
    "Interdição confirmada é bloqueio rígido, nos dois modais; risco previsto só penaliza.",
    "Conferido contra NetworkX: 0 diferenças em 100 pares por modal. Valida o algoritmo, não a malha.",
    "Sem ônibus, sem instruções de manobra, sem trânsito ou semáforos."], tam=16)

# ======================================================================================================= 12. ocorrências
s = novo("Gestão de ocorrências e interdições", "Um relato nunca interdita; só a confirmação humana, com evidência", "docs/operacao_ocorrencias.md; tests/e2e/jornada.js",
         "Este é o fluxo mais importante para a confiança do sistema. Qualquer pessoa pode relatar um problema, mas o relato entra como pendente e não interdita nada. Um operador, com credencial e evidência escrita, "
         "pode confirmar e declarar o impacto. Só a confirmação com impacto de interdição remove o trecho do cálculo das rotas. Tudo fica no histórico. O teste de ponta a ponta verifica que o traçado da rota muda depois da confirmação. "
         "Quem é o operador na prática, e quais evidências valem, depende de decisão institucional; está marcado como pendente de aprovação.", "ocorrências")
passos = [("Relato", "qualquer pessoa\n(pendente, sem verificação)", MUDO), ("Revisão", "operador com credencial\n+ evidência escrita", AZUL), ("Confirmação", "situação e impacto\ndeclarados", PETROLEO), ("Interdição", "o trecho sai do\ncálculo das rotas", VERMELHO), ("Rota recalculada", "o traçado muda;\nalternativa apresentada", VERDE)]
x = Inches(0.55)
for i, (t, sub, c) in enumerate(passos):
    retangulo(s, x, Inches(1.8), Inches(2.25), Inches(1.9), c, None)
    texto(s, x, Inches(1.8), Inches(2.25), Inches(1.9), [(t, {"tam": 17, "negrito": True, "cor": RGBColor(255, 255, 255)}), (sub, {"tam": 12, "cor": RGBColor(0xE8, 0xEF, 0xF2)})], alinhar=PP_ALIGN.CENTER, ancora=MSO_ANCHOR.MIDDLE)
    if i < 4: seta(s, x + Inches(2.25), Inches(2.75), x + Inches(2.52), Inches(2.75))
    x += Inches(2.5)
marcadores(s, Inches(0.6), Inches(4.1), Inches(12.2), Inches(2.6), [
    "Relato público nunca é tratado como interdição confirmada.",
    "Histórico de cada decisão (quem, quando, evidência). Correção: nova revisão, sem apagar o histórico.",
    "Persistência em arquivo local: o registro confirmado sobrevive ao reinício (testado em contêiner).",
    "Pendente de aprovação institucional: quem é operador, quais evidências valem, quem guarda a credencial."], tam=16)

# ======================================================================================================= 13. desktop
s = novo("Experiência desktop", "Mapa com painéis flutuantes, proveniência e fallback 2D", "Capturas do painel (Chromium, 1400 px). Porto Alegre: dados sintéticos de demonstração. Rio Grande do Sul: camadas estaduais",
         "O painel de análise tem o mapa como protagonista, com painéis flutuantes por cima. À esquerda, o Rio Grande do Sul, com a cobertura de dados dos municípios e a malha de rodovias. À direita, Porto Alegre, com o risco estimado por trecho "
         "em uma hora à frente, ocorrências e interdições, em 3D com relevo, que é só visual e não entra em nenhum cálculo. A captura de Porto Alegre usa chuva sintética e está identificada. Sem WebGL, o mapa 2D mantém as mesmas funções nos dois territórios. "
         "A aba de proveniência diz o que se pode e o que não se pode afirmar.", "desktop")
foto(s, "painel_rio_grande_do_sul_mapa.png", Inches(0.5), Inches(1.3), Inches(6.2), Inches(4.5), "Rio Grande do Sul: cobertura de dados e rodovias")
foto(s, "painel_porto_alegre_mapa_sintetico.png", Inches(6.9), Inches(1.3), Inches(6.2), Inches(4.5), "Porto Alegre: risco estimado, ocorrências e relevo (demonstração)", sintetico=True)
texto(s, Inches(0.6), Inches(6.0), Inches(12.2), Inches(0.7), "Painel contextual por seleção · assistente · aba de proveniência com o que se pode e o que não se pode afirmar · mapa 2D sem WebGL com as mesmas funções.", tam=14, cor=MUDO)

# ======================================================================================================= 14. PWA
s = novo("Experiência PWA mobile", "Mapa em tela cheia, cartão de orientação e painel inferior", "Capturas do navegador em emulação de celular (390 px e 320 px), com demonstração: dados sintéticos. Não são capturas de aparelho físico",
         "No celular, o mapa é a tela. No alto, um cartão de orientação com a rota e o que há adiante: a distância até o primeiro trecho de atenção e as interdições consideradas. Não há instruções de manobra, porque o backend não as produz. "
         "Uma barra lateral mostra onde a exposição estimada se concentra ao longo da rota. O painel inferior alterna entre resumo e detalhes por botão, sem depender de arrastar. "
         "As capturas são de emulação no Chromium e usam dados sintéticos; o teste em aparelho físico está pendente.", "PWA")
for i, (arq, leg) in enumerate([("pwa_planejar_390.png", "Planejar"), ("pwa_navegacao_compacta_390.png", "Rota e alternativas"), ("pwa_navegacao_detalhes_390.png", "Detalhes"), ("pwa_navegacao_compacta_320.png", "320 px")]):
    foto(s, arq, Inches(0.5 + i * 3.2), Inches(1.25), Inches(3.0), Inches(5.0), leg)
    etiqueta(s, Inches(0.55 + i * 3.2), Inches(1.3), "SINTÉTICO", ALERTA, Inches(1.2))
texto(s, Inches(0.6), Inches(6.35), Inches(12.2), Inches(0.4), "Emulação de navegador; teste em dispositivo físico pendente (docs/qa_mobile_fisico.md).", tam=12, cor=VERMELHO, negrito=True)

# ======================================================================================================= 15. gemini
s = novo("Integração com o Gemini", "Camada de comunicação: reformula, não decide", "docs/validacao_gemini.md; tests/test_linguagem.py; tests/test_servico.py",
         "O Gemini atua apenas como camada de comunicação. Cada pergunta sugerida tem uma resposta determinística montada a partir dos dados; o modelo só reformula. Ele não cria interdições, não altera ocorrências, não calcula rotas "
         "e não vê coordenadas. O texto que ele devolve passa por validação de tamanho e por um filtro que rejeita afirmações como 'rota segura'. Eu testei com chamadas reais em amostra pequena, com respostas entre 1,7 e 2,7 segundos, "
         "inclusive com uma instrução maliciosa na pergunta, que não criou nenhuma interdição. Não medi custo nem volume, e a chuva dessas chamadas era sintética. Sem a chave, o texto padrão funciona e a tela diz isso.", "Gemini")
caixa_texto(s, Inches(0.6), Inches(1.4), Inches(4.0), Inches(5.1), "O que ele faz", [
    "Reformula respostas que o sistema já calculou.",
    "Recebe só resumos agregados: sem coordenadas, origem ou destino.",
    "Sem chave ou com falha: texto padrão, declarado na tela."], cor_titulo=VERDE, tam=14)
caixa_texto(s, Inches(4.8), Inches(1.4), Inches(4.0), Inches(5.1), "O que ele não faz", [
    "Não cria interdições nem muda ocorrências.",
    "Não calcula rotas nem altera parâmetros de risco.",
    "Não inventa chuva; resposta com 'segura' é descartada.",
    "Pergunta livre é tratada como dado não confiável."], cor_titulo=VERMELHO, tam=14)
caixa_texto(s, Inches(9.0), Inches(1.4), Inches(3.8), Inches(5.1), "Validação (amostra pequena)", [
    "Chamadas reais: 1,7 a 2,7 s.",
    "Falhas testadas: chave inválida, timeout, indisponibilidade.",
    "Instrução maliciosa: 0 interdições criadas.",
    "Não medidos: custo, volume, qualidade em escala. Chuva sintética."], cor_titulo=ALERTA, tam=13)

# ======================================================================================================= 16. resultado central
s = novo("Resultado do estudo de mobilidade", "Quanto da cidade deixa de ser alcançável em 30 minutos", "Documentação técnica, seção 6.3 (pipeline de pesquisa; Open-Meteo, OSM, IBGE; GTFS de 2025 para ônibus; bloqueios EPTC)",
         "Este é o resultado central do estudo de pesquisa. Com chuva abaixo de 26,2 milímetros, nenhum bloqueio é atribuído. Entre 26 e 35 milímetros, a cidade perde 3,5 por cento da mobilidade de carro; com 40 a 45 milímetros, esse valor dobra para 7 por cento, "
         "atingindo 190 mil pessoas que perdem ao menos 10 por cento do que alcançam. A média esconde a instabilidade local: em algumas áreas a perda chega a 79 por cento. "
         "Atenção às ressalvas: o ajuste entre chuva e número de bloqueios usa só três datas, e os trechos fechados vêm de uma regra explícita, não de uma previsão validada.", "resultados")
foto(s, "curva_mobilidade_perdida.png", Inches(0.4), Inches(1.25), Inches(7.4), Inches(5.3), "Mobilidade perdida por nível de chuva (degraus: o conjunto de trechos fechados só muda nos níveis calculados)")
caixa_texto(s, Inches(8.0), Inches(1.35), Inches(4.9), Inches(3.1), "Carro, mobilidade perdida na cidade", [
    "26,2 a 35 mm: 3,5% · 81 mil pessoas perdem ≥ 10% · perda local de até 73%.",
    "40 a 45 mm: 7,0% · 190 mil pessoas · perda local de até 79%.",
    "Ônibus e a pé: perdas médias menores (0,3% a 0,5%), com áreas de até 74% a pé."], tam=13)
caixa_texto(s, Inches(8.0), Inches(4.6), Inches(4.9), Inches(1.95), "Ressalvas", [
    "Ajuste chuva × bloqueio com 3 datas; regra explícita, não previsão validada.",
    "GTFS de 2025; bloqueio binário; viés de notificação."], tam=12, cor_titulo=VERMELHO)

# ======================================================================================================= 17. testes
s = novo("Resultados e testes", "O que foi executado e o que cada resultado prova", "docs/qa_relatorio_final.md (execução de 11/11/2026)",
         "A suíte automatizada tem 500 testes aprovados e um ignorado, por falta de um pacote de publicação externa. Há cinco testes de navegador, incluindo a jornada integrada: relato, confirmação do operador e rota recalculada, e o mapa sem WebGL. "
         "O contêiner foi construído e validado, inclusive com chuva real e com a persistência após reinício. O roteamento foi conferido contra a referência. Cada linha tem uma leitura correta ao lado: por exemplo, os testes de navegador são em emulação, "
         "e a auditoria do roteamento valida o algoritmo, não a malha.", "testes")
linhas = [("Verificação", "Resultado", "Leitura correta"),
          ("Suíte automatizada completa", "500 aprovados, 1 ignorado", "Lógica, contratos, HTTP, auditorias e navegador"),
          ("Navegador: painel, PWA, mapa sem WebGL, SW, jornada", "5 aprovados (5 a 7 larguras)", "Chromium em emulação; sem Safari ou aparelho físico"),
          ("Roteamento × caminho de referência", "0 diferenças em 100 pares por modal", "Valida o algoritmo, não a malha"),
          ("Risco × bloqueios documentados", "4 de 19 (2 na hora do reporte)", "Baixo poder de detecção; sem validação em vias"),
          ("Contêiner Docker (chuva real)", "saúde, relato, confirmação, reinício: ok", "Local; nada foi publicado"),
          ("Jornada integrada", "aprovada: o traçado da rota muda", "Dados sintéticos declarados")]
tb = s.shapes.add_table(len(linhas), 3, Inches(0.6), Inches(1.4), Inches(12.2), Inches(4.9)).table
for j, w in enumerate((4.6, 3.6, 4.0)): tb.columns[j].width = Inches(w)
for i, lin in enumerate(linhas):
    for j, t in enumerate(lin):
        c = tb.cell(i, j); c.text = t; r = c.text_frame.paragraphs[0].runs[0]; r.font.size = Pt(14 if i == 0 else 13); r.font.name = FONTE; r.font.bold = (i == 0)
        c.fill.solid(); c.fill.fore_color.rgb = PETROLEO if i == 0 else (CARD if i % 2 else RGBColor(0xEE, 0xF2, 0xF4)); r.font.color.rgb = RGBColor(255, 255, 255) if i == 0 else TINTA

# ======================================================================================================= 18. limitações
s = novo("Limitações e validade dos resultados", "O que o trabalho não demonstra", "docs/seguranca_lgpd.md; docs/qa_relatorio_final.md; docs/sintese_academica.md",
         "Esta é a lâmina que dá credibilidade ao resto. Não validamos a previsão de alagamento por rua: o baseline detectou 4 de 19 eventos. A chuva é regional, de cerca de 10 quilômetros, e o passado é análise de modelo. "
         "O roteamento está correto computacionalmente, mas isso não prova a malha. O Gemini foi testado em amostra pequena. Os dados sintéticos da demonstração não são validação empírica. "
         "Não houve teste em dispositivo físico, e nada foi publicado. E não declaramos conformidade com a LGPD: os controles técnicos existem, mas faltam base legal e processos.", "limites")
itens = [("Risco por trecho", "Sem validação em vias; 4 de 19 eventos detectados.", VERMELHO), ("Chuva", "Regional (~10 km); passado é análise do modelo.", ALERTA),
         ("Roteamento", "Algoritmo validado; a malha OSM, não.", ALERTA), ("Gemini", "Amostra pequena; custo e volume não medidos.", ALERTA),
         ("Dados sintéticos", "Só em testes e demonstração; não são validação.", ALERTA), ("Dispositivo físico", "Não testado (bloqueio externo).", VERMELHO),
         ("Publicação e LGPD", "Nada publicado; conformidade não declarada.", VERMELHO), ("Eventos", "Poucos (19 em 4 datas) e com viés de notificação.", ALERTA)]
for i, (t, d, c) in enumerate(itens):
    x = Inches(0.6 + (i % 2) * 6.2); y = Inches(1.35 + (i // 2) * 1.3)
    retangulo(s, x, y, Inches(6.0), Inches(1.15), CARD)
    b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, Inches(0.12), Inches(1.15)); b.fill.solid(); b.fill.fore_color.rgb = c; b.line.fill.background()
    texto(s, x + Inches(0.25), y + Inches(0.08), Inches(5.6), Inches(0.4), t, tam=15, negrito=True, cor=c)
    texto(s, x + Inches(0.25), y + Inches(0.5), Inches(5.6), Inches(0.6), d, tam=13, cor=TINTA)

# ======================================================================================================= 19. contribuições
s = novo("Contribuições do projeto", None, "Repositório do projeto (branch develop) e documentos em docs/",
         "As contribuições não são uma previsão de alagamento, que não foi validada. São quatro. Primeiro, um pipeline reprodutível que mede a mobilidade perdida com dados abertos. "
         "Segundo, uma plataforma integrada, demonstrável de ponta a ponta. Terceiro, uma disciplina de transparência: cada resultado diz o que prova e o que não prova, e a interface separa observado, previsto, simulado e confirmado. "
         "Quarto, um resultado negativo documentado com rigor, que diz exatamente quais dados faltam.", "contribuições")
cont = [("Pipeline reprodutível", "Mobilidade perdida por nível de chuva com dados abertos e relatórios versionados."), ("Plataforma integrada", "Painel, PWA, roteamento, ocorrências com confirmação humana e assistente, demonstráveis de ponta a ponta."),
        ("Transparência dos limites", "Observado, previsto, simulado e confirmado separados; limitações na interface, não só no texto."), ("Resultado negativo documentado", "Hipótese não confirmada e baixa detecção de eventos, com os dados que faltam para validar.")]
for i, (t, d) in enumerate(cont):
    x = Inches(0.6 + (i % 2) * 6.2); y = Inches(1.5 + (i // 2) * 2.6)
    caixa_texto(s, x, y, Inches(6.0), Inches(2.35), t, d, tam=15, cor_titulo=AZUL)

# ======================================================================================================= 20. conclusão
s = novo("Conclusão", None, "docs/sintese_academica.md; docs/proposta.md, seção 6",
         "Concluindo. A pergunta sobre a perda de mobilidade com chuvas de até 45 milímetros foi respondida no estudo, com as ressalvas dos dados. O trabalho entregou uma ferramenta integrada, demonstrável e reproduzível, que mostra seus próprios limites. "
         "Mas é preciso ser claro: a hipótese de que um modelo treinado supera regras simples não foi confirmada, e a previsão de alagamento por trecho de via não foi validada. Isso não compromete a entrega; delimita o que ela afirma.", "conclusão")
caixa_texto(s, Inches(0.6), Inches(1.4), Inches(6.0), Inches(4.9), "O que se pode afirmar", [
    "A perda de mobilidade com chuvas comuns foi quantificada, com as ressalvas dos dados.",
    "A plataforma integra dados, regras, ocorrências, rotas e comunicação, de ponta a ponta, em ambiente controlado.",
    "O roteamento está correto computacionalmente; uma interdição confirmada altera as rotas.",
    "Os limites aparecem na própria interface."], cor_titulo=VERDE, tam=15)
caixa_texto(s, Inches(6.8), Inches(1.4), Inches(6.0), Inches(4.9), "O que não se pode afirmar", [
    "Que o sistema prevê alagamentos por rua.",
    "Que uma rota é segura.",
    "Que o modelo treinado supera regras simples (não confirmado).",
    "Que a chuva regional vale para uma rua, ou que os resultados valem fora das 4 datas e dos 19 pontos."], cor_titulo=VERMELHO, tam=15)

# ======================================================================================================= 21. próximos passos
s = novo("Próximos passos", "O que falta para validar e para colocar em uso", "docs/qa_relatorio_final.md; docs/operacao_ocorrencias.md; docs/hospedagem.md",
         "Os próximos passos são de dois tipos. Para validar a previsão por trecho, faltam dados: mais ocorrências georreferenciadas, por mais datas e com hora; chuva medida com resolução melhor que 10 quilômetros; rótulos de ausência verificados; "
         "e o histórico real de interdições confirmadas. Para pôr o produto em uso, faltam decisões e ações externas: o teste em dispositivo físico, a aprovação institucional do procedimento do operador e, só então, uma decisão separada sobre publicação.", "próximos passos")
caixa_texto(s, Inches(0.6), Inches(1.4), Inches(6.0), Inches(4.9), "Para validar cientificamente", [
    "Mais ocorrências georreferenciadas, por mais datas e com hora e duração.",
    "Chuva medida (pluviômetro ou radar) com resolução melhor que 10 km.",
    "Rótulos de ausência verificados (dia de chuva forte com via livre).",
    "Histórico de interdições confirmadas em uso real."], cor_titulo=AZUL, tam=15)
caixa_texto(s, Inches(6.8), Inches(1.4), Inches(6.0), Inches(4.9), "Para operar", [
    "Teste em dispositivo físico (Android e iOS).",
    "Aprovação institucional do procedimento do operador.",
    "Avaliação jurídica de dados pessoais (LGPD) e teste de carga e segurança.",
    "Decisão separada sobre publicação e custos de hospedagem."], cor_titulo=ALERTA, tam=15)

SAIDA.parent.mkdir(parents=True, exist_ok=True)
prs.save(SAIDA)
print(f"{_n[0]} slides em {SAIDA}")
