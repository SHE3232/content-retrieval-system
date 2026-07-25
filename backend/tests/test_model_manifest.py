import hashlib
import json
from pathlib import Path

import pytest


def write_manifest(
    path: Path,
    *,
    relative_path: str,
    sha256: str,
    model_id: str = "text-multilingual-v1",
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "models": [
                    {
                        "model_id": model_id,
                        "space_id": "text-semantic-v1",
                        "modality": "text",
                        "dimensions": 3,
                        "relative_path": relative_path,
                        "sha256": sha256,
                        "license_name": "Apache-2.0",
                        "runtime": "sentence-transformers",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_manifest_loads_model_metadata_and_verifies_a_local_file(
    tmp_path: Path,
) -> None:
    from content_retrieval.embeddings.manifest import ModelManifest

    model_root = tmp_path / "models"
    model_root.mkdir()
    artifact = model_root / "encoder.bin"
    artifact.write_bytes(b"offline-model")
    expected_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    write_manifest(
        manifest_path,
        relative_path="encoder.bin",
        sha256=expected_hash,
    )

    manifest = ModelManifest.load(manifest_path, model_root=model_root)
    entry = manifest.require("text-multilingual-v1")

    assert entry.space_id == "text-semantic-v1"
    assert entry.modality == "text"
    assert entry.dimensions == 3
    assert entry.path == artifact.resolve()
    assert entry.verify() == expected_hash


def test_manifest_rejects_a_hash_mismatch(tmp_path: Path) -> None:
    from content_retrieval.embeddings.manifest import (
        ModelManifest,
        ModelManifestError,
    )

    model_root = tmp_path / "models"
    model_root.mkdir()
    (model_root / "encoder.bin").write_bytes(b"tampered")
    manifest_path = tmp_path / "manifest.json"
    write_manifest(
        manifest_path,
        relative_path="encoder.bin",
        sha256="0" * 64,
    )

    entry = ModelManifest.load(manifest_path, model_root=model_root).require(
        "text-multilingual-v1"
    )

    with pytest.raises(ModelManifestError, match="SHA-256"):
        entry.verify()


def test_manifest_rejects_paths_outside_the_model_root(tmp_path: Path) -> None:
    from content_retrieval.embeddings.manifest import (
        ModelManifest,
        ModelManifestError,
    )

    model_root = tmp_path / "models"
    model_root.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    manifest_path = tmp_path / "manifest.json"
    write_manifest(
        manifest_path,
        relative_path="../outside.bin",
        sha256=hashlib.sha256(outside.read_bytes()).hexdigest(),
    )

    with pytest.raises(ModelManifestError, match="outside model_root"):
        ModelManifest.load(manifest_path, model_root=model_root)


def test_manifest_hashes_directories_deterministically(tmp_path: Path) -> None:
    from content_retrieval.embeddings.manifest import (
        ModelManifest,
        sha256_path,
    )

    model_root = tmp_path / "models"
    model_dir = model_root / "text-model"
    (model_dir / "nested").mkdir(parents=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "nested" / "weights.bin").write_bytes(b"weights")
    expected_hash = sha256_path(model_dir)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(
        manifest_path,
        relative_path="text-model",
        sha256=expected_hash,
    )

    entry = ModelManifest.load(manifest_path, model_root=model_root).require(
        "text-multilingual-v1"
    )

    assert entry.verify() == expected_hash
    (model_dir / "nested" / "weights.bin").write_bytes(b"changed")
    with pytest.raises(Exception, match="SHA-256"):
        entry.verify()


def test_directory_hash_ignores_download_cache_metadata(tmp_path: Path) -> None:
    from content_retrieval.embeddings.manifest import sha256_path

    model_dir = tmp_path / "model"
    cache_dir = model_dir / ".cache" / "huggingface"
    cache_dir.mkdir(parents=True)
    (model_dir / "weights.bin").write_bytes(b"weights")
    (cache_dir / "download.json").write_text("first", encoding="utf-8")

    first = sha256_path(model_dir)
    (cache_dir / "download.json").write_text("changed", encoding="utf-8")
    second = sha256_path(model_dir)

    assert first == second


def test_manifest_rejects_duplicate_ids_and_unknown_models(tmp_path: Path) -> None:
    from content_retrieval.embeddings.manifest import (
        ModelManifest,
        ModelManifestError,
    )

    model_root = tmp_path / "models"
    model_root.mkdir()
    artifact = model_root / "encoder.bin"
    artifact.write_bytes(b"model")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    model = {
        "model_id": "duplicate",
        "space_id": "text-semantic-v1",
        "modality": "text",
        "dimensions": 3,
        "relative_path": "encoder.bin",
        "sha256": digest,
        "license_name": "Apache-2.0",
        "runtime": "sentence-transformers",
    }
    manifest_path.write_text(
        json.dumps({"schema_version": "1", "models": [model, model]}),
        encoding="utf-8",
    )

    with pytest.raises(ModelManifestError, match="duplicate model_id"):
        ModelManifest.load(manifest_path, model_root=model_root)

    write_manifest(
        manifest_path,
        relative_path="encoder.bin",
        sha256=digest,
    )
    manifest = ModelManifest.load(manifest_path, model_root=model_root)
    with pytest.raises(ModelManifestError, match="unknown model_id"):
        manifest.require("missing")
