from dataclasses import dataclass
from pathlib import Path

from content_retrieval.domain.errors import (
    FileTooLargeError,
    InternalParseError,
    ParseError,
    PathNotAuthorizedError,
    PathNotFoundError,
)
from content_retrieval.domain.models import (
    BatchItem,
    BatchResult,
    SkippedFile,
)
from content_retrieval.parsers._file_info import sha256_file
from content_retrieval.parsers.registry import ParserRegistry


@dataclass(frozen=True, slots=True)
class _Candidate:
    path: Path
    explicit: bool
    error: ParseError | None = None


class BatchIngestionService:
    """Scan and parse one local directory without persisting parsed data."""

    def __init__(
        self,
        registry: ParserRegistry,
        *,
        max_file_size_bytes: int,
    ) -> None:
        if max_file_size_bytes <= 0:
            raise ValueError("max_file_size_bytes must be positive")

        self._registry = registry
        self._max_file_size_bytes = max_file_size_bytes
        self._allowed_extensions = registry.supported_extensions

    def scan_directory(
        self, directory: Path | str, *, recursive: bool = True
    ) -> list[Path]:
        root = Path(directory).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError(root)

        candidates = root.rglob("*") if recursive else root.iterdir()
        files = [
            path.resolve()
            for path in candidates
            if path.is_file() and path.suffix.lower() in self._allowed_extensions
        ]
        return sorted(files, key=lambda path: self._sort_key(root, path))

    def parse_directory(
        self, directory: Path | str, *, recursive: bool = True
    ) -> BatchResult:
        return self.parse_paths([directory], recursive=recursive)

    def parse_paths(
        self,
        paths: list[Path | str],
        *,
        recursive: bool = True,
        authorized_roots: list[Path | str] | None = None,
    ) -> BatchResult:
        roots = self._resolve_authorized_roots(authorized_roots)
        candidates = self._expand_paths(
            paths,
            recursive=recursive,
            authorized_roots=roots,
        )
        return self._parse_candidates(candidates)

    @staticmethod
    def _resolve_authorized_roots(
        roots: list[Path | str] | None,
    ) -> tuple[Path, ...] | None:
        if roots is None:
            return None
        return tuple(Path(root).expanduser().resolve(strict=True) for root in roots)

    def _expand_paths(
        self,
        paths: list[Path | str],
        *,
        recursive: bool,
        authorized_roots: tuple[Path, ...] | None,
    ) -> list[_Candidate]:
        candidates: list[_Candidate] = []
        seen_paths: set[Path] = set()

        for source in paths:
            source_path = Path(source).expanduser()
            try:
                resolved = source_path.resolve(strict=True)
            except FileNotFoundError:
                missing = source_path.absolute()
                expanded = [
                    _Candidate(
                        missing,
                        explicit=True,
                        error=PathNotFoundError(missing),
                    )
                ]
            else:
                if not self._is_authorized(resolved, authorized_roots):
                    expanded = [
                        _Candidate(
                            resolved,
                            explicit=True,
                            error=PathNotAuthorizedError(resolved),
                        )
                    ]
                elif resolved.is_file():
                    expanded = [_Candidate(resolved, explicit=True)]
                else:
                    children = (
                        resolved.rglob("*") if recursive else resolved.iterdir()
                    )
                    child_paths = sorted(
                        (path for path in children if path.is_file()),
                        key=lambda path: self._sort_key(resolved, path),
                    )
                    expanded = []
                    for path in child_paths:
                        try:
                            child = path.resolve(strict=True)
                        except FileNotFoundError:
                            missing = path.absolute()
                            expanded.append(
                                _Candidate(
                                    missing,
                                    explicit=False,
                                    error=PathNotFoundError(missing),
                                )
                            )
                            continue

                        error = None
                        if not self._is_authorized(child, authorized_roots):
                            error = PathNotAuthorizedError(child)
                        expanded.append(
                            _Candidate(child, explicit=False, error=error)
                        )

            for candidate in expanded:
                if candidate.path not in seen_paths:
                    seen_paths.add(candidate.path)
                    candidates.append(candidate)

        return candidates

    @staticmethod
    def _is_authorized(
        path: Path,
        authorized_roots: tuple[Path, ...] | None,
    ) -> bool:
        if authorized_roots is None:
            return True
        return any(path.is_relative_to(root) for root in authorized_roots)

    def _parse_candidates(self, candidates: list[_Candidate]) -> BatchResult:
        batch = BatchResult()
        seen_content: dict[str, Path] = {}

        for candidate in candidates:
            path = candidate.path
            if candidate.error is not None:
                batch.errors.append(candidate.error)
                batch.items.append(
                    BatchItem(path=path, status="failed", error=candidate.error)
                )
                continue

            if not candidate.explicit and path.suffix.lower() not in self._allowed_extensions:
                skip = SkippedFile(path=path, reason="unsupported_format")
                batch.skips.append(skip)
                batch.items.append(
                    BatchItem(path=path, status="skipped", skip=skip)
                )
                continue

            try:
                size_bytes = path.stat().st_size
                if size_bytes > self._max_file_size_bytes:
                    raise FileTooLargeError(
                        path, size_bytes, self._max_file_size_bytes
                    )

                file_id = sha256_file(path)
                duplicate_of = seen_content.get(file_id)
                if duplicate_of is not None:
                    skip = SkippedFile(
                        path=path,
                        reason="duplicate_content",
                        file_id=file_id,
                        duplicate_of=duplicate_of,
                    )
                    batch.skips.append(skip)
                    batch.items.append(
                        BatchItem(path=path, status="skipped", skip=skip)
                    )
                    continue

                seen_content[file_id] = path
                parser = self._registry.resolve(path)
                result = parser.parse(path)
            except ParseError as error:
                batch.errors.append(error)
                batch.items.append(
                    BatchItem(path=path, status="failed", error=error)
                )
            except Exception:
                error = InternalParseError(path)
                batch.errors.append(error)
                batch.items.append(
                    BatchItem(path=path, status="failed", error=error)
                )
            else:
                batch.results.append(result)
                batch.items.append(
                    BatchItem(path=path, status="succeeded", result=result)
                )

        return batch

    @staticmethod
    def _sort_key(root: Path, path: Path) -> tuple[str, str]:
        relative_path = path.relative_to(root).as_posix()
        return relative_path.casefold(), relative_path
