"""Gera o DOCX da documentação técnica final a partir de docs/documentacao_tecnica_final.md (a fonte). O .docx é local: não vai para o Git (.gitignore).

    PYTHONPATH=<pasta com python-docx> python tools/gerar_docx_tecnico.py [--saida documentacao_final/Flooding_Mapping_Documentacao_Tecnica.docx]

Entende o subconjunto de Markdown usado no documento: títulos (#, ##), parágrafos, listas com - e 1., tabelas com |, **negrito**, *itálico* e `código`.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[1]
FONTE = RAIZ / "docs/documentacao_tecnica_final.md"
AZUL = RGBColor(0x0B, 0x5D, 0x8F)
TOKEN = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)")


def runs(par, texto: str, negrito: bool = False, tamanho: float | None = None):
    for parte in TOKEN.split(texto):
        if not parte:
            continue
        if parte.startswith("**"):
            r = par.add_run(parte[2:-2]); r.bold = True
        elif parte.startswith("`"):
            r = par.add_run(parte[1:-1]); r.font.name = "Consolas"; r.font.size = Pt(9.5)
        elif parte.startswith("*") and parte.endswith("*") and len(parte) > 2:
            r = par.add_run(parte[1:-1]); r.italic = True
        else:
            r = par.add_run(parte)
        if negrito:
            r.bold = True
        if tamanho and not parte.startswith("`"):
            r.font.size = Pt(tamanho)


def sombrear(celula, cor: str):
    tc = celula._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), cor); tc.append(sh)


def campo(par, instr: str):
    for tipo, texto in (("begin", None), (None, instr), ("end", None)):
        r = par.add_run()
        if tipo:
            f = OxmlElement("w:fldChar"); f.set(qn("w:fldCharType"), tipo); r._r.append(f)
        else:
            t = OxmlElement("w:instrText"); t.set(qn("xml:space"), "preserve"); t.text = texto; r._r.append(t)


def tabela(doc, linhas: list[list[str]]):
    t = doc.add_table(rows=len(linhas), cols=len(linhas[0]))
    t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, linha in enumerate(linhas):
        for j, txt in enumerate(linha):
            c = t.cell(i, j); c.text = ""
            p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(2)
            runs(p, txt, negrito=(i == 0), tamanho=9.5)
            if i == 0:
                sombrear(c, "0B5D8F")
                for r in p.runs:
                    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            elif i % 2 == 0:
                sombrear(c, "EAF2F6")
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def gerar(saida: Path) -> Path:
    linhas = FONTE.read_text(encoding="utf-8").splitlines()
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.2); sec.top_margin = Cm(2.2); sec.bottom_margin = Cm(2.0)
    est = doc.styles["Normal"]; est.font.name = "Calibri"; est.font.size = Pt(11)
    est.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri"); est.paragraph_format.space_after = Pt(6); est.paragraph_format.line_spacing = 1.12
    for nome, tam in (("Heading 1", 16), ("Heading 2", 13)):
        h = doc.styles[nome]; h.font.name = "Calibri"; h.font.size = Pt(tam); h.font.bold = True; h.font.color.rgb = AZUL
        h.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri"); h.paragraph_format.space_before = Pt(16 if tam == 16 else 12); h.paragraph_format.keep_with_next = True
    # rodapé com numeração
    rod = sec.footer.paragraphs[0]; rod.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = rod.add_run("Flooding Mapping · Documentação técnica final · página "); r.font.size = Pt(9)
    campo(rod, "PAGE")
    # capa
    for _ in range(5):
        doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run("FLOODING MAPPING"); r.bold = True; r.font.size = Pt(34); r.font.color.rgb = AZUL
    p = doc.add_paragraph(); r = p.add_run("Documentação técnica final"); r.font.size = Pt(20)
    p = doc.add_paragraph(); r = p.add_run("Escoamento superficial potencial em Porto Alegre: arquitetura, camadas, fontes, publicação e limitações"); r.font.size = Pt(13); r.italic = True
    for _ in range(3):
        doc.add_paragraph()
    for t in ("Helena de Oliveira Valanera", "FTL Brasil 2026 Space Tech Bootcamp · Projeto final", "Estado em 27 de novembro de 2026", "helena.valanera@gmail.com"):
        doc.add_paragraph(t)
    doc.add_page_break()
    i, primeiro_titulo = 0, True
    while i < len(linhas):
        ln = linhas[i]
        if ln.startswith("# "):
            i += 1
            continue                                   # o título está na capa
        if ln.startswith("## "):
            if not primeiro_titulo:
                pass
            primeiro_titulo = False
            doc.add_heading(ln[3:].strip(), level=1)
        elif ln.startswith("|"):
            bloco = []
            while i < len(linhas) and linhas[i].startswith("|"):
                if not re.match(r"^\|[\s\-|:]+\|$", linhas[i]):
                    bloco.append([c.strip() for c in linhas[i].strip().strip("|").split("|")])
                i += 1
            tabela(doc, bloco)
            continue
        elif re.match(r"^- ", ln):
            p = doc.add_paragraph(style="List Bullet"); runs(p, ln[2:])
        elif re.match(r"^\d+\. ", ln):
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Cm(0.9); p.paragraph_format.first_line_indent = Cm(-0.6); runs(p, ln)    # numeração literal: a lista automática do Word continuaria entre seções
        elif ln.startswith("Autora:"):
            pass                                       # já está na capa
        elif ln.strip():
            p = doc.add_paragraph(); runs(p, ln.strip())
        i += 1
    saida.parent.mkdir(parents=True, exist_ok=True)
    doc.core_properties.author = "Helena de Oliveira Valanera"; doc.core_properties.title = "Flooding Mapping: documentação técnica final"
    doc.save(saida)
    return saida


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--saida", type=Path, default=RAIZ / "documentacao_final/Flooding_Mapping_Documentacao_Tecnica.docx")
    a = ap.parse_args()
    print(gerar(a.saida))
