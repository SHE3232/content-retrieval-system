from __future__ import annotations

import json
import io
import math
import os
import sys
import zipfile
from pathlib import Path

from lxml import etree
from PIL import Image, ImageChops, ImageDraw
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "docs" / "week2" / "reports"
WORK_DIR = ROOT / "tmp" / "week2-deliverables"
ASSET_DIR = WORK_DIR / "assets"
DATE = "2026-07-19"

sys.path.insert(0, str(ROOT / "tmp" / "docx"))
import build_architecture_docx as base  # noqa: E402


ACCENT = "000000"
ACCENT_DARK = "000000"
INK = "000000"
MUTED = "000000"
LIGHT_BLUE = "FFFFFF"
LIGHT_GRAY = "FFFFFF"
LIGHT_GREEN = "FFFFFF"
LIGHT_AMBER = "FFFFFF"
BORDER = "000000"
RISK_RED = "000000"
CAUTION = "000000"
WHITE = "FFFFFF"
FONT_NAME = "Times New Roman"


def enforce_docx_visual_spec(path: Path) -> None:
    """Force every Word text style/run to Times New Roman and black on white."""
    tmp_path = path.with_suffix(".spec.tmp.docx")
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    theme_attrs = {
        qn("w:asciiTheme"), qn("w:hAnsiTheme"), qn("w:eastAsiaTheme"), qn("w:cstheme"),
        qn("w:themeColor"), qn("w:themeTint"), qn("w:themeShade"),
        qn("w:themeFill"), qn("w:themeFillTint"), qn("w:themeFillShade"),
    }
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename.startswith("word/") and item.filename.endswith(".xml"):
                root = etree.fromstring(data)
                if item.filename.startswith("word/theme/"):
                    for color_group in root.xpath(".//a:clrScheme/*", namespaces={"a": a_ns}):
                        value = "FFFFFF" if etree.QName(color_group).localname in {"lt1", "lt2"} else "000000"
                        for child in list(color_group):
                            color_group.remove(child)
                        etree.SubElement(color_group, f"{{{a_ns}}}srgbClr", val=value)
                else:
                    for element in root.iter():
                        if element.tag == qn("w:rFonts"):
                            for script in ("ascii", "hAnsi", "eastAsia", "cs"):
                                element.set(qn(f"w:{script}"), FONT_NAME)
                        if element.tag == qn("w:color"):
                            element.set(qn("w:val"), "000000")
                        elif element.tag == qn("w:shd"):
                            element.set(qn("w:fill"), "FFFFFF")
                            element.set(qn("w:color"), "auto")
                        elif element.tag == qn("w:highlight"):
                            element.set(qn("w:val"), "none")
                        for attr in list(element.attrib):
                            if attr in theme_attrs:
                                del element.attrib[attr]
                            elif attr == qn("w:color") and element.tag != qn("w:shd"):
                                element.set(attr, "000000")
                            elif attr == qn("w:fill"):
                                element.set(attr, "FFFFFF")
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            target.writestr(item, data)
    os.replace(tmp_path, path)


def validate_docx_visual_spec(path: Path) -> None:
    """Fail generation if the final package violates the project visual standard."""
    forbidden_theme_attrs = {
        qn("w:asciiTheme"), qn("w:hAnsiTheme"), qn("w:eastAsiaTheme"), qn("w:cstheme"),
        qn("w:themeColor"), qn("w:themeTint"), qn("w:themeShade"),
        qn("w:themeFill"), qn("w:themeFillTint"), qn("w:themeFillShade"),
    }
    with zipfile.ZipFile(path, "r") as package:
        for item in package.infolist():
            if item.filename.startswith("word/") and item.filename.endswith(".xml") and not item.filename.startswith("word/theme/"):
                root = etree.fromstring(package.read(item.filename))
                for element in root.iter():
                    if element.tag == qn("w:rFonts"):
                        for script in ("ascii", "hAnsi", "eastAsia", "cs"):
                            if element.get(qn(f"w:{script}")) != FONT_NAME:
                                raise ValueError(f"{path.name}: non-standard font in {item.filename}")
                    if element.tag == qn("w:color") and element.get(qn("w:val")) != "000000":
                        raise ValueError(f"{path.name}: non-black text color in {item.filename}")
                    if element.tag == qn("w:shd") and element.get(qn("w:fill")) != "FFFFFF":
                        raise ValueError(f"{path.name}: non-white shading in {item.filename}")
                    for attr in element.attrib:
                        if attr in forbidden_theme_attrs:
                            raise ValueError(f"{path.name}: unresolved theme styling in {item.filename}")
                        if attr == qn("w:color") and element.tag != qn("w:shd") and element.get(attr) != "000000":
                            raise ValueError(f"{path.name}: non-black line color in {item.filename}")
                        if attr == qn("w:fill") and element.get(attr) != "FFFFFF":
                            raise ValueError(f"{path.name}: non-white fill in {item.filename}")
            elif item.filename.startswith("word/media/"):
                try:
                    with Image.open(io.BytesIO(package.read(item.filename))) as image:
                        rgb_image = image.convert("RGB")
                        red, green, blue = rgb_image.split()
                        if ImageChops.difference(red, green).getbbox() or ImageChops.difference(green, blue).getbbox():
                            raise ValueError(f"{path.name}: color image found in {item.filename}")
                except OSError:
                    pass


def configure_styles(doc: Document) -> None:
    """Apply the project's Times New Roman, black-on-white DOCX standard."""
    normal = doc.styles["Normal"]
    normal.font.name = FONT_NAME
    normal.font.size = Pt(11)
    normal.font.color.rgb = base.rgb(INK)
    for script in ("ascii", "hAnsi", "eastAsia", "cs"):
        normal._element.rPr.rFonts.set(qn(f"w:{script}"), FONT_NAME)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.10

    specs = {
        "Title": (28, INK, 0, 8, True),
        "Subtitle": (14, MUTED, 0, 8, False),
        "Heading 1": (16, ACCENT, 16, 8, True),
        "Heading 2": (13, ACCENT, 12, 6, True),
        "Heading 3": (12, ACCENT_DARK, 8, 4, True),
        "Caption": (9, MUTED, 4, 8, False),
    }
    for name, (size, color, before, after, bold) in specs.items():
        style = doc.styles[name]
        style.font.name = FONT_NAME
        style.font.size = Pt(size)
        style.font.color.rgb = base.rgb(color)
        style.font.bold = bold
        for script in ("ascii", "hAnsi", "eastAsia", "cs"):
            style._element.rPr.rFonts.set(qn(f"w:{script}"), FONT_NAME)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.10
        style.paragraph_format.keep_with_next = True


def add_field(paragraph, instruction: str, display_text: str) -> None:
    base.add_field(paragraph, instruction, display_text)


def configure_document(doc: Document, short_title: str) -> None:
    configure_styles(doc)
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.right_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)
    section.different_first_page_header_footer = True
    doc.settings.odd_and_even_pages_header_footer = False

    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hp.paragraph_format.space_after = Pt(0)
    base.set_run(hp.add_run("离线无障碍多模态本地内容检索系统"), size=8.5, bold=True, color=MUTED)
    base.set_run(hp.add_run(f"    第 2 周 · {short_title}"), size=8.5, color=MUTED)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.paragraph_format.space_before = Pt(0)
    base.set_run(fp.add_run(f"{short_title}  |  第 "), size=8.5, color=MUTED)
    add_field(fp, "PAGE", "1")
    base.set_run(fp.add_run(" 页 / 共 "), size=8.5, color=MUTED)
    add_field(fp, "NUMPAGES", "1")
    base.set_run(fp.add_run(" 页"), size=8.5, color=MUTED)


def add_cover(
    doc: Document,
    *,
    title: str,
    subtitle: str,
    document_no: str,
    status: str,
    scope: str,
    summary: str,
) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(40)
    p.paragraph_format.space_after = Pt(8)
    base.set_run(p.add_run("WEEK 2 · FORMAL DELIVERABLE"), size=10.5, bold=True, color=ACCENT)

    title_p = doc.add_paragraph(style="Title")
    title_p.paragraph_format.space_after = Pt(8)
    base.set_run(title_p.add_run(title), size=28, bold=True, color=INK)

    subtitle_p = doc.add_paragraph(style="Subtitle")
    subtitle_p.paragraph_format.space_after = Pt(22)
    base.set_run(subtitle_p.add_run(subtitle), size=14, color=ACCENT_DARK)

    metadata = [
        ("文档编号", document_no),
        ("文档状态", status),
        ("基线日期", DATE),
        ("项目阶段", "第 2 周：系统结构与文件解析基础"),
        ("覆盖范围", scope),
    ]
    for label, value in metadata:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        base.set_run(p.add_run(f"{label}："), size=10, bold=True, color=ACCENT_DARK)
        base.set_run(p.add_run(value), size=10, color=INK)

    add_callout(doc, "交付摘要", summary, color=ACCENT, fill=LIGHT_BLUE)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(26)
    base.set_run(p.add_run("编制依据：当前仓库代码、自动化测试、数据集清单与项目周次计划"), size=9, italic=True, color=MUTED)
    doc.add_page_break()


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_paragraph(style=f"Heading {level}")
    color = ACCENT if level < 3 else ACCENT_DARK
    size = {1: 16, 2: 13, 3: 12}[level]
    base.set_run(p.add_run(text), size=size, bold=True, color=color)


