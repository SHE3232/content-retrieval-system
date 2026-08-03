from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path

import pytest

from content_retrieval.domain.errors import (
    CorruptedFileError,
    UnsupportedFormatError,
)
from content_retrieval.domain.models import BatchResult, ParseResult
from content_retrieval.parsers.base import Parser
from content_retrieval.parsers.registry import ParserRegistry


FILE_ID = "a" * 64
MODIFIED_AT = datetime(2026, 7, 17, 9, 30, tzinfo=timezone.utc)


def make_result(path: Path) -> ParseResult:
    return ParseResult(
        file_id=FILE_ID,
        path=path,
        name=path.name,
        mime_type="text/plain",
        modality="text",
        size_bytes=12,
        modified_at=MODIFIED_AT,
        text="hello world",
    )


def test_parse_result_exposes_the_unified_data_contract(tmp_path: Path) -> None:
    source = (tmp_path / "notes.txt").resolve()

    result = make_result(source)

    assert [field.name for field in fields(ParseResult)] == [
        "file_id",
        "path",
        "name",
        "mime_type",
        "modality",
        "size_bytes",
        "modified_at",
        "text",
        "page_count",
        "width",
        "height",
        "metadata",
        "warnings",
    ]
    assert result.path == source
    assert result.page_count is None
    assert result.width is None
    assert result.height is None
    assert result.metadata == {}
    assert result.warnings == []


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"file_id": "not-a-sha256"}, "SHA-256"),
        ({"modality": "audio"}, "modality"),
        ({"size_bytes": -1}, "size_bytes"),
    ],
)
def test_parse_result_rejects_values_outside_the_contract(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "file_id": FILE_ID,
        "path": (tmp_path / "notes.txt").resolve(),
        "name": "notes.txt",
        "mime_type": "text/plain",
        "modality": "text",
        "size_bytes": 12,
        "modified_at": MODIFIED_AT,
    }
    values.update(changes)

    with pytest.raises(ValueError, match=message):
        ParseResult(**values)


def test_parse_result_defaults_are_not_shared(tmp_path: Path) -> None:
    first = make_result((tmp_path / "first.txt").resolve())
    second = make_result((tmp_path / "second.txt").resolve())

    first.metadata["encoding"] = "utf-8"
    first.warnings.append("empty line removed")

    assert second.metadata == {}
    assert second.warnings == []


class StubParser:
    supported_extensions = frozenset({".txt"})
    supported_mime_types = frozenset({"text/plain"})

    def parse(self, path: Path) -> ParseResult:
        return make_result(path)


def test_parser_is_a_runtime_checkable_interface() -> None:
    assert isinstance(StubParser(), Parser)


def test_registry_routes_by_normalized_extension_and_mime_type(
    tmp_path: Path,
) -> None:
    parser = StubParser()
    registry = ParserRegistry([parser])

    assert registry.resolve(tmp_path / "NOTES.TXT") is parser
    assert registry.resolve(tmp_path / "no-extension", "TEXT/PLAIN") is parser


def test_registry_raises_a_controlled_error_for_unknown_formats(
    tmp_path: Path,
) -> None:
    source = tmp_path / "archive.bin"
    registry = ParserRegistry([StubParser()])

    with pytest.raises(UnsupportedFormatError) as raised:
        registry.resolve(source, "application/octet-stream")

    assert raised.value.path == source
    assert raised.value.mime_type == "application/octet-stream"


def test_corrupted_file_error_preserves_safe_context(tmp_path: Path) -> None:
    source = tmp_path / "broken.pdf"

    error = CorruptedFileError(source, "invalid cross-reference table")

    assert error.path == source
    assert error.reason == "invalid cross-reference table"
    assert "broken.pdf" in str(error)


def test_batch_result_reports_success_and_failure_counts(tmp_path: Path) -> None:
    result = make_result((tmp_path / "notes.txt").resolve())
    error = CorruptedFileError(tmp_path / "broken.pdf", "invalid header")

    batch = BatchResult(results=[result], errors=[error])

    assert batch.total == 2
    assert batch.succeeded == 1
    assert batch.failed == 1


def test_batch_result_defaults_are_not_shared() -> None:
    first = BatchResult()
    second = BatchResult()

    first.errors.append(UnsupportedFormatError(Path("unknown.xyz")))

    assert second.errors == []
