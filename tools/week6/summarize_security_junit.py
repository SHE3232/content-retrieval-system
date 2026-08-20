#!/usr/bin/env python3
"""Convert the required Week 6 security pytest cases into gate-ready JSON."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


PATH_TRAVERSAL_CASES = (
    "test_authorized_root_rejects_direct_outside_file",
    "test_dot_dot_and_separator_variants_cannot_escape_root",
    "test_deleted_and_unsupported_files_are_not_read",
)
REPARSE_CASES = ("test_symlink_or_junction_escape_is_rejected",)


def _case_status(case: ET.Element) -> str:
    if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
        return "FAIL"
    return "PASS"


def summarize_security_junit(path: Path) -> dict[str, object]:
    source = path.read_bytes()
    root = ET.fromstring(source)
    cases = {
        str(case.get("name")): _case_status(case)
        for case in root.iter("testcase")
        if case.get("name")
    }

    def group_status(required: tuple[str, ...]) -> str:
        return "PASS" if all(cases.get(name) == "PASS" for name in required) else "FAIL"

    checks = {
        "path_traversal": group_status(PATH_TRAVERSAL_CASES),
        "reparse_point_escape": group_status(REPARSE_CASES),
    }
    return {
        "status": "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "junit_sha256": hashlib.sha256(source).hexdigest(),
        "checks": checks,
        "cases": [
            {"name": name, "status": cases.get(name, "MISSING")}
            for name in PATH_TRAVERSAL_CASES + REPARSE_CASES
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize_security_junit(args.junit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
