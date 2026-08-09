from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from typing import Literal

import pytest

from content_retrieval.domain.models import EmbeddingVector
from content_retrieval.domain.retrieval import IndexRecord
from content_retrieval.services.index_catalog import IndexCatalogService


MODIFIED_AT = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_record(
    tmp_path: Path,
    *,
    source_key: str,
    file_key: str,
    record_key: str,
    relative_path: str,
    modified_at: datetime = MODIFIED_AT,
    modality: Literal["text", "image"] = "text",
    size_bytes: int = 7,
) -> IndexRecord:
    source_id = digest(f"record:{record_key}")
    file_id = digest(f"file:{file_key}")
    vector = EmbeddingVector(
        source_id=source_id,
        file_id=file_id,
        model_id=f"{modality}-test-v1",
        space_id=f"{modality}-space-v1",
        modality=modality,
        values=[1.0, 0.0],
        dimensions=2,
        normalized=True,
    )
    path = (tmp_path / relative_path).resolve()
    return IndexRecord(
        record_id=source_id,
        source_id=source_id,
        file_id=file_id,
        source_key=source_key,
        path=path,
        name=path.name,
        mime_type="image/png" if modality == "image" else "text/plain",
        modality=modality,
        document=path.name,
        vector=vector,
        modified_at=modified_at,
        size_bytes=size_bytes,
        paragraph_number=1 if modality == "text" else None,
    )


class FakeRepository:
    def __init__(self, records: list[IndexRecord]) -> None:
        self.records = list(records)
        self.deleted_sources: list[str] = []

    def list_records(self) -> list[IndexRecord]:
        return list(self.records)

    def delete_source(self, source_key: str) -> int:
        self.deleted_sources.append(source_key)
        retained = [
            record
            for record in self.records
            if record.source_key != source_key
        ]
        deleted = len(self.records) - len(retained)
        self.records = retained
        return deleted


def test_list_files_aggregates_before_deterministic_pagination(
    tmp_path: Path,
) -> None:
    alpha_source = digest("path:alpha")
    zulu_source = digest("path:zulu")
    repository = FakeRepository(
        [
            make_record(
                tmp_path,
                source_key=zulu_source,
                file_key="zulu",
                record_key="zulu-2",
                relative_path="Zulu.txt",
            ),
            make_record(
                tmp_path,
                source_key=alpha_source,
                file_key="alpha",
                record_key="alpha-1",
                relative_path="alpha.png",
                modality="image",
            ),
            make_record(
                tmp_path,
                source_key=zulu_source,
                file_key="zulu",
                record_key="zulu-1",
                relative_path="Zulu.txt",
            ),
        ]
    )
    catalog = IndexCatalogService(repository)

    first = catalog.list_files(page=1, page_size=1)
    second = catalog.list_files(page=2, page_size=1)
    beyond = catalog.list_files(page=3, page_size=1)

    assert first.total == 2
    assert first.total_pages == 2
    assert first.items[0].source_key == alpha_source
    assert first.items[0].record_count == 1
    assert second.items[0].source_key == zulu_source
    assert second.items[0].record_count == 2
    assert beyond.items == ()
    assert beyond.total == 2
    assert beyond.total_pages == 2


def test_list_files_uses_newest_record_as_metadata_representative(
    tmp_path: Path,
) -> None:
    source_key = digest("path:notes")
    older = make_record(
        tmp_path,
        source_key=source_key,
        file_key="old-content",
        record_key="old",
        relative_path="older.txt",
        modified_at=MODIFIED_AT,
        size_bytes=10,
    )
    newer = make_record(
        tmp_path,
        source_key=source_key,
        file_key="new-content",
        record_key="new",
        relative_path="newer.png",
        modified_at=MODIFIED_AT + timedelta(minutes=1),
        modality="image",
        size_bytes=20,
    )

    item = IndexCatalogService(
        FakeRepository([older, newer])
    ).list_files(page=1, page_size=20).items[0]

    assert item.source_key == source_key
    assert item.file_id == newer.file_id
    assert item.path == newer.path
    assert item.name == "newer.png"
    assert item.mime_type == "image/png"
    assert item.modality == "image"
    assert item.size_bytes == 20
    assert item.modified_at == newer.modified_at
    assert item.record_count == 2


@pytest.mark.parametrize(
    ("page", "page_size"),
    [(0, 20), (-1, 20), (1, 0), (1, 101)],
)
def test_list_files_rejects_invalid_pagination(
    page: int,
    page_size: int,
) -> None:
    catalog = IndexCatalogService(FakeRepository([]))

    with pytest.raises(ValueError):
        catalog.list_files(page=page, page_size=page_size)


def test_empty_catalog_has_zero_pages() -> None:
    page = IndexCatalogService(FakeRepository([])).list_files(
        page=1,
        page_size=20,
    )

    assert page.items == ()
    assert page.total == 0
    assert page.total_pages == 0


def test_get_and_delete_file_are_scoped_to_source_key(
    tmp_path: Path,
) -> None:
    target = digest("path:target")
    other = digest("path:other")
    repository = FakeRepository(
        [
            make_record(
                tmp_path,
                source_key=target,
                file_key="target",
                record_key="target-1",
                relative_path="target.txt",
            ),
            make_record(
                tmp_path,
                source_key=target,
                file_key="target",
                record_key="target-2",
                relative_path="target.txt",
            ),
            make_record(
                tmp_path,
                source_key=other,
                file_key="other",
                record_key="other-1",
                relative_path="other.txt",
            ),
        ]
    )
    catalog = IndexCatalogService(repository)

    assert catalog.get_file(target) is not None
    assert catalog.get_file(digest("missing")) is None
    assert catalog.delete_file(digest("missing")) is None
    assert catalog.delete_file(target) == 2
    assert repository.deleted_sources == [target]
    assert [record.source_key for record in repository.records] == [other]
