from pathlib import Path
from typing import Any

import httpx

from content_retrieval.domain.errors import (
    InternalParseError,
    ParseTimeoutError,
    TikaUnavailableError,
)


class TikaClient:
    """Small HTTP adapter for the local Apache Tika server."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:9998",
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = httpx.Timeout(timeout_seconds)
        self.transport = transport

    def extract(
        self,
        path: Path,
        content: bytes,
        mime_type: str,
    ) -> dict[str, Any]:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
                trust_env=False,
            ) as client:
                response = client.put(
                    "/rmeta/text",
                    content=content,
                    headers={
                        "Content-Type": mime_type,
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as error:
            raise ParseTimeoutError(path) from error
        except httpx.ConnectError as error:
            raise TikaUnavailableError(path) from error
        except (httpx.HTTPStatusError, ValueError) as error:
            raise InternalParseError(path) from error

        if not isinstance(payload, list) or not payload:
            raise InternalParseError(path)
        metadata = payload[0]
        if not isinstance(metadata, dict):
            raise InternalParseError(path)
        return metadata
