import json
import tempfile
import unittest
from pathlib import Path

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
            self.assertEqual(len(manifest["files"]), 5)
            self.assertEqual(result, manifest)
            self.assertEqual({entry["name"] for entry in manifest["files"]}, set(EXPECTED_FILES))
            for entry in manifest["files"]:
                self.assertIn("query", entry)
                self.assertIn("mode", entry)

    def test_text_and_office_documents_contain_demo_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_demo_data(out)
            self.assertIn("星桥检索协议", (out / "01_课程检索笔记.txt").read_text(encoding="utf-8"))
            doc = Document(out / "03_离线系统方案.docx")
            text = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("不会发送到云端", text)

    def test_pdf_and_images_are_real_and_contentful(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_demo_data(out)
            pdf = PdfDocument(str(out / "02_无障碍设计指南.pdf"))
            extracted = "".join(page.get_textpage().get_text_range() for page in pdf)
            pdf.close()
            self.assertIn("DEMO-PDF-ACCESSIBILITY", extracted)
            with Image.open(out / "04_红色苹果.jpg") as apple:
                r, g, b = apple.convert("RGB").getpixel((256, 256))
                self.assertGreater(r, 180); self.assertLess(g, 100); self.assertLess(b, 100)
            with Image.open(out / "05_蓝色方块.png") as square:
                r, g, b = square.convert("RGB").getpixel((256, 256))
                self.assertLess(r, 100); self.assertLess(g, 180); self.assertGreater(b, 180)

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


if __name__ == "__main__":
    unittest.main()
