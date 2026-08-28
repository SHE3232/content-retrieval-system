from __future__ import annotations

from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
CI = REPOSITORY / ".github" / "workflows" / "ci.yml"
RELEASE = REPOSITORY / ".github" / "workflows" / "release.yml"


def test_ci_covers_public_backend_tooling_flutter_and_windows_policy() -> None:
    source = CI.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in source
    assert "runs-on: ubuntu-24.04" in source
    assert "runs-on: windows-2022" in source
    assert "python-version: \"3.10\"" in source
    assert "uv sync --project backend --locked" in source
    assert "tools/compliance/tests" in source
    assert "tools/demo/tests" in source
    assert "tools/week8/tests" in source
    assert "flutter analyze --no-pub" in source
    assert "flutter test --no-pub" in source
    assert "actions/checkout@v4" in source
    assert "astral-sh/setup-uv@v6" in source
    assert "subosito/flutter-action@v2" in source
    assert "download_mobileclip.py" not in source
    assert "download_models.py" not in source


def test_release_workflow_is_tag_only_and_uploads_no_research_artifact() -> None:
    source = RELEASE.read_text(encoding="utf-8")

    assert "tags:\n      - \"v*\"" in source
    assert "permissions:\n  contents: write" in source
    assert "git rev-parse HEAD" in source
    assert "build_clean_source.py" in source
    assert "SHA256SUMS.txt" in source
    assert "softprops/action-gh-release@v2" in source
    assert "research-only" not in source.lower()
    assert "MobileCLIP" not in source
