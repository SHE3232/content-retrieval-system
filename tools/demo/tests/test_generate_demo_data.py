import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from PIL import Image
from pypdfium2 import PdfDocument

from tools.demo.generate_demo_data import EXPECTED_FILES, generate_demo_data


class DemoDataGeneratorTests(unittest.TestCase):
    def test_generates_exact_five_files_and_matching_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo"
            result = generate_demo_data(out)
            self.assertEqual(set(p.name for p in out.iterdir()), set(EXPECTED_FILES) | {"MANIFEST.json"})
            manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["generated_by"], "tools/demo/generate_demo_data.py")
            self.assertEqual(len(manifest["files"]), 5)
            self.assertEqual(result, manifest)
            self.assertEqual({entry["name"] for entry in manifest["files"]}, set(EXPECTED_FILES))
            expected = [
                (EXPECTED_FILES[0], "星桥检索协议", "精确"),
                (EXPECTED_FILES[1], "哪个文档介绍了不用鼠标操作界面", "文本语义"),
                (EXPECTED_FILES[2], "怎样在断网时保护本地文档隐私", "文本语义"),
                (EXPECTED_FILES[3], "a simple red apple on a white background", "图像语义"),
                (EXPECTED_FILES[4], "a simple blue square on a white background", "图像语义"),
            ]
            self.assertEqual([(e["name"], e["query"], e["mode"]) for e in manifest["files"]], expected)
            for entry in manifest["files"]:
                self.assertIn("query", entry)
                self.assertIn("mode", entry)

    def test_text_and_office_documents_contain_demo_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_demo_data(out)
            txt = (out / "01_课程检索笔记.txt").read_text(encoding="utf-8")
            self.assertIn("星桥检索协议", txt)
            self.assertIn("按内容检索", txt)
            self.assertIn("无需记住文件名", txt)
            doc = Document(out / "03_离线系统方案.docx")
            text = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("本机完成", text); self.assertIn("解析、检索与排序", text)
            self.assertIn("不会发送到云端", text)
            self.assertEqual(doc.styles["Normal"].font.name, "Times New Roman")
            self.assertEqual(doc.styles["Title"].font.name, "Times New Roman")
            self.assertEqual(doc.styles["Heading 1"].font.name, "Times New Roman")
            with ZipFile(out / "03_离线系统方案.docx") as archive:
                styles_xml = archive.read("word/styles.xml").decode("utf-8")
            self.assertIn('w:eastAsia="Times New Roman"', styles_xml)

    def test_pdf_and_images_are_real_and_contentful(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_demo_data(out)
            pdf = PdfDocument(str(out / "02_无障碍设计指南.pdf"))
            extracted = "".join(page.get_textpage().get_text_range() for page in pdf)
            pdf.close()
            for phrase in ("DEMO-PDF-ACCESSIBILITY", "Tab", "高对比度", "200%", "减少动态效果"):
                self.assertIn(phrase, extracted)
            with Image.open(out / "04_红色苹果.jpg") as apple:
                self.assertEqual(apple.size, (512, 512))
                r, g, b = apple.convert("RGB").getpixel((256, 256))
                self.assertGreater(r, 180); self.assertLess(g, 100); self.assertLess(b, 100)
                self.assertEqual(apple.convert("RGB").getpixel((0, 0)), (255, 255, 255))
                self.assertGreater(apple.convert("RGB").getpixel((330, 90))[1], 100)
            with Image.open(out / "05_蓝色方块.png") as square:
                self.assertEqual(square.size, (512, 512))
                r, g, b = square.convert("RGB").getpixel((256, 256))
                self.assertLess(r, 100); self.assertLess(g, 180); self.assertGreater(b, 180)
                self.assertEqual(square.convert("RGB").getpixel((0, 0)), (255, 255, 255))

    def test_nonempty_output_requires_force_and_force_preserves_unknown_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); out.mkdir(exist_ok=True)
            (out / "unknown.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError): generate_demo_data(out)
            (out / "unknown.txt").unlink()
            out.rmdir()
            generate_demo_data(out)
            (out / "unknown.txt").write_text("keep", encoding="utf-8")
            generate_demo_data(out, force=True)
            self.assertEqual((out / "unknown.txt").read_text(encoding="utf-8"), "keep")

    def test_force_rejects_foreign_or_invalid_manifest_without_modifying_files(self):
        for manifest in (
            {"schema_version": 1, "generated_by": "other.py", "files": []},
            {"schema_version": 2, "generated_by": "tools/demo/generate_demo_data.py", "files": []},
            {"schema_version": 1, "generated_by": "tools/demo/generate_demo_data.py", "files": [{"name": EXPECTED_FILES[0]}]},
            {"schema_version": 1, "generated_by": "tools/demo/generate_demo_data.py", "files": [{"name": name} for name in EXPECTED_FILES[:-1]]},
        ):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp); sentinel = out / EXPECTED_FILES[0]
                sentinel.write_text("sentinel", encoding="utf-8")
                (out / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(FileExistsError): generate_demo_data(out, force=True)
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "sentinel")

    def test_cli_generates_six_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "cli"
            python = r"C:\Users\Aaron\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
            completed = subprocess.run([python, "tools/demo/generate_demo_data.py", str(output)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(f"Generated five demo files in {output.resolve()}", completed.stdout)
            self.assertEqual(len(list(output.iterdir())), 6)


if __name__ == "__main__":
    unittest.main()
