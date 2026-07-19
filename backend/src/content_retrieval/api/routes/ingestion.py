import asyncio

from fastapi import APIRouter, FastAPI, HTTPException, Request, status

from content_retrieval.api.schemas import (
    CreateIngestionJobRequest,
    IngestionJobResponse,
    JobCountsResponse,
    JobCreatedResponse,
    JobErrorResponse,
    JobSkipResponse,
    ParseResultResponse,
)
from content_retrieval.services.batch_ingestion import BatchIngestionService
from content_retrieval.services.ingestion_jobs import (
    IngestionJob,
    InMemoryIngestionJobStore,
)


router = APIRouter(prefix="/v1/ingestion", tags=["ingestion"])


@router.post(
    "/jobs",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_job(
    payload: CreateIngestionJobRequest,
    request: Request,
) -> JobCreatedResponse:
    store: InMemoryIngestionJobStore = request.app.state.job_store
    job = store.create()
    task = asyncio.create_task(_run_job(request.app, job.job_id, payload))
    background_tasks: set[asyncio.Task[None]] = (
        request.app.state.background_tasks
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
def get_job(job_id: str, request: Request) -> IngestionJobResponse:
    store: InMemoryIngestionJobStore = request.app.state.job_store
    job = store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "JOB_NOT_FOUND",
                "message": "Ingestion job not found",
            },
        )
    return _job_response(job)


async def _run_job(
    app: FastAPI,
    job_id: str,
    payload: CreateIngestionJobRequest,
) -> None:
    store: InMemoryIngestionJobStore = app.state.job_store
    service: BatchIngestionService = app.state.ingestion_service
    store.mark_running(job_id)
    try:
        result = await asyncio.to_thread(
            service.parse_paths,
            payload.paths,
            recursive=payload.recursive,
            authorized_roots=payload.authorized_roots,
        )
    except Exception:
        store.fail(job_id)
    else:
        store.complete(job_id, result)


def _job_response(job: IngestionJob) -> IngestionJobResponse:
    result = job.result
    if result is None:
        return IngestionJobResponse(
            job_id=job.job_id,
            status=job.status,
            counts=JobCountsResponse(
                total=0,
                pending=0,
                running=0,
                succeeded=0,
                failed=0,
                skipped=0,
            ),
            results=[],
            errors=[],
            skips=[],
        )

    return IngestionJobResponse(
        job_id=job.job_id,
        status=job.status,
        counts=JobCountsResponse(
            total=result.total,
            pending=0,
            running=0,
            succeeded=result.succeeded,
            failed=result.failed,
            skipped=result.skipped,
        ),
        results=[
            ParseResultResponse.model_validate(parsed)
            for parsed in result.results
        ],
        errors=[
            JobErrorResponse(
                path=error.path,
                code=error.code,
                message=str(error),
                retryable=error.retryable,
            )
            for error in result.errors
        ],
        skips=[JobSkipResponse.model_validate(skip) for skip in result.skips],
    )
