#!/usr/bin/env python3
"""Validate the real Week 8 demonstration video with ffprobe."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any


def _duration(value: object, label: str) -> float:
    try:
        duration = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} duration is missing or invalid") from error
    if duration <= 0:
        raise ValueError(f"{label} duration must be positive")
    return duration


def _frame_rate(value: object) -> Fraction:
    try:
        rate = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError("video frame rate is invalid") from error
    if rate != Fraction(30, 1):
        raise ValueError("video must use exact 30 fps")
    return rate


def validate_probe_data(
    probe: dict[str, Any], *, source_commit: str
) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source_commit must be a full lowercase Git commit")
    streams = probe.get("streams")
    if not isinstance(streams, list):
        raise TypeError("ffprobe streams are missing")
    videos = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"]
    if not videos:
        raise ValueError("video stream is missing")
    if not audios:
        raise ValueError("audio stream is missing")
    video = videos[0]
    audio = audios[0]
    format_data = probe.get("format")
    if not isinstance(format_data, dict) or "mp4" not in str(format_data.get("format_name", "")):
        raise ValueError("container must be MP4")
    duration = _duration(format_data.get("duration"), "format")
    if not 299.5 <= duration <= 300.5:
        raise ValueError("video duration must be from 299.5 through 300.5 seconds")
    if video.get("codec_name") != "h264":
        raise ValueError("video codec must be H.264")
    if (video.get("width"), video.get("height")) != (1920, 1080):
        raise ValueError("video resolution must be 1920x1080")
    _frame_rate(video.get("avg_frame_rate"))
    tags = video.get("tags", {})
    if isinstance(tags, dict) and str(tags.get("rotate", "0")) not in {"", "0"}:
        raise ValueError("video rotation metadata is not permitted")
    side_data = video.get("side_data_list", [])
    if isinstance(side_data, list) and any(
        isinstance(item, dict) and float(item.get("rotation", 0) or 0) != 0
        for item in side_data
    ):
        raise ValueError("video rotation metadata is not permitted")
    if audio.get("codec_name") != "aac":
        raise ValueError("audio codec must be AAC")
    audio_duration = _duration(audio.get("duration"), "audio")
    try:
        channels = int(audio.get("channels", 0))
        bitrate = int(audio.get("bit_rate", 0))
        sample_rate = int(audio.get("sample_rate", 0))
    except (TypeError, ValueError) as error:
        raise ValueError("audio metadata is invalid") from error
    if channels <= 0 or bitrate <= 0 or sample_rate <= 0 or audio_duration <= 0:
        raise ValueError("video requires non-zero audio")
    return {
        "schema_version": 1,
        "status": "PASS",
        "source_commit": source_commit,
        "duration_seconds": duration,
        "video": {
            "codec": "h264",
            "width": 1920,
            "height": 1080,
            "frame_rate": "30/1",
        },
        "audio": {
            "codec": "aac",
            "duration_seconds": audio_duration,
            "sample_rate": sample_rate,
            "channels": channels,
            "bit_rate": bitrate,
        },
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_video(
    video_path: Path,
    *,
    source_commit: str,
    ffprobe: str = "ffprobe",
) -> dict[str, object]:
    video_path = video_path.resolve()
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        raise ValueError(f"video file is missing or empty: {video_path}")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"ffprobe failed: {completed.stderr.strip()}")
    probe = json.loads(completed.stdout)
    if not isinstance(probe, dict):
        raise TypeError("ffprobe output must be a JSON object")
    result = validate_probe_data(probe, source_commit=source_commit)
    result["path"] = str(video_path)
    result["bytes"] = video_path.stat().st_size
    result["sha256"] = _sha256(video_path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = validate_video(
        args.video, source_commit=args.source_commit, ffprobe=args.ffprobe
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
