from datetime import datetime, timedelta, timezone
import gc
import hashlib
from pathlib import Path

import pytest

from content_retrieval.domain.errors import StorageError
from content_retrieval.domain.models import EmbeddingVector
from content_retrieval.domain.retrieval import IndexRecord, SearchFilters
from content_retrieval.storage.chroma import ChromaVectorRepository


MODIFIED_AT = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_record(
    tmp_path: Path,
    *,
    key: str,
    vector_values: list[float],
    modality: str = "text",
    space_id: str | None = None,
    model_id: str | None = None,
    source_key: str | None = None,
    relative_path: str | None = None,
    mime_type: str | None = None,
    modified_at: datetime = MODIFIED_AT,
) -> IndexRecord:
    source_id = digest(f"source:{key}")
    file_id = digest(f"file:{key}")
    path = tmp_path / (
        relative_path
        or (f"{key}.png" if modality == "image" else f"{key}.txt")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")
    vector = EmbeddingVector(
        source_id=source_id,
        file_id=file_id,
        model_id=model_id
        or ("mobileclip-test-v1" if modality == "image" else "text-test-v1"),
        space_id=space_id
        or (
            "mobileclip-image-text-v1"
            if modality == "image"
            else "text-semantic-v1"
        ),
        modality=modality,
        values=vector_values,
        dimensions=len(vector_values),
        normalized=True,
        metadata={"fixture": key},
    )
    return IndexRecord(
        record_id=source_id,
        source_id=source_id,
        file_id=file_id,
        source_key=source_key or digest(f"path:{key}"),
        path=path.resolve(),
        name=path.name,
        mime_type=mime_type
        or ("image/png" if modality == "image" else "text/plain"),
        modality=modality,
        document=(
            f"visual fixture {key}"
            if modality == "image"
            else f"offline local search fixture {key}"
        ),
        vector=vector,
        modified_at=modified_at,
        size_bytes=7,
        paragraph_number=None if modality == "image" else 1,
    )


def make_query(
    *,
    values: list[float],
    space_id: str = "text-semantic-v1",
    model_id: str = "text-test-v1",
    normalized: bool = True,
) -> EmbeddingVector:
    return EmbeddingVector(
        source_id=digest("f"),
        file_id=digest("f"),
        model_id=model_id,
        space_id=space_id,
        modality="text",
        values=values,
        dimensions=len(values),
        normalized=normalized,
        metadata={"source_kind": "query"},
    )


def test_upsert_survives_restart_and_roundtrips_record(tmp_path: Path) -> None:
    database_path = tmp_path / "index"
    record = make_record(tmp_path, key="a", vector_values=[1.0, 0.0])

    first = ChromaVectorRepository(database_path)
    assert first.upsert([record]) == 1
    assert first.count() == 1

    second = ChromaVectorRepository(database_path)
    assert second.get(record.record_id) == record
    assert second.list_records() == [record]
    search_records = second.list_search_records()
    assert search_records == [record]
    assert not hasattr(search_records[0], "vector")


def test_close_releases_persistent_chroma_system(tmp_path: Path) -> None:
    from chromadb.api.shared_system_client import SharedSystemClient

    repository = ChromaVectorRepository(tmp_path / "index")
    identifier = str(repository.database_path)

    assert identifier in SharedSystemClient._identifier_to_system

    repository.close()
    repository.close()

    assert identifier not in SharedSystemClient._identifier_to_system


def test_context_manager_closes_repository(tmp_path: Path) -> None:
    from chromadb.api.shared_system_client import SharedSystemClient

    with ChromaVectorRepository(tmp_path / "index") as repository:
        identifier = str(repository.database_path)
        assert identifier in SharedSystemClient._identifier_to_system

    assert identifier not in SharedSystemClient._identifier_to_system


def test_unreferenced_repository_releases_chroma_system(tmp_path: Path) -> None:
    from chromadb.api.shared_system_client import SharedSystemClient

    repository = ChromaVectorRepository(tmp_path / "index")
    identifier = str(repository.database_path)

    del repository
    gc.collect()

    assert identifier not in SharedSystemClient._identifier_to_system


def test_upsert_is_idempotent_and_updates_document(tmp_path: Path) -> None:
    repository = ChromaVectorRepository(tmp_path / "index")
    original = make_record(tmp_path, key="a", vector_values=[1.0, 0.0])
    updated = IndexRecord(
        record_id=original.record_id,
        source_id=original.source_id,
        file_id=original.file_id,
        source_key=original.source_key,
        path=original.path,
        name=original.name,
        mime_type=original.mime_type,
        modality=original.modality,
        document="updated searchable text",
        vector=original.vector,
        modified_at=original.modified_at,
        size_bytes=original.size_bytes,
        paragraph_number=original.paragraph_number,
    )

    repository.upsert([original])
    repository.upsert([updated])

    assert repository.count() == 1
    assert repository.get(original.record_id) == updated


def test_repository_keeps_embedding_spaces_isolated(tmp_path: Path) -> None:
    repository = ChromaVectorRepository(tmp_path / "index")
    text_record = make_record(
        tmp_path,
        key="a",
        vector_values=[1.0, 0.0],
    )
    image_record = make_record(
        tmp_path,
        key="c",
        vector_values=[1.0, 0.0],
        modality="image",
    )
    repository.upsert([text_record, image_record])

    text_candidates = repository.query(
        make_query(values=[1.0, 0.0]),
        limit=10,
    )
    image_candidates = repository.query(
        make_query(
            values=[1.0, 0.0],
            space_id="mobileclip-image-text-v1",
            model_id="mobileclip-test-v1",
        ),
        limit=10,
    )

    assert [candidate.record for candidate in text_candidates] == [text_record]
    assert [candidate.record for candidate in image_candidates] == [image_record]
    assert text_candidates[0].score == pytest.approx(1.0)
    assert image_candidates[0].score == pytest.approx(1.0)


def test_query_cache_reuses_results_and_invalidates_after_upsert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ChromaVectorRepository(tmp_path / "index", query_cache_size=2)
    first = make_record(tmp_path, key="a", vector_values=[1.0, 0.0])
    repository.upsert([first])
    collection = repository._collection_for_vector(first.vector, create=False)
    assert collection is not None
    original_query = collection.query
    calls = 0

    def recording_query(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        return original_query(*args, **kwargs)

    monkeypatch.setattr(collection, "query", recording_query)
    monkeypatch.setattr(
        repository,
        "_collection_for_vector",
        lambda vector, *, create: collection,
    )
    query = make_query(values=[1.0, 0.0])

    assert repository.query(query, limit=10)[0].record == first
    assert repository.query(query, limit=10)[0].record == first
    assert calls == 1

    second = make_record(tmp_path, key="b", vector_values=[0.9, 0.1])
    repository.upsert([second])
    repository.query(query, limit=10)

    assert calls == 2


def test_query_applies_metadata_and_path_filters(tmp_path: Path) -> None:
    repository = ChromaVectorRepository(tmp_path / "index")
    included = make_record(
        tmp_path,
        key="a",
        vector_values=[1.0, 0.0],
        relative_path="allowed/included.txt",
        mime_type="text/plain",
    )
    wrong_path = make_record(
        tmp_path,
        key="c",
        vector_values=[0.99, 0.01],
        relative_path="other/wrong.txt",
        mime_type="text/plain",
    )
    wrong_mime = make_record(
        tmp_path,
        key="e",
        vector_values=[0.98, 0.02],
        relative_path="allowed/wrong.pdf",
        mime_type="application/pdf",
    )
    too_old = make_record(
        tmp_path,
        key="g",
        vector_values=[0.97, 0.03],
        relative_path="allowed/old.txt",
        mime_type="text/plain",
        modified_at=MODIFIED_AT - timedelta(days=10),
    )
    repository.upsert([included, wrong_path, wrong_mime, too_old])

    candidates = repository.query(
        make_query(values=[1.0, 0.0]),
        limit=10,
        filters=SearchFilters(
            mime_types=("text/plain",),
            modalities=("text",),
            path_prefix=(tmp_path / "allowed").resolve(),
            modified_after=MODIFIED_AT - timedelta(days=1),
        ),
    )

    assert [candidate.record for candidate in candidates] == [included]


def test_delete_source_clear_and_count_are_collection_wide(tmp_path: Path) -> None:
    repository = ChromaVectorRepository(tmp_path / "index")
    shared_source_key = digest("9")
    first = make_record(
        tmp_path,
        key="a",
        vector_values=[1.0, 0.0],
        source_key=shared_source_key,
    )
    second = make_record(
        tmp_path,
        key="c",
        vector_values=[0.0, 1.0],
        source_key=shared_source_key,
    )
    remaining = make_record(
        tmp_path,
        key="e",
        vector_values=[1.0, 0.0],
        modality="image",
    )
    repository.upsert([first, second, remaining])

    assert repository.delete_source(shared_source_key) == 2
    assert repository.list_records() == [remaining]
    assert repository.clear() == 1
    assert repository.count() == 0


def test_delete_records_removes_only_explicit_records(tmp_path: Path) -> None:
    repository = ChromaVectorRepository(tmp_path / "index")
    first = make_record(tmp_path, key="a", vector_values=[1.0, 0.0])
    second = make_record(tmp_path, key="c", vector_values=[0.0, 1.0])
    repository.upsert([first, second])

    assert repository.delete_records([first]) == 1
    assert repository.list_records() == [second]


def test_repository_rejects_incompatible_collection_or_query(tmp_path: Path) -> None:
    repository = ChromaVectorRepository(tmp_path / "index")
    record = make_record(tmp_path, key="a", vector_values=[1.0, 0.0])
    repository.upsert([record])
    wrong_model = make_record(
        tmp_path,
        key="c",
        vector_values=[1.0, 0.0],
        space_id=record.space_id,
        model_id="different-model",
    )

    with pytest.raises(StorageError, match="model"):
        repository.upsert([wrong_model])

    with pytest.raises(StorageError, match="normalized"):
        repository.query(
            make_query(values=[1.0, 0.0], normalized=False),
            limit=1,
        )

    with pytest.raises(ValueError, match="limit"):
        repository.query(make_query(values=[1.0, 0.0]), limit=0)
