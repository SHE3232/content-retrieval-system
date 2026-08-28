from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

VOICEOVER_CHECKS = (
    "navigation",
    "labels",
    "search_results",
    "high_contrast",
    "text_150_percent",
    "reduced_motion",
    "copy_path",
    "open_file",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _evidence_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} path is missing")
    path = (root / value).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} path escapes the evidence directory") from error
    if not path.is_file():
        raise ValueError(f"{label} is not a file: {path}")
    return path


def validate_macos_evidence(
    evidence_path: Path | str,
    *,
    expected_commit: str,
) -> dict[str, Any]:
    path = Path(evidence_path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"macOS evidence is not a file: {path}")
    if len(expected_commit) != 40 or any(
        character not in "0123456789abcdef" for character in expected_commit
    ):
        raise ValueError("expected commit must be a full lowercase SHA-1 hash")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("macOS evidence is not valid UTF-8 JSON") from error
    data = _mapping(data, "macOS evidence")
    if data.get("source_commit") != expected_commit:
        raise ValueError("macOS evidence commit does not match the release commit")

    host = _mapping(data.get("host"), "host")
    if host.get("platform") != "Darwin":
        raise ValueError("macOS evidence must be captured on Darwin")
    if host.get("simulator") is not False:
        raise ValueError("real macOS hardware evidence is required")
    for field in ("sw_vers", "uname", "hardware"):
        if not isinstance(host.get(field), str) or not host[field].strip():
            raise ValueError(f"real macOS host field is missing: {field}")

    build = _mapping(data.get("flutter_build"), "flutter_build")
    if build.get("command") != "flutter build macos --release --no-pub":
        raise ValueError("Flutter build command is missing or not release mode")
    if build.get("exit_code") != 0:
        raise ValueError("Flutter build did not pass")
    build_log = _evidence_file(path.parent, build.get("log"), "Flutter build log")
    if "flutter build macos --release" not in build_log.read_text(
        encoding="utf-8",
        errors="replace",
    ):
        raise ValueError("Flutter build log does not prove a macOS release build")

    app = _mapping(data.get("app_archive"), "app_archive")
    app_archive = _evidence_file(path.parent, app.get("path"), "app archive")
    if app.get("sha256") != _sha256(app_archive):
        raise ValueError("app archive SHA-256 mismatch")

    runtime = _mapping(data.get("runtime_checks"), "runtime_checks")
    if any(
        runtime.get(name) != "PASS"
        for name in ("launch", "health", "five_format_e2e")
    ):
        raise ValueError("macOS runtime checks are incomplete")

    voiceover = _mapping(data.get("voiceover"), "voiceover")
    if any(voiceover.get(name) is not True for name in VOICEOVER_CHECKS):
        raise ValueError("VoiceOver and accessibility checks are incomplete")

    screenshots = data.get("screenshots")
    if not isinstance(screenshots, list) or not screenshots:
        raise ValueError("at least one hashed macOS screenshot is required")
    for index, item in enumerate(screenshots):
        screenshot = _mapping(item, f"screenshot {index}")
        screenshot_file = _evidence_file(
            path.parent,
            screenshot.get("path"),
            f"screenshot {index}",
        )
        if screenshot.get("sha256") != _sha256(screenshot_file):
            raise ValueError(f"screenshot {index} SHA-256 mismatch")

    return {
        "schema_version": 1,
        "status": "PASS",
        "source_commit": expected_commit,
        "host_platform": "Darwin",
        "app_archive_sha256": app["sha256"],
        "screenshot_count": len(screenshots),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate evidence captured on a real macOS host."
    )
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    result = validate_macos_evidence(
        args.evidence,
        expected_commit=args.expected_commit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