def add_para(doc: Document, text: str, *, bold_label: str | None = None) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.10
    if bold_label:
        base.set_run(p.add_run(bold_label), size=11, bold=True, color=INK)
    base.add_markdown_runs(p, text, size=11, color=INK)


def add_callout(doc: Document, label: str, text: str, *, color: str, fill: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.left_indent = Inches(0.12)
    p.paragraph_format.right_indent = Inches(0.08)
    p.paragraph_format.line_spacing = 1.10
    ppr = p._p.get_or_add_pPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    ppr.append(shading)
    borders = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "18")
    left.set(qn("w:color"), color)
    borders.append(left)
    ppr.append(borders)
    base.set_run(p.add_run(f"{label}  "), size=10.5, bold=True, color=color)
    base.add_markdown_runs(p, text, size=10.5, color=INK)


def create_numbering(doc: Document, fmt: str) -> int:
    numbering = doc.part.numbering_part.element
    abstract_ids = [int(x.get(qn("w:abstractNumId"))) for x in numbering.findall(qn("w:abstractNum"))]
    num_ids = [int(x.get(qn("w:numId"))) for x in numbering.findall(qn("w:num"))]
    abstract_id = max(abstract_ids, default=0) + 1
    num_id = max(num_ids, default=0) + 1

    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    multi = OxmlElement("w:multiLevelType")
    multi.set(qn("w:val"), "singleLevel")
    abstract.append(multi)
    lvl = OxmlElement("w:lvl")
    lvl.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    num_fmt = OxmlElement("w:numFmt")
    num_fmt.set(qn("w:val"), fmt)
    lvl_text = OxmlElement("w:lvlText")
    lvl_text.set(qn("w:val"), "•" if fmt == "bullet" else "%1.")
    suff = OxmlElement("w:suff")
    suff.set(qn("w:val"), "tab")
    ppr = OxmlElement("w:pPr")
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "num")
    tab.set(qn("w:pos"), "720")
    tabs.append(tab)
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "720")
    ind.set(qn("w:hanging"), "360")
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:after"), "160")
    spacing.set(qn("w:line"), "280")
    spacing.set(qn("w:lineRule"), "auto")
    ppr.extend([tabs, ind, spacing])
    lvl.extend([start, num_fmt, lvl_text, suff, ppr])
    abstract.append(lvl)
    first_num_index = next((i for i, child in enumerate(numbering) if child.tag == qn("w:num")), len(numbering))
    numbering.insert(first_num_index, abstract)

    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(num_id))
    ref = OxmlElement("w:abstractNumId")
    ref.set(qn("w:val"), str(abstract_id))
    num.append(ref)
    numbering.append(num)
    return num_id


def apply_numbering(paragraph, num_id: int) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    num_pr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    num = OxmlElement("w:numId")
    num.set(qn("w:val"), str(num_id))
    num_pr.extend([ilvl, num])
    ppr.append(num_pr)


def add_bullets(doc: Document, items: list[str]) -> None:
    num_id = create_numbering(doc, "bullet")
    for item in items:
        p = doc.add_paragraph()
        apply_numbering(p, num_id)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.line_spacing = 1.167
        base.add_markdown_runs(p, item, size=11, color=INK)


def add_numbered(doc: Document, items: list[str]) -> None:
    num_id = create_numbering(doc, "decimal")
    for item in items:
        p = doc.add_paragraph()
        apply_numbering(p, num_id)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.line_spacing = 1.167
        base.add_markdown_runs(p, item, size=11, color=INK)


def set_cell_margins(cell, top=80, bottom=80, start=120, end=120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("bottom", bottom), ("start", start), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def add_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    *,
    weights: list[float],
    center_cols: set[int] | None = None,
    font_size: float = 9.0,
) -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    center_cols = center_cols or set()
    all_rows = [headers] + rows
    for ridx, values in enumerate(all_rows):
        row = table.rows[ridx]
        base.prevent_row_split(row)
        if ridx == 0:
            base.set_repeat_table_header(row)
        for cidx, value in enumerate(values):
            cell = row.cells[cidx]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            base.set_cell_borders(cell, color=BORDER, size="6")
            if ridx == 0:
                base.set_cell_shading(cell, LIGHT_GRAY)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.08
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if cidx in center_cols or ridx == 0 else WD_ALIGN_PARAGRAPH.LEFT
            base.add_markdown_runs(p, value, size=font_size, color=INK)
            for run in p.runs:
                if ridx == 0:
                    run.bold = True
    widths = base.column_widths_from_weights(weights, 9360)
    base.apply_table_geometry(
        table,
        widths,
        table_width_dxa=9360,
        indent_dxa=120,
        cell_margins_dxa={"top": 80, "bottom": 80, "start": 120, "end": 120},
    )
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)


def add_code(doc: Document, text: str) -> None:
    lines = text.strip("\n").splitlines()
    base.add_code_block(doc, lines)
    doc.paragraphs[-1].paragraph_format.keep_together = True


def add_figure(doc: Document, path: Path, caption: str, alt: str, width=6.15) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    shape = p.add_run().add_picture(str(path), width=Inches(width))
    base.set_image_alt(shape, caption, alt)
    cap = doc.add_paragraph(style="Caption")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    base.set_run(cap.add_run(caption), size=9, color=MUTED)


def diagram_box(draw: ImageDraw.ImageDraw, xy, title, subtitle, status, *, fill, outline) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline=outline, width=4)
    title_font = base.find_font(36, bold=True)
    sub_font = base.find_font(26)
    badge_font = base.find_font(18, bold=True)
    title_lines = base.wrap_text(draw, title, title_font, x2 - x1 - 32)
    sub_lines = base.wrap_text(draw, subtitle, sub_font, x2 - x1 - 32)
    y = y1 + 24
    for line in title_lines:
        w = draw.textlength(line, font=title_font)
        draw.text(((x1 + x2 - w) / 2, y), line, font=title_font, fill="#000000")
        y += 44
    for line in sub_lines:
        w = draw.textlength(line, font=sub_font)
        draw.text(((x1 + x2 - w) / 2, y), line, font=sub_font, fill="#000000")
        y += 33
    badge_w = draw.textlength(status, font=badge_font) + 24
    draw.rounded_rectangle((x2 - badge_w - 12, y2 - 34, x2 - 12, y2 - 10), radius=8, fill="white", outline="black", width=2)
    draw.text((x2 - badge_w, y2 - 32), status, font=badge_font, fill="black")


def build_architecture_diagram(path: Path) -> None:
    img = Image.new("RGB", (2200, 1700), "white")
    d = ImageDraw.Draw(img)
    boxes = {
        "flutter": (760, 50, 1440, 175),
        "api": (690, 245, 1510, 385),
        "job": (100, 470, 660, 610),
        "batch": (820, 470, 1380, 610),
        "routes": (1540, 470, 2100, 610),
        "registry": (820, 690, 1380, 830),
        "txt": (40, 930, 460, 1070),
        "pdf": (550, 930, 970, 1070),
        "docx": (1060, 930, 1480, 1070),
        "image": (1570, 930, 2160, 1070),
        "tika": (1060, 1150, 1480, 1285),
        "models": (650, 1360, 1450, 1500),
        "embed": (1510, 1360, 1815, 1500),
        "chroma": (1870, 1360, 2160, 1500),
    }
    planned = {"flutter", "embed", "chroma"}
    external = {"tika"}
    labels = {
        "flutter": ("Flutter UI / LocalBackendClient", "脚手架存在；IPC 客户端尚未接入"),
        "api": ("FastAPI Application", "健康检查、任务创建与任务查询"),
        "job": ("InMemoryIngestionJobStore", "线程安全快照；进程重启后丢失"),
        "batch": ("BatchIngestionService", "路径展开、授权、大小限制、去重、顺序解析"),
        "routes": ("HTTP Routes", "GET live/ready · POST/GET jobs"),
        "registry": ("ParserRegistry", "按 MIME 或扩展名路由；尚无签名探测"),
        "txt": ("TXT Parser", "BOM + 严格 UTF-8"),
        "pdf": ("PDF Parser", "pypdfium2 分页文本"),
        "docx": ("DOCX Parser", "Tika HTTP 适配器"),
        "image": ("Image Parser", "Pillow 解码与安全 EXIF"),
        "tika": ("Apache Tika 3.3.1", "本机 127.0.0.1:9998"),
        "models": ("ParseResult / BatchResult", "当前统一数据契约与批量汇总"),
        "embed": ("Embedding", "第 3 周"),
        "chroma": ("ChromaDB", "第 4 周"),
    }
    for key, box in boxes.items():
        if key in planned:
            fill, outline, status = "#FFFFFF", "#000000", "计划"
        elif key in external:
            fill, outline, status = "#FFFFFF", "#000000", "外部依赖"
        elif key == "models":
            fill, outline, status = "#FFFFFF", "#000000", "已实现"
        else:
            fill, outline, status = "#FFFFFF", "#000000", "已实现"
        diagram_box(d, box, *labels[key], status, fill=fill, outline=outline)

    def top(key):
        x1, y1, x2, _ = boxes[key]
        return ((x1 + x2) / 2, y1)

    def bottom(key):
        x1, _, x2, y2 = boxes[key]
        return ((x1 + x2) / 2, y2)

    base.arrow(d, bottom("flutter"), top("api"), color="#000000", dashed=True)
    base.arrow(d, bottom("api"), top("batch"))
    base.arrow(d, (boxes["api"][0] + 120, boxes["api"][3]), top("job"))
    base.arrow(d, (boxes["api"][2] - 120, boxes["api"][3]), top("routes"))
    base.arrow(d, bottom("batch"), top("registry"))
    for parser in ("txt", "pdf", "docx", "image"):
        base.arrow(d, bottom("registry"), top(parser))
        base.arrow(d, bottom(parser), top("models"))
    base.arrow(d, bottom("docx"), top("tika"), color="#000000")
    base.arrow(d, (boxes["models"][2], 1430), (boxes["embed"][0], 1430), color="#000000", dashed=True)
    base.arrow(d, (boxes["embed"][2], 1430), (boxes["chroma"][0], 1430), color="#000000", dashed=True)

    legend_font = base.find_font(21)
    d.text((70, 1590), "实线：当前后端主链路    虚线：尚未接入/后续周扩展", font=legend_font, fill="#000000")
    d.text((1540, 655), "当前 API 由 ASGI 自动化测试验证；网络绑定与令牌尚未验收", font=legend_font, fill="#000000")
    img.save(path, dpi=(220, 220))


