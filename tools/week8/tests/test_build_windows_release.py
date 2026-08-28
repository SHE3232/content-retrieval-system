from __future__ import annotations

import json
import subprocess
from pathlib import Path
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
    include_research_runtime: bool = True,
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
            if include_research_runtime:
                archive.writestr(
                    "app/runtime/python/Lib/site-packages/mobileclip/__init__.py",
                    b"# research runtime fixture\n",
                )
            archive.writestr(
                "app/models/mobileclip/LICENSE_MODELS",
                (
                    "Disclaimer: This Apple Machine Learning Research Model "
                    "is provided solely for Research Purposes."
                ),
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


def test_research_archive_requires_mobileclip_runtime(tmp_path: Path) -> None:
    archive = tmp_path / "research-without-runtime.zip"
    _write_archive(
        archive,
        distribution_class="research-only",
        include_research_model=True,
        include_research_runtime=False,
    )

    with pytest.raises(ValueError, match="MobileCLIP runtime"):
        validate_windows_archive(
            archive,
            expected_commit=COMMIT,
            distribution="research-only",
            size_limit_bytes=1_000_000,
        )


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


def test_windows_builder_rejects_dirty_worktree(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    marker = repository / "tracked.txt"
    marker.write_text("clean\n", encoding="utf-8")
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
    subprocess.run(["git", "add", "tracked.txt"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repository, check=True)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    marker.write_text("dirty\n", encoding="utf-8")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_SCRIPT),
            "-RepositoryRoot",
            str(repository),
            "-SourceCommit",
            head,
            "-ValidateOnly",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode != 0
    assert "Worktree is not clean" in completed.stdout + completed.stderr


def test_windows_builder_does_not_use_stale_native_exit_code_for_ps1_calls() -> None:
    source = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "Default public Windows package build failed" not in source
    assert "Research-only Windows package build failed" not in source
    assert "Public model launcher preflight failed" not in source


def test_windows_builder_stages_research_models_without_source_caches() -> None:
    source = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "--distribution research-only" in source
    assert "-ModelRoot $researchModelRoot" in source
    assert "-ModelRoot $sourceModels" not in source


def test_windows_builder_keeps_mobileclip_source_out_of_public_package() -> None:
    source = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "ResearchThirdPartySourceDir" in source
    assert "$publicThirdPartySource = Join-Path $runRoot 'public-third-party-omitted'" in source
    assert "-ThirdPartySourceDir $publicThirdPartySource" in source
    assert "-ThirdPartySourceDir $researchThirdPartySource" in source


def test_windows_builder_uses_separate_research_python_runtime() -> None:
    source = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "ResearchPythonRuntimeDir" in source
    assert "$researchPythonRuntime -eq $pythonRuntime" in source
    assert "import mobileclip" in source
    assert "$researchPackageCommon['PythonRuntimeDir'] = $researchPythonRuntime" in source
