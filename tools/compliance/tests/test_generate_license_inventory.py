from pathlib import Path

import pytest

from tools.compliance.generate_license_inventory import (
    build_inventory,
    parse_pubspec_lock,
    parse_uv_lock,
)


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
