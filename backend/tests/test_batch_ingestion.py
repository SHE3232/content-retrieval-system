from datetime import datetime, timezone
import hashlib
from pathlib import Path

from content_retrieval.domain.errors import CorruptedFileError, FileTooLargeError
from content_retrieval.domain.models import ParseResult
from content_retrieval.parsers.registry import ParserRegistry
from content_retrieval.services.batch_ingestion import BatchIngestionService


MODIFIED_AT = datetime(2026, 7, 19, tzinfo=timezone.utc)


class RecordingTextParser:
    supported_extensions = frozenset({".txt"})
    supported_mime_types = frozenset({"text/plain"})

    def __init__(self) -> None:
        self.parsed_paths: list[Path] = []

    def parse(self, path: Path) -> ParseResult:
        self.parsed_paths.append(path)
        content = path.read_bytes()
        if content == b"broken":
            raise CorruptedFileError(path, "fixture is damaged")
        if content == b"crash":
            raise RuntimeError("third-party parser crashed")
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
    parser: RecordingTextParser, *, max_file_size_bytes: int = 1024
) -> BatchIngestionService:
    return BatchIngestionService(
        ParserRegistry([parser]),
        max_file_size_bytes=max_file_size_bytes,
    )


def test_scan_directory_filters_the_whitelist_and_has_stable_order(
    tmp_path: Path,
) -> None:
    (tmp_path / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "A.TXT").write_text("a", encoding="utf-8")
    (tmp_path / "ignored.pdf").write_bytes(b"pdf")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("b", encoding="utf-8")

    service = make_service(RecordingTextParser())

    non_recursive = service.scan_directory(tmp_path, recursive=False)
    recursive = service.scan_directory(tmp_path, recursive=True)

    assert [path.relative_to(tmp_path).as_posix() for path in non_recursive] == [
        "A.TXT",
        "z.txt",
    ]
    assert [path.relative_to(tmp_path).as_posix() for path in recursive] == [
        "A.TXT",
        "nested/b.txt",
        "z.txt",
    ]


def test_parse_directory_isolates_controlled_and_unexpected_file_failures(
    tmp_path: Path,
) -> None:
    (tmp_path / "01-good.txt").write_text("good", encoding="utf-8")
    (tmp_path / "02-broken.txt").write_bytes(b"broken")
    (tmp_path / "03-crash.txt").write_bytes(b"crash")
    (tmp_path / "04-good.txt").write_text("still good", encoding="utf-8")

    batch = make_service(RecordingTextParser()).parse_directory(tmp_path)

    assert batch.succeeded == 2
    assert batch.skipped == 0
    assert batch.failed == 2
    assert batch.total == 4
    assert [item.status for item in batch.items] == [
        "succeeded",
        "failed",
        "failed",
        "succeeded",
    ]
    assert [result.name for result in batch.results] == [
        "01-good.txt",
        "04-good.txt",
    ]
    assert isinstance(batch.errors[0], CorruptedFileError)
    assert batch.errors[1].code == "INTERNAL_ERROR"
    assert "third-party parser crashed" not in str(batch.errors[1])


def test_parse_directory_skips_duplicate_content_by_sha256(tmp_path: Path) -> None:
    (tmp_path / "first.txt").write_text("same content", encoding="utf-8")
    (tmp_path / "second.txt").write_text("same content", encoding="utf-8")
    parser = RecordingTextParser()

    batch = make_service(parser).parse_directory(tmp_path)

    expected_hash = hashlib.sha256(b"same content").hexdigest()
    assert batch.succeeded == 1
    assert batch.skipped == 1
    assert batch.failed == 0
    assert parser.parsed_paths == [(tmp_path / "first.txt").resolve()]
    assert batch.skips[0].path == (tmp_path / "second.txt").resolve()
    assert batch.skips[0].reason == "duplicate_content"
    assert batch.skips[0].file_id == expected_hash
    assert batch.skips[0].duplicate_of == (tmp_path / "first.txt").resolve()
    assert [item.status for item in batch.items] == ["succeeded", "skipped"]


