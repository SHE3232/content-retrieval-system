from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any
from uuid import uuid4

TEXT_MODEL_ID = "text-multilingual-v1"
IMAGE_MODEL_ID = "mobileclip-s0-v1"
PUBLIC_MODEL_LICENSE = "Apache-2.0"
RESEARCH_MODEL_LICENSE = "Apple Machine Learning Research Model License"
RESEARCH_LICENSE_MARKER = "Apple Machine Learning Research Model"


def _sha256_file(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def sha256_path(path: Path) -> str:
    resolved = path.resolve(strict=True)
    if resolved.is_file():
        return _sha256_file(resolved).hex()
    if not resolved.is_dir():
        raise ValueError(f"model artifact is not a file or directory: {path}")
    files = sorted(
        (
            candidate
            for candidate in resolved.rglob("*")
            if candidate.is_file()
            and ".cache" not in candidate.relative_to(resolved).parts
        ),
        key=lambda candidate: candidate.relative_to(resolved).as_posix(),
    )
    if not files:
        raise ValueError(f"model directory is empty: {path}")
    digest = hashlib.sha256()
    for candidate in files:
        relative = candidate.relative_to(resolved).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(_sha256_file(candidate))
    return digest.hexdigest()


def _is_linklike(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse)


def _assert_plain_tree(path: Path) -> None:
    if _is_linklike(path):
        raise ValueError(f"model artifact must not be a link or reparse point: {path}")
    if path.is_dir():
        for candidate in path.rglob("*"):
            if _is_linklike(candidate):
                raise ValueError(
                    "model artifact contains a link or reparse point: "
                    f"{candidate}"
                )


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"model manifest is invalid: {path}") from error
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise TypeError("model manifest must contain a models array")
    return data


