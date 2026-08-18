from __future__ import annotations

from copy import deepcopy

import pytest

from tools.week6.compare_performance import compare_performance


def _result(multiplier: float = 1.0) -> dict:
    return {
        "source_commit": "a" * 40,
        "hardware": {"fingerprint": "same-machine", "power_mode": "balanced"},
        "dataset_sha256": "b" * 64,
        "models_sha256": "c" * 64,
        "configuration": {
            "workload_sha256": "d" * 64,
            "workload_mode": "mixed-cold-and-cache-hit",
            "unique_queries": 20,
            "target_cache_hit_ratio": 0.8,
            "warmup_inputs_disjoint": True,
        },
        "rounds": [
            {
                "metrics": {
                    "embedding_combined_p95_ms": 100 * multiplier,
                    "vector_query_p95_ms": 100 * multiplier,
                    "embedding_hot_p95_ms": 100 * multiplier,
                    "vector_query_hot_p95_ms": 100 * multiplier,
                    "peak_rss_bytes": 1000 * multiplier,
                    "full_search_p95_ms": 200 * multiplier,
                }
            }
            for _ in range(3)
        ],
        "accuracy": {
            "nq_recall_at_10": 0.8,
            "nq_mrr_at_10": 0.7,
            "nq_ndcg_at_10": 0.75,
            "coco_recall_at_10": 0.6,
            "coco_mrr_at_10": 0.5,
            "coco_ndcg_at_10": 0.55,
        },
    }


def test_three_round_medians_pass_at_five_percent_improvement() -> None:
    result = compare_performance(_result(), _result(0.95))
    assert result["status"] == "PASS"
    assert result["improvements_percent"]["peak_rss_bytes"] == pytest.approx(5.0)
    assert result["improvements_percent"]["embedding_hot_p95_ms"] == pytest.approx(5.0)
    assert result["improvements_percent"]["vector_query_hot_p95_ms"] == pytest.approx(5.0)


def test_hot_cache_improvement_is_separate_from_cold_mixed_latency() -> None:
    baseline = _result()
    candidate = _result()
    for item in candidate["rounds"]:
        item["metrics"]["embedding_hot_p95_ms"] = 90.0
        item["metrics"]["vector_query_hot_p95_ms"] = 90.0
        item["metrics"]["peak_rss_bytes"] = 900.0

    result = compare_performance(baseline, candidate)

    assert result["status"] == "PASS"
    assert result["improvements_percent"]["embedding_combined_p95_ms"] == 0.0
    assert result["improvements_percent"]["vector_query_p95_ms"] == 0.0


@pytest.mark.parametrize("field", ["hardware", "dataset_sha256", "models_sha256"])
def test_comparison_rejects_incomparable_inputs(field: str) -> None:
    candidate = _result(0.9)
    if field == "hardware":
        candidate[field]["fingerprint"] = "other-machine"
    else:
        candidate[field] = "d" * 64
    with pytest.raises(ValueError, match="comparable"):
        compare_performance(_result(), candidate)


def test_comparison_rejects_unknown_power_mode_or_different_workload() -> None:
    baseline = _result()
    candidate = _result(0.9)
    baseline["hardware"]["power_mode"] = "recorded-by-operator:unknown"
    candidate["hardware"]["power_mode"] = "recorded-by-operator:unknown"
    with pytest.raises(ValueError, match="power mode"):
        compare_performance(baseline, candidate)

    baseline = _result()
    candidate = _result(0.9)
    candidate["configuration"]["workload_sha256"] = "e" * 64
    with pytest.raises(ValueError, match="workload"):
        compare_performance(baseline, candidate)


def test_comparison_requires_three_rounds_and_rss() -> None:
    candidate = _result(0.9)
    candidate["rounds"] = candidate["rounds"][:2]
    with pytest.raises(ValueError, match="three rounds"):
        compare_performance(_result(), candidate)
    candidate = _result(0.9)
    del candidate["rounds"][0]["metrics"]["peak_rss_bytes"]
    with pytest.raises(ValueError, match="peak_rss_bytes"):
        compare_performance(_result(), candidate)


def test_less_than_five_percent_or_slow_vector_query_fails() -> None:
    assert compare_performance(_result(), _result(0.951))["status"] == "FAIL"
    candidate = _result(0.9)
    for item in candidate["rounds"]:
        item["metrics"]["vector_query_p95_ms"] = 2000.01
    assert compare_performance(_result(), candidate)["status"] == "FAIL"


def test_accuracy_drop_over_one_point_fails() -> None:
    candidate = _result(0.9)
    candidate["accuracy"]["nq_recall_at_10"] = 0.789
    result = compare_performance(_result(), candidate)
    assert result["status"] == "FAIL"
    assert result["accuracy_checks"]["nq_recall_at_10"]["status"] == "FAIL"


def test_regression_is_reported_as_negative_improvement() -> None:
    result = compare_performance(_result(), _result(1.1))
    assert result["status"] == "FAIL"
    assert result["improvements_percent"]["vector_query_p95_ms"] < 0
