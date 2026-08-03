from datetime import datetime, timezone
from pathlib import Path

import pytest

from content_retrieval.domain.errors import UnsupportedFormatError
from content_retrieval.domain.models import ParseResult
from content_retrieval.parsers import (
    DocxParser,
    ImageParser,
    PdfParser,
    TxtParser,
    create_default_registry,
)
from content_retrieval.parsers.registry import ParserRegistry


class NamedParser:
    supported_extensions: frozenset[str]
    supported_mime_types: frozenset[str]

    def __init__(self, name: str, extensions: set[str], mime_types: set[str]) -> None:
        self.name = name
        self.supported_extensions = frozenset(extensions)
        self.supported_mime_types = frozenset(mime_types)

    def parse(self, path: Path) -> ParseResult:
        return ParseResult(
            file_id="a" * 64,
            path=path,
            name=path.name,
            mime_type="text/plain",
            modality="text",
            size_bytes=0,
            modified_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
        )


def test_tc_075_registration_adds_a_missing_extension_dot() -> None:
    parser = NamedParser("text", {"TXT"}, {"text/plain"})
    registry = ParserRegistry([parser])

    assert registry.supported_extensions == frozenset({".txt"})


def test_tc_076_resolution_normalizes_uppercase_extensions() -> None:
    parser = NamedParser("text", {".txt"}, {"text/plain"})

    assert ParserRegistry([parser]).resolve(Path("NOTES.TXT")) is parser


def test_tc_077_resolution_normalizes_mime_type_case() -> None:
    parser = NamedParser("text", {".txt"}, {"text/plain"})

    assert ParserRegistry([parser]).resolve(Path("notes"), "TEXT/PLAIN") is parser


def test_tc_078_mime_type_takes_priority_over_extension() -> None:
    text = NamedParser("text", {".txt"}, {"text/plain"})
    pdf = NamedParser("pdf", {".pdf"}, {"application/pdf"})

    resolved = ParserRegistry([text, pdf]).resolve(Path("looks-like.txt"), "application/pdf")

    assert resolved is pdf


def test_tc_079_later_registration_replaces_the_same_extension() -> None:
    first = NamedParser("first", {".txt"}, {"text/first"})
    second = NamedParser("second", {".txt"}, {"text/second"})

    registry = ParserRegistry([first, second])

    assert registry.resolve(Path("notes.txt")) is second


def test_tc_080_empty_registry_reports_unsupported_format() -> None:
    with pytest.raises(UnsupportedFormatError):
        ParserRegistry().resolve(Path("notes.txt"))


def test_tc_081_compound_backup_extension_is_not_misclassified() -> None:
    parser = NamedParser("text", {".txt"}, {"text/plain"})

    with pytest.raises(UnsupportedFormatError):
        ParserRegistry([parser]).resolve(Path("notes.txt.bak"))


def test_tc_082_mime_type_whitespace_is_not_silently_guessed() -> None:
    parser = NamedParser("text", {".txt"}, {"text/plain"})

    with pytest.raises(UnsupportedFormatError):
        ParserRegistry([parser]).resolve(Path("no-extension"), " text/plain ")


def test_tc_083_supported_extensions_is_immutable() -> None:
    parser = NamedParser("text", {".txt"}, {"text/plain"})
    extensions = ParserRegistry([parser]).supported_extensions

    with pytest.raises(AttributeError):
        extensions.add(".pdf")  # type: ignore[attr-defined]


def test_tc_084_default_registry_has_the_expected_parser_set() -> None:
    registry = create_default_registry()

    assert registry.supported_extensions == frozenset(
        {".txt", ".pdf", ".docx", ".jpg", ".jpeg", ".png"}
    )
    assert isinstance(registry.resolve(Path("sample.txt")), TxtParser)
    assert isinstance(registry.resolve(Path("sample.pdf")), PdfParser)
    assert isinstance(registry.resolve(Path("sample.docx")), DocxParser)
    assert isinstance(registry.resolve(Path("sample.png")), ImageParser)
