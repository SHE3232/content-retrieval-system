from collections.abc import Sequence

from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine
from content_retrieval.embeddings.service import MultimodalEmbeddingService
from content_retrieval.embeddings.text import TextEmbeddingEngine
from content_retrieval.services.chunking import TextChunker


class RecordingTextBackend:
    model_id = "text-test-v1"
    space_id = "text-semantic-v1"
    dimensions = 2

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[3.0, 4.0] for _ in texts]


class FakeMobileClipBackend:
    model_id = "mobileclip-test-v1"
    space_id = "mobileclip-image-text-v1"
    dimensions = 2

    def encode_images(self, paths: Sequence[object]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in paths]

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class SelectivelyFailingTextBackend(RecordingTextBackend):
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if "bad" in texts:
            raise RuntimeError("rejected query")
        return [[3.0, 4.0] for _ in texts]


def test_text_queries_are_normalized_batched_and_deterministic() -> None:
    backend = RecordingTextBackend()
    engine = TextEmbeddingEngine(backend, batch_size=2)

    first = engine.embed_queries(["  local   search  ", "notes", "third"])
    second = engine.embed_queries(["local search"])

    assert backend.calls == [
        ["local search", "notes"],
        ["third"],
    ]
    assert [item.space_id for item in first.items] == [
        "text-semantic-v1",
        "text-semantic-v1",
        "text-semantic-v1",
    ]
    assert first.items[0].source_id == second.items[0].source_id
    assert first.items[0].file_id == first.items[0].source_id
    assert first.items[0].values == [0.6, 0.8]
    assert first.items[0].metadata == {
        "input_index": 0,
        "source_kind": "query",
    }
    assert first.items[0] is not second.items[0]


def test_text_query_cache_is_bounded_and_refreshes_recent_entries() -> None:
    backend = RecordingTextBackend()
    engine = TextEmbeddingEngine(backend, query_cache_size=2)

    engine.embed_queries(["first"])
    engine.embed_queries(["second"])
    engine.embed_queries(["first"])
    engine.embed_queries(["third"])
    engine.embed_queries(["second"])

    assert backend.calls == [["first"], ["second"], ["third"], ["second"]]


def test_text_queries_isolate_blank_and_backend_failures() -> None:
    backend = SelectivelyFailingTextBackend()
    result = TextEmbeddingEngine(backend, batch_size=3).embed_queries(
        ["good", " ", "bad", "also good"]
    )

    assert [item.metadata["input_index"] for item in result.items] == [0, 3]
    assert result.failed == 2
    assert "empty" in str(result.errors[0])
    assert "failed" in str(result.errors[1])
    assert backend.calls == [
        ["good", "bad", "also good"],
        ["good"],
        ["bad"],
        ["also good"],
    ]


def test_unified_service_exposes_text_query_space() -> None:
    text_engine = TextEmbeddingEngine(RecordingTextBackend())
    service = MultimodalEmbeddingService(
        chunker=TextChunker(),
        text_engine=text_engine,
        mobileclip_engine=MobileClipEmbeddingEngine(FakeMobileClipBackend()),
    )

    result = service.embed_text_queries(["offline notes"])

    assert result.items[0].space_id == "text-semantic-v1"
    assert result.items[0].metadata["source_kind"] == "query"
