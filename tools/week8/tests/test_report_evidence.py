from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools.week8.build_report_evidence import build_report_evidence


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _write_json(
        repository / "docs/week4/evidence/retrieval-benchmark-summary.json",
        {"nq": {"query_latency": {"p95_ms": 239.29}}},
    )
    _write_json(
        repository / "docs/week4/evidence/performance-summary.json",
        {"target": {"maximum_ms": 2000.0}},
    )
    _write_json(
        repository / "docs/week3/evidence/text-performance-summary.json",
        {
            "measurements": [
                {"batch_size": 1, "p50_latency_ms": 21.18},
                {"batch_size": 16, "throughput_items_per_second": 346.50},
            ]
        },
    )
    _write_json(
        repository / "docs/week5/evidence/attachments/five-format-e2e.json",
        {
            "status": "PASS",
            "indexing": {"result": {"parsed_files": 5, "indexed_files": 5}},
        },
    )
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.email", "week8@example.invalid"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Week 8 Test"],
        cwd=repository,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repository, check=True)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    return repository, commit


def test_build_report_evidence_binds_metrics_and_statuses_to_head(tmp_path: Path) -> None:
    repository, commit = _repository(tmp_path)
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "schema_version": 1,
            "source_commit": commit,
            "tests": {"backend": {"status": "PASS", "passed": 445, "skipped": 1}},
            "platforms": {
                "windows": {"status": "PASS", "reason": "validated"},
                "linux": {"status": "PASS", "reason": "validated"},
                "macos": {"status": "BLOCKED", "reason": "no host"},
            },
        },
    )

    evidence = build_report_evidence(
        repository=repository,
        manifest_path=manifest,
        output_path=tmp_path / "evidence.json",
        github_status="BLOCKED：未配置远程仓库",
        video_status="BLOCKED：未完成真实录屏",
    )

    assert evidence["source_commit"] == commit
    assert evidence["benchmarks"] == {
        "search_p95_ms": 239.29,
        "target_p95_ms": 2000.0,
        "text_batch1_p50_ms": 21.18,
        "text_batch16_throughput": 346.5,
    }
    assert evidence["five_formats"] == {
        "status": "PASS",
        "parsed_files": 5,
        "indexed_files": 5,
    }
    assert evidence["external_gates"]["github"].startswith("BLOCKED")
    assert len(evidence["sources"]) == 5


def test_build_report_evidence_rejects_manifest_from_other_commit(tmp_path: Path) -> None:
    repository, _ = _repository(tmp_path)
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "source_commit": "f" * 40,
            "tests": {},
            "platforms": {},
        },
    )

    with pytest.raises(ValueError, match="does not match repository HEAD"):
        build_report_evidence(
            repository=repository,
            manifest_path=manifest,
            output_path=tmp_path / "evidence.json",
            github_status="BLOCKED",
            video_status="BLOCKED",
        )
