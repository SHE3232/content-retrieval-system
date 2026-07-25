from dataclasses import fields
from datetime import datetime, timezone
import importlib
from pathlib import Path

import pytest

from content_retrieval.domain import errors as domain_errors
from content_retrieval.domain import models as domain_models
from content_retrieval.domain.models import ParseResult


FILE_ID = "a" * 64
MODIFIED_AT = datetime(2026, 7, 25, tzinfo=timezone.utc)


def make_document(
    path: Path,
    *,
    text: str | None,
    mime_type: str = "text/plain",
    modality: str = "text",
    page_count: int | None = None,
    metadata: dict[str, object] | None = None,
    file_id: str = FILE_ID,
) -> ParseResult:
    return ParseResult(
        file_id=file_id,
        path=path,
        name=path.name,
        mime_type=mime_type,
        modality=modality,
        size_bytes=len((text or "").encode("utf-8")),
        modified_at=MODIFIED_AT,
        text=text,
        page_count=page_count,
        metadata=metadata or {},
    )


def chunking_contracts() -> tuple[type, type, type, type, type, type]:
    return (
        getattr(domain_models, "TextChunk"),
        getattr(domain_models, "EmbeddingVector"),
        getattr(domain_models, "BatchProcessingResult"),
        getattr(domain_errors, "ProcessingError"),
        getattr(domain_errors, "ChunkingError"),
        getattr(domain_errors, "EmbeddingError"),
    )


def text_chunker_type() -> type:
    module = importlib.import_module("content_retrieval.services.chunking")
    return getattr(module, "TextChunker")


def test_p0_exposes_the_frozen_processing_contracts() -> None:
    (
        text_chunk,
        embedding_vector,
        batch_result,
        processing_error,
        chunking_error,
        embedding_error,
    ) = chunking_contracts()

    assert [field.name for field in fields(text_chunk)] == [
        "chunk_id",
        "file_id",
        "text",
        "sequence_number",
        "page_number",
        "paragraph_number",
        "split_number",
        "metadata",
        "schema_version",
    ]
    assert [field.name for field in fields(embedding_vector)] == [
        "source_id",
        "file_id",
        "model_id",
        "space_id",
        "modality",
        "values",
        "dimensions",
        "normalized",
        "metadata",
        "schema_version",
    ]
    assert [field.name for field in fields(batch_result)] == ["items", "errors"]
    assert issubclass(chunking_error, processing_error)
    assert issubclass(embedding_error, processing_error)


def test_text_chunk_requires_one_valid_source_locator() -> None:
    TextChunk, *_ = chunking_contracts()

    page_chunk = TextChunk(
        chunk_id="b" * 64,
        file_id=FILE_ID,
        text="page text",
        sequence_number=0,
        page_number=1,
    )
    paragraph_chunk = TextChunk(
        chunk_id="c" * 64,
        file_id=FILE_ID,
        text="paragraph text",
        sequence_number=1,
        paragraph_number=2,
    )

    assert page_chunk.page_number == 1
    assert page_chunk.paragraph_number is None
    assert paragraph_chunk.page_number is None
    assert paragraph_chunk.paragraph_number == 2
    with pytest.raises(ValueError, match="exactly one"):
        TextChunk(
            chunk_id="d" * 64,
            file_id=FILE_ID,
            text="ambiguous",
            sequence_number=0,
            page_number=1,
            paragraph_number=1,
        )
    with pytest.raises(ValueError, match="exactly one"):
        TextChunk(
            chunk_id="e" * 64,
            file_id=FILE_ID,
            text="unlocated",
            sequence_number=0,
        )


def test_embedding_vector_validates_dimensions_and_finite_values() -> None:
    _, EmbeddingVector, *_ = chunking_contracts()

    vector = EmbeddingVector(
        source_id="b" * 64,
        file_id=FILE_ID,
        model_id="local-test-model",
        space_id="text-semantic-v1",
        modality="text",
        values=[0.25, -0.5, 1.0],
        dimensions=3,
        normalized=True,
    )

    assert vector.values == [0.25, -0.5, 1.0]
    with pytest.raises(ValueError, match="dimensions"):
        EmbeddingVector(
            source_id="b" * 64,
            file_id=FILE_ID,
            model_id="local-test-model",
            space_id="text-semantic-v1",
            modality="text",
            values=[0.25],
            dimensions=2,
        )
    with pytest.raises(ValueError, match="finite"):
        EmbeddingVector(
            source_id="b" * 64,
            file_id=FILE_ID,
            model_id="local-test-model",
            space_id="text-semantic-v1",
            modality="text",
            values=[float("nan")],
            dimensions=1,
        )


def test_embedding_vector_supports_image_sources_and_rejects_blank_spaces() -> None:
    _, EmbeddingVector, *_ = chunking_contracts()

    vector = EmbeddingVector(
        source_id=FILE_ID,
        file_id=FILE_ID,
        model_id="mobileclip-s0",
        space_id="mobileclip-image-text-v1",
        modality="image",
        values=[0.6, 0.8],
        dimensions=2,
        normalized=True,
    )

    assert vector.source_id == FILE_ID
    assert vector.modality == "image"
    with pytest.raises(ValueError, match="space_id"):
        EmbeddingVector(
            source_id=FILE_ID,
            file_id=FILE_ID,
            model_id="mobileclip-s0",
            space_id=" ",
            modality="image",
            values=[1.0],
            dimensions=1,
        )


