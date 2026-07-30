from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from content_retrieval.domain.errors import RetrievalError, StorageError
from content_retrieval.domain.models import EmbeddingVector
from content_retrieval.domain.retrieval import IndexRecord, SearchFilters
from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine
from content_retrieval.embeddings.service import MultimodalEmbeddingService
from content_retrieval.embeddings.text import TextEmbeddingEngine
from content_retrieval.retrieval.service import RetrievalService
from content_retrieval.services.chunking import TextChunker
from content_retrieval.storage.chroma import ChromaVectorRepository


NOW = datetime(2026, 7, 30, 14, 0, tzinfo=timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class QueryTextBackend:
    model_id = "text-test-v1"
    space_id = "text-semantic-v1"
    dimensions = 2

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [
            [1.0, 0.0] if "alpha" in text or "meaning" in text else [0.0, 1.0]
            for text in texts
        ]


class QueryImageBackend:
    model_id = "mobileclip-test-v1"
    space_id = "mobileclip-image-text-v1"
    dimensions = 2

    def __init__(self) -> None:
        self.query_calls: list[list[str]] = []

    def encode_images(self, paths: Sequence[Path]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in paths]

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        self.query_calls.append(list(texts))
        return [[1.0, 0.0] for _ in texts]


class FailingTextBackend(QueryTextBackend):
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("query backend failed")


def make_record(
    tmp_path: Path,
    *,
    key: str,
    file_key: str,
    name: str,
    document: str,
    vector_values: list[float],
    modality: str = "text",
    sequence_number: int = 0,
) -> IndexRecord:
    source_id = digest(f"source:{key}")
    file_id = digest(f"file:{file_key}")
    path = (tmp_path / name).resolve()
    vector = EmbeddingVector(
        source_id=source_id,
        file_id=file_id,
        model_id=(
            "mobileclip-test-v1" if modality == "image" else "text-test-v1"
        ),
        space_id=(
            "mobileclip-image-text-v1"
            if modality == "image"
            else "text-semantic-v1"
        ),
        modality=modality,
        values=vector_values,
        dimensions=2,
        normalized=True,
    )
    return IndexRecord(
        record_id=source_id,
        source_id=source_id,
        file_id=file_id,
        source_key=digest(f"path:{name}"),
        path=path,
        name=name,
        mime_type="image/png" if modality == "image" else "text/plain",
        modality=modality,
        document=document,
        vector=vector,
        modified_at=NOW,
        size_bytes=10,
        paragraph_number=None if modality == "image" else sequence_number + 1,
        sequence_number=sequence_number,
    )


def make_service(
    tmp_path: Path,
    *,
    records: list[IndexRecord] | None = None,
    text_backend: QueryTextBackend | None = None,
) -> tuple[
    RetrievalService,
    ChromaVectorRepository,
    QueryTextBackend,
    QueryImageBackend,
]:
    repository = ChromaVectorRepository(tmp_path / "index")
    if records:
        repository.upsert(records)
    resolved_text_backend = text_backend or QueryTextBackend()
    image_backend = QueryImageBackend()
    embeddings = MultimodalEmbeddingService(
        chunker=TextChunker(),
        text_engine=TextEmbeddingEngine(resolved_text_backend),
        mobileclip_engine=MobileClipEmbeddingEngine(image_backend),
    )
    return (
        RetrievalService(
            repository=repository,
            embedding_service=embeddings,
        ),
        repository,
        resolved_text_backend,
        image_backend,
    )


def corpus(tmp_path: Path) -> list[IndexRecord]:
    return [
        make_record(
            tmp_path,
            key="a1",
            file_key="a",
            name="alpha-notes.txt",
            document="alpha offline content",
            vector_values=[1.0, 0.0],
        ),
        make_record(
            tmp_path,
            key="a2",
            file_key="a",
            name="alpha-notes.txt",
            document="alpha second chunk",
            vector_values=[1.0, 0.0],
            sequence_number=1,
        ),
        make_record(
            tmp_path,
            key="b1",
            file_key="b",
            name="beta.txt",
            document="beta reference",
            vector_values=[0.0, 1.0],
        ),
        make_record(
            tmp_path,
            key="c1",
            file_key="c",
            name="cat.png",
            document="cat.png",
            vector_values=[1.0, 0.0],
            modality="image",
        ),
    ]


def test_keyword_only_returns_ranked_file_level_results(tmp_path: Path) -> None:
    records = corpus(tmp_path)
    service, _, text_backend, image_backend = make_service(
        tmp_path,
        records=records,
    )

    result = service.search(
        "alpha offline",
        top_k=5,
        channels=("keyword",),
    )

    assert [hit.file_id for hit in result.hits] == [records[0].file_id]
    assert result.hits[0].match_reasons == ("keyword",)
    assert result.hits[0].snippet == "alpha offline content"
    assert text_backend.calls == []
    assert image_backend.query_calls == []


def test_text_semantic_query_uses_text_space_and_deduplicates_chunks(
    tmp_path: Path,
) -> None:
    records = corpus(tmp_path)
    service, _, text_backend, _ = make_service(tmp_path, records=records)

    result = service.search(
        "meaning",
        top_k=5,
        channels=("text_semantic",),
    )

    assert [hit.file_id for hit in result.hits] == [
        records[0].file_id,
        records[2].file_id,
    ]
    assert len({hit.file_id for hit in result.hits}) == len(result.hits)
    assert result.hits[0].match_reasons == ("text_semantic",)
    assert text_backend.calls == [["meaning"]]


def test_image_semantic_query_returns_visual_result(tmp_path: Path) -> None:
    records = corpus(tmp_path)
    service, _, _, image_backend = make_service(tmp_path, records=records)

    result = service.search(
        "a cat",
        top_k=5,
        channels=("image_semantic",),
    )

    assert [hit.name for hit in result.hits] == ["cat.png"]
    assert result.hits[0].snippet is None
    assert result.hits[0].match_reasons == ("image_semantic",)
    assert image_backend.query_calls == [["a cat"]]


def test_all_channels_are_fused_without_duplicate_files(tmp_path: Path) -> None:
    records = corpus(tmp_path)
    service, _, _, _ = make_service(tmp_path, records=records)

    result = service.search("alpha cat", top_k=10)

    assert result.hits[0].file_id == records[0].file_id
    assert result.hits[0].match_reasons == ("keyword", "text_semantic")
    assert any(
        hit.name == "cat.png" and "image_semantic" in hit.match_reasons
        for hit in result.hits
    )
    assert len({hit.file_id for hit in result.hits}) == len(result.hits)
    assert result.total_candidates == 3


def test_modality_filter_skips_irrelevant_query_encoder(
    tmp_path: Path,
) -> None:
    records = corpus(tmp_path)
    service, _, text_backend, image_backend = make_service(
        tmp_path,
        records=records,
    )

    result = service.search(
        "cat",
        top_k=5,
        filters=SearchFilters(modalities=("image",)),
    )

    assert [hit.name for hit in result.hits] == ["cat.png"]
    assert text_backend.calls == []
    assert image_backend.query_calls == [["cat"]]


def test_refresh_rebuilds_keyword_catalog_after_index_changes(
    tmp_path: Path,
) -> None:
    service, repository, _, _ = make_service(tmp_path)
    record = corpus(tmp_path)[0]
    repository.upsert([record])

    assert service.search(
        "alpha",
        top_k=5,
        channels=("keyword",),
    ).hits == ()

    service.refresh()

    assert [
        hit.file_id
        for hit in service.search(
            "alpha",
            top_k=5,
            channels=("keyword",),
        ).hits
    ] == [record.file_id]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"query": " ", "top_k": 5}, "empty"),
        ({"query": "alpha", "top_k": 0}, "top_k"),
        ({"query": "alpha", "top_k": 101}, "top_k"),
        (
            {
                "query": "alpha",
                "top_k": 5,
                "channels": ("unknown",),
            },
            "channel",
        ),
    ],
)
def test_search_validates_request(
    tmp_path: Path,
    kwargs: dict[str, object],
    message: str,
) -> None:
    service, _, _, _ = make_service(tmp_path, records=corpus(tmp_path))

    with pytest.raises((ValueError, RetrievalError), match=message):
        service.search(**kwargs)


def test_query_embedding_failure_becomes_controlled_retrieval_error(
    tmp_path: Path,
) -> None:
    service, _, _, _ = make_service(
        tmp_path,
        records=corpus(tmp_path),
        text_backend=FailingTextBackend(),
    )

    with pytest.raises(RetrievalError, match="embedding"):
        service.search(
            "alpha",
            top_k=5,
            channels=("text_semantic",),
        )


def test_storage_failure_becomes_controlled_retrieval_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository, _, _ = make_service(
        tmp_path,
        records=corpus(tmp_path),
    )

    def fail_query(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise StorageError("database unavailable")

    monkeypatch.setattr(repository, "query", fail_query)

    with pytest.raises(RetrievalError, match="vector search"):
        service.search(
            "alpha",
            top_k=5,
            channels=("text_semantic",),
        )
