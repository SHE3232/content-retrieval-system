from pathlib import Path
import re
from typing import Any

from content_retrieval.domain.models import ParseResult

from ._file_info import modified_at, sha256_bytes
from .tika import TikaClient


DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


class DocxParser:
    supported_extensions = frozenset({".docx"})
    supported_mime_types = frozenset({DOCX_MIME_TYPE})

    _METADATA_FIELDS = {
        "title": ("dc:title",),
        "author": ("meta:author", "dc:creator"),
        "created_at": ("dcterms:created",),
        "modified_at": ("dcterms:modified",),
    }

    def __init__(self, tika_client: TikaClient | None = None) -> None:
        self.tika_client = tika_client or TikaClient()

    def parse(self, path: Path) -> ParseResult:
        content = path.read_bytes()
        tika_metadata = self.tika_client.extract(
            path,
            content,
            DOCX_MIME_TYPE,
        )
        text = self._normalize_text(tika_metadata.get("X-TIKA:content"))

        return ParseResult(
            file_id=sha256_bytes(content),
            path=path.resolve(),
            name=path.name,
            mime_type=DOCX_MIME_TYPE,
            modality="document",
            size_bytes=len(content),
            modified_at=modified_at(path),
            text=text,
            metadata=self._safe_metadata(tika_metadata),
            warnings=[] if text else ["document contains no extractable text"],
        )

    @staticmethod
    def _normalize_text(value: object) -> str:
        if not isinstance(value, str):
            return ""
        normalized = value.replace("\r\n", "\n").replace("\r", "\n")
        normalized = "\n".join(line.strip() for line in normalized.split("\n"))
        return re.sub(r"\n{3,}", "\n\n", normalized).strip()

    @classmethod
    def _safe_metadata(cls, metadata: dict[str, Any]) -> dict[str, object]:
        safe: dict[str, object] = {}
        for result_name, source_names in cls._METADATA_FIELDS.items():
            for source_name in source_names:
                value = metadata.get(source_name)
                if isinstance(value, str):
                    value = value.strip()
                if value not in (None, "", []):
                    safe[result_name] = value
                    break
        return safe
