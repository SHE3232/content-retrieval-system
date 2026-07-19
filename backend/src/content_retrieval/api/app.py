from fastapi import FastAPI

from content_retrieval.api.routes import health, ingestion
from content_retrieval.parsers.registry import create_default_registry
from content_retrieval.services.batch_ingestion import BatchIngestionService
from content_retrieval.services.ingestion_jobs import InMemoryIngestionJobStore


DEFAULT_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024


def create_app(
    ingestion_service: BatchIngestionService | None = None,
) -> FastAPI:
    application = FastAPI(title="Content Retrieval API")
    application.state.ingestion_service = (
        ingestion_service
        or BatchIngestionService(
            create_default_registry(),
            max_file_size_bytes=DEFAULT_MAX_FILE_SIZE_BYTES,
        )
    )
    application.state.job_store = InMemoryIngestionJobStore()
    application.state.background_tasks = set()
    application.state.ready = True
    application.include_router(health.router)
    application.include_router(ingestion.router)
    return application


app = create_app()
