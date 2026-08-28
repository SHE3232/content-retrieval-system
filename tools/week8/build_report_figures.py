#!/usr/bin/env python3
"""Build monochrome, evidence-bound figures for the Week 8 final report."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1800
HEIGHT = 1000
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
FIGURE_NAMES = (
    "01_总体架构.png",
    "02_文件摄取时序.png",
    "03_混合检索链路.png",
    "04_八周成果时间线.png",
    "05_三类发行关系.png",
    "06_测试结果汇总.png",
    "07_性能对比.png",
    "08_最终交付结构.png",
)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        (
            Path("C:/Windows/Fonts/msyhbd.ttc")
            if bold
            else Path("C:/Windows/Fonts/msyh.ttc")
        ),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
        if bold
        else Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if bold
        else Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


TITLE_FONT = _font(54, bold=True)
SUBTITLE_FONT = _font(26)
LABEL_FONT = _font(30, bold=True)
BODY_FONT = _font(25)
SMALL_FONT = _font(21)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for character in paragraph:
            candidate = current + character
            if current and _text_width(draw, candidate, font) > max_width:
                lines.append(current)
                current = character
            else:
                current = candidate
        lines.append(current)
    return lines


def _centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    *,
    font: ImageFont.ImageFont = BODY_FONT,
    spacing: int = 10,
) -> None:
    left, top, right, bottom = box
    lines = _wrap(draw, text, font, right - left - 36)
    heights = [draw.textbbox((0, 0), line or " ", font=font)[3] for line in lines]
    total = sum(heights) + spacing * max(0, len(lines) - 1)
    y = top + max(0, (bottom - top - total) // 2)
    for line, height in zip(lines, heights):
        width = _text_width(draw, line, font)
        draw.text((left + (right - left - width) / 2, y), line, font=font, fill=BLACK)
        y += height + spacing


def _box(
    draw: ImageDraw.ImageDraw,
    coordinates: tuple[int, int, int, int],
    text: str,
    *,
    font: ImageFont.ImageFont = BODY_FONT,
    width: int = 3,
) -> None:
    draw.rounded_rectangle(coordinates, radius=18, fill=WHITE, outline=BLACK, width=width)
    _centered_text(draw, coordinates, text, font=font)


def _arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    width: int = 4,
) -> None:
    draw.line((start, end), fill=BLACK, width=width)
    x, y = end
    if abs(end[0] - start[0]) >= abs(end[1] - start[1]):
        direction = 1 if end[0] > start[0] else -1
        points = [(x, y), (x - direction * 18, y - 11), (x - direction * 18, y + 11)]
    else:
        direction = 1 if end[1] > start[1] else -1
        points = [(x, y), (x - 11, y - direction * 18), (x + 11, y - direction * 18)]
    draw.polygon(points, fill=BLACK)


def _canvas(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((80, 46), title, font=TITLE_FONT, fill=BLACK)
    draw.text((82, 120), subtitle, font=SUBTITLE_FONT, fill=BLACK)
    draw.line((80, 170, WIDTH - 80, 170), fill=BLACK, width=3)
    return image, draw


def _architecture(_: dict[str, object]) -> Image.Image:
    image, draw = _canvas("总体架构", "离线优先的客户端、API、检索与本地模型分层")
    rows = [
        (220, "Flutter 客户端：搜索｜索引库｜设置｜无障碍"),
        (365, "FastAPI：健康检查｜异步摄取｜搜索｜统计"),
        (510, "领域服务：解析｜分块｜嵌入｜BM25｜加权 RRF"),
        (655, "本地基础设施：ChromaDB｜Tika｜模型清单｜哈希校验"),
        (800, "本机文件与持久化数据；服务仅绑定 127.0.0.1"),
    ]
    for index, (top, label) in enumerate(rows):
        _box(draw, (190, top, 1610, top + 92), label, font=LABEL_FONT if index == 0 else BODY_FONT)
        if index:
            _arrow(draw, (900, top - 35), (900, top - 5))
    return image


def _ingestion(_: dict[str, object]) -> Image.Image:
    image, draw = _canvas("文件摄取时序", "统一五格式输入、内容身份与持久化的一致性链路")
    labels = [
        "选择目录\nTXT / PDF / DOCX / JPEG / PNG",
        "解析器注册表\n文本直读 / Tika / Pillow",
        "统一内容模型\n来源、MIME、正文或图像",
        "分块与嵌入\n文本默认；图像研究配置",
        "Chroma 提交\n幂等更新与陈旧记录清理",
    ]
    lefts = [60, 410, 760, 1110, 1460]
    for index, (left, label) in enumerate(zip(lefts, labels)):
        right = left + 280
        _box(draw, (left, 320, right, 610), label, font=BODY_FONT)
        if index < len(labels) - 1:
            _arrow(draw, (right + 10, 465), (lefts[index + 1] - 10, 465))
    _box(
        draw,
        (360, 740, 1440, 875),
        "增量判定：规范化绝对路径 + 文件元数据 + 内容摘要；失败项独立记录，不破坏已提交索引",
        font=BODY_FONT,
    )
    return image


def _retrieval(_: dict[str, object]) -> Image.Image:
    image, draw = _canvas("混合检索链路", "不同检索空间分别排序，再以加权倒数排名融合")
    _box(draw, (90, 260, 420, 430), "查询与过滤条件", font=LABEL_FONT)
    channels = [
        (570, 215, "关键词 BM25\n字段加权与词项匹配"),
        (570, 430, "文本语义\n384 维余弦空间"),
        (570, 645, "图文语义\n512 维研究配置"),
    ]
    for left, top, label in channels:
        _box(draw, (left, top, left + 390, top + 150), label)
        _arrow(draw, (430, 345), (left - 10, top + 75))
    _box(draw, (1110, 355, 1440, 560), "加权 RRF\n按文件聚合与去重", font=LABEL_FONT)
    for _, top, _ in channels:
        _arrow(draw, (970, top + 75), (1100, 455))
    _box(draw, (1510, 355, 1730, 560), "排序结果\n可解释元数据", font=BODY_FONT)
    _arrow(draw, (1450, 455), (1500, 455))
    return image


def _timeline(_: dict[str, object]) -> Image.Image:
    image, draw = _canvas("八周成果时间线", "从需求、解析与模型到客户端、发布和结项")
    items = [
        ("W1", "需求与架构"),
        ("W2", "五格式解析"),
        ("W3", "多模态嵌入"),
        ("W4", "索引与检索"),
        ("W5", "Flutter 与无障碍"),
        ("W6", "集成与发布门禁"),
        ("W7", "文档、演示与复核"),
        ("W8", "清理、跨平台与结项"),
    ]
    y = 510
    draw.line((120, y, 1680, y), fill=BLACK, width=5)
    for index, (week, label) in enumerate(items):
        x = 150 + index * 215
        draw.ellipse((x - 13, y - 13, x + 13, y + 13), fill=WHITE, outline=BLACK, width=4)
        top = 250 if index % 2 == 0 else 610
        _box(draw, (x - 90, top, x + 90, top + 135), f"{week}\n{label}", font=SMALL_FONT)
        start_y = top + 135 if top < y else top
        end_y = y - 18 if top < y else y + 18
        draw.line((x, start_y, x, end_y), fill=BLACK, width=3)
    return image


def _release_model(_: dict[str, object]) -> Image.Image:
    image, draw = _canvas("三类发行关系", "源码、默认公开二进制与课程研究材料保持许可证隔离")
    _box(draw, (100, 285, 550, 700), "公开源码\n\nApache-2.0 项目代码\n锁文件、测试、文档\n不含模型权重与本机缓存", font=BODY_FONT)
    _box(draw, (675, 285, 1125, 700), "默认公开发行包\n\n文本模型 + CPU 运行时\n关键词与文本语义\n不含 MobileCLIP 权重", font=BODY_FONT)
    _box(draw, (1250, 285, 1700, 700), "课程研究包\n\n在独立门禁中加入 MobileCLIP\n随附研究许可证、模型卡\n来源修订与 SHA-256", font=BODY_FONT)
    _arrow(draw, (560, 492), (665, 492))
    _arrow(draw, (1135, 492), (1240, 492))
    draw.text((565, 750), "公开边界", font=LABEL_FONT, fill=BLACK)
    draw.text((1170, 750), "显式研究边界", font=LABEL_FONT, fill=BLACK)
    return image


def _test_summary(evidence: dict[str, object]) -> Image.Image:
    image, draw = _canvas("测试结果汇总", "数字直接读取最终报告证据；状态不由文件名推断")
    tests = evidence.get("tests", {})
    if not isinstance(tests, dict):
        tests = {}
    rows = []
    for name, result in tests.items():
        if isinstance(result, dict):
            rows.append((str(name), int(result.get("passed", 0)), str(result.get("status", "BLOCKED"))))
    rows = rows[:8]
    maximum = max((count for _, count, _ in rows), default=1)
    for index, (name, count, status) in enumerate(rows):
        y = 235 + index * 82
        draw.text((100, y), name, font=SMALL_FONT, fill=BLACK)
        bar_left = 500
        bar_right = bar_left + int(920 * count / maximum)
        draw.rectangle((bar_left, y + 3, max(bar_left + 4, bar_right), y + 42), fill=WHITE, outline=BLACK, width=3)
        draw.text((1450, y), f"{count}  {status}", font=SMALL_FONT, fill=BLACK)
    total = sum(count for _, count, _ in rows)
    draw.text((100, 900), f"汇总通过数：{total}（各套件存在范围重叠时不作为唯一测试用例总量）", font=SMALL_FONT, fill=BLACK)
    return image


def _performance(evidence: dict[str, object]) -> Image.Image:
    image, draw = _canvas("性能基线", "展示已核验历史基线，不把历史测量冒充最终硬件重测")
    metrics = evidence.get("benchmarks", {})
    if not isinstance(metrics, dict):
        metrics = {}
    values = [
        ("文本单条 P50", float(metrics.get("text_batch1_p50_ms", 0)), "ms", 100),
        ("检索 P95", float(metrics.get("search_p95_ms", 0)), "ms", 1000),
        ("验收上限", float(metrics.get("target_p95_ms", 0)), "ms", 2000),
        ("批量吞吐", float(metrics.get("text_batch16_throughput", 0)), "items/s", 400),
    ]
    for index, (label, value, unit, scale) in enumerate(values):
        y = 250 + index * 155
        draw.text((110, y), label, font=LABEL_FONT, fill=BLACK)
        bar_left = 520
        bar_width = min(1000, int(1000 * value / max(scale, 1)))
        draw.rectangle((bar_left, y, bar_left + max(5, bar_width), y + 60), fill=WHITE, outline=BLACK, width=4)
        draw.text((1550, y + 8), f"{value:.2f} {unit}", font=BODY_FONT, fill=BLACK)
    return image


def _delivery(_: dict[str, object]) -> Image.Image:
    image, draw = _canvas("最终交付结构", "同一 SOURCE_VERSION 与统一清单连接全部本地成果")
    _box(draw, (640, 210, 1160, 335), "第八周最终交付\nDELIVERY_MANIFEST + SHA256SUMS", font=LABEL_FONT)
    children = [
        (80, 500, "01 平台发布\nWindows / Linux / macOS 状态"),
        (410, 500, "02 公开源码\n白名单工程目录"),
        (740, 500, "03 课程演示研究包\n独立许可证边界"),
        (1070, 500, "04 演示视频\n严格五分钟门禁"),
        (1400, 500, "05 作品集\n06 结项文档"),
    ]
    for left, top, label in children:
        _box(draw, (left, top, left + 290, top + 210), label, font=SMALL_FONT)
        _arrow(draw, (900, 345), (left + 145, top - 10), width=3)
    _box(draw, (430, 800, 1370, 900), "每个文件记录相对路径、字节数、SHA-256、发行类别与来源；BLOCKED 状态保留原因", font=BODY_FONT)
    return image


FIGURE_BUILDERS: tuple[Callable[[dict[str, object]], Image.Image], ...] = (
    _architecture,
    _ingestion,
    _retrieval,
    _timeline,
    _release_model,
    _test_summary,
    _performance,
    _delivery,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_figures(evidence_path: Path, output_dir: Path) -> list[Path]:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    commit = evidence.get("source_commit")
    if not isinstance(commit, str) or len(commit) != 40:
        raise ValueError("report evidence requires a full source_commit")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    records: list[dict[str, object]] = []
    for name, builder in zip(FIGURE_NAMES, FIGURE_BUILDERS):
        path = output_dir / name
        image = builder(evidence)
        image.save(path, format="PNG", optimize=True)
        outputs.append(path)
        records.append(
            {
                "path": name,
                "width": image.width,
                "height": image.height,
                "sha256": _sha256(path),
            }
        )
    (output_dir / "figures.json").write_text(
        json.dumps(
            {"schema_version": 1, "source_commit": commit, "figures": records},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    outputs = build_figures(args.evidence, args.output_dir)
    print(json.dumps({"figure_count": len(outputs), "output_dir": str(args.output_dir.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
