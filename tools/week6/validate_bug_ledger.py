#!/usr/bin/env python3
"""Validate the Week 6 defect trace and zero-open-severity gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

COMMIT = re.compile(r"^[0-9a-f]{40}$")
SEVERITIES = {"Critical", "High", "Medium", "Low"}
STATUSES = {"Open", "Closed"}
BASE_FIELDS = (
    "id",
    "title",
    "severity",
    "gate",
    "environment",
    "reproduction_steps",
    "expected",
    "actual",
    "failure_evidence",
    "status",
)
CLOSED_FIELDS = ("regression_test", "fix_commit", "retest_command", "retest_evidence")


def validate_bug_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    commit = ledger.get("source_commit")
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise ValueError("source_commit must be a 40-character lowercase Git commit")
    sessions = ledger.get("test_sessions")
    if not isinstance(sessions, list) or not sessions or any(not isinstance(item, str) or not item for item in sessions):
        raise ValueError("test_sessions must reference at least one executed test session")
    bugs = ledger.get("bugs")
    if not isinstance(bugs, list):
        raise ValueError("bugs must be a list")
    seen: set[str] = set()
    for index, bug in enumerate(bugs):
        if not isinstance(bug, dict):
            raise ValueError(f"bug {index + 1} must be an object")
        for field in BASE_FIELDS:
            if field not in bug or bug[field] in (None, "", []):
                raise ValueError(f"bug {index + 1} requires {field}")
        identifier = bug["id"]
        if identifier in seen:
            raise ValueError(f"duplicate bug id: {identifier}")
        seen.add(identifier)
        if bug["severity"] not in SEVERITIES:
            raise ValueError(f"invalid severity for {identifier}")
        if bug["status"] not in STATUSES:
            raise ValueError(f"invalid status for {identifier}")
        if bug["status"] == "Closed":
            for field in CLOSED_FIELDS:
                if field not in bug or bug[field] in (None, "", []):
                    raise ValueError(f"closed bug {identifier} requires {field}")
            if not isinstance(bug["fix_commit"], str) or not COMMIT.fullmatch(bug["fix_commit"]):
                raise ValueError(f"closed bug {identifier} fix_commit must be a full commit")
    open_critical = sum(bug["status"] == "Open" and bug["severity"] == "Critical" for bug in bugs)
    open_high = sum(bug["status"] == "Open" and bug["severity"] == "High" for bug in bugs)
    return {
        "status": "PASS" if open_critical == 0 and open_high == 0 else "FAIL",
        "open_critical": open_critical,
        "open_high": open_high,
        "closed": sum(bug["status"] == "Closed" for bug in bugs),
        "total": len(bugs),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_bug_ledger(json.loads(args.ledger.read_text(encoding="utf-8")))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
