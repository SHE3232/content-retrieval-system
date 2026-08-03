"""Runtime configuration and dependency readiness checks for the offline MVP."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

import httpx
from fastapi import FastAPI

from content_retrieval.api.app import create_app
from content_retrieval.runtime import LocalRuntime, build_local_runtime

MODEL_ROOT_ENV = "CONTENT_RETRIEVAL_MODEL_ROOT"
MANIFEST_PATH_ENV = "CONTENT_RETRIEVAL_MANIFEST_PATH"
DATA_DIR_ENV = "CONTENT_RETRIEVAL_DATA_DIR"
TIKA_URL_ENV = "CONTENT_RETRIEVAL_TIKA_URL"

DEFAULT_TIKA_URL = "http://127.0.0.1:9998"


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_local_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


@dataclass(frozen=True, slots=True)
class MvpSettings:
    model_root: Path
    manifest_path: Path
    data_dir: Path
    tika_url: str

    @classmethod
    def from_environment(
        cls,
        *,
        repository_root: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> MvpSettings:
        root = (repository_root or _repository_root()).resolve()
        values = os.environ if environ is None else environ
        return cls(
            model_root=_resolve_local_path(root, values.get(MODEL_ROOT_ENV, "models")),
            manifest_path=_resolve_local_path(
                root, values.get(MANIFEST_PATH_ENV, "models/model-manifest.json")
            ),
            data_dir=_resolve_local_path(root, values.get(DATA_DIR_ENV, "data/mvp")),
            tika_url=values.get(TIKA_URL_ENV, DEFAULT_TIKA_URL).rstrip("/"),
        )


class TikaReadinessProbe:
    def __init__(
        self,
        base_url: str = DEFAULT_TIKA_URL,
        timeout_seconds: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def is_ready(self) -> bool:
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                transport=self._transport,
                trust_env=False,
            ) as client:
                response = client.get("/version")
        except (httpx.HTTPError, httpx.InvalidURL):
            return False
        return response.status_code == 200 and "Apache Tika" in response.text


class RuntimeBuilder(Protocol):
    def __call__(
        self,
        *,
        model_root: Path,
        manifest_path: Path,
        data_dir: Path,
    ) -> LocalRuntime: ...


def create_mvp_app(
    settings: MvpSettings | None = None,
    *,
    runtime_builder: RuntimeBuilder = build_local_runtime,
    tika_probe: TikaReadinessProbe | None = None,
) -> FastAPI:
    if settings is None:
        settings = MvpSettings.from_environment()
    probe = (
        tika_probe
        if tika_probe is not None
        else TikaReadinessProbe(settings.tika_url)
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        runtime = runtime_builder(
            model_root=settings.model_root,
            manifest_path=settings.manifest_path,
            data_dir=settings.data_dir,
        )
        try:
            if not probe.is_ready():
                raise RuntimeError(
                    f"Tika dependency is not ready at {settings.tika_url}"
                )
            application.state.runtime = runtime
            application.state.indexing_service = runtime.indexing_service
            application.state.retrieval_service = runtime.retrieval_service
            application.state.ready = True
            yield
        finally:
            application.state.ready = False
            try:
                background_tasks = tuple(application.state.background_tasks)
                for task in background_tasks:
                    task.cancel()
                if background_tasks:
                    await asyncio.gather(*background_tasks, return_exceptions=True)
            finally:
                runtime.close()

    application = create_app(lifespan=lifespan, ready=False)

    def readiness_check() -> bool:
        runtime = getattr(application.state, "runtime", None)
        return bool(
            runtime is not None
            and probe.is_ready()
            and runtime.repository.count() >= 0
        )

    application.state.readiness_check = readiness_check
    return application