def sequence_diagram_layout() -> dict[str, object]:
    return {
        "canvas": (2400, 1800),
        "names": ["API 调用方", "FastAPI", "Job Store", "后台任务", "Batch Service", "Registry / Parser"],
        "xs": [170, 580, 990, 1400, 1810, 2230],
        "header_width": 320,
        "lifeline_bottom": 1450,
        "title_font_size": 38,
        "message_font_size": 32,
        "note_font_size": 30,
        "events": [
            (230, 0, 1, "POST /v1/ingestion/jobs"),
            (325, 1, 2, "create() → queued"),
            (420, 1, 3, "asyncio.create_task"),
            (515, 1, 0, "202 · job_id · queued"),
            (620, 3, 2, "mark_running"),
            (715, 3, 4, "asyncio.to_thread(parse_paths)"),
            (810, 4, 5, "逐文件顺序 resolve / parse"),
            (905, 5, 4, "ParseResult / ParseError"),
            (1000, 4, 3, "BatchResult"),
            (1095, 3, 2, "complete 或 fail"),
            (1210, 0, 1, "GET /v1/ingestion/jobs/{job_id}"),
            (1325, 1, 0, "状态、计数、结果、错误、跳过项"),
        ],
        "note_box": (120, 1510, 2280, 1750),
        "notes": [
            "批内解析为顺序执行",
            "运行中查询尚不返回实时文件计数",
            "取消、结果分页、关闭接口未实现",
        ],
    }


def build_sequence_diagram(path: Path) -> None:
    layout = sequence_diagram_layout()
    img = Image.new("RGB", layout["canvas"], "white")
    d = ImageDraw.Draw(img)
    names = layout["names"]
    xs = layout["xs"]
    title_font = base.find_font(layout["title_font_size"], bold=True)
    msg_font = base.find_font(layout["message_font_size"])

    for x, name in zip(xs, names):
        half = layout["header_width"] / 2
        d.rounded_rectangle((x - half, 35, x + half, 135), radius=14, fill="#FFFFFF", outline="#000000", width=4)
        tw = d.textlength(name, font=title_font)
        d.text((x - tw / 2, 63), name, font=title_font, fill="#000000")
        d.line((x, 135, x, layout["lifeline_bottom"]), fill="#000000", width=4)

    for y, source, target, label in layout["events"]:
        base.arrow(d, (xs[source], y), (xs[target], y), width=5)
        center = (xs[source] + xs[target]) / 2
        text_width = d.textlength(label, font=msg_font)
        d.rounded_rectangle(
            (center - text_width / 2 - 12, y - 40, center + text_width / 2 + 12, y - 4),
            radius=6,
            fill="#FFFFFF",
        )
        d.text((center - text_width / 2, y - 39), label, font=msg_font, fill="#000000")

    left, top, right, bottom = layout["note_box"]
    d.rounded_rectangle((left, top, right, bottom), radius=20, fill="#FFFFFF", outline="#000000", width=4)
    d.text((left + 35, top + 22), "当前行为（第 2 周）", font=base.find_font(32, bold=True), fill="#000000")
    note_font = base.find_font(layout["note_font_size"])
    for index, note in enumerate(layout["notes"]):
        d.text((left + 45, top + 82 + index * 48), "• " + note, font=note_font, fill="#000000")

    img.save(path, dpi=(220, 220))


def init_doc(title: str, short_title: str, document_no: str, scope: str, summary: str) -> Document:
    doc = Document()
    configure_document(doc, short_title)
    doc.core_properties.title = title
    doc.core_properties.subject = "离线无障碍多模态本地内容检索系统第 2 周交付物"
    doc.core_properties.author = "项目组"
    doc.core_properties.keywords = "FastAPI, 文件解析, Tika, PDFium, Pillow, 第2周"
    add_cover(
        doc,
        title=title,
        subtitle="离线无障碍多模态本地内容检索系统",
        document_no=document_no,
        status="正式交付版 v1.0",
        scope=scope,
        summary=summary,
    )
    return doc


