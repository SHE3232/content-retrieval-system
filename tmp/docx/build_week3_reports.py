from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from typing import Iterable, Sequence

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "docs" / "week3" / "reports"
EVIDENCE_DIR = ROOT / "docs" / "week3" / "evidence"
OUTPUT_DIR = ROOT / "output" / "week3"

FONT = "Times New Roman"
BLACK = RGBColor(0, 0, 0)
WHITE = "FFFFFF"
CONTENT_WIDTH_DXA = 9360
TABLE_INDENT_DXA = 120
CELL_MARGINS = {"top": 80, "bottom": 80, "start": 120, "end": 120}


@dataclass(frozen=True)
class ReportMeta:
    title: str
    subtitle: str
    document_type: str
    header_title: str | None = None
    version: str = "1.0"
    status: str = "已验证"


def set_run_font(
    run,
    *,
    size: float = 11,
    bold: bool = False,
    italic: bool = False,
) -> None:
    run.font.name = FONT
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), FONT)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), FONT)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = BLACK


def configure_style(style, *, size: float, bold: bool, before: float, after: float) -> None:
    style.font.name = FONT
    style._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), FONT)
    style._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), FONT)
    style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = BLACK
    style.paragraph_format.space_before = Pt(before)
    style.paragraph_format.space_after = Pt(after)
    style.paragraph_format.line_spacing = 1.25
    style.paragraph_format.keep_with_next = style.name.startswith("Heading")


def configure_document(doc: Document, short_title: str) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.right_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    configure_style(doc.styles["Normal"], size=11, bold=False, before=0, after=6)
    configure_style(doc.styles["Title"], size=26, bold=True, before=0, after=8)
    configure_style(doc.styles["Subtitle"], size=13, bold=False, before=0, after=16)
    configure_style(doc.styles["Heading 1"], size=16, bold=True, before=18, after=10)
    configure_style(doc.styles["Heading 2"], size=13, bold=True, before=14, after=7)
    configure_style(doc.styles["Heading 3"], size=12, bold=True, before=10, after=5)

    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hp.paragraph_format.space_after = Pt(0)
    set_run_font(hp.add_run(short_title), size=9)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fp.paragraph_format.space_after = Pt(0)
    set_run_font(fp.add_run("第三周  |  第 "), size=9)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    for key in ("ascii", "hAnsi", "eastAsia"):
        fonts.set(qn(f"w:{key}"), FONT)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "000000")
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "18")
    rpr.extend([fonts, color, size])
    text = OxmlElement("w:t")
    text.text = "1"
    run.extend([rpr, text])
    field.append(run)
    fp._p.append(field)
    set_run_font(fp.add_run(" 页"), size=9)

    props = doc.core_properties
    props.title = short_title
    props.subject = "第三周多模态嵌入引擎交付文档"
    props.author = "Content Retrieval System Team"
    props.last_modified_by = "Content Retrieval System Team"
    props.keywords = "multimodal embedding, offline retrieval, week 3"


