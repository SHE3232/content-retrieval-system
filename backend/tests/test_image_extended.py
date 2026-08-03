import hashlib
from pathlib import Path

from PIL import Image
import pytest

from content_retrieval.domain.errors import ImageDecodeError
from content_retrieval.parsers.image import ImageParser


class FakeExifImage:
    def __init__(self, exif: dict[int, object]) -> None:
        self.exif = exif

    def getexif(self) -> dict[int, object]:
        return self.exif


def test_tc_145_extracts_rgb_jpeg_metadata(tmp_path: Path) -> None:
    source = tmp_path / "rgb.jpg"
    Image.new("RGB", (11, 7), "red").save(source, format="JPEG")

    result = ImageParser().parse(source)

    assert (result.width, result.height) == (11, 7)
    assert result.metadata["format"] == "JPEG"
    assert result.metadata["color_mode"] == "RGB"


def test_tc_146_preserves_grayscale_jpeg_mode(tmp_path: Path) -> None:
    source = tmp_path / "gray.jpg"
    Image.new("L", (9, 5), 128).save(source, format="JPEG")

    assert ImageParser().parse(source).metadata["color_mode"] == "L"


def test_tc_147_extracts_rgba_png_metadata(tmp_path: Path) -> None:
    source = tmp_path / "rgba.png"
    Image.new("RGBA", (8, 6), (1, 2, 3, 4)).save(source, format="PNG")

    result = ImageParser().parse(source)

    assert result.mime_type == "image/png"
    assert result.metadata["format"] == "PNG"
    assert result.metadata["color_mode"] == "RGBA"


def test_tc_148_trims_exif_descriptions() -> None:
    assert ImageParser._safe_exif(FakeExifImage({270: "  description  "})) == {
        "image_description": "description"
    }


def test_tc_149_accepts_exif_orientation_one() -> None:
    assert ImageParser._safe_exif(FakeExifImage({274: 1})) == {"orientation": 1}


def test_tc_150_accepts_exif_orientation_eight() -> None:
    assert ImageParser._safe_exif(FakeExifImage({274: 8})) == {"orientation": 8}


def test_tc_151_rejects_exif_orientation_zero() -> None:
    assert ImageParser._safe_exif(FakeExifImage({274: 0})) == {}


def test_tc_152_rejects_exif_orientation_nine() -> None:
    assert ImageParser._safe_exif(FakeExifImage({274: 9})) == {}


def test_tc_153_rejects_boolean_exif_orientation() -> None:
    assert ImageParser._safe_exif(FakeExifImage({274: True})) == {}


def test_tc_154_excludes_unknown_exif_fields() -> None:
    assert ImageParser._safe_exif(FakeExifImage({271: "Camera", 272: "Model"})) == {}


def test_tc_155_returns_empty_exif_for_images_without_exif() -> None:
    assert ImageParser._safe_exif(FakeExifImage({})) == {}


def test_tc_156_rejects_a_truncated_png(tmp_path: Path) -> None:
    source = tmp_path / "truncated.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")

    with pytest.raises(ImageDecodeError):
        ImageParser().parse(source)


def test_tc_157_rejects_a_gif_disguised_as_png(tmp_path: Path) -> None:
    source = tmp_path / "disguised.png"
    Image.new("RGB", (4, 4), "blue").save(source, format="GIF")

    with pytest.raises(ImageDecodeError):
        ImageParser().parse(source)


def test_tc_158_rejects_decompression_bomb_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "large-pixels.png"
    Image.new("RGB", (20, 20), "white").save(source, format="PNG")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 250)

    with pytest.raises(ImageDecodeError):
        ImageParser().parse(source)


def test_tc_159_loads_every_frame_of_a_valid_apng(tmp_path: Path) -> None:
    source = tmp_path / "animated.png"
    first = Image.new("RGBA", (8, 8), "red")
    second = Image.new("RGBA", (8, 8), "blue")
    first.save(
        source,
        format="PNG",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )

    result = ImageParser().parse(source)

    assert (result.width, result.height) == (8, 8)
    assert result.metadata["format"] == "PNG"


def test_tc_160_reports_image_file_information(tmp_path: Path) -> None:
    source = tmp_path / "info.png"
    Image.new("RGB", (3, 2), "green").save(source, format="PNG")
    content = source.read_bytes()

    result = ImageParser().parse(source)

    assert result.path == source.resolve()
    assert result.name == source.name
    assert result.size_bytes == len(content)
    assert result.file_id == hashlib.sha256(content).hexdigest()
    assert result.modified_at.tzinfo is not None
