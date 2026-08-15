#!/usr/bin/env python3
"""Measure real local embedding, 10k Chroma query, search latency and RSS."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from typing import Any, Callable

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ.get("WEEK6_SOURCE_REPOSITORY", DEFAULT_ROOT)).resolve()
BACKEND_SOURCE = Path(
    os.environ.get("WEEK6_BACKEND_SOURCE", ROOT / "backend" / "src")
).resolve()
for path in (ROOT, BACKEND_SOURCE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tools.week6.run_stress import (  # noqa: E402
    _normalized_vector,
    _sha,
    current_process_peak_rss,
    dataset_manifest_hash,
    percentile,
    write_json_atomic,
)


def _measure(call: Callable[[], Any], *, warmups: int, iterations: int) -> list[float]:
    for _ in range(warmups):
        call()
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        call()
        samples.append((time.perf_counter() - started) * 1000)
    return samples


def _hardware() -> dict[str, str]:
    value = "|".join(
        [platform.platform(), platform.machine(), platform.processor(), os.environ.get("PROCESSOR_IDENTIFIER", "")]
    )
    return {
        "fingerprint": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        "description": value,
        "power_mode": os.environ.get("WEEK6_POWER_MODE", "recorded-by-operator:unknown"),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "CONTENT_RETRIEVAL_MODEL_ROOT": str(args.model_root.resolve()),
            "CONTENT_RETRIEVAL_MANIFEST_PATH": str(args.manifest.resolve()),
            "CONTENT_RETRIEVAL_DATA_DIR": str(args.data_dir.resolve()),
        }
    )
    from content_retrieval.domain.models import EmbeddingVector
    from content_retrieval.domain.retrieval import SearchFilters
    from content_retrieval.runtime import build_local_runtime
    from content_retrieval.storage.chroma import ChromaVectorRepository

    accuracy = json.loads(args.accuracy.read_text(encoding="utf-8"))
    runtime = build_local_runtime(
        model_root=args.model_root,
        manifest_path=args.manifest,
        data_dir=args.data_dir,
    )
    rounds: list[dict[str, Any]] = []
    try:
        with ChromaVectorRepository(args.stress_database) as stress_repository:
            if stress_repository.count() < 10_000:
                raise ValueError("stress database must contain at least 10000 records")
            query_vector = EmbeddingVector(
                source_id=_sha("week6-performance-query"),
                file_id=_sha("week6-performance-query-file"),
                model_id="week6-deterministic-stress-v1",
                space_id=f"week6-stress-{args.dimensions}",
                modality="text",
                values=_normalized_vector(args.seed, 0, args.dimensions),
                dimensions=args.dimensions,
                normalized=True,
            )
            for round_index in range(args.rounds):
                text = _measure(
                    lambda: runtime.embedding_service.embed_text_queries(["offline local document retrieval"]),
                    warmups=args.warmups,
                    iterations=args.iterations,
                )
                image = _measure(
                    lambda: runtime.embedding_service.embed_image_queries(["a red apple on white background"]),
                    warmups=args.warmups,
                    iterations=args.iterations,
                )
                vector = _measure(
                    lambda: stress_repository.query(query_vector, limit=10, filters=SearchFilters()),
                    warmups=args.warmups,
                    iterations=args.iterations,
                )
                full = _measure(
                    lambda: runtime.retrieval_service.search(
                        "offline local document retrieval",
                        top_k=10,
                        channels=("keyword", "text_semantic", "image_semantic"),
                    ),
                    warmups=args.warmups,
                    iterations=args.iterations,
                )
                rounds.append(
                    {
                        "round": round_index + 1,
                        "metrics": {
                            "text_embedding_p50_ms": statistics.median(text),
                            "text_embedding_p95_ms": percentile(text, 95),
                            "image_embedding_p50_ms": statistics.median(image),
                            "image_embedding_p95_ms": percentile(image, 95),
                            "embedding_combined_p95_ms": percentile(text + image, 95),
                            "vector_query_p50_ms": statistics.median(vector),
                            "vector_query_p95_ms": percentile(vector, 95),
                            "full_search_p50_ms": statistics.median(full),
                            "full_search_p95_ms": percentile(full, 95),
                            "peak_rss_bytes": current_process_peak_rss(),
                        },
                    }
                )
    finally:
        runtime.close()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    return {
        "schema_version": "1",
        "source_commit": commit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hardware": _hardware(),
        "dataset_sha256": dataset_manifest_hash(seed=args.seed, records=10_000, dimensions=args.dimensions),
        "models_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "configuration": {
            "warmups": args.warmups,
            "iterations": args.iterations,
            "rounds": args.rounds,
            "offline": True,
        },
        "rounds": rounds,
        "accuracy": accuracy,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--stress-database", type=Path, required=True)
    parser.add_argument("--accuracy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--dimensions", type=int, default=32)
    args = parser.parse_args()
    if args.rounds < 3 or args.iterations < 100 or args.warmups < 10:
        parser.error("final evidence requires >=3 rounds, >=100 iterations, and >=10 warmups")
    write_json_atomic(args.output, run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
