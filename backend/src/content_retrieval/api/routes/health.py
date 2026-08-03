from fastapi import APIRouter, Request, Response, status


router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(request: Request, response: Response) -> dict[str, str]:
    try:
        is_ready = bool(request.app.state.ready)
        readiness_check = request.app.state.readiness_check
        if is_ready and readiness_check is not None:
            is_ready = bool(readiness_check())
    except Exception:
        is_ready = False

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready"}
    return {"status": "ready"}
