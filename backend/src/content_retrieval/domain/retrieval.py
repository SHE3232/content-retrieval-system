from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
from pathlib import Path
import re
from typing import Literal

from content_retrieval.domain.models import EmbeddingVector


SearchModality = Literal["text", "image"]
SearchChannel = Literal["keyword", "text_semantic", "image_semantic"]
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _require_sha256(value: str, field_name: str) -> None:
    if not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a hexadecimal SHA-256 digest")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class IndexRecord:
    """One persistable source record paired with a compatible embedding."""

    record_id: str
    source_id: str
    file_id: str
    source_key: str
    path: Path
    name: str
    mime_type: str
    modality: SearchModality
    document: str
    vector: EmbeddingVector
    modified_at: datetime
    size_bytes: int
    page_number: int | None = None
    paragraph_number: int | None = None
    sequence_number: int = 0

    def __post_init__(self) -> None:
        _require_sha256(self.record_id, "record_id")
        _require_sha256(self.source_id, "source_id")
        _require_sha256(self.file_id, "file_id")
        _require_sha256(self.source_key, "source_key")
        if self.record_id != self.source_id:
            raise ValueError("record_id must match source_id")
        if self.vector.source_id != self.source_id:
            raise ValueError("vector source_id must match source_id")
        if self.vector.file_id != self.file_id:
            raise ValueError("vector file_id must match file_id")
        if self.vector.modality != self.modality:
            raise ValueError("vector modality must match record modality")
        if not self.vector.normalized:
            raise ValueError("vector must be normalized before indexing")
        if not self.path.is_absolute():
            raise ValueError("path must be absolute")
        if not self.name.strip():
            raise ValueError("name must not be blank")
        if not self.mime_type.strip():
            raise ValueError("mime_type must not be blank")
        if self.modality not in {"text", "image"}:
            raise ValueError("modality must be text or image")
        if not self.document.strip():
            raise ValueError("document must not be blank")
        _require_aware(self.modified_at, "modified_at")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")
        if self.sequence_number < 0:
            raise ValueError("sequence_number must be non-negative")
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("page_number must be one-based")
        if self.paragraph_number is not None and self.paragraph_number < 1:
            raise ValueError("paragraph_number must be one-based")
        has_page = self.page_number is not None
        has_paragraph = self.paragraph_number is not None
        if self.modality == "text" and has_page == has_paragraph:
            raise ValueError("text record requires exactly one source locator")
        if self.modality == "image" and (has_page or has_paragraph):
            raise ValueError("image record must not have a text source locator")

    @property
    def model_id(self) -> str:
        return self.vector.model_id

    @property
    def space_id(self) -> str:
        return self.vector.space_id

    @property
    def dimensions(self) -> int:
        return self.vector.dimensions


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Optional local metadata filters applied before ranking."""

    mime_types: tuple[str, ...] = ()
    modalities: tuple[SearchModality, ...] = ()
    path_prefix: Path | None = None
    modified_after: datetime | None = None
    modified_before: datetime | None = None

    def __post_init__(self) -> None:
        if any(not mime_type.strip() for mime_type in self.mime_types):
            raise ValueError("mime_types must not contain blank values")
        if any(modality not in {"text", "image"} for modality in self.modalities):
            raise ValueError("modality filters must be text or image")
        if self.path_prefix is not None and not self.path_prefix.is_absolute():
            raise ValueError("path_prefix must be absolute")
        if self.modified_after is not None:
            _require_aware(self.modified_after, "modified_after")
        if self.modified_before is not None:
            _require_aware(self.modified_before, "modified_before")
        if (
            self.modified_after is not None
            and self.modified_before is not None
            and self.modified_after > self.modified_before
        ):
            raise ValueError("modified_after must not be later than modified_before")


@dataclass(frozen=True, slots=True)
class VectorCandidate:
    record: IndexRecord
    score: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.score) or not -1.0 <= self.score <= 1.0:
            raise ValueError("score must be finite and between -1 and 1")


@dataclass(frozen=True, slots=True)
class IndexingFailure:
    path: Path
    code: str
    message: str
    stage: str
    retryable: bool
    file_id: str | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise ValueError("failure path must be absolute")
        if not self.code.strip() or not self.message.strip() or not self.stage.strip():
            raise ValueError("failure diagnostics must not be blank")
        if self.file_id is not None:
            _require_sha256(self.file_id, "file_id")
        if self.source_id is not None:
            _require_sha256(self.source_id, "source_id")


@dataclass(frozen=True, slots=True)
class IndexingResult:
    parsed_files: int
    indexed_files: int
    indexed_records: int
    skipped_files: int
    failed_files: int
    partial_files: int
    unchanged_files: int
    removed_stale_records: int
    failures: tuple[IndexingFailure, ...] = ()

    def __post_init__(self) -> None:
        counters = {
            "parsed_files": self.parsed_files,
            "indexed_files": self.indexed_files,
            "indexed_records": self.indexed_records,
            "skipped_files": self.skipped_files,
            "failed_files": self.failed_files,
            "partial_files": self.partial_files,
            "unchanged_files": self.unchanged_files,
            "removed_stale_records": self.removed_stale_records,
        }
        if any(value < 0 for value in counters.values()):
            raise ValueError("indexing counters must be non-negative")
        categorized = (
            self.indexed_files + self.failed_files + self.unchanged_files
        )
        if self.parsed_files != categorized:
            raise ValueError(
                "parsed_files must equal indexed, failed, and unchanged files"
            )
        if self.partial_files > self.indexed_files:
            raise ValueError("partial_files cannot exceed indexed_files")


@dataclass(frozen=True, slots=True)
class SearchHit:
    file_id: str
    source_id: str
    path: Path
    name: str
    mime_type: str
    modality: SearchModality
    score: float
    match_reasons: tuple[SearchChannel, ...]
    snippet: str | None
    page_number: int | None
    paragraph_number: int | None

    def __post_init__(self) -> None:
        _require_sha256(self.file_id, "file_id")
        _require_sha256(self.source_id, "source_id")
        if not self.path.is_absolute():
            raise ValueError("path must be absolute")
        if not self.name.strip() or not self.mime_type.strip():
            raise ValueError("name and mime_type must not be blank")
        if self.modality not in {"text", "image"}:
            raise ValueError("modality must be text or image")
        if not math.isfinite(self.score) or not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be finite and between 0 and 1")
        if not self.match_reasons:
            raise ValueError("match_reasons must not be empty")
        if len(set(self.match_reasons)) != len(self.match_reasons):
            raise ValueError("match_reasons must not contain duplicates")
        if any(
            reason not in {"keyword", "text_semantic", "image_semantic"}
            for reason in self.match_reasons
        ):
            raise ValueError("match_reasons contain an unsupported channel")
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("page_number must be one-based")
        if self.paragraph_number is not None and self.paragraph_number < 1:
            raise ValueError("paragraph_number must be one-based")


@dataclass(frozen=True, slots=True)
class SearchResult:
    query: str
    hits: tuple[SearchHit, ...]
    total_candidates: int
    elapsed_ms: float
    weights: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be blank")
        if self.total_candidates < len(self.hits):
            raise ValueError("total_candidates must include every returned hit")
        if not math.isfinite(self.elapsed_ms) or self.elapsed_ms < 0:
            raise ValueError("elapsed_ms must be finite and non-negative")
        if any(
            not channel.strip()
            or not math.isfinite(weight)
            or weight <= 0
            for channel, weight in self.weights.items()
        ):
            raise ValueError("weights must use non-blank channels and positive values")
        if any(
            left.score < right.score
            for left, right in zip(self.hits, self.hits[1:])
        ):
            raise ValueError("hits must be sorted by descending score")
