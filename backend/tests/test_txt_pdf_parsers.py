import base64
import hashlib
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from content_retrieval.domain.errors import (
    CorruptedFileError,
    EncryptedPdfError,
    TextDecodeError,
)
from content_retrieval.parsers import PdfParser, TxtParser, create_default_registry


ENCRYPTED_BLANK_PDF = base64.b64decode(
    "JVBERi0xLjMKJeLjz9MKMSAwIG9iago8PAovUHJvZHVjZXIgPDM1YzY5Y2I1ZTA+"
    "Cj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9UeXBlIC9QYWdlcwovQ291bnQgMQovS2lk"
    "cyBbIDQgMCBSIF0KPj4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL0NhdGFsb2cK"
    "L1BhZ2VzIDIgMCBSCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9UeXBlIC9QYWdlCi9S"
    "ZXNvdXJjZXMgPDwKPj4KL01lZGlhQm94IFsgMC4wIDAuMCA3MiA3MiBdCi9QYXJl"
    "bnQgMiAwIFIKPj4KZW5kb2JqCjUgMCBvYmoKPDwKL1YgMgovUiAzCi9MZW5ndGgg"
    "MTI4Ci9QIDQyOTQ5NjcyOTIKL0ZpbHRlciAvU3RhbmRhcmQKL08gPDBlNTIyOTI1"
    "YTNlNGU4NzRjM2NmYWNiZWY1MTFhNzNhYzRlYzJiZDg2NWRjZDNkNDYyNzYxNDkx"
    "N2FiZmQ3ZTQ+Ci9VIDxiNjIzNzAzMjY3YTBjODJlMzliYmIwMTc0YTVlODUzNDI4"
    "YmY0ZTVlNGU3NThhNDE2NDAwNGU1NmZmZmEwMTA4Pgo+PgplbmRvYmoKeHJlZgow"
    "IDYKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDE1IDAwMDAwIG4gCjAwMDAw"
    "MDAwNTkgMDAwMDAgbiAKMDAwMDAwMDExOCAwMDAwMCBuIAowMDAwMDAwMTY3IDAw"
    "MDAwIG4gCjAwMDAwMDAyNTkgMDAwMDAgbiAKdHJhaWxlcgo8PAovU2l6ZSA2Ci9S"
    "b290IDMgMCBSCi9JbmZvIDEgMCBSCi9JRCBbIDw2NDY2NjM2MTY2NjM1MzQzMjM3"
    "MzkzMDMzMzIzMDM2NjQ2NDMxMzEzNDM0MzE2NDMwNjIzNTYyNjEzOTM2MzE2Mj4g"
    "PDY0NjY2MzYxNjYzNTM0MzIzNzM5MzAzMzMyMzAzNjY0NjQzMTMxMzQzNDMxNjQz"
    "MDYyMzU2MjYxMzkzNjMxNjI+IF0KL0VuY3J5cHQgNSAwIFIKPj4Kc3RhcnR4cmVm"
    "CjQ3NAolJUVPRgo="
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_text_pdf_fixture(path: Path) -> None:
    streams = (
        b"BT /F1 12 Tf 72 750 Td (Software Engineering Project) Tj "
        b"0 -20 Td (Duration) Tj 0 -20 Td (Project Background) Tj "
        b"0 -20 Td (Core Tech Stack) Tj ET",
        b"BT /F1 12 Tf 72 750 Td (Flutter Chroma DB WCAG) Tj ET",
    )
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 7 0 R >> >> /Contents 5 0 R >>"
        ),
        4: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>"
        ),
        5: (
            f"<< /Length {len(streams[0])} >>\nstream\n".encode("ascii")
            + streams[0]
            + b"\nendstream"
        ),
        6: (
            f"<< /Length {len(streams[1])} >>\nstream\n".encode("ascii")
            + streams[1]
            + b"\nendstream"
        ),
        7: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }

    payload = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, 8):
        offsets.append(len(payload))
        payload.extend(f"{object_id} 0 obj\n".encode("ascii"))
        payload.extend(objects[object_id])
        payload.extend(b"\nendobj\n")

    xref_offset = len(payload)
    payload.extend(b"xref\n0 8\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        b"trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    path.write_bytes(payload)


@pytest.mark.parametrize("sample_id", ["D001", "D002", "D003"])
def test_txt_parser_extracts_utf8_generated_samples(
    sample_id: str,
    tmp_path: Path,
) -> None:
    contents = {
        "D001": "离线语义检索支持 PDF 文档。\n",
        "D002": "keyboard screen-reader contrast\n",
        "D003": "Windows semantic search 本地检索\n",
    }
    source = tmp_path / f"{sample_id.lower()}.txt"
    source.write_text(contents[sample_id], encoding="utf-8")

    result = TxtParser().parse(source)

    assert result.file_id == sha256_file(source)
    assert result.modality == "text"
    assert result.metadata["encoding"] == "utf-8"
    assert result.metadata["character_count"] == len(result.text)
    assert result.text

    expected_markers = {
        "D001": ("离线", "PDF"),
        "D002": ("keyboard", "screen-reader", "contrast"),
        "D003": ("Windows", "semantic search", "本地检索"),
    }
    assert all(marker in result.text for marker in expected_markers[sample_id])


def test_txt_parser_accepts_an_empty_file(tmp_path: Path) -> None:
    source = tmp_path / "empty.txt"
    source.write_bytes(b"")

    result = TxtParser().parse(source)

    assert result.text == ""
    assert result.size_bytes == 0
    assert result.metadata["character_count"] == 0
    assert "empty text file" in result.warnings


def test_txt_parser_rejects_invalid_utf8_without_guessing(tmp_path: Path) -> None:
    source = tmp_path / "legacy.txt"
    source.write_bytes(b"invalid byte: \x80")

    with pytest.raises(TextDecodeError) as raised:
        TxtParser().parse(source)

    assert raised.value.path == source
    assert raised.value.encoding == "utf-8"


def test_duplicate_generated_txt_files_have_the_same_sha256(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "duplicate-a.txt"
    second_path = tmp_path / "duplicate-b.txt"
    first_path.write_text("duplicated detection\n", encoding="utf-8")
    second_path.write_bytes(first_path.read_bytes())

    first = TxtParser().parse(first_path)
    second = TxtParser().parse(second_path)

    assert first.file_id == sha256_file(first_path)
    assert second.file_id == sha256_file(second_path)
    assert first.file_id == second.file_id
    assert first.text == second.text


def test_pdf_parser_extracts_generated_page_count_and_each_page_text(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fixture.pdf"
    write_text_pdf_fixture(source)

    result = PdfParser().parse(source)

    page_texts = result.metadata["page_texts"]
    assert result.file_id == sha256_file(source)
    assert result.page_count == 2
    assert len(page_texts) == result.page_count
    assert all(isinstance(text, str) for text in page_texts)
    assert result.text == "\n\n".join(page_texts)
    for keyword in ("Flutter", "Chroma DB", "WCAG"):
        assert keyword in result.text


def test_pdf_parser_preserves_basic_text_order(tmp_path: Path) -> None:
    source = tmp_path / "fixture.pdf"
    write_text_pdf_fixture(source)

    result = PdfParser().parse(source)
    first_page = result.metadata["page_texts"][0]

    assert first_page.index("Software Engineering Project") < first_page.index("Duration")
    assert first_page.index("Project Background") < first_page.index("Core Tech Stack")


def test_pdf_parser_keeps_a_blank_page_as_an_empty_page(tmp_path: Path) -> None:
    source = tmp_path / "blank.pdf"
    document = pdfium.PdfDocument.new()
    document.new_page(width=595, height=842)
    document.save(source)
    document.close()

    result = PdfParser().parse(source)

    assert result.page_count == 1
    assert result.metadata["page_texts"] == [""]
    assert result.text == ""
    assert "page 1 contains no extractable text" in result.warnings


def test_pdf_parser_turns_a_damaged_pdf_into_a_controlled_error(
    tmp_path: Path,
) -> None:
    source = tmp_path / "damaged.pdf"
    source.write_bytes(b"%PDF-1.7\nthis is not a valid PDF")

    with pytest.raises(CorruptedFileError) as raised:
        PdfParser().parse(source)

    assert raised.value.path == source
    assert "damaged.pdf" in str(raised.value)


def test_pdf_parser_rejects_an_encrypted_pdf_with_a_specific_error(
    tmp_path: Path,
) -> None:
    source = tmp_path / "encrypted.pdf"
    source.write_bytes(ENCRYPTED_BLANK_PDF)

    with pytest.raises(EncryptedPdfError) as raised:
        PdfParser().parse(source)

    assert raised.value.path == source


def test_default_registry_routes_txt_and_pdf() -> None:
    registry = create_default_registry()

    assert isinstance(registry.resolve(Path("sample.TXT")), TxtParser)
    assert isinstance(registry.resolve(Path("sample.PDF")), PdfParser)
