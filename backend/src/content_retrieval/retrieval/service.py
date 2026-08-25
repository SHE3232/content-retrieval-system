from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from time import perf_counter

from content_retrieval.domain.errors import RetrievalError, StorageError
from content_retrieval.domain.retrieval import (
    SearchChannel,
    SearchFilters,
    SearchHit,
    SearchResult,
)
from content_retrieval.embeddings.service import MultimodalEmbeddingService
from content_retrieval.retrieval.fusion import RankedCandidate, weighted_rrf
from content_retrieval.retrieval.keyword import KeywordIndex
from content_retrieval.storage.chroma import ChromaVectorRepository


DEFAULT_SEARCH_WEIGHTS: dict[SearchChannel, float] = {
    "keyword": 0.35,
    "text_semantic": 1.0,
    "image_semantic": 0.85,
}
DEFAULT_SEMANTIC_MIN_SCORES: dict[SearchChannel, float] = {
    "text_semantic": 0.10,
    "image_semantic": 0.15,
}
DEFAULT_SEARCH_CHANNELS: tuple[SearchChannel, ...] = (
    "keyword",
    "text_semantic",
    "image_semantic",
)
_VALID_CHANNELS = frozenset(DEFAULT_SEARCH_CHANNELS)


class RetrievalService:
    """Run local keyword and dual-space semantic retrieval."""

    def __init__(
        self,
        *,
        repository: ChromaVectorRepository,
        embedding_service: MultimodalEmbeddingService,
    ) -> None:
        self.repository = repository
        self.embedding_service = embedding_service
        self.keyword_index = KeywordIndex()
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the volatile keyword catalog from persistent records."""
        try:
            records = self.repository.list_search_records()
        except StorageError as error:
            raise RetrievalError(
                "keyword catalog refresh failed"
            ) from error
        self.keyword_index.rebuild(records)

    def invalidate(self) -> None:
        """Clear volatile keyword state after a failed refresh."""
        self.keyword_index.rebuild(())

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: SearchFilters | None = None,
        channels: tuple[SearchChannel, ...] = DEFAULT_SEARCH_CHANNELS,
        weights: Mapping[str, float] | None = None,
    ) -> SearchResult:
        started = perf_counter()
        normalized_query = " ".join(query.split())
        if not normalized_query:
            raise RetrievalError("search query is empty")
        if not 1 <= top_k <= 100:
            raise ValueError("top_k must be between 1 and 100")
        if not channels or len(set(channels)) != len(channels):
            raise ValueError("search channels must be non-empty and unique")
        if any(channel not in _VALID_CHANNELS for channel in channels):
            raise ValueError("unsupported search channel")

        active_filters = filters or SearchFilters()
        active_channels = self._channels_allowed_by_filter(
            channels,
            active_filters,
        )
        resolved_weights = {
            channel: float(
                (weights or DEFAULT_SEARCH_WEIGHTS).get(
                    channel,
                    DEFAULT_SEARCH_WEIGHTS[channel],
                )
            )
            for channel in active_channels
        }
        candidate_limit = max(20, top_k * 5)
        ranked: dict[SearchChannel, list[RankedCandidate]] = {}

        if "keyword" in active_channels:
            ranked["keyword"] = self.keyword_index.search(
                normalized_query,
                limit=candidate_limit,
                filters=active_filters,
            )
        if "text_semantic" in active_channels:
            query_vector = self._text_query_vector(normalized_query)
            ranked["text_semantic"] = self._vector_candidates(
                query_vector,
                limit=candidate_limit,
                filters=active_filters,
                min_score=DEFAULT_SEMANTIC_MIN_SCORES["text_semantic"],
            )
        if "image_semantic" in active_channels:
            query_vector = self._image_query_vector(normalized_query)
            ranked["image_semantic"] = self._vector_candidates(
                query_vector,
                limit=candidate_limit,
                filters=active_filters,
                min_score=DEFAULT_SEMANTIC_MIN_SCORES["image_semantic"],
            )

        total_candidates = len(
            {
                candidate.record.file_id
                for candidates in ranked.values()
                for candidate in candidates
            }
        )
        fused = weighted_rrf(
            ranked,
            resolved_weights,
            limit=top_k,
        )
        hits = tuple(self._hit_from_fused(candidate) for candidate in fused)
        elapsed_ms = (perf_counter() - started) * 1000.0
        return SearchResult(
            query=normalized_query,
            hits=hits,
            total_candidates=total_candidates,
            elapsed_ms=elapsed_ms,
            weights=dict(resolved_weights),
        )

    @staticmethod
    def _channels_allowed_by_filter(
        channels: tuple[SearchChannel, ...],
        filters: SearchFilters,
    ) -> tuple[SearchChannel, ...]:
        allowed = list(channels)
        if filters.modalities:
            if "text" not in filters.modalities:
                allowed = [
                    channel
                    for channel in allowed
                    if channel != "text_semantic"
                ]
            if "image" not in filters.modalities:
                allowed = [
                    channel
                    for channel in allowed
                    if channel != "image_semantic"
                ]
        return tuple(allowed)

    def _text_query_vector(self, query: str):
        embedded = self.embedding_service.embed_text_queries([query])
        if embedded.errors or not embedded.items:
            raise RetrievalError("text query embedding failed")
        return embedded.items[0]

    def _image_query_vector(self, query: str):
        embedded = self.embedding_service.embed_image_queries([query])
        if embedded.errors or not embedded.items:
            raise RetrievalError("image query embedding failed")
        return embedded.items[0]

    def _vector_candidates(
        self,
        query_vector,
        *,
        limit: int,
        filters: SearchFilters,
        min_score: float,
    ):
        try:
            return self.repository.query(
                query_vector,
                limit=limit,
                filters=filters,
                min_score=min_score,
            )
        except StorageError as error:
            raise RetrievalError("local vector search failed") from error

    @staticmethod
    def _hit_from_fused(candidate) -> SearchHit:
        record = candidate.record
        snippet = (
            RetrievalService._snippet(record.document)
            if record.modality == "text"
            else None
        )
        return SearchHit(
            file_id=record.file_id,
            source_id=record.source_id,
            path=record.path,
            name=record.name,
            mime_type=record.mime_type,
            modality=record.modality,
            score=candidate.score,
            match_reasons=candidate.channels,
            snippet=snippet,
            page_number=record.page_number,
            paragraph_number=record.paragraph_number,
        )

    @staticmethod
    def _snippet(document: str, *, limit: int = 240) -> str:
        normalized = " ".join(document.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1].rstrip() + "…"
