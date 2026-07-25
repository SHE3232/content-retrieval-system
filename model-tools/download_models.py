from __future__ import annotations

import argparse
from collections.abc import Callable
import json
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SOURCE = REPOSITORY_ROOT / "backend" / "src"
if str(BACKEND_SOURCE) not in sys.path:
    sys.path.insert(0, str(BACKEND_SOURCE))

from content_retrieval.embeddings.manifest import sha256_path


TEXT_MODEL_FILES = [
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
]


def upsert_manifest(path: Path, entry: dict[str, object]) -> None:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != "1"
            or not isinstance(payload.get("models"), list)
        ):
            raise ValueError("existing model manifest has an unsupported shape")
        models = payload["models"]
    else:
        payload = {"schema_version": "1", "models": []}
        models = payload["models"]

    model_id = entry.get("model_id")
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("entry.model_id must be a non-empty string")
    replacement_index = next(
        (
            index
            for index, current in enumerate(models)
            if isinstance(current, dict) and current.get("model_id") == model_id
        ),
        None,
    )
    if replacement_index is None:
        models.append(entry)
    else:
        models[replacement_index] = entry

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def download_text_model(
    *,
    repo_id: str,
    revision: str,
    model_root: Path,
    manifest_path: Path,
    model_id: str,
    space_id: str,
    license_name: str,
    snapshot_downloader: Callable[..., str] | None = None,
    model_factory: Callable[..., Any] | None = None,
) -> dict[str, object]:
    if not revision.strip():
        raise ValueError("revision must be pinned")
    root = model_root.resolve()
    target = (root / "text" / model_id).resolve()
    if not target.is_relative_to(root):
        raise ValueError("model_id resolves outside model_root")
    target.parent.mkdir(parents=True, exist_ok=True)

    if snapshot_downloader is None:
        from huggingface_hub import snapshot_download

        snapshot_downloader = snapshot_download
    snapshot_downloader(
        repo_id=repo_id,
        revision=revision,
        local_dir=str(target),
        local_dir_use_symlinks=False,
        allow_patterns=TEXT_MODEL_FILES,
    )

    if model_factory is None:
        from sentence_transformers import SentenceTransformer

        model_factory = SentenceTransformer
    model = model_factory(
        str(target),
        device="cpu",
        local_files_only=True,
    )
    if hasattr(model, "get_embedding_dimension"):
        dimensions = model.get_embedding_dimension()
    else:
        dimensions = model.get_sentence_embedding_dimension()
    if not isinstance(dimensions, int) or dimensions <= 0:
        raise ValueError("downloaded model has no valid embedding dimension")

    entry: dict[str, object] = {
        "model_id": model_id,
        "space_id": space_id,
        "modality": "text",
        "dimensions": dimensions,
        "relative_path": target.relative_to(root).as_posix(),
        "sha256": sha256_path(target),
        "license_name": license_name,
        "runtime": "sentence-transformers",
        "source_repo": repo_id,
        "revision": revision,
    }
    upsert_manifest(manifest_path, entry)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and verify a pinned local text embedding model."
    )
    parser.add_argument(
        "--repo-id",
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    parser.add_argument("--revision", required=True)
    parser.add_argument("--model-id", default="text-multilingual-v1")
    parser.add_argument("--space-id", default="text-semantic-v1")
    parser.add_argument("--license-name", default="Apache-2.0")
    parser.add_argument(
        "--model-root",
        type=Path,
        default=REPOSITORY_ROOT / "models",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPOSITORY_ROOT / "models" / "model-manifest.json",
    )
    args = parser.parse_args()

    entry = download_text_model(
        repo_id=args.repo_id,
        revision=args.revision,
        model_root=args.model_root,
        manifest_path=args.manifest,
        model_id=args.model_id,
        space_id=args.space_id,
        license_name=args.license_name,
    )
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
