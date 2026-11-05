"""Word 文档排版工具：统一的字体、标题、表格与正文样式。
被 build_industry_docx.py 与 build_proposal_docx.py 共用，保证两份交付物版式一致。
"""
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm

FONT = 'Microsoft YaHei'
INK = '1F2937'
ACCENT = '1D4ED8'
MUTED = '6B7280'


def set_run_font(run, size=10.5, bold=False, color=INK, italic=False):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)
    run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    run._element.rPr.rFonts.set(qn('w:ascii'), FONT)
    run._element.rPr.rFonts.set(qn('w:hAnsi'), FONT)


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def new_document(margin_cm=2.4):
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(margin_cm)
    sec.bottom_margin = Cm(margin_cm)
    sec.left_margin = Cm(margin_cm)
    sec.right_margin = Cm(margin_cm)

    normal = doc.styles['Normal']
    normal.font.name = FONT
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    pf = normal.paragraph_format
    pf.space_after = Pt(4)
    pf.line_spacing = 1.35
    return doc


def title(doc, text, subtitle=None, meta=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_run_font(p.add_run(text), size=20, bold=True, color=INK)
    if subtitle:
        sp = doc.add_paragraph()
        set_run_font(sp.add_run(subtitle), size=11.5, color=ACCENT, bold=True)
    if meta:
        mt = doc.add_paragraph()
        set_run_font(mt.add_run(meta), size=9.5, color=MUTED)
    hrule(doc)


def hrule(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '8')
    bottom.set(qn('w:color'), 'D1D5DB')
    pbdr.append(bottom)
    pPr.append(pbdr)


def h(doc, text, level=1):
    sizes = {1: 15, 2: 12.5, 3: 11}
    colors = {1: INK, 2: ACCENT, 3: INK}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(6)
    set_run_font(p.add_run(text), size=sizes.get(level, 11), bold=True, color=colors.get(level, INK))
    return p


def para(doc, text, size=10.5, color=INK, bold=False, italic=False, space_after=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    set_run_font(p.add_run(text), size=size, color=color, bold=bold, italic=italic)
    return p


def bullets(doc, items, size=10.5):
    for it in items:
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(2)
        set_run_font(p.add_run(it), size=size)


def numbered(doc, items, size=10.5):
    for it in items:
        p = doc.add_paragraph(style='List Number')
        p.paragraph_format.space_after = Pt(2)
        set_run_font(p.add_run(it), size=size)


def table(doc, header, rows, widths=None, font_size=9.5, header_fill='1E293B'):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    hdr = t.rows[0].cells
    for i, cap in enumerate(header):
        shade(hdr[i], header_fill)
        cell_text(hdr[i], cap, size=font_size, bold=True, color='FFFFFF')
    for r in rows:
        cells = t.add_row().cells
        for i, val in enumerate(r):
            cell_text(cells[i], str(val), size=font_size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def cell_text(cell, text, size=9.5, bold=False, color=INK, fill=None):
    cell.text = ''
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.space_before = Pt(1)
    lines = str(text).split('\n')
    for i, line in enumerate(lines):
        if i > 0:
            p = cell.add_paragraph()
            p.paragraph_format.space_after = Pt(1)
        set_run_font(p.add_run(line), size=size, bold=bold, color=color)
    if fill:
        shade(cell, fill)


def caption(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    set_run_font(p.add_run(text), size=9, color=MUTED, italic=True)


def note_box(doc, text, color=None):
    """用单列表格模拟提示框"""
    t = doc.add_table(rows=1, cols=1)
    t.style = 'Table Grid'
    c = t.rows[0].cells[0]
    shade(c, 'F8FAFC')
    cell_text(c, text, size=9.5, color=color or '334155')
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
