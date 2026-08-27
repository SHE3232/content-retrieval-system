import hashlib
import json
from pathlib import Path

import pytest

from content_retrieval.embeddings.manifest import (
    ModelManifestError,
    sha256_path,
)


class FakeTextBackend:
    created: list[dict[str, object]] = []

    def __init__(
        self,
        model_path: Path,
        *,
        model_id: str,
        space_id: str,
        dimensions: int,
        batch_size: int,
    ) -> None:
        self.model_path = Path(model_path)
        self.model_id = model_id
        self.space_id = space_id
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.created.append(
            {
                "path": self.model_path,
                "model_id": model_id,
                "space_id": space_id,
                "dimensions": dimensions,
                "batch_size": batch_size,
            }
        )

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FakeMobileClipBackend:
    created: list[dict[str, object]] = []

    def __init__(
        self,
        weights_path: Path,
        *,
        model_id: str,
        space_id: str,
        dimensions: int,
    ) -> None:
        self.weights_path = Path(weights_path)
        self.model_id = model_id
        self.space_id = space_id
        self.dimensions = dimensions
        self.created.append(
            {
                "path": self.weights_path,
                "model_id": model_id,
                "space_id": space_id,
                "dimensions": dimensions,
            }
        )

    def encode_images(self, paths: list[Path]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in paths]

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def write_manifest(
    root: Path,
    *,
    text_hash: str | None = None,
    include_image: bool = True,
) -> Path:
    text_path = root / "text" / "text-multilingual-v1"
    text_path.mkdir(parents=True)
    (text_path / "config.json").write_text(
        '{"fixture": true}',
        encoding="utf-8",
    )
    image_path = root / "mobileclip" / "mobileclip_s0.pt"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"local-mobileclip-fixture")
    manifest = root / "model-manifest.json"
    entries = [
        {
            "model_id": "text-multilingual-v1",
            "space_id": "text-semantic-v1",
            "modality": "text",
            "dimensions": 2,
            "relative_path": "text/text-multilingual-v1",
            "sha256": text_hash or sha256_path(text_path),
            "license_name": "Apache-2.0",
            "runtime": "sentence-transformers",
        }
    ]
    if include_image:
        entries.append(
            {
                "model_id": "mobileclip-s0-v1",
                "space_id": "mobileclip-image-text-v1",
                "modality": "image_text",
                "dimensions": 2,
                "relative_path": "mobileclip/mobileclip_s0.pt",
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "license_name": "Fixture",
                "runtime": "pytorch-mobileclip",
            }
        )
    manifest.write_text(
        json.dumps({"schema_version": "1", "models": entries}),
        encoding="utf-8",
    )
    return manifest


def test_runtime_factory_requires_explicit_local_paths(tmp_path: Path) -> None:
    from content_retrieval.runtime import build_local_runtime

    with pytest.raises(FileNotFoundError):
        build_local_runtime(
            model_root=tmp_path / "missing-models",
            manifest_path=tmp_path / "missing-manifest.json",
            data_dir=tmp_path / "data",
        )


def test_runtime_factory_validates_hashes_before_loading_models(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import content_retrieval.runtime as runtime

    model_root = tmp_path / "models"
    manifest = write_manifest(model_root, text_hash="0" * 64)
    calls: list[str] = []
    monkeypatch.setattr(
        runtime,
        "SentenceTransformerBackend",
        lambda *args, **kwargs: calls.append("text"),
    )
    monkeypatch.setattr(
        runtime,
        "LocalMobileClipBackend",
        lambda *args, **kwargs: calls.append("image"),
    )

    with pytest.raises(ModelManifestError, match="SHA-256 mismatch"):
        runtime.build_local_runtime(
            model_root=model_root,
            manifest_path=manifest,
            data_dir=tmp_path / "data",
        )

    assert calls == []


def test_runtime_factory_builds_persistent_local_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import content_retrieval.runtime as runtime

    FakeTextBackend.created.clear()
    FakeMobileClipBackend.created.clear()
    model_root = tmp_path / "models"
    manifest = write_manifest(model_root)
    data_dir = tmp_path / "runtime-data"
    monkeypatch.setattr(
        runtime,
        "SentenceTransformerBackend",
        FakeTextBackend,
    )
    monkeypatch.setattr(
        runtime,
        "LocalMobileClipBackend",
        FakeMobileClipBackend,
    )

    bundle = runtime.build_local_runtime(
        model_root=model_root,
        manifest_path=manifest,
        data_dir=data_dir,
        tika_url="http://127.0.0.1:10098",
        text_batch_size=4,
        image_batch_size=3,
    )

    assert bundle.model_root == model_root.resolve()
    assert bundle.data_dir == data_dir.resolve()
    assert bundle.repository.database_path == (data_dir / "chroma").resolve()
    assert bundle.indexing_service.repository is bundle.repository
    assert bundle.retrieval_service.repository is bundle.repository
    assert bundle.embedding_service.text_engine is bundle.text_engine
    assert bundle.embedding_service.mobileclip_engine is bundle.image_engine
    assert FakeTextBackend.created == [
        {
            "path": (
                model_root / "text" / "text-multilingual-v1"
            ).resolve(),
            "model_id": "text-multilingual-v1",
            "space_id": "text-semantic-v1",
            "dimensions": 2,
            "batch_size": 4,
        }
    ]
    assert FakeMobileClipBackend.created == [
        {
            "path": (
                model_root / "mobileclip" / "mobileclip_s0.pt"
            ).resolve(),
            "model_id": "mobileclip-s0-v1",
            "space_id": "mobileclip-image-text-v1",
            "dimensions": 2,
        }
    ]
    assert bundle.text_engine.batch_size == 4
    assert bundle.image_engine.batch_size == 3
    docx_parser = bundle.ingestion_service._registry.resolve(Path("sample.docx"))
    assert docx_parser.tika_client.base_url == "http://127.0.0.1:10098"
    assert bundle.repository.count() == 0

    from chromadb.api.shared_system_client import SharedSystemClient

    identifier = str(bundle.repository.database_path)
    assert identifier in SharedSystemClient._identifier_to_system

    bundle.close()

    assert identifier not in SharedSystemClient._identifier_to_system


def test_runtime_factory_builds_text_only_runtime_without_mobileclip_weights(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import content_retrieval.runtime as runtime

    FakeTextBackend.created.clear()
    model_root = tmp_path / "models"
    manifest = write_manifest(model_root, include_image=False)
    monkeypatch.setattr(runtime, "SentenceTransformerBackend", FakeTextBackend)

    def reject_mobileclip(*args, **kwargs):
        raise AssertionError(
            "MobileCLIP backend must not load for a text-only manifest"
        )

    monkeypatch.setattr(runtime, "LocalMobileClipBackend", reject_mobileclip)

    bundle = runtime.build_local_runtime(
        model_root=model_root,
        manifest_path=manifest,
        data_dir=tmp_path / "runtime-data",
    )

    assert bundle.image_engine.available is False
    assert bundle.embedding_service.image_semantic_available is False
    assert bundle.retrieval_service.available_channels == (
        "keyword",
        "text_semantic",
    )
    bundle.close()
