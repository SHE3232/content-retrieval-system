import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from content_retrieval.domain.errors import StorageError
from content_retrieval.domain.retrieval import (
    IndexingFailure,
    IndexingResult,
)
from content_retrieval.services.index_catalog import (
    IndexedFile,
    IndexedFilePage,
)
from content_retrieval.services.indexing_jobs import IndexingJobError


SOURCE_KEY = "a" * 64
MODIFIED_AT = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)


def make_indexed_file(path: Path) -> IndexedFile:
    return IndexedFile(
        source_key=SOURCE_KEY,
        file_id="b" * 64,
        path=path.resolve(),
        name=path.name,
        mime_type="text/plain",
        modality="text",
        size_bytes=12,
        modified_at=MODIFIED_AT,
        record_count=2,
    )


class FakeCatalogService:
    def __init__(
        self,
        indexed_file: IndexedFile | None = None,
        *,
        list_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self.indexed_file = indexed_file
        self.list_error = list_error
        self.delete_error = delete_error
        self.list_calls: list[tuple[int, int]] = []
        self.get_calls: list[str] = []
        self.delete_calls: list[str] = []

    def list_files(self, *, page: int, page_size: int) -> IndexedFilePage:
        self.list_calls.append((page, page_size))
        if self.list_error is not None:
            raise self.list_error
        items = () if self.indexed_file is None else (self.indexed_file,)
        return IndexedFilePage(
            items=items,
            page=page,
            page_size=page_size,
            total=2 if items else 0,
            total_pages=2 if items else 0,
        )

    def get_file(self, source_key: str) -> IndexedFile | None:
        self.get_calls.append(source_key)
        return self.indexed_file if source_key == SOURCE_KEY else None

    def delete_file(self, source_key: str) -> int | None:
        self.delete_calls.append(source_key)
        if self.delete_error is not None:
            raise self.delete_error
        if self.indexed_file is None or source_key != SOURCE_KEY:
            return None
        return self.indexed_file.record_count


class RefreshOnlyRetrievalService:
    def __init__(self) -> None:
        self.refresh_calls = 0

    def refresh(self) -> None:
        self.refresh_calls += 1


class FakeIndexingService:
    def __init__(self) -> None:
        self.calls: list[
            tuple[list[Path], bool, list[Path], bool]
        ] = []

    def index_paths(
        self,
        paths: list[Path],
        *,
        recursive: bool,
        authorized_roots: list[Path],
        force: bool = False,
    ) -> IndexingResult:
        self.calls.append((paths, recursive, authorized_roots, force))
        return IndexingResult(
            parsed_files=1,
            indexed_files=1,
            indexed_records=2,
            skipped_files=0,
            failed_files=0,
            partial_files=0,
            unchanged_files=0,
            removed_stale_records=0,
        )


async def wait_for_index_job(
    client: AsyncClient,
    job_id: str,
) -> dict[str, object]:
    for _ in range(100):
        response = await client.get(f"/v1/indexing/jobs/{job_id}")
        payload = response.json()
        if payload["status"] not in {"queued", "running"}:
            return payload
        await asyncio.sleep(0.01)
    pytest.fail("indexing job did not reach a terminal state")


@pytest.mark.anyio
async def test_list_indexed_files_serializes_file_page(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    indexed_file = make_indexed_file(tmp_path / "notes.txt")
    catalog = FakeCatalogService(indexed_file)
    app = create_app(index_catalog_service=catalog)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/v1/index/files",
            params={"page": 2, "page_size": 1},
        )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "source_key": SOURCE_KEY,
                "file_id": "b" * 64,
                "path": str(indexed_file.path),
                "name": "notes.txt",
                "mime_type": "text/plain",
                "modality": "text",
                "size_bytes": 12,
                "modified_at": "2026-08-09T10:00:00Z",
                "record_count": 2,
            }
        ],
        "page": 2,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }
    assert catalog.list_calls == [(2, 1)]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "query",
    ["page=0", "page_size=0", "page_size=101"],
)
async def test_list_indexed_files_rejects_invalid_pagination(
    query: str,
) -> None:
    from content_retrieval.api.app import create_app

    app = create_app(index_catalog_service=FakeCatalogService())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/v1/index/files?{query}")

    assert response.status_code == 422


@pytest.mark.anyio
async def test_delete_indexed_file_refreshes_retrieval(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    source = tmp_path / "notes.txt"
    source.write_text("keep the source file", encoding="utf-8")
    catalog = FakeCatalogService(make_indexed_file(source))
    retrieval = RefreshOnlyRetrievalService()
    app = create_app(
        index_catalog_service=catalog,
        retrieval_service=retrieval,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete(f"/v1/index/files/{SOURCE_KEY}")

    assert response.status_code == 200
    assert response.json() == {
        "source_key": SOURCE_KEY,
        "deleted_records": 2,
    }
    assert catalog.delete_calls == [SOURCE_KEY]
    assert retrieval.refresh_calls == 1
    assert source.read_text(encoding="utf-8") == "keep the source file"


@pytest.mark.anyio
async def test_delete_unknown_indexed_file_has_structured_404() -> None:
    from content_retrieval.api.app import create_app

    app = create_app(index_catalog_service=FakeCatalogService())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete(f"/v1/index/files/{SOURCE_KEY}")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "FILE_NOT_INDEXED",
            "message": "Indexed file not found",
        }
    }


