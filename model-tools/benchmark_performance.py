from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import time
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def _model_size(path: Path) -> int:
    return sum(
        file.stat().st_size
        for file in path.rglob("*")
        if file.is_file() and ".cache" not in file.parts
    )


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = max(
        0,
        min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))),
    )
    return ordered[position]


def benchmark_batch(
    model: Any,
    *,
    batch_size: int,
    iterations: int,
    warmups: int,
) -> dict[str, float | int]:
    texts = [
        f"offline multimodal retrieval benchmark sample {index}"
        for index in range(batch_size)
    ]
    for _ in range(warmups):
        model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    durations: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        durations.append(time.perf_counter() - started)
    total_items = batch_size * iterations
    total_seconds = sum(durations)
    return {
        "batch_size": batch_size,
        "iterations": iterations,
        "p50_latency_ms": statistics.median(durations) * 1000.0,
        "p95_latency_ms": _percentile(durations, 0.95) * 1000.0,
        "throughput_items_per_second": total_items / total_seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure local text embedding latency and throughput."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "models"
            / "text"
            / "text-multilingual-v1"
        ),
    )
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "output"
            / "week3"
            / "text-performance.json"
        ),
    )
    args = parser.parse_args()
    if args.iterations <= 0 or args.warmups < 0:
        parser.error("iterations must be positive and warmups non-negative")

    from sentence_transformers import SentenceTransformer

    model_path = args.model.resolve(strict=True)
    model = SentenceTransformer(
        str(model_path),
        device="cpu",
        local_files_only=True,
    )
    payload = {
        "schema_version": "1",
        "model_id": "text-multilingual-v1",
        "space_id": "text-semantic-v1",
        "model_size_bytes": _model_size(model_path),
        "device": {
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
            "python": platform.python_version(),
        },
        "measurements": [
            benchmark_batch(
                model,
                batch_size=batch_size,
                iterations=args.iterations,
                warmups=args.warmups,
            )
            for batch_size in (1, 16)
        ],
    }
    destination = args.output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
