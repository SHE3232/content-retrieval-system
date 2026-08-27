from __future__ import annotations

import json
from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from tools.week8.validate_windows_release import validate_windows_archive


COMMIT = "a" * 40
REPOSITORY = Path(__file__).resolve().parents[3]
BUILD_SCRIPT = REPOSITORY / "tools" / "week8" / "build_windows_release.ps1"


def _write_archive(
    path: Path,
    *,
    commit: str = COMMIT,
    distribution_class: str = "general",
    include_legal: bool = True,
    release_frontend: bool = True,
    include_research_model: bool = False,
    extra_bytes: int = 0,
) -> None:
    model_entries = [
        {
            "model_id": "text-multilingual-v1",
            "license_name": "Apache-2.0",
            "relative_path": "text/text-multilingual-v1",
        }
    ]
    if include_research_model:
        model_entries.append(
            {
                "model_id": "mobileclip-s0-v1",
                "license_name": (
                    "Apple Machine Learning Research Model License"
                ),
                "relative_path": "mobileclip/mobileclip_s0.pt",
            }
        )
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "app/PACKAGE_MANIFEST.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "source_commit": commit,
                    "distribution_class": distribution_class,
                    "platform_claim": "Windows lightweight integrated stable build",
                }
            ),
        )
        if include_legal:
            archive.writestr("app/LICENSE", "MIT")
            archive.writestr("app/NOTICE", "notices")
            archive.writestr("app/THIRD_PARTY_NOTICES.md", "third parties")
        frontend_name = (
            "app/frontend/content_retrieval_app.exe"
            if release_frontend
            else "app/frontend/content_retrieval_app.pdb"
        )
        archive.writestr(frontend_name, b"release-binary")
        archive.writestr(
            "app/models/model-manifest.json",
            json.dumps({"schema_version": "1", "models": model_entries}),
        )
        archive.writestr(
            "app/models/text/text-multilingual-v1/config.json",
            "{}",
        )
        if include_research_model:
            archive.writestr(
                "app/models/mobileclip/mobileclip_s0.pt",
                b"research-weight",
            )
            archive.writestr(
                "app/models/mobileclip/LICENSE_MODELS",
                "Apple Machine Learning Research Model License",
            )
        if extra_bytes:
            archive.writestr("padding.bin", b"x" * extra_bytes)


def test_public_archive_passes_strict_distribution_validation(tmp_path: Path) -> None:
    archive = tmp_path / "public.zip"
    _write_archive(archive)

    result = validate_windows_archive(
        archive,
        expected_commit=COMMIT,
        distribution="default-public",
        size_limit_bytes=1_000_000,
    )

    assert result["source_commit"] == COMMIT
    assert result["distribution"] == "default-public"
    assert len(result["sha256"]) == 64


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"commit": "b" * 40}, "source commit mismatch"),
        ({"include_legal": False}, "required legal file"),
        ({"release_frontend": False}, "release frontend executable"),
        ({"include_research_model": True}, "research-only model"),
    ],
)
def test_public_archive_rejects_invalid_release_contents(
    tmp_path: Path,
    changes: dict[str, object],
    message: str,
) -> None:
    archive = tmp_path / "invalid.zip"
    _write_archive(archive, **changes)

    with pytest.raises(ValueError, match=message):
        validate_windows_archive(
            archive,
            expected_commit=COMMIT,
            distribution="default-public",
            size_limit_bytes=1_000_000,
        )


def test_archive_size_limit_is_strict(tmp_path: Path) -> None:
    archive = tmp_path / "public.zip"
    _write_archive(archive)
    exact_size = archive.stat().st_size

    with pytest.raises(ValueError, match="strict size limit"):
        validate_windows_archive(
            archive,
            expected_commit=COMMIT,
            distribution="default-public",
            size_limit_bytes=exact_size,
        )


def test_research_archive_requires_license_and_restricted_manifest(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "research.zip"
    _write_archive(
        archive,
        distribution_class="research-only",
        include_research_model=True,
    )

    result = validate_windows_archive(
        archive,
        expected_commit=COMMIT,
        distribution="research-only",
        size_limit_bytes=1_000_000,
    )

    assert result["distribution"] == "research-only"


def test_windows_builder_rejects_abbreviated_commit_before_other_inputs() -> None:
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_SCRIPT),
            "-RepositoryRoot",
            str(REPOSITORY),
            "-SourceCommit",
            "abc123",
            "-ValidateOnly",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode != 0
    assert "full 40-character" in completed.stdout + completed.stderr


def _run_builder_validation(commit: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_SCRIPT),
            "-RepositoryRoot",
            str(REPOSITORY),
            "-SourceCommit",
            commit,
            "-ValidateOnly",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_windows_builder_rejects_source_commit_mismatch() -> None:
    completed = _run_builder_validation("b" * 40)

    assert completed.returncode != 0
    assert "does not match repository HEAD" in completed.stdout + completed.stderr


def test_windows_builder_rejects_dirty_worktree() -> None:
    head = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.strip()
    completed = _run_builder_validation(head)

    assert completed.returncode != 0
    assert "Worktree is not clean" in completed.stdout + completed.stderr
