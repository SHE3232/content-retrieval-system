from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from content_retrieval.domain.errors import (
    IndexingError,
    RetrievalError,
    StorageError,
)
from content_retrieval.domain.models import EmbeddingVector
from content_retrieval.domain.retrieval import (
    IndexRecord,
    SearchFilters,
    SearchHit,
    SearchResult,
    VectorCandidate,
)


FILE_ID = "a" * 64
SOURCE_ID = "b" * 64
SOURCE_KEY = "c" * 64
MODIFIED_AT = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)


def make_vector(
    *,
    source_id: str = SOURCE_ID,
    file_id: str = FILE_ID,
    modality: str = "text",
    normalized: bool = True,
) -> EmbeddingVector:
    return EmbeddingVector(
        source_id=source_id,
        file_id=file_id,
        model_id="text-test-v1",
        space_id="text-semantic-v1",
        modality=modality,
        values=[1.0, 0.0],
        dimensions=2,
        normalized=normalized,
    )


def make_record(
    tmp_path: Path,
    *,
    source_id: str = SOURCE_ID,
    file_id: str = FILE_ID,
    modality: str = "text",
    vector: EmbeddingVector | None = None,
) -> IndexRecord:
    source_path = tmp_path / ("image.png" if modality == "image" else "notes.txt")
    source_path.write_bytes(b"fixture")
    return IndexRecord(
        record_id=source_id,
        source_id=source_id,
        file_id=file_id,
        source_key=SOURCE_KEY,
        path=source_path,
        name=source_path.name,
        mime_type="image/png" if modality == "image" else "text/plain",
        modality=modality,
        document=source_path.name if modality == "image" else "offline local search",
        vector=vector or make_vector(
            source_id=source_id,
            file_id=file_id,
            modality=modality,
        ),
        modified_at=MODIFIED_AT,
        size_bytes=7,
        paragraph_number=None if modality == "image" else 1,
    )


def test_index_record_exposes_vector_identity(tmp_path: Path) -> None:
    record = make_record(tmp_path)

    assert record.space_id == "text-semantic-v1"
    assert record.model_id == "text-test-v1"
    assert record.dimensions == 2


@pytest.mark.parametrize(
    ("vector", "message"),
    [
        (make_vector(source_id="d" * 64), "source_id"),
        (make_vector(file_id="d" * 64), "file_id"),
        (make_vector(modality="image"), "modality"),
        (make_vector(normalized=False), "normalized"),
    ],
)
def test_index_record_rejects_incompatible_vector(
    tmp_path: Path,
    vector: EmbeddingVector,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        make_record(tmp_path, vector=vector)


def test_index_record_requires_source_locator_for_text(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("notes", encoding="utf-8")

    with pytest.raises(ValueError, match="locator"):
        IndexRecord(
            record_id=SOURCE_ID,
            source_id=SOURCE_ID,
            file_id=FILE_ID,
            source_key=SOURCE_KEY,
            path=path,
            name=path.name,
            mime_type="text/plain",
            modality="text",
            document="notes",
            vector=make_vector(),
            modified_at=MODIFIED_AT,
            size_bytes=5,
        )


def test_search_filters_validate_time_range() -> None:
    later = MODIFIED_AT + timedelta(days=1)

    with pytest.raises(ValueError, match="modified"):
        SearchFilters(modified_after=later, modified_before=MODIFIED_AT)


def test_search_filters_reject_blank_values_and_invalid_modalities() -> None:
    with pytest.raises(ValueError, match="mime"):
        SearchFilters(mime_types=("text/plain", " "))

    with pytest.raises(ValueError, match="modality"):
        SearchFilters(modalities=("audio",))


def test_vector_candidate_requires_finite_similarity(tmp_path: Path) -> None:
    record = make_record(tmp_path)

    with pytest.raises(ValueError, match="score"):
        VectorCandidate(record=record, score=float("nan"))


@pytest.mark.parametrize(
    ("error_type", "code", "stage", "retryable"),
    [
        (StorageError, "STORAGE_ERROR", "storage", True),
        (IndexingError, "INDEXING_ERROR", "indexing", False),
        (RetrievalError, "RETRIEVAL_ERROR", "retrieval", False),
    ],
)
def test_week4_errors_have_stable_diagnostics(
    error_type: type[Exception],
    code: str,
    stage: str,
    retryable: bool,
) -> None:
    error = error_type("controlled failure", file_id=FILE_ID)

    assert error.to_dict() == {
        "code": code,
        "message": "controlled failure",
        "retryable": retryable,
        "stage": stage,
        "file_id": FILE_ID,
        "chunk_id": None,
    }


def test_search_result_requires_ranked_bounded_hits(tmp_path: Path) -> None:
    record = make_record(tmp_path)
    hit = SearchHit(
        file_id=record.file_id,
        source_id=record.source_id,
        path=record.path,
        name=record.name,
        mime_type=record.mime_type,
        modality=record.modality,
        score=0.8,
        match_reasons=("text_semantic",),
        snippet=record.document,
        page_number=None,
        paragraph_number=1,
    )
    result = SearchResult(
        query="local search",
        hits=(hit,),
        total_candidates=1,
        elapsed_ms=2.5,
        weights={"text_semantic": 1.0},
    )

    assert result.hits == (hit,)

    with pytest.raises(ValueError, match="score"):
        SearchHit(
            file_id=record.file_id,
            source_id=record.source_id,
            path=record.path,
            name=record.name,
            mime_type=record.mime_type,
            modality=record.modality,
            score=1.1,
            match_reasons=("text_semantic",),
            snippet=record.document,
            page_number=None,
            paragraph_number=1,
        )
