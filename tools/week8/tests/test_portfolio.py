from __future__ import annotations

import json
from pathlib import Path

from tools.week8.build_portfolio import build_portfolio
from tools.week8.build_report_figures import build_figures
from tools.week8.validate_portfolio import validate_portfolio


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_portfolio_is_evidence_bound_and_all_local_links_resolve(tmp_path: Path) -> None:
    commit = "a" * 40
    evidence = _write_json(
        tmp_path / "evidence.json",
        {
            "schema_version": 1,
            "source_commit": commit,
            "tests": {
                "backend": {"status": "PASS", "passed": 445, "skipped": 1},
                "flutter": {"status": "PASS", "passed": 249, "skipped": 0},
            },
            "platforms": {
                "windows": {"status": "PASS", "reason": "validated"},
                "linux": {"status": "PASS", "reason": "validated"},
                "macos": {"status": "BLOCKED", "reason": "no real host"},
            },
            "external_gates": {
                "github": "BLOCKED：未配置远程仓库",
                "video": "BLOCKED：未完成真实录屏",
            },
            "benchmarks": {
                "search_p95_ms": 239.29,
                "target_p95_ms": 2000.0,
                "text_batch1_p50_ms": 21.18,
                "text_batch16_throughput": 346.5,
            },
            "five_formats": {"status": "PASS", "parsed_files": 5, "indexed_files": 5},
        },
    )
    figures = tmp_path / "figures"
    build_figures(evidence, figures)
    manifest = _write_json(
        tmp_path / "manifest.json",
        {
            "source_commit": commit,
            "artifacts": [
                {
                    "path": "01_平台发布/Windows/offline.zip",
                    "bytes": 123,
                    "sha256": "b" * 64,
                    "distribution_class": "default-public",
                },
                {
                    "path": "03_课程演示研究包/research.zip",
                    "bytes": 456,
                    "sha256": "c" * 64,
                    "distribution_class": "research-only",
                },
            ],
        },
    )
    output = tmp_path / "portfolio"

    readme = build_portfolio(
        evidence_path=evidence,
        delivery_manifest_path=manifest,
        figure_dir=figures,
        output_dir=output,
    )
    result = validate_portfolio(readme, evidence, manifest)

    text = readme.read_text(encoding="utf-8")
    assert result["status"] == "PASS"
    assert commit in text
    assert "445" in text and "249" in text
    assert "GitHub" in text and "BLOCKED" in text
    assert "视频" in text and "BLOCKED" in text
    assert "b" * 64 in text
    assert "![总体架构图](assets/architecture.png)" in text
    assert "![发行关系图](assets/release-model.png)" in text
    assert "![测试汇总图](assets/test-summary.png)" in text
