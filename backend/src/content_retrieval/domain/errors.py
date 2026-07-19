from pathlib import Path


class ParseError(Exception):
    """Base class for controlled file parsing failures."""

    code = "PARSE_ERROR"
    retryable = False

    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        super().__init__(message)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": str(self),
            "retryable": self.retryable,
        }


class PathNotFoundError(ParseError):
    code = "PATH_NOT_FOUND"

    def __init__(self, path: Path) -> None:
        super().__init__(path, f"Path does not exist: {path}")


class PathNotAuthorizedError(ParseError):
    code = "PATH_NOT_AUTHORIZED"

    def __init__(self, path: Path) -> None:
        super().__init__(path, f"Path is outside the authorized roots: {path}")


class UnsupportedFormatError(ParseError):
    code = "UNSUPPORTED_FORMAT"

    def __init__(self, path: Path, mime_type: str | None = None) -> None:
        self.mime_type = mime_type
        detail = f" ({mime_type})" if mime_type else ""
        super().__init__(path, f"Unsupported format for {path.name}{detail}")


class CorruptedFileError(ParseError):
    code = "CORRUPTED_FILE"

    def __init__(self, path: Path, reason: str) -> None:
        self.reason = reason
        super().__init__(path, f"Corrupted file {path.name}: {reason}")


class TextDecodeError(ParseError):
    """A text file cannot be decoded with the deterministic encoding policy."""

    code = "TEXT_DECODE_ERROR"

    def __init__(self, path: Path, encoding: str = "utf-8") -> None:
        self.encoding = encoding
        super().__init__(path, f"Cannot decode {path.name} as {encoding}")


class ImageDecodeError(ParseError):
    """An image cannot be decoded as a supported image format."""

    code = "IMAGE_DECODE_ERROR"

    def __init__(self, path: Path) -> None:
        super().__init__(path, f"Cannot decode image {path.name}")


class EncryptedPdfError(ParseError):
    """A PDF requires a password and therefore cannot be parsed locally."""

    code = "PDF_ENCRYPTED"

    def __init__(self, path: Path) -> None:
        super().__init__(path, f"Encrypted PDF is not supported: {path.name}")


class TikaUnavailableError(ParseError):
    """Apache Tika cannot currently accept parsing requests."""

    code = "TIKA_UNAVAILABLE"
    retryable = True

    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            f"Apache Tika is unavailable while parsing {path.name}",
        )


class ParseTimeoutError(ParseError):
    """A parser did not finish within its configured time limit."""

    code = "PARSE_TIMEOUT"
    retryable = True

    def __init__(self, path: Path) -> None:
        super().__init__(path, f"Parsing timed out for {path.name}")


class FileTooLargeError(ParseError):
    """A file exceeds the configured per-file parsing limit."""

    code = "FILE_TOO_LARGE"
    retryable = True

    def __init__(
        self, path: Path, actual_size_bytes: int, max_size_bytes: int
    ) -> None:
        self.actual_size_bytes = actual_size_bytes
        self.max_size_bytes = max_size_bytes
        super().__init__(
            path,
            f"File {path.name} is {actual_size_bytes} bytes; "
            f"limit is {max_size_bytes} bytes",
        )


class InternalParseError(ParseError):
    """A safe boundary for unexpected per-file parser failures."""

    code = "INTERNAL_ERROR"

    def __init__(self, path: Path) -> None:
        super().__init__(path, f"Unexpected error while parsing {path.name}")
