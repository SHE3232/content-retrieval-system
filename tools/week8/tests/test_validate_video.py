from __future__ import annotations

import copy

import pytest

from tools.week8.validate_video import validate_probe_data

COMMIT = "1" * 40


def _probe() -> dict[str, object]:
    return {
        "format": {"duration": "300.000000", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30/1",
                "r_frame_rate": "30/1",
                "duration": "300.000000",
                "tags": {},
                "side_data_list": [],
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "duration": "300.000000",
                "sample_rate": "48000",
                "channels": 2,
                "bit_rate": "192000",
            },
        ],
    }


def test_exact_five_minute_probe_passes() -> None:
    result = validate_probe_data(_probe(), source_commit=COMMIT)

    assert result["status"] == "PASS"
    assert result["duration_seconds"] == 300.0
    assert result["source_commit"] == COMMIT


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("format", "duration", "299.49"), "duration"),
        (("streams", 0, "codec_name", "hevc"), "H.264"),
        (("streams", 0, "width", 1280), "1920x1080"),
        (("streams", 0, "avg_frame_rate", "30000/1001"), "30 fps"),
        (("streams", 1, "codec_name", "mp3"), "AAC"),
        (("streams", 1, "bit_rate", "0"), "non-zero audio"),
    ],
)
def test_invalid_video_metadata_is_rejected(
    mutation: tuple[object, ...], message: str
) -> None:
    probe = copy.deepcopy(_probe())
    target: object = probe
    for key in mutation[:-2]:
        target = target[key]  # type: ignore[index]
    target[mutation[-2]] = mutation[-1]  # type: ignore[index]

    with pytest.raises(ValueError, match=message):
        validate_probe_data(probe, source_commit=COMMIT)


def test_rotation_metadata_is_rejected() -> None:
    probe = _probe()
    probe["streams"][0]["tags"] = {"rotate": "90"}  # type: ignore[index]

    with pytest.raises(ValueError, match="rotation"):
        validate_probe_data(probe, source_commit=COMMIT)
