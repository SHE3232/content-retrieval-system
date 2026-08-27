from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import hashlib
import os
from pathlib import Path

from content_retrieval.domain.errors import (
    ChunkingError,
    ProcessingError,
    StorageError,
)
from content_retrieval.domain.models import (
    EmbeddingVector,
    ParseResult,
    TextChunk,
)
from content_retrieval.domain.retrieval import (
    IndexRecord,
    IndexingFailure,
    IndexingResult,
)
from content_retrieval.embeddings.mobileclip import (
    MobileClipEmbeddingEngine,
    UnavailableMobileClipEmbeddingEngine,
)
from content_retrieval.embeddings.text import TextEmbeddingEngine
from content_retrieval.services.batch_ingestion import BatchIngestionService
from content_retrieval.services.chunking import TextChunker
from content_retrieval.storage.chroma import ChromaVectorRepository


class IndexingService:
    """Connect parsing, source-aware chunking, embeddings, and persistence."""

    def __init__(
        self,
        *,
        ingestion_service: BatchIngestionService,
        chunker: TextChunker,
        text_engine: TextEmbeddingEngine,
        mobileclip_engine: (
            MobileClipEmbeddingEngine | UnavailableMobileClipEmbeddingEngine
        ),
        repository: ChromaVectorRepository,
    ) -> None:
        self.ingestion_service = ingestion_service
        self.chunker = chunker
        self.text_engine = text_engine
        self.mobileclip_engine = mobileclip_engine
        self.repository = repository

    def index_paths(
        self,
        paths: list[Path | str],
        *,
        recursive: bool = True,
        authorized_roots: list[Path | str] | None = None,
        force: bool = False,
    ) -> IndexingResult:
        batch = self.ingestion_service.parse_paths(
            paths,
            recursive=recursive,
            authorized_roots=authorized_roots,
        )
        failures = [
            IndexingFailure(
                path=error.path.resolve(),
                code=error.code,
                message=str(error),
                stage="parsing",
                retryable=error.retryable,
            )
            for error in batch.errors
        ]
        failed_files = len(batch.errors)
        indexed_files = 0
        indexed_records = 0
        partial_files = 0
        unchanged_files = 0
        removed_stale_records = 0

        existing_by_source: dict[str, list[IndexRecord]] = defaultdict(list)
        for record in self.repository.list_records():
            existing_by_source[record.source_key].append(record)

        for document in batch.results:
            source_key = self.source_key(document.path)
            existing = existing_by_source.get(source_key, [])
            if not force and self._is_unchanged(document, existing):
                unchanged_files += 1
                continue

            records, item_failures = self._records_for_document(
                document,
                source_key=source_key,
            )
            failures.extend(item_failures)
            is_partial = bool(item_failures)
            if not records:
                failed_files += 1
                continue

            try:
                written = self.repository.upsert(records)
            except StorageError as error:
                failures.append(
                    self._failure_from_processing_error(
                        document,
                        error,
                    )
                )
                failed_files += 1
                continue

            removed = 0
            if not is_partial:
                current_identities = {
                    (record.space_id, record.record_id)
                    for record in records
                }
                stale = [
                    record
                    for record in existing
                    if (record.space_id, record.record_id)
                    not in current_identities
                ]
                try:
                    removed = self.repository.delete_records(stale)
                except StorageError as error:
                    failures.append(
                        self._failure_from_processing_error(
                            document,
                            error,
                        )
                    )
                    is_partial = True

            indexed_files += 1
            indexed_records += written
            removed_stale_records += removed
            if is_partial:
                partial_files += 1
            existing_by_source[source_key] = records

        parsed_files = len(batch.results) + len(batch.errors)
        return IndexingResult(
            parsed_files=parsed_files,
            indexed_files=indexed_files,
            indexed_records=indexed_records,
            skipped_files=len(batch.skips),
            failed_files=failed_files,
            partial_files=partial_files,
            unchanged_files=unchanged_files,
            removed_stale_records=removed_stale_records,
            failures=tuple(failures),
        )

    @staticmethod
    def source_key(path: Path | str) -> str:
        normalized = os.path.normcase(
            str(Path(path).expanduser().resolve())
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _records_for_document(
        self,
        document: ParseResult,
        *,
        source_key: str,
    ) -> tuple[list[IndexRecord], list[IndexingFailure]]:
        if document.modality == "image":
            embedded = self.mobileclip_engine.embed_images([document])
            records = [
                self._image_record(document, source_key, vector)
                for vector in embedded.items
            ]
            failures = [
                self._failure_from_processing_error(document, error)
                for error in embedded.errors
            ]
            return records, failures

        try:
            chunks = self.chunker.chunk(document)
        except ChunkingError as error:
            return [], [self._failure_from_processing_error(document, error)]

        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        embedded = self.text_engine.embed(chunks)
        records: list[IndexRecord] = []
        failures = [
            self._failure_from_processing_error(document, error)
            for error in embedded.errors
        ]
        for vector in embedded.items:
            chunk = chunk_by_id.get(vector.source_id)
            if chunk is None:
                failures.append(
                    IndexingFailure(
                        path=document.path.resolve(),
                        code="INDEXING_ERROR",
                        message="embedding source does not match a text chunk",
                        stage="indexing",
                        retryable=False,
                        file_id=document.file_id,
                        source_id=vector.source_id,
                    )
                )
                continue
            records.append(
                self._text_record(document, source_key, chunk, vector)
            )
        return records, failures

    @staticmethod
    def _text_record(
        document: ParseResult,
        source_key: str,
        chunk: TextChunk,
        vector: EmbeddingVector,
    ) -> IndexRecord:
        return IndexRecord(
            record_id=vector.source_id,
            source_id=vector.source_id,
            file_id=document.file_id,
            source_key=source_key,
            path=document.path.resolve(),
            name=document.name,
            mime_type=document.mime_type,
            modality="text",
            document=chunk.text,
            vector=vector,
            modified_at=document.modified_at,
            size_bytes=document.size_bytes,
            page_number=chunk.page_number,
            paragraph_number=chunk.paragraph_number,
            sequence_number=chunk.sequence_number,
        )

    @staticmethod
    def _image_record(
        document: ParseResult,
        source_key: str,
        vector: EmbeddingVector,
    ) -> IndexRecord:
        return IndexRecord(
            record_id=vector.source_id,
            source_id=vector.source_id,
            file_id=document.file_id,
            source_key=source_key,
            path=document.path.resolve(),
            name=document.name,
            mime_type=document.mime_type,
            modality="image",
            document=document.name,
            vector=vector,
            modified_at=document.modified_at,
            size_bytes=document.size_bytes,
        )

    def _is_unchanged(
        self,
        document: ParseResult,
        records: Iterable[IndexRecord],
    ) -> bool:
        source = list(records)
        if not source:
            return False
        if document.modality == "image":
            model_id = self.mobileclip_engine.backend.model_id
            space_id = self.mobileclip_engine.backend.space_id
            dimensions = self.mobileclip_engine.backend.dimensions
            expected_source_ids = {document.file_id}
        else:
            model_id = self.text_engine.backend.model_id
            space_id = self.text_engine.backend.space_id
            dimensions = self.text_engine.backend.dimensions
            try:
                expected_source_ids = {
                    chunk.chunk_id for chunk in self.chunker.chunk(document)
                }
            except ChunkingError:
                return False
        return {
            record.source_id for record in source
        } == expected_source_ids and all(
            record.file_id == document.file_id
            and record.model_id == model_id
            and record.space_id == space_id
            and record.dimensions == dimensions
            for record in source
        )

    @staticmethod
    def _failure_from_processing_error(
        document: ParseResult,
        error: ProcessingError,
    ) -> IndexingFailure:
        return IndexingFailure(
            path=document.path.resolve(),
            code=error.code,
            message=str(error),
            stage=error.stage,
            retryable=error.retryable,
            file_id=error.file_id or document.file_id,
            source_id=error.chunk_id,
        )
