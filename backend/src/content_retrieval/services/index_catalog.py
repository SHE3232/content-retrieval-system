from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
from threading import Lock

from content_retrieval.domain.retrieval import (
    IndexRecord,
    SearchModality,
)
from content_retrieval.storage.chroma import ChromaVectorRepository


GLOBAL_INDEX_MUTATION_KEY = "__global_index_mutation__"


@dataclass(frozen=True, slots=True)
class IndexedFile:
    source_key: str
    file_id: str
    path: Path
    name: str
    mime_type: str
    modality: SearchModality
    size_bytes: int
    modified_at: datetime
    record_count: int


@dataclass(frozen=True, slots=True)
class IndexedFilePage:
    items: tuple[IndexedFile, ...]
    page: int
    page_size: int
    total: int
    total_pages: int


class IndexMutationCoordinator:
    """Reject overlapping process-local mutations for one source."""

    def __init__(self) -> None:
        self._active: set[str] = set()
        self._lock = Lock()

    def claim(self, source_key: str) -> bool:
        with self._lock:
            if source_key in self._active:
                return False
            self._active.add(source_key)
            return True

    def release(self, source_key: str) -> None:
        with self._lock:
            self._active.discard(source_key)


class IndexCatalogService:
    """Project record-level storage into stable file-level views."""

    def __init__(self, repository: ChromaVectorRepository) -> None:
        self.repository = repository

    def list_files(self, *, page: int, page_size: int) -> IndexedFilePage:
        self._validate_pagination(page, page_size)
        files = self._list_all_files()
        total = len(files)
        start = (page - 1) * page_size
        return IndexedFilePage(
            items=tuple(files[start : start + page_size]),
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def get_file(self, source_key: str) -> IndexedFile | None:
        return next(
            (
                item
                for item in self._list_all_files()
                if item.source_key == source_key
            ),
            None,
        )

    def delete_file(self, source_key: str) -> int | None:
        if self.get_file(source_key) is None:
            return None
        return self.repository.delete_source(source_key)

    def _list_all_files(self) -> list[IndexedFile]:
        grouped: dict[str, list[IndexRecord]] = defaultdict(list)
        for record in self.repository.list_records():
            grouped[record.source_key].append(record)

        files: list[IndexedFile] = []
        for source_key, records in grouped.items():
            representative = max(
                records,
                key=lambda record: (record.modified_at, record.file_id),
            )
            files.append(
                IndexedFile(
                    source_key=source_key,
                    file_id=representative.file_id,
                    path=representative.path,
                    name=representative.name,
                    mime_type=representative.mime_type,
                    modality=representative.modality,
                    size_bytes=representative.size_bytes,
                    modified_at=representative.modified_at,
                    record_count=len(records),
                )
            )
        return sorted(
            files,
            key=lambda item: (
                item.path.as_posix().casefold(),
                item.source_key,
            ),
        )

    @staticmethod
    def _validate_pagination(page: int, page_size: int) -> None:
        if page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
