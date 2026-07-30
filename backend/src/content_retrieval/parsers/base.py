from pathlib import Path
from typing import Protocol, runtime_checkable

from content_retrieval.domain.models import ParseResult


@runtime_checkable
class Parser(Protocol):
    supported_extensions: frozenset[str]
    supported_mime_types: frozenset[str]

    def parse(self, path: Path) -> ParseResult:
        """Parse one local file into the unified result contract."""
        ...
