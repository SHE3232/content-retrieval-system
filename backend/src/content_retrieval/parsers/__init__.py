"""Parser interfaces and format routing."""

from .base import Parser
from .docx import DocxParser
from .image import ImageParser
from .pdf import PdfParser
from .registry import ParserRegistry, create_default_registry
from .tika import TikaClient
from .txt import TextParser, TxtParser


__all__ = [
    "Parser",
    "ParserRegistry",
    "DocxParser",
    "ImageParser",
    "PdfParser",
    "TikaClient",
    "TextParser",
    "TxtParser",
    "create_default_registry",
]
