#!/usr/bin/env python3
"""Build an evidence-linked Week 8 project portfolio."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

FIGURE_COPIES = {
    "01_总体架构.png": "architecture.png",
    "05_三类发行关系.png": "release-model.png",
    "06_测试结果汇总.png": "test-summary.png",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"portfolio input must be a JSON object: {path}")
    return value


def _test_lines(evidence: dict[str, Any]) -> list[str]:
    tests = evidence.get("tests", {})
    lines = ["| 测试套件 | 状态 | 通过 | 跳过 |", "|---|---:|---:|---:|"]
    if isinstance(tests, dict):
        for name, result in tests.items():
            if isinstance(result, dict):
                lines.append(
                    f"| {name} | {result.get('status', 'BLOCKED')} | "
                    f"{int(result.get('passed', 0))} | {int(result.get('skipped', 0))} |"
                )
    return lines


def _platform_lines(evidence: dict[str, Any]) -> list[str]:
    platforms = evidence.get("platforms", {})
    lines = ["| 平台 | 状态 | 说明 |", "|---|---:|---|"]
    for platform in ("windows", "linux", "macos"):
        result = platforms.get(platform, {}) if isinstance(platforms, dict) else {}
        if not isinstance(result, dict):
            result = {}
        lines.append(
            f"| {platform} | {result.get('status', 'BLOCKED')} | "
            f"{result.get('reason', '')} |"
        )
    return lines


def _artifact_lines(manifest: dict[str, Any]) -> list[str]:
    artifacts = manifest.get("artifacts", [])
    lines = ["| 发行类别 | 产物路径 | 字节数 | SHA-256 |", "|---|---|---:|---|"]
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict):
                lines.append(
                    f"| {artifact.get('distribution_class', '')} | "
                    f"`{artifact.get('path', '')}` | {int(artifact.get('bytes', 0))} | "
                    f"`{artifact.get('sha256', '')}` |"
                )
    return lines


def build_portfolio(
    *,
    evidence_path: Path,
    delivery_manifest_path: Path,
    figure_dir: Path,
    output_dir: Path,
) -> Path:
    evidence = _load(evidence_path)
    manifest = _load(delivery_manifest_path)
    commit = evidence.get("source_commit")
    if manifest.get("source_commit") != commit:
        raise ValueError("portfolio evidence and delivery manifest commits differ")

    assets = output_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for source_name, target_name in FIGURE_COPIES.items():
        source = figure_dir / source_name
        if not source.is_file():
            raise ValueError(f"portfolio figure is missing: {source}")
        shutil.copy2(source, assets / target_name)

    external = evidence.get("external_gates", {})
    if not isinstance(external, dict):
        external = {}
    benchmarks = evidence.get("benchmarks", {})
    if not isinstance(benchmarks, dict):
        benchmarks = {}
    five_formats = evidence.get("five_formats", {})
    if not isinstance(five_formats, dict):
        five_formats = {}

    lines = [
        "# 离线可访问多模态本地内容检索系统｜项目作品集",
        "",
        f"源码提交：`{commit}`",
        "",
        "## 项目背景与个人职责",
        "",
        (
            "项目解决本机 TXT、PDF、DOCX、JPEG、PNG 内容难以按语义统一检索的问题。"
            "我负责需求拆解、总体架构、后端与 Flutter 实现、模型和索引工程、无障碍、测试、"
            "许可证审查、跨平台发布以及最终文档与证据收口。系统默认离线运行，用户文件和查询不发送到远程服务。"
        ),
        "",
        "![总体架构图](assets/architecture.png)",
        "",
        "## 架构与摄取/检索流程",
        "",
        (
            "Flutter 客户端通过回环地址访问 FastAPI；领域层把解析、分块、嵌入、索引和检索分开；"
            "ChromaDB、Tika、模型与清单全部位于本机。文件先进入解析器注册表和统一内容模型，"
            "文本按稳定规则分块，关键词 BM25 与文本语义分别排序，研究配置另启用图文语义，最终通过加权 RRF 文件级融合。"
        ),
        "",
        "## 关键用户界面",
        "",
        (
            "搜索页覆盖空、加载、就绪、离线和错误状态；索引库支持查看、重建与删除；设置页持久化后端地址、"
            "高对比度、文本缩放和减少动态效果。结果卡提供可解释命中信息、复制路径和打开文件操作。"
        ),
        "",
        "## 技术挑战与解决方案",
        "",
        "1. 使用 `space_id`、维度和模型标识隔离文本与图文向量，避免错误相似度比较。",
        "2. 采用稳定文件/分块身份和完成后替换策略，保证增量索引失败时不破坏旧数据。",
        "3. 将 MobileCLIP 从公开基础锁中移出，用显式研究安装和不可用引擎表达能力边界。",
        "4. 通过锁文件、来源修订、模型清单、Temurin/Tika 摘要和归档验证建立供应链证据。",
        "",
        "## 测试与性能结果",
        "",
        *_test_lines(evidence),
        "",
        "![测试汇总图](assets/test-summary.png)",
        "",
        (
            f"五格式端到端状态为 {five_formats.get('status', 'BLOCKED')}，解析 "
            f"{int(five_formats.get('parsed_files', 0))} 个文件并索引 {int(five_formats.get('indexed_files', 0))} 个文件。"
            f"历史持久化检索 P95 为 {float(benchmarks.get('search_p95_ms', 0)):.2f} ms，"
            f"验收目标上限为 {float(benchmarks.get('target_p95_ms', 0)):.2f} ms；这些数字按原始证据标为历史基线。"
        ),
        "",
        "## 无障碍、隐私与合规",
        "",
        (
            "客户端支持语义标签、键盘操作、可见焦点、高对比度、200% 文本缩放和减少动态效果。"
            "API 只绑定 `127.0.0.1`，运行时不自动下载模型。项目自有部分采用 Apache-2.0，第三方材料保留各自许可证；"
            "默认公开发行不含 MobileCLIP 权重，课程研究包不作为通用开源或商业二进制发布。"
        ),
        "",
        "![发行关系图](assets/release-model.png)",
        "",
        "## 平台与外部门禁",
        "",
        *_platform_lines(evidence),
        "",
        f"- GitHub：{external.get('github', 'BLOCKED')} ",
        f"- 项目演示视频：{external.get('video', 'BLOCKED')} ",
        "",
        "外部门禁没有直接证据时保持 BLOCKED；本地脚本、模拟器或占位文件不能替代真实主机、匿名访问和人工录屏。",
        "",
        "## 下载与交付清单",
        "",
        *_artifact_lines(manifest),
        "",
        "公开 Release 只允许公开源码和默认公开资产；`research-only` 条目保存在课程演示研究包目录，不进入公共 Release。",
        "",
        "## 文档入口",
        "",
        (
            "工程内提供 `README.md`、`docs/ARCHITECTURE.md`、`docs/API_REFERENCE.md`、"
            "`docs/MAINTENANCE_GUIDE.md`、`docs/OPEN_SOURCE_COMPLIANCE.md` 和第八周结项报告。"
        ),
        "",
        "## 已知局限与反思",
        "",
        (
            "当前服务面向本机单用户，没有认证和多租户隔离；任务状态不跨重启；后端尚不支持 WebP；"
            "公开包不提供图片语义；检索质量基于有限冻结子集。八周实践表明，离线产品的核心不仅是模型调用，"
            "还包括稳定数据身份、失败恢复、可访问交互、许可证边界和可复现发布。诚实保留 BLOCKED 比无证据的全绿状态更有工程价值。"
        ),
        "",
    ]
    readme = output_dir / "README.md"
    readme.write_text("\n".join(lines), encoding="utf-8")
    return readme


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--delivery-manifest", type=Path, required=True)
    parser.add_argument("--figures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    readme = build_portfolio(
        evidence_path=args.evidence,
        delivery_manifest_path=args.delivery_manifest,
        figure_dir=args.figures,
        output_dir=args.output,
    )
    print(json.dumps({"output": str(readme.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
