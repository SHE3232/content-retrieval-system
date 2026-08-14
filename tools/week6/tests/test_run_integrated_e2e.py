from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.week6.run_integrated_e2e import (
    REQUIRED_UI_OPERATIONS,
    assert_ui_evidence,
    catalog_items_under_root,
    workflow_status,
)


def test_catalog_scope_uses_normalized_parent_path(tmp_path: Path) -> None:
    target = tmp_path / "api"
    other = tmp_path / "ui"
    target.mkdir()
    other.mkdir()
    items = [
        {"name": "same.txt", "path": str(target / "same.txt")},
        {"name": "same.txt", "path": str(other / "same.txt")},
    ]
    assert catalog_items_under_root(items, target) == [items[0]]


def _ui_payload() -> dict[str, object]:
    return {
        "status": "PASS",
        "real_backend": True,
        "operations": {name: True for name in REQUIRED_UI_OPERATIONS},
    }


def test_ui_evidence_requires_real_backend_and_every_operation(tmp_path: Path) -> None:
    path = tmp_path / "ui.json"
    path.write_text(json.dumps(_ui_payload()), encoding="utf-8")
    value = assert_ui_evidence(path)
    assert value["status"] == "PASS"


@pytest.mark.parametrize("missing", sorted(REQUIRED_UI_OPERATIONS))
def test_ui_evidence_rejects_missing_or_false_operation(tmp_path: Path, missing: str) -> None:
    payload = _ui_payload()
    payload["operations"][missing] = False  # type: ignore[index]
    path = tmp_path / "ui.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=missing):
        assert_ui_evidence(path)


def test_ui_evidence_rejects_mock_backend(tmp_path: Path) -> None:
    payload = _ui_payload()
    payload["real_backend"] = False
    path = tmp_path / "ui.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="real backend"):
        assert_ui_evidence(path)


def test_workflow_passes_only_when_all_required_sections_pass() -> None:
    sections = {
        "five_format_index": "PASS",
        "search_channels": "PASS",
        "filters": "PASS",
        "mutations": "PASS",
        "persistence": "PASS",
        "disconnect_recovery": "PASS",
        "flutter_ui": "PASS",
    }
    assert workflow_status(sections) == "PASS"
    sections["persistence"] = "FAIL"
    assert workflow_status(sections) == "FAIL"
