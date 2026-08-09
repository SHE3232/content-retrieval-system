from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Lock
from typing import Literal
from uuid import uuid4

from content_retrieval.domain.errors import ProcessingError
from content_retrieval.domain.retrieval import IndexingResult


IndexingJobStatus = Literal[
    "queued",
    "running",
    "completed",
    "completed_with_errors",
    "failed",
]


@dataclass(frozen=True, slots=True)
class IndexingJobError:
    code: str
    message: str
    retryable: bool

    @classmethod
    def from_exception(cls, error: Exception) -> IndexingJobError:
        if isinstance(error, ProcessingError):
            return cls(
                code=error.code,
                message=str(error),
                retryable=error.retryable,
            )
        return cls(
            code="INDEXING_JOB_FAILED",
            message="Indexing job failed unexpectedly",
            retryable=True,
        )


@dataclass(frozen=True, slots=True)
class IndexingJob:
    job_id: str
    status: IndexingJobStatus
    result: IndexingResult | None = None
    error: IndexingJobError | None = None


class InMemoryIndexingJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, IndexingJob] = {}
        self._lock = Lock()

    def create(self) -> IndexingJob:
        job = IndexingJob(job_id=str(uuid4()), status="queued")
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> IndexingJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def mark_running(self, job_id: str) -> None:
        self._replace(job_id, status="running")

    def complete(self, job_id: str, result: IndexingResult) -> None:
        status: IndexingJobStatus = (
            "completed_with_errors"
            if result.failed_files or result.partial_files
            else "completed"
        )
        self._replace(job_id, status=status, result=result)

    def fail(
        self,
        job_id: str,
        error: IndexingJobError | None = None,
    ) -> None:
        self._replace(
            job_id,
            status="failed",
            error=error
            or IndexingJobError(
                code="INDEXING_JOB_FAILED",
                message="Indexing job failed unexpectedly",
                retryable=True,
            ),
        )

    def _replace(
        self,
        job_id: str,
        *,
        status: IndexingJobStatus,
        result: IndexingResult | None = None,
        error: IndexingJobError | None = None,
    ) -> None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = replace(
                current,
                status=status,
                result=result,
                error=error,
            )
