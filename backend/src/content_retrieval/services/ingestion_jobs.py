from dataclasses import dataclass, replace
from threading import Lock
from typing import Literal
from uuid import uuid4

from content_retrieval.domain.models import BatchResult


JobStatus = Literal[
    "queued",
    "running",
    "completed",
    "completed_with_errors",
    "failed",
]


@dataclass(frozen=True, slots=True)
class IngestionJob:
    job_id: str
    status: JobStatus
    result: BatchResult | None = None


class InMemoryIngestionJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, IngestionJob] = {}
        self._lock = Lock()

    def create(self) -> IngestionJob:
        job = IngestionJob(job_id=str(uuid4()), status="queued")
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> IngestionJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def mark_running(self, job_id: str) -> None:
        self._replace(job_id, status="running")

    def complete(self, job_id: str, result: BatchResult) -> None:
        status: JobStatus = (
            "completed_with_errors" if result.failed else "completed"
        )
        self._replace(job_id, status=status, result=result)

    def fail(self, job_id: str) -> None:
        self._replace(job_id, status="failed")

    def _replace(
        self,
        job_id: str,
        *,
        status: JobStatus,
        result: BatchResult | None = None,
    ) -> None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = replace(
                current,
                status=status,
                result=result,
            )