def stage_public_model_root(
    *,
    source_model_root: Path | str,
    source_manifest_path: Path | str,
    destination: Path | str,
) -> dict[str, Any]:
    source_root = Path(source_model_root).expanduser().resolve(strict=True)
    manifest_path = Path(source_manifest_path).expanduser().resolve(strict=True)
    target = Path(destination).expanduser().resolve()
    if not source_root.is_dir():
        raise ValueError(f"source model root is not a directory: {source_root}")
    if not manifest_path.is_file():
        raise ValueError(f"source model manifest is not a file: {manifest_path}")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FileExistsError(f"destination is not empty: {target}")

    data = _load_manifest(manifest_path)
    matching = [
        model
        for model in data["models"]
        if isinstance(model, dict) and model.get("model_id") == TEXT_MODEL_ID
    ]
    if len(matching) != 1:
        raise ValueError(
            f"model manifest must contain exactly one {TEXT_MODEL_ID} entry"
        )
    text_entry = matching[0]
    if text_entry.get("license_name") != PUBLIC_MODEL_LICENSE:
        raise ValueError(
            f"{TEXT_MODEL_ID} must use the {PUBLIC_MODEL_LICENSE} license"
        )
    relative_path = text_entry.get("relative_path")
    expected_digest = text_entry.get("sha256")
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError(f"{TEXT_MODEL_ID} relative_path is invalid")
    if (
        not isinstance(expected_digest, str)
        or len(expected_digest) != 64
        or any(character not in "0123456789abcdef" for character in expected_digest)
    ):
        raise ValueError(f"{TEXT_MODEL_ID} SHA-256 is invalid")

    artifact = (source_root / relative_path).resolve(strict=True)
    try:
        artifact.relative_to(source_root)
    except ValueError as error:
        raise ValueError(f"model artifact escapes source root: {artifact}") from error
    _assert_plain_tree(artifact)
    actual_digest = sha256_path(artifact)
    if actual_digest != expected_digest:
        raise ValueError(
            f"model SHA-256 mismatch for {TEXT_MODEL_ID}: "
            f"expected {expected_digest}, got {actual_digest}"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.parent / f".{target.name}.stage-{uuid4().hex}"
    if stage.exists():
        raise FileExistsError(f"temporary staging path already exists: {stage}")
    try:
        staged_artifact = stage / relative_path
        staged_artifact.parent.mkdir(parents=True, exist_ok=True)
        if artifact.is_dir():
            shutil.copytree(
                artifact,
                staged_artifact,
                ignore=shutil.ignore_patterns(".cache"),
            )
        else:
            shutil.copy2(artifact, staged_artifact)
        staged_digest = sha256_path(staged_artifact)
        if staged_digest != expected_digest:
            raise ValueError(
                f"staged model SHA-256 mismatch for {TEXT_MODEL_ID}: "
                f"expected {expected_digest}, got {staged_digest}"
            )
        public_manifest = {
            "schema_version": data.get("schema_version", "1"),
            "models": [text_entry],
        }
        (stage / "model-manifest.json").write_text(
            json.dumps(public_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = {
            "schema_version": 1,
            "distribution_class": "default-public",
            "source_manifest_sha256": _sha256_file(manifest_path).hex(),
            "included_model_ids": [TEXT_MODEL_ID],
            "excluded_model_policy": "MobileCLIP weights are not included",
            "model_artifact_sha256": expected_digest,
        }
        (stage / "PUBLIC_MODEL_ROOT_MANIFEST.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if target.exists():
            target.rmdir()
        os.replace(stage, target)
        return result
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def stage_research_model_root(
    *,
    source_model_root: Path | str,
    source_manifest_path: Path | str,
    destination: Path | str,
) -> dict[str, Any]:
    source_root = Path(source_model_root).expanduser().resolve(strict=True)
    manifest_path = Path(source_manifest_path).expanduser().resolve(strict=True)
    target = Path(destination).expanduser().resolve()
    if not source_root.is_dir():
        raise ValueError(f"source model root is not a directory: {source_root}")
    if not manifest_path.is_file():
        raise ValueError(f"source model manifest is not a file: {manifest_path}")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FileExistsError(f"destination is not empty: {target}")

    data = _load_manifest(manifest_path)
    entries = [entry for entry in data["models"] if isinstance(entry, dict)]
    by_id = {entry.get("model_id"): entry for entry in entries}
    required_ids = [TEXT_MODEL_ID, IMAGE_MODEL_ID]
    if set(by_id) != set(required_ids) or len(entries) != len(required_ids):
        raise ValueError(
            "research manifest must contain exactly the text and MobileCLIP models"
        )
    if by_id[TEXT_MODEL_ID].get("license_name") != PUBLIC_MODEL_LICENSE:
        raise ValueError(
            f"{TEXT_MODEL_ID} must use the {PUBLIC_MODEL_LICENSE} license"
        )
    if by_id[IMAGE_MODEL_ID].get("license_name") != RESEARCH_MODEL_LICENSE:
        raise ValueError(
            f"{IMAGE_MODEL_ID} must use the research-only model license"
        )

    validated: list[tuple[dict[str, Any], Path, str]] = []
    for model_id in required_ids:
        entry = by_id[model_id]
        relative_path = entry.get("relative_path")
        expected_digest = entry.get("sha256")
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError(f"{model_id} relative_path is invalid")
        if (
            not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_digest
            )
        ):
            raise ValueError(f"{model_id} SHA-256 is invalid")
        artifact = (source_root / relative_path).resolve(strict=True)
        try:
            artifact.relative_to(source_root)
        except ValueError as error:
            raise ValueError(
                f"model artifact escapes source root: {artifact}"
            ) from error
        _assert_plain_tree(artifact)
        actual_digest = sha256_path(artifact)
        if actual_digest != expected_digest:
            raise ValueError(
                f"model SHA-256 mismatch for {model_id}: "
                f"expected {expected_digest}, got {actual_digest}"
            )
        validated.append((entry, artifact, relative_path))

    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.parent / f".{target.name}.stage-{uuid4().hex}"
    if stage.exists():
        raise FileExistsError(f"temporary staging path already exists: {stage}")
    try:
        for entry, artifact, relative_path in validated:
            staged_artifact = stage / relative_path
            staged_artifact.parent.mkdir(parents=True, exist_ok=True)
            if artifact.is_dir():
                shutil.copytree(
                    artifact,
                    staged_artifact,
                    ignore=shutil.ignore_patterns(".cache"),
                )
            else:
                shutil.copy2(artifact, staged_artifact)
                for license_path in artifact.parent.iterdir():
                    if (
                        license_path.is_file()
                        and license_path.name.upper()
                        in {"LICENSE", "LICENSE_MODELS"}
                    ):
                        shutil.copy2(
                            license_path,
                            staged_artifact.parent / license_path.name,
                        )
            staged_digest = sha256_path(staged_artifact)
            if staged_digest != entry["sha256"]:
                raise ValueError(
                    f"staged model SHA-256 mismatch for {entry['model_id']}: "
                    f"expected {entry['sha256']}, got {staged_digest}"
                )

        license_files = [
            candidate
            for candidate in stage.rglob("*")
            if candidate.is_file()
            and candidate.name.upper() in {"LICENSE", "LICENSE_MODELS"}
        ]
        if not any(
            RESEARCH_LICENSE_MARKER
            in candidate.read_text(encoding="utf-8", errors="replace")
            for candidate in license_files
        ):
            raise ValueError("research model license text was not staged")
        research_manifest = {
            "schema_version": data.get("schema_version", "1"),
            "models": entries,
        }
        (stage / "model-manifest.json").write_text(
            json.dumps(research_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = {
            "schema_version": 1,
            "distribution_class": "research-only",
            "source_manifest_sha256": _sha256_file(manifest_path).hex(),
            "included_model_ids": required_ids,
            "cache_policy": "download caches are excluded",
            "model_artifact_sha256": {
                entry["model_id"]: entry["sha256"] for entry in entries
            },
        }
        (stage / "RESEARCH_MODEL_ROOT_MANIFEST.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if target.exists():
            target.rmdir()
        os.replace(stage, target)
        return result
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage the Apache-licensed text model for public releases."
    )
    parser.add_argument("--source-model-root", required=True, type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument(
        "--distribution",
        choices=("default-public", "research-only"),
        default="default-public",
    )
    args = parser.parse_args()
    builder = (
        stage_public_model_root
        if args.distribution == "default-public"
        else stage_research_model_root
    )
    result = builder(
        source_model_root=args.source_model_root,
        source_manifest_path=args.source_manifest,
        destination=args.destination,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
