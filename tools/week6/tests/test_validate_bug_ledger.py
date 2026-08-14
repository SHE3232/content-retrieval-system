from __future__ import annotations

from copy import deepcopy

import pytest

from tools.week6.validate_bug_ledger import validate_bug_ledger


def _ledger() -> dict:
    return {
        "source_commit": "a" * 40,
        "test_sessions": ["docs/week6/evidence/tests/e2e-junit.xml"],
        "bugs": [
            {
                "id": "W6-001",
                "title": "Scoped catalog mixed fixtures",
                "severity": "High",
                "gate": "G2",
                "environment": "Windows",
                "reproduction_steps": ["Run two fixture roots"],
                "expected": "Only target root is selected",
                "actual": "Same-name files were mixed",
                "failure_evidence": "docs/week6/evidence/e2e/failed.json",
                "regression_test": "tools/week6/tests/test_run_integrated_e2e.py",
                "fix_commit": "b" * 40,
                "retest_command": "pytest tools/week6/tests/test_run_integrated_e2e.py",
                "retest_evidence": "docs/week6/evidence/e2e/summary.json",
                "status": "Closed",
            }
        ],
    }


def test_closed_high_bug_with_full_trace_passes() -> None:
    result = validate_bug_ledger(_ledger())
    assert result["status"] == "PASS"
    assert result["open_high"] == 0


@pytest.mark.parametrize("severity", ["Critical", "High"])
def test_open_critical_or_high_fails(severity: str) -> None:
    ledger = _ledger()
    ledger["bugs"][0]["severity"] = severity
    ledger["bugs"][0]["status"] = "Open"
    assert validate_bug_ledger(ledger)["status"] == "FAIL"


def test_empty_ledger_requires_real_test_sessions() -> None:
    ledger = _ledger()
    ledger["bugs"] = []
    ledger["test_sessions"] = []
    with pytest.raises(ValueError, match="test_sessions"):
        validate_bug_ledger(ledger)


def test_closed_serious_bug_requires_complete_fix_chain() -> None:
    for field in ("regression_test", "fix_commit", "retest_command", "retest_evidence"):
        ledger = _ledger()
        del ledger["bugs"][0][field]
        with pytest.raises(ValueError, match=field):
            validate_bug_ledger(ledger)
