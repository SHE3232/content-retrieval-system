import asyncio

from fastapi import APIRouter, FastAPI, HTTPException, Request, status

from content_retrieval.api.schemas import (
    IndexStatsResponse,
    SearchRequest,
    SearchResponse,
)
from content_retrieval.domain.errors import RetrievalError, StorageError
from content_retrieval.retrieval.service import RetrievalService


router = APIRouter(tags=["search"])


@router.post("/v1/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    request: Request,
) -> SearchResponse:
    service = _require_retrieval_service(request.app)
    try:
        filters = payload.filters.to_domain()
        result = await asyncio.to_thread(
            service.search,
            payload.query,
            top_k=payload.top_k,
            filters=filters,
            channels=payload.channels,
            weights=payload.weights,
        )
    except (RetrievalError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "SEARCH_FAILED",
                "message": str(error),
            },
        ) from error
    return SearchResponse.model_validate(result)


@router.get("/v1/index/stats", response_model=IndexStatsResponse)
async def index_stats(request: Request) -> IndexStatsResponse:
    service = _require_retrieval_service(request.app)
    try:
        records = await asyncio.to_thread(
            service.repository.list_records
        )
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "STORAGE_UNAVAILABLE",
                "message": "Local index is unavailable",
            },
        ) from error
    return IndexStatsResponse(
        record_count=len(records),
        file_count=len({record.file_id for record in records}),
        text_record_count=sum(
            record.modality == "text" for record in records
        ),
        image_record_count=sum(
            record.modality == "image" for record in records
        ),
    )


def _require_retrieval_service(app: FastAPI) -> RetrievalService:
    service = app.state.retrieval_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "Week 4 search runtime is not configured",
            },
        )
    return service
