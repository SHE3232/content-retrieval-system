from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from content_retrieval.domain.models import Modality, SkipReason
from content_retrieval.domain.retrieval import (
    SearchChannel,
    SearchFilters,
    SearchModality,
)
from content_retrieval.services.indexing_jobs import IndexingJobStatus
from content_retrieval.services.ingestion_jobs import JobStatus


class CreateIngestionJobRequest(BaseModel):
    paths: list[Path] = Field(min_length=1)
    authorized_roots: list[Path] = Field(min_length=1)
    recursive: bool = True


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobCountsResponse(BaseModel):
    total: int
    pending: int
    running: int
    succeeded: int
    failed: int
    skipped: int


class ParseResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: str
    path: Path
    name: str
    mime_type: str
    modality: Modality
    size_bytes: int
    modified_at: datetime
    text: str | None = None
    page_count: int | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class JobErrorResponse(BaseModel):
    path: Path
    code: str
    message: str
    retryable: bool


class JobSkipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: Path
    reason: SkipReason
    file_id: str | None = None
    duplicate_of: Path | None = None


class IngestionJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    counts: JobCountsResponse
    results: list[ParseResultResponse]
    errors: list[JobErrorResponse]
    skips: list[JobSkipResponse]


class CreateIndexingJobRequest(BaseModel):
    paths: list[Path] = Field(min_length=1)
    authorized_roots: list[Path] = Field(min_length=1)
    recursive: bool = True


class IndexingJobCreatedResponse(BaseModel):
    job_id: str
    status: IndexingJobStatus


class IndexingFailureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: Path
    code: str
    message: str
    stage: str
    retryable: bool
    file_id: str | None = None
    source_id: str | None = None


class IndexingResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parsed_files: int
    indexed_files: int
    indexed_records: int
    skipped_files: int
    failed_files: int
    partial_files: int
    unchanged_files: int
    removed_stale_records: int
    failures: list[IndexingFailureResponse]


class IndexingJobResponse(BaseModel):
    job_id: str
    status: IndexingJobStatus
    result: IndexingResultResponse | None = None


class IndexingJobErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    message: str
    retryable: bool


class IndexingFailuresResponse(BaseModel):
    job_id: str
    status: IndexingJobStatus
    total: int
    failures: list[IndexingFailureResponse]
    error: IndexingJobErrorResponse | None = None


class SearchFiltersRequest(BaseModel):
    mime_types: tuple[str, ...] = ()
    modalities: tuple[SearchModality, ...] = ()
    path_prefix: Path | None = None
    modified_after: datetime | None = None
    modified_before: datetime | None = None

    def to_domain(self) -> SearchFilters:
        return SearchFilters(
            mime_types=self.mime_types,
            modalities=self.modalities,
            path_prefix=self.path_prefix,
            modified_after=self.modified_after,
            modified_before=self.modified_before,
        )


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    filters: SearchFiltersRequest = Field(
        default_factory=SearchFiltersRequest
    )
    channels: tuple[SearchChannel, ...] = Field(
        default=(
            "keyword",
            "text_semantic",
            "image_semantic",
        ),
        min_length=1,
    )
    weights: dict[str, float] | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, query: str) -> str:
        normalized = " ".join(query.split())
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized

    @field_validator("channels")
    @classmethod
    def validate_channels(
        cls,
        channels: tuple[SearchChannel, ...],
    ) -> tuple[SearchChannel, ...]:
        if len(set(channels)) != len(channels):
            raise ValueError("channels must be unique")
        return channels

    @field_validator("weights")
    @classmethod
    def validate_weights(
        cls,
        weights: dict[str, float] | None,
    ) -> dict[str, float] | None:
        if weights is None:
            return None
        valid_channels = {
            "keyword",
            "text_semantic",
            "image_semantic",
        }
        if set(weights) - valid_channels:
            raise ValueError("weights contain an unsupported channel")
        if any(weight <= 0 for weight in weights.values()):
            raise ValueError("weights must be positive")
        return weights


class SearchHitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: str
    source_id: str
    path: Path
    name: str
    mime_type: str
    modality: SearchModality
    score: float
    match_reasons: list[SearchChannel]
    snippet: str | None
    page_number: int | None
    paragraph_number: int | None


class SearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query: str
    hits: list[SearchHitResponse]
    total_candidates: int
    elapsed_ms: float
    weights: dict[str, float]


class IndexStatsResponse(BaseModel):
    record_count: int
    file_count: int
    text_record_count: int
    image_record_count: int


class IndexedFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_key: str
    file_id: str
    path: Path
    name: str
    mime_type: str
    modality: SearchModality
    size_bytes: int
    modified_at: datetime
    record_count: int


class IndexedFilePageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[IndexedFileResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class DeletedIndexedFileResponse(BaseModel):
    source_key: str
    deleted_records: int
