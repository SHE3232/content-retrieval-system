from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "benchmark_performance.py"


def test_benchmark_can_target_an_explicit_source_checkout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repository = tmp_path / "baseline"
    backend_source = repository / "backend" / "src"
    backend_source.mkdir(parents=True)
    monkeypatch.setenv("WEEK6_SOURCE_REPOSITORY", str(repository))
    monkeypatch.setenv("WEEK6_BACKEND_SOURCE", str(backend_source))
    spec = importlib.util.spec_from_file_location("week6_benchmark_target_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.ROOT == repository.resolve()
    assert module.BACKEND_SOURCE == backend_source.resolve()


def test_benchmark_builds_a_disclosed_mixed_workload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repository = tmp_path / "candidate"
    backend_source = repository / "backend" / "src"
    backend_source.mkdir(parents=True)
    monkeypatch.setenv("WEEK6_SOURCE_REPOSITORY", str(repository))
    monkeypatch.setenv("WEEK6_BACKEND_SOURCE", str(backend_source))
    spec = importlib.util.spec_from_file_location("week6_benchmark_workload_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, "build_workload")
    workload = module.build_workload(iterations=100, warmups=10, seed=20260814)

    assert workload["mode"] == "mixed-cold-and-cache-hit"
    assert workload["unique_queries"] >= 10
    assert 0.50 <= workload["target_cache_hit_ratio"] <= 0.90
    assert len(workload["text_queries"]) == 100
    assert len(set(workload["text_queries"])) == workload["unique_queries"]
    assert set(workload["warmup_text_queries"]).isdisjoint(workload["text_queries"])
    assert len(workload["vector_seeds"]) == 100


def test_full_catalog_memory_probe_scans_all_records_without_embeddings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repository = tmp_path / "candidate"
    backend_source = repository / "backend" / "src"
    backend_source.mkdir(parents=True)
    monkeypatch.setenv("WEEK6_SOURCE_REPOSITORY", str(repository))
    monkeypatch.setenv("WEEK6_BACKEND_SOURCE", str(backend_source))
    spec = importlib.util.spec_from_file_location("week6_benchmark_memory_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class FakeRepository:
        def count(self) -> int:
            return 10_000

        def list_search_records(self) -> list[int]:
            return list(range(10_000))

    fake = FakeRepository()
    monkeypatch.setattr(module, "current_process_peak_rss", lambda: 123_456)

    assert module.measure_full_catalog_peak_rss(fake) == 123_456
