#!/usr/bin/env python3
"""Strictly compare three-round Week 6 performance evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
from typing import Any

REQUIRED_METRICS = (
    "embedding_combined_p95_ms",
    "vector_query_p95_ms",
    "embedding_hot_p95_ms",
    "vector_query_hot_p95_ms",
    "peak_rss_bytes",
    "full_search_p95_ms",
)
IMPROVEMENT_METRICS = (
    "embedding_hot_p95_ms",
    "vector_query_hot_p95_ms",
    "peak_rss_bytes",
)
ACCURACY_METRICS = (
    "nq_recall_at_10",
    "nq_mrr_at_10",
    "nq_ndcg_at_10",
    "coco_recall_at_10",
    "coco_mrr_at_10",
    "coco_ndcg_at_10",
)


def _medians(value: dict[str, Any]) -> dict[str, float]:
    rounds = value.get("rounds")
    if not isinstance(rounds, list) or len(rounds) < 3:
        raise ValueError("performance evidence requires at least three rounds")
    medians: dict[str, float] = {}
    for name in REQUIRED_METRICS:
        samples: list[float] = []
        for index, item in enumerate(rounds):
            metrics = item.get("metrics") if isinstance(item, dict) else None
            sample = metrics.get(name) if isinstance(metrics, dict) else None
            if not isinstance(sample, (int, float)) or sample <= 0:
                raise ValueError(f"round {index + 1} requires positive {name}")
            samples.append(float(sample))
        medians[name] = statistics.median(samples)
    return medians


def _require_comparable(baseline: dict[str, Any], candidate: dict[str, Any]) -> None:
    baseline_hardware = baseline.get("hardware")
    candidate_hardware = candidate.get("hardware")
    if not isinstance(baseline_hardware, dict) or not isinstance(candidate_hardware, dict):
        raise ValueError("hardware evidence is required for comparable runs")
    baseline_power = baseline_hardware.get("power_mode")
    candidate_power = candidate_hardware.get("power_mode")
    if not isinstance(baseline_power, str) or not baseline_power.strip() or "unknown" in baseline_power.lower():
        raise ValueError("recorded non-unknown power mode is required")
    if not isinstance(candidate_power, str) or not candidate_power.strip() or "unknown" in candidate_power.lower():
        raise ValueError("recorded non-unknown power mode is required")

    baseline_configuration = baseline.get("configuration")
    candidate_configuration = candidate.get("configuration")
    if not isinstance(baseline_configuration, dict) or not isinstance(candidate_configuration, dict):
        raise ValueError("comparable workload configuration is required")
    workload_fields = (
        "workload_sha256",
        "workload_mode",
        "unique_queries",
        "target_cache_hit_ratio",
        "warmup_inputs_disjoint",
    )
    if any(
        baseline_configuration.get(field) != candidate_configuration.get(field)
        for field in workload_fields
    ):
        raise ValueError("baseline and candidate workload are not comparable")
    if baseline_configuration.get("workload_mode") != "mixed-cold-and-cache-hit":
        raise ValueError("mixed cold and cache-hit workload is required")
    if baseline_configuration.get("warmup_inputs_disjoint") is not True:
        raise ValueError("workload warmup inputs must be disjoint")

    comparable = (
        baseline_hardware.get("fingerprint") == candidate_hardware.get("fingerprint")
        and baseline_power == candidate_power
        and baseline.get("dataset_sha256") == candidate.get("dataset_sha256")
        and baseline.get("models_sha256") == candidate.get("models_sha256")
    )
    if not comparable:
        raise ValueError("baseline and candidate are not comparable")


def compare_performance(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    _require_comparable(baseline, candidate)
    baseline_medians = _medians(baseline)
    candidate_medians = _medians(candidate)
    improvements = {
        name: (baseline_medians[name] - candidate_medians[name]) / baseline_medians[name] * 100
        for name in REQUIRED_METRICS
    }
    checks: list[dict[str, Any]] = []
    for name in IMPROVEMENT_METRICS:
        checks.append(
            {
                "id": f"improvement:{name}",
                "status": "PASS" if improvements[name] >= 5.0 else "FAIL",
                "actual_percent": improvements[name],
                "expected": ">= 5.0%",
            }
        )
    checks.append(
        {
            "id": "vector_query_p95_limit",
            "status": "PASS" if candidate_medians["vector_query_p95_ms"] <= 2000 else "FAIL",
            "actual_ms": candidate_medians["vector_query_p95_ms"],
            "expected": "<= 2000 ms",
        }
    )
    checks.append(
        {
            "id": "mixed_embedding_no_regression",
            "status": "PASS" if improvements["embedding_combined_p95_ms"] >= -5.0 else "FAIL",
            "actual_percent": improvements["embedding_combined_p95_ms"],
            "expected": ">= -5.0%",
        }
    )
    checks.append(
        {
            "id": "mixed_vector_no_regression",
            "status": "PASS" if improvements["vector_query_p95_ms"] >= -5.0 else "FAIL",
            "actual_percent": improvements["vector_query_p95_ms"],
            "expected": ">= -5.0%",
        }
    )
    checks.append(
        {
            "id": "full_search_no_regression",
            "status": "PASS" if improvements["full_search_p95_ms"] >= -5.0 else "FAIL",
            "actual_percent": improvements["full_search_p95_ms"],
            "expected": ">= -5.0%",
        }
    )
    baseline_accuracy = baseline.get("accuracy")
    candidate_accuracy = candidate.get("accuracy")
    if not isinstance(baseline_accuracy, dict) or not isinstance(candidate_accuracy, dict):
        raise ValueError("accuracy evidence is required")
    accuracy_checks: dict[str, dict[str, Any]] = {}
    for name in ACCURACY_METRICS:
        before = baseline_accuracy.get(name)
        after = candidate_accuracy.get(name)
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            raise ValueError(f"accuracy metric is required: {name}")
        drop = float(before) - float(after)
        status = "PASS" if drop <= 0.01 + 1e-12 else "FAIL"
        accuracy_checks[name] = {
            "status": status,
            "baseline": float(before),
            "candidate": float(after),
            "drop": drop,
            "maximum_drop": 0.01,
        }
        checks.append({"id": f"accuracy:{name}", "status": status, "drop": drop})
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "status": status,
        "baseline_commit": baseline.get("source_commit"),
        "candidate_commit": candidate.get("source_commit"),
        "baseline_medians": baseline_medians,
        "candidate_medians": candidate_medians,
        "improvements_percent": improvements,
        "workload": {
            field: baseline["configuration"].get(field)
            for field in (
                "workload_sha256",
                "workload_mode",
                "unique_queries",
                "target_cache_hit_ratio",
                "warmup_inputs_disjoint",
            )
        },
        "accuracy_checks": accuracy_checks,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    result = compare_performance(baseline, candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
