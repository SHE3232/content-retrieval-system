from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def compare_outputs(
    reference: np.ndarray,
    converted: np.ndarray,
) -> dict[str, float | int]:
    """Compare two model outputs without hiding shape or numeric failures."""
    left = np.asarray(reference, dtype=np.float64)
    right = np.asarray(converted, dtype=np.float64)
    if left.shape != right.shape:
        raise ValueError("reference and converted outputs must have the same shape")
    if left.size == 0:
        raise ValueError("outputs must not be empty")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("outputs must contain only finite values")

    left_flat = left.ravel()
    right_flat = right.ravel()
    left_norm = float(np.linalg.norm(left_flat))
    right_norm = float(np.linalg.norm(right_flat))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("outputs must have non-zero norms")

    difference = np.abs(left - right)
    cosine = float(
        np.dot(left_flat, right_flat) / (left_norm * right_norm)
    )
    return {
        "cosine_similarity": max(-1.0, min(1.0, cosine)),
        "max_absolute_error": float(difference.max()),
        "mean_absolute_error": float(difference.mean()),
        "element_count": int(left.size),
    }


def write_parity_report(
    *,
    output_path: Path,
    model_id: str,
    source_runtime: str,
    converted_runtime: str,
    reference: np.ndarray,
    converted: np.ndarray,
    min_cosine: float = 0.999,
    max_absolute_error: float = 1e-4,
    artifacts: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not model_id.strip():
        raise ValueError("model_id must not be blank")
    if not 0.0 <= min_cosine <= 1.0:
        raise ValueError("min_cosine must be between zero and one")
    if max_absolute_error < 0.0:
        raise ValueError("max_absolute_error must be non-negative")

    metrics = compare_outputs(reference, converted)
    passed = (
        metrics["cosine_similarity"] >= min_cosine
        and metrics["max_absolute_error"] <= max_absolute_error
    )
    payload: dict[str, Any] = {
        "schema_version": "1",
        "model_id": model_id,
        "source_runtime": source_runtime,
        "converted_runtime": converted_runtime,
        "passed": bool(passed),
        "metrics": metrics,
        "thresholds": {
            "min_cosine_similarity": min_cosine,
            "max_absolute_error": max_absolute_error,
        },
        "artifacts": artifacts or {},
    }

    destination = output_path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare NumPy reference and LiteRT output arrays."
    )
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--converted", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--source-runtime", default="pytorch")
    parser.add_argument("--converted-runtime", default="litert")
    parser.add_argument("--min-cosine", type=float, default=0.999)
    parser.add_argument("--max-absolute-error", type=float, default=1e-4)
    args = parser.parse_args()

    payload = write_parity_report(
        output_path=args.output,
        model_id=args.model_id,
        source_runtime=args.source_runtime,
        converted_runtime=args.converted_runtime,
        reference=np.load(args.reference, allow_pickle=False),
        converted=np.load(args.converted, allow_pickle=False),
        min_cosine=args.min_cosine,
        max_absolute_error=args.max_absolute_error,
        artifacts={
            "reference_output": str(args.reference),
            "converted_output": str(args.converted),
        },
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
