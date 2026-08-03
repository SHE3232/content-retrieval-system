from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from content_retrieval.domain.errors import CorruptedFileError
from content_retrieval.domain.models import ParseResult
from content_retrieval.parsers.registry import ParserRegistry
from content_retrieval.services.batch_ingestion import BatchIngestionService


MODIFIED_AT = datetime(2026, 7, 22, tzinfo=timezone.utc)


class ConfigurableTextParser:
    supported_extensions = frozenset({".txt"})
    supported_mime_types = frozenset({"text/plain"})

    def __init__(self) -> None:
        self.parsed_paths: list[Path] = []

    def parse(self, path: Path) -> ParseResult:
        self.parsed_paths.append(path)
        content = path.read_bytes()
        if content == b"controlled-error":
            raise CorruptedFileError(path, "controlled fixture failure")
        if content == b"unexpected-error":
            raise RuntimeError("sensitive parser detail")
        return ParseResult(
            file_id=hashlib.sha256(content).hexdigest(),
            path=path,
            name=path.name,
            mime_type="text/plain",
            modality="text",
            size_bytes=len(content),
            modified_at=MODIFIED_AT,
            text=content.decode("utf-8"),
        )


def make_service(
    parser: ConfigurableTextParser | None = None,
    *,
    max_file_size_bytes: int = 1024,
) -> tuple[BatchIngestionService, ConfigurableTextParser]:
    actual_parser = parser or ConfigurableTextParser()
    return (
        BatchIngestionService(
            ParserRegistry([actual_parser]),
            max_file_size_bytes=max_file_size_bytes,
        ),
        actual_parser,
    )


def test_tc_161_rejects_zero_file_size_limit() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        make_service(max_file_size_bytes=0)


def test_tc_162_rejects_negative_file_size_limit() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        make_service(max_file_size_bytes=-1)


def test_tc_163_scan_directory_rejects_missing_directory(tmp_path: Path) -> None:
    service, _ = make_service()

    with pytest.raises(FileNotFoundError):
        service.scan_directory(tmp_path / "missing")


