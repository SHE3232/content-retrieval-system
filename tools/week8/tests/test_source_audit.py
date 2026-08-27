from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from tools.week8.source_audit import audit_paths


REPOSITORY = Path(__file__).resolve().parents[3]
SCRIPT = REPOSITORY / "tools" / "week8" / "source_audit.py"


def test_audit_paths_reports_unused_import(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("from pathlib import PurePath\n\nVALUE = 1\n", encoding="utf-8")

    report = audit_paths([source], minimum_confidence=80)

    assert report["findings"] == [
        {
            "confidence": 90,
            "kind": "import",
            "line": 1,
            "message": "unused import 'PurePath'",
            "path": str(source.resolve()),
            "symbol": "PurePath",
        }
    ]


def test_audit_paths_records_framework_callbacks_as_reviewed_exemptions(tmp_path: Path) -> None:
    source = tmp_path / "callbacks.py"
    source.write_text(
        "\n".join(
            (
                "from fastapi import FastAPI",
                "from pydantic import BaseModel, field_validator",
                "",
                "app = FastAPI()",
                "",
                "@app.get('/health')",
                "def health():",
                "    return {'status': 'ok'}",
                "",
                "class Payload(BaseModel):",
                "    value: str",
                "",
                "    @field_validator('value')",
                "    @classmethod",
                "    def validate_value(cls, value):",
                "        return value.strip() if cls else value",
                "",
            )
        ),
        encoding="utf-8",
    )

    report = audit_paths([source], minimum_confidence=80)

    assert report["findings"] == []
    assert report["reviewed_exemptions"] == [
        {
            "decorator": "app.get",
            "kind": "function",
            "line": 7,
            "path": str(source.resolve()),
            "symbol": "health",
        },
        {
            "decorator": "field_validator",
            "kind": "function",
            "line": 15,
            "path": str(source.resolve()),
            "symbol": "validate_value",
        },
    ]


def test_cli_writes_auditable_json_and_fails_for_findings(tmp_path: Path) -> None:
    source = tmp_path / "unused.py"
    source.write_text("import json\n", encoding="utf-8")
    output = tmp_path / "report.json"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--output", str(output)],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["minimum_confidence"] == 80
    assert payload["source_commit"] == subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, text=True
    ).strip()
    assert payload["tool"] == {"name": "vulture", "version": "2.16"}
    assert payload["paths"] == [str(source.resolve())]
    assert payload["findings"][0]["message"] == "unused import 'json'"


def test_audit_paths_excludes_virtualenv_and_mock_patch_decorator(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "test_sample.py").write_text(
        "\n".join(
            (
                "from unittest.mock import patch",
                "",
                "@patch('example.value')",
                "def test_value(mock_value):",
                "    assert mock_value",
                "",
            )
        ),
        encoding="utf-8",
    )
    site_packages = project / ".venv" / "Lib" / "site-packages"
    site_packages.mkdir(parents=True)
    (site_packages / "dependency.py").write_text("import json\n", encoding="utf-8")

    report = audit_paths([project], minimum_confidence=80)

    assert report["findings"] == []
    assert report["reviewed_exemptions"] == []
