import hashlib
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("benchmark_week4_pipeline.py")


def load_module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_week4_pipeline",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retrieval_metrics_include_rank_sensitive_measures() -> None:
    benchmark = load_module()

    metrics = benchmark.retrieval_metrics(
        {
            "q1": ["d1", "x1", "x2"],
            "q2": ["x3", "d2", "x4"],
        },
        {
            "q1": {"d1"},
            "q2": {"d2"},
        },
    )

    assert metrics["recall@1"] == pytest.approx(0.5)
    assert metrics["recall@5"] == pytest.approx(1.0)
    assert metrics["recall@10"] == pytest.approx(1.0)
    assert metrics["mrr@10"] == pytest.approx(0.75)
    assert metrics["ndcg@10"] == pytest.approx(
        (1.0 + 1.0 / benchmark.math.log2(3)) / 2
    )
    assert metrics["median_rank"] == pytest.approx(1.5)


def test_latency_summary_uses_linear_percentiles() -> None:
    benchmark = load_module()

    summary = benchmark.latency_summary([float(value) for value in range(1, 101)])

    assert summary == {
        "query_count": 100,
        "p50_ms": pytest.approx(50.5),
        "p95_ms": pytest.approx(95.05),
        "max_ms": 100.0,
    }


def test_source_hashes_are_content_derived(tmp_path: Path) -> None:
    benchmark = load_module()
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.tsv"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    hashes = benchmark.source_hashes([first, second])

    assert hashes == {
        "first.jsonl": {
            "bytes": 5,
            "sha256": hashlib.sha256(b"first").hexdigest(),
        },
        "second.tsv": {
            "bytes": 6,
            "sha256": hashlib.sha256(b"second").hexdigest(),
        },
    }


def test_normalize_rows_rejects_zero_vectors() -> None:
    benchmark = load_module()

    with pytest.raises(ValueError, match="zero vector"):
        benchmark.normalize_rows([[0.0, 0.0]])
