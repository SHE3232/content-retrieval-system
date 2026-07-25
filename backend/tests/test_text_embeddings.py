from collections.abc import Sequence
import sys
import types
from pathlib import Path

import pytest

from content_retrieval.domain.models import TextChunk


FILE_ID = "a" * 64


def make_chunk(index: int, text: str) -> TextChunk:
    return TextChunk(
        chunk_id=f"{index + 1:064x}",
        file_id=FILE_ID,
        text=text,
        sequence_number=index,
        paragraph_number=index + 1,
    )


class RecordingBackend:
    model_id = "fake-text-v1"
    space_id = "text-semantic-v1"
    dimensions = 3

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        self.calls.append(list(texts))
        return [
            [float(len(text)), float(index + 1), 2.0]
            for index, text in enumerate(texts)
        ]


class SelectivelyFailingBackend(RecordingBackend):
    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        self.calls.append(list(texts))
        if "bad" in texts:
            raise RuntimeError("backend rejected input")
        return [[3.0, 4.0, 0.0] for _ in texts]


class InvalidVectorBackend(RecordingBackend):
    def __init__(self, vector: list[float]) -> None:
        super().__init__()
        self.vector = vector

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [self.vector for _ in texts]


def test_text_engine_batches_in_order_and_normalizes_vectors() -> None:
    from content_retrieval.embeddings.text import TextEmbeddingEngine

    backend = RecordingBackend()
    chunks = [make_chunk(index, f"text-{index}") for index in range(5)]

    batch = TextEmbeddingEngine(backend, batch_size=2).embed(chunks)

    assert backend.calls == [
        ["text-0", "text-1"],
        ["text-2", "text-3"],
        ["text-4"],
    ]
    assert [item.source_id for item in batch.items] == [
        chunk.chunk_id for chunk in chunks
    ]
    assert [item.file_id for item in batch.items] == [FILE_ID] * 5
    assert all(item.model_id == backend.model_id for item in batch.items)
    assert all(item.space_id == backend.space_id for item in batch.items)
    assert all(item.modality == "text" for item in batch.items)
    assert all(item.normalized for item in batch.items)
    assert all(
        abs(sum(value * value for value in item.values) - 1.0) < 1e-9
        for item in batch.items
    )
    assert batch.failed == 0


def test_text_engine_isolates_a_failed_item_without_losing_other_chunks() -> None:
    from content_retrieval.embeddings.text import TextEmbeddingEngine

    backend = SelectivelyFailingBackend()
    chunks = [
        make_chunk(0, "good-one"),
        make_chunk(1, "bad"),
        make_chunk(2, "good-two"),
    ]

    batch = TextEmbeddingEngine(backend, batch_size=3).embed(chunks)

    assert [item.source_id for item in batch.items] == [
        chunks[0].chunk_id,
        chunks[2].chunk_id,
    ]
    assert batch.failed == 1
    assert batch.errors[0].file_id == FILE_ID
    assert batch.errors[0].chunk_id == chunks[1].chunk_id
    assert batch.errors[0].stage == "embedding"
    assert backend.calls == [
        ["good-one", "bad", "good-two"],
        ["good-one"],
        ["bad"],
        ["good-two"],
    ]


@pytest.mark.parametrize(
    ("vector", "message"),
    [
        ([1.0, 2.0], "dimensions"),
        ([0.0, 0.0, 0.0], "zero vector"),
        ([1.0, float("nan"), 0.0], "finite"),
    ],
)
def test_text_engine_reports_invalid_backend_vectors_per_item(
    vector: list[float],
    message: str,
) -> None:
    from content_retrieval.embeddings.text import TextEmbeddingEngine

    chunk = make_chunk(0, "content")

    batch = TextEmbeddingEngine(
        InvalidVectorBackend(vector),
        batch_size=1,
    ).embed([chunk])

    assert batch.succeeded == 0
    assert batch.failed == 1
    assert message in str(batch.errors[0])
    assert batch.errors[0].chunk_id == chunk.chunk_id


def test_text_engine_rejects_invalid_batch_size_and_backend_contract() -> None:
    from content_retrieval.embeddings.text import TextEmbeddingEngine

    backend = RecordingBackend()
    with pytest.raises(ValueError, match="batch_size"):
        TextEmbeddingEngine(backend, batch_size=0)

    backend.space_id = " "
    with pytest.raises(ValueError, match="space_id"):
        TextEmbeddingEngine(backend)


def test_sentence_transformer_backend_loads_only_from_a_local_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from content_retrieval.embeddings.sentence_transformer import (
        SentenceTransformerBackend,
    )

    model_path = tmp_path / "model"
    model_path.mkdir()
    calls: dict[str, object] = {}

    class FakeArray:
        def tolist(self) -> list[list[float]]:
            return [[3.0, 4.0, 0.0]]

    class FakeSentenceTransformer:
        def __init__(self, path: str, **kwargs: object) -> None:
            calls["path"] = path
            calls["init_kwargs"] = kwargs

        def get_sentence_embedding_dimension(self) -> int:
            return 3

        def encode(self, texts: list[str], **kwargs: object) -> FakeArray:
            calls["texts"] = texts
            calls["encode_kwargs"] = kwargs
            return FakeArray()

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    backend = SentenceTransformerBackend(
        model_path,
        model_id="text-multilingual-v1",
        space_id="text-semantic-v1",
        dimensions=3,
        batch_size=8,
    )

    assert backend.encode(["hello"]) == [[3.0, 4.0, 0.0]]
    assert calls["path"] == str(model_path.resolve())
    assert calls["init_kwargs"] == {
        "device": "cpu",
        "local_files_only": True,
    }
    assert calls["encode_kwargs"] == {
        "batch_size": 8,
        "convert_to_numpy": True,
        "normalize_embeddings": False,
        "show_progress_bar": False,
    }


def test_sentence_transformer_backend_rejects_missing_or_wrong_models(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from content_retrieval.embeddings.sentence_transformer import (
        SentenceTransformerBackend,
    )

    with pytest.raises(FileNotFoundError):
        SentenceTransformerBackend(
            tmp_path / "missing",
            model_id="text-model",
            space_id="text-space",
            dimensions=3,
        )

    model_path = tmp_path / "model"
    model_path.mkdir()

    class FakeSentenceTransformer:
        def __init__(self, path: str, **kwargs: object) -> None:
            pass

        def get_sentence_embedding_dimension(self) -> int:
            return 2

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    with pytest.raises(ValueError, match="dimension"):
        SentenceTransformerBackend(
            model_path,
            model_id="text-model",
            space_id="text-space",
            dimensions=3,
        )