def test_tc_164_scan_directory_rejects_regular_file(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("content", encoding="utf-8")
    service, _ = make_service()

    with pytest.raises(NotADirectoryError):
        service.scan_directory(source)


def test_tc_165_empty_path_list_produces_empty_batch(tmp_path: Path) -> None:
    service, _ = make_service()

    batch = service.parse_paths([], authorized_roots=[tmp_path])

    assert (batch.total, batch.succeeded, batch.failed, batch.skipped) == (0, 0, 0, 0)


def test_tc_166_missing_authorized_root_is_rejected(tmp_path: Path) -> None:
    service, _ = make_service()

    with pytest.raises(FileNotFoundError):
        service.parse_paths([], authorized_roots=[tmp_path / "missing"])


def test_tc_167_multiple_authorized_roots_are_supported(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first = first_root / "a.txt"
    second = second_root / "b.txt"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    service, _ = make_service()

    batch = service.parse_paths(
        [first, second], authorized_roots=[first_root, second_root]
    )

    assert [result.name for result in batch.results] == ["a.txt", "b.txt"]


def test_tc_168_file_can_be_an_exact_authorized_root(tmp_path: Path) -> None:
    source = tmp_path / "only.txt"
    source.write_text("allowed", encoding="utf-8")
    service, _ = make_service()

    batch = service.parse_paths([source], authorized_roots=[source])

    assert batch.succeeded == 1
    assert batch.results[0].text == "allowed"


def test_tc_169_normalized_parent_traversal_is_rejected(tmp_path: Path) -> None:
    authorized = tmp_path / "authorized"
    authorized.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    traversal = authorized / ".." / "outside.txt"
    service, _ = make_service()

    batch = service.parse_paths([traversal], authorized_roots=[authorized])

    assert batch.failed == 1
    assert batch.errors[0].code == "PATH_NOT_AUTHORIZED"


def test_tc_170_directory_scan_skips_unsupported_files(tmp_path: Path) -> None:
    (tmp_path / "supported.txt").write_text("ok", encoding="utf-8")
    unsupported = tmp_path / "unsupported.bin"
    unsupported.write_bytes(b"bin")
    service, _ = make_service()

    batch = service.parse_paths([tmp_path], authorized_roots=[tmp_path])

    assert batch.succeeded == 1
    assert batch.skipped == 1
    assert batch.skips[0].path == unsupported.resolve()


def test_tc_171_exact_file_size_limit_is_accepted(tmp_path: Path) -> None:
    source = tmp_path / "exact.txt"
    source.write_bytes(b"1234")
    service, parser = make_service(max_file_size_bytes=4)

    batch = service.parse_paths([source], authorized_roots=[tmp_path])

    assert batch.succeeded == 1
    assert parser.parsed_paths == [source.resolve()]


def test_tc_172_one_byte_over_limit_is_rejected_before_parsing(tmp_path: Path) -> None:
    source = tmp_path / "large.txt"
    source.write_bytes(b"12345")
    service, parser = make_service(max_file_size_bytes=4)

    batch = service.parse_paths([source], authorized_roots=[tmp_path])

    assert batch.failed == 1
    assert batch.errors[0].code == "FILE_TOO_LARGE"
    assert parser.parsed_paths == []


def test_tc_173_three_equal_files_keep_first_as_duplicate_origin(tmp_path: Path) -> None:
    files = [tmp_path / name for name in ("a.txt", "b.txt", "c.txt")]
    for source in files:
        source.write_text("same", encoding="utf-8")
    service, parser = make_service()

    batch = service.parse_paths(files, authorized_roots=[tmp_path])

    assert batch.succeeded == 1
    assert batch.skipped == 2
    assert parser.parsed_paths == [files[0].resolve()]
    assert [skip.duplicate_of for skip in batch.skips] == [
        files[0].resolve(),
        files[0].resolve(),
    ]


def test_tc_174_same_real_path_is_processed_only_once(tmp_path: Path) -> None:
    source = tmp_path / "single.txt"
    source.write_text("one", encoding="utf-8")
    service, parser = make_service()

    batch = service.parse_paths(
        [source, source.parent / "." / source.name],
        authorized_roots=[tmp_path],
    )

    assert batch.total == 1
    assert parser.parsed_paths == [source.resolve()]


def test_tc_175_sort_key_has_deterministic_case_tie_breaker() -> None:
    root = Path("C:/fixture")

    upper = BatchIngestionService._sort_key(root, root / "A.txt")
    lower = BatchIngestionService._sort_key(root, root / "a.txt")

    assert upper[0] == lower[0]
    assert upper < lower


def test_tc_176_controlled_parser_error_is_preserved(tmp_path: Path) -> None:
    source = tmp_path / "broken.txt"
    source.write_bytes(b"controlled-error")
    service, _ = make_service()

    batch = service.parse_paths([source], authorized_roots=[tmp_path])

    assert batch.failed == 1
    assert isinstance(batch.errors[0], CorruptedFileError)
    assert batch.items[0].error is batch.errors[0]


def test_tc_177_unexpected_parser_error_is_sanitized(tmp_path: Path) -> None:
    source = tmp_path / "crash.txt"
    source.write_bytes(b"unexpected-error")
    service, _ = make_service()

    batch = service.parse_paths([source], authorized_roots=[tmp_path])

    assert batch.errors[0].code == "INTERNAL_ERROR"
    assert "sensitive parser detail" not in str(batch.errors[0])


def test_tc_178_mixed_sources_keep_caller_order(tmp_path: Path) -> None:
    second_dir = tmp_path / "directory"
    second_dir.mkdir()
    nested = second_dir / "nested.txt"
    nested.write_text("nested", encoding="utf-8")
    first = tmp_path / "first.txt"
    first.write_text("first", encoding="utf-8")
    service, _ = make_service()

    batch = service.parse_paths(
        [first, second_dir], authorized_roots=[tmp_path]
    )

    assert [item.path for item in batch.items] == [first.resolve(), nested.resolve()]


def test_tc_179_non_recursive_scan_does_not_include_nested_files(tmp_path: Path) -> None:
    top = tmp_path / "top.txt"
    top.write_text("top", encoding="utf-8")
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "hidden.txt").write_text("hidden", encoding="utf-8")
    service, _ = make_service()

    batch = service.parse_paths(
        [tmp_path], recursive=False, authorized_roots=[tmp_path]
    )

    assert [result.path for result in batch.results] == [top.resolve()]


def test_tc_180_batch_counts_partition_all_items(tmp_path: Path) -> None:
    (tmp_path / "good.txt").write_text("good", encoding="utf-8")
    (tmp_path / "duplicate.txt").write_text("good", encoding="utf-8")
    (tmp_path / "bad.txt").write_bytes(b"controlled-error")
    (tmp_path / "ignored.bin").write_bytes(b"ignored")
    service, _ = make_service()

    batch = service.parse_paths([tmp_path], authorized_roots=[tmp_path])

    assert batch.total == len(batch.items) == 4
    assert batch.total == batch.succeeded + batch.failed + batch.skipped
    assert sorted(item.status for item in batch.items) == [
        "failed",
        "skipped",
        "skipped",
        "succeeded",
    ]
