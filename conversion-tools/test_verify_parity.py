from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_parity import compare_outputs, write_parity_report


def test_compare_outputs_reports_cosine_and_absolute_errors() -> None:
    reference = np.asarray([[1.0, 2.0, 3.0]], dtype=np.float32)
    converted = np.asarray([[1.0, 2.00001, 2.99999]], dtype=np.float32)

    report = compare_outputs(reference, converted)

    assert report["cosine_similarity"] >= 0.999
    assert report["max_absolute_error"] <= 1.1e-5
    assert report["mean_absolute_error"] > 0.0
    assert report["element_count"] == 3


def test_compare_outputs_rejects_shape_mismatch_and_zero_vectors() -> None:
    with pytest.raises(ValueError, match="same shape"):
        compare_outputs(np.ones((1, 2)), np.ones((2, 1)))

    with pytest.raises(ValueError, match="non-zero norms"):
        compare_outputs(np.zeros((2,)), np.ones((2,)))


def test_write_parity_report_records_threshold_status(tmp_path: Path) -> None:
    output = tmp_path / "reports" / "parity.json"

    payload = write_parity_report(
        output_path=output,
        model_id="tiny-test-v1",
        source_runtime="pytorch",
        converted_runtime="litert",
        reference=np.asarray([1.0, 0.0]),
        converted=np.asarray([0.999999, 0.000001]),
        min_cosine=0.999,
        max_absolute_error=1e-4,
        artifacts={"converted_model": "models/tiny.tflite"},
    )

    saved = json.loads(output.read_text(encoding="utf-8"))
    assert payload == saved
    assert saved["schema_version"] == "1"
    assert saved["model_id"] == "tiny-test-v1"
    assert saved["passed"] is True
    assert saved["thresholds"] == {
        "min_cosine_similarity": 0.999,
        "max_absolute_error": 0.0001,
    }
    assert saved["artifacts"]["converted_model"] == "models/tiny.tflite"


def test_write_parity_report_marks_failed_threshold(tmp_path: Path) -> None:
    payload = write_parity_report(
        output_path=tmp_path / "parity.json",
        model_id="bad-test-v1",
        source_runtime="pytorch",
        converted_runtime="litert",
        reference=np.asarray([1.0, 0.0]),
        converted=np.asarray([0.8, 0.6]),
        min_cosine=0.999,
        max_absolute_error=1e-4,
    )

    assert payload["passed"] is False
