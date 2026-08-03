from pathlib import Path

import httpx
import pytest

from content_retrieval.domain.errors import InternalParseError
from content_retrieval.parsers.docx import DOCX_MIME_TYPE, DocxParser
from content_retrieval.parsers.tika import TikaClient


def source_docx(tmp_path: Path, name: str = "sample.docx") -> Path:
    source = tmp_path / name
    source.write_bytes(b"docx bytes")
    return source


def parser_for(handler, **client_options: object) -> DocxParser:
    return DocxParser(
        TikaClient(
            transport=httpx.MockTransport(handler),
            **client_options,
        )
    )


def response_with(payload: object, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


def test_tc_125_tika_uses_put_rmeta_text(tmp_path: Path) -> None:
    seen: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return response_with([{"X-TIKA:content": "body"}])

    parser_for(handle).parse(source_docx(tmp_path))

    assert seen == [("PUT", "/rmeta/text")]


def test_tc_126_tika_sends_docx_content_and_json_accept_headers(tmp_path: Path) -> None:
    seen: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        seen["content_type"] = request.headers["content-type"]
        seen["accept"] = request.headers["accept"]
        return response_with([{"X-TIKA:content": "body"}])

    parser_for(handle).parse(source_docx(tmp_path))

    assert seen == {"content_type": DOCX_MIME_TYPE, "accept": "application/json"}


def test_tc_127_tika_uses_a_custom_base_url(tmp_path: Path) -> None:
    seen_hosts: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen_hosts.append(request.url.host)
        return response_with([{"X-TIKA:content": "body"}])

    parser_for(handle, base_url="http://tika.local:9998").parse(source_docx(tmp_path))

    assert seen_hosts == ["tika.local"]


def test_tc_128_tika_applies_the_configured_timeout(tmp_path: Path) -> None:
    seen_timeout: list[dict[str, float]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen_timeout.append(request.extensions["timeout"])
        return response_with([{"X-TIKA:content": "body"}])

    parser_for(handle, timeout_seconds=1.25).parse(source_docx(tmp_path))

    assert seen_timeout == [
        {"connect": 1.25, "read": 1.25, "write": 1.25, "pool": 1.25}
    ]


def test_tc_129_tika_disables_environment_proxy_inheritance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from content_retrieval.parsers import tika as tika_module

    captured: dict[str, object] = {}
    real_client = httpx.Client

    def recording_client(*args: object, **kwargs: object) -> httpx.Client:
        captured.update(kwargs)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(tika_module.httpx, "Client", recording_client)

    def handle(request: httpx.Request) -> httpx.Response:
        return response_with([{"X-TIKA:content": "body"}])

    parser_for(handle).parse(source_docx(tmp_path))

    assert captured["trust_env"] is False


def test_tc_130_tika_maps_http_400_to_internal_error(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    with pytest.raises(InternalParseError):
        parser_for(handle).parse(source_docx(tmp_path))


def test_tc_131_tika_maps_http_500_to_internal_error(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    with pytest.raises(InternalParseError):
        parser_for(handle).parse(source_docx(tmp_path))


def test_tc_132_tika_maps_invalid_json_to_internal_error(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    with pytest.raises(InternalParseError):
        parser_for(handle).parse(source_docx(tmp_path))


def test_tc_133_tika_rejects_an_empty_result_list(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with([])

    with pytest.raises(InternalParseError):
        parser_for(handle).parse(source_docx(tmp_path))


def test_tc_134_tika_rejects_a_dictionary_instead_of_a_list(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with({"X-TIKA:content": "body"})

    with pytest.raises(InternalParseError):
        parser_for(handle).parse(source_docx(tmp_path))


def test_tc_135_tika_rejects_a_non_dictionary_first_item(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with(["not metadata"])

    with pytest.raises(InternalParseError):
        parser_for(handle).parse(source_docx(tmp_path))


def test_tc_136_docx_warns_when_tika_content_is_missing(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with([{"dc:title": "Title"}])

    result = parser_for(handle).parse(source_docx(tmp_path))

    assert result.text == ""
    assert result.warnings == ["document contains no extractable text"]


def test_tc_137_docx_treats_non_string_content_as_empty(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with([{"X-TIKA:content": ["body"]}])

    result = parser_for(handle).parse(source_docx(tmp_path))

    assert result.text == ""
    assert result.warnings == ["document contains no extractable text"]


def test_tc_138_docx_normalizes_crlf_and_cr_line_endings(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with([{"X-TIKA:content": "one\r\ntwo\rthree"}])

    assert parser_for(handle).parse(source_docx(tmp_path)).text == "one\ntwo\nthree"


def test_tc_139_docx_trims_each_line(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with([{"X-TIKA:content": "  one  \n  two\t"}])

    assert parser_for(handle).parse(source_docx(tmp_path)).text == "one\ntwo"


def test_tc_140_docx_collapses_three_or_more_newlines(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with([{"X-TIKA:content": "one\n\n\n\n\ntwo"}])

    assert parser_for(handle).parse(source_docx(tmp_path)).text == "one\n\ntwo"


def test_tc_141_docx_trims_title_metadata(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with([{"X-TIKA:content": "body", "dc:title": "  Report  "}])

    assert parser_for(handle).parse(source_docx(tmp_path)).metadata["title"] == "Report"


def test_tc_142_docx_prefers_meta_author(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with(
            [
                {
                    "X-TIKA:content": "body",
                    "meta:author": "Primary",
                    "dc:creator": "Fallback",
                }
            ]
        )

    assert parser_for(handle).parse(source_docx(tmp_path)).metadata["author"] == "Primary"


def test_tc_143_docx_falls_back_to_dc_creator(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with(
            [{"X-TIKA:content": "body", "meta:author": " ", "dc:creator": "Ada"}]
        )

    assert parser_for(handle).parse(source_docx(tmp_path)).metadata["author"] == "Ada"


def test_tc_144_docx_exposes_only_safe_metadata_fields(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return response_with(
            [
                {
                    "X-TIKA:content": "body",
                    "dc:title": "Title",
                    "meta:author": "Author",
                    "dcterms:created": "2026-07-01T00:00:00Z",
                    "dcterms:modified": "2026-07-02T00:00:00Z",
                    "resourceName": "secret-path.docx",
                    "X-Parsed-By": "parser implementation",
                }
            ]
        )

    assert parser_for(handle).parse(source_docx(tmp_path)).metadata == {
        "title": "Title",
        "author": "Author",
        "created_at": "2026-07-01T00:00:00Z",
        "modified_at": "2026-07-02T00:00:00Z",
    }
