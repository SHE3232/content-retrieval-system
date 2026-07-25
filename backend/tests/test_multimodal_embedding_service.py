from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from content_retrieval.domain.models import EmbeddingVector, ParseResult
from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine
from content_retrieval.embeddings.service import (
    MultimodalEmbeddingService,
    cosine_similarity,
)
from content_retrieval.embeddings.text import TextEmbeddingEngine
from content_retrieval.services.chunking import TextChunker


class FakeTextBackend:
    model_id = "text-test-v1"
    space_id = "text-semantic-v1"
    dimensions = 2

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[3.0, 4.0] for _ in texts]


class FakeMobileClipBackend:
    model_id = "mobileclip-test-v1"
    space_id = "mobileclip-image-text-v1"
    dimensions = 2

    def encode_images(self, paths: list[Path]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in paths]

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.8, 0.6] for _ in texts]


def parse_result(
    *,
    identifier: str,
    modality: str,
    text: str | None = None,
) -> ParseResult:
    suffix = ".png" if modality == "image" else ".txt"
    mime_type = "image/png" if modality == "image" else "text/plain"
    return ParseResult(
        file_id=identifier * 64,
        path=Path(f"{identifier}{suffix}"),
        name=f"{identifier}{suffix}",
        mime_type=mime_type,
        modality=modality,
        size_bytes=1,
        modified_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        text=text,
        width=10 if modality == "image" else None,
        height=20 if modality == "image" else None,
    )


@pytest.fixture
def service() -> MultimodalEmbeddingService:
    return MultimodalEmbeddingService(
        chunker=TextChunker(max_characters=100, overlap_characters=10),
        text_engine=TextEmbeddingEngine(FakeTextBackend(), batch_size=2),
        mobileclip_engine=MobileClipEmbeddingEngine(
            FakeMobileClipBackend(),
            batch_size=2,
        ),
    )


def test_dispatches_documents_in_input_order_and_records_source_position(
    service: MultimodalEmbeddingService,
) -> None:
    inputs = [
        parse_result(identifier="a", modality="text", text="first"),
        parse_result(identifier="b", modality="image"),
        parse_result(identifier="c", modality="document", text="third"),
    ]

    result = service.embed_documents(inputs)

    assert [item.modality for item in result.items] == [
        "text",
        "image",
        "text",
    ]
    assert [item.file_id for item in result.items] == [
        "a" * 64,
        "b" * 64,
        "c" * 64,
    ]
    assert [item.metadata["input_index"] for item in result.items] == [0, 1, 2]


def test_keeps_processing_after_one_document_cannot_be_chunked(
    service: MultimodalEmbeddingService,
) -> None:
    inputs = [
        parse_result(identifier="a", modality="text", text=""),
        parse_result(identifier="b", modality="image"),
    ]

    result = service.embed_documents(inputs)

    assert result.succeeded == 1
    assert result.failed == 1
    assert result.items[0].file_id == "b" * 64
    assert result.errors[0].file_id == "a" * 64


def test_mobileclip_queries_use_the_image_embedding_space(
    service: MultimodalEmbeddingService,
) -> None:
    image = service.embed_documents(
        [parse_result(identifier="a", modality="image")]
    ).items[0]
    query = service.embed_image_queries(["a square"]).items[0]

    assert image.space_id == query.space_id
    assert query.metadata["source_kind"] == "query"
    assert cosine_similarity(image, query) == pytest.approx(0.8)


def vector(
    *,
    space_id: str = "space-a",
    dimensions: int = 2,
    values: list[float] | None = None,
    normalized: bool = True,
) -> EmbeddingVector:
    return EmbeddingVector(
        source_id="d" * 64,
        file_id="e" * 64,
        model_id="model-a",
        space_id=space_id,
        modality="text",
        values=values or [1.0, 0.0],
        dimensions=dimensions,
        normalized=normalized,
    )


def test_cosine_similarity_rejects_incompatible_vectors() -> None:
    with pytest.raises(ValueError, match="different embedding spaces"):
        cosine_similarity(vector(), vector(space_id="space-b"))

    with pytest.raises(ValueError, match="different dimensions"):
        cosine_similarity(
            vector(),
            vector(dimensions=3, values=[1.0, 0.0, 0.0]),
        )

    with pytest.raises(ValueError, match="L2-normalized"):
        cosine_similarity(vector(), vector(normalized=False))


def test_cosine_similarity_clamps_rounding_noise() -> None:
    left = vector(values=[1.0, 1e-16])
    right = vector(values=[1.0, 1e-16])

    assert cosine_similarity(left, right) == 1.0
