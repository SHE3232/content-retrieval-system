from datetime import datetime, timezone
from pathlib import Path

import pytest

from content_retrieval.domain.errors import (
    FileTooLargeError,
    InternalParseError,
    ParseTimeoutError,
    TikaUnavailableError,
    UnsupportedFormatError,
)
from content_retrieval.domain.models import (
    BatchItem,
    BatchResult,
    ParseResult,
    SkippedFile,
)


NOW = datetime(2026, 7, 22, tzinfo=timezone.utc)


def make_result(path: Path, **changes: object) -> ParseResult:
    values: dict[str, object] = {
        "file_id": "a" * 64,
        "path": path,
        "name": path.name,
        "mime_type": "text/plain",
        "modality": "text",
        "size_bytes": 0,
        "modified_at": NOW,
        "text": "",
    }
    values.update(changes)
    return ParseResult(**values)


def test_tc_059_rejects_uppercase_sha256(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        make_result(tmp_path / "upper.txt", file_id="A" * 64)


def test_tc_060_rejects_sha256_shorter_than_64_characters(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        make_result(tmp_path / "short.txt", file_id="a" * 63)


def test_tc_061_rejects_sha256_longer_than_64_characters(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        make_result(tmp_path / "long.txt", file_id="a" * 65)


def test_tc_062_rejects_non_hexadecimal_sha256(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        make_result(tmp_path / "invalid.txt", file_id="g" * 64)


def test_tc_063_allows_zero_byte_files(tmp_path: Path) -> None:
    result = make_result(tmp_path / "empty.txt", size_bytes=0)

    assert result.size_bytes == 0


def test_tc_064_preserves_unicode_file_names_and_paths(tmp_path: Path) -> None:
    source = tmp_path / "中文 空格 🧪.txt"

    result = make_result(source)

    assert result.path == source
    assert result.name == "中文 空格 🧪.txt"


def test_tc_065_preserves_naive_modified_at_values(tmp_path: Path) -> None:
    naive = datetime(2026, 7, 22, 12, 30)

    result = make_result(tmp_path / "naive.txt", modified_at=naive)

    assert result.modified_at is naive
    assert result.modified_at.tzinfo is None


def test_tc_066_preserves_nested_metadata(tmp_path: Path) -> None:
    metadata = {"nested": {"items": [1, "two", True]}, "count": 3}

    result = make_result(tmp_path / "metadata.txt", metadata=metadata)

    assert result.metadata == metadata


def test_tc_067_keeps_warning_order_and_instance_isolation(tmp_path: Path) -> None:
    first = make_result(
        tmp_path / "first.txt",
        warnings=["first warning", "second warning"],
    )
    second = make_result(tmp_path / "second.txt")

    first.warnings.append("third warning")

    assert first.warnings == ["first warning", "second warning", "third warning"]
    assert second.warnings == []


def test_tc_068_successful_batch_item_keeps_result(tmp_path: Path) -> None:
    result = make_result(tmp_path / "success.txt")

    item = BatchItem(path=result.path, status="succeeded", result=result)

    assert item.result is result
    assert item.error is None
    assert item.skip is None


def test_tc_069_failed_batch_item_keeps_error(tmp_path: Path) -> None:
    source = tmp_path / "failed.txt"
    error = InternalParseError(source)

    item = BatchItem(path=source, status="failed", error=error)

    assert item.error is error
    assert item.result is None


def test_tc_070_skipped_batch_item_keeps_reason(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.txt"
    skip = SkippedFile(source, "duplicate_content", "a" * 64, tmp_path / "first.txt")

    item = BatchItem(path=source, status="skipped", skip=skip)

    assert item.skip is skip
    assert item.skip.reason == "duplicate_content"


def test_tc_071_parse_error_dictionary_has_stable_fields(tmp_path: Path) -> None:
    error = UnsupportedFormatError(tmp_path / "archive.bin", "application/octet-stream")

    payload = error.to_dict()

    assert list(payload) == ["code", "message", "retryable"]
    assert payload["code"] == "UNSUPPORTED_FORMAT"
    assert payload["retryable"] is False


def test_tc_072_retryable_error_matrix(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    retryable = [
        TikaUnavailableError(source),
        ParseTimeoutError(source),
        FileTooLargeError(source, 11, 10),
    ]
    terminal = [UnsupportedFormatError(source), InternalParseError(source)]

    assert all(error.retryable for error in retryable)
    assert not any(error.retryable for error in terminal)


def test_tc_073_file_too_large_error_preserves_limits(tmp_path: Path) -> None:
    source = tmp_path / "large.bin"

    error = FileTooLargeError(source, actual_size_bytes=101, max_size_bytes=100)

    assert error.actual_size_bytes == 101
    assert error.max_size_bytes == 100
    assert "101 bytes" in str(error)
    assert "100 bytes" in str(error)


def test_tc_074_batch_items_preserve_candidate_order(tmp_path: Path) -> None:
    paths = [tmp_path / "02.txt", tmp_path / "01.txt", tmp_path / "03.txt"]
    items = [
        BatchItem(path=path, status="succeeded", result=make_result(path))
        for path in paths
    ]

    batch = BatchResult(items=items, results=[item.result for item in items if item.result])

    assert [item.path for item in batch.items] == paths