def add_title_block(doc: Document, meta: ReportMeta) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    set_run_font(p.add_run(meta.document_type.upper()), size=10, bold=True)

    title = doc.add_paragraph()
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after = Pt(8)
    title.paragraph_format.line_spacing = 1.0
    title.paragraph_format.keep_with_next = True
    set_run_font(title.add_run(meta.title), size=26, bold=True)

    subtitle = doc.add_paragraph(style="Subtitle")
    subtitle.paragraph_format.keep_with_next = True
    set_run_font(subtitle.add_run(meta.subtitle), size=13)

    rows = [
        ("项目", "离线可访问多模态本地内容检索系统"),
        ("版本", meta.version),
        ("日期", date.today().isoformat()),
        ("状态", meta.status),
    ]
    for label, value in rows:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.1
        set_run_font(p.add_run(f"{label}: "), size=10.5, bold=True)
        set_run_font(p.add_run(value), size=10.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_paragraph(style=f"Heading {level}")
    set_run_font(p.add_run(text), size={1: 16, 2: 13, 3: 12}[level], bold=True)


def add_body(doc: Document, text: str, *, bold_lead: str | None = None) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.25
    p.paragraph_format.space_after = Pt(6)
    if bold_lead and text.startswith(bold_lead):
        set_run_font(p.add_run(bold_lead), bold=True)
        set_run_font(p.add_run(text[len(bold_lead):]))
    else:
        set_run_font(p.add_run(text))


def _next_abstract_num_id(numbering) -> int:
    values = [
        int(node.get(qn("w:abstractNumId")))
        for node in numbering.findall(qn("w:abstractNum"))
    ]
    return max(values, default=-1) + 1


def _next_num_id(numbering) -> int:
    values = [int(node.get(qn("w:numId"))) for node in numbering.findall(qn("w:num"))]
    return max(values, default=0) + 1


def create_numbering(doc: Document, *, ordered: bool) -> int:
    numbering = doc.part.numbering_part.element
    abstract_id = _next_abstract_num_id(numbering)
    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    multi = OxmlElement("w:multiLevelType")
    multi.set(qn("w:val"), "singleLevel")
    abstract.append(multi)
    level = OxmlElement("w:lvl")
    level.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    fmt = OxmlElement("w:numFmt")
    fmt.set(qn("w:val"), "decimal" if ordered else "bullet")
    text = OxmlElement("w:lvlText")
    text.set(qn("w:val"), "%1." if ordered else "•")
    justification = OxmlElement("w:lvlJc")
    justification.set(qn("w:val"), "left")
    ppr = OxmlElement("w:pPr")
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "num")
    tab.set(qn("w:pos"), "540")
    tabs.append(tab)
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "540")
    ind.set(qn("w:hanging"), "270")
    ppr.extend([tabs, ind])
    level.extend([start, fmt, text, justification, ppr])
    if not ordered:
        rpr = OxmlElement("w:rPr")
        fonts = OxmlElement("w:rFonts")
        fonts.set(qn("w:ascii"), FONT)
        fonts.set(qn("w:hAnsi"), FONT)
        fonts.set(qn("w:eastAsia"), FONT)
        color = OxmlElement("w:color")
        color.set(qn("w:val"), "000000")
        rpr.extend([fonts, color])
        level.append(rpr)
    abstract.append(level)
    first_num = numbering.find(qn("w:num"))
    if first_num is None:
        numbering.append(abstract)
    else:
        first_num.addprevious(abstract)
    num_id = _next_num_id(numbering)
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(num_id))
    abstract_ref = OxmlElement("w:abstractNumId")
    abstract_ref.set(qn("w:val"), str(abstract_id))
    num.append(abstract_ref)
    numbering.append(num)
    return num_id


def add_list(doc: Document, items: Iterable[str], *, ordered: bool = False) -> None:
    num_id = create_numbering(doc, ordered=ordered)
    for item in items:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.25
        ppr = p._p.get_or_add_pPr()
        num_pr = OxmlElement("w:numPr")
        ilvl = OxmlElement("w:ilvl")
        ilvl.set(qn("w:val"), "0")
        num = OxmlElement("w:numId")
        num.set(qn("w:val"), str(num_id))
        num_pr.extend([ilvl, num])
        ppr.append(num_pr)
        set_run_font(p.add_run(item))


def _set_cell_fill(cell) -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    shd = tcpr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcpr.append(shd)
    shd.set(qn("w:fill"), WHITE)
    shd.set(qn("w:color"), "auto")


def _set_cell_margins(cell) -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    margins = tcpr.find(qn("w:tcMar"))
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tcpr.append(margins)
    for edge, value in CELL_MARGINS.items():
        node = margins.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _set_repeat_header(row) -> None:
    trpr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    trpr.append(header)


