from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CAPTIONS_URL = (
    "http://images.cocodataset.org/annotations/annotations_trainval2017.zip"
)
IMAGES_BASE_URL = "http://images.cocodataset.org/val2017"


def _download(url: str) -> bytes:
    request = Request(
        url,
        headers={"User-Agent": "content-retrieval-week3/1.0"},
    )
    last_error: OSError | None = None
    for _ in range(3):
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except OSError as error:
            last_error = error
    assert last_error is not None
    raise last_error


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_key(image_id: int) -> str:
    return hashlib.sha256(
        f"coco-2017-val\0{image_id}".encode("utf-8")
    ).hexdigest()


def prepare_subset(
    captions: dict[str, Any],
    instances: dict[str, Any],
    *,
    image_dir: Path,
    size: int,
    validation_size: int,
    downloader: Callable[[str], bytes] = _download,
    max_workers: int = 8,
) -> list[dict[str, Any]]:
    """Select and materialize a deterministic, license-preserving COCO subset."""
    if size <= 0:
        raise ValueError("size must be positive")
    if not 0 <= validation_size <= size:
        raise ValueError("validation_size must be between zero and size")
    if max_workers <= 0:
        raise ValueError("max_workers must be positive")

    license_rows = instances.get("licenses")
    image_rows = instances.get("images")
    caption_rows = captions.get("annotations")
    if not isinstance(license_rows, list) or not isinstance(image_rows, list):
        raise ValueError("instances must contain licenses and images lists")
    if not isinstance(caption_rows, list):
        raise ValueError("captions must contain an annotations list")

    licenses: dict[int, dict[str, Any]] = {}
    for license_row in license_rows:
        if not isinstance(license_row, dict):
            continue
        license_id = license_row.get("id")
        if isinstance(license_id, int):
            licenses[license_id] = license_row

    captions_by_image: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for index, caption_row in enumerate(caption_rows):
        if not isinstance(caption_row, dict):
            continue
        image_id = caption_row.get("image_id")
        caption = caption_row.get("caption")
        annotation_id = caption_row.get("id", index)
        if (
            isinstance(image_id, int)
            and isinstance(caption, str)
            and caption.strip()
        ):
            sort_id = annotation_id if isinstance(annotation_id, int) else index
            captions_by_image[image_id].append((sort_id, caption.strip()))

    eligible: list[dict[str, Any]] = []
    for image_row in image_rows:
        if not isinstance(image_row, dict):
            continue
        image_id = image_row.get("id")
        license_id = image_row.get("license")
        file_name = image_row.get("file_name")
        if (
            isinstance(image_id, int)
            and image_id in captions_by_image
            and isinstance(license_id, int)
            and license_id in licenses
            and isinstance(file_name, str)
            and Path(file_name).name == file_name
        ):
            eligible.append(image_row)
    eligible.sort(key=lambda image: _stable_key(int(image["id"])))
    if len(eligible) < size:
        raise ValueError(
            f"only {len(eligible)} eligible images are available; need {size}"
        )

    destination = image_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    def materialize(
        image: dict[str, Any],
    ) -> tuple[dict[str, Any], bytes, str]:
        image_id = int(image["id"])
        file_name = str(image["file_name"])
        image_url = image.get("coco_url")
        if not isinstance(image_url, str) or not image_url:
            image_url = f"{IMAGES_BASE_URL}/{file_name}"
        image_path = destination / file_name
        if image_path.is_file() and image_path.stat().st_size > 0:
            content = image_path.read_bytes()
        else:
            content = downloader(image_url)
            if not content:
                raise ValueError(f"downloaded image {image_id} is empty")
            temporary = image_path.with_suffix(image_path.suffix + ".tmp")
            temporary.write_bytes(content)
            temporary.replace(image_path)
        return image, content, image_url

    selected = eligible[:size]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        materialized = list(executor.map(materialize, selected))

    rows: list[dict[str, Any]] = []
    for index, (image, content, image_url) in enumerate(materialized):
        image_id = int(image["id"])
        file_name = str(image["file_name"])
        license_row = licenses[int(image["license"])]
        rows.append(
            {
                "image_id": image_id,
                "file_name": file_name,
                "split": (
                    "validation" if index < validation_size else "benchmark"
                ),
                "captions": [
                    caption
                    for _, caption in sorted(captions_by_image[image_id])
                ],
                "license_id": int(image["license"]),
                "license_name": str(license_row.get("name", "")),
                "license_url": str(license_row.get("url", "")),
                "coco_url": image_url,
                "flickr_url": str(image.get("flickr_url", "")),
                "sha256": _sha256_bytes(content),
                "bytes": len(content),
                "selection_key": _stable_key(image_id),
            }
        )
    return rows


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a deterministic COCO 2017 text-to-image subset."
    )
    parser.add_argument(
        "--captions",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "datasets"
            / "raw"
            / "coco"
            / "annotations"
            / "captions_val2017.json"
        ),
    )
    parser.add_argument(
        "--instances",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "datasets"
            / "raw"
            / "coco"
            / "annotations"
            / "instances_val2017.json"
        ),
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "datasets"
            / "raw"
            / "coco"
            / "val2017"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPOSITORY_ROOT / "datasets" / "processed" / "coco",
    )
    parser.add_argument("--size", type=int, default=200)
    parser.add_argument("--validation-size", type=int, default=160)
    args = parser.parse_args()

    captions_path = args.captions.resolve(strict=True)
    instances_path = args.instances.resolve(strict=True)
    captions = json.loads(captions_path.read_text(encoding="utf-8"))
    instances = json.loads(instances_path.read_text(encoding="utf-8"))
    if not isinstance(captions, dict) or not isinstance(instances, dict):
        raise ValueError("annotation roots must be JSON objects")
    rows = prepare_subset(
        captions,
        instances,
        image_dir=args.image_dir,
        size=args.size,
        validation_size=args.validation_size,
    )

    output = args.output_dir.resolve()
    validation = [row for row in rows if row["split"] == "validation"]
    benchmark = [row for row in rows if row["split"] == "benchmark"]
    validation_path = output / "validation" / "items.jsonl"
    benchmark_path = output / "benchmark" / "items.jsonl"
    _write_jsonl(validation_path, validation)
    _write_jsonl(benchmark_path, benchmark)
    license_counts: dict[int, int] = defaultdict(int)
    for row in rows:
        license_counts[int(row["license_id"])] += 1
    license_examples = {
        int(row["license_id"]): row
        for row in rows
    }
    metadata = {
        "schema_version": "1",
        "dataset": "COCO 2017 validation",
        "annotations_source": CAPTIONS_URL,
        "selection": (
            "eligible image IDs sorted by SHA-256(coco-2017-val NUL image_id)"
        ),
        "validation_images": len(validation),
        "benchmark_images": len(benchmark),
        "total_image_bytes": sum(int(row["bytes"]) for row in rows),
        "captions_sha256": _sha256_path(captions_path),
        "instances_sha256": _sha256_path(instances_path),
        "license_distribution": [
            {
                "license_id": license_id,
                "license_name": license_examples[license_id]["license_name"],
                "license_url": license_examples[license_id]["license_url"],
                "image_count": license_counts[license_id],
            }
            for license_id in sorted(license_counts)
        ],
        "artifacts": {
            "validation/items.jsonl": {
                "sha256": _sha256_path(validation_path),
                "bytes": validation_path.stat().st_size,
            },
            "benchmark/items.jsonl": {
                "sha256": _sha256_path(benchmark_path),
                "bytes": benchmark_path.stat().st_size,
            },
        },
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
