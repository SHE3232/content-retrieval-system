import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "docs" / "demo" / "PROJECT_DEMO_VIDEO_SCRIPT.md"
README_PATH = REPOSITORY_ROOT / "docs" / "demo" / "README.md"
EXPECTED_TIMELINE = (
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
RESERVE_SECONDS = {
    "0:00–0:25": 1,
    "0:25–1:05": 4,
    "1:05–1:50": 4,
    "1:50–2:40": 4,
    "2:40–3:25": 4,
    "3:25–3:55": 7,
    "3:55–4:25": 3,
    "4:25–4:45": 5,
    "4:45–5:00": 3,
}
MAX_HAN_CHARACTERS_PER_MINUTE = 260


def has_positive_webp_claim(text: str) -> bool:
    """Return whether a sentence or clause positively claims WebP capability."""
    negative_before = re.compile(
        r"(?:尚未|不再|不|未)(?:支持|可索引|可以索引|能处理|可以处理)\s*WebP",
        re.IGNORECASE,
    )
    negative_after = re.compile(
        r"WebP(?:\s*格式)?.{0,4}(?:不受支持|尚未支持|未支持|不能处理|不可索引|不可处理)",
        re.IGNORECASE,
    )
    positive = re.compile(
        r"(?:支持|可索引|可以索引|能处理|可以处理)\s*WebP"
        r"|WebP(?:\s*格式)?.{0,4}(?:已经)?(?:支持|可索引|可处理)",
        re.IGNORECASE,
    )
    for clause in re.split(r"[。！？；;\n]", text):
        if re.search(r"WebP", clause, re.IGNORECASE) is None:
            continue
        without_negative_boundaries = negative_before.sub("", clause)
        without_negative_boundaries = negative_after.sub("", without_negative_boundaries)
        if positive.search(without_negative_boundaries) is not None:
            return True
    return False


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

    def assertOrdered(self, text: str, values: tuple[str, ...], subject: str):
        cursor = 0
        for value in values:
            position = text.find(value, cursor)
            self.assertNotEqual(position, -1, f"{subject} 缺少或顺序错误：{value}")
            cursor = position + len(value)

    def _section(self, text: str, heading: str) -> str:
        match = re.search(
            rf"^{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^## |\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match, f"缺少章节：{heading}")
        return match.group("body")

    def _timed_rows(self):
        rows = []
        for line in self.script.splitlines():
            cells = [cell.strip() for cell in line.strip().split("|")]
            if len(cells) < 7:
                continue
            match = re.fullmatch(r"(\d):(\d{2})–(\d):(\d{2})", cells[1])
            if match is None:
                continue
            start = int(match.group(1)) * 60 + int(match.group(2))
            end = int(match.group(3)) * 60 + int(match.group(4))
            rows.append((cells[1], start, end, cells[3]))
        return rows

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
        self.assertContainsAll(self.script, EXPECTED_TIMELINE, "逐秒脚本时间锚点")

    def test_timeline_has_exactly_nine_contiguous_nonoverlapping_segments(self):
        rows = self._timed_rows()
        labels = tuple(row[0] for row in rows)
        self.assertEqual(
            labels,
            EXPECTED_TIMELINE,
            f"时间轴必须恰好按规定顺序包含九段；实际为 {labels}",
        )
        self.assertEqual(len(set(labels)), 9, "时间轴不得含重复时段")
        self.assertEqual(rows[0][1], 0, "时间轴必须从 0:00 开始")
        self.assertEqual(rows[-1][2], 300, "时间轴必须在 5:00 结束")
        for current, following in zip(rows, rows[1:]):
            self.assertGreater(current[2], current[1], f"时段 {current[0]} 的时长必须为正")
            self.assertEqual(
                current[2],
                following[1],
                f"时段 {current[0]} 与 {following[0]} 之间存在空隙、重复或重叠",
            )

    def test_narration_is_recordable_and_within_target_length(self):
        narration_cells = [row[3] for row in self._timed_rows()]
        self.assertEqual(len(narration_cells), 9, "九个时间段都应有可直接朗读的讲解词")
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

    def test_each_segment_respects_speaking_budget_after_operation_pauses(self):
        counts = {}
        for label, start, end, narration in self._timed_rows():
            count = len(re.findall(r"[\u3400-\u9fff]", narration))
            counts[label] = count
            effective_seconds = end - start - RESERVE_SECONDS[label]
            limit = int(effective_seconds * MAX_HAN_CHARACTERS_PER_MINUTE / 60)
            with self.subTest(segment=label):
                self.assertLessEqual(
                    count,
                    limit,
                    f"{label} 有 {count} 个汉字，但扣除 {RESERVE_SECONDS[label]} 秒操作停顿后"
                    f"最多容纳 {limit} 个（按 {MAX_HAN_CHARACTERS_PER_MINUTE} 汉字/分钟）",
                )
        self.assertGreaterEqual(counts["4:25–4:45"], 60, "离线段旁白应约为 60–65 个汉字")
        self.assertLessEqual(counts["4:25–4:45"], 65, "离线段旁白应约为 60–65 个汉字")
        self.assertGreaterEqual(counts["4:45–5:00"], 50, "总结段旁白应约为 50–55 个汉字")
        self.assertLessEqual(counts["4:45–5:00"], 55, "总结段旁白应约为 50–55 个汉字")
        self.assertGreaterEqual(counts["3:25–3:55"], 96, "文档操作段旁白应约为 96–100 个汉字")
        self.assertLessEqual(counts["3:25–3:55"], 100, "文档操作段旁白应约为 96–100 个汉字")

    def test_closing_segment_summarizes_all_four_project_values(self):
        closing_line = next(
            line for line in self.script.splitlines() if line.startswith("| 4:45–5:00 |")
        )
        cells = [cell.strip() for cell in closing_line.split("|")]
        closing_copy = f"{cells[3]}\n{cells[5]}"
        concepts = {
            "本地离线": "本地" in closing_copy and "离线" in closing_copy,
            "五类文件": bool(
                re.search(r"(?:五类|五种).{0,4}(?:文件|格式)|(?:文件|格式).{0,4}(?:五类|五种)", closing_copy)
            ),
            "多模态检索": "多模态" in closing_copy,
            "无障碍支持": "无障碍" in closing_copy,
        }
        for concept, present in concepts.items():
            with self.subTest(concept=concept):
                self.assertTrue(present, f"4:45–5:00 的旁白或字幕缺少“{concept}”价值总结")

    def test_script_uses_real_ui_copy_and_shortcuts(self):
        ui_copy = (
            "搜索本地资料",
            "搜索资料",
            "精确",
            "综合",
            "语义",
            "关键词",
            "文本语义",
            "图像语义",
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
        self.assertNotIn("图片语义", self.script, "UI/检索通道名称必须使用实际文案“图像语义”")

    def test_rehearsal_and_recording_use_separate_sequential_data_directories(self):
        script_prep = self._section(self.script, "## 二、录制前准备")
        readme_flow_match = re.search(
            r"^## 启动预演实例\s*$\n(?P<body>.*)\Z",
            self.readme,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(readme_flow_match, "README 必须从“启动预演实例”开始说明双实例顺序")
        for subject, flow in (
            ("脚本录制前准备", script_prep),
            ("README 实例流程", readme_flow_match.group("body")),
        ):
            with self.subTest(subject=subject):
                self.assertContainsAll(
                    flow,
                    (
                        "rehearsal-01",
                        "recording-01",
                        "rehearsal-02",
                        "recording-02",
                        "Ctrl+C",
                        "全新",
                    ),
                    subject,
                )
                self.assertRegex(
                    flow,
                    r"start-mvp\.ps1 -CheckOnly -DataDir ['\"]?F:\\contentretrieval-demo\\rehearsal-01",
                    f"{subject} 缺少 rehearsal-01 的 CheckOnly 命令",
                )
                self.assertRegex(
                    flow,
                    r"start-mvp\.ps1 -DataDir ['\"]?F:\\contentretrieval-demo\\rehearsal-01",
                    f"{subject} 缺少 rehearsal-01 的启动命令",
                )
                self.assertRegex(
                    flow,
                    r"start-mvp\.ps1 -CheckOnly -DataDir ['\"]?F:\\contentretrieval-demo\\recording-01",
                    f"{subject} 缺少 recording-01 的 CheckOnly 命令",
                )
                self.assertRegex(
                    flow,
                    r"start-mvp\.ps1 -DataDir ['\"]?F:\\contentretrieval-demo\\recording-01",
                    f"{subject} 缺少 recording-01 的启动命令",
                )
                self.assertOrdered(
                    flow,
                    ("rehearsal-01", "Ctrl+C", "recording-01"),
                    f"{subject} 必须先停止预演实例，再启动正式实例",
                )
                self.assertRegex(
                    flow,
                    r"(?:停止|退出)预演实例.{0,50}(?:再|然后).{0,20}(?:启动|预检).{0,20}正式",
                    f"{subject} 必须明确停止预演实例后再启动正式实例",
                )
                self.assertRegex(
                    flow,
                    r"(?:不要|不得).{0,20}(?:同时|并行).{0,20}(?:实例|8000|端口)",
                    f"{subject} 必须禁止两个实例同时占用 8000 端口",
                )

    def test_frontend_is_restarted_and_empty_state_checked_after_recording_backend_starts(self):
        recording_start = (
            "& .\\tools\\start-mvp.ps1 -DataDir "
            "'F:\\contentretrieval-demo\\recording-01'"
        )
        for subject, flow in (
            ("脚本准备流程", self._section(self.script, "## 二、录制前准备")),
            (
                "README 实例流程",
                re.search(
                    r"^## 启动预演实例\s*$\n(?P<body>.*)\Z",
                    self.readme,
                    re.MULTILINE | re.DOTALL,
                ).group("body"),
            ),
        ):
            prefix, marker, after_recording_start = flow.partition(recording_start)
            with self.subTest(subject=subject, requirement="recording command"):
                self.assertTrue(marker, f"{subject} 缺少 recording-01 的正式启动命令")
            if not marker:
                continue
            with self.subTest(subject=subject, requirement="stop order"):
                self.assertOrdered(
                    prefix,
                    ("停止 Flutter", "停止预演实例"),
                    f"{subject} 必须先停止 Flutter，再停止 rehearsal MVP",
                )
            with self.subTest(subject=subject, requirement="restart Flutter"):
                self.assertContainsAll(
                    after_recording_start,
                    ("重新启动 Flutter", "flutter run -d windows"),
                    f"{subject} 必须为 recording-01 重建 Flutter controller",
                )
            with self.subTest(subject=subject, requirement="empty-state order"):
                self.assertOrdered(
                    after_recording_start,
                    (
                        "health/ready",
                        "flutter run -d windows",
                        "Ctrl+2",
                        "F5",
                        "索引库为空",
                        "Ctrl+1",
                        "搜索本地资料",
                    ),
                    f"{subject} 必须在新前端验证正式数据目录空态",
                )

    def test_offline_clip_uses_library_refresh_instead_of_disabled_search(self):
        script_prep = self._section(self.script, "## 二、录制前准备")
        offline_line = next(
            line for line in self.script.splitlines() if line.startswith("| 4:25–4:45 |")
        )
        offline_plan = next(
            line for line in self.script.splitlines() if line.startswith("| 服务离线 |")
        )
        for subject, instructions in (
            ("脚本准备步骤", script_prep),
            ("4:25–4:45 时间行", offline_line),
            ("服务离线预案", offline_plan),
        ):
            with self.subTest(subject=subject):
                self.assertContainsAll(
                    instructions,
                    ("Ctrl+2", "索引库", "F5"),
                    f"{subject} 的真实可点击离线路径",
                )
                self.assertNotRegex(
                    instructions,
                    r"(?:回到|返回)搜索.{0,12}触发(?:一次)?请求|搜索后出现完整错误",
                    f"{subject} 不得依赖离线时被禁用的搜索按钮",
                )
        readme_offline = self._section(self.readme, "## 预录离线异常")
        self.assertContainsAll(
            readme_offline,
            ("Ctrl+2", "索引库", "F5"),
            "README 离线预录的真实可点击路径",
        )
        self.assertNotRegex(
            readme_offline,
            r"(?:回到|返回)搜索.{0,12}触发(?:一次)?请求|搜索后出现完整错误",
            "README 离线预录不得依赖离线时被禁用的搜索按钮",
        )
        self.assertOrdered(
            script_prep,
            (
                "http://127.0.0.1:65534",
                "Ctrl+2",
                "F5",
                "无法连接本地检索服务，请检查服务地址和运行状态。",
                "http://127.0.0.1:8000",
                "Ctrl+2",
                "F5",
                "Ctrl+1",
            ),
            "脚本离线异常的触发与恢复顺序",
        )

    def test_document_actions_follow_a_verified_hybrid_pdf_result(self):
        action_line = next(
            line for line in self.script.splitlines() if line.startswith("| 3:25–3:55 |")
        )
        cells = [cell.strip() for cell in action_line.split("|")]
        operation = cells[2]
        self.assertOrdered(
            operation,
            (
                "清空",
                "查询为空",
                "重置",
                "取消“文本文件”",
                "取消“图片”",
                "只保留“文档”",
                "输入",
                "哪个文档介绍了不用鼠标操作界面",
                "搜索资料",
                "02_无障碍设计指南.pdf",
                "复制路径",
                "路径已复制",
                "打开文件",
            ),
            "3:25–3:55 必须先清空旧查询，再配置筛选并执行 PDF 文件操作",
        )
        self.assertContainsAll(
            action_line,
            (
                "重置",
                "综合",
                "文档",
                "哪个文档介绍了不用鼠标操作界面",
                "02_无障碍设计指南.pdf",
                "路径已复制",
                "打开文件",
            ),
            "3:25–3:55 文档检索与文件操作链",
        )
        self.assertRegex(
            action_line,
            r"取消[“\"]?文本文件[”\"]?.{0,20}取消[“\"]?图片[”\"]?.{0,20}只保留[“\"]?文档",
            "重置后必须取消“文本文件”和“图片”，只保留已选中的“文档”",
        )

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
        self.assertFalse(
            has_positive_webp_claim(self.script),
            "不得正向声称支持或可处理 WebP",
        )
        self.assertNotRegex(
            self.script,
            r"score\s*(?:=|等于|就是|表示|代表)\s*(?:准确率|概率)",
            "不得把 score 表述为准确率或概率",
        )

    def test_webp_boundary_allows_negative_but_rejects_positive_claims(self):
        for statement in (
            "不支持 WebP",
            "未支持 WebP",
            "不再支持 WebP",
            "WebP 不受支持",
            "WebP 尚未支持",
            "WebP 不能处理",
        ):
            with self.subTest(statement=statement):
                self.assertFalse(
                    has_positive_webp_claim(statement),
                    f"准确的否定边界不应被误判：{statement}",
                )
        for statement in (
            "支持 WebP",
            "WebP 格式已经支持",
            "可以索引 WebP",
            "WebP 可索引",
            "WebP 可处理",
        ):
            with self.subTest(statement=statement):
                self.assertTrue(
                    has_positive_webp_claim(statement),
                    f"正向能力声明必须被识别：{statement}",
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
            "rehearsal-01",
            "rehearsal-02",
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
            "语义/图像排序波动",
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
