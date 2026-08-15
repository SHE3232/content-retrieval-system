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