def build_architecture_doc() -> Path:
    output = REPORT_DIR / "01_系统架构设计.docx"
    diagram = ASSET_DIR / "current-architecture.png"
    sequence = ASSET_DIR / "current-ingestion-sequence.png"
    build_architecture_diagram(diagram)
    build_sequence_diagram(sequence)
    doc = init_doc(
        "系统架构设计",
        "系统架构设计",
        "W2-ARCH-01",
        "架构图、模块职责、数据流、IPC、异常处理与实际完成状态",
        "第 2 周后端解析主链路已经形成并通过自动化验证；Flutter IPC 客户端、取消、关闭、令牌鉴权、动态端口与 Embedding/ChromaDB 接入仍属于后续工作。",
    )

    add_heading(doc, "1. 文档目的与基线")
    add_para(doc, "本文档把第 2 周原有“实现前架构基线”更新为**当前仓库实际架构**。所有“已实现”结论均能在 `backend/src/content_retrieval/` 或自动化测试中找到对应依据；未落地能力明确标为“部分完成”或“计划中”。")
    add_table(doc, ["项", "说明"], [
        ["基线日期", DATE],
        ["当前主链路", "本地路径 → FastAPI 任务 → BatchIngestionService → ParserRegistry → 具体 Parser → ParseResult/BatchResult"],
        ["支持格式", "TXT、PDF、DOCX、JPG/JPEG、PNG"],
        ["边界", "本周不包含向量生成、ChromaDB 检索、Flutter 页面接入、OCR 和发布打包"],
    ], weights=[0.23, 0.77], center_cols={0}, font_size=9.2)
    add_callout(doc, "结论", "后端文件解析与最小任务 API 已可独立使用；系统尚未达到“桌面端可操作 MVP”，因为前端 IPC 和运行期管理能力未接通。", color=ACCENT, fill=LIGHT_BLUE)
    add_heading(doc, "1.1 架构约束原则", 2)
    add_bullets(doc, [
        "本地优先：解析器只读取用户授权的本地路径，不接受远程 URL。",
        "职责隔离：API 管理契约，服务管理批次，解析器只负责格式内容提取。",
        "确定性与可复现：路径排序、编码规则和 SHA-256 去重保持稳定。",
        "安全失败：单文件错误不终止批次，未知异常不直接暴露第三方内部文本。",
    ])

    add_heading(doc, "2. 总体架构与依赖方向")
    add_figure(doc, diagram, "图 1  当前系统架构与后续扩展边界", "当前系统以 FastAPI 为入口，使用内存任务仓储和批量解析服务，经注册表路由到 TXT、PDF、DOCX 和图片解析器；DOCX 依赖本机 Tika。Flutter、Embedding 和 ChromaDB 标为计划。")
    add_para(doc, "代码依赖方向为 `api → services → domain/parsers`。API 层不直接调用 PDFium、Pillow 或 Tika；外部库被限制在具体解析器与 Tika 适配器内。`ParseResult` 和 `BatchResult` 是当前统一契约，原设计中的 `ParsedDocument + segments/assets` 尚未实现。")
    add_bullets(doc, [
        "蓝色模块属于当前后端实现；黄色表示受管范围之外的本机依赖；灰色表示后续周能力。",
        "当前任务 API 已验证请求响应契约，但尚未验证真实网络绑定、启动握手和鉴权。",
        "Embedding 将消费解析结果，不应反向改变 TXT/PDF/DOCX/图片解析器的职责。",
    ])

    doc.add_page_break()
    add_heading(doc, "3. 模块职责与实际完成状态")
    add_table(doc, ["模块", "职责", "状态", "当前事实 / 限制"], [
        ["Flutter 前端", "文件选择、进度、错误展示", "部分完成", "桌面脚手架存在；LocalBackendClient、导入页面和后端进程管理未实现"],
        ["FastAPI 应用", "装配服务、注册路由", "已完成", "提供 2 个健康接口和 2 个任务接口；默认最大文件 100 MiB"],
        ["Job Store", "保存任务状态快照", "已完成", "线程安全、进程内存储；重启后丢失，无取消状态"],
        ["BatchIngestionService", "路径展开、授权、大小检查、SHA-256 去重、错误隔离", "已完成", "批内顺序解析；没有工作队列、并发上限和实时进度"],
        ["ParserRegistry", "按 MIME/扩展名选择解析器", "已完成", "支持大小写归一化；未做文件签名探测和格式不匹配检查"],
        ["TXT Parser", "确定性文本解码", "已完成", "BOM 识别；无 BOM 严格 UTF-8；输出编码、换行和字符数"],
        ["PDF Parser", "分页文本抽取", "已完成", "pypdfium2；页文本保存在 metadata.page_texts；无 OCR"],
        ["DOCX Parser", "正文和元数据抽取", "已完成", "PUT Tika /rmeta/text；白名单元数据；依赖独立 Tika 进程"],
        ["Image Parser", "解码验证和元数据", "已完成", "JPG/JPEG/PNG；验证全部帧；只保留描述与方向 EXIF"],
        ["Embedding / Chroma", "向量生成与检索", "计划中", "依赖和烟测基础存在，但未接入解析主链路"],
    ], weights=[0.17, 0.28, 0.13, 0.42], center_cols={0, 2}, font_size=8.3)

    add_heading(doc, "4. 当前数据流")
    add_figure(doc, sequence, "图 2  当前任务创建、解析与查询时序", "调用方创建任务后立即收到 queued；后台任务切换 running，在工作线程中顺序解析文件并写入终态快照；调用方通过 GET 查询状态和结果。")
    add_numbered(doc, [
        "调用方提交绝对路径、授权根目录和 `recursive` 选项；Pydantic 拒绝空列表。",
        "FastAPI 创建 `queued` 任务并用 `asyncio.create_task` 启动后台协程，立即返回 `202`。",
        "后台协程把阻塞的 `parse_paths()` 放入 `asyncio.to_thread`，避免阻塞事件循环。",
        "服务解析和规范化输入路径，使用 `Path.is_relative_to()` 校验授权根目录，并按稳定路径顺序展开目录。",
        "每个候选文件依次完成格式路由、大小检查、SHA-256 内容去重和具体解析；单文件异常转为受控错误，批次继续。",
        "任务完成后保存 `completed` 或 `completed_with_errors` 快照；未捕获的任务级异常保存为 `failed`。",
    ])

    add_heading(doc, "5. 当前统一数据契约")
    add_table(doc, ["结构", "关键字段", "作用"], [
        ["ParseResult", "file_id、path、name、mime_type、modality、size_bytes、modified_at、text、page_count、width、height、metadata、warnings", "单文件成功结果；file_id 为内容 SHA-256"],
        ["BatchItem", "path、status、result/error/skip", "保持候选文件顺序并表示单项结果"],
        ["SkippedFile", "path、reason、file_id、duplicate_of", "表示目录中不支持格式或内容重复"],
        ["BatchResult", "results、errors、skips、items", "汇总 total/succeeded/skipped/failed"],
    ], weights=[0.18, 0.48, 0.34], center_cols={0}, font_size=8.6)
    add_callout(doc, "与原设计的差异", "当前模型没有 `schema_version`、`segments`、`assets` 和 `parsed_at`；PDF 页级来源暂存在 `metadata.page_texts`。第 3 周在设计 Embedding 输入时应先定义兼容迁移方式。", color=CAUTION, fill=LIGHT_AMBER)

    add_heading(doc, "6. IPC 设计：当前可用与目标差距")
    add_table(doc, ["方面", "当前状态", "后续要求"], [
        ["协议", "FastAPI HTTP/JSON 契约已实现，自动化测试使用 ASGITransport", "补充真实 127.0.0.1 网络端到端烟测"],
        ["路由", "live、ready、创建任务、查询任务", "取消、结果分页、系统关闭"],
        ["端口绑定", "应用对象本身不决定监听地址", "启动器显式绑定 127.0.0.1，发布态使用动态端口"],
        ["鉴权", "未实现 Bearer 会话令牌", "Flutter 启动后端时生成一次性令牌并保护 /v1 路由"],
        ["进程生命周期", "Tika 脚本可独立启动；无 Python/Tika supervisor", "ready 握手、子进程核验、受控关闭与崩溃恢复"],
        ["任务进度", "queued/running 阶段返回零计数；终态返回完整结果", "增量计数、失败项与可访问进度通知"],
    ], weights=[0.20, 0.38, 0.42], center_cols={0}, font_size=8.8)
    add_para(doc, "Tika 适配器固定访问 `http://127.0.0.1:9998` 并设置 `trust_env=False`，避免 Windows 系统代理截获回环请求。FastAPI 的回环绑定和会话令牌尚未由代码保证，不能把“本地设计目标”误写成已完成安全能力。")

    add_heading(doc, "7. 异常处理")
    add_table(doc, ["层级", "当前处理", "代表错误"], [
        ["请求级", "Pydantic 校验失败直接返回 422，不创建任务", "空 paths / authorized_roots"],
        ["路径级", "缺失或越权路径转为文件项失败", "PATH_NOT_FOUND、PATH_NOT_AUTHORIZED"],
        ["解析级", "具体解析器抛出 ParseError，批服务记录后继续", "TEXT_DECODE_ERROR、PDF_ENCRYPTED、IMAGE_DECODE_ERROR"],
        ["依赖级", "Tika 连接失败或超时转为可重试错误", "TIKA_UNAVAILABLE、PARSE_TIMEOUT"],
        ["未知文件级", "第三方异常被替换为安全错误，不回传原始异常文本", "INTERNAL_ERROR"],
        ["任务级", "后台协程未捕获异常将任务标记 failed", "当前响应不携带任务级诊断详情"],
    ], weights=[0.17, 0.51, 0.32], center_cols={0}, font_size=8.7)
    add_bullets(doc, [
        "解析器不修改、移动或删除原始文件。",
        "重复内容按 SHA-256 在单批次内跳过；同一路径通过规范化路径先去重。",
        "DOCX 只暴露白名单元数据；图片 EXIF 不保留 GPS、序列号等敏感字段。",
        "当前没有专门的 `PERMISSION_DENIED`、`FORMAT_MISMATCH`、`CANCELLED` 错误；权限异常在某些路径上可能升级为任务级 failed。",
    ])

    add_heading(doc, "8. 任务状态模型")
    add_code(doc, "queued → running → completed\n                 → completed_with_errors\n                 → failed")
    add_para(doc, "`completed_with_errors` 表示至少一个文件级错误；目录扫描产生的 `unsupported_format` 或重复内容属于 `skipped`，不会单独把任务转为错误终态。当前没有取消终态，也没有状态迁移幂等 API。")

    add_heading(doc, "9. 代码边界")
    add_code(doc, "backend/src/content_retrieval/\n├─ api/{app.py, schemas.py, routes/health.py, routes/ingestion.py}\n├─ domain/{errors.py, models.py}\n├─ parsers/{base.py, registry.py, txt.py, pdf.py, docx.py, image.py, tika.py}\n└─ services/{batch_ingestion.py, ingestion_jobs.py}")
    add_para(doc, "当前目录与依赖方向清晰，适合在第 3 周新增 `embeddings/` 或 `services/embedding.py`。不建议把模型调用塞入解析器；解析器只负责稳定提取内容，模型分块和向量生成应保持独立。")

    add_heading(doc, "10. 实际完成状态与验收结论")
    add_table(doc, ["验收项", "结论", "说明"], [
        ["五类文件路由与正常解析", "通过", "TXT、PDF、DOCX、JPG/JPEG、PNG 均有自动化用例"],
        ["损坏/加密/超时错误隔离", "通过", "关键受控错误已覆盖；未知异常不会泄露内部文本"],
        ["批量路径、授权、去重", "通过", "混合文件/目录、递归、越权、缺失、重复均有用例"],
        ["最小 FastAPI 任务 API", "通过", "创建和查询任务、健康检查已完成"],
        ["实时进度、并发与取消", "未通过", "当前批内顺序执行，运行中计数为零，无取消接口"],
        ["Flutter 端到端 IPC", "未通过", "前端尚未实现本地客户端和进程管理"],
        ["鉴权与动态端口", "未通过", "仍是架构目标，尚无代码和验收"],
    ], weights=[0.35, 0.16, 0.49], center_cols={1}, font_size=8.7)
    add_callout(doc, "架构基线结论", "第 2 周可以判定“后端文件解析基础与最小任务 API 完成”，但不能判定“完整本地 IPC、可取消批任务或桌面端导入体验完成”。", color=ACCENT_DARK, fill=LIGHT_GREEN)

    add_heading(doc, "11. 后续演进")
    add_bullets(doc, [
        "第 3 周：定义 EmbeddingEngine 与 EmbeddingRecord；实现文本分块、BERT 文本向量和 MobileCLIP 图像向量；保持解析器无模型依赖。",
        "第 4 周：把向量、分块来源与最小元数据写入 ChromaDB，形成检索闭环。",
        "第 5 周：实现 Flutter LocalBackendClient、导入控制器和无障碍进度反馈。",
        "整合阶段：补齐令牌鉴权、动态端口、取消、持久化任务、性能与跨平台端到端测试。",
    ])

    doc.save(output)
    enforce_docx_visual_spec(output)
    validate_docx_visual_spec(output)
    return output


