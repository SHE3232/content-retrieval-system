from pathlib import Path

import pypdfium2 as pdfium

from content_retrieval.domain.errors import CorruptedFileError, EncryptedPdfError
from content_retrieval.domain.models import ParseResult

from ._file_info import modified_at, sha256_bytes


class PdfParser:
    supported_extensions = frozenset({".pdf"})
    supported_mime_types = frozenset({"application/pdf"})

    def parse(self, path: Path) -> ParseResult:
        content = path.read_bytes()
        document = self._open(path)
        try:
            page_texts, warnings = self._extract_pages(path, document)
            metadata = self._metadata(document)
        finally:
            document.close()

        metadata["page_texts"] = page_texts
        metadata["encrypted"] = False
        return ParseResult(
            file_id=sha256_bytes(content),
            path=path.resolve(),
            name=path.name,
            mime_type="application/pdf",
            modality="document",
            size_bytes=len(content),
            modified_at=modified_at(path),
            text="\n\n".join(page_texts),
            page_count=len(page_texts),
            metadata=metadata,
            warnings=warnings,
        )

    @staticmethod
    def _open(path: Path) -> pdfium.PdfDocument:
        try:
            return pdfium.PdfDocument(path)
        except pdfium.PdfiumError as error:
            if "password" in str(error).lower():
                raise EncryptedPdfError(path) from error
            raise CorruptedFileError(path, "invalid PDF structure") from error

    @staticmethod
    def _extract_pages(
        path: Path, document: pdfium.PdfDocument
    ) -> tuple[list[str], list[str]]:
        page_texts: list[str] = []
        warnings: list[str] = []
        try:
            for index in range(len(document)):
                page = document[index]
                try:
                    text_page = page.get_textpage()
                    try:
                        text = text_page.get_text_bounded(errors="replace")
                    finally:
                        text_page.close()
                finally:
                    page.close()

                normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
                page_texts.append(normalized)
                if not normalized:
                    warnings.append(
                        f"page {index + 1} contains no extractable text"
                    )
        except pdfium.PdfiumError as error:
            raise CorruptedFileError(path, "page text extraction failed") from error
        return page_texts, warnings

    @staticmethod
    def _metadata(document: pdfium.PdfDocument) -> dict[str, object]:
        try:
            raw_metadata = document.get_metadata_dict()
            version = document.get_version()
        except pdfium.PdfiumError:
            return {}

        metadata: dict[str, object] = {
            key.lower(): value for key, value in raw_metadata.items() if value
        }
        if version:
            metadata["pdf_version"] = f"1.{version % 10}"
        return metadata
