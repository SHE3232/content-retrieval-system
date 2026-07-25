import hashlib
import json
import re
from collections.abc import Iterable

from content_retrieval.domain.errors import ChunkingError
from content_retrieval.domain.models import (
    BatchProcessingResult,
    ParseResult,
    TextChunk,
)


class TextChunker:
    """Create deterministic, source-located character-window text chunks."""

    def __init__(
        self,
        *,
        max_characters: int = 1000,
        overlap_characters: int = 100,
    ) -> None:
        if max_characters <= 0:
            raise ValueError("max_characters must be positive")
        if overlap_characters < 0:
            raise ValueError("overlap_characters must be non-negative")
        if overlap_characters >= max_characters:
            raise ValueError("overlap_characters must be less than max_characters")
        self.max_characters = max_characters
        self.overlap_characters = overlap_characters

    def chunk(self, document: ParseResult) -> list[TextChunk]:
        units = self._source_units(document)
        chunks: list[TextChunk] = []

        for locator_name, locator_number, source_text in units:
            for split_number, text in enumerate(self._split_text(source_text)):
                sequence_number = len(chunks)
                page_number = (
                    locator_number if locator_name == "page_number" else None
                )
                paragraph_number = (
                    locator_number
                    if locator_name == "paragraph_number"
                    else None
                )
                chunk_id = self._chunk_id(
                    file_id=document.file_id,
                    text=text,
                    sequence_number=sequence_number,
                    page_number=page_number,
                    paragraph_number=paragraph_number,
                    split_number=split_number,
                )
                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        file_id=document.file_id,
                        text=text,
                        sequence_number=sequence_number,
                        page_number=page_number,
                        paragraph_number=paragraph_number,
                        split_number=split_number,
                        metadata={
                            "source_name": document.name,
                            "mime_type": document.mime_type,
                        },
                    )
                )

        if not chunks:
            raise ChunkingError(
                "document contains no extractable text",
                file_id=document.file_id,
            )
        return chunks

    def chunk_many(
        self,
        documents: Iterable[ParseResult],
    ) -> BatchProcessingResult:
        batch = BatchProcessingResult()
        for document in documents:
            try:
                batch.items.extend(self.chunk(document))
            except ChunkingError as error:
                batch.errors.append(error)
        return batch

    @staticmethod
    def _source_units(
        document: ParseResult,
    ) -> list[tuple[str, int, str]]:
        if document.mime_type == "application/pdf":
            page_texts = document.metadata.get("page_texts")
            if not isinstance(page_texts, list) or not all(
                isinstance(text, str) for text in page_texts
            ):
                raise ChunkingError(
                    "PDF metadata.page_texts is required to preserve page numbers",
                    file_id=document.file_id,
                )
            return [
                ("page_number", page_number, text.strip())
                for page_number, text in enumerate(page_texts, start=1)
                if text.strip()
            ]

        if not isinstance(document.text, str):
            raise ChunkingError(
                "document contains no extractable text",
                file_id=document.file_id,
            )
        normalized = document.text.replace("\r\n", "\n").replace("\r", "\n")
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n[ \t]*\n+", normalized)
            if paragraph.strip()
        ]
        return [
            ("paragraph_number", paragraph_number, paragraph)
            for paragraph_number, paragraph in enumerate(paragraphs, start=1)
        ]

    def _split_text(self, text: str) -> list[str]:
        if not text.strip():
            return []
        if len(text) <= self.max_characters:
            return [text.strip()]

        step = self.max_characters - self.overlap_characters
        pieces: list[str] = []
        for start in range(0, len(text), step):
            piece = text[start : start + self.max_characters].strip()
            if piece:
                pieces.append(piece)
            if start + self.max_characters >= len(text):
                break
        return pieces

    @staticmethod
    def _chunk_id(
        *,
        file_id: str,
        text: str,
        sequence_number: int,
        page_number: int | None,
        paragraph_number: int | None,
        split_number: int,
    ) -> str:
        identity = {
            "schema_version": "1",
            "file_id": file_id,
            "text": text,
            "sequence_number": sequence_number,
            "page_number": page_number,
            "paragraph_number": paragraph_number,
            "split_number": split_number,
        }
        canonical = json.dumps(
            identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
