from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from content_retrieval.domain.errors import StorageError
from content_retrieval.domain.models import (
    BatchResult,
    ParseResult,
    SkippedFile,
)
from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine
from content_retrieval.embeddings.text import TextEmbeddingEngine
from content_retrieval.services.chunking import TextChunker
from content_retrieval.services.indexing import IndexingService
from content_retrieval.storage.chroma import ChromaVectorRepository


class LocalFixtureIngestion:
    def parse_paths(
        self,
        paths: list[Path | str],
        *,
        recursive: bool = True,
        authorized_roots: list[Path | str] | None = None,
    ) -> BatchResult:
        del recursive, authorized_roots
        result = BatchResult()
        for source in paths:
            path = Path(source).resolve()
            if path.suffix == ".skip":
                result.skips.append(
                    SkippedFile(path=path, reason="unsupported_format")
                )
                continue
            content = path.read_bytes()
            file_id = hashlib.sha256(content).hexdigest()
            if path.suffix == ".png":
                parsed = ParseResult(
                    file_id=file_id,
                    path=path,
                    name=path.name,
                    mime_type="image/png",
                    modality="image",
                    size_bytes=len(content),
                    modified_at=datetime.fromtimestamp(
                        path.stat().st_mtime,
                        tz=timezone.utc,
                    ),
                    width=10,
                    height=20,
                )
            else:
                parsed = ParseResult(
                    file_id=file_id,
                    path=path,
                    name=path.name,
                    mime_type="text/plain",
                    modality="text",
                    size_bytes=len(content),
                    modified_at=datetime.fromtimestamp(
                        path.stat().st_mtime,
                        tz=timezone.utc,
                    ),
                    text=content.decode("utf-8"),
                )
            result.results.append(parsed)
        return result


class RecordingTextBackend:
    model_id = "text-test-v1"
    space_id = "text-semantic-v1"
    dimensions = 2

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        rows: list[list[float]] = []
        for text in texts:
            if text == "bad":
                raise RuntimeError("rejected text")
            rows.append([1.0, 0.0])
        return rows


class RecordingImageBackend:
    model_id = "mobileclip-test-v1"
    space_id = "mobileclip-image-text-v1"
    dimensions = 2

    def __init__(self) -> None:
        self.calls: list[list[Path]] = []

    def encode_images(self, paths: Sequence[Path]) -> list[list[float]]:
        self.calls.append(list(paths))
        return [[0.0, 1.0] for _ in paths]

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0, 1.0] for _ in texts]


class RecoveringTextBackend(RecordingTextBackend):
    def __init__(self) -> None:
        super().__init__()
        self.remaining_failures = 2

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if "bad" in texts and self.remaining_failures:
            self.remaining_failures -= 1
            raise RuntimeError("temporary rejection")
        return [[1.0, 0.0] for _ in texts]


def make_service(
    tmp_path: Path,
) -> tuple[
    IndexingService,
    ChromaVectorRepository,
    RecordingTextBackend,
    RecordingImageBackend,
]:
    repository = ChromaVectorRepository(tmp_path / "index")
    text_backend = RecordingTextBackend()
    image_backend = RecordingImageBackend()
    service = IndexingService(
        ingestion_service=LocalFixtureIngestion(),
        chunker=TextChunker(max_characters=100, overlap_characters=10),
        text_engine=TextEmbeddingEngine(text_backend, batch_size=4),
        mobileclip_engine=MobileClipEmbeddingEngine(
            image_backend,
            batch_size=4,
        ),
        repository=repository,
    )
    return service, repository, text_backend, image_backend


