import csv
import json
from pathlib import Path

import pytest

from tools.compliance.generate_license_inventory import (
    PYTHON_LOCKS,
    build_inventory,
    parse_pubspec_lock,
    parse_uv_lock,
)


REPOSITORY = Path(__file__).resolve().parents[3]


def test_python_lock_set_includes_demo_tools() -> None:
    assert ("demo-tools", Path("tools/demo/uv.lock"), Path("tools/demo/pyproject.toml")) in PYTHON_LOCKS


def test_parse_uv_lock_keeps_name_version_and_registry(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text(
        'version = 1\n\n[[package]]\nname = "demo"\nversion = "1.2.3"\n'
        'source = { registry = "https://pypi.org/simple" }\n',
        encoding="utf-8",
    )

    assert parse_uv_lock(lock) == [
        {
            "name": "demo",
            "version": "1.2.3",
            "source": "https://pypi.org/simple",
        }
    ]


def test_parse_pubspec_lock_keeps_dependency_kind(tmp_path: Path) -> None:
    lock = tmp_path / "pubspec.lock"
    lock.write_text(
        "packages:\n"
        "  http:\n"
        '    dependency: "direct main"\n'
        "    description:\n"
        "      name: http\n"
        '      url: "https://pub.dev"\n'
        "    source: hosted\n"
        '    version: "1.6.0"\n',
        encoding="utf-8",
    )

    assert parse_pubspec_lock(lock) == [
        {
            "name": "http",
            "version": "1.6.0",
            "source": "https://pub.dev",
            "dependency_type": "direct-main",
        }
    ]


def test_build_inventory_rejects_unapproved_locked_component(tmp_path: Path) -> None:
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "uv.lock").write_text(
        '[[package]]\nname = "demo"\nversion = "1.2.3"\n'
        'source = { registry = "https://pypi.org/simple" }\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"unreviewed component: python:demo@1\.2\.3",
    ):
        build_inventory(tmp_path, {"components": []})


def test_repository_inventory_covers_every_locked_component() -> None:
    approvals = json.loads(
        (REPOSITORY / "tools/compliance/approved-licenses.json").read_text(
            encoding="utf-8"
        )
    )
    rows = build_inventory(REPOSITORY, approvals)
    with (REPOSITORY / "docs/dependency-licenses.csv").open(
        encoding="utf-8",
        newline="",
    ) as inventory_file:
        rendered = list(csv.DictReader(inventory_file))

    assert rendered == rows
    assert len(rows) == 383
    assert not [
        row for row in rows if row["review_status"] == "review-required"
    ]


def test_compliance_summary_matches_lock_record_counts() -> None:
    report = (REPOSITORY / "docs/OPEN_SOURCE_COMPLIANCE.md").read_text(encoding="utf-8")
    assert "252 个唯一的" in report
    assert "| 模型工具 Python | `model-tools/uv.lock` | 99 |" in report
    assert "| 转换工具 Python | `conversion-tools/uv.lock` | 84 |" in report
