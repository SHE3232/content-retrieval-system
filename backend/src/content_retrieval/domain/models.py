from dataclasses import dataclass, field
from datetime import datetime
import math
from pathlib import Path
import re
from typing import Any, Literal

from .errors import ParseError, ProcessingError


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


@dataclass(slots=True)
class TextChunk:
    chunk_id: str
    file_id: str
    text: str
    sequence_number: int
    page_number: int | None = None
    paragraph_number: int | None = None
    split_number: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not _SHA256_PATTERN.fullmatch(self.chunk_id):
            raise ValueError("chunk_id must be a hexadecimal SHA-256 digest")
        if not _SHA256_PATTERN.fullmatch(self.file_id):
            raise ValueError("file_id must be a hexadecimal SHA-256 digest")
        if not self.text.strip():
            raise ValueError("text must contain non-whitespace content")
        if self.sequence_number < 0:
            raise ValueError("sequence_number must be non-negative")
        if self.split_number < 0:
            raise ValueError("split_number must be non-negative")
        if (self.page_number is None) == (self.paragraph_number is None):
            raise ValueError(
                "exactly one of page_number or paragraph_number is required"
            )
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("page_number must be one-based")
        if self.paragraph_number is not None and self.paragraph_number < 1:
            raise ValueError("paragraph_number must be one-based")
        if self.schema_version != "1":
            raise ValueError("unsupported TextChunk schema_version")


@dataclass(slots=True)
class EmbeddingVector:
    source_id: str
    file_id: str
    model_id: str
    space_id: str
    modality: Literal["text", "image"]
    values: list[float]
    dimensions: int
    normalized: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not _SHA256_PATTERN.fullmatch(self.source_id):
            raise ValueError("source_id must be a hexadecimal SHA-256 digest")
        if not _SHA256_PATTERN.fullmatch(self.file_id):
            raise ValueError("file_id must be a hexadecimal SHA-256 digest")
        if not self.model_id.strip():
            raise ValueError("model_id must not be blank")
        if not self.space_id.strip():
            raise ValueError("space_id must not be blank")
        if self.modality not in {"text", "image"}:
            raise ValueError("modality must be text or image")
        if self.dimensions <= 0:
            raise ValueError("dimensions must be positive")
        if self.dimensions != len(self.values):
            raise ValueError("dimensions must match the number of vector values")
        if not all(
            isinstance(value, (int, float)) and math.isfinite(value)
            for value in self.values
        ):
            raise ValueError("vector values must be finite numbers")
        if self.schema_version != "1":
            raise ValueError("unsupported EmbeddingVector schema_version")


@dataclass(slots=True)
class BatchProcessingResult:
    items: list[TextChunk | EmbeddingVector] = field(default_factory=list)
    errors: list[ProcessingError] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.items) + len(self.errors)

    @property
    def succeeded(self) -> int:
        return len(self.items)

    @property
    def failed(self) -> int:
        return len(self.errors)
