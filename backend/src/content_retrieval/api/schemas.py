from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from content_retrieval.domain.models import Modality, SkipReason
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
