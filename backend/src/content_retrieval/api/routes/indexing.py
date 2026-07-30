import asyncio

from fastapi import APIRouter, FastAPI, HTTPException, Request, status

from content_retrieval.api.schemas import (
    CreateIndexingJobRequest,
    IndexingJobCreatedResponse,
    IndexingJobResponse,
    IndexingResultResponse,
)
from content_retrieval.services.indexing import IndexingService
from content_retrieval.services.indexing_jobs import (
    InMemoryIndexingJobStore,
    IndexingJob,
)


router = APIRouter(prefix="/v1/indexing", tags=["indexing"])


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


async def _run_job(
    app: FastAPI,
    job_id: str,
    payload: CreateIndexingJobRequest,
) -> None:
    store: InMemoryIndexingJobStore = app.state.indexing_job_store
    service: IndexingService = app.state.indexing_service
    store.mark_running(job_id)
    try:
        result = await asyncio.to_thread(
            service.index_paths,
            payload.paths,
            recursive=payload.recursive,
            authorized_roots=payload.authorized_roots,
        )
        retrieval_service = app.state.retrieval_service
        if retrieval_service is not None:
            await asyncio.to_thread(retrieval_service.refresh)
    except Exception:
        store.fail(job_id)
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
