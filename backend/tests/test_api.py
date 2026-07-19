import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from content_retrieval.domain.errors import CorruptedFileError
from content_retrieval.domain.models import BatchResult
from content_retrieval.parsers.registry import ParserRegistry
from content_retrieval.parsers.txt import TxtParser
from content_retrieval.services.batch_ingestion import BatchIngestionService


def make_ingestion_service() -> BatchIngestionService:
    return BatchIngestionService(
        ParserRegistry([TxtParser()]),
        max_file_size_bytes=1024,
    )


async def wait_for_terminal_job(
    client: AsyncClient,
    job_id: str,
) -> tuple[int, dict[str, object]]:
    for _ in range(100):
        response = await client.get(f"/v1/ingestion/jobs/{job_id}")
        payload = response.json()
        if payload["status"] not in {"queued", "running"}:
            return response.status_code, payload
        await asyncio.sleep(0.01)
    pytest.fail("ingestion job did not reach a terminal state")


def test_job_store_creates_and_transitions_a_job() -> None:
    from content_retrieval.services.ingestion_jobs import (
        InMemoryIngestionJobStore,
    )

    store = InMemoryIngestionJobStore()

    queued = store.create()
    store.mark_running(queued.job_id)
    running = store.get(queued.job_id)

    assert queued.status == "queued"
    assert running is not None
    assert running.status == "running"
    assert running is not queued
    assert store.get("missing") is None