def build_api_doc() -> Path:
    output = REPORT_DIR / "02_文件解析模块API文档.docx"
    doc = init_doc(
        "文件解析模块 API 文档",
        "文件解析模块 API",
        "W2-API-02",
        "Python 解析接口、FastAPI 接口、请求响应示例和错误码",
        "本版本记录仓库中真实可调用的 Python 接口与 4 个 FastAPI 路由；取消、关闭、结果分页和会话令牌不属于当前可用接口。",
    )

    add_heading(doc, "1. 接口范围与约定")
    add_para(doc, "API 分为两层：Python 内部接口用于解析器注册、单文件解析与批量路径解析；FastAPI 接口用于创建异步任务和查询终态结果。路径均表示**后端所在机器上的本地绝对路径**，不是上传文件字节，也不接受远程 URL。")
    add_table(doc, ["属性", "当前值"], [
        ["API 标题", "Content Retrieval API"],
        ["版本状态", "第 2 周最小可用接口"],
        ["默认单文件上限", "100 MiB（FastAPI 默认服务实例）"],
        ["任务存储", "进程内存；进程重启后失效"],
        ["鉴权", "未实现；发布前必须增加会话令牌"],
    ], weights=[0.30, 0.70], center_cols={0}, font_size=9.2)

    add_heading(doc, "2. Python 解析接口")
    add_heading(doc, "2.1 Parser 协议", 2)
    add_code(doc, "class Parser(Protocol):\n    supported_extensions: frozenset[str]\n    supported_mime_types: frozenset[str]\n\n    def parse(self, path: Path) -> ParseResult: ...")
    add_bullets(doc, [
        "`parse()` 成功时返回 `ParseResult`；可预期失败抛出 `ParseError` 子类。",
        "解析器不得修改原文件；具体第三方库对象不得进入 `ParseResult.metadata`。",
        "当前协议没有 `probe()`；格式选择主要依赖 MIME 或扩展名。",
    ])

    add_heading(doc, "2.2 ParseResult", 2)
    add_table(doc, ["字段", "类型", "说明"], [
        ["file_id", "str", "原文件内容 SHA-256，64 位小写十六进制"],
        ["path / name", "Path / str", "规范化绝对路径与文件名"],
        ["mime_type", "str", "实际解析结果使用的 MIME"],
        ["modality", "text | document | image", "内容模态"],
        ["size_bytes", "int", "原始文件字节数"],
        ["modified_at", "datetime", "带 UTC 时区的修改时间"],
        ["text", "str | None", "TXT/PDF/DOCX 文本；图片为 null"],
        ["page_count", "int | None", "PDF 页数"],
        ["width / height", "int | None", "图片像素尺寸"],
        ["metadata", "dict[str, Any]", "格式专属、可 JSON 序列化的元数据"],
        ["warnings", "list[str]", "空文件、空白页等非致命提示"],
    ], weights=[0.22, 0.24, 0.54], center_cols={0, 1}, font_size=8.7)

    add_heading(doc, "2.3 ParserRegistry", 2)
    add_code(doc, "registry = create_default_registry()\nparser = registry.resolve(Path('report.PDF'))\nresult = parser.parse(Path('report.PDF'))")
    add_para(doc, "`resolve(path, mime_type=None)` 优先查 MIME，再按小写扩展名查找；找不到时抛出 `UnsupportedFormatError`。`supported_extensions` 返回已注册扩展名集合。当前默认注册 TXT、PDF、DOCX 和图片解析器。")

    add_heading(doc, "2.4 BatchIngestionService", 2)
    add_code(doc, "service.parse_paths(\n    paths: list[Path | str],\n    *,\n    recursive: bool = True,\n    authorized_roots: list[Path | str] | None = None,\n) -> BatchResult\n\nservice.parse_directory(directory, *, recursive=True) -> BatchResult\nservice.scan_directory(directory, *, recursive=True) -> list[Path]")
    add_bullets(doc, [
        "显式文件格式不支持时产生 `UNSUPPORTED_FORMAT` 失败；目录中发现的不支持格式记录为 `skipped/unsupported_format`。",
        "同一规范化路径只处理一次；不同路径但内容 SHA-256 相同的后续文件记录为 `duplicate_content`。",
        "每个文件先检查大小，再计算哈希并解析；当前批次内部按稳定路径顺序串行执行。",
        "单文件 `ParseError` 不终止批次；未知异常替换为 `INTERNAL_ERROR`。",
    ])

    add_heading(doc, "3. 解析器行为")
    add_table(doc, ["解析器", "输入", "输出重点", "主要异常"], [
        ["TxtParser", ".txt / text/plain", "BOM 编码或严格 UTF-8；换行风格、字符数", "TEXT_DECODE_ERROR"],
        ["PdfParser", ".pdf / application/pdf", "全文、页数、metadata.page_texts、基础 PDF 元数据", "PDF_ENCRYPTED、CORRUPTED_FILE"],
        ["DocxParser", ".docx / OOXML MIME", "Tika 正文；标题、作者、创建/修改时间白名单", "TIKA_UNAVAILABLE、PARSE_TIMEOUT、INTERNAL_ERROR"],
        ["ImageParser", ".jpg/.jpeg/.png", "格式、尺寸、色彩模式、描述/方向 EXIF", "IMAGE_DECODE_ERROR"],
    ], weights=[0.18, 0.25, 0.37, 0.20], center_cols={0}, font_size=8.5)

    add_heading(doc, "4. FastAPI 接口总览")
    add_callout(doc, "Base URL", "开发/发布启动器应使用 `http://127.0.0.1:<port>`；当前 FastAPI 应用对象本身不强制绑定地址。", color=CAUTION, fill=LIGHT_AMBER)
    add_table(doc, ["方法", "路径", "用途", "成功状态"], [
        ["GET", "/health/live", "进程存活检查", "200"],
        ["GET", "/health/ready", "应用 ready 标志检查", "200 / 503"],
        ["POST", "/v1/ingestion/jobs", "创建异步解析任务", "202"],
        ["GET", "/v1/ingestion/jobs/{job_id}", "查询状态、计数、结果、错误和跳过项", "200"],
    ], weights=[0.12, 0.35, 0.37, 0.16], center_cols={0, 3}, font_size=8.8)

    add_heading(doc, "5. 健康检查")
    add_heading(doc, "5.1 GET /health/live", 2)
    add_code(doc, "HTTP/1.1 200 OK\n{\"status\": \"ok\"}")
    add_heading(doc, "5.2 GET /health/ready", 2)
    add_code(doc, "HTTP/1.1 200 OK\n{\"status\": \"ready\"}\n\nHTTP/1.1 503 Service Unavailable\n{\"status\": \"not_ready\"}")
    add_para(doc, "当前 `ready` 仅检查 `application.state.ready` 布尔值，不包含 Tika 健康状态、模型状态或数据库状态；因此它是最小就绪信号，不是完整依赖探针。")

    add_heading(doc, "6. 创建解析任务")
    add_heading(doc, "6.1 POST /v1/ingestion/jobs", 2)
    add_table(doc, ["字段", "类型", "必填", "规则"], [
        ["paths", "list[Path]", "是", "至少 1 项；文件或目录绝对路径"],
        ["authorized_roots", "list[Path]", "是", "至少 1 项；解析后真实路径必须位于其中"],
        ["recursive", "bool", "否", "默认 true；控制目录递归"],
    ], weights=[0.20, 0.23, 0.13, 0.44], center_cols={0, 2}, font_size=8.8)
    add_para(doc, "请求示例：")
    add_code(doc, '{\n  "paths": [\n    "F:\\\\Documents\\\\notes.txt",\n    "F:\\\\Documents\\\\reports"\n  ],\n  "authorized_roots": ["F:\\\\Documents"],\n  "recursive": true\n}')
    add_para(doc, "响应示例：")
    add_code(doc, 'HTTP/1.1 202 Accepted\n{\n  "job_id": "9c0b94ad-9b3a-43de-b223-2da99ae8973d",\n  "status": "queued"\n}')
    add_para(doc, "任务创建后由后台协程执行。`202` 只表示任务已登记，不表示文件已解析成功。")

    add_heading(doc, "7. 查询解析任务")
    add_heading(doc, "7.1 GET /v1/ingestion/jobs/{job_id}", 2)
    add_para(doc, "终态成功响应示例：")
    add_code(doc, '{\n  "job_id": "9c0b94ad-9b3a-43de-b223-2da99ae8973d",\n  "status": "completed",\n  "counts": {\n    "total": 1, "pending": 0, "running": 0,\n    "succeeded": 1, "failed": 0, "skipped": 0\n  },\n  "results": [{\n    "file_id": "a4985d59d689345f0ff69f7ce6b8bb76a0d859a62e65e6ab1a7c5c8e9ef91582",\n    "path": "F:\\\\Documents\\\\notes.txt",\n    "name": "notes.txt",\n    "mime_type": "text/plain",\n    "modality": "text",\n    "size_bytes": 264,\n    "modified_at": "2026-07-19T10:30:00Z",\n    "text": "离线本地内容检索示例……",\n    "page_count": null, "width": null, "height": null,\n    "metadata": {"encoding": "utf-8", "newline_style": "lf", "character_count": 92},\n    "warnings": []\n  }],\n  "errors": [],\n  "skips": []\n}')
    add_para(doc, "混合结果响应将使用 `status = completed_with_errors`，并同时返回成功结果、文件级错误和跳过项。目录发现的不支持格式属于 `skips`；显式提交的不支持文件属于 `errors`。")
    add_code(doc, '{\n  "path": "F:\\\\Documents\\\\archive.bin",\n  "code": "UNSUPPORTED_FORMAT",\n  "message": "Unsupported format for archive.bin",\n  "retryable": false\n}')
    add_para(doc, "`queued`、`running` 或任务级 `failed` 且无 `BatchResult` 时，当前实现返回全零 counts 和空 results/errors/skips；这不是实时进度。")

    add_heading(doc, "8. HTTP 错误")
    add_table(doc, ["状态", "触发条件", "响应特征"], [
        ["404", "job_id 不存在", "detail.code = JOB_NOT_FOUND"],
        ["422", "请求体字段缺失、类型错误或列表为空", "FastAPI/Pydantic 标准 detail 数组"],
        ["503", "应用 ready 标志为 false", "{status: not_ready}"],
    ], weights=[0.16, 0.42, 0.42], center_cols={0}, font_size=8.9)
    add_code(doc, 'HTTP/1.1 404 Not Found\n{\n  "detail": {\n    "code": "JOB_NOT_FOUND",\n    "message": "Ingestion job not found"\n  }\n}')

    add_heading(doc, "9. 文件级错误码")
    add_table(doc, ["错误码", "来源 / 含义", "retryable"], [
        ["PATH_NOT_FOUND", "输入路径不存在", "false"],
        ["PATH_NOT_AUTHORIZED", "真实路径不在授权根目录", "false"],
        ["UNSUPPORTED_FORMAT", "没有可用解析器", "false"],
        ["CORRUPTED_FILE", "PDF 等文件结构损坏", "false"],
        ["TEXT_DECODE_ERROR", "不符合 BOM/严格 UTF-8 策略", "false"],
        ["IMAGE_DECODE_ERROR", "图片无法识别、验证或完整解码", "false"],
        ["PDF_ENCRYPTED", "PDF 需要密码", "false"],
        ["TIKA_UNAVAILABLE", "Tika 无法连接", "true"],
        ["PARSE_TIMEOUT", "Tika 等解析超时", "true"],
        ["FILE_TOO_LARGE", "超过服务配置上限", "true"],
        ["INTERNAL_ERROR", "未知异常的安全边界", "false"],
    ], weights=[0.30, 0.52, 0.18], center_cols={0, 2}, font_size=8.7)
    add_callout(doc, "兼容性说明", "原架构文档中列出的 `PERMISSION_DENIED`、`FORMAT_MISMATCH` 和 `CANCELLED` 尚未实现，不能作为当前稳定错误码对外承诺。", color=CAUTION, fill=LIGHT_AMBER)

    add_heading(doc, "10. 调用示例")
    add_heading(doc, "10.1 Python 直接调用", 2)
    add_code(doc, "from pathlib import Path\nfrom content_retrieval.parsers.registry import create_default_registry\nfrom content_retrieval.services.batch_ingestion import BatchIngestionService\n\nservice = BatchIngestionService(\n    create_default_registry(),\n    max_file_size_bytes=100 * 1024 * 1024,\n)\nbatch = service.parse_paths(\n    [Path(r'F:\\Documents\\notes.txt')],\n    authorized_roots=[Path(r'F:\\Documents')],\n)\nprint(batch.succeeded, batch.failed, batch.skipped)")
    add_heading(doc, "10.2 PowerShell HTTP 调用", 2)
    add_code(doc, "$body = @{\n  paths = @('F:\\Documents\\notes.txt')\n  authorized_roots = @('F:\\Documents')\n  recursive = $true\n} | ConvertTo-Json\n\n$created = Invoke-RestMethod -Method Post `\n  -Uri 'http://127.0.0.1:8000/v1/ingestion/jobs' `\n  -ContentType 'application/json' -Body $body\n\nInvoke-RestMethod `\n  -Uri (\"http://127.0.0.1:8000/v1/ingestion/jobs/{0}\" -f $created.job_id)")

    add_heading(doc, "11. 已知限制与版本演进")
    add_bullets(doc, [
        "当前接口没有 Bearer 鉴权，不适合作为对外网络服务暴露。",
        "任务结果全部内嵌在查询响应中；大批量结果需要后续增加分页或文档结果端点。",
        "任务无法取消，服务重启后任务丢失，运行中查询没有实时单文件计数。",
        "路径授权是服务层约束，不等于操作系统授权；调用方仍应只传递用户明确选择的目录。",
        "新增字段应保持向后兼容；若第 3 周引入分块/向量定位，建议增加 schema_version 而不是改变现有字段语义。",
    ])

    doc.save(output)
    enforce_docx_visual_spec(output)
    validate_docx_visual_spec(output)
    return output


