# Five-Minute Project Demo Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a record-ready five-minute Chinese project-demo script, reproducible five-format demo data, and a verified contingency playbook for the local multimodal content-retrieval system.

**Architecture:** A deterministic Python generator creates five small fixtures plus a machine-readable manifest without modifying the application index. A single Markdown runbook owns the second-by-second screen actions, narration, expected results, accessibility proof, and failure fallbacks; lightweight `unittest` checks lock its required sections and prevent unsupported claims.

**Tech Stack:** Markdown, bundled Python 3.12 document runtime, `python-docx`, ReportLab, Pillow, `pypdfium2`, standard-library `unittest`, and the existing Flutter/FastAPI application.

---

## File structure

| Path | Responsibility |
|---|---|
| `tools/demo/__init__.py` | Makes demo tooling importable. |
| `tools/demo/generate_demo_data.py` | Generates five deterministic demo files and `MANIFEST.json`; never indexes or deletes user files. |
| `tools/demo/tests/test_generate_demo_data.py` | Opens each artifact and verifies searchable content or visual identity. |
| `tools/demo/tests/test_demo_materials.py` | Locks the runbook structure, UI wording, time boundary, and claim guardrails. |
| `docs/demo/PROJECT_DEMO_VIDEO_SCRIPT.md` | Owns preparation, timeline, narration, expected results, editing notes, and contingencies. |
| `docs/demo/README.md` | Provides short generation and rehearsal instructions. |
| `demo-data/project-demo/` | Holds the generated five-format recording fixtures and manifest. |

Preserve the existing dirty worktree. Stage and commit only paths named in this plan.

### Task 1: Build the deterministic five-format data generator

**Files:**
- Create: `tools/demo/__init__.py`
- Create: `tools/demo/generate_demo_data.py`
- Create: `tools/demo/tests/test_generate_demo_data.py`

- [ ] **Step 1: Write the failing generator tests**

