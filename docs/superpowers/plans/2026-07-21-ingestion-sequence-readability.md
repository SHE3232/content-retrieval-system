# Ingestion Sequence Diagram Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redraw the Week 2 ingestion sequence diagram so every message label is readable and the behavior note no longer overlaps lifelines or arrows.

**Architecture:** Keep the existing Pillow-based diagram generator and DOCX builder. Extract the geometry into a pure layout function that can be regression-tested, render the note as a full-width band below the sequence area, then rebuild only the architecture report and verify it through Microsoft Word rendering.

**Tech Stack:** Python 3.12, Pillow, python-docx, unittest, Microsoft Word COM, pypdfium2

---

## File map

- Modify: `tmp/docx/build_week2_reports.py` — sequence diagram geometry, typography, labels, and note-band drawing.
- Create: `tmp/docx/test_week2_sequence_diagram.py` — geometry and output-image regression checks.
- Regenerate: `tmp/week2-deliverables/assets/current-ingestion-sequence.png` — high-resolution diagram asset used by the report builder.
- Regenerate: `docs/week2/reports/01_系统架构设计.docx` — final architecture report containing the revised figure.

### Task 1: Add a failing layout regression test

**Files:**
- Create: `tmp/docx/test_week2_sequence_diagram.py`
- Test: `tmp/docx/test_week2_sequence_diagram.py`

- [ ] **Step 1: Write the failing geometry and rendering tests**

```python
from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_week2_reports as reports


class SequenceDiagramReadabilityTest(unittest.TestCase):
    def test_note_band_is_separate_from_sequence_area(self):
        layout = reports.sequence_diagram_layout()
        event_bottom = max(event[0] for event in layout["events"])
        note_left, note_top, note_right, note_bottom = layout["note_box"]

        self.assertGreaterEqual(note_top - event_bottom, 90)
        self.assertLess(layout["lifeline_bottom"], note_top)
        self.assertGreater(note_right, note_left)
        self.assertLessEqual(note_bottom, layout["canvas"][1])

    def test_lanes_and_message_type_are_large_enough(self):
        layout = reports.sequence_diagram_layout()
        gaps = [right - left for left, right in zip(layout["xs"], layout["xs"][1:])]

        self.assertGreaterEqual(min(gaps), 390)
        self.assertGreaterEqual(layout["message_font_size"], 30)
        self.assertGreaterEqual(layout["note_font_size"], 28)

    def test_rendered_asset_has_expected_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sequence.png"
            reports.build_sequence_diagram(output)
            with Image.open(output) as image:
                self.assertEqual(reports.sequence_diagram_layout()["canvas"], image.size)
                self.assertEqual("RGB", image.mode)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the new layout API is missing**

Run:

```powershell
$py='C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m unittest tmp/docx/test_week2_sequence_diagram.py -v
```

Expected: FAIL with `AttributeError: module 'build_week2_reports' has no attribute 'sequence_diagram_layout'`.

- [ ] **Step 3: Commit the failing regression test**

```powershell
git add -- tmp/docx/test_week2_sequence_diagram.py
git commit -m "test: cover sequence diagram readability layout"
```

### Task 2: Implement the non-overlapping diagram layout

**Files:**
- Modify: `tmp/docx/build_week2_reports.py:537-579`
- Test: `tmp/docx/test_week2_sequence_diagram.py`

- [ ] **Step 1: Add a pure layout function above `build_sequence_diagram`**

```python
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
```

- [ ] **Step 2: Replace `build_sequence_diagram` with the approved bottom-note layout**

```python
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
```

- [ ] **Step 3: Run the regression tests**

Run:

```powershell
$py='C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m unittest tmp/docx/test_week2_sequence_diagram.py -v
```

Expected: 3 tests run, all `OK`.

- [ ] **Step 4: Render and inspect the standalone PNG**

Run:

```powershell
$py='C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -c "from pathlib import Path; import sys; sys.path.insert(0, r'F:\contentretrivalsystem\tmp\docx'); import build_week2_reports as r; r.build_sequence_diagram(Path(r'F:\contentretrivalsystem\tmp\docx\sequence-readability-preview.png'))"
```

Expected: a 2400 × 1800 white-background PNG with the note band below all lifelines and message arrows.

- [ ] **Step 5: Commit the diagram implementation**

```powershell
git add -- tmp/docx/build_week2_reports.py
git commit -m "docs: improve ingestion sequence readability"
```

### Task 3: Rebuild and verify the architecture report

**Files:**
- Regenerate: `tmp/week2-deliverables/assets/current-ingestion-sequence.png`
- Regenerate: `docs/week2/reports/01_系统架构设计.docx`
- Test: `tmp/docx/test_week2_sequence_diagram.py`

- [ ] **Step 1: Rebuild only the architecture report**

Run:

```powershell
$py='C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -c "import sys; sys.path.insert(0, r'F:\contentretrivalsystem\tmp\docx'); import build_week2_reports as r; print(r.build_architecture_doc())"
```

Expected: `F:\contentretrivalsystem\docs\week2\reports\01_系统架构设计.docx` is regenerated and the builder's Times New Roman / black / white validation passes.

- [ ] **Step 2: Run the document and image audits**

Run:

```powershell
$py='C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$skill='C:\Users\Aaron\.codex\plugins\cache\openai-primary-runtime\documents\26.715.12143\skills\documents'
$doc='F:\contentretrivalsystem\docs\week2\reports\01_系统架构设计.docx'
& $py "$skill\scripts\images_audit.py" $doc
& $py "$skill\scripts\a11y_audit.py" $doc
& $py "$skill\scripts\table_geometry.py" $doc
```

Expected: two inline images, zero high/medium/low accessibility findings, and matching table geometry.

- [ ] **Step 3: Export through Microsoft Word and rasterize every page**

Run:

```powershell
$doc='F:\contentretrivalsystem\docs\week2\reports\01_系统架构设计.docx'
$qa='F:\contentretrivalsystem\tmp\docx\week2-architecture-readability-qa'
$pdf=Join-Path $qa '01_系统架构设计_QA.pdf'
$pages=Join-Path $qa 'pages'
New-Item -ItemType Directory -Force -Path $qa,$pages | Out-Null
powershell -ExecutionPolicy Bypass -File 'C:\Users\Aaron\.codex\skills\windows-docx-finalize\scripts\export-docx-pdf.ps1' -DocxPath $doc -PdfPath $pdf
$py='C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py 'F:\contentretrivalsystem\tmp\docx\render_pdf_pages.py' $pdf $pages
```

Expected: Word reports `status=ok`; page PNGs are produced for the complete document.

- [ ] **Step 4: Inspect every page at original resolution**

Check every `page-<N>.png`, with special attention to the page containing “图 2 当前任务创建、解析与查询时序”. Confirm:

- every message label is readable;
- the note band is entirely below the sequence area;
- no text, arrow, lifeline, caption, table, header, or footer overlaps or clips;
- the page count and surrounding content remain stable.

- [ ] **Step 5: Run the final regression test and hash the deliverable**

Run:

```powershell
$py='C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m unittest tmp/docx/test_week2_sequence_diagram.py -v
Get-FileHash -Algorithm SHA256 'F:\contentretrivalsystem\docs\week2\reports\01_系统架构设计.docx'
```

Expected: all tests pass and a SHA-256 hash is printed for the final DOCX.

- [ ] **Step 6: Commit the regenerated report and asset**

```powershell
git add -- docs/week2/reports/01_系统架构设计.docx tmp/week2-deliverables/assets/current-ingestion-sequence.png
git commit -m "docs: refresh architecture report sequence diagram"
```
