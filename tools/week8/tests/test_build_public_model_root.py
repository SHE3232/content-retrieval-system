from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.week8.build_public_model_root import stage_public_model_root


TEXT_MODEL_ID = "text-multilingual-v1"
IMAGE_MODEL_ID = "mobileclip-s0-v1"


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = file_path.relative_to(path).as_posix().encode("utf-8")
        file_digest = hashlib.sha256(file_path.read_bytes()).digest()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(file_digest)
    return digest.hexdigest()


def _write_source(root: Path, *, text_digest: str | None = None) -> Path:
    text_path = root / "text" / TEXT_MODEL_ID
    text_path.mkdir(parents=True)
    (text_path / "config.json").write_text("{}", encoding="utf-8")
    (text_path / "model.safetensors").write_bytes(b"text-model")
    image_path = root / "mobileclip" / "mobileclip_s0.pt"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"research-only-image-model")
    manifest = {
        "schema_version": "1",
        "models": [
            {
                "model_id": TEXT_MODEL_ID,
                "space_id": "text-semantic-v1",
                "modality": "text",
                "dimensions": 384,
                "relative_path": f"text/{TEXT_MODEL_ID}",
                "sha256": text_digest or _sha256_path(text_path),
                "license_name": "Apache-2.0",
                "runtime": "sentence-transformers",
            },
            {
                "model_id": IMAGE_MODEL_ID,
                "space_id": "mobileclip-image-text-v1",
                "modality": "image_text",
                "dimensions": 512,
                "relative_path": "mobileclip/mobileclip_s0.pt",
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "license_name": (
                    "Apple Machine Learning Research Model License"
                ),
                "runtime": "pytorch-mobileclip",
            },
        ],
    }
    manifest_path = root / "model-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest_path


def test_stages_only_verified_apache_text_model(tmp_path: Path) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    destination = tmp_path / "public-models"

    result = stage_public_model_root(
        source_model_root=source,
        source_manifest_path=manifest,
        destination=destination,
    )

    staged_manifest = json.loads(
        (destination / "model-manifest.json").read_text(encoding="utf-8")
    )
    assert result["included_model_ids"] == [TEXT_MODEL_ID]
    assert staged_manifest["models"] == [
        next(
            model
            for model in json.loads(manifest.read_text(encoding="utf-8"))[
                "models"
            ]
            if model["model_id"] == TEXT_MODEL_ID
        )
    ]
    assert (destination / "text" / TEXT_MODEL_ID / "config.json").is_file()
    assert not (destination / "mobileclip").exists()
    assert IMAGE_MODEL_ID not in (destination / "model-manifest.json").read_text(
        encoding="utf-8"
    )


def test_rejects_text_model_digest_mismatch_without_partial_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source, text_digest="0" * 64)
    destination = tmp_path / "public-models"

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        stage_public_model_root(
            source_model_root=source,
            source_manifest_path=manifest,
            destination=destination,
        )

    assert not destination.exists()


def test_refuses_nonempty_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    destination = tmp_path / "public-models"
    destination.mkdir()
    (destination / "owned-by-user.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="not empty"):
        stage_public_model_root(
            source_model_root=source,
            source_manifest_path=manifest,
            destination=destination,
        )

    assert (destination / "owned-by-user.txt").read_text(encoding="utf-8") == "keep"
