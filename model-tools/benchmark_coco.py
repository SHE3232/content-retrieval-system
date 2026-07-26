from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SOURCE = REPOSITORY_ROOT / "backend" / "src"
if str(BACKEND_SOURCE) not in sys.path:
    sys.path.insert(0, str(BACKEND_SOURCE))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from content_retrieval.embeddings.mobileclip import LocalMobileClipBackend


def normalize_rows(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError("vectors must be two-dimensional")
    if not np.isfinite(array).all():
        raise ValueError("vectors must contain only finite values")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if np.any(norms == 0.0):
        raise ValueError("cannot normalize a zero vector")
    return array / norms


def image_retrieval_metrics(
    scores: np.ndarray,
    target_indices: list[int],
    *,
    cutoffs: tuple[int, ...] = (1, 5, 10),
) -> tuple[dict[str, float], list[int]]:
    matrix = np.asarray(scores, dtype=np.float32)
    if matrix.ndim != 2:
        raise ValueError("scores must be two-dimensional")
    if matrix.shape[0] != len(target_indices):
        raise ValueError("target count does not match score rows")
    if not target_indices:
        raise ValueError("targets must not be empty")
    if any(index < 0 or index >= matrix.shape[1] for index in target_indices):
        raise ValueError("target index is outside the image score columns")

    ranked_indices = np.argsort(-matrix, axis=1, kind="stable")
    ranks = [
        int(np.flatnonzero(row == target)[0]) + 1
        for row, target in zip(ranked_indices, target_indices, strict=True)
    ]
    metrics = {
        f"recall@{cutoff}": sum(rank <= cutoff for rank in ranks) / len(ranks)
        for cutoff in cutoffs
    }
    metrics["median_rank"] = float(np.median(ranks))
    return metrics, ranks


def _load_items(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"items.jsonl:{line_number} is not an object")
            captions = row.get("captions")
            if (
                not isinstance(row.get("file_name"), str)
                or not isinstance(captions, list)
                or not captions
                or not all(isinstance(caption, str) for caption in captions)
            ):
                raise ValueError(
                    f"items.jsonl:{line_number} has an invalid shape"
                )
            rows.append(row)
    return rows


def _encode_in_batches(
    function: Any,
    values: list[Any],
    *,
    batch_size: int,
) -> np.ndarray:
    batches = []
    for start in range(0, len(values), batch_size):
        batches.extend(function(values[start : start + batch_size]))
    return normalize_rows(np.asarray(batches, dtype=np.float32))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate MobileCLIP text-to-image retrieval on COCO."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=REPOSITORY_ROOT / "datasets" / "processed" / "coco",
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "datasets"
            / "raw"
            / "coco"
            / "val2017"
        ),
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=REPOSITORY_ROOT / "models" / "mobileclip" / "mobileclip_s0.pt",
    )
    parser.add_argument(
        "--split",
        choices=["validation", "benchmark"],
        default="benchmark",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "output" / "week3" / "coco-benchmark.json",
    )
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")

    items = _load_items(
        args.dataset_root.resolve(strict=True)
        / args.split
        / "items.jsonl"
    )
    image_root = args.image_dir.resolve(strict=True)
    paths = [
        (image_root / str(item["file_name"])).resolve(strict=True)
        for item in items
    ]
    captions: list[str] = []
    target_indices: list[int] = []
    for image_index, item in enumerate(items):
        for caption in item["captions"]:
            captions.append(caption)
            target_indices.append(image_index)

    backend = LocalMobileClipBackend(
        args.weights,
        model_id="mobileclip-s0-v1",
        space_id="mobileclip-image-text-v1",
    )
    started = time.perf_counter()
    image_embeddings = _encode_in_batches(
        backend.encode_images,
        paths,
        batch_size=args.batch_size,
    )
    text_embeddings = _encode_in_batches(
        backend.encode_texts,
        captions,
        batch_size=args.batch_size,
    )
    scores = text_embeddings @ image_embeddings.T
    metrics, ranks = image_retrieval_metrics(scores, target_indices)
    elapsed_seconds = time.perf_counter() - started
    payload = {
        "schema_version": "1",
        "dataset": "COCO 2017 validation",
        "split": args.split,
        "frozen_test_split": args.split == "benchmark",
        "model_id": "mobileclip-s0-v1",
        "space_id": "mobileclip-image-text-v1",
        "image_count": len(items),
        "caption_query_count": len(captions),
        "dimensions": int(image_embeddings.shape[1]),
        "batch_size": args.batch_size,
        "elapsed_seconds": elapsed_seconds,
        "metrics": metrics,
        "relevant_ranks": ranks,
    }
    destination = args.output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
