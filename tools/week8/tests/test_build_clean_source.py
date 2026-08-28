from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.week8.build_clean_source import (
    export_clean_source,
    load_profile,
    read_tracked_paths,
    select_tracked_paths,
)

REPOSITORY = Path(__file__).resolve().parents[3]
DELIVERY_PROFILE = REPOSITORY / "tools" / "week8" / "delivery_profile.json"
CLEAN_SOURCE_SCRIPT = REPOSITORY / "tools" / "week8" / "build_clean_source.py"


PROFILE = {
    "include_root_files": ["README.md", "LICENSE"],
    "include_root_directories": ["backend", "frontend", "docs", "models", "demo-data"],
    "exclude_globs": [
        "docs/**/*.docx",
        "docs/**/*.zip",
        "docs/superpowers/**",
        "**/.venv/**",
        "**/build/**",
        "models/**",
    ],
    "allow_globs": ["models/model-manifest.example.json"],
}


def test_select_tracked_paths_is_allowlist_first_and_records_exclusion_reason() -> None:
    tracked = [
        "README.md",
        "LICENSE",
        "AGENTS.md",
        "backend/src/app.py",
        "frontend/lib/main.dart",
        "frontend/build/windows/app.exe",
        "docs/ARCHITECTURE.md",
        "docs/week7/reports/report.docx",
        "docs/week7/submission/archive.zip",
        "docs/superpowers/plans/internal.md",
        "models/model-manifest.example.json",
        "models/mobileclip/model.safetensors",
        "demo-data/project-demo/fixture.docx",
    ]

    selected, excluded = select_tracked_paths(tracked, PROFILE)

    assert selected == [
        "LICENSE",
        "README.md",
        "backend/src/app.py",
        "demo-data/project-demo/fixture.docx",
        "docs/ARCHITECTURE.md",
        "frontend/lib/main.dart",
        "models/model-manifest.example.json",
    ]
    assert excluded == {
        "AGENTS.md": "not-allowlisted",
        "docs/superpowers/plans/internal.md": "excluded:docs/superpowers/**",
        "docs/week7/reports/report.docx": "excluded:docs/**/*.docx",
        "docs/week7/submission/archive.zip": "excluded:docs/**/*.zip",
        "frontend/build/windows/app.exe": "excluded:**/build/**",
        "models/mobileclip/model.safetensors": "excluded:models/**",
    }


def test_repository_profile_keeps_runnable_source_and_excludes_history_binaries() -> None:
    profile = load_profile(DELIVERY_PROFILE)
    tracked = read_tracked_paths(REPOSITORY)

    selected, _ = select_tracked_paths(tracked, profile)
    selected_set = set(selected)

    assert {
        "README.md",
        "LICENSE",
        "NOTICE",
        "THIRD_PARTY_NOTICES.md",
        "backend/pyproject.toml",
        "backend/uv.lock",
        "frontend/pubspec.yaml",
        "frontend/pubspec.lock",
        "models/model-manifest.example.json",
        "tools/start-mvp.ps1",
        "tools/compliance/generate_license_inventory.py",
    }.issubset(selected_set)
    assert any(path.startswith("demo-data/") and path.endswith(".docx") for path in selected)
    assert not any(path.startswith("docs/superpowers/") for path in selected)
    assert not any(
        path.startswith("docs/") and path.endswith((".docx", ".zip"))
        for path in selected
    )
    assert not any(path.startswith("models/") for path in selected if path != "models/model-manifest.example.json")


