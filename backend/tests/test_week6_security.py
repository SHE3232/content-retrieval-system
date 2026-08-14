from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess

import pytest

from content_retrieval.domain.models import ParseResult
from content_retrieval.parsers.registry import ParserRegistry
from content_retrieval.services.batch_ingestion import BatchIngestionService


class _TextParser:
    supported_extensions = frozenset({".txt"})
    supported_mime_types = frozenset({"text/plain"})

    def parse(self, path: Path) -> ParseResult:
        content = path.read_bytes()
        return ParseResult(
            file_id=hashlib.sha256(content).hexdigest(),
            path=path,
            name=path.name,
            mime_type="text/plain",
            modality="text",
            size_bytes=len(content),
            modified_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
            text=content.decode("utf-8"),
        )


def _service() -> BatchIngestionService:
    return BatchIngestionService(ParserRegistry([_TextParser()]), max_file_size_bytes=1024)


def test_authorized_root_rejects_direct_outside_file(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("private", encoding="utf-8")
    result = _service().parse_paths([outside], authorized_roots=[allowed])
    assert result.failed == 1
    assert result.errors[0].code == "PATH_NOT_AUTHORIZED"


def test_dot_dot_and_separator_variants_cannot_escape_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("private", encoding="utf-8")
    escaped = allowed / "nested" / ".." / ".." / "secret.txt"
    result = _service().parse_paths([escaped], authorized_roots=[str(allowed) + os.sep])
    assert result.failed == 1
    assert result.errors[0].code == "PATH_NOT_AUTHORIZED"


def test_deleted_and_unsupported_files_are_not_read(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    deleted = allowed / "deleted.txt"
    result = _service().parse_paths([deleted], authorized_roots=[allowed])
    assert result.failed == 1
    assert result.errors[0].code == "PATH_NOT_FOUND"
    malicious = allowed / "payload.exe"
    malicious.write_bytes(b"not executable content")
    result = _service().parse_paths([malicious], authorized_roots=[allowed])
    assert result.succeeded == 0
    assert result.failed == 1


def test_symlink_or_junction_escape_is_rejected(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("private", encoding="utf-8")
    link = allowed / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if os.name != "nt":
            pytest.skip(f"symbolic links are unavailable: {error}")
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True,
            text=True,
            check=False,
        )
        if created.returncode != 0:
            pytest.fail(f"cannot create a Windows junction fixture: {created.stderr}")
    result = _service().parse_paths([link / "secret.txt"], authorized_roots=[allowed])
    assert result.failed == 1
    assert result.errors[0].code == "PATH_NOT_AUTHORIZED"