def test_processing_error_and_batch_result_have_stable_shapes() -> None:
    (
        TextChunk,
        _,
        BatchProcessingResult,
        _,
        ChunkingError,
        _,
    ) = chunking_contracts()
    chunk = TextChunk(
        chunk_id="b" * 64,
        file_id=FILE_ID,
        text="content",
        sequence_number=0,
        paragraph_number=1,
    )
    error = ChunkingError(
        "document contains no extractable text",
        file_id="c" * 64,
    )

    batch = BatchProcessingResult(items=[chunk], errors=[error])

    assert (batch.total, batch.succeeded, batch.failed) == (2, 1, 1)
    assert error.to_dict() == {
        "code": "CHUNKING_ERROR",
        "message": "document contains no extractable text",
        "retryable": False,
        "stage": "chunking",
        "file_id": "c" * 64,
        "chunk_id": None,
    }


def test_pdf_chunks_keep_one_based_page_numbers_and_global_sequence(
    tmp_path: Path,
) -> None:
    TextChunker = text_chunker_type()
    document = make_document(
        tmp_path / "guide.pdf",
        text="first page\n\nsecond page",
        mime_type="application/pdf",
        modality="document",
        page_count=2,
        metadata={"page_texts": ["first page", "second page"]},
    )

    chunks = TextChunker(max_characters=100, overlap_characters=0).chunk(document)

    assert [chunk.text for chunk in chunks] == ["first page", "second page"]
    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert [chunk.paragraph_number for chunk in chunks] == [None, None]
    assert [chunk.sequence_number for chunk in chunks] == [0, 1]
    assert all(chunk.file_id == FILE_ID for chunk in chunks)


def test_non_pdf_chunks_keep_paragraph_and_split_numbers(tmp_path: Path) -> None:
    TextChunker = text_chunker_type()
    document = make_document(
        tmp_path / "notes.docx",
        text="First paragraph.\n\nABCDEFGHIJ\n\nThird paragraph.",
        mime_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        modality="document",
    )

    chunks = TextChunker(max_characters=6, overlap_characters=2).chunk(document)

    assert [(chunk.paragraph_number, chunk.split_number) for chunk in chunks] == [
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (2, 0),
        (2, 1),
        (3, 0),
        (3, 1),
        (3, 2),
        (3, 3),
    ]
    assert [chunk.sequence_number for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.page_number is None for chunk in chunks)


def test_reprocessing_the_same_file_produces_stable_chunk_ids(
    tmp_path: Path,
) -> None:
    TextChunker = text_chunker_type()
    first = make_document(
        tmp_path / "first-name.txt",
        text="Alpha paragraph.\n\nBeta paragraph.",
    )
    duplicate = make_document(
        tmp_path / "renamed-copy.txt",
        text=first.text,
    )
    chunker = TextChunker(max_characters=10, overlap_characters=2)

    first_ids = [chunk.chunk_id for chunk in chunker.chunk(first)]
    repeated_ids = [chunk.chunk_id for chunk in chunker.chunk(first)]
    duplicate_ids = [chunk.chunk_id for chunk in chunker.chunk(duplicate)]

    assert first_ids == repeated_ids == duplicate_ids
    assert len(first_ids) == len(set(first_ids))
    assert all(len(chunk_id) == 64 for chunk_id in first_ids)


def test_chunk_id_changes_when_source_text_changes(tmp_path: Path) -> None:
    TextChunker = text_chunker_type()
    first = make_document(tmp_path / "notes.txt", text="Original text.")
    changed = make_document(
        tmp_path / "notes.txt",
        text="Changed text.",
        file_id="f" * 64,
    )
    chunker = TextChunker(max_characters=100, overlap_characters=0)

    first_id = chunker.chunk(first)[0].chunk_id
    changed_id = chunker.chunk(changed)[0].chunk_id

    assert first_id != changed_id


def test_chunker_rejects_textless_documents_with_controlled_error(
    tmp_path: Path,
) -> None:
    TextChunker = text_chunker_type()
    *_, ChunkingError, _ = chunking_contracts()
    document = make_document(
        tmp_path / "empty.txt",
        text=" \n\n ",
    )

    with pytest.raises(ChunkingError) as raised:
        TextChunker().chunk(document)

    assert raised.value.file_id == FILE_ID
    assert raised.value.stage == "chunking"


def test_pdf_without_page_segments_fails_instead_of_losing_page_numbers(
    tmp_path: Path,
) -> None:
    TextChunker = text_chunker_type()
    *_, ChunkingError, _ = chunking_contracts()
    document = make_document(
        tmp_path / "unsegmented.pdf",
        text="text exists but page locations are unavailable",
        mime_type="application/pdf",
        modality="document",
        page_count=1,
    )

    with pytest.raises(ChunkingError, match="page_texts"):
        TextChunker().chunk(document)


def test_chunk_batch_isolates_document_failures(tmp_path: Path) -> None:
    TextChunker = text_chunker_type()
    valid = make_document(tmp_path / "valid.txt", text="valid text")
    empty = make_document(
        tmp_path / "empty.txt",
        text="",
        file_id="b" * 64,
    )

    batch = TextChunker().chunk_many([valid, empty])

    assert batch.succeeded == 1
    assert batch.failed == 1
    assert batch.total == 2
    assert batch.items[0].file_id == FILE_ID
    assert batch.errors[0].file_id == "b" * 64


@pytest.mark.parametrize(
    ("max_characters", "overlap_characters"),
    [(0, 0), (10, -1), (10, 10), (10, 11)],
)
def test_chunker_rejects_invalid_window_configuration(
    max_characters: int,
    overlap_characters: int,
) -> None:
    TextChunker = text_chunker_type()

    with pytest.raises(ValueError):
        TextChunker(
            max_characters=max_characters,
            overlap_characters=overlap_characters,
        )
