from __future__ import annotations

import io
import json
from pathlib import Path
import tarfile

import pytest

from tools.week8.validate_linux_release import validate_linux_archive


COMMIT = "c" * 40
REPOSITORY = Path(__file__).resolve().parents[3]
BUILD_SCRIPT = REPOSITORY / "tools" / "week8" / "build_linux_release.sh"


def _add_bytes(archive: tarfile.TarFile, name: str, value: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(value)
    info.mode = 0o755 if name.endswith("content_retrieval_app") else 0o644
    archive.addfile(info, io.BytesIO(value))


def _write_archive(
    path: Path,
    *,
    commit: str = COMMIT,
    include_research_model: bool = False,
) -> None:
    models = [
        {
            "model_id": "text-multilingual-v1",
            "license_name": "Apache-2.0",
        }
    ]
    if include_research_model:
        models.append(
            {
                "model_id": "mobileclip-s0-v1",
                "license_name": (
                    "Apple Machine Learning Research Model License"
                ),
            }
        )
    with tarfile.open(path, "w:gz") as archive:
        _add_bytes(
            archive,
            "app/PACKAGE_MANIFEST.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "source_commit": commit,
                    "distribution_class": "general",
                    "platform_claim": "Ubuntu 24.04 x64 release",
                }
            ).encode(),
        )
        _add_bytes(archive, "app/LICENSE", b"MIT")
        _add_bytes(archive, "app/NOTICE", b"notices")
        _add_bytes(archive, "app/THIRD_PARTY_NOTICES.md", b"third parties")
        _add_bytes(
            archive,
            "app/frontend/content_retrieval_app",
            b"linux-release",
        )
        _add_bytes(
            archive,
            "app/models/model-manifest.json",
            json.dumps({"schema_version": "1", "models": models}).encode(),
        )
        _add_bytes(
            archive,
            "app/models/text/text-multilingual-v1/config.json",
            b"{}",
        )
        if include_research_model:
            _add_bytes(
                archive,
                "app/models/mobileclip/mobileclip_s0.pt",
                b"restricted",
            )


def test_linux_archive_passes_public_release_validation(tmp_path: Path) -> None:
    archive = tmp_path / "linux.tar.gz"
    _write_archive(archive)

    result = validate_linux_archive(
        archive,
        expected_commit=COMMIT,
        size_limit_bytes=1_000_000,
    )

    assert result["source_commit"] == COMMIT
    assert result["distribution"] == "default-public"
    assert len(result["sha256"]) == 64


def test_linux_archive_rejects_research_weight(tmp_path: Path) -> None:
    archive = tmp_path / "linux.tar.gz"
    _write_archive(archive, include_research_model=True)

    with pytest.raises(ValueError, match="research-only model"):
        validate_linux_archive(
            archive,
            expected_commit=COMMIT,
            size_limit_bytes=1_000_000,
        )


def test_linux_builder_contains_fail_closed_release_policy() -> None:
    source = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "set -euo pipefail" in source
    assert "trap cleanup EXIT" in source
    assert "^[0-9a-f]{40}$" in source
    assert "git status --porcelain=v1 --untracked-files=all" in source
    assert "flutter build linux --release --no-pub" in source
    assert "build_public_model_root.py" in source
    assert "validate_linux_release.py" in source
    assert "sha256sum" in source
    assert "PACKAGE_MANIFEST.json" in source
    assert "MobileCLIP weights are not included" in source
