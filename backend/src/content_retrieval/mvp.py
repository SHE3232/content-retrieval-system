"""Runtime configuration and dependency readiness checks for the offline MVP."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import httpx

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
        except httpx.HTTPError:
            return False
        return response.status_code == 200 and "Apache Tika" in response.text
