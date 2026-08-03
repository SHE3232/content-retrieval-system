import hashlib
from pathlib import Path
import struct
from zipfile import ZIP_DEFLATED, ZipFile
import zlib

import httpx
from PIL import Image
import pytest

from content_retrieval.domain.errors import (
    ImageDecodeError,
    ParseTimeoutError,
    TikaUnavailableError,
)
from content_retrieval.parsers import (
    DocxParser,
    ImageParser,
    TikaClient,
    create_default_registry,
)


DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def write_docx_fixture(path: Path) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>第一周</w:t></w:r></w:p>
    <w:p><w:r><w:t>开发环境</w:t></w:r></w:p>
    <w:p><w:r><w:t>风险</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>""",
        )


def test_docx_parser_uses_tika_http_timeout_and_whitelists_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "plan.docx"
    source.write_bytes(b"docx payload")

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/rmeta/text"
        assert request.headers["content-type"] == DOCX_MIME_TYPE
        assert request.headers["accept"] == "application/json"
        assert request.content == b"docx payload"
        assert request.extensions["timeout"] == {
            "connect": 0.25,
            "read": 0.25,
            "write": 0.25,
            "pool": 0.25,
        }
        return httpx.Response(
            200,
            json=[
                {
                    "X-TIKA:content": " Heading  \r\n\r\nBody text   \n",
                    "Content-Type": DOCX_MIME_TYPE,
                    "dc:title": "Project plan",
                    "meta:author": "Test author",
                    "dcterms:created": "2026-07-18T01:02:03Z",
                    "dcterms:modified": "2026-07-18T04:05:06Z",
                    "resourceName": "plan.docx",
                    "X-Parsed-By": "org.apache.tika.parser.DefaultParser",
                }
            ],
        )

    parser = DocxParser(
        TikaClient(
            timeout_seconds=0.25,
            transport=httpx.MockTransport(handle),
        )
    )

    result = parser.parse(source)

    assert result.text == "Heading\n\nBody text"
    assert result.mime_type == DOCX_MIME_TYPE
    assert result.modality == "document"
    assert result.metadata == {
        "title": "Project plan",
        "author": "Test author",
        "created_at": "2026-07-18T01:02:03Z",
        "modified_at": "2026-07-18T04:05:06Z",
    }


def test_docx_parser_maps_tika_dc_creator_to_author(tmp_path: Path) -> None:
    source = tmp_path / "author.docx"
    source.write_bytes(b"docx payload")

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "X-TIKA:content": "Document body",
                    "dc:creator": "Tika author",
                }
            ],
        )

    parser = DocxParser(TikaClient(transport=httpx.MockTransport(handle)))

    assert parser.parse(source).metadata == {"author": "Tika author"}


def test_docx_parser_returns_structured_error_when_tika_is_not_running(
    tmp_path: Path,
) -> None:
    source = tmp_path / "offline.docx"
    source.write_bytes(b"docx payload")

    def fail_to_connect(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    parser = DocxParser(
        TikaClient(transport=httpx.MockTransport(fail_to_connect))
    )

    with pytest.raises(TikaUnavailableError) as raised:
        parser.parse(source)

    assert raised.value.path == source
    assert raised.value.to_dict() == {
        "code": "TIKA_UNAVAILABLE",
        "message": "Apache Tika is unavailable while parsing offline.docx",
        "retryable": True,
    }


def test_docx_parser_turns_http_timeout_into_structured_error(
    tmp_path: Path,
) -> None:
    source = tmp_path / "slow.docx"
    source.write_bytes(b"docx payload")

    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    parser = DocxParser(TikaClient(transport=httpx.MockTransport(time_out)))

    with pytest.raises(ParseTimeoutError) as raised:
        parser.parse(source)

    assert raised.value.path == source
    assert raised.value.to_dict()["code"] == "PARSE_TIMEOUT"
    assert raised.value.to_dict()["retryable"] is True


def test_real_tika_extracts_a_generated_docx(tmp_path: Path) -> None:
    source = tmp_path / "tika-fixture.docx"
    write_docx_fixture(source)

    try:
        result = DocxParser(TikaClient(timeout_seconds=10)).parse(source)
    except TikaUnavailableError:
        pytest.skip("real Tika integration test requires 127.0.0.1:9998")

    assert result.file_id == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result.text
    for keyword in ("第一周", "开发环境", "风险"):
        assert keyword in result.text


def test_image_parser_extracts_jpg_dimensions_mode_and_safe_exif(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fixture.jpg"
    exif = Image.Exif()
    exif[270] = "Small JPG fixture"
    exif[274] = 1
    Image.new("RGB", (4, 3), "white").save(
        source,
        format="JPEG",
        exif=exif,
    )

    result = ImageParser().parse(source)

    assert result.file_id == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result.mime_type == "image/jpeg"
    assert result.modality == "image"
    assert result.text is None
    assert (result.width, result.height) == (4, 3)
    assert result.metadata == {
        "format": "JPEG",
        "color_mode": "RGB",
        "exif": {
            "image_description": "Small JPG fixture",
            "orientation": 1,
        },
    }


def test_image_parser_extracts_generated_png_metadata(tmp_path: Path) -> None:
    source = tmp_path / "fixture.png"
    Image.new("RGBA", (64, 64), (10, 20, 30, 255)).save(
        source,
        format="PNG",
    )

    result = ImageParser().parse(source)

    assert result.mime_type == "image/png"
    assert (result.width, result.height) == (64, 64)
    assert result.metadata["format"] == "PNG"
    assert result.metadata["color_mode"] in {"RGB", "RGBA"}
    assert result.metadata["exif"] == {}


def test_image_parser_rejects_a_damaged_jpg(tmp_path: Path) -> None:
    source = tmp_path / "damaged.jpg"
    source.write_bytes(b"\xff\xd8\xff\xe0broken jpeg data")

    with pytest.raises(ImageDecodeError) as raised:
        ImageParser().parse(source)

    assert raised.value.path == source
    assert raised.value.to_dict()["code"] == "IMAGE_DECODE_ERROR"


def test_image_parser_rejects_a_damaged_later_apng_frame(
    tmp_path: Path,
) -> None:
    source = tmp_path / "damaged-later-frame.png"
    first = Image.new("RGB", (8, 8), "red")
    second = Image.new("RGB", (8, 8), "blue")
    first.save(
        source,
        format="PNG",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )

    content = bytearray(source.read_bytes())
    offset = 8
    while offset < len(content):
        length = struct.unpack_from(">I", content, offset)[0]
        chunk_type = bytes(content[offset + 4 : offset + 8])
        data_start = offset + 8
        data_end = data_start + length
        if chunk_type == b"fdAT":
            content[data_start + 4 : data_end] = b"\x00" * (length - 4)
            crc = zlib.crc32(chunk_type)
            crc = zlib.crc32(content[data_start:data_end], crc)
            struct.pack_into(">I", content, data_end, crc & 0xFFFFFFFF)
            source.write_bytes(content)
            break
        offset = data_end + 4
    else:
        raise AssertionError("Pillow did not generate an fdAT chunk")

    with pytest.raises(ImageDecodeError) as raised:
        ImageParser().parse(source)

    assert raised.value.path == source
    assert raised.value.to_dict()["code"] == "IMAGE_DECODE_ERROR"


def test_default_registry_routes_docx_jpg_jpeg_and_png() -> None:
    registry = create_default_registry()

    assert isinstance(registry.resolve(Path("sample.DOCX")), DocxParser)
    assert isinstance(registry.resolve(Path("sample.JPG")), ImageParser)
    assert isinstance(registry.resolve(Path("sample.JPEG")), ImageParser)
    assert isinstance(registry.resolve(Path("sample.PNG")), ImageParser)
