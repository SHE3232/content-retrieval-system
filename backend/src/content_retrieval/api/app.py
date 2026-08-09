from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI

from content_retrieval.api.routes import health, indexing, ingestion, search
from content_retrieval.parsers.registry import create_default_registry
from content_retrieval.services.batch_ingestion import BatchIngestionService
from content_retrieval.services.index_catalog import IndexCatalogService
from content_retrieval.services.indexing_jobs import InMemoryIndexingJobStore
from content_retrieval.services.ingestion_jobs import InMemoryIngestionJobStore


DEFAULT_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
AppLifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(
    ingestion_service: BatchIngestionService | None = None,
    *,
    indexing_service=None,
    index_catalog_service: IndexCatalogService | None = None,
    retrieval_service=None,
    lifespan: AppLifespan | None = None,
    ready: bool = True,
    readiness_check: Callable[[], bool] | None = None,
) -> FastAPI:
    application = FastAPI(title="Content Retrieval API", lifespan=lifespan)
    application.state.ingestion_service = (
        ingestion_service
        or BatchIngestionService(
            create_default_registry(),
            max_file_size_bytes=DEFAULT_MAX_FILE_SIZE_BYTES,
        )
    )
    application.state.job_store = InMemoryIngestionJobStore()
    application.state.indexing_job_store = InMemoryIndexingJobStore()
    application.state.indexing_service = indexing_service
    application.state.index_catalog_service = index_catalog_service
    application.state.retrieval_service = retrieval_service
    application.state.background_tasks = set()
    application.state.ready = ready
    application.state.readiness_check = readiness_check
    application.include_router(health.router)
    application.include_router(ingestion.router)
    application.include_router(indexing.router)
    application.include_router(indexing.index_router)
    application.include_router(search.router)
    return application


app = create_app()
