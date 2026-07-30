import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from content_retrieval.domain.retrieval import (
    IndexingResult,
    SearchFilters,
    SearchHit,
    SearchResult,
)


class FakeIndexingService:
    def __init__(self) -> None:
        self.calls: list[tuple[list[Path], bool, list[Path]]] = []

    def index_paths(
        self,
        paths: list[Path],
        *,
        recursive: bool,
        authorized_roots: list[Path],
    ) -> IndexingResult:
        self.calls.append((paths, recursive, authorized_roots))
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


class FakeRepository:
    def list_records(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(file_id="a" * 64, modality="text"),
            SimpleNamespace(file_id="a" * 64, modality="text"),
            SimpleNamespace(file_id="b" * 64, modality="image"),
        ]


class FakeRetrievalService:
    def __init__(self, result_path: Path) -> None:
        self.result_path = result_path
        self.repository = FakeRepository()
        self.calls: list[dict[str, object]] = []
        self.refresh_calls = 0

    def search(
        self,
        query: str,
        *,
        top_k: int,
        filters: SearchFilters,
        channels: tuple[str, ...],
        weights: dict[str, float] | None,
    ) -> SearchResult:
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "filters": filters,
                "channels": channels,
                "weights": weights,
            }
        )
        return SearchResult(
            query=query,
            hits=(
                SearchHit(
                    file_id="a" * 64,
                    source_id="c" * 64,
                    path=self.result_path,
                    name=self.result_path.name,
                    mime_type="text/plain",
                    modality="text",
                    score=0.75,
                    match_reasons=("keyword", "text_semantic"),
                    snippet="local notes",
                    page_number=None,
                    paragraph_number=1,
                ),
            ),
            total_candidates=1,
            elapsed_ms=3.5,
            weights={"keyword": 0.35, "text_semantic": 1.0},
        )

    def refresh(self) -> None:
        self.refresh_calls += 1


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
async def test_indexing_job_runs_in_background_and_refreshes_search(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    source = tmp_path / "notes.txt"
    source.write_text("local notes", encoding="utf-8")
    indexing = FakeIndexingService()
    retrieval = FakeRetrievalService(source.resolve())
    app = create_app(
        indexing_service=indexing,
        retrieval_service=retrieval,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/v1/indexing/jobs",
            json={
                "paths": [str(source)],
                "authorized_roots": [str(tmp_path)],
                "recursive": False,
            },
        )
        assert created.status_code == 202
        assert created.json()["status"] == "queued"
        payload = await wait_for_index_job(client, created.json()["job_id"])

    assert payload["status"] == "completed"
    assert payload["result"] == {
        "parsed_files": 1,
        "indexed_files": 1,
        "indexed_records": 2,
        "skipped_files": 0,
        "failed_files": 0,
        "partial_files": 0,
        "unchanged_files": 0,
        "removed_stale_records": 0,
        "failures": [],
    }
    assert indexing.calls == [
        ([source], False, [tmp_path])
    ]
    assert retrieval.refresh_calls == 1


@pytest.mark.anyio
async def test_search_serializes_hits_and_passes_filters(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    result_path = (tmp_path / "notes.txt").resolve()
    retrieval = FakeRetrievalService(result_path)
    app = create_app(retrieval_service=retrieval)
    after = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/v1/search",
            json={
                "query": "local notes",
                "top_k": 5,
                "channels": ["keyword", "text_semantic"],
                "weights": {"keyword": 0.35, "text_semantic": 1.0},
                "filters": {
                    "mime_types": ["text/plain"],
                    "modalities": ["text"],
                    "path_prefix": str(tmp_path.resolve()),
                    "modified_after": after.isoformat(),
                },
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "query": "local notes",
        "hits": [
            {
                "file_id": "a" * 64,
                "source_id": "c" * 64,
                "path": str(result_path),
                "name": "notes.txt",
                "mime_type": "text/plain",
                "modality": "text",
                "score": 0.75,
                "match_reasons": ["keyword", "text_semantic"],
                "snippet": "local notes",
                "page_number": None,
                "paragraph_number": 1,
            }
        ],
        "total_candidates": 1,
        "elapsed_ms": 3.5,
        "weights": {"keyword": 0.35, "text_semantic": 1.0},
    }
    call = retrieval.calls[0]
    assert call["top_k"] == 5
    assert call["channels"] == ("keyword", "text_semantic")
    assert call["weights"] == {"keyword": 0.35, "text_semantic": 1.0}
    filters = call["filters"]
    assert isinstance(filters, SearchFilters)
    assert filters.mime_types == ("text/plain",)
    assert filters.modalities == ("text",)
    assert filters.path_prefix == tmp_path.resolve()
    assert filters.modified_after == after


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"query": "   ", "top_k": 5},
        {"query": "notes", "top_k": 0},
        {"query": "notes", "top_k": 101},
        {"query": "notes", "channels": []},
        {"query": "notes", "channels": ["unknown"]},
    ],
)
async def test_search_rejects_invalid_requests(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    from content_retrieval.api.app import create_app

    app = create_app(retrieval_service=FakeRetrievalService(tmp_path.resolve()))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/v1/search", json=payload)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_unknown_indexing_job_has_structured_404(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    app = create_app(indexing_service=FakeIndexingService())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/v1/indexing/jobs/missing")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "JOB_NOT_FOUND",
            "message": "Indexing job not found",
        }
    }


@pytest.mark.anyio
async def test_index_stats_reports_records_files_and_modalities(
    tmp_path: Path,
) -> None:
    from content_retrieval.api.app import create_app

    app = create_app(retrieval_service=FakeRetrievalService(tmp_path.resolve()))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/v1/index/stats")

    assert response.status_code == 200
    assert response.json() == {
        "record_count": 3,
        "file_count": 2,
        "text_record_count": 2,
        "image_record_count": 1,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "post",
            "/v1/indexing/jobs",
            {
                "paths": ["C:/offline/notes.txt"],
                "authorized_roots": ["C:/offline"],
            },
        ),
        ("post", "/v1/search", {"query": "notes"}),
        ("get", "/v1/index/stats", None),
    ],
)
async def test_unconfigured_week4_services_return_stable_503(
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    from content_retrieval.api.app import create_app

    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.request(method, path, json=payload)

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "SERVICE_UNAVAILABLE",
            "message": "Week 4 search runtime is not configured",
        }
    }
