import codecs
from pathlib import Path

from content_retrieval.domain.errors import TextDecodeError
from content_retrieval.domain.models import ParseResult

from ._file_info import modified_at, sha256_bytes


class TxtParser:
    supported_extensions = frozenset({".txt"})
    supported_mime_types = frozenset({"text/plain"})

    _BOM_ENCODINGS = (
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_BE, "utf-16"),
        (codecs.BOM_UTF16_LE, "utf-16"),
    )

    def parse(self, path: Path) -> ParseResult:
        content = path.read_bytes()
        encoding = self._encoding_for(content)
        try:
            text = content.decode(encoding, errors="strict")
        except UnicodeDecodeError as error:
            raise TextDecodeError(path, encoding) from error

        warnings = ["empty text file"] if not content else []
        return ParseResult(
            file_id=sha256_bytes(content),
            path=path.resolve(),
            name=path.name,
            mime_type="text/plain",
            modality="text",
            size_bytes=len(content),
            modified_at=modified_at(path),
            text=text,
            metadata={
                "encoding": encoding,
                "newline_style": self._newline_style(text),
                "character_count": len(text),
            },
            warnings=warnings,
        )

    @classmethod
    def _encoding_for(cls, content: bytes) -> str:
        for bom, encoding in cls._BOM_ENCODINGS:
            if content.startswith(bom):
                return encoding
        return "utf-8"

    @staticmethod
    def _newline_style(text: str) -> str:
        crlf_count = text.count("\r\n")
        remaining = text.replace("\r\n", "")
        styles = {
            name
            for name, present in (
                ("crlf", crlf_count > 0),
                ("lf", "\n" in remaining),
                ("cr", "\r" in remaining),
            )
            if present
        }
        if not styles:
            return "none"
        if len(styles) > 1:
            return "mixed"
        return styles.pop()


TextParser = TxtParser
