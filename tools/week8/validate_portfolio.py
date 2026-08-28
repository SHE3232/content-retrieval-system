#!/usr/bin/env python3
"""Validate portfolio facts and local image links against final evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

REQUIRED_HEADINGS = (
    "项目背景与个人职责",
    "架构与摄取/检索流程",
    "关键用户界面",
    "技术挑战与解决方案",
    "测试与性能结果",
    "无障碍、隐私与合规",
    "平台与外部门禁",
    "下载与交付清单",
    "文档入口",
    "已知局限与反思",
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"portfolio validation input must be an object: {path}")
    return value


def validate_portfolio(
    readme_path: Path, evidence_path: Path, manifest_path: Path
) -> dict[str, object]:
    readme_path = readme_path.resolve()
    root = readme_path.parent
    text = readme_path.read_text(encoding="utf-8")
    evidence = _load(evidence_path)
    manifest = _load(manifest_path)
    errors: list[str] = []
    commit = evidence.get("source_commit")
    if manifest.get("source_commit") != commit:
        errors.append("evidence and manifest commits differ")
    if not isinstance(commit, str) or commit not in text:
        errors.append("portfolio does not contain the evidence source_commit")
    for heading in REQUIRED_HEADINGS:
        if f"## {heading}" not in text:
            errors.append(f"missing portfolio section: {heading}")

    tests = evidence.get("tests", {})
    if isinstance(tests, dict):
        for name, result in tests.items():
            if isinstance(result, dict):
                for value in (
                    name,
                    str(result.get("status", "BLOCKED")),
                    str(int(result.get("passed", 0))),
                    str(int(result.get("skipped", 0))),
                ):
                    if value not in text:
                        errors.append(f"portfolio omits test fact: {name}={value}")

    platforms = evidence.get("platforms", {})
    if isinstance(platforms, dict):
        for name, result in platforms.items():
            if isinstance(result, dict) and str(result.get("status", "BLOCKED")) not in text:
                errors.append(f"portfolio omits platform status: {name}")

    artifacts = manifest.get("artifacts", [])
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            for key in ("path", "sha256"):
                value = str(artifact.get(key, ""))
                if not value or value not in text:
                    errors.append(f"portfolio omits artifact {key}: {value}")

    image_links = re.findall(r"!\[([^]]*)\]\(([^)]+)\)", text)
    if len(image_links) < 3:
        errors.append("portfolio requires at least three images")
    for alt, target in image_links:
        if not alt.strip():
            errors.append(f"portfolio image lacks alt text: {target}")
        pure = PurePosixPath(target)
        if pure.is_absolute() or ".." in pure.parts:
            errors.append(f"portfolio image path is unsafe: {target}")
            continue
        path = root.joinpath(*pure.parts).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            errors.append(f"portfolio image is missing: {target}")
    if "MobileCLIP" not in text or "research-only" not in text:
        errors.append("portfolio omits public/research license boundary")
    if errors:
        raise ValueError("invalid portfolio: " + "; ".join(errors))
    return {
        "schema_version": 1,
        "status": "PASS",
        "source_commit": commit,
        "image_count": len(image_links),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portfolio", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--delivery-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = validate_portfolio(args.portfolio, args.evidence, args.delivery_manifest)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