def build_test_report() -> Path:
    output = REPORT_DIR / "03_文件解析模块测试报告.docx"
    coverage_path = WORK_DIR / "coverage.json"
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    totals = coverage["totals"]
    assert totals["num_statements"] == 665
    assert totals["covered_lines"] == 642
    doc = init_doc(
        "文件解析模块测试报告",
        "文件解析模块测试报告",
        "W2-TEST-03",
        "测试环境、样本、测试用例、运行结果和覆盖率",
        "2026-07-19 完整后端测试共收集并执行 58 个用例，58 个通过、0 个失败、0 个跳过；行覆盖率 97%（642/665），真实 Tika 3.3.1 集成用例已执行。",
    )

    add_heading(doc, "1. 测试结论")
    add_table(doc, ["指标", "结果", "判定"], [
        ["自动化用例", "58 passed", "通过"],
        ["失败 / 错误", "0 / 0", "通过"],
        ["跳过", "0", "真实 Tika 用例已参与"],
        ["执行时间", "5.57 s", "信息项"],
        ["行覆盖率", "97%（642 / 665）", "通过"],
        ["分支覆盖率", "未启用", "待补充"],
    ], weights=[0.28, 0.36, 0.36], center_cols={0, 1, 2}, font_size=9.1)
    add_callout(doc, "总体判定", "文件解析、批量路径处理、任务状态与最小 FastAPI 契约达到第 2 周后端交付要求。性能、并发、取消、Flutter 端到端和真实网络绑定不在本次通过范围内。", color=ACCENT_DARK, fill=LIGHT_GREEN)

    add_heading(doc, "2. 测试环境")
    add_table(doc, ["组件", "版本 / 配置"], [
        ["操作系统", "Windows，build 26200（Python platform 兼容字符串显示 Windows-10）"],
        ["Python", "3.10.18"],
        ["FastAPI / Pydantic", "0.139.0 / 2.13.4"],
        ["HTTPX", "0.28.1"],
        ["Pillow", "12.3.0"],
        ["pypdfium2", "4.30.0"],
        ["pytest / coverage.py", "8.4.2 / 7.15.0"],
        ["Apache Tika", "3.3.1，http://127.0.0.1:9998"],
        ["工作目录", "F:\\contentretrivalsystem\\backend"],
        ["测试时间", "2026-07-19，Asia/Shanghai"],
    ], weights=[0.30, 0.70], center_cols={0}, font_size=9.0)
    add_para(doc, "测试使用项目自带 `backend/.venv`。Tika 在本机回环地址运行，DOCX 真实集成用例未触发跳过逻辑。覆盖率命令未开启 `--branch`，因此本报告只声明行覆盖率。")

    add_heading(doc, "3. 测试样本")
    add_table(doc, ["样本组", "样本", "用途", "本次使用"], [
        ["文本", "D001–D005", "中文、英文、混合语言、重复内容", "直接使用"],
        ["PDF", "D006 项目说明 PDF（6 页）", "分页文本、顺序、关键词与 SHA-256", "直接使用"],
        ["DOCX", "D007 项目总理解和周次安排", "真实 Tika 中文正文抽取", "直接使用"],
        ["PNG", "D008 64×64；D009 512×512", "图片解码与尺寸", "D008 直接；D009 未直接断言"],
        ["JPEG", "D010 4×3，含描述和方向 EXIF", "安全 EXIF 白名单", "直接使用"],
        ["动态临时样本", "空 TXT、非法 UTF-8、空白/损坏/加密 PDF、损坏 JPG/APNG、越权/缺失/重复路径", "边界和失败隔离", "测试运行时创建"],
    ], weights=[0.14, 0.30, 0.34, 0.22], center_cols={0, 3}, font_size=8.4)
    add_para(doc, "`datasets/manifest.csv` 共登记 10 个烟测样本。本次解析器用例直接引用其中 9 个；D009 仍属于样本资产，但没有独立自动化断言，因此不把它计为已单独验收。")

    add_heading(doc, "4. 测试套件与用例分布")
    add_table(doc, ["测试文件", "用例数", "主要覆盖"], [
        ["test_api.py", "13", "Job Store、健康检查、创建/查询任务、422/404、混合结果"],
        ["test_batch_ingestion.py", "12", "扫描顺序、失败隔离、大小限制、授权、递归、路径/内容去重"],
        ["test_docx_image_parsers.py", "10", "Tika 成功/连接/超时、元数据白名单、JPG/PNG/APNG"],
        ["test_parsing_contracts.py", "11", "ParseResult 约束、Parser 协议、Registry、BatchResult"],
        ["test_txt_pdf_parsers.py", "12", "TXT 编码、PDF 页文本、空白/损坏/加密与默认路由"],
    ], weights=[0.35, 0.14, 0.51], center_cols={0, 1}, font_size=8.8)

    add_heading(doc, "5. 关键测试用例与结果")
    add_table(doc, ["编号", "测试主题", "预期", "结果"], [
        ["TC-01", "统一数据契约", "非法 SHA-256、模态和负数大小被拒绝", "通过"],
        ["TC-02", "TXT 确定性解码", "BOM/UTF-8 成功；非法 UTF-8 抛 TEXT_DECODE_ERROR", "通过"],
        ["TC-03", "PDF 分页", "D006 为 6 页，页文本顺序和关键词正确", "通过"],
        ["TC-04", "PDF 异常", "空白页警告；损坏与加密使用稳定错误", "通过"],
        ["TC-05", "DOCX/Tika", "真实 D007 抽取正文；HTTP 元数据白名单正确", "通过"],
        ["TC-06", "Tika 失败", "连接失败和超时分别映射可重试错误", "通过"],
        ["TC-07", "图片解析", "尺寸、模式、安全 EXIF 正确；损坏帧被拒绝", "通过"],
        ["TC-08", "批量失败隔离", "受控/未知异常只影响单文件且不泄露原异常", "通过"],
        ["TC-09", "路径授权", "越权、缺失、显式不支持格式可区分", "通过"],
        ["TC-10", "去重", "真实路径去重；内容重复记录 duplicate_of", "通过"],
        ["TC-11", "FastAPI 任务", "202 创建；终态计数、结果、错误和跳过项一致", "通过"],
        ["TC-12", "健康检查", "live=200；ready 可返回 200/503", "通过"],
    ], weights=[0.13, 0.29, 0.43, 0.15], center_cols={0, 3}, font_size=8.3)

    add_heading(doc, "6. 执行命令与原始结果")
    add_code(doc, "backend\\.venv\\Scripts\\python.exe -m pytest -q `\n  --cov=content_retrieval `\n  --cov-report=term-missing `\n  --cov-report=json:F:\\contentretrivalsystem\\tmp\\week2-deliverables\\coverage.json")
    add_code(doc, "..........................................................  [100%]\n58 passed in 5.57s\nTOTAL  665 statements  23 missed  97%")

    add_heading(doc, "7. 覆盖率")
    add_table(doc, ["模块", "语句", "未覆盖", "覆盖率"], [
        ["api/app.py", "16", "0", "100%"],
        ["api/routes/health.py", "11", "0", "100%"],
        ["api/routes/ingestion.py", "36", "2", "94%"],
        ["api/schemas.py", "53", "0", "100%"],
        ["domain/errors.py", "62", "0", "100%"],
        ["domain/models.py", "63", "0", "100%"],
        ["parsers/docx.py", "37", "1", "97%"],
        ["parsers/image.py", "48", "2", "96%"],
        ["parsers/pdf.py", "57", "4", "93%"],
        ["parsers/registry.py", "36", "1", "97%"],
        ["parsers/tika.py", "27", "4", "85%"],
        ["parsers/txt.py", "35", "2", "94%"],
        ["services/batch_ingestion.py", "116", "7", "94%"],
        ["services/ingestion_jobs.py", "34", "0", "100%"],
        ["其他包/辅助模块", "34", "0", "100%"],
        ["合计", str(totals["num_statements"]), str(totals["missing_lines"]), f"{totals['percent_covered_display']}%"],
    ], weights=[0.50, 0.16, 0.16, 0.18], center_cols={1, 2, 3}, font_size=8.3)
    add_para(doc, "覆盖率最低的是 Tika 适配器（85%），未覆盖主要集中在 HTTP 状态异常、无效 JSON、空列表和非字典响应。其他缺口包括任务级未知异常、PDFium 提取/元数据读取异常、目录子项在扫描期间消失或越权等低频分支。")

    add_heading(doc, "8. 未覆盖范围与残余风险")
    add_bullets(doc, [
        "未做并发、吞吐、内存峰值和大文件性能测试；当前批内解析实际上是串行。",
        "未做取消、关闭、任务持久化和后端崩溃恢复测试，因为对应功能尚未实现。",
        "FastAPI 用例使用 ASGITransport，没有验证真实 127.0.0.1 绑定、端口握手或会话令牌。",
        "未做 Flutter 到后端的端到端测试、键盘/屏幕阅读器进度反馈或跨平台文件选择测试。",
        "未启用分支覆盖率；97% 不能解释为所有异常路径都已执行。",
    ])

    add_heading(doc, "9. 验收结论与建议")
    add_para(doc, "**结论：第 2 周后端解析与最小任务 API 通过验收，可进入第 3 周 Embedding 开发；Flutter IPC、任务取消、性能和真实网络绑定不在本次通过范围内。**")

    doc.save(output)
    enforce_docx_visual_spec(output)
    validate_docx_visual_spec(output)
    return output


