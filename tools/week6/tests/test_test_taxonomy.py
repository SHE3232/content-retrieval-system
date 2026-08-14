from __future__ import annotations

from tools.week6.test_taxonomy import classify_nodeid


def test_ordinary_backend_test_is_unit() -> None:
    assert classify_nodeid("tests/test_retrieval_service.py::test_search") == {
        "unit"
    }


def test_week4_end_to_end_test_is_e2e() -> None:
    assert classify_nodeid("tests/test_week4_e2e.py::test_pipeline") == {
        "e2e"
    }


def test_mvp_http_smoke_is_e2e() -> None:
    assert classify_nodeid("tests/test_mvp_smoke.py::test_smoke") == {
        "e2e"
    }


def test_launcher_process_tests_are_integration() -> None:
    assert classify_nodeid("tests/test_mvp_launcher.py::test_preflight") == {
        "integration"
    }


def test_real_tika_test_is_integration_and_requires_tika() -> None:
    assert classify_nodeid(
        "tests/test_docx_image_parsers.py::test_real_tika_extracts_a_generated_docx"
    ) == {"integration", "requires_tika"}


def test_every_classification_has_exactly_one_primary_layer() -> None:
    primary = {"unit", "integration", "e2e", "stress"}
    examples = (
        "tests/test_api.py::test_health",
        "tests/test_mvp_launcher.py::test_preflight",
        "tests/test_week4_e2e.py::test_pipeline",
    )

    for nodeid in examples:
        assert len(classify_nodeid(nodeid) & primary) == 1
