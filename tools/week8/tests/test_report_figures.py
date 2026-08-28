from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from tools.week8.build_report_figures import FIGURE_NAMES, build_figures


def _evidence(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_commit": "d" * 40,
                "tests": {
                    "backend": {"status": "PASS", "passed": 445, "skipped": 1},
                    "flutter": {"status": "PASS", "passed": 249, "skipped": 0},
                },
                "platforms": {
                    "windows": {"status": "PASS"},
                    "linux": {"status": "PASS"},
                    "macos": {"status": "BLOCKED"},
                },
                "benchmarks": {
                    "search_p95_ms": 239.292845017917,
                    "target_p95_ms": 2000.0,
                    "text_batch1_p50_ms": 21.179750037845224,
                    "text_batch16_throughput": 346.5024477276606,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_build_figures_creates_eight_monochrome_high_resolution_pngs(
    tmp_path: Path,
) -> None:
    output = tmp_path / "assets"

    files = build_figures(_evidence(tmp_path / "evidence.json"), output)

    assert [path.name for path in files] == list(FIGURE_NAMES)
    for path in files:
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.mode == "RGB"
            assert image.width >= 1600
            assert image.height >= 900
            assert image.getpixel((0, 0)) == (255, 255, 255)
            colors = image.getcolors(maxcolors=image.width * image.height)
            assert colors is not None
            assert any(max(rgb) < 80 for _, rgb in colors)

    metadata = json.loads((output / "figures.json").read_text(encoding="utf-8"))
    assert metadata["source_commit"] == "d" * 40
    assert len(metadata["figures"]) == 8
