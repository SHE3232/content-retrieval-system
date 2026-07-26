from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_coco import image_retrieval_metrics, normalize_rows


def test_image_retrieval_metrics_compute_recall_and_median_rank() -> None:
    scores = np.asarray(
        [
            [0.9, 0.1, 0.0],
            [0.8, 0.7, 0.1],
            [0.2, 0.3, 0.9],
        ]
    )

    metrics, ranks = image_retrieval_metrics(
        scores,
        target_indices=[0, 1, 1],
        cutoffs=(1, 2, 3),
    )

    assert ranks == [1, 2, 2]
    assert metrics["recall@1"] == pytest.approx(1 / 3)
    assert metrics["recall@2"] == pytest.approx(1.0)
    assert metrics["recall@3"] == pytest.approx(1.0)
    assert metrics["median_rank"] == 2.0


def test_image_retrieval_metrics_validate_inputs() -> None:
    with pytest.raises(ValueError, match="two-dimensional"):
        image_retrieval_metrics(np.ones(3), [0])
    with pytest.raises(ValueError, match="target count"):
        image_retrieval_metrics(np.ones((2, 2)), [0])
    with pytest.raises(ValueError, match="outside"):
        image_retrieval_metrics(np.ones((1, 2)), [2])


def test_normalize_rows_rejects_zero_vectors() -> None:
    normalized = normalize_rows(np.asarray([[3.0, 4.0]]))
    np.testing.assert_allclose(normalized, [[0.6, 0.8]])

    with pytest.raises(ValueError, match="zero"):
        normalize_rows(np.asarray([[0.0, 0.0]]))
