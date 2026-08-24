import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "docs" / "demo" / "PROJECT_DEMO_VIDEO_SCRIPT.md"
README_PATH = REPOSITORY_ROOT / "docs" / "demo" / "README.md"


class DemoMaterialsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = cls._read_if_present(SCRIPT_PATH)
        cls.readme = cls._read_if_present(README_PATH)

    @staticmethod
    def _read_if_present(path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def assertContainsAll(self, text: str, values: tuple[str, ...], subject: str):
        missing = [value for value in values if value not in text]
        self.assertFalse(missing, f"{subject} 缺少以下必需内容：{missing}")

    def test_required_material_files_exist(self):
        for path in (SCRIPT_PATH, README_PATH):
            self.assertTrue(
                path.is_file(),
                f"缺少演示材料文件：{path.relative_to(REPOSITORY_ROOT)}",
            )

    def test_script_has_required_sections_and_timed_table(self):
        headings = (
            "## 一、成片目标",
            "## 二、录制前准备",
            "## 三、五分钟逐秒演示脚本",
            "## 四、测试数据与预期结果",
            "## 五、异常预案",
            "## 六、录制验收清单",
        )
        self.assertContainsAll(self.script, headings, "成片脚本")
        self.assertIn(
            "| 时间 | 画面操作 | 逐字讲解词 | 验收画面/证据 | 剪辑或字幕提示 |",
            self.script,
            "逐秒脚本表格必须提供全部五列",
        )
        anchors = (
            "0:00–0:25",
            "0:25–1:05",
            "1:05–1:50",
            "1:50–2:40",
            "2:40–3:25",
            "3:25–3:55",
            "3:55–4:25",
            "4:25–4:45",
            "4:45–5:00",
        )
        self.assertContainsAll(self.script, anchors, "逐秒脚本时间锚点")

    def test_narration_is_recordable_and_within_target_length(self):
        narration_cells = []
        for line in self.script.splitlines():
            cells = [cell.strip() for cell in line.strip().split("|")]
            if len(cells) >= 7 and re.fullmatch(r"\d:\d{2}–\d:\d{2}", cells[1]):
                narration_cells.append(cells[3])
        self.assertGreaterEqual(len(narration_cells), 9, "每个时间锚点都应有可直接朗读的讲解词")
        narration = "".join(narration_cells)
        han_count = len(re.findall(r"[\u3400-\u9fff]", narration))
        self.assertGreaterEqual(han_count, 850, f"逐字讲解词仅 {han_count} 个汉字，低于 850")
        self.assertLessEqual(han_count, 1050, f"逐字讲解词共 {han_count} 个汉字，超过 1050")
        for index, cell in enumerate(narration_cells, start=1):
            self.assertGreaterEqual(
                len(re.findall(r"[\u3400-\u9fff]", cell)),
                35,
                f"第 {index} 段讲解词过短，疑似只有要点",
            )

    def test_script_uses_real_ui_copy_and_shortcuts(self):
        ui_copy = (
            "搜索本地资料",
            "搜索资料",
            "精确",
            "综合",
            "语义",
            "关键词",
            "文本语义",
            "图片语义",
            "添加资料文件夹",
            "资料已可搜索",
            "打开文件",
            "路径已复制",
            "高对比度",
            "减少动态效果",
            "保存设置",
            "无法连接本地检索服务，请检查服务地址和运行状态。",
            "Ctrl+1",
            "Ctrl+2",
            "Ctrl+3",
            "F5",
            "150%",
        )
        self.assertContainsAll(self.script, ui_copy, "成片脚本 UI 文案与快捷键")

    def test_test_data_queries_and_expectations_are_complete(self):
        fixtures = (
            ("01_课程检索笔记.txt", "星桥检索协议"),
            ("02_无障碍设计指南.pdf", "哪个文档介绍了不用鼠标操作界面"),
            ("03_离线系统方案.docx", "怎样在断网时保护本地文档隐私"),
            ("04_红色苹果.jpg", "a simple red apple on a white background"),
            ("05_蓝色方块.png", "a simple blue square on a white background"),
        )
        for filename, query in fixtures:
            self.assertIn(filename, self.script, f"测试数据缺少文件 {filename}")
            self.assertIn(query, self.script, f"测试数据缺少查询 {query}")
        self.assertContainsAll(
            self.script,
            ("目标文件出现在可见结果", "连续验证两次"),
            "搜索预期结果",
        )
        self.assertRegex(
            self.script,
            r"不(?:声称|保证|承诺).{0,8}图片.{0,8}固定第一名",
            "脚本必须明确否认图片固定第一名",
        )
        self.assertNotRegex(self.script, r"图片.{0,20}(必定|保证|总是).{0,10}第一名")

    def test_script_states_capability_boundaries_without_overclaiming(self):
        boundaries = (
            "只监听 localhost",
            "离线指运行时不上传",
            "依赖和模型需预先准备",
            "score 不是概率，也不是准确率",
        )
        self.assertContainsAll(self.script, boundaries, "能力边界说明")
        self.assertNotRegex(self.script, re.compile(r"WebP", re.IGNORECASE), "不得声称支持 WebP")
        self.assertNotRegex(
            self.script,
            r"score\s*(?:=|等于|就是|表示|代表)\s*(?:准确率|概率)",
            "不得把 score 表述为准确率或概率",
        )

    def test_recording_preparation_is_safe_reproducible_and_complete(self):
        prep = (
            "1920×1080",
            "30 fps",
            "隐藏私密内容",
            "关闭通知",
            "麦克风",
            "鼠标",
            "recording-01",
            "recording-02",
            "$env:TEMP",
            "$env:TMP",
            "$env:UV_CACHE_DIR",
            "F:\\",
            "uv run --project tools/demo --locked",
            "tools/start-mvp.ps1 -CheckOnly",
            "-DataDir",
            "http://127.0.0.1:8000/health/ready",
            "flutter run -d windows",
            "预演两遍",
            "异常离线片段",
            "http://127.0.0.1:8000",
        )
        self.assertContainsAll(self.script, prep, "录制前准备")
        self.assertRegex(self.script, r"不得删除|不要删除", "不得建议删除旧数据目录")

    def test_exception_plan_covers_all_required_scenarios_and_honesty_rules(self):
        scenarios = (
            "服务离线",
            "索引慢",
            "部分失败",
            "无结果",
            "语义/图片排序波动",
            "源文件移动或打开失败",
            "无障碍布局不理想",
            "成片超时",
        )
        self.assertContainsAll(self.script, scenarios, "异常预案")
        self.assertIn(
            "| 场景 | 触发 | 屏幕症状 | 立即动作 | 备用逐字话术 | 备用片段 |",
            self.script,
        )
        self.assertContainsAll(
            self.script,
            ("不伪装成功", "不在镜头内等待超过 8 秒", "真实完成状态", "跳切"),
            "异常处置原则",
        )

    def test_readme_links_commands_and_force_policy_are_actionable(self):
        required = (
            "[五分钟项目演示成片脚本](./PROJECT_DEMO_VIDEO_SCRIPT.md)",
            "[演示数据生成器](../../tools/demo/generate_demo_data.py)",
            "[演示材料契约测试](../../tools/demo/tests/test_demo_materials.py)",
            "uv run --project tools/demo --locked python tools/demo/generate_demo_data.py",
            "uv run --project tools/demo --locked python -m unittest tools.demo.tests.test_demo_materials -v",
            "uv run --project tools/demo --locked python -m unittest discover -s tools/demo/tests -v",
            "tools/start-mvp.ps1 -CheckOnly",
            "-DataDir",
            "http://127.0.0.1:8000/health/ready",
        )
        self.assertContainsAll(self.readme, required, "演示 README")
        first_generation = re.search(
            r"## 首次生成(?P<body>.*?)(?=\n## |\Z)", self.readme, re.DOTALL
        )
        self.assertIsNotNone(first_generation, "README 必须有“首次生成”章节")
        self.assertNotIn("--force", first_generation.group("body"), "首次生成命令不得带 --force")
        self.assertRegex(
            self.readme,
            r"只有.{0,30}生成器.{0,30}(拥有|生成).{0,30}目录.{0,30}--force",
            "README 必须限定仅生成器拥有的目录才可用 --force 重建",
        )
        self.assertNotRegex(self.readme, r"(?im)^\s*(?:pip install|uv add)\b", "不得要求安装未锁定依赖")


if __name__ == "__main__":
    unittest.main()
