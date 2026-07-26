from __future__ import annotations

import hashlib
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))

from prepare_coco_retrieval import prepare_subset


def test_prepare_subset_is_deterministic_and_preserves_licenses(
    tmp_path: Path,
) -> None:
    captions = {
        "annotations": [
            {"image_id": 20, "caption": "a blue square"},
            {"image_id": 10, "caption": "a red circle"},
            {"image_id": 20, "caption": "blue shape"},
        ]
    }
    instances = {
        "licenses": [
            {
                "id": 4,
                "name": "Attribution License",
                "url": "https://example.test/license",
            }
        ],
        "images": [
            {
                "id": 20,
                "file_name": "000000000020.jpg",
                "license": 4,
                "coco_url": "https://example.test/20.jpg",
                "flickr_url": "https://flickr.test/20",
            },
            {
                "id": 10,
                "file_name": "000000000010.jpg",
                "license": 4,
                "coco_url": "https://example.test/10.jpg",
                "flickr_url": "https://flickr.test/10",
            },
        ],
    }
    payloads = {
        "https://example.test/10.jpg": b"image-ten",
        "https://example.test/20.jpg": b"image-twenty",
    }

    rows = prepare_subset(
        captions,
        instances,
        image_dir=tmp_path / "images",
        size=2,
        validation_size=1,
        downloader=lambda url: payloads[url],
    )

    expected_ids = sorted(
        [10, 20],
        key=lambda image_id: hashlib.sha256(
            f"coco-2017-val\0{image_id}".encode()
        ).hexdigest(),
    )
    assert [row["image_id"] for row in rows] == expected_ids
    assert [row["split"] for row in rows] == ["validation", "benchmark"]
    assert rows[0]["license_url"] == "https://example.test/license"
    assert rows[0]["license_name"] == "Attribution License"
    assert len(rows[0]["sha256"]) == 64
    assert len(rows[0]["captions"]) >= 1
    assert (tmp_path / "images" / rows[0]["file_name"]).is_file()


def test_prepare_subset_reuses_valid_existing_images(tmp_path: Path) -> None:
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    existing = image_dir / "one.jpg"
    existing.write_bytes(b"existing")
    captions = {"annotations": [{"image_id": 1, "caption": "one"}]}
    instances = {
        "licenses": [{"id": 1, "name": "L", "url": "https://license"}],
        "images": [
            {
                "id": 1,
                "file_name": "one.jpg",
                "license": 1,
                "coco_url": "https://example.test/one.jpg",
            }
        ],
    }

    rows = prepare_subset(
        captions,
        instances,
        image_dir=image_dir,
        size=1,
        validation_size=0,
        downloader=lambda _: (_ for _ in ()).throw(AssertionError()),
    )

    assert rows[0]["sha256"] == hashlib.sha256(b"existing").hexdigest()
