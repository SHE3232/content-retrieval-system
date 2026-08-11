#!/usr/bin/env python3
"""Validate Week 5 evidence without third-party dependencies."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REQUIRED_GATES = {
    "build.windows",
    "build.macos",
    "build.linux",
    "build.android",
    "build.web",
    "a11y.nvda",
    "a11y.voiceover",
    "a11y.android_scanner",
    "a11y.wave",
    "a11y.keyboard",
    "a11y.high_contrast",
    "a11y.text_scale_200",
    "a11y.reduced_motion",
    "e2e.five_formats",
    "e2e.persistence",
    "usability.participant_01",
    "usability.participant_02",
    "usability.participant_03",
    "usability.summary",
}

ALLOWED_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def validate_evidence(root: Path, allow_incomplete: bool = False) -> int:
    root = root.resolve()
    structural_errors: list[str] = []
    completeness_errors: list[str] = []
    records: dict[str, dict[str, Any]] = {}

    if not root.is_dir():
        print(f"ERROR evidence root not found: {root}")
        return 1

    for path in sorted(root.rglob("*.json")):
        if path.name == "manifest.json":
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            structural_errors.append(f"{path.relative_to(root)}: invalid JSON ({error})")
            continue
        if not isinstance(value, dict) or not isinstance(value.get("gate_id"), str):
            structural_errors.append(f"{path.relative_to(root)}: missing gate_id")
            continue
        gate_id = value["gate_id"]
        if gate_id in records:
            structural_errors.append(f"{gate_id}: duplicate gate_id")
            continue
        records[gate_id] = value
        _validate_record(root, gate_id, value, structural_errors, completeness_errors)

    for gate_id in sorted(REQUIRED_GATES):
        if gate_id not in records:
            completeness_errors.append(f"{gate_id}: missing")

    for gate_id in sorted(REQUIRED_GATES):
        record = records.get(gate_id)
        status = record.get("status") if record else "MISSING"
        print(f"{gate_id}: {status}")

    passed = sum(
        1
        for gate_id in REQUIRED_GATES
        if records.get(gate_id, {}).get("status") == "PASS"
    )
    print(f"Week 5 evidence: {passed}/{len(REQUIRED_GATES)} required gates PASS")
    for error in structural_errors + completeness_errors:
        print(f"ERROR {error}")

    if structural_errors:
        return 1
    if completeness_errors and not allow_incomplete:
        return 1
    return 0


def _validate_record(
    root: Path,
    gate_id: str,
    record: dict[str, Any],
    structural_errors: list[str],
    completeness_errors: list[str],
) -> None:
    status = record.get("status")
    if status not in ALLOWED_STATUSES:
        structural_errors.append(f"{gate_id}: invalid status {status!r}")
    elif status != "PASS":
        completeness_errors.append(f"{gate_id}: status is {status}")

    for field in ("tester", "environment"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            structural_errors.append(f"{gate_id}: missing {field}")
    for field in ("procedure", "observations"):
        if not _nonempty_list(record.get(field)):
            structural_errors.append(f"{gate_id}: missing {field}")

    tested_at = record.get("tested_at")
    try:
        parsed = datetime.fromisoformat(tested_at) if isinstance(tested_at, str) else None
        if parsed is None or parsed.tzinfo is None:
            raise ValueError("timezone required")
        if parsed.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("future timestamp")
    except ValueError as error:
        structural_errors.append(f"{gate_id}: invalid tested_at ({error})")

    attachments = record.get("attachments")
    if not _nonempty_list(attachments):
        structural_errors.append(f"{gate_id}: missing attachments")
        return
    for attachment in attachments:
        resolved = (root / attachment).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            structural_errors.append(f"{gate_id}: invalid attachment {attachment!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    return validate_evidence(args.evidence_root, args.allow_incomplete)


if __name__ == "__main__":
    raise SystemExit(main())
