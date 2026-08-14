"""Deterministic Week 6 pytest layer classification."""

from __future__ import annotations


def classify_nodeid(nodeid: str) -> set[str]:
    normalized = nodeid.replace("\\", "/")
    if normalized.startswith("backend/"):
        normalized = normalized[len("backend/") :]
    if normalized.startswith("tests/test_mvp_launcher.py::"):
        return {"integration"}
    if normalized.startswith("tests/test_week4_e2e.py::") or normalized.startswith(
        "tests/test_mvp_smoke.py::"
    ):
        return {"e2e"}
    if "test_real_tika_extracts_a_generated_docx" in normalized:
        return {"integration", "requires_tika"}
    return {"unit"}