Create `tools/demo/tests/test_generate_demo_data.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

import pypdfium2
from docx import Document
from PIL import Image

from tools.demo.generate_demo_data import EXPECTED_FILES, generate_demo_data


class GenerateDemoDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_generates_exact_fixture_set_and_manifest(self) -> None:
        manifest = generate_demo_data(self.root)
        self.assertEqual(
            {path.name for path in self.root.iterdir()},
            EXPECTED_FILES | {"MANIFEST.json"},
        )
        persisted = json.loads(
            (self.root / "MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest, persisted)
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(len(manifest["files"]), 5)

    def test_text_document_and_pdf_contain_search_contracts(self) -> None:
        generate_demo_data(self.root)
        text = (self.root / "01_课程检索笔记.txt").read_text(encoding="utf-8")
        self.assertIn("星桥检索协议", text)
        document = Document(self.root / "03_离线系统方案.docx")
        docx_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        self.assertIn("不会发送到云端", docx_text)
        pdf = pypdfium2.PdfDocument(self.root / "02_无障碍设计指南.pdf")
        pdf_text = "\n".join(
            pdf[index].get_textpage().get_text_range() for index in range(len(pdf))
        )
        self.assertIn("DEMO-PDF-ACCESSIBILITY", pdf_text)

    def test_images_have_expected_shape_colours(self) -> None:
        generate_demo_data(self.root)
        with Image.open(self.root / "04_红色苹果.jpg") as apple:
            red, green, blue = apple.convert("RGB").getpixel((256, 256))
            self.assertGreater(red, 180)
            self.assertLess(green, 80)
            self.assertLess(blue, 80)
        with Image.open(self.root / "05_蓝色方块.png") as square:
            red, green, blue = square.convert("RGB").getpixel((256, 256))
            self.assertLess(red, 60)
            self.assertLess(green, 130)
            self.assertGreater(blue, 180)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the missing-module failure**

```powershell
$env:TEMP = 'F:\contentretrivalsystem\.tmp\demo-tests'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
& 'C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  -m unittest tools.demo.tests.test_generate_demo_data -v
```

Expected: `ERROR` with `ModuleNotFoundError: No module named 'tools.demo.generate_demo_data'`.

- [ ] **Step 3: Implement the generator**

Create an empty `tools/demo/__init__.py`. Implement `tools/demo/generate_demo_data.py` with this public contract:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


EXPECTED_FILES = {
    "01_课程检索笔记.txt",
    "02_无障碍设计指南.pdf",
    "03_离线系统方案.docx",
    "04_红色苹果.jpg",
    "05_蓝色方块.png",
}


def _refuse_unowned_directory(root: Path, force: bool) -> None:
    if not root.exists() or not any(root.iterdir()):
        return
    if force and (root / "MANIFEST.json").exists():
        return
    raise FileExistsError(
        f"Refusing to write into non-empty directory without an owned manifest: {root}"
    )


def _write_pdf(path: Path) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setTitle("无障碍设计指南")
    pdf.setFont("STSong-Light", 20)
    pdf.drawString(72, 780, "无障碍设计指南")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(72, 752, "DEMO-PDF-ACCESSIBILITY")
    pdf.setFont("STSong-Light", 12)
    lines = [
        "键盘用户可以通过 Tab 键依次访问搜索框、筛选器和结果操作。",
        "界面提供高对比度、最高 200% 字号和减少动态效果选项。",
        "关键状态同时使用文字与图标表达，不只依赖颜色。",
    ]
    for index, line in enumerate(lines):
        pdf.drawString(72, 714 - index * 28, line)
    pdf.save()


def _write_docx(path: Path) -> None:
    document = Document()
    document.add_heading("离线系统方案", level=1)
    document.add_paragraph(
        "系统在没有网络连接的环境中仍可运行。资料解析、检索请求和结果排序都在当前设备上完成。"
    )
    document.add_paragraph(
        "用户文件、搜索内容和命中片段不会发送到云端，从而降低私人学习资料外泄的风险。"
    )
    document.save(path)


def _write_images(root: Path) -> None:
    apple = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(apple)
    draw.ellipse((96, 96, 416, 416), fill=(220, 30, 30), outline=(90, 0, 0), width=12)
    draw.polygon([(256, 105), (285, 45), (312, 112)], fill=(20, 130, 45))
    apple.save(root / "04_红色苹果.jpg", quality=95)
    square = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(square)
    draw.rectangle((96, 96, 416, 416), fill=(25, 90, 220), outline=(0, 25, 90), width=12)
    square.save(root / "05_蓝色方块.png")


def generate_demo_data(root: Path, *, force: bool = False) -> dict[str, object]:
    root = root.resolve()
    _refuse_unowned_directory(root, force)
    root.mkdir(parents=True, exist_ok=True)
    (root / "01_课程检索笔记.txt").write_text(
        "课程资料整理约定\n\n星桥检索协议用于标记本次课程演示资料。\n"
        "本地内容检索可以根据记得的句子找到文件，而不要求用户记住文件名。\n",
        encoding="utf-8",
    )
    _write_pdf(root / "02_无障碍设计指南.pdf")
    _write_docx(root / "03_离线系统方案.docx")
    _write_images(root)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "generated_by": "tools/demo/generate_demo_data.py",
        "files": [
            {"name": "01_课程检索笔记.txt", "query": "星桥检索协议", "mode": "精确"},
            {"name": "02_无障碍设计指南.pdf", "query": "哪个文档介绍了不用鼠标操作界面", "mode": "文本语义"},
            {"name": "03_离线系统方案.docx", "query": "怎样在断网时保护本地文档隐私", "mode": "文本语义"},
            {"name": "04_红色苹果.jpg", "query": "a simple red apple on a white background", "mode": "图像语义"},
            {"name": "05_蓝色方块.png", "query": "a simple blue square on a white background", "mode": "图像语义"},
        ],
    }
    (root / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate fixed project-demo fixtures")
    parser.add_argument("output", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    generate_demo_data(args.output, force=args.force)
    print(f"Generated five demo files in {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Re-run Task 1 tests**

Expected: three tests report `ok` and the command ends with `OK`.

- [ ] **Step 5: Commit the generator unit**

```powershell
git add -- tools/demo/__init__.py tools/demo/generate_demo_data.py tools/demo/tests/test_generate_demo_data.py
git commit -m "feat: add deterministic project demo fixtures"
```

### Task 2: Write and contract-test the recording materials

**Files:**
- Create: `tools/demo/tests/test_demo_materials.py`
- Create: `docs/demo/PROJECT_DEMO_VIDEO_SCRIPT.md`
- Create: `docs/demo/README.md`

- [ ] **Step 1: Write the failing documentation contract test**

Create `tools/demo/tests/test_demo_materials.py`:

```python
import unittest
from pathlib import Path


class DemoMaterialsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = Path("docs/demo/PROJECT_DEMO_VIDEO_SCRIPT.md").read_text(
            encoding="utf-8"
        )

    def test_required_sections_and_time_boundary_are_present(self) -> None:
        for heading in (
            "## 一、成片目标",
            "## 二、录制前准备",
            "## 三、五分钟逐秒演示脚本",
            "## 四、测试数据与预期结果",
            "## 五、异常预案",
            "## 六、录制验收清单",
        ):
            self.assertIn(heading, self.script)
        self.assertIn("4:45–5:00", self.script)
        self.assertNotIn("5:01", self.script)

    def test_current_ui_copy_and_supported_claims(self) -> None:
        for copy in (
            "添加资料文件夹", "搜索资料", "精确", "综合", "语义",
            "打开文件", "高对比度", "减少动态效果",
        ):
            self.assertIn(copy, self.script)
        for unsupported in ("WebP 可索引", "准确率 100%", "置信度百分比"):
            self.assertNotIn(unsupported, self.script)

    def test_fixtures_and_queries_are_documented(self) -> None:
        for value in (
            "01_课程检索笔记.txt", "02_无障碍设计指南.pdf",
            "03_离线系统方案.docx", "04_红色苹果.jpg",
            "05_蓝色方块.png", "星桥检索协议",
            "a simple red apple on a white background",
        ):
            self.assertIn(value, self.script)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it and verify `FileNotFoundError` for the absent runbook**

```powershell
& 'C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  -m unittest tools.demo.tests.test_demo_materials -v
```

- [ ] **Step 3: Write `docs/demo/PROJECT_DEMO_VIDEO_SCRIPT.md`**

Use sections “成片目标、录制前准备、五分钟逐秒演示脚本、测试数据与预期结果、异常预案、录制验收清单”. The main table must contain these exact action/narration anchors:

| Time | Screen action | Narration anchor |
|---|---|---|
| 0:00–0:25 | Title then Search page | “我们经常记得内容，却忘了文件名和位置。本项目让用户在不上传资料的情况下检索本地文档和图片。” |
| 0:25–1:05 | Index Library → `添加资料文件夹` → running → completed | “这里加入包含 TXT、PDF、DOCX、JPEG 和 PNG 的资料夹；完成后五个文件都进入可搜索状态。” |
| 1:05–1:50 | `精确` + `星桥检索协议` | “精确检索适合已知短语，结果给出命中片段、来源路径和段落位置。” |
| 1:50–2:40 | `语义` + `哪个文档介绍了不用鼠标操作界面` | “即使没有照抄原文，文本语义检索仍能找到无障碍设计指南。” |
| 2:40–3:25 | Image-semantic only + English apple query | “图像语义通道让文字描述匹配图片内容，目标苹果图片出现在结果中。” |
| 3:25–3:55 | Reset to `综合`, filter, copy path, open file | “用户可以缩小范围，也能直接打开原文件或复制完整路径。” |
| 3:55–4:25 | High contrast, 150% text, reduced motion, `Ctrl+1` | “高对比度、字号、减少动态效果和键盘导航是产品基线。” |
| 4:25–4:45 | Pre-recorded offline error then recovery | “服务断开时界面会给出可理解的提示，恢复后可以继续检索。” |
| 4:45–5:00 | Results plus four closing keywords | “项目完成了本地离线、五类文件、多模态检索和无障碍交互的一体化闭环。” |

Add exact actions, spoken lines, expected screen evidence, editing notes, and fallback narration for: offline service, slow index, partial failure, no result, unstable ranking, missing file, accessibility layout issue, and runtime overrun. Do not claim WebP indexing, probabilities, or unverified accuracy.

- [ ] **Step 4: Write `docs/demo/README.md`**

```markdown
# 项目演示材料

- [五分钟项目演示脚本](PROJECT_DEMO_VIDEO_SCRIPT.md)
- 测试数据生成器：`tools/demo/generate_demo_data.py`
- 默认数据目录：`demo-data/project-demo/`

## 生成测试数据

```powershell
& 'C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  tools/demo/generate_demo_data.py demo-data/project-demo --force
```

生成后先按主脚本的“录制前准备”逐项试跑，再开始录制。
```

