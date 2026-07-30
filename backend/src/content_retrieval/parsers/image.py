from io import BytesIO
from pathlib import Path
import warnings

from PIL import Image, UnidentifiedImageError

from content_retrieval.domain.errors import ImageDecodeError
from content_retrieval.domain.models import ParseResult

from ._file_info import modified_at, sha256_bytes


class ImageParser:
    supported_extensions = frozenset({".jpg", ".jpeg", ".png"})
    supported_mime_types = frozenset({"image/jpeg", "image/png"})

    _FORMATS = ("JPEG", "PNG")
    _MIME_TYPES = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
    }
    _EXIF_FIELDS = {
        270: "image_description",
        274: "orientation",
    }

    def parse(self, path: Path) -> ParseResult:
        content = path.read_bytes()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content), formats=self._FORMATS) as image:
                    image.verify()

                with Image.open(BytesIO(content), formats=self._FORMATS) as image:
                    image.load()
                    image_format = image.format
                    mime_type = self._MIME_TYPES.get(image_format or "")
                    if mime_type is None:
                        raise ImageDecodeError(path)

                    width, height = image.size
                    color_mode = image.mode
                    exif = self._safe_exif(image)
                    for frame_index in range(1, getattr(image, "n_frames", 1)):
                        image.seek(frame_index)
                        image.load()
        except ImageDecodeError:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            EOFError,
            OSError,
            SyntaxError,
            ValueError,
        ) as error:
            raise ImageDecodeError(path) from error

        return ParseResult(
            file_id=sha256_bytes(content),
            path=path.resolve(),
            name=path.name,
            mime_type=mime_type,
            modality="image",
            size_bytes=len(content),
            modified_at=modified_at(path),
            text=None,
            width=width,
            height=height,
            metadata={
                "format": image_format,
                "color_mode": color_mode,
                "exif": exif,
            },
            warnings=[],
        )

    @classmethod
    def _safe_exif(cls, image: Image.Image) -> dict[str, object]:
        source = image.getexif()
        safe: dict[str, object] = {}

        description = source.get(270)
        if isinstance(description, str) and description.strip():
            safe[cls._EXIF_FIELDS[270]] = description.strip()

        orientation = source.get(274)
        if (
            isinstance(orientation, int)
            and not isinstance(orientation, bool)
            and 1 <= orientation <= 8
        ):
            safe[cls._EXIF_FIELDS[274]] = orientation

        return safe