def test_job_store_marks_successful_batch_completed() -> None:
    from content_retrieval.services.ingestion_jobs import (
        InMemoryIngestionJobStore,
    )

    store = InMemoryIngestionJobStore()
    job = store.create()
    result = BatchResult()

    store.complete(job.job_id, result)

    completed = store.get(job.job_id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.result is result


def test_job_store_marks_batch_with_errors_completed_with_errors() -> None:
    from content_retrieval.services.ingestion_jobs import (
        InMemoryIngestionJobStore,
    )

    store = InMemoryIngestionJobStore()
    job = store.create()
    result = BatchResult(
        errors=[CorruptedFileError(Path("broken.pdf"), "invalid fixture")]
    )

    store.complete(job.job_id, result)

    completed = store.get(job.job_id)
    assert completed is not None
    assert completed.status == "completed_with_errors"
    assert completed.result is result


def test_job_store_marks_unexpected_task_failure() -> None:
    from content_retrieval.services.ingestion_jobs import (
        InMemoryIngestionJobStore,
    )

    store = InMemoryIngestionJobStore()
    job = store.create()

    store.fail(job.job_id)

    failed = store.get(job.job_id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.result is None


@pytest.mark.anyio
async def test_live_health_endpoint_reports_process_is_alive() -> None:
    from content_retrieval.api.app import create_app

    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_ready_health_endpoint_reports_services_are_initialized() -> None:
    from content_retrieval.api.app import create_app

    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.anyio
async def test_ready_health_endpoint_reports_unavailable_service() -> None:
    from content_retrieval.api.app import create_app

    app = create_app()
    app.state.ready = False
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


@pytest.mark.anyio
async def test_api_creates_and_queries_mixed_path_ingestion_job(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    explicit = tmp_path / "explicit.txt"
    explicit.write_text("explicit result", encoding="utf-8")
    directory = tmp_path / "reports"
    directory.mkdir()
    nested = directory / "nested.txt"
    nested.write_text("nested result", encoding="utf-8")

    app = create_app(make_ingestion_service())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/v1/ingestion/jobs",
            json={
                "paths": [str(explicit), str(directory)],
                "authorized_roots": [str(tmp_path)],
                "recursive": True,
            },
        )

        assert created.status_code == 202
        created_payload = created.json()
        assert created_payload["status"] == "queued"

        query_status, payload = await wait_for_terminal_job(
            client,
            created_payload["job_id"],
        )

    assert query_status == 200
    assert payload["status"] == "completed"
    assert payload["counts"] == {
        "total": 2,
        "pending": 0,
        "running": 0,
        "succeeded": 2,
        "failed": 0,
        "skipped": 0,
    }
    assert [result["text"] for result in payload["results"]] == [
        "explicit result",
        "nested result",
    ]
    assert [Path(result["path"]) for result in payload["results"]] == [
        explicit.resolve(),
        nested.resolve(),
    ]
    assert all(result["modified_at"] for result in payload["results"])
    assert payload["errors"] == []
    assert payload["skips"] == []


@pytest.mark.anyio
async def test_api_returns_structured_error_for_unknown_job() -> None:
    from content_retrieval.api.app import create_app

    async with AsyncClient(
        transport=ASGITransport(app=create_app(make_ingestion_service())),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/v1/ingestion/jobs/unknown")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "JOB_NOT_FOUND",
            "message": "Ingestion job not found",
        }
    }


@pytest.mark.anyio
@pytest.mark.parametrize("empty_field", ["paths", "authorized_roots"])
async def test_api_rejects_empty_path_lists(
    tmp_path: Path,
    empty_field: str,
) -> None:
    from content_retrieval.api.app import create_app

    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    payload = {
        "paths": [str(source)],
        "authorized_roots": [str(tmp_path)],
        "recursive": True,
    }
    payload[empty_field] = []

    async with AsyncClient(
        transport=ASGITransport(app=create_app(make_ingestion_service())),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/v1/ingestion/jobs", json=payload)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_api_reports_file_errors_and_directory_skips(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    valid = tmp_path / "valid.txt"
    valid.write_text("valid", encoding="utf-8")
    unsupported = tmp_path / "explicit.bin"
    unsupported.write_bytes(b"explicit")
    directory = tmp_path / "directory"
    directory.mkdir()
    ignored = directory / "ignored.bin"
    ignored.write_bytes(b"ignored")
    missing = tmp_path / "missing.txt"

    async with AsyncClient(
        transport=ASGITransport(app=create_app(make_ingestion_service())),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/v1/ingestion/jobs",
            json={
                "paths": [
                    str(valid),
                    str(unsupported),
                    str(directory),
                    str(missing),
                ],
                "authorized_roots": [str(tmp_path)],
                "recursive": True,
            },
        )
        query_status, payload = await wait_for_terminal_job(
            client,
            created.json()["job_id"],
        )

    assert query_status == 200
    assert payload["status"] == "completed_with_errors"
    assert payload["counts"] == {
        "total": 4,
        "pending": 0,
        "running": 0,
        "succeeded": 1,
        "failed": 2,
        "skipped": 1,
    }
    assert [error["code"] for error in payload["errors"]] == [
        "UNSUPPORTED_FORMAT",
        "PATH_NOT_FOUND",
    ]
    assert payload["skips"] == [
        {
            "path": str(ignored.resolve()),
            "reason": "unsupported_format",
            "file_id": None,
            "duplicate_of": None,
        }
    ]


@pytest.mark.anyio
async def test_api_passes_non_recursive_option_to_service(tmp_path: Path) -> None:
    from content_retrieval.api.app import create_app

    directory = tmp_path / "directory"
    directory.mkdir()
    visible = directory / "visible.txt"
    visible.write_text("visible", encoding="utf-8")
    nested_directory = directory / "nested"
    nested_directory.mkdir()
    (nested_directory / "hidden.txt").write_text("hidden", encoding="utf-8")

    async with AsyncClient(
        transport=ASGITransport(app=create_app(make_ingestion_service())),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/v1/ingestion/jobs",
            json={
                "paths": [str(directory)],
                "authorized_roots": [str(tmp_path)],
                "recursive": False,
            },
        )
        query_status, payload = await wait_for_terminal_job(
            client,
            created.json()["job_id"],
        )

    assert query_status == 200
    assert payload["counts"]["total"] == 1
    assert [Path(result["path"]) for result in payload["results"]] == [
        visible.resolve()
    ]