- [ ] **Step 5: Re-run Task 2 tests**

Expected: three tests report `ok` and the command ends with `OK`.

- [ ] **Step 6: Commit the recording materials**

```powershell
git add -- docs/demo/PROJECT_DEMO_VIDEO_SCRIPT.md docs/demo/README.md tools/demo/tests/test_demo_materials.py
git commit -m "docs: add five-minute project demo runbook"
```

### Task 3: Generate and inspect the deliverable test data

**Files:**
- Create: `demo-data/project-demo/01_课程检索笔记.txt`
- Create: `demo-data/project-demo/02_无障碍设计指南.pdf`
- Create: `demo-data/project-demo/03_离线系统方案.docx`
- Create: `demo-data/project-demo/04_红色苹果.jpg`
- Create: `demo-data/project-demo/05_蓝色方块.png`
- Create: `demo-data/project-demo/MANIFEST.json`

- [ ] **Step 1: Generate fixtures on the F drive**

```powershell
$env:TEMP = 'F:\contentretrivalsystem\.tmp\demo-generation'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
& 'C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  tools/demo/generate_demo_data.py demo-data/project-demo --force
```

Expected: `Generated five demo files in F:\contentretrivalsystem\demo-data\project-demo`.

- [ ] **Step 2: Verify exact inventory and non-zero sizes**

```powershell
Get-ChildItem -LiteralPath 'demo-data/project-demo' -File |
  Sort-Object Name |
  Select-Object Name,Length
```

Expected: exactly the five fixtures plus `MANIFEST.json`.

- [ ] **Step 3: Run every demo test**

```powershell
& 'C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  -m unittest discover -s tools/demo/tests -p 'test_*.py' -v
```

Expected: six tests report `ok` and the command ends with `OK`.

- [ ] **Step 4: Commit only the six generated artifacts**

```powershell
git add -- `
  'demo-data/project-demo/01_课程检索笔记.txt' `
  'demo-data/project-demo/02_无障碍设计指南.pdf' `
  'demo-data/project-demo/03_离线系统方案.docx' `
  'demo-data/project-demo/04_红色苹果.jpg' `
  'demo-data/project-demo/05_蓝色方块.png' `
  'demo-data/project-demo/MANIFEST.json'
git commit -m "testdata: add project demo fixture set"
```

### Task 4: Rehearse the live path and finalize

**Files:**
- Modify only if rehearsal changes a verified expectation: `docs/demo/PROJECT_DEMO_VIDEO_SCRIPT.md`

- [ ] **Step 1: Run the MVP preflight**

```powershell
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1 -CheckOnly
```

Expected: `MVP preflight passed`. If it fails, use a previously verified joined-index recording and do not claim a fresh live index succeeded.

- [ ] **Step 2: Start the service and check readiness**

```powershell
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1
```

In a second terminal run `Invoke-RestMethod http://127.0.0.1:8000/health/ready`; expected `status=ready`.

- [ ] **Step 3: Rehearse the exact UI path twice**

Add `F:\contentretrivalsystem\demo-data\project-demo`, then verify twice:

1. `精确` + `星桥检索协议` returns `01_课程检索笔记.txt`.
2. Text semantic + `哪个文档介绍了不用鼠标操作界面` includes `02_无障碍设计指南.pdf`.
3. Image semantic + `a simple red apple on a white background` includes `04_红色苹果.jpg` in the first visible results.
4. Content filters leave matching MIME groups.
5. `复制路径` shows `路径已复制`; `打开文件` opens the fixture.

If ordering differs, change narration from “第一条” to “结果中” rather than inventing a guarantee.

- [ ] **Step 4: Run final checks**

```powershell
git diff --check
git status --short
& 'C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  -m unittest discover -s tools/demo/tests -p 'test_*.py' -v
```

Expected: no whitespace errors, only pre-existing unrelated working-tree changes remain, and all six demo tests pass.

- [ ] **Step 5: Commit only a rehearsal-driven wording correction**

If Step 3 changed wording:

```powershell
git add -- docs/demo/PROJECT_DEMO_VIDEO_SCRIPT.md
git commit -m "docs: align demo narration with rehearsed results"
```

If no wording changed, make no commit.
