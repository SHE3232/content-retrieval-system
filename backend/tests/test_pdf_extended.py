import shutil
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from content_retrieval.domain.errors import CorruptedFileError, EncryptedPdfError
from content_retrieval.parsers.pdf import PdfParser


class FakeTextPage:
    def __init__(self, text: str = "", *, fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.closed = False

    def get_text_bounded(self, *, errors: str) -> str:
        assert errors == "replace"
        if self.fail:
            raise pdfium.PdfiumError("text extraction failed")
        return self.text

    def close(self) -> None:
        self.closed = True


class FakePage:
    def __init__(self, text_page: FakeTextPage, *, fail_before_text_page: bool = False) -> None:
        self.text_page = text_page
        self.fail_before_text_page = fail_before_text_page
        self.closed = False

    def get_textpage(self) -> FakeTextPage:
        if self.fail_before_text_page:
            raise pdfium.PdfiumError("cannot create text page")
        return self.text_page

    def close(self) -> None:
        self.closed = True


class FakeDocument:
    def __init__(
        self,
        pages: list[FakePage] | None = None,
        *,
        metadata: dict[str, str] | None = None,
        version: int | None = None,
        metadata_error: bool = False,
    ) -> None:
        self.pages = pages or []
        self.metadata = metadata or {}
        self.version = version
        self.metadata_error = metadata_error
        self.closed = False

    def __len__(self) -> int:
        return len(self.pages)

    def __getitem__(self, index: int) -> FakePage:
        return self.pages[index]

    def get_metadata_dict(self) -> dict[str, str]:
        if self.metadata_error:
            raise pdfium.PdfiumError("metadata failed")
        return self.metadata

    def get_version(self) -> int | None:
        if self.metadata_error:
            raise pdfium.PdfiumError("version failed")
        return self.version

    def close(self) -> None:
        self.closed = True


def make_blank_pdf(path: Path, pages: int = 1) -> None:
    document = pdfium.PdfDocument.new()
    for _ in range(pages):
        document.new_page(width=595, height=842)
    document.save(path)
    document.close()


def test_tc_103_parses_a_single_page_pdf(tmp_path: Path) -> None:
    source = tmp_path / "single.pdf"
    make_blank_pdf(source)

    result = PdfParser().parse(source)

    assert result.page_count == 1
    assert result.metadata["page_texts"] == [""]


def test_tc_104_warns_for_each_consecutive_blank_page(tmp_path: Path) -> None:
    source = tmp_path / "blank-pages.pdf"
    make_blank_pdf(source, pages=3)

    result = PdfParser().parse(source)

    assert result.warnings == [
        "page 1 contains no extractable text",
        "page 2 contains no extractable text",
        "page 3 contains no extractable text",
    ]


def test_tc_105_normalizes_pdf_page_line_endings() -> None:
    document = FakeDocument([FakePage(FakeTextPage("  one\r\ntwo\rthree  "))])

    texts, warnings = PdfParser._extract_pages(Path("sample.pdf"), document)

    assert texts == ["one\ntwo\nthree"]
    assert warnings == []


def test_tc_106_normalizes_nonempty_pdf_metadata_keys() -> None:
    document = FakeDocument(
        metadata={"Title": "Report", "Author": "Ada", "Empty": ""},
        version=7,
    )

    metadata = PdfParser._metadata(document)

    assert metadata == {"title": "Report", "author": "Ada", "pdf_version": "1.7"}


def test_tc_107_returns_empty_metadata_when_none_is_available() -> None:
    assert PdfParser._metadata(FakeDocument()) == {}


def test_tc_108_formats_the_pdf_version() -> None:
    assert PdfParser._metadata(FakeDocument(version=4)) == {"pdf_version": "1.4"}


def test_tc_109_recovers_from_pdf_metadata_errors() -> None:
    assert PdfParser._metadata(FakeDocument(metadata_error=True)) == {}


def test_tc_110_maps_page_text_errors_to_corrupted_file() -> None:
    document = FakeDocument([FakePage(FakeTextPage(fail=True))])

    with pytest.raises(CorruptedFileError, match="page text extraction failed"):
        PdfParser._extract_pages(Path("broken.pdf"), document)


def test_tc_111_maps_non_password_open_errors_to_corruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_open(path: Path):
        raise pdfium.PdfiumError("invalid header")

    monkeypatch.setattr(pdfium, "PdfDocument", fail_open)

    with pytest.raises(CorruptedFileError, match="invalid PDF structure"):
        PdfParser._open(Path("broken.pdf"))


def test_tc_112_detects_password_errors_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_open(path: Path):
        raise pdfium.PdfiumError("PASSWORD required")

    monkeypatch.setattr(pdfium, "PdfDocument", fail_open)

    with pytest.raises(EncryptedPdfError):
        PdfParser._open(Path("locked.pdf"))


def test_tc_113_handles_a_zero_page_document_without_indexing() -> None:
    texts, warnings = PdfParser._extract_pages(Path("empty.pdf"), FakeDocument())

    assert texts == []
    assert warnings == []


def test_tc_114_closes_each_page_after_successful_extraction() -> None:
    page = FakePage(FakeTextPage("text"))

    PdfParser._extract_pages(Path("sample.pdf"), FakeDocument([page]))

    assert page.closed is True


def test_tc_115_closes_each_text_page_after_successful_extraction() -> None:
    text_page = FakeTextPage("text")

    PdfParser._extract_pages(Path("sample.pdf"), FakeDocument([FakePage(text_page)]))

    assert text_page.closed is True


def test_tc_116_closes_the_document_after_successful_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"valid-enough-for-hash")
    document = FakeDocument([FakePage(FakeTextPage("body"))])
    monkeypatch.setattr(PdfParser, "_open", staticmethod(lambda path: document))

    PdfParser().parse(source)

    assert document.closed is True


