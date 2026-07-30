from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.errors import NotFoundError

from content_retrieval.domain.errors import StorageError
from content_retrieval.domain.models import EmbeddingVector
from content_retrieval.domain.retrieval import (
    IndexRecord,
    SearchFilters,
    VectorCandidate,
)


class ChromaVectorRepository:
    """Persist explicit local embeddings without invoking remote embedders."""

    schema_version = "1"

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.database_path))

    def upsert(self, records: Iterable[IndexRecord]) -> int:
        grouped: dict[str, list[IndexRecord]] = defaultdict(list)
        for record in records:
            grouped[record.space_id].append(record)

        written = 0
        for space_id in sorted(grouped):
            batch = grouped[space_id]
            first = batch[0]
            if any(
                record.model_id != first.model_id
                or record.dimensions != first.dimensions
                for record in batch
            ):
                raise StorageError(
                    "one embedding space cannot mix model IDs or dimensions"
                )
            collection = self._collection_for_vector(first.vector, create=True)
            try:
                collection.upsert(
                    ids=[record.record_id for record in batch],
                    embeddings=[record.vector.values for record in batch],
                    metadatas=[
                        self._metadata_from_record(record) for record in batch
                    ],
                    documents=[record.document for record in batch],
                )
            except StorageError:
                raise
            except Exception as error:
                raise StorageError(
                    f"Chroma upsert failed for space {space_id}"
                ) from error
            written += len(batch)
        return written

    def get(self, record_id: str) -> IndexRecord | None:
        for collection in self._collections():
            try:
                result = collection.get(
                    ids=[record_id],
                    include=["documents", "metadatas", "embeddings"],
                )
            except Exception as error:
                raise StorageError("Chroma record lookup failed") from error
            if result["ids"]:
                return self._record_from_result(
                    record_id=result["ids"][0],
                    document=self._required_item(result.get("documents"), 0),
                    metadata=self._required_item(result.get("metadatas"), 0),
                    embedding=self._required_item(result.get("embeddings"), 0),
                )
        return None

    def list_records(self) -> list[IndexRecord]:
        records: list[IndexRecord] = []
        for collection in self._collections():
            try:
                result = collection.get(
                    include=["documents", "metadatas", "embeddings"],
                )
            except Exception as error:
                raise StorageError("Chroma collection listing failed") from error
            for index, record_id in enumerate(result["ids"]):
                records.append(
                    self._record_from_result(
                        record_id=record_id,
                        document=self._required_item(
                            result.get("documents"),
                            index,
                        ),
                        metadata=self._required_item(
                            result.get("metadatas"),
                            index,
                        ),
                        embedding=self._required_item(
                            result.get("embeddings"),
                            index,
                        ),
                    )
                )
        return sorted(records, key=self._record_sort_key)

    def query(
        self,
        vector: EmbeddingVector,
        *,
        limit: int,
        filters: SearchFilters | None = None,
    ) -> list[VectorCandidate]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if not vector.normalized:
            raise StorageError("query vector must be normalized")
        collection = self._collection_for_vector(vector, create=False)
        if collection is None:
            return []
        count = collection.count()
        if count == 0:
            return []

        active_filters = filters or SearchFilters()
        where = self._where_from_filters(active_filters)
        n_results = count if active_filters.path_prefix is not None else min(
            count,
            limit,
        )
        try:
            result = collection.query(
                query_embeddings=[vector.values],
                n_results=n_results,
                where=where,
                include=[
                    "documents",
                    "metadatas",
                    "embeddings",
                    "distances",
                ],
            )
        except Exception as error:
            raise StorageError(
                f"Chroma query failed for space {vector.space_id}"
            ) from error

        ids = self._required_item(result.get("ids"), 0)
        documents = self._required_item(result.get("documents"), 0)
        metadatas = self._required_item(result.get("metadatas"), 0)
        embeddings = self._required_item(result.get("embeddings"), 0)
        distances = self._required_item(result.get("distances"), 0)
        candidates: list[VectorCandidate] = []
        for record_id, document, metadata, embedding, distance in zip(
            ids,
            documents,
            metadatas,
            embeddings,
            distances,
            strict=True,
        ):
            record = self._record_from_result(
                record_id=record_id,
                document=document,
                metadata=metadata,
                embedding=embedding,
            )
            if not self._matches_filters(record, active_filters):
                continue
            score = max(-1.0, min(1.0, 1.0 - float(distance)))
            candidates.append(VectorCandidate(record=record, score=score))

        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                *self._record_sort_key(candidate.record),
            )
        )
        return candidates[:limit]

    def delete_source(self, source_key: str) -> int:
        deleted = 0
        for collection in self._collections():
            try:
                result = collection.get(
                    where={"source_key": source_key},
                    include=[],
                )
                ids = list(result["ids"])
                if ids:
                    collection.delete(ids=ids)
                    deleted += len(ids)
            except Exception as error:
                raise StorageError(
                    "Chroma source deletion failed"
                ) from error
        return deleted

    def clear(self) -> int:
        collections = self._collections()
        deleted = sum(collection.count() for collection in collections)
        for collection in collections:
            try:
                self._client.delete_collection(collection.name)
            except Exception as error:
                raise StorageError("Chroma index clearing failed") from error
        return deleted

    def count(self) -> int:
        try:
            return sum(
                collection.count() for collection in self._collections()
            )
        except Exception as error:
            raise StorageError("Chroma record count failed") from error

    def _collection_for_vector(
        self,
        vector: EmbeddingVector,
        *,
        create: bool,
    ) -> Collection | None:
        name = self._collection_name(vector.space_id)
        try:
            collection = self._client.get_collection(
                name,
                embedding_function=None,
            )
        except NotFoundError:
            if not create:
                return None
            try:
                return self._client.create_collection(
                    name,
                    configuration={"hnsw": {"space": "cosine"}},
                    metadata={
                        "schema_version": self.schema_version,
                        "space_id": vector.space_id,
                        "model_id": vector.model_id,
                        "dimensions": vector.dimensions,
                    },
                    embedding_function=None,
                )
            except Exception as error:
                raise StorageError(
                    f"cannot create Chroma collection for {vector.space_id}"
                ) from error

        self._validate_collection(collection, vector)
        return collection

    def _collections(self) -> list[Collection]:
        try:
            collections = list(self._client.list_collections())
        except Exception as error:
            raise StorageError("cannot list Chroma collections") from error
        return sorted(collections, key=lambda collection: collection.name)

    def _validate_collection(
        self,
        collection: Collection,
        vector: EmbeddingVector,
    ) -> None:
        metadata = collection.metadata or {}
        if metadata.get("schema_version") != self.schema_version:
            raise StorageError("collection schema version is incompatible")
        if metadata.get("space_id") != vector.space_id:
            raise StorageError("collection embedding space is incompatible")
        if metadata.get("model_id") != vector.model_id:
            raise StorageError("collection model ID is incompatible")
        if int(metadata.get("dimensions", -1)) != vector.dimensions:
            raise StorageError("collection vector dimensions are incompatible")

    @staticmethod
    def _collection_name(space_id: str) -> str:
        digest = hashlib.sha256(space_id.encode("utf-8")).hexdigest()[:24]
        return f"space-{digest}"

    @staticmethod
    def _metadata_from_record(record: IndexRecord) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "schema_version": ChromaVectorRepository.schema_version,
            "source_id": record.source_id,
            "file_id": record.file_id,
            "source_key": record.source_key,
            "source_path": str(record.path),
            "source_name": record.name,
            "mime_type": record.mime_type,
            "modality": record.modality,
            "model_id": record.model_id,
            "space_id": record.space_id,
            "dimensions": record.dimensions,
            "normalized": record.vector.normalized,
            "vector_schema_version": record.vector.schema_version,
            "vector_metadata": json.dumps(
                record.vector.metadata,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "modified_at": record.modified_at.timestamp(),
            "size_bytes": record.size_bytes,
            "sequence_number": record.sequence_number,
        }
        if record.page_number is not None:
            metadata["page_number"] = record.page_number
        if record.paragraph_number is not None:
            metadata["paragraph_number"] = record.paragraph_number
        return metadata

    @staticmethod
    def _record_from_result(
        *,
        record_id: str,
        document: Any,
        metadata: Any,
        embedding: Any,
    ) -> IndexRecord:
        if not isinstance(document, str) or not isinstance(metadata, Mapping):
            raise StorageError("stored Chroma record is incomplete")
        values = [float(value) for value in embedding]
        try:
            vector_metadata = json.loads(
                str(metadata.get("vector_metadata", "{}"))
            )
            vector = EmbeddingVector(
                source_id=str(metadata["source_id"]),
                file_id=str(metadata["file_id"]),
                model_id=str(metadata["model_id"]),
                space_id=str(metadata["space_id"]),
                modality=str(metadata["modality"]),
                values=values,
                dimensions=int(metadata["dimensions"]),
                normalized=bool(metadata["normalized"]),
                metadata=vector_metadata,
                schema_version=str(metadata["vector_schema_version"]),
            )
            return IndexRecord(
                record_id=record_id,
                source_id=str(metadata["source_id"]),
                file_id=str(metadata["file_id"]),
                source_key=str(metadata["source_key"]),
                path=Path(str(metadata["source_path"])),
                name=str(metadata["source_name"]),
                mime_type=str(metadata["mime_type"]),
                modality=str(metadata["modality"]),
                document=document,
                vector=vector,
                modified_at=datetime.fromtimestamp(
                    float(metadata["modified_at"]),
                    tz=timezone.utc,
                ),
                size_bytes=int(metadata["size_bytes"]),
                page_number=ChromaVectorRepository._optional_int(
                    metadata.get("page_number")
                ),
                paragraph_number=ChromaVectorRepository._optional_int(
                    metadata.get("paragraph_number")
                ),
                sequence_number=int(metadata["sequence_number"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise StorageError("stored Chroma metadata is invalid") from error

    @staticmethod
    def _where_from_filters(
        filters: SearchFilters,
    ) -> dict[str, Any] | None:
        conditions: list[dict[str, Any]] = []
        if filters.mime_types:
            operator = (
                {"$eq": filters.mime_types[0]}
                if len(filters.mime_types) == 1
                else {"$in": list(filters.mime_types)}
            )
            conditions.append({"mime_type": operator})
        if filters.modalities:
            operator = (
                {"$eq": filters.modalities[0]}
                if len(filters.modalities) == 1
                else {"$in": list(filters.modalities)}
            )
            conditions.append({"modality": operator})
        if filters.modified_after is not None:
            conditions.append(
                {"modified_at": {"$gte": filters.modified_after.timestamp()}}
            )
        if filters.modified_before is not None:
            conditions.append(
                {"modified_at": {"$lte": filters.modified_before.timestamp()}}
            )
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    @staticmethod
    def _matches_filters(
        record: IndexRecord,
        filters: SearchFilters,
    ) -> bool:
        if filters.mime_types and record.mime_type not in filters.mime_types:
            return False
        if filters.modalities and record.modality not in filters.modalities:
            return False
        if (
            filters.modified_after is not None
            and record.modified_at < filters.modified_after
        ):
            return False
        if (
            filters.modified_before is not None
            and record.modified_at > filters.modified_before
        ):
            return False
        if filters.path_prefix is not None:
            record_path = os.path.normcase(str(record.path.resolve()))
            prefix_path = os.path.normcase(str(filters.path_prefix.resolve()))
            try:
                if os.path.commonpath([record_path, prefix_path]) != prefix_path:
                    return False
            except ValueError:
                return False
        return True

    @staticmethod
    def _record_sort_key(record: IndexRecord) -> tuple[str, int, str]:
        return (
            os.path.normcase(str(record.path)),
            record.sequence_number,
            record.record_id,
        )

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        return None if value is None else int(value)

    @staticmethod
    def _required_item(items: Any, index: int) -> Any:
        if items is None or len(items) <= index:
            raise StorageError("stored Chroma result is incomplete")
        return items[index]