def _set_table_geometry(table, widths: Sequence[int]) -> None:
    if sum(widths) != CONTENT_WIDTH_DXA:
        raise ValueError(f"table widths must sum to {CONTENT_WIDTH_DXA}: {widths}")
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tblpr = table._tbl.tblPr
    tblw = tblpr.find(qn("w:tblW"))
    if tblw is None:
        tblw = OxmlElement("w:tblW")
        tblpr.append(tblw)
    tblw.set(qn("w:w"), str(CONTENT_WIDTH_DXA))
    tblw.set(qn("w:type"), "dxa")
    indent = tblpr.find(qn("w:tblInd"))
    if indent is None:
        indent = OxmlElement("w:tblInd")
        tblpr.append(indent)
    indent.set(qn("w:w"), str(TABLE_INDENT_DXA))
    indent.set(qn("w:type"), "dxa")
    layout = tblpr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tblpr.append(layout)
    layout.set(qn("w:type"), "fixed")

    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for cell, width in zip(row.cells, widths, strict=True):
            cell.width = Inches(width / 1440)
            tcpr = cell._tc.get_or_add_tcPr()
            tcw = tcpr.find(qn("w:tcW"))
            if tcw is None:
                tcw = OxmlElement("w:tcW")
                tcpr.append(tcw)
            tcw.set(qn("w:w"), str(width))
            tcw.set(qn("w:type"), "dxa")


def _set_table_borders(table) -> None:
    tblpr = table._tbl.tblPr
    borders = tblpr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tblpr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "6")
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), "000000")


def add_table(
    doc: Document,
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    widths: Sequence[int],
) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(0)
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    header = table.rows[0]
    _set_repeat_header(header)
    for cell, value in zip(header.cells, headers, strict=True):
        cell.text = ""
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _set_cell_fill(cell)
        _set_cell_margins(cell)
        cp = cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_after = Pt(0)
        cp.paragraph_format.line_spacing = 1.1
        set_run_font(cp.add_run(str(value)), size=9.5, bold=True)
    for row_values in rows:
        row = table.add_row()
        for column, (cell, value) in enumerate(zip(row.cells, row_values, strict=True)):
            cell.text = ""
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            _set_cell_fill(cell)
            _set_cell_margins(cell)
            cp = cell.paragraphs[0]
            cp.alignment = WD_ALIGN_PARAGRAPH.LEFT if column else WD_ALIGN_PARAGRAPH.CENTER
            cp.paragraph_format.space_after = Pt(0)
            cp.paragraph_format.line_spacing = 1.1
            set_run_font(cp.add_run(str(value)), size=9.5)
    _set_table_geometry(table, widths)
    _set_table_borders(table)
    after = doc.add_paragraph()
    after.paragraph_format.space_before = Pt(0)
    after.paragraph_format.space_after = Pt(4)


