from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.week8.validate_macos_evidence import validate_macos_evidence


COMMIT = "d" * 40
REPOSITORY = Path(__file__).resolve().parents[3]
BUILD_SCRIPT = REPOSITORY / "tools" / "week8" / "build_macos_release.sh"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_evidence(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    build_log = tmp_path / "flutter-build.log"
    build_log.write_text("flutter build macos --release\nBuilt app", encoding="utf-8")
    app_archive = tmp_path / "offline-retrieval-macos.zip"
    app_archive.write_bytes(b"macOS app fixture")
    screenshot = tmp_path / "voiceover-search.png"
    screenshot.write_bytes(b"screenshot")
    data: dict[str, object] = {
        "schema_version": 1,
        "source_commit": COMMIT,
        "host": {
            "platform": "Darwin",
            "sw_vers": "ProductVersion: 15.6",
            "uname": "Darwin arm64",
            "hardware": "MacBookPro18,3",
            "simulator": False,
        },
        "flutter_build": {
            "command": "flutter build macos --release --no-pub",
            "exit_code": 0,
            "log": build_log.name,
        },
        "app_archive": {
            "path": app_archive.name,
            "sha256": _sha256(app_archive),
        },
        "runtime_checks": {
            "launch": "PASS",
            "health": "PASS",
            "five_format_e2e": "PASS",
        },
        "voiceover": {
            "navigation": True,
            "labels": True,
            "search_results": True,
            "high_contrast": True,
            "text_150_percent": True,
            "reduced_motion": True,
            "copy_path": True,
            "open_file": True,
        },
        "screenshots": [
            {"path": screenshot.name, "sha256": _sha256(screenshot)}
        ],
    }
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(data), encoding="utf-8")
    return evidence, data


def test_accepts_complete_real_macos_evidence(tmp_path: Path) -> None:
    evidence, _ = _valid_evidence(tmp_path)

    result = validate_macos_evidence(evidence, expected_commit=COMMIT)

    assert result["status"] == "PASS"
    assert result["source_commit"] == COMMIT


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data["host"].update(platform="Windows"), "Darwin"),
        (lambda data: data["host"].update(simulator=True), "real macOS"),
        (lambda data: data.update(source_commit="e" * 40), "commit"),
        (lambda data: data["flutter_build"].update(exit_code=1), "Flutter build"),
        (lambda data: data["runtime_checks"].update(health="FAIL"), "runtime"),
        (lambda data: data["voiceover"].update(labels=False), "VoiceOver"),
        (lambda data: data.update(screenshots=[]), "screenshot"),
    ],
)
def test_rejects_incomplete_or_non_macos_evidence(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    evidence, data = _valid_evidence(tmp_path)
    mutation(data)
    evidence.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        validate_macos_evidence(evidence, expected_commit=COMMIT)


def test_macos_builder_requires_real_host_release_and_evidence_capture() -> None:
    source = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "set -euo pipefail" in source
    assert '[[ "$(uname -s)" == "Darwin" ]]' in source
    assert "git status --porcelain=v1 --untracked-files=all" in source
    assert "flutter build macos --release --no-pub" in source
    assert "sw_vers" in source
    assert "system_profiler SPHardwareDataType" in source
    assert "run_real_five_format_e2e.py" in source
    assert '--base-url "$e2e_base_url"' in source
    assert "shasum -a 256" in source
    assert "validate_macos_evidence.py" in source
