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
import random
import statistics
import subprocess
import sys
import time
from typing import Any, Callable, Hashable, Sequence

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


def build_workload(*, iterations: int, warmups: int, seed: int) -> dict[str, Any]:
    if iterations < 10:
        raise ValueError("mixed workload requires at least 10 iterations")
    unique_queries = min(20, max(10, iterations // 5))
    rng = random.Random(seed)
    indexes = [index % unique_queries for index in range(iterations)]
    rng.shuffle(indexes)
    text_pool = [f"offline local document retrieval topic {index}" for index in range(unique_queries)]
    image_pool = [f"consumer photo description {index}" for index in range(unique_queries)]
    full_pool = [f"mixed local search request {index}" for index in range(unique_queries)]
    workload = {
        "mode": "mixed-cold-and-cache-hit",
        "unique_queries": unique_queries,
        "target_cache_hit_ratio": 1.0 - unique_queries / iterations,
        "warmup_inputs_disjoint": True,
        "warmup_text_queries": [f"warmup text query {seed}-{index}" for index in range(warmups)],
        "warmup_image_queries": [f"warmup image query {seed}-{index}" for index in range(warmups)],
        "warmup_vector_seeds": [seed + 1_000_000 + index for index in range(warmups)],
        "warmup_full_search_queries": [f"warmup full search {seed}-{index}" for index in range(warmups)],
        "text_queries": [text_pool[index] for index in indexes],
        "image_queries": [image_pool[index] for index in indexes],
        "vector_seeds": [seed + index for index in indexes],
        "full_search_queries": [full_pool[index] for index in indexes],
    }
    return workload


def _measure_sequence(
    call: Callable[[Any], Any],
    *,
    warmup_inputs: Sequence[Any],
    inputs: Sequence[Any],
) -> dict[str, list[float]]:
    for value in warmup_inputs:
        call(value)
    samples: list[float] = []
    cold_samples: list[float] = []
    hot_samples: list[float] = []
    seen: set[Hashable] = set()
    for value in inputs:
        started = time.perf_counter()
        call(value)
        elapsed = (time.perf_counter() - started) * 1000
        samples.append(elapsed)
        key = value if isinstance(value, Hashable) else repr(value)
        if key in seen:
            hot_samples.append(elapsed)
        else:
            cold_samples.append(elapsed)
            seen.add(key)
    return {"all": samples, "cold": cold_samples, "hot": hot_samples}


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
            base_workload = build_workload(
                iterations=args.iterations,
                warmups=args.warmups,
                seed=args.seed,
            )

            def vector_for(seed_value: int) -> EmbeddingVector:
                return EmbeddingVector(
                    source_id=_sha(f"week6-performance-query-{seed_value}"),
                    file_id=_sha(f"week6-performance-query-file-{seed_value}"),
                    model_id="week6-deterministic-stress-v1",
                    space_id=f"week6-stress-{args.dimensions}",
                    modality="text",
                    values=_normalized_vector(seed_value, 0, args.dimensions),
                    dimensions=args.dimensions,
                    normalized=True,
                )

            for round_index in range(args.rounds):
                round_tag = f" round-{round_index + 1}"
                text_inputs = [value + round_tag for value in base_workload["text_queries"]]
                image_inputs = [value + round_tag for value in base_workload["image_queries"]]
                full_inputs = [value + round_tag for value in base_workload["full_search_queries"]]
                warmup_text = [value + round_tag for value in base_workload["warmup_text_queries"]]
                warmup_image = [value + round_tag for value in base_workload["warmup_image_queries"]]
                warmup_full = [value + round_tag for value in base_workload["warmup_full_search_queries"]]
                vector_offset = round_index * 10_000_000
                vector_inputs = [
                    vector_for(int(value) + vector_offset)
                    for value in base_workload["vector_seeds"]
                ]
                warmup_vectors = [
                    vector_for(int(value) + vector_offset)
                    for value in base_workload["warmup_vector_seeds"]
                ]
                text = _measure_sequence(
                    lambda value: runtime.embedding_service.embed_text_queries([value]),
                    warmup_inputs=warmup_text,
                    inputs=text_inputs,
                )
                image = _measure_sequence(
                    lambda value: runtime.embedding_service.embed_image_queries([value]),
                    warmup_inputs=warmup_image,
                    inputs=image_inputs,
                )
                vector = _measure_sequence(
                    lambda value: stress_repository.query(value, limit=10, filters=SearchFilters()),
                    warmup_inputs=warmup_vectors,
                    inputs=vector_inputs,
                )
                full = _measure_sequence(
                    lambda value: runtime.retrieval_service.search(
                        value,
                        top_k=10,
                        channels=("keyword", "text_semantic", "image_semantic"),
                    ),
                    warmup_inputs=warmup_full,
                    inputs=full_inputs,
                )
                rounds.append(
                    {
                        "round": round_index + 1,
                        "metrics": {
                            "text_embedding_p50_ms": statistics.median(text["all"]),
                            "text_embedding_p95_ms": percentile(text["all"], 95),
                            "image_embedding_p50_ms": statistics.median(image["all"]),
                            "image_embedding_p95_ms": percentile(image["all"], 95),
                            "embedding_combined_p95_ms": percentile(text["all"] + image["all"], 95),
                            "embedding_cold_p95_ms": percentile(text["cold"] + image["cold"], 95),
                            "embedding_hot_p95_ms": percentile(text["hot"] + image["hot"], 95),
                            "vector_query_p50_ms": statistics.median(vector["all"]),
                            "vector_query_p95_ms": percentile(vector["all"], 95),
                            "vector_query_cold_p95_ms": percentile(vector["cold"], 95),
                            "vector_query_hot_p95_ms": percentile(vector["hot"], 95),
                            "full_search_p50_ms": statistics.median(full["all"]),
                            "full_search_p95_ms": percentile(full["all"], 95),
                            "peak_rss_bytes": current_process_peak_rss(),
                        },
                    }
                )
    finally:
        runtime.close()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    workload_payload = {
        key: value
        for key, value in base_workload.items()
        if key not in {"warmup_text_queries", "warmup_image_queries", "warmup_vector_seeds", "warmup_full_search_queries"}
    }
    workload_sha256 = hashlib.sha256(
        json.dumps(workload_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
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
            "workload_sha256": workload_sha256,
            "workload_mode": base_workload["mode"],
            "unique_queries": base_workload["unique_queries"],
            "target_cache_hit_ratio": base_workload["target_cache_hit_ratio"],
            "warmup_inputs_disjoint": base_workload["warmup_inputs_disjoint"],
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
