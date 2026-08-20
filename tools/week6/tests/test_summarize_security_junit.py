from __future__ import annotations

from pathlib import Path

from tools.week6.summarize_security_junit import summarize_security_junit


def _write_junit(path: Path, cases: str) -> None:
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites><testsuite name="security">'
        f"{cases}"
        "</testsuite></testsuites>",
        encoding="utf-8",
    )


def test_security_junit_summary_maps_path_and_reparse_checks(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    _write_junit(
        junit,
        "".join(
            f'<testcase classname="backend.tests.test_week6_security" name="{name}" />'
            for name in (
                "test_authorized_root_rejects_direct_outside_file",
                "test_dot_dot_and_separator_variants_cannot_escape_root",
                "test_deleted_and_unsupported_files_are_not_read",
                "test_symlink_or_junction_escape_is_rejected",
            )
        ),
    )

    result = summarize_security_junit(junit)

    assert result["status"] == "PASS"
    assert result["checks"] == {
        "path_traversal": "PASS",
        "reparse_point_escape": "PASS",
    }
    assert len(result["cases"]) == 4


def test_security_junit_summary_fails_skipped_or_missing_required_case(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    _write_junit(
        junit,
        '<testcase classname="backend.tests.test_week6_security" '
        'name="test_symlink_or_junction_escape_is_rejected"><skipped /></testcase>',
    )

    result = summarize_security_junit(junit)

    assert result["status"] == "FAIL"
    assert result["checks"]["path_traversal"] == "FAIL"
    assert result["checks"]["reparse_point_escape"] == "FAIL"