def test_index_paths_persists_located_text_and_image_records(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "notes.txt"
    text_path.write_text("first paragraph\n\nsecond paragraph", encoding="utf-8")
    image_path = tmp_path / "picture.png"
    image_path.write_bytes(b"fake-image")
    service, repository, _, _ = make_service(tmp_path)

    result = service.index_paths(
        [text_path, image_path],
        authorized_roots=[tmp_path],
    )
    records = repository.list_records()

    assert result.parsed_files == 2
    assert result.indexed_files == 2
    assert result.indexed_records == 3
    assert result.failed_files == 0
    assert result.partial_files == 0
    assert [record.document for record in records if record.modality == "text"] == [
        "first paragraph",
        "second paragraph",
    ]
    assert [
        record.paragraph_number
        for record in records
        if record.modality == "text"
    ] == [1, 2]
    assert [record.name for record in records if record.modality == "image"] == [
        "picture.png"
    ]


def test_repeated_unchanged_file_skips_embedding_and_upsert(
    tmp_path: Path,
) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("unchanged", encoding="utf-8")
    service, repository, text_backend, _ = make_service(tmp_path)

    first = service.index_paths([path], authorized_roots=[tmp_path])
    second = service.index_paths([path], authorized_roots=[tmp_path])

    assert first.indexed_records == 1
    assert second.unchanged_files == 1
    assert second.indexed_files == 0
    assert repository.count() == 1
    assert text_backend.calls == [["unchanged"]]


def test_force_reindex_bypasses_unchanged_file_short_circuit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("unchanged", encoding="utf-8")
    service, repository, text_backend, _ = make_service(tmp_path)

    first = service.index_paths([path], authorized_roots=[tmp_path])
    second = service.index_paths(
        [path],
        authorized_roots=[tmp_path],
        force=True,
    )

    assert first.indexed_files == 1
    assert second.indexed_files == 1
    assert second.indexed_records == 1
    assert second.unchanged_files == 0
    assert repository.count() == 1
    assert text_backend.calls == [["unchanged"], ["unchanged"]]


def test_changed_file_replaces_stale_records_after_new_upsert(
    tmp_path: Path,
) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("first\n\nsecond", encoding="utf-8")
    service, repository, _, _ = make_service(tmp_path)

    first = service.index_paths([path], authorized_roots=[tmp_path])
    old_file_id = repository.list_records()[0].file_id
    path.write_text("replacement", encoding="utf-8")
    second = service.index_paths([path], authorized_roots=[tmp_path])

    records = repository.list_records()
    assert first.indexed_records == 2
    assert second.indexed_records == 1
    assert second.removed_stale_records == 2
    assert len(records) == 1
    assert records[0].document == "replacement"
    assert records[0].file_id != old_file_id


def test_partial_text_failure_does_not_block_other_files(tmp_path: Path) -> None:
    partial_path = tmp_path / "partial.txt"
    partial_path.write_text("good\n\nbad", encoding="utf-8")
    image_path = tmp_path / "picture.png"
    image_path.write_bytes(b"fake-image")
    service, repository, _, _ = make_service(tmp_path)

    result = service.index_paths(
        [partial_path, image_path],
        authorized_roots=[tmp_path],
    )

    assert result.indexed_files == 2
    assert result.partial_files == 1
    assert result.failed_files == 0
    assert result.indexed_records == 2
    assert len(result.failures) == 1
    assert result.failures[0].stage == "embedding"
    assert {record.modality for record in repository.list_records()} == {
        "text",
        "image",
    }


def test_skipped_files_are_counted_without_processing(tmp_path: Path) -> None:
    path = tmp_path / "ignored.skip"
    path.write_text("ignored", encoding="utf-8")
    service, repository, _, _ = make_service(tmp_path)

    result = service.index_paths([path], authorized_roots=[tmp_path])

    assert result.skipped_files == 1
    assert result.parsed_files == 0
    assert repository.count() == 0


def test_multiple_errors_mark_one_file_partial_only_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("old", encoding="utf-8")
    service, repository, _, _ = make_service(tmp_path)
    service.index_paths([path], authorized_roots=[tmp_path])
    path.write_text("good\n\nbad", encoding="utf-8")

    def fail_delete(records: object) -> int:
        del records
        raise StorageError("cannot remove stale records")

    monkeypatch.setattr(repository, "delete_records", fail_delete)

    result = service.index_paths([path], authorized_roots=[tmp_path])

    assert result.indexed_files == 1
    assert result.partial_files == 1
    assert [failure.stage for failure in result.failures] == [
        "embedding",
        "storage",
    ]


def test_repeated_partial_file_retries_missing_embeddings(
    tmp_path: Path,
) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("good\n\nbad", encoding="utf-8")
    repository = ChromaVectorRepository(tmp_path / "index")
    text_backend = RecoveringTextBackend()
    service = IndexingService(
        ingestion_service=LocalFixtureIngestion(),
        chunker=TextChunker(max_characters=100, overlap_characters=10),
        text_engine=TextEmbeddingEngine(text_backend, batch_size=4),
        mobileclip_engine=MobileClipEmbeddingEngine(RecordingImageBackend()),
        repository=repository,
    )

    first = service.index_paths([path], authorized_roots=[tmp_path])
    second = service.index_paths([path], authorized_roots=[tmp_path])

    assert first.partial_files == 1
    assert first.indexed_records == 1
    assert second.unchanged_files == 0
    assert second.indexed_records == 2
    assert repository.count() == 2
