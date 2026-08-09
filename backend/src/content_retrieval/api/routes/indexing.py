import asyncio
from typing import Annotated

from fastapi import (
    APIRouter,
    FastAPI,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)

from content_retrieval.api.schemas import (
    CreateIndexingJobRequest,
    DeletedIndexedFileResponse,
    IndexedFilePageResponse,
    IndexingFailuresResponse,
    IndexingJobCreatedResponse,
    IndexingJobErrorResponse,
    IndexingJobResponse,
    IndexingFailureResponse,
    IndexingResultResponse,
)
from content_retrieval.domain.errors import StorageError
from content_retrieval.services.index_catalog import IndexCatalogService
from content_retrieval.services.indexing import IndexingService
from content_retrieval.services.indexing_jobs import (
    InMemoryIndexingJobStore,
    IndexingJob,
    IndexingJobError,
)


router = APIRouter(prefix="/v1/indexing", tags=["indexing"])
index_router = APIRouter(prefix="/v1/index", tags=["indexing"])
SourceKey = Annotated[
    str,
    Path(pattern=r"^[0-9a-f]{64}$"),
]


@index_router.get("/files", response_model=IndexedFilePageResponse)
async def list_indexed_files(
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> IndexedFilePageResponse:
    service = _require_index_catalog_service(request.app)
    try:
        result = await asyncio.to_thread(
            service.list_files,
            page=page,
            page_size=page_size,
        )
    except StorageError as error:
        raise _storage_unavailable() from error
    return IndexedFilePageResponse.model_validate(result)


@index_router.delete(
    "/files/{source_key}",
    response_model=DeletedIndexedFileResponse,
)
async def delete_indexed_file(
    source_key: SourceKey,
    request: Request,
) -> DeletedIndexedFileResponse:
    service = _require_index_catalog_service(request.app)
    try:
        deleted = await asyncio.to_thread(
            service.delete_file,
            source_key,
        )
        if deleted is not None:
            retrieval_service = request.app.state.retrieval_service
            if retrieval_service is not None:
                await asyncio.to_thread(retrieval_service.refresh)
    except StorageError as error:
        raise _storage_unavailable() from error
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FILE_NOT_INDEXED",
                "message": "Indexed file not found",
            },
        )
    return DeletedIndexedFileResponse(
        source_key=source_key,
        deleted_records=deleted,
    )


@index_router.post(
    "/files/{source_key}/reindex",
    response_model=IndexingJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reindex_file(
    source_key: SourceKey,
    request: Request,
) -> IndexingJobCreatedResponse:
    _require_indexing_service(request.app)
    catalog = _require_index_catalog_service(request.app)
    try:
        indexed_file = await asyncio.to_thread(
            catalog.get_file,
            source_key,
        )
    except StorageError as error:
        raise _storage_unavailable() from error
    if indexed_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FILE_NOT_INDEXED",
                "message": "Indexed file not found",
            },
        )
    if not await asyncio.to_thread(indexed_file.path.is_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SOURCE_FILE_NOT_FOUND",
                "message": "Source file no longer exists",
            },
        )

    store: InMemoryIndexingJobStore = request.app.state.indexing_job_store
    job = store.create()
    payload = CreateIndexingJobRequest(
        paths=[indexed_file.path],
        authorized_roots=[indexed_file.path.parent],
        recursive=False,
    )
    task = asyncio.create_task(
        _run_job(request.app, job.job_id, payload, force=True)
    )
    background_tasks: set[asyncio.Task[None]] = (
        request.app.state.background_tasks
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return IndexingJobCreatedResponse(job_id=job.job_id, status=job.status)


@router.post(
    "/jobs",
    response_model=IndexingJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_job(
    payload: CreateIndexingJobRequest,
    request: Request,
) -> IndexingJobCreatedResponse:
    _require_indexing_service(request.app)
    store: InMemoryIndexingJobStore = request.app.state.indexing_job_store
    job = store.create()
    task = asyncio.create_task(_run_job(request.app, job.job_id, payload))
    background_tasks: set[asyncio.Task[None]] = (
        request.app.state.background_tasks
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return IndexingJobCreatedResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=IndexingJobResponse)
def get_job(job_id: str, request: Request) -> IndexingJobResponse:
    _require_indexing_service(request.app)
    store: InMemoryIndexingJobStore = request.app.state.indexing_job_store
    job = store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "JOB_NOT_FOUND",
                "message": "Indexing job not found",
            },
        )
    return _job_response(job)


@router.get(
    "/jobs/{job_id}/failures",
    response_model=IndexingFailuresResponse,
)
def get_job_failures(
    job_id: str,
    request: Request,
) -> IndexingFailuresResponse:
    _require_indexing_service(request.app)
    store: InMemoryIndexingJobStore = request.app.state.indexing_job_store
    job = store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "JOB_NOT_FOUND",
                "message": "Indexing job not found",
            },
        )
    failures = job.result.failures if job.result is not None else ()
    return IndexingFailuresResponse(
        job_id=job.job_id,
        status=job.status,
        total=len(failures),
        failures=[
            IndexingFailureResponse.model_validate(failure)
            for failure in failures
        ],
        error=(
            IndexingJobErrorResponse.model_validate(job.error)
            if job.error is not None
            else None
        ),
    )


async def _run_job(
    app: FastAPI,
    job_id: str,
    payload: CreateIndexingJobRequest,
    *,
    force: bool = False,
) -> None:
    store: InMemoryIndexingJobStore = app.state.indexing_job_store
    service: IndexingService = app.state.indexing_service
    store.mark_running(job_id)
    try:
        if force:
            result = await asyncio.to_thread(
                service.index_paths,
                payload.paths,
                recursive=payload.recursive,
                authorized_roots=payload.authorized_roots,
                force=True,
            )
        else:
            result = await asyncio.to_thread(
                service.index_paths,
                payload.paths,
                recursive=payload.recursive,
                authorized_roots=payload.authorized_roots,
            )
        retrieval_service = app.state.retrieval_service
        if retrieval_service is not None:
            await asyncio.to_thread(retrieval_service.refresh)
    except Exception as error:
        store.fail(job_id, IndexingJobError.from_exception(error))
    else:
        store.complete(job_id, result)


def _job_response(job: IndexingJob) -> IndexingJobResponse:
    result = (
        IndexingResultResponse.model_validate(job.result)
        if job.result is not None
        else None
    )
    return IndexingJobResponse(
        job_id=job.job_id,
        status=job.status,
        result=result,
    )


def _require_indexing_service(app: FastAPI) -> IndexingService:
    service = app.state.indexing_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "Week 4 search runtime is not configured",
            },
        )
    return service


def _require_index_catalog_service(app: FastAPI) -> IndexCatalogService:
    service = app.state.index_catalog_service
    if service is not None:
        return service
    indexing_service = app.state.indexing_service
    repository = getattr(indexing_service, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "Week 4 search runtime is not configured",
            },
        )
    service = IndexCatalogService(repository)
    app.state.index_catalog_service = service
    return service


def _storage_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "STORAGE_UNAVAILABLE",
            "message": "Local index is unavailable",
        },
    )
