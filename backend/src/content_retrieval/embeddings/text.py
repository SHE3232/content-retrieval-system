from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Sequence
import hashlib
import math
from typing import Protocol, runtime_checkable

from content_retrieval.domain.errors import EmbeddingError
from content_retrieval.domain.models import (
    BatchProcessingResult,
    EmbeddingVector,
    TextChunk,
)


@runtime_checkable
class TextEncoderBackend(Protocol):
    model_id: str
    space_id: str
    dimensions: int

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Encode text without performing network access."""
        ...


class TextEmbeddingEngine:
    """Validate, normalize, and isolate failures from a local text encoder."""

    def __init__(
        self,
        backend: TextEncoderBackend,
        *,
        batch_size: int = 16,
        query_cache_size: int = 128,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not backend.model_id.strip():
            raise ValueError("backend model_id must not be blank")
        if not backend.space_id.strip():
            raise ValueError("backend space_id must not be blank")
        if backend.dimensions <= 0:
            raise ValueError("backend dimensions must be positive")
        if query_cache_size < 0:
            raise ValueError("query_cache_size must be non-negative")
        self.backend = backend
        self.batch_size = batch_size
        self.query_cache_size = query_cache_size
        self._query_cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()

    def embed(self, chunks: Iterable[TextChunk]) -> BatchProcessingResult:
        source = list(chunks)
        result = BatchProcessingResult()
        for start in range(0, len(source), self.batch_size):
            batch = source[start : start + self.batch_size]
            self._embed_batch(batch, result)
        return result

    def embed_queries(self, queries: Iterable[str]) -> BatchProcessingResult:
        """Embed local text queries in the document text semantic space."""
        result = BatchProcessingResult()
        valid: list[tuple[int, str, str]] = []
        for input_index, query in enumerate(queries):
            normalized = " ".join(query.split())
            if not normalized:
                result.errors.append(EmbeddingError("query text is empty"))
                continue
            query_id = hashlib.sha256(
                f"{self.backend.model_id}\0{normalized}".encode("utf-8")
            ).hexdigest()
            cached = self._cached_query(query_id, input_index=input_index)
            if cached is not None:
                result.items.append(cached)
                continue
            valid.append((input_index, normalized, query_id))

        for start in range(0, len(valid), self.batch_size):
            self._embed_query_batch(
                valid[start : start + self.batch_size],
                result,
            )
        result.items.sort(key=lambda item: int(item.metadata["input_index"]))
        return result

    def _embed_batch(
        self,
        chunks: list[TextChunk],
        result: BatchProcessingResult,
    ) -> None:
        if not chunks:
            return
        try:
            vectors = self.backend.encode([chunk.text for chunk in chunks])
            if len(vectors) != len(chunks):
                raise ValueError(
                    "backend output count does not match input count"
                )
        except Exception:
            if len(chunks) == 1:
                result.errors.append(self._backend_error(chunks[0]))
                return
            for chunk in chunks:
                self._embed_batch([chunk], result)
            return

        for chunk, vector in zip(chunks, vectors, strict=True):
            try:
                normalized = self._normalize(vector)
                result.items.append(
                    EmbeddingVector(
                        source_id=chunk.chunk_id,
                        file_id=chunk.file_id,
                        model_id=self.backend.model_id,
                        space_id=self.backend.space_id,
                        modality="text",
                        values=normalized,
                        dimensions=self.backend.dimensions,
                        normalized=True,
                        metadata={
                            "sequence_number": chunk.sequence_number,
                            "page_number": chunk.page_number,
                            "paragraph_number": chunk.paragraph_number,
                            "split_number": chunk.split_number,
                        },
                    )
                )
            except (TypeError, ValueError) as error:
                result.errors.append(
                    EmbeddingError(
                        str(error),
                        file_id=chunk.file_id,
                        chunk_id=chunk.chunk_id,
                    )
                )

    def _embed_query_batch(
        self,
        entries: list[tuple[int, str, str]],
        result: BatchProcessingResult,
    ) -> None:
        if not entries:
            return
        try:
            vectors = self.backend.encode(
                [query for _, query, _ in entries]
            )
            if len(vectors) != len(entries):
                raise ValueError(
                    "backend output count does not match input count"
                )
        except Exception:
            if len(entries) == 1:
                result.errors.append(
                    EmbeddingError("text encoder failed for one query")
                )
                return
            for entry in entries:
                self._embed_query_batch([entry], result)
            return

        for (input_index, _, query_id), vector in zip(
            entries,
            vectors,
            strict=True,
        ):
            try:
                normalized = self._normalize(vector)
                result.items.append(
                    EmbeddingVector(
                        source_id=query_id,
                        file_id=query_id,
                        model_id=self.backend.model_id,
                        space_id=self.backend.space_id,
                        modality="text",
                        values=normalized,
                        dimensions=self.backend.dimensions,
                        normalized=True,
                        metadata={
                            "input_index": input_index,
                            "source_kind": "query",
                        },
                    )
                )
                self._cache_query(query_id, normalized)
            except (TypeError, ValueError) as error:
                result.errors.append(EmbeddingError(str(error)))

    def _cached_query(
        self,
        query_id: str,
        *,
        input_index: int,
    ) -> EmbeddingVector | None:
        values = self._query_cache.get(query_id)
        if values is None:
            return None
        self._query_cache.move_to_end(query_id)
        return EmbeddingVector(
            source_id=query_id,
            file_id=query_id,
            model_id=self.backend.model_id,
            space_id=self.backend.space_id,
            modality="text",
            values=list(values),
            dimensions=self.backend.dimensions,
            normalized=True,
            metadata={"input_index": input_index, "source_kind": "query"},
        )

    def _cache_query(self, query_id: str, values: Sequence[float]) -> None:
        if self.query_cache_size == 0:
            return
        self._query_cache[query_id] = tuple(float(value) for value in values)
        self._query_cache.move_to_end(query_id)
        while len(self._query_cache) > self.query_cache_size:
            self._query_cache.popitem(last=False)

    def _normalize(self, vector: Sequence[float]) -> list[float]:
        values = list(vector)
        if len(values) != self.backend.dimensions:
            raise ValueError(
                "backend vector dimensions do not match the declared dimensions"
            )
        if not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in values
        ):
            raise ValueError("backend vector values must be finite numbers")
        norm = math.sqrt(sum(float(value) * float(value) for value in values))
        if norm == 0.0:
            raise ValueError("backend returned a zero vector")
        return [float(value) / norm for value in values]

    @staticmethod
    def _backend_error(chunk: TextChunk) -> EmbeddingError:
        return EmbeddingError(
            "text encoder failed for one chunk",
            file_id=chunk.file_id,
            chunk_id=chunk.chunk_id,
        )
