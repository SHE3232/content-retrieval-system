from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from uuid import UUID

from content_retrieval.api.routes.ingestion import _job_response
from content_retrieval.api.schemas import CreateIngestionJobRequest
from content_retrieval.domain.errors import CorruptedFileError, ParseTimeoutError
from content_retrieval.domain.models import BatchResult, ParseResult, SkippedFile
from content_retrieval.services.ingestion_jobs import (
    IngestionJob,
    InMemoryIngestionJobStore,
)


def sample_result(path: Path = Path("sample.txt")) -> ParseResult:
    content = b"sample"
    return ParseResult(
        file_id=hashlib.sha256(content).hexdigest(),
        path=path,
        name=path.name,
        mime_type="text/plain",
        modality="text",
        size_bytes=len(content),
        modified_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
        text="sample",
        metadata={"encoding": "utf-8"},
        warnings=["fixture warning"],
    )


def test_tc_181_created_job_id_is_valid_uuid() -> None:
    job = InMemoryIngestionJobStore().create()

    assert str(UUID(job.job_id)) == job.job_id


def test_tc_182_sequential_job_ids_are_unique() -> None:
    store = InMemoryIngestionJobStore()

    identifiers = {store.create().job_id for _ in range(100)}

    assert len(identifiers) == 100


def test_tc_183_queued_job_response_has_zero_counts() -> None:
    response = _job_response(IngestionJob(job_id="queued", status="queued"))

    assert response.status == "queued"
    assert response.counts.model_dump() == {
        "total": 0,
        "pending": 0,
        "running": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
    }


def test_tc_184_running_job_response_has_zero_counts() -> None:
    response = _job_response(IngestionJob(job_id="running", status="running"))

    assert response.status == "running"
    assert response.results == response.errors == response.skips == []


def test_tc_185_failed_job_response_has_zero_counts() -> None:
    response = _job_response(IngestionJob(job_id="failed", status="failed"))

    assert response.status == "failed"
    assert response.counts.total == 0


def test_tc_186_completed_job_response_serializes_parse_result() -> None:
    result = sample_result()
    response = _job_response(
        IngestionJob(
            job_id="completed",
            status="completed",
            result=BatchResult(results=[result]),
        )
    )

    serialized = response.results[0]
    assert serialized.file_id == result.file_id
    assert serialized.text == "sample"
    assert serialized.metadata == {"encoding": "utf-8"}
    assert serialized.warnings == ["fixture warning"]


def test_tc_187_completed_with_errors_serializes_controlled_error() -> None:
    error = CorruptedFileError(Path("broken.pdf"), "invalid trailer")
    response = _job_response(
        IngestionJob(
            job_id="partial",
            status="completed_with_errors",
            result=BatchResult(errors=[error]),
        )
    )

    assert response.counts.failed == 1
    assert response.errors[0].model_dump() == {
        "path": Path("broken.pdf"),
        "code": "CORRUPTED_FILE",
        "message": "Corrupted file broken.pdf: invalid trailer",
        "retryable": False,
    }


def test_tc_188_retryable_error_flag_is_exposed() -> None:
    response = _job_response(
        IngestionJob(
            job_id="timeout",
            status="completed_with_errors",
            result=BatchResult(errors=[ParseTimeoutError(Path("slow.docx"))]),
        )
    )

    assert response.errors[0].code == "PARSE_TIMEOUT"
    assert response.errors[0].retryable is True


def test_tc_189_duplicate_skip_serializes_origin_and_hash() -> None:
    duplicate = SkippedFile(
        path=Path("copy.txt"),
        reason="duplicate_content",
        file_id="a" * 64,
        duplicate_of=Path("original.txt"),
    )
    response = _job_response(
        IngestionJob(
            job_id="duplicate",
            status="completed",
            result=BatchResult(skips=[duplicate]),
        )
    )

    assert response.skips[0].model_dump() == {
        "path": Path("copy.txt"),
        "reason": "duplicate_content",
        "file_id": "a" * 64,
        "duplicate_of": Path("original.txt"),
    }


def test_tc_190_response_counts_match_mixed_batch() -> None:
    response = _job_response(
        IngestionJob(
            job_id="mixed",
            status="completed_with_errors",
            result=BatchResult(
                results=[sample_result()],
                errors=[CorruptedFileError(Path("bad.pdf"), "bad")],
                skips=[SkippedFile(Path("ignored.bin"), "unsupported_format")],
            ),
        )
    )

    assert response.counts.model_dump() == {
        "total": 3,
        "pending": 0,
        "running": 0,
        "succeeded": 1,
        "failed": 1,
        "skipped": 1,
    }


def test_tc_191_request_recursive_option_defaults_to_true() -> None:
    request = CreateIngestionJobRequest(
        paths=[Path("source.txt")],
        authorized_roots=[Path(".")],
    )

    assert request.recursive is True


def test_tc_192_job_store_is_thread_safe_for_parallel_creates() -> None:
    store = InMemoryIngestionJobStore()

    with ThreadPoolExecutor(max_workers=8) as executor:
        jobs = list(executor.map(lambda _: store.create(), range(200)))

    assert len({job.job_id for job in jobs}) == 200
    assert all(store.get(job.job_id) == job for job in jobs)
