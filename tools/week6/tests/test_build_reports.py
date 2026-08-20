from __future__ import annotations

import pytest

from tools.week6.build_reports import (
    REPORT_FILENAMES,
    _performance_summary_rows,
    _security_summary_rows,
    validate_report_inputs,
)


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


def test_performance_report_separates_mixed_hot_and_resource_metrics() -> None:
    rows = _performance_summary_rows(
        {
            "candidate_medians": {
                "embedding_combined_p95_ms": 12.3,
                "vector_query_p95_ms": 45.6,
                "embedding_hot_p95_ms": 1.2,
                "vector_query_hot_p95_ms": 3.4,
                "peak_rss_bytes": 1_073_741_824,
                "full_search_p95_ms": 78.9,
            },
            "improvements_percent": {
                "embedding_hot_p95_ms": 8.5,
                "vector_query_hot_p95_ms": 9.5,
                "peak_rss_bytes": 6.0,
            },
        }
    )

    labels = [row[0] for row in rows]
    assert labels == [
        "混合负载嵌入 P95",
        "混合负载向量查询 P95",
        "热缓存嵌入 P95",
        "热缓存向量查询 P95",
        "峰值 RSS",
        "全链路检索 P95",
    ]
    assert rows[2][2] == "8.500%"
    assert rows[4][1] == "1024.00 MiB"


def test_security_report_supports_gate_ready_check_map_and_isolation_details() -> None:
    rows = _security_summary_rows(
        {
            "network_isolation": {
                "enforced": True,
                "method": "process-network-deny",
                "sample_seconds": 1800,
                "probe_blocked": True,
            },
            "checks": {
                "offline_e2e": "PASS",
                "non_loopback_connections": "PASS",
                "path_traversal": "PASS",
                "reparse_point_escape": "PASS",
                "package_audit": "PASS",
            },
        }
    )

    assert rows[0] == ("网络隔离", "process-network-deny；1800 秒；外联探针已阻断", "PASS")
    assert ("路径穿越", "授权根目录边界", "PASS") in rows
    assert ("重解析点逃逸", "符号链接或目录联接", "PASS") in rows