def test_parse_directory_rejects_oversized_files_before_parsing(
    tmp_path: Path,
) -> None:
    (tmp_path / "large.txt").write_bytes(b"12345")
    (tmp_path / "small.txt").write_bytes(b"1234")
    parser = RecordingTextParser()

    batch = make_service(parser, max_file_size_bytes=4).parse_directory(tmp_path)

    assert batch.succeeded == 1
    assert batch.skipped == 0
    assert batch.failed == 1
    assert parser.parsed_paths == [(tmp_path / "small.txt").resolve()]
    assert isinstance(batch.errors[0], FileTooLargeError)
    assert batch.errors[0].actual_size_bytes == 5
    assert batch.errors[0].max_size_bytes == 4
    assert [item.path.name for item in batch.items] == ["large.txt", "small.txt"]


def test_duplicate_tracking_is_scoped_to_one_batch(tmp_path: Path) -> None:
    source = tmp_path / "only.txt"
    source.write_text("content", encoding="utf-8")
    service = make_service(RecordingTextParser())

    first = service.parse_directory(tmp_path)
    second = service.parse_directory(tmp_path)

    assert first.succeeded == 1
    assert first.skipped == 0
    assert second.succeeded == 1
    assert second.skipped == 0


def test_parse_paths_expands_mixed_files_and_directories(tmp_path: Path) -> None:
    explicit = tmp_path / "explicit.txt"
    explicit.write_text("explicit", encoding="utf-8")
    directory = tmp_path / "reports"
    directory.mkdir()
    (directory / "01-nested.txt").write_text("nested", encoding="utf-8")
    (directory / "02-ignored.bin").write_bytes(b"ignored")

    batch = make_service(RecordingTextParser()).parse_paths(
        [explicit, directory],
        authorized_roots=[tmp_path],
    )

    assert [item.path.name for item in batch.items] == [
        "explicit.txt",
        "01-nested.txt",
        "02-ignored.bin",
    ]
    assert batch.succeeded == 2
    assert batch.skipped == 1
    assert batch.failed == 0
    assert batch.total == 3
    assert batch.skips[0].reason == "unsupported_format"


def test_parse_paths_respects_non_recursive_directory_scan(tmp_path: Path) -> None:
    (tmp_path / "visible.txt").write_text("visible", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "hidden.txt").write_text("hidden", encoding="utf-8")

    batch = make_service(RecordingTextParser()).parse_paths(
        [tmp_path],
        recursive=False,
        authorized_roots=[tmp_path],
    )

    assert [result.name for result in batch.results] == ["visible.txt"]
    assert batch.total == 1


def test_parse_paths_reports_explicit_unsupported_file(tmp_path: Path) -> None:
    unsupported = tmp_path / "archive.bin"
    unsupported.write_bytes(b"unsupported")

    batch = make_service(RecordingTextParser()).parse_paths(
        [unsupported],
        authorized_roots=[tmp_path],
    )

    assert batch.total == 1
    assert batch.failed == 1
    assert batch.errors[0].code == "UNSUPPORTED_FORMAT"


def test_explicit_unsupported_file_wins_over_size_validation(
    tmp_path: Path,
) -> None:
    unsupported = tmp_path / "large.bin"
    unsupported.write_bytes(b"12345")

    batch = make_service(
        RecordingTextParser(),
        max_file_size_bytes=4,
    ).parse_paths(
        [unsupported],
        authorized_roots=[tmp_path],
    )

    assert batch.failed == 1
    assert batch.errors[0].code == "UNSUPPORTED_FORMAT"


def test_parse_paths_reports_missing_input_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"

    batch = make_service(RecordingTextParser()).parse_paths(
        [missing],
        authorized_roots=[tmp_path],
    )

    assert batch.total == 1
    assert batch.failed == 1
    assert batch.errors[0].code == "PATH_NOT_FOUND"


def test_parse_paths_rejects_path_outside_authorized_roots(
    tmp_path: Path,
) -> None:
    authorized = tmp_path / "authorized"
    authorized.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    batch = make_service(RecordingTextParser()).parse_paths(
        [outside],
        authorized_roots=[authorized],
    )

    assert batch.total == 1
    assert batch.failed == 1
    assert batch.errors[0].code == "PATH_NOT_AUTHORIZED"


def test_parse_paths_deduplicates_the_same_real_path(tmp_path: Path) -> None:
    directory = tmp_path / "reports"
    directory.mkdir()
    source = directory / "notes.txt"
    source.write_text("same file", encoding="utf-8")
    parser = RecordingTextParser()

    batch = make_service(parser).parse_paths(
        [source, directory],
        authorized_roots=[tmp_path],
    )

    assert batch.total == 1
    assert batch.succeeded == 1
    assert batch.skipped == 0
    assert parser.parsed_paths == [source.resolve()]
