import codecs
import hashlib
from pathlib import Path

import pytest

from content_retrieval.domain.errors import TextDecodeError
from content_retrieval.parsers.txt import TxtParser


def parse_bytes(tmp_path: Path, name: str, content: bytes):
    source = tmp_path / name
    source.write_bytes(content)
    return source, TxtParser().parse(source)


def test_tc_085_decodes_utf8_bom_without_returning_the_bom(tmp_path: Path) -> None:
    _, result = parse_bytes(tmp_path, "utf8.txt", codecs.BOM_UTF8 + "正文".encode())

    assert result.text == "正文"
    assert result.metadata["encoding"] == "utf-8-sig"


def test_tc_086_decodes_utf16_little_endian_bom(tmp_path: Path) -> None:
    _, result = parse_bytes(tmp_path, "utf16le.txt", "正文".encode("utf-16"))

    assert result.text == "正文"
    assert result.metadata["encoding"] == "utf-16"


def test_tc_087_decodes_utf16_big_endian_bom(tmp_path: Path) -> None:
    content = codecs.BOM_UTF16_BE + "正文".encode("utf-16-be")

    _, result = parse_bytes(tmp_path, "utf16be.txt", content)

    assert result.text == "正文"
    assert result.metadata["encoding"] == "utf-16"


def test_tc_088_decodes_utf32_little_endian_bom(tmp_path: Path) -> None:
    content = codecs.BOM_UTF32_LE + "正文".encode("utf-32-le")

    _, result = parse_bytes(tmp_path, "utf32le.txt", content)

    assert result.text == "正文"
    assert result.metadata["encoding"] == "utf-32"


def test_tc_089_decodes_utf32_big_endian_bom(tmp_path: Path) -> None:
    content = codecs.BOM_UTF32_BE + "正文".encode("utf-32-be")

    _, result = parse_bytes(tmp_path, "utf32be.txt", content)

    assert result.text == "正文"
    assert result.metadata["encoding"] == "utf-32"


def test_tc_090_decodes_ascii_as_utf8(tmp_path: Path) -> None:
    _, result = parse_bytes(tmp_path, "ascii.txt", b"plain ascii")

    assert result.text == "plain ascii"
    assert result.metadata["encoding"] == "utf-8"


def test_tc_091_reports_crlf_newlines(tmp_path: Path) -> None:
    _, result = parse_bytes(tmp_path, "crlf.txt", b"one\r\ntwo\r\n")

    assert result.metadata["newline_style"] == "crlf"


def test_tc_092_reports_lf_newlines(tmp_path: Path) -> None:
    _, result = parse_bytes(tmp_path, "lf.txt", b"one\ntwo\n")

    assert result.metadata["newline_style"] == "lf"


def test_tc_093_reports_cr_newlines(tmp_path: Path) -> None:
    _, result = parse_bytes(tmp_path, "cr.txt", b"one\rtwo\r")

    assert result.metadata["newline_style"] == "cr"


def test_tc_094_reports_mixed_newlines(tmp_path: Path) -> None:
    _, result = parse_bytes(tmp_path, "mixed.txt", b"one\r\ntwo\nthree\r")

    assert result.metadata["newline_style"] == "mixed"


def test_tc_095_reports_no_newline_for_a_single_line(tmp_path: Path) -> None:
    _, result = parse_bytes(tmp_path, "single.txt", b"single line")

    assert result.metadata["newline_style"] == "none"


def test_tc_096_preserves_emoji_and_supplementary_characters(tmp_path: Path) -> None:
    text = "检索 🧪 𠀀"
    _, result = parse_bytes(tmp_path, "unicode.txt", text.encode("utf-8"))

    assert result.text == text
    assert result.metadata["character_count"] == len(text)


def test_tc_097_does_not_normalize_combining_characters(tmp_path: Path) -> None:
    text = "Cafe\u0301"
    _, result = parse_bytes(tmp_path, "combining.txt", text.encode("utf-8"))

    assert result.text == text
    assert result.text != "Café"


def test_tc_098_preserves_a_long_single_line(tmp_path: Path) -> None:
    text = "数据" * 50_000
    _, result = parse_bytes(tmp_path, "long.txt", text.encode("utf-8"))

    assert result.text == text
    assert result.metadata["character_count"] == 100_000


def test_tc_099_preserves_a_trailing_newline(tmp_path: Path) -> None:
    _, result = parse_bytes(tmp_path, "trailing.txt", b"line\n")

    assert result.text == "line\n"


def test_tc_100_rejects_an_invalid_utf8_continuation_byte(tmp_path: Path) -> None:
    source = tmp_path / "invalid.txt"
    source.write_bytes(b"prefix\x80suffix")

    with pytest.raises(TextDecodeError) as raised:
        TxtParser().parse(source)

    assert raised.value.encoding == "utf-8"


def test_tc_101_preserves_nul_characters(tmp_path: Path) -> None:
    _, result = parse_bytes(tmp_path, "nul.txt", b"before\x00after")

    assert result.text == "before\x00after"
    assert result.warnings == []


def test_tc_102_reports_txt_file_information(tmp_path: Path) -> None:
    content = "metadata".encode("utf-8")
    source, result = parse_bytes(tmp_path, "metadata.txt", content)

    assert result.path == source.resolve()
    assert result.name == source.name
    assert result.size_bytes == len(content)
    assert result.file_id == hashlib.sha256(content).hexdigest()
    assert result.modified_at.tzinfo is not None
