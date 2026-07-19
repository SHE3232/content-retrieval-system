from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Literal

from .errors import ParseError


Modality = Literal["text", "document", "image"]
BatchStatus = Literal["succeeded", "skipped", "failed"]
SkipReason = Literal["duplicate_content", "unsupported_format"]
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(slots=True)
class ParseResult:
    file_id: str
    path: Path
    name: str
    mime_type: str
    modality: Modality
    size_bytes: int
    modified_at: datetime
    text: str | None = None
    page_count: int | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not _SHA256_PATTERN.fullmatch(self.file_id):
            raise ValueError("file_id must be a hexadecimal SHA-256 digest")
        if self.modality not in {"text", "document", "image"}:
            raise ValueError("modality must be text, document, or image")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")


@dataclass(slots=True)
class SkippedFile:
    path: Path
    reason: SkipReason
    file_id: str | None = None
    duplicate_of: Path | None = None


@dataclass(slots=True)
class BatchItem:
    path: Path
    status: BatchStatus
    result: ParseResult | None = None
    error: ParseError | None = None
    skip: SkippedFile | None = None


@dataclass(slots=True)
class BatchResult:
    results: list[ParseResult] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    skips: list[SkippedFile] = field(default_factory=list)
    items: list[BatchItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results) + len(self.skips) + len(self.errors)

    @property
    def succeeded(self) -> int:
        return len(self.results)

    @property
    def skipped(self) -> int:
        return len(self.skips)

    @property
    def failed(self) -> int:
        return len(self.errors)
