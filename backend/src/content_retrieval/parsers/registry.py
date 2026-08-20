from collections.abc import Iterable
from pathlib import Path

from content_retrieval.domain.errors import UnsupportedFormatError

from .base import Parser


class ParserRegistry:
    def __init__(self, parsers: Iterable[Parser] = ()) -> None:
        self._by_extension: dict[str, Parser] = {}
        self._by_mime_type: dict[str, Parser] = {}
        for parser in parsers:
            self.register(parser)

    def register(self, parser: Parser) -> None:
        for extension in parser.supported_extensions:
            normalized = extension.lower()
            if not normalized.startswith("."):
                normalized = f".{normalized}"
            self._by_extension[normalized] = parser

        for mime_type in parser.supported_mime_types:
            self._by_mime_type[mime_type.lower()] = parser

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset(self._by_extension)

    def resolve(self, path: Path, mime_type: str | None = None) -> Parser:
        if mime_type:
            parser = self._by_mime_type.get(mime_type.lower())
            if parser is not None:
                return parser

        parser = self._by_extension.get(path.suffix.lower())
        if parser is not None:
            return parser

        raise UnsupportedFormatError(path, mime_type)


def create_default_registry(
    *,
    tika_url: str = "http://127.0.0.1:9998",
) -> ParserRegistry:
    from .docx import DocxParser
    from .image import ImageParser
    from .pdf import PdfParser
    from .tika import TikaClient
    from .txt import TxtParser

    return ParserRegistry(
        [
            TxtParser(),
            PdfParser(),
            DocxParser(TikaClient(tika_url)),
            ImageParser(),
        ]
    )