def build_weekly_report() -> Path:
    output = REPORT_DIR / "04_第二周工作周报.docx"
    doc = init_doc(
        "第二周工作周报",
        "第二周工作周报",
        "W2-WEEKLY-04",
        "完成工作、问题处理、风险变化和第三周计划",
        "本周完成后端五类文件解析、批量路径处理和最小 FastAPI 任务 API，完整测试 58 项全部通过、行覆盖率 97%；前端 IPC、取消/关闭与安全握手顺延。",
    )

    add_heading(doc, "1. 本周目标与完成度")
    add_para(doc, "项目总计划把第 2 周定义为“打基础：设计系统结构，先让软件能读取各种文件”。按这一目标，本周已完成后端解析基础和可测试的最小任务入口；“软件界面可完成导入”尚未达到。")
    add_table(doc, ["目标", "计划内容", "结果", "完成度"], [
        ["架构设计", "模块、数据流、IPC 与异常策略", "已更新为实际架构并标注差距", "100%"],
        ["文件解析", "TXT、PDF、DOCX、JPG/PNG", "五类格式实现并测试", "100%"],
        ["批量导入基础", "目录扫描、失败隔离、去重、授权", "已完成；当前顺序执行", "85%"],
        ["最小后端 API", "健康、任务创建、状态查询", "4 个路由完成", "100%"],
        ["完整本地 IPC", "Flutter 客户端、进程、令牌、取消", "未接入", "20%"],
        ["自动化测试", "成功、异常、集成与覆盖率", "58/58，行覆盖率 97%", "100%"],
    ], weights=[0.22, 0.34, 0.28, 0.16], center_cols={0, 3}, font_size=8.6)

    add_heading(doc, "2. 本周完成工作")
    add_heading(doc, "2.1 解析领域模型与错误体系", 2)
    add_bullets(doc, [
        "建立 `ParseResult`、`BatchItem`、`SkippedFile` 和 `BatchResult`，统一成功、失败与跳过结果。",
        "建立受控错误体系，覆盖路径缺失/越权、格式不支持、损坏、编码失败、加密 PDF、图片失败、Tika 不可用/超时、文件过大与内部错误。",
        "以 SHA-256 作为 file_id 和单批次内容去重依据。",
    ])
    add_heading(doc, "2.2 五类文件解析", 2)
    add_bullets(doc, [
        "TXT：BOM 识别与严格 UTF-8，输出编码、换行类型、字符数。",
        "PDF：使用 pypdfium2 分页抽取，保留页数和 page_texts，处理空白、损坏与加密文件。",
        "DOCX：通过本机 Apache Tika 3.3.1 抽取正文和白名单元数据；回环请求禁用系统代理。",
        "图片：Pillow 验证 JPG/JPEG/PNG，加载全部帧，输出尺寸、模式与安全 EXIF。",
    ])
    add_heading(doc, "2.3 批量服务与 API", 2)
    add_bullets(doc, [
        "支持显式文件与目录混合输入、递归开关、稳定排序、真实路径去重和授权根目录校验。",
        "实现单文件失败隔离、文件大小上限和目录内不支持格式跳过。",
        "实现线程安全内存任务仓储，以及 live/ready、创建任务和查询任务 4 个 FastAPI 路由。",
        "后台任务使用 `asyncio.to_thread` 隔离阻塞解析，避免占用 FastAPI 事件循环。",
    ])
    add_heading(doc, "2.4 测试与文档", 2)
    add_bullets(doc, [
        "后端 58 个用例全部通过；真实 Tika 集成测试执行成功；行覆盖率 97%。",
        "更新系统架构设计，修正旧文档中把 Flutter、并发/取消和 ParsedDocument 写成已实现的问题。",
        "形成 API 文档、测试报告与本周工作周报，统一进入正式交付目录。",
    ])

    add_heading(doc, "3. 本周交付物")
    add_table(doc, ["编号", "文件", "内容", "状态"], [
        ["01", "01_系统架构设计.docx", "架构图、职责、数据流、IPC、异常与状态差距", "完成"],
        ["02", "02_文件解析模块API文档.docx", "Python/FastAPI 接口、示例、错误码和限制", "完成"],
        ["03", "03_文件解析模块测试报告.docx", "环境、样本、58 项结果、97% 覆盖率", "完成"],
        ["04", "04_第二周工作周报.docx", "工作总结、问题、风险与第三周计划", "完成"],
    ], weights=[0.10, 0.34, 0.42, 0.14], center_cols={0, 3}, font_size=8.8)

    add_heading(doc, "4. 问题处理")
    add_table(doc, ["问题", "处理", "结果 / 遗留"], [
        ["设计文档与代码状态漂移", "逐项核对 API、服务、解析器和测试，把计划能力与已实现能力分开", "本次交付文档已修正；后续需随实现同步更新"],
        ["Windows 系统代理干扰本机 Tika", "TikaClient 使用 trust_env=False 并固定回环地址", "真实 DOCX 用例通过；仍缺 Tika 生命周期管理"],
        ["第三方解析异常可能泄露内部信息", "批服务统一转换为 INTERNAL_ERROR", "文件级安全边界完成；任务级 failed 仍缺诊断 DTO"],
        ["混合路径存在越权与重复风险", "真实路径解析、is_relative_to 授权、路径去重和 SHA-256 内容去重", "核心用例通过；目录扫描竞态仍需补测"],
        ["显式不支持格式与大小限制优先级", "先做 ParserRegistry 格式解析，再做大小验证", "错误码稳定为 UNSUPPORTED_FORMAT"],
    ], weights=[0.28, 0.43, 0.29], font_size=8.5)

    add_heading(doc, "5. 风险变化")
    add_table(doc, ["风险", "本周变化", "当前等级", "下一步"], [
        ["Tika 外部进程不可用", "结构化连接/超时错误与真实集成测试使风险下降", "中", "增加 health 探针、启动监督与受控重启"],
        ["格式误路由", "注册表完成，但仍依赖扩展名/MIME，无签名探测", "中", "增加 probe/魔数检查与 FORMAT_MISMATCH"],
        ["本地 IPC 安全", "授权根目录已完成；令牌和回环绑定仍未落地", "中高", "实现启动握手、Bearer 令牌与网络端到端测试"],
        ["大批量性能与内存", "加入 100 MiB 上限和线程隔离；批内仍顺序、解析器多为整文件读取", "中", "建立性能基线、流式哈希/读取和有界并发"],
        ["回归风险", "58 项通过、行覆盖率 97%，风险下降", "低", "补分支覆盖与低频异常"],
        ["AI 模型可行性", "第 3 周即将进入 BERT/MobileCLIP 接入，风险开始上升", "中高", "先做统一接口、CPU 基准和小样本验收"],
        ["前后端集成延期", "Flutter IPC 未开始，可能挤压第 5 周界面工作", "中高", "第 3 周保留最小真实 HTTP 烟测，不扩大前端功能"],
    ], weights=[0.24, 0.42, 0.13, 0.21], center_cols={2}, font_size=8.2)

    add_heading(doc, "6. 质量与进度指标")
    add_table(doc, ["指标", "本周值"], [
        ["支持解析格式", "TXT、PDF、DOCX、JPG/JPEG、PNG"],
        ["FastAPI 业务/健康路由", "4"],
        ["自动化测试", "58 passed / 0 failed / 0 skipped"],
        ["行覆盖率", "97%（642/665）"],
        ["真实集成", "Tika 3.3.1 + D007 DOCX"],
        ["当前任务执行", "后台线程隔离；批内顺序"],
    ], weights=[0.43, 0.57], center_cols={0}, font_size=9.1)

    add_heading(doc, "7. 未完成与顺延项")
    add_bullets(doc, [
        "Flutter LocalBackendClient、导入状态管理和后端进程管理。",
        "任务取消、结果分页、系统关闭、实时进度与任务持久化。",
        "Bearer 会话令牌、动态端口握手和真实 127.0.0.1 网络验收。",
        "Parser probe/格式签名校验与专门的 PERMISSION_DENIED/FORMAT_MISMATCH。",
        "性能基线、有界并发、资源预算和跨平台路径测试。",
    ])
    add_callout(doc, "范围管理", "顺延项不阻塞第 3 周 Embedding 原型，但必须在第 4–6 周集成前回收；尤其是前端 IPC 与安全握手不能推迟到发布阶段。", color=CAUTION, fill=LIGHT_AMBER)

    add_heading(doc, "8. 第三周计划：AI 理解能力")
    add_para(doc, "第三周目标是让已解析文本和图片转换为可比较的向量，为第 4 周 ChromaDB 检索做准备。本周只完成“Embedding 输入到向量输出”，不提前实现完整搜索 UI 或数据库检索。")
    add_table(doc, ["时间", "工作项", "产出 / 验收"], [
        ["第 1 天", "定义 EmbeddingEngine、EmbeddingRecord、模型配置与错误契约；确定 ParseResult 适配策略", "接口评审通过；文本/图片入口互不污染解析器"],
        ["第 2 天", "实现确定性文本分块：TXT/DOCX 段落、PDF page_texts；加入长度、重叠和来源定位", "分块顺序稳定；中英文样本不丢文本；页来源可追踪"],
        ["第 3 天", "接入 BERT 文本向量：tokenize、pooling、归一化、CPU 推理", "D001–D007 目标文本产生固定维度有限向量；重复输入一致"],
        ["第 4 天", "接入 MobileCLIP-S0 图像向量与预处理；使用 D008–D010", "PNG/JPEG 产生固定维度向量；损坏图片保持解析层错误"],
        ["第 5 天", "统一批量 Embedding、缓存/模型版本字段、性能基线、自动化测试和文档", "离线运行；输出可供第 4 周 ChromaDB 使用；形成基准报告"],
    ], weights=[0.14, 0.50, 0.36], center_cols={0}, font_size=8.3)

    add_heading(doc, "9. 第三周验收标准")
    add_numbered(doc, [
        "文本和图片通过统一 Embedding 抽象生成固定维度向量，向量元素均为有限值。",
        "相同模型版本、相同输入和相同配置得到可复现结果；向量归一化策略明确。",
        "文本分块保留 document/file_id、chunk_index 和 PDF 页来源，不改变解析器职责。",
        "D001–D007 文本样本和 D008–D010 图片样本至少各形成一条成功验收路径。",
        "整个流程在离线模式下运行，不自动下载模型；缺失模型返回结构化错误。",
        "记录 CPU 环境下的加载时间、单样本延迟、批量吞吐、峰值内存与模型大小。",
        "新增自动化测试并保持完整后端回归通过；第 4 周前确定 ChromaDB 所需向量与元数据 schema。",
    ])

    add_heading(doc, "10. 周报结论")
    add_para(doc, "第 2 周核心价值是把“能否稳定读取本地文件”从设计假设变成可测试的后端能力。下一周应优先保持接口清晰和性能可测，避免同时扩展数据库、前端和模型三条主线。只要第三周交付统一向量输出与可靠基准，第 4 周即可在较低集成风险下连接 ChromaDB。")

    doc.save(output)
    enforce_docx_visual_spec(output)
    validate_docx_visual_spec(output)
    return output


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    outputs = [
        build_architecture_doc(),
        build_api_doc(),
        build_test_report(),
        build_weekly_report(),
    ]
    for path in outputs:
        print(f"DOCX={path}")


if __name__ == "__main__":
    main()
