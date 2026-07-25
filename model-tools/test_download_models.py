import json
from pathlib import Path


def test_download_text_model_saves_a_pinned_snapshot_and_updates_manifest(
    tmp_path: Path,
) -> None:
    from download_models import download_text_model

    calls: dict[str, object] = {}

    def fake_snapshot_download(**kwargs: object) -> str:
        calls["snapshot"] = kwargs
        target = Path(str(kwargs["local_dir"]))
        target.mkdir(parents=True)
        (target / "config.json").write_text("{}", encoding="utf-8")
        (target / "model.safetensors").write_bytes(b"weights")
        return str(target)

    class FakeModel:
        def get_sentence_embedding_dimension(self) -> int:
            return 384

    def fake_model_factory(path: str, **kwargs: object) -> FakeModel:
        calls["model"] = {"path": path, "kwargs": kwargs}
        return FakeModel()

    manifest_path = tmp_path / "model-manifest.json"
    entry = download_text_model(
        repo_id="sentence-transformers/example",
        revision="abc123",
        model_root=tmp_path / "models",
        manifest_path=manifest_path,
        model_id="text-multilingual-v1",
        space_id="text-semantic-v1",
        license_name="Apache-2.0",
        snapshot_downloader=fake_snapshot_download,
        model_factory=fake_model_factory,
    )

    assert calls["snapshot"] == {
        "repo_id": "sentence-transformers/example",
        "revision": "abc123",
        "local_dir": str(
            (tmp_path / "models" / "text" / "text-multilingual-v1").resolve()
        ),
        "local_dir_use_symlinks": False,
        "allow_patterns": [
            "1_Pooling/config.json",
            "README.md",
            "config.json",
            "config_sentence_transformers.json",
            "model.safetensors",
            "modules.json",
            "sentence_bert_config.json",
            "sentencepiece.bpe.model",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "unigram.json",
        ],
    }
    assert calls["model"] == {
        "path": str(
            (tmp_path / "models" / "text" / "text-multilingual-v1").resolve()
        ),
        "kwargs": {"device": "cpu", "local_files_only": True},
    }
    assert entry["dimensions"] == 384
    assert len(entry["sha256"]) == 64
    assert entry["revision"] == "abc123"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload == {"schema_version": "1", "models": [entry]}


def test_download_text_model_preserves_other_manifest_entries(
    tmp_path: Path,
) -> None:
    from download_models import upsert_manifest

    manifest_path = tmp_path / "manifest.json"
    image_entry = {
        "model_id": "mobileclip-s0-v1",
        "space_id": "mobileclip-image-text-v1",
    }
    manifest_path.write_text(
        json.dumps({"schema_version": "1", "models": [image_entry]}),
        encoding="utf-8",
    )
    text_entry = {
        "model_id": "text-multilingual-v1",
        "space_id": "text-semantic-v1",
    }

    upsert_manifest(manifest_path, text_entry)
    upsert_manifest(manifest_path, {**text_entry, "dimensions": 384})

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [entry["model_id"] for entry in payload["models"]] == [
        "mobileclip-s0-v1",
        "text-multilingual-v1",
    ]
    assert payload["models"][1]["dimensions"] == 384
