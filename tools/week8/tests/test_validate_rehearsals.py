from __future__ import annotations

import copy

import pytest
from validate_rehearsals import REQUIRED_STEPS, validate_rehearsals

COMMIT = "a" * 40


def _record() -> dict[str, object]:
    runs = []
    for index in range(2):
        runs.append(
            {
                "recorded_at": f"2026-08-2{7 + index}T19:30:00+08:00",
                "duration_seconds": 300 + index,
                "environment": {
                    "os": "Windows 11",
                    "app_artifact_sha256": str(index + 1) * 64,
                    "operator": "course owner",
                },
                "steps": {step: "PASS" for step in REQUIRED_STEPS},
                "notes": "",
            }
        )
    return {"source_commit": COMMIT, "runs": runs}


def test_accepts_two_complete_rehearsals() -> None:
    result = validate_rehearsals(_record(), source_commit=COMMIT)
    assert result["status"] == "PASS"
    assert result["run_count"] == 2


@pytest.mark.parametrize("count", [0, 1, 3])
def test_rejects_wrong_run_count(count: int) -> None:
    record = _record()
    record["runs"] = record["runs"][:count] if count < 2 else record["runs"] + [record["runs"][0]]
    with pytest.raises(ValueError, match="exactly two"):
        validate_rehearsals(record, source_commit=COMMIT)


def test_rejects_failed_required_step() -> None:
    record = copy.deepcopy(_record())
    record["runs"][1]["steps"]["screen_reader"] = "BLOCKED"
    with pytest.raises(ValueError, match="screen_reader"):
        validate_rehearsals(record, source_commit=COMMIT)


def test_rejects_unbound_commit() -> None:
    with pytest.raises(ValueError, match="differs"):
        validate_rehearsals(_record(), source_commit="b" * 40)
