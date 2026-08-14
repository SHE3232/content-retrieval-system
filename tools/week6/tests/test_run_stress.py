from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.week6.run_stress import (
    assess_stress,
    current_process_rss,
    dataset_manifest_hash,
    percentile,
    write_json_atomic,
)


def test_current_process_rss_is_positive() -> None:
    assert current_process_rss() > 0


def test_percentile_uses_linear_interpolation() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 95) == pytest.approx(3.85)


def test_dataset_hash_is_stable_and_sensitive() -> None:
    first = dataset_manifest_hash(seed=20260814, records=10_000, dimensions=32)
    second = dataset_manifest_hash(seed=20260814, records=10_000, dimensions=32)
    changed = dataset_manifest_hash(seed=20260815, records=10_000, dimensions=32)
    assert first == second
    assert first != changed
    assert len(first) == 64


def test_assess_stress_requires_all_acceptance_limits() -> None:
    result = assess_stress(
        record_count=10_000,
        requested_queries=500,
        completed_queries=500,
        soak_seconds=1800,
        query_p95_ms=120.0,
        first_window_rss_median=100.0,
        last_window_rss_median=109.9,
        crashes=0,
        deadlocks=0,
        unhandled_exceptions=0,
        malformed_responses=0,
    )
    assert result["status"] == "PASS"
    assert all(check["status"] == "PASS" for check in result["checks"])


@pytest.mark.parametrize(
    ("override", "check_id"),
    [
        ({"record_count": 9_999}, "record_count"),
        ({"completed_queries": 499}, "query_count"),
        ({"soak_seconds": 1799}, "soak_duration"),
        ({"query_p95_ms": 2000.01}, "query_p95"),
        ({"last_window_rss_median": 110.01}, "rss_growth"),
        ({"crashes": 1}, "process_stability"),
        ({"deadlocks": 1}, "process_stability"),
        ({"unhandled_exceptions": 1}, "exception_count"),
        ({"malformed_responses": 1}, "response_shape"),
    ],
)
def test_assess_stress_fails_each_broken_gate(override: dict[str, float], check_id: str) -> None:
    values: dict[str, float | int] = {
        "record_count": 10_000,
        "requested_queries": 500,
        "completed_queries": 500,
        "soak_seconds": 1800,
        "query_p95_ms": 120.0,
        "first_window_rss_median": 100.0,
        "last_window_rss_median": 110.0,
        "crashes": 0,
        "deadlocks": 0,
        "unhandled_exceptions": 0,
        "malformed_responses": 0,
    }
    values.update(override)
    result = assess_stress(**values)
    assert result["status"] == "FAIL"
    failed = {check["id"] for check in result["checks"] if check["status"] == "FAIL"}
    assert check_id in failed


def test_atomic_writer_replaces_complete_json(tmp_path: Path) -> None:
    output = tmp_path / "summary.json"
    write_json_atomic(output, {"status": "PASS", "count": 500})
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "status": "PASS",
        "count": 500,
    }
    assert list(tmp_path.glob("*.tmp")) == []