def test_tc_117_closes_resources_when_text_page_creation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "broken.pdf"
    source.write_bytes(b"broken")
    page = FakePage(FakeTextPage(), fail_before_text_page=True)
    document = FakeDocument([page])
    monkeypatch.setattr(PdfParser, "_open", staticmethod(lambda path: document))

    with pytest.raises(CorruptedFileError):
        PdfParser().parse(source)

    assert page.closed is True
    assert document.closed is True


def test_tc_118_preserves_cjk_and_mixed_language_text() -> None:
    text = "离线检索 / semantic search"
    document = FakeDocument([FakePage(FakeTextPage(text))])

    texts, _ = PdfParser._extract_pages(Path("unicode.pdf"), document)

    assert texts == [text]


def test_tc_119_does_not_drop_text_from_rotated_page_adapters() -> None:
    document = FakeDocument([FakePage(FakeTextPage("rotated page text"))])

    texts, _ = PdfParser._extract_pages(Path("rotated.pdf"), document)

    assert texts == ["rotated page text"]


def test_tc_120_extracts_one_hundred_pages_in_order() -> None:
    document = FakeDocument(
        [FakePage(FakeTextPage(f"page {index}")) for index in range(1, 101)]
    )

    texts, warnings = PdfParser._extract_pages(Path("large.pdf"), document)

    assert texts == [f"page {index}" for index in range(1, 101)]
    assert warnings == []


def test_tc_121_same_pdf_bytes_have_stable_hashes(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    make_blank_pdf(first)
    shutil.copyfile(first, second)

    assert PdfParser().parse(first).file_id == PdfParser().parse(second).file_id


def test_tc_122_changed_pdf_bytes_change_the_hash(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    make_blank_pdf(first)
    shutil.copyfile(first, second)
    second.write_bytes(second.read_bytes() + b"\n% changed after EOF")

    assert PdfParser().parse(first).file_id != PdfParser().parse(second).file_id


def test_tc_123_joins_page_text_with_double_newlines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "multi.pdf"
    source.write_bytes(b"multi")
    document = FakeDocument(
        [FakePage(FakeTextPage("first")), FakePage(FakeTextPage("second"))]
    )
    monkeypatch.setattr(PdfParser, "_open", staticmethod(lambda path: document))

    result = PdfParser().parse(source)

    assert result.text == "first\n\nsecond"


def test_tc_124_all_blank_pages_keep_positions_and_warnings(tmp_path: Path) -> None:
    source = tmp_path / "all-blank.pdf"
    make_blank_pdf(source, pages=4)

    result = PdfParser().parse(source)

    assert result.page_count == 4
    assert result.metadata["page_texts"] == ["", "", "", ""]
    assert len(result.warnings) == 4
