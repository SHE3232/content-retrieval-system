#!/usr/bin/env python3
"""Validate two real Week 8 end-to-end rehearsal records."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_STEPS = (
    "cold_start",
    "text_ingestion",
    "image_ingestion",
    "text_search",
    "image_search",
    "keyboard_navigation",
    "screen_reader",
    "privacy_check",
    "shutdown",
)


def validate_rehearsals(data: dict[str, Any], *, source_commit: str) -> dict[str, object]:
    """Return a PASS summary only for two complete, timestamped rehearsals."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source_commit must be a full lowercase Git commit")
    if data.get("source_commit") != source_commit:
        raise ValueError("rehearsal source_commit differs from the frozen commit")
    runs = data.get("runs")
    if not isinstance(runs, list) or len(runs) != 2:
        raise ValueError("exactly two rehearsal runs are required")

    timestamps: set[str] = set()
    durations: list[float] = []
    for index, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            raise TypeError(f"rehearsal {index} must be an object")
        recorded_at = str(run.get("recorded_at", ""))
        try:
            parsed = datetime.fromisoformat(recorded_at)
        except ValueError as error:
            raise ValueError(f"rehearsal {index} recorded_at is invalid") from error
        if parsed.tzinfo is None:
            raise ValueError(f"rehearsal {index} recorded_at requires a time zone")
        if recorded_at in timestamps:
            raise ValueError("rehearsal timestamps must be distinct")
        timestamps.add(recorded_at)

        try:
            duration = float(run.get("duration_seconds", 0))
        except (TypeError, ValueError) as error:
            raise ValueError(f"rehearsal {index} duration is invalid") from error
        if not 240 <= duration <= 420:
            raise ValueError(f"rehearsal {index} duration must be 240-420 seconds")
        durations.append(duration)

        environment = run.get("environment")
        if not isinstance(environment, dict):
            raise TypeError(f"rehearsal {index} environment must be an object")
        for field in ("os", "app_artifact_sha256", "operator"):
            if not str(environment.get(field, "")).strip():
                raise ValueError(f"rehearsal {index} environment.{field} is missing")
        if not re.fullmatch(r"[0-9a-f]{64}", str(environment["app_artifact_sha256"])):
            raise ValueError(f"rehearsal {index} artifact hash is invalid")

        steps = run.get("steps")
        if not isinstance(steps, dict):
            raise TypeError(f"rehearsal {index} steps must be an object")
        missing = [step for step in REQUIRED_STEPS if steps.get(step) != "PASS"]
        if missing:
            raise ValueError(
                f"rehearsal {index} has missing or failed steps: {', '.join(missing)}"
            )
        if not isinstance(run.get("notes"), str):
            raise TypeError(f"rehearsal {index} notes must be a string")

    return {
        "schema_version": 1,
        "status": "PASS",
        "source_commit": source_commit,
        "run_count": 2,
        "durations_seconds": durations,
        "required_steps": list(REQUIRED_STEPS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    data = json.loads(args.record.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("rehearsal record must be a JSON object")
    result = validate_rehearsals(data, source_commit=args.source_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