def _init_repository(root: Path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "week8@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Week 8 Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _write_test_profile(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "test-public-source",
                "include_root_files": ["README.md", "LICENSE"],
                "include_root_directories": ["backend", "docs", "models"],
                "exclude_globs": ["docs/**/*.docx", "models/**"],
                "allow_globs": ["models/model-manifest.example.json"],
                "required_files": [
                    "README.md",
                    "LICENSE",
                    "backend/app.py",
                    "models/model-manifest.example.json",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_export_clean_source_copies_only_tracked_selected_files_and_hashes_them(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "backend").mkdir()
    (repository / "docs" / "week7").mkdir(parents=True)
    (repository / "models").mkdir()
    (repository / "README.md").write_text("public\n", encoding="utf-8")
    (repository / "LICENSE").write_text("license\n", encoding="utf-8")
    (repository / "backend" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repository / "docs" / "week7" / "report.docx").write_bytes(b"private history")
    (repository / "models" / "model-manifest.example.json").write_text("{}\n", encoding="utf-8")
    (repository / "models" / "weight.safetensors").write_bytes(b"restricted")
    commit = _init_repository(repository)
    profile_path = tmp_path / "profile.json"
    _write_test_profile(profile_path)
    destination = tmp_path / "clean-source"

    manifest = export_clean_source(repository, destination, profile_path)

    copied = [item["path"] for item in manifest["files"]]
    assert copied == [
        "LICENSE",
        "README.md",
        "backend/app.py",
        "models/model-manifest.example.json",
    ]
    assert manifest["source_commit"] == commit
    assert manifest["file_count"] == 4
    assert manifest["total_bytes"] == sum(item["bytes"] for item in manifest["files"])
    assert manifest["exclusions_by_rule"] == {
        "excluded:docs/**/*.docx": 1,
        "excluded:models/**": 1,
    }
    assert not (destination / "docs" / "week7" / "report.docx").exists()
    assert not (destination / "models" / "weight.safetensors").exists()
    for item in manifest["files"]:
        exported = destination / item["path"]
        assert exported.is_file()
        assert item["sha256"] == hashlib.sha256(exported.read_bytes()).hexdigest()
    persisted = json.loads(
        (destination / "CLEAN_SOURCE_MANIFEST.json").read_text(encoding="utf-8")
    )
    assert persisted == manifest


def test_export_clean_source_rejects_nonempty_unowned_destination(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("public\n", encoding="utf-8")
    (repository / "LICENSE").write_text("license\n", encoding="utf-8")
    (repository / "backend").mkdir()
    (repository / "backend" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repository / "models").mkdir()
    (repository / "models" / "model-manifest.example.json").write_text("{}\n", encoding="utf-8")
    _init_repository(repository)
    profile_path = tmp_path / "profile.json"
    _write_test_profile(profile_path)
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "user.txt").write_text("do not overwrite\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not an owned clean-source directory"):
        export_clean_source(repository, destination, profile_path)

    assert (destination / "user.txt").read_text(encoding="utf-8") == "do not overwrite\n"


def test_export_clean_source_rejects_tracked_worktree_changes(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("public\n", encoding="utf-8")
    (repository / "LICENSE").write_text("license\n", encoding="utf-8")
    (repository / "backend").mkdir()
    (repository / "backend" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repository / "models").mkdir()
    (repository / "models" / "model-manifest.example.json").write_text("{}\n", encoding="utf-8")
    _init_repository(repository)
    (repository / "backend" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    profile_path = tmp_path / "profile.json"
    _write_test_profile(profile_path)

    with pytest.raises(ValueError, match="requires a clean tree"):
        export_clean_source(repository, tmp_path / "clean-source", profile_path)


def test_export_clean_source_replaces_only_its_matching_owned_destination(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("public\n", encoding="utf-8")
    (repository / "LICENSE").write_text("license\n", encoding="utf-8")
    (repository / "backend").mkdir()
    (repository / "backend" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repository / "models").mkdir()
    (repository / "models" / "model-manifest.example.json").write_text("{}\n", encoding="utf-8")
    commit = _init_repository(repository)
    profile_path = tmp_path / "profile.json"
    _write_test_profile(profile_path)
    destination = tmp_path / "clean-source"
    first = export_clean_source(repository, destination, profile_path)
    (destination / "stale.txt").write_text("owned staging residue\n", encoding="utf-8")

    second = export_clean_source(repository, destination, profile_path)

    assert not (destination / "stale.txt").exists()
    assert second["source_commit"] == first["source_commit"] == commit
    assert second["files"] == first["files"]


def test_export_clean_source_rejects_tracked_symbolic_link(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "config", "core.symlinks", "true"], cwd=repository, check=True)
    (repository / "README.md").write_text("public\n", encoding="utf-8")
    (repository / "LICENSE").write_text("license\n", encoding="utf-8")
    (repository / "backend").mkdir()
    (repository / "backend" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repository / "models").mkdir()
    (repository / "models" / "model-manifest.example.json").write_text("{}\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("SECRET = True\n", encoding="utf-8")
    try:
        os.symlink(outside, repository / "backend" / "linked.py")
    except OSError as error:
        pytest.skip(f"symbolic links unavailable on this host: {error}")
    _init_repository(repository)
    profile_path = tmp_path / "profile.json"
    _write_test_profile(profile_path)

    with pytest.raises(ValueError, match="symbolic link"):
        export_clean_source(repository, tmp_path / "clean-source", profile_path)


def test_export_clean_source_fails_closed_when_tracked_path_is_link_like(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("public\n", encoding="utf-8")
    (repository / "LICENSE").write_text("license\n", encoding="utf-8")
    (repository / "backend").mkdir()
    (repository / "backend" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repository / "models").mkdir()
    (repository / "models" / "model-manifest.example.json").write_text("{}\n", encoding="utf-8")
    _init_repository(repository)
    profile_path = tmp_path / "profile.json"
    _write_test_profile(profile_path)
    original_is_symlink = Path.is_symlink

    def is_symlink(path: Path) -> bool:
        return path.name == "app.py" or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", is_symlink)

    with pytest.raises(ValueError, match="symbolic link"):
        export_clean_source(repository, tmp_path / "clean-source", profile_path)


def test_cli_exports_clean_source_and_prints_summary(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("public\n", encoding="utf-8")
    (repository / "LICENSE").write_text("license\n", encoding="utf-8")
    (repository / "backend").mkdir()
    (repository / "backend" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repository / "models").mkdir()
    (repository / "models" / "model-manifest.example.json").write_text("{}\n", encoding="utf-8")
    commit = _init_repository(repository)
    profile_path = tmp_path / "profile.json"
    _write_test_profile(profile_path)
    destination = tmp_path / "clean-source"

    completed = subprocess.run(
        [
            sys.executable,
            str(CLEAN_SOURCE_SCRIPT),
            "--repository",
            str(repository),
            "--destination",
            str(destination),
            "--profile",
            str(profile_path),
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary == {
        "destination": str(destination.resolve()),
        "file_count": 4,
        "source_commit": commit,
        "total_bytes": sum(
            path.stat().st_size
            for path in (
                destination / "README.md",
                destination / "LICENSE",
                destination / "backend" / "app.py",
                destination / "models" / "model-manifest.example.json",
            )
        ),
    }