@pytest.mark.anyio
@pytest.mark.parametrize("source_key", ["short", "A" * 64, "g" * 64])
async def test_file_actions_reject_invalid_source_key(
    source_key: str,
) -> None:
    from content_retrieval.api.app import create_app

    app = create_app(index_catalog_service=FakeCatalogService())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete(f"/v1/index/files/{source_key}")

    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["list", "delete"])
async def test_file_catalog_storage_failure_has_structured_503(
    tmp_path: Path,
    operation: str,
) -> None:
    from content_retrieval.api.app import create_app

    error = StorageError("local catalog unavailable")
    catalog = FakeCatalogService(
        make_indexed_file(tmp_path / "notes.txt"),
        list_error=error if operation == "list" else None,
        delete_error=error if operation == "delete" else None,
    )
    app = create_app(index_catalog_service=catalog)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        if operation == "list":
            response = await client.get("/v1/index/files")
        else:
            response = await client.delete(
                f"/v1/index/files/{SOURCE_KEY}"
            )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "STORAGE_UNAVAILABLE",
            "message": "Local index is unavailable",
        }
    }


@pytest.mark.anyio
async def test_reindex_file_creates_forced_background_job(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    source = tmp_path / "notes.txt"
    source.write_text("local notes", encoding="utf-8")
    catalog = FakeCatalogService(make_indexed_file(source))
    indexing = FakeIndexingService()
    retrieval = RefreshOnlyRetrievalService()
    app = create_app(
        indexing_service=indexing,
        index_catalog_service=catalog,
        retrieval_service=retrieval,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            f"/v1/index/files/{SOURCE_KEY}/reindex"
        )
        assert created.status_code == 202
        assert created.json()["status"] == "queued"
        completed = await wait_for_index_job(
            client,
            created.json()["job_id"],
        )

    assert completed["status"] == "completed"
    assert indexing.calls == [
        ([source.resolve()], False, [source.parent.resolve()], True)
    ]
    assert retrieval.refresh_calls == 1


@pytest.mark.anyio
async def test_reindex_unknown_file_has_structured_404() -> None:
    from content_retrieval.api.app import create_app

    app = create_app(
        indexing_service=FakeIndexingService(),
        index_catalog_service=FakeCatalogService(),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"/v1/index/files/{SOURCE_KEY}/reindex"
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "FILE_NOT_INDEXED",
            "message": "Indexed file not found",
        }
    }


@pytest.mark.anyio
async def test_reindex_missing_source_file_has_structured_404(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    missing = tmp_path / "missing.txt"
    app = create_app(
        indexing_service=FakeIndexingService(),
        index_catalog_service=FakeCatalogService(
            make_indexed_file(missing)
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"/v1/index/files/{SOURCE_KEY}/reindex"
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "SOURCE_FILE_NOT_FOUND",
            "message": "Source file no longer exists",
        }
    }


@pytest.mark.anyio
async def test_indexing_failure_details_serialize_file_failures(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    failed_path = (tmp_path / "broken.pdf").resolve()
    app = create_app(indexing_service=FakeIndexingService())
    job = app.state.indexing_job_store.create()
    app.state.indexing_job_store.complete(
        job.job_id,
        IndexingResult(
            parsed_files=1,
            indexed_files=0,
            indexed_records=0,
            skipped_files=0,
            failed_files=1,
            partial_files=0,
            unchanged_files=0,
            removed_stale_records=0,
            failures=(
                IndexingFailure(
                    path=failed_path,
                    code="CORRUPTED_FILE",
                    message="Cannot parse broken.pdf",
                    stage="parsing",
                    retryable=False,
                    file_id="b" * 64,
                ),
            ),
        ),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/v1/indexing/jobs/{job.job_id}/failures"
        )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job.job_id,
        "status": "completed_with_errors",
        "total": 1,
        "failures": [
            {
                "path": str(failed_path),
                "code": "CORRUPTED_FILE",
                "message": "Cannot parse broken.pdf",
                "stage": "parsing",
                "retryable": False,
                "file_id": "b" * 64,
                "source_id": None,
            }
        ],
        "error": None,
    }


@pytest.mark.anyio
async def test_indexing_failure_details_serialize_task_error() -> None:
    from content_retrieval.api.app import create_app

    app = create_app(indexing_service=FakeIndexingService())
    job = app.state.indexing_job_store.create()
    app.state.indexing_job_store.fail(
        job.job_id,
        IndexingJobError(
            code="STORAGE_ERROR",
            message="local index is locked",
            retryable=True,
        ),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/v1/indexing/jobs/{job.job_id}/failures"
        )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job.job_id,
        "status": "failed",
        "total": 0,
        "failures": [],
        "error": {
            "code": "STORAGE_ERROR",
            "message": "local index is locked",
            "retryable": True,
        },
    }


@pytest.mark.anyio
async def test_unknown_indexing_failure_details_have_structured_404() -> None:
    from content_retrieval.api.app import create_app

    app = create_app(indexing_service=FakeIndexingService())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/v1/indexing/jobs/missing/failures"
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "JOB_NOT_FOUND",
            "message": "Indexing job not found",
        }
    }
