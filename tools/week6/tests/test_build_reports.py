from __future__ import annotations

import pytest

from tools.week6.build_reports import REPORT_FILENAMES, validate_report_inputs


def _manifest(status: str = "PASS") -> dict:
    return {
        "source_commit": "a" * 40,
        "gates": [{"gate_id": f"G{i}", "status": status} for i in range(10)],
    }


def test_final_reports_require_all_gates_pass() -> None:
    validate_report_inputs(_manifest(), draft=False)
    incomplete = _manifest()
    incomplete["gates"][6]["status"] = "BLOCKED"
    with pytest.raises(ValueError, match="G6"):
        validate_report_inputs(incomplete, draft=False)


def test_draft_reports_preserve_incomplete_status() -> None:
    incomplete = _manifest("NOT_RUN")
    result = validate_report_inputs(incomplete, draft=True)
    assert result["document_status"] == "DRAFT - NOT ACCEPTED"
    assert result["incomplete_gates"] == [f"G{i}" for i in range(10)]


def test_exactly_three_formal_report_names_are_fixed() -> None:
    assert tuple(REPORT_FILENAMES) == (
        "完整测试与覆盖率报告.docx",
        "性能优化基准报告.docx",
        "缺陷修复与本地数据安全审查报告.docx",
    )