def save(doc: Document, filename: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / filename
    doc.save(path)
    return path


def new_report(meta: ReportMeta) -> Document:
    doc = Document()
    configure_document(doc, meta.header_title or meta.title)
    add_title_block(doc, meta)
    return doc


def build_api_document() -> Path:
    doc = new_report(
        ReportMeta(
            title="多模态嵌入模块 API 文档",
            subtitle="离线双向量空间、批处理接口与错误契约",
            document_type="Technical API Reference",
            header_title="嵌入模块 API 文档",
        )
    )
    add_heading(doc, "1. 模块定位")
    add_body(doc, "模块消费 ParseResult，在入库前生成可审计、L2 归一化的文本或图片向量。文本语义空间用于文档检索；MobileCLIP 图文联合空间用于文字搜图。")
    add_table(
        doc,
        ["向量空间", "输入", "输出维度", "用途"],
        [
            ["text-semantic-v1", "查询文本、文档分块", "384", "多语言文本语义检索"],
            ["mobileclip-image-text-v1", "图片、文字搜图查询", "512", "跨模态文字搜图"],
        ],
        [2200, 2500, 1260, 3400],
    )

    add_heading(doc, "2. 核心数据契约")
    add_heading(doc, "2.1 TextChunk", 2)
    add_table(
        doc,
        ["字段", "类型", "规则"],
        [
            ["chunk_id", "str", "确定性 SHA-256"],
            ["file_id", "str", "源文件 SHA-256"],
            ["text", "str", "非空正文"],
            ["sequence_number", "int", "从 0 开始"],
            ["page_number / paragraph_number", "int | None", "二者必须且只能有一个"],
            ["split_number", "int", "同一来源单元内的窗口编号"],
        ],
        [2100, 1800, 5460],
    )
    add_heading(doc, "2.2 EmbeddingVector", 2)
    add_table(
        doc,
        ["字段", "含义", "约束"],
        [
            ["source_id", "分块或图片身份", "64 位小写 SHA-256"],
            ["file_id", "源文件身份", "64 位小写 SHA-256"],
            ["model_id", "模型版本", "非空"],
            ["space_id", "向量兼容空间", "跨空间禁止比较"],
            ["modality", "text / image", "受控枚举"],
            ["values", "浮点向量", "有限数值且维度一致"],
            ["normalized", "是否 L2 归一化", "生产输出为 true"],
            ["metadata", "来源位置与输入顺序", "不包含文档全文"],
        ],
        [1900, 3000, 4460],
    )

    add_heading(doc, "3. 公开接口")
    add_heading(doc, "3.1 TextChunker", 2)
    add_body(doc, "构造：TextChunker(max_characters=1000, overlap_characters=100)。chunk(document) 为单文档生成确定性分块；chunk_many(documents) 返回 BatchProcessingResult 并隔离单文件错误。PDF 从 metadata.page_texts 保留页码，其他文本按段落定位。")
    add_heading(doc, "3.2 TextEmbeddingEngine", 2)
    add_body(doc, "构造：TextEmbeddingEngine(backend, batch_size=16)。embed(chunks) 负责批次切分、后端输出数量与维度校验、有限值检查、L2 归一化和单分块失败降级。生产后端 SentenceTransformerBackend 只接受本地目录并启用 local_files_only。")
    add_heading(doc, "3.3 MobileClipEmbeddingEngine", 2)
    add_body(doc, "构造：MobileClipEmbeddingEngine(backend, batch_size=8)。embed_images(images) 生成图片向量；embed_queries(queries) 生成位于同一 MobileCLIP 空间的文字查询向量。生产后端会应用 EXIF 方向、RGB 转换、官方预处理与 tokenizer。")
    add_heading(doc, "3.4 MultimodalEmbeddingService", 2)
    add_body(doc, "embed_documents(documents) 按输入顺序分派：text/document 先分块再编码，image 进入 MobileCLIP；每个输出 metadata.input_index 标记原输入位置。embed_image_queries(queries) 是文字搜图入口。cosine_similarity(left, right) 仅接受同 space_id、同维度且已归一化的向量。")

    add_heading(doc, "4. 最小调用流程")
    add_list(
        doc,
        [
            "加载 models/model-manifest.json，并通过 ModelManifest.require(model_id) 校验路径、维度与 SHA-256。",
            "使用清单中的本地路径构造 SentenceTransformerBackend 与 LocalMobileClipBackend。",
            "构造 TextChunker、两个嵌入引擎和 MultimodalEmbeddingService。",
            "调用 embed_documents 或 embed_image_queries；分别检查 items 与 errors。",
            "只有 space_id 和 dimensions 兼容时才调用 cosine_similarity。",
        ],
    )
    add_heading(doc, "5. 错误与安全边界")
    add_table(
        doc,
        ["错误", "阶段", "处理"],
        [
            ["ModelManifestError", "模型准备", "拒绝越界路径、缺失文件或哈希不符"],
            ["ChunkingError", "文本分块", "记录 file_id，继续其他文件"],
            ["EmbeddingError", "模型推理", "记录 file_id/chunk_id，批次降级为单项隔离"],
            ["ValueError", "相似度接口", "拒绝跨空间、跨维度或未归一化向量"],
        ],
        [2200, 1700, 5460],
    )
    add_list(
        doc,
        [
            "运行时模型加载不允许自动联网。",
            "日志和报告不保存全文、完整用户路径或向量内容。",
            "MobileCLIP 权重受 Apple Research Model License 约束，不进入公开代码包。",
            "模型清单中的相对路径必须位于配置的模型根目录内。",
        ],
    )
    return save(doc, "多模态嵌入模块API文档.docx")


def build_test_document(coverage: dict) -> Path:
    doc = new_report(
        ReportMeta(
            title="多模态嵌入模块测试报告",
            subtitle="单元测试、回归、覆盖率与离线转换验收",
            document_type="Verification Report",
        )
    )
    add_heading(doc, "1. 验收结论")
    add_body(doc, "结论：第三周嵌入引擎通过功能、回归、覆盖率和真实模型一致性验收。统一测试入口共 262 passed、1 skipped；后端覆盖率运行共 242 passed、1 skipped；嵌入包行覆盖率为 86.51%，高于 85% 门槛。", bold_lead="结论：")
    add_table(
        doc,
        ["质量门", "要求", "实测", "结果"],
        [
            ["统一回归", "无新增失败", "262 passed / 1 skipped", "通过"],
            ["嵌入覆盖率", ">= 85%", "86.51%", "通过"],
            ["文本 LiteRT", "cos >= 0.999; max error <= 1e-4", "0.9999999999995; 1.49e-7", "通过"],
            ["MobileCLIP 图像 LiteRT", "同上", "0.9999999980; 9.74e-6", "通过"],
            ["MobileCLIP 文本 LiteRT", "同上", "0.9999999999993; 2.98e-7", "通过"],
        ],
        [1900, 2600, 3300, 1560],
    )

    add_heading(doc, "2. 覆盖率明细")
    files = coverage["files"]
    coverage_rows = []
    for path, details in sorted(files.items()):
        name = Path(path).name
        summary = details["summary"]
        coverage_rows.append(
            [name, summary["num_statements"], summary["missing_lines"], f"{summary['percent_covered']:.0f}%"]
        )
    add_table(doc, ["模块", "语句", "未覆盖", "覆盖率"], coverage_rows, [3500, 1700, 1900, 2260])
    add_body(doc, "覆盖率报告覆盖 manifest、text、sentence_transformer、mobileclip、service 与包级惰性导出。生产适配器中依赖真实第三方模型的异常分支占主要未覆盖行；核心统一服务达到 100%。")

    add_heading(doc, "3. 功能测试矩阵")
    add_table(
        doc,
        ["模块", "主要测试点", "判定"],
        [
            ["模型清单", "路径约束、文件/目录哈希、重复 ID、未知 ID、缓存目录忽略", "通过"],
            ["文本分块", "页/段定位、重叠窗口、确定性 ID、空文本错误", "通过"],
            ["文本嵌入", "批处理、顺序、归一化、维度、零向量、失败隔离", "通过"],
            ["MobileCLIP", "图片/查询双入口、稳定查询 ID、EXIF/RGB、联合空间", "通过"],
            ["统一服务", "模态分派、输入位置、局部失败、跨空间拒绝", "通过"],
            ["评测工具", "NQ 指标、COCO Recall/median rank、数据装载校验", "通过"],
            ["转换工具", "形状、余弦、绝对误差、阈值报告、失败记录", "通过"],
        ],
        [1900, 5800, 1660],
    )

    add_heading(doc, "4. 真实模型冒烟")
    add_list(
        doc,
        [
            "多语言文本模型离线加载成功，输出 384 维，中文/英文相关文本相似度高于无关文本。",
            "MobileCLIP-S0 离线加载成功，图片和查询均输出 512 维单位向量；匹配描述得分高于无关描述。",
            "文本 TFLite 产物约 469.8 MB；MobileCLIP 图像/文本产物约 45.6 MB / 169.8 MB。",
            "LiteRT 基础 TinyModel 冒烟、真实模型转换和参考输出对比均成功。",
        ],
    )
    add_heading(doc, "5. 已知限制")
    add_list(
        doc,
        [
            "MobileCLIP 上游仍输出 timm.models.layers 弃用提醒，不影响数值和产物。",
            "MobileCLIP 文本模型将 EOT 索引计算放在主机 tokenizer 后处理，TFLite 接收 token IDs 与 EOT index 两个输入。",
            "1 个 skipped 来自既有环境依赖条件，不是第三周功能失败。",
            "覆盖率只衡量执行行，不替代真实模型、数据许可和端侧运行验收。",
        ],
    )
    return save(doc, "多模态嵌入模块测试报告.docx")


def build_accuracy_document(nq: dict, coco: dict, perf: dict) -> Path:
    doc = new_report(
        ReportMeta(
            title="模型准确率验证报告",
            subtitle="NQ 文本检索、COCO 文字搜图与 CPU 性能基线",
            document_type="Model Evaluation Report",
        )
    )
    add_heading(doc, "1. 评测设计")
    add_body(doc, "评测严格区分开发 validation 与冻结 benchmark。文本检索使用固定 40 查询、5,446 候选段落的 NQ 衍生 benchmark；文字搜图使用固定 40 图、201 caption 查询的 COCO 2017 benchmark。两个空间分别排名，不做跨空间分数混合。")
    add_table(
        doc,
        ["任务", "模型/空间", "冻结规模", "指标"],
        [
            ["文本检索", "text-multilingual-v1 / text-semantic-v1", "40 查询 / 5,446 段落", "Recall@K, MRR@10, nDCG@10"],
            ["文字搜图", "mobileclip-s0-v1 / mobileclip-image-text-v1", "40 图片 / 201 captions", "Recall@K, median rank"],
        ],
        [1700, 3000, 2200, 2460],
    )

    add_heading(doc, "2. NQ 文本检索结果")
    metrics = nq["metrics"]
    add_table(
        doc,
        ["指标", "结果"],
        [
            ["Recall@1", f"{metrics['recall@1']:.2%}"],
            ["Recall@5", f"{metrics['recall@5']:.2%}"],
            ["Recall@10", f"{metrics['recall@10']:.2%}"],
            ["MRR@10", f"{metrics['mrr@10']:.4f}"],
            ["nDCG@10", f"{metrics['ndcg@10']:.4f}"],
        ],
        [4680, 4680],
    )
    add_body(doc, "解释：该通用多语言句向量模型在未针对 NQ 进行专门检索训练的条件下，Recall@10 达到 59.58%。结果可作为第三周可复现基线，但尚不足以替代第四周的候选召回优化、重排或领域微调。")

    add_heading(doc, "3. COCO 文字搜图结果")
    cm = coco["metrics"]
    add_table(
        doc,
        ["指标", "结果"],
        [
            ["Recall@1", f"{cm['recall@1']:.2%}"],
            ["Recall@5", f"{cm['recall@5']:.2%}"],
            ["Recall@10", f"{cm['recall@10']:.2%}"],
            ["Median Rank", f"{cm['median_rank']:.0f}"],
        ],
        [4680, 4680],
    )
    add_body(doc, "解释：在 40 图冻结子集上，MobileCLIP 的 caption→image Recall@1 为 91.04%，Recall@5/10 为 100%，中位名次为 1。子集规模较小，结果用于验证本地跨模态管线与空间一致性，不宣称代表完整 COCO 榜单性能。")

    add_heading(doc, "4. CPU 性能基线")
    rows = []
    for item in perf["measurements"]:
        rows.append(
            [
                item["batch_size"],
                f"{item['p50_latency_ms']:.2f} ms",
                f"{item['p95_latency_ms']:.2f} ms",
                f"{item['throughput_items_per_second']:.2f} items/s",
            ]
        )
    add_table(doc, ["Batch", "P50", "P95", "吞吐"], rows, [1500, 2300, 2300, 3260])
    add_body(doc, f"测试设备：{perf['device']['processor']}；Python {perf['device']['python']}。文本模型本地目录体积为 {perf['model_size_bytes'] / 1_000_000:.1f} MB。Batch 16 将吞吐提升至 346.50 items/s，适合离线批量建库。")

    add_heading(doc, "5. 可复现性与限制")
    add_list(
        doc,
        [
            "NQ 与 COCO 选择规则均由稳定 SHA-256 排序固定，冻结 benchmark 不用于调参。",
            "所有模型按固定 revision 下载并通过本地 SHA-256 清单验证。",
            "COCO 每张图片保留 Flickr/COCO URL、许可证 ID/URL 与文件 SHA-256；图片二进制不进入公开包。",
            "性能结果受 CPU、线程调度、句长和缓存状态影响，应在目标设备上重新测量。",
            "NQ 衍生数据按 CC BY-SA 3.0 保守处理；MobileCLIP 权重按 Apple Research Model License 管理。",
        ],
    )
    return save(doc, "模型准确率验证报告.docx")


def build_weekly_document(nq: dict, coco: dict) -> Path:
    doc = new_report(
        ReportMeta(
            title="第三周工作周报",
            subtitle="多模态嵌入引擎、端侧导出与检索评测",
            document_type="Weekly Engineering Report",
        )
    )
    add_heading(doc, "1. 本周目标与完成度")
    add_body(doc, "本周完成离线双空间嵌入引擎：文本分块与多语言向量、MobileCLIP 图片/文字向量、统一批处理服务、模型清单校验、LiteRT 导出、NQ/COCO 冻结评测、覆盖率与正式交付材料。范围内任务全部落地并通过回归。")
    add_table(
        doc,
        ["工作项", "产物", "状态"],
        [
            ["P0 契约与分块", "TextChunk / EmbeddingVector / TextChunker", "完成"],
            ["文本嵌入", "本地 Sentence Transformer + 清单", "完成"],
            ["图片与图文嵌入", "MobileCLIP-S0 双编码入口", "完成"],
            ["统一服务", "模态分派、顺序元数据、失败隔离", "完成"],
            ["端侧导出", "3 个真实 LiteRT 模型与一致性证据", "完成"],
            ["准确率与性能", "NQ、COCO、CPU batch 基线", "完成"],
            ["质量与交付", "262 项回归、覆盖率、四份 DOCX、代码 ZIP", "完成"],
        ],
        [2400, 5200, 1760],
    )

    add_heading(doc, "2. 关键工程决策")
    add_list(
        doc,
        [
            "采用 text-semantic-v1 与 mobileclip-image-text-v1 两个独立空间，接口层阻止跨空间相似度。",
            "EmbeddingVector 使用通用 source_id，使文本分块和图片共享同一输出契约。",
            "模型只从本地路径加载，并通过 revision、SHA-256、许可证和运行时字段形成可审计清单。",
            "批次失败递归降级到单项，保证坏文件或坏向量不终止整批任务。",
            "冻结 benchmark 与 validation 分离，报告只引用机器可读证据。",
        ],
    )

    add_heading(doc, "3. 量化结果")
    add_table(
        doc,
        ["指标", "结果"],
        [
            ["统一 Python 回归", "262 passed / 1 skipped"],
            ["嵌入包覆盖率", "86.51%（门槛 85%）"],
            ["NQ Recall@10", f"{nq['metrics']['recall@10']:.2%}"],
            ["NQ MRR@10", f"{nq['metrics']['mrr@10']:.4f}"],
            ["COCO Recall@1", f"{coco['metrics']['recall@1']:.2%}"],
            ["COCO Recall@5 / @10", "100% / 100%"],
            ["文本 LiteRT 最大绝对误差", "1.49e-7"],
            ["MobileCLIP 图像/文本最大绝对误差", "9.74e-6 / 2.98e-7"],
        ],
        [4400, 4960],
    )

    add_heading(doc, "4. 问题与解决")
    add_table(
        doc,
        ["问题", "解决方案", "结果"],
        [
            ["MobileCLIP 文本图内 arg_max 无法被 LiteRT 合法化", "把 EOT index 移至 tokenizer 后的主机预处理，图内改用 gather", "文本 TFLite 成功导出"],
            ["NQ 存在标题非空、正文为空的合法段落", "允许 title/text 至少一项非空，并新增回归测试", "5,446 段落全部纳入"],
            ["模型工具导入 MobileCLIP 时被解析器依赖耦合", "包级统一服务改为惰性导出", "模型环境无需 PDF 依赖"],
            ["COCO HTTPS 端点证书主机名不匹配", "不关闭 TLS 校验，使用官方 HTTP 端点并记录 SHA-256", "标注包可审计"],
            ["COCO 顺序下载过慢", "8 路并发、原子写入、完整文件复用", "200 图准备完成"],
        ],
        [3000, 4300, 2060],
    )

    add_heading(doc, "5. 风险与下周建议")
    add_list(
        doc,
        [
            "文本 NQ Recall@1 仍偏低；第四周应增加向量库候选召回、查询/文档提示词验证与可选重排。",
            "MobileCLIP 权重与转换产物受研究模型许可约束，发布流程必须继续与代码包分离。",
            "Flutter 端需要按导出契约实现 tokenizer、EOT index、图像归一化和两个独立集合。",
            "建立 ChromaDB 双集合后，增加真实端到端 P50/P95 与索引增量更新测试。",
            "在目标 Windows/Android 设备复测 LiteRT 线程、内存和批大小，避免只依赖开发机数据。",
        ],
    )
    return save(doc, "第三周工作周报.docx")


def audit_document(path: Path) -> None:
    doc = Document(path)
    section = doc.sections[0]
    assert section.page_width == Inches(8.5)
    assert section.page_height == Inches(11)
    assert section.left_margin == Inches(1)
    assert section.right_margin == Inches(1)
    for paragraph in list(doc.paragraphs) + list(section.header.paragraphs) + list(section.footer.paragraphs):
        for run in paragraph.runs:
            assert run.font.name == FONT, (path.name, paragraph.text, run.font.name)
            if run.font.color.type is not None and run.font.color.rgb is not None:
                assert run.font.color.rgb == BLACK, (path.name, paragraph.text, run.font.color.rgb)
    for table in doc.tables:
        tblpr = table._tbl.tblPr
        assert tblpr.find(qn("w:tblW")).get(qn("w:w")) == str(CONTENT_WIDTH_DXA)
        assert tblpr.find(qn("w:tblInd")).get(qn("w:w")) == str(TABLE_INDENT_DXA)
        grid = [int(node.get(qn("w:w"))) for node in table._tbl.tblGrid]
        assert sum(grid) == CONTENT_WIDTH_DXA
        for row in table.rows:
            assert len(row.cells) == len(grid)
            for cell, width in zip(row.cells, grid, strict=True):
                tcw = cell._tc.get_or_add_tcPr().find(qn("w:tcW"))
                assert tcw.get(qn("w:w")) == str(width)
                shd = cell._tc.get_or_add_tcPr().find(qn("w:shd"))
                assert shd is not None and shd.get(qn("w:fill")) == WHITE
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        if not run.text:
                            continue
                        assert run.font.name == FONT, (
                            path.name,
                            paragraph.text,
                            run.text,
                            run.font.name,
                        )
                        assert run.font.color.rgb == BLACK, (
                            path.name,
                            paragraph.text,
                            run.text,
                            run.font.color.rgb,
                        )


def main() -> int:
    coverage = json.loads((OUTPUT_DIR / "embedding-coverage.json").read_text(encoding="utf-8"))
    nq = json.loads((EVIDENCE_DIR / "nq-benchmark-summary.json").read_text(encoding="utf-8"))
    coco = json.loads((EVIDENCE_DIR / "coco-benchmark-summary.json").read_text(encoding="utf-8"))
    perf = json.loads((EVIDENCE_DIR / "text-performance-summary.json").read_text(encoding="utf-8"))
    paths = [
        build_api_document(),
        build_test_document(coverage),
        build_accuracy_document(nq, coco, perf),
        build_weekly_document(nq, coco),
    ]
    for path in paths:
        audit_document(path)
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
