from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MODALITIES = {"text", "image", "image_text"}


class ModelManifestError(Exception):
    """A local model manifest or artifact failed validation."""


def _sha256_file(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.digest()


def sha256_path(path: Path) -> str:
    """Hash one file or a directory tree without following external paths."""

    resolved = path.resolve(strict=True)
    if resolved.is_file():
        return _sha256_file(resolved).hex()
    if not resolved.is_dir():
        raise ModelManifestError(f"model artifact is not a file or directory: {path}")

    digest = hashlib.sha256()
    files = sorted(
        (candidate for candidate in resolved.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(resolved).as_posix(),
    )
    if not files:
        raise ModelManifestError(f"model directory is empty: {path}")
    for candidate in files:
        relative = candidate.relative_to(resolved).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(_sha256_file(candidate))
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ModelEntry:
    model_id: str
    space_id: str
    modality: str
    dimensions: int
    path: Path
    sha256: str
    license_name: str
    runtime: str

    def verify(self) -> str:
        try:
            actual = sha256_path(self.path)
        except FileNotFoundError as error:
            raise ModelManifestError(
                f"model artifact does not exist: {self.path}"
            ) from error
        if actual != self.sha256:
            raise ModelManifestError(
                f"model SHA-256 mismatch for {self.model_id}: "
                f"expected {self.sha256}, got {actual}"
            )
        return actual


@dataclass(frozen=True, slots=True)
class ModelManifest:
    entries: tuple[ModelEntry, ...]
    schema_version: str = "1"

    @classmethod
    def load(
        cls,
        path: Path | str,
        *,
        model_root: Path | str,
    ) -> ModelManifest:
        manifest_path = Path(path).resolve(strict=True)
        root = Path(model_root).resolve(strict=True)
        if not root.is_dir():
            raise ModelManifestError(f"model_root is not a directory: {root}")

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ModelManifestError(
                f"cannot read model manifest: {manifest_path}"
            ) from error
        if not isinstance(payload, dict):
            raise ModelManifestError("model manifest root must be an object")
        if payload.get("schema_version") != "1":
            raise ModelManifestError("unsupported model manifest schema_version")
        raw_models = payload.get("models")
        if not isinstance(raw_models, list) or not raw_models:
            raise ModelManifestError("model manifest must contain a non-empty models list")

        entries: list[ModelEntry] = []
        seen_ids: set[str] = set()
        for index, raw in enumerate(raw_models):
            if not isinstance(raw, dict):
                raise ModelManifestError(f"models[{index}] must be an object")
            entry = cls._entry_from_json(raw, index=index, model_root=root)
            if entry.model_id in seen_ids:
                raise ModelManifestError(
                    f"duplicate model_id in manifest: {entry.model_id}"
                )
            seen_ids.add(entry.model_id)
            entries.append(entry)
        return cls(entries=tuple(entries))

    @staticmethod
    def _entry_from_json(
        raw: dict[str, Any],
        *,
        index: int,
        model_root: Path,
    ) -> ModelEntry:
        required_text = (
            "model_id",
            "space_id",
            "modality",
            "relative_path",
            "sha256",
            "license_name",
            "runtime",
        )
        values: dict[str, str] = {}
        for field_name in required_text:
            value = raw.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ModelManifestError(
                    f"models[{index}].{field_name} must be a non-empty string"
                )
            values[field_name] = value.strip()

        dimensions = raw.get("dimensions")
        if not isinstance(dimensions, int) or isinstance(dimensions, bool):
            raise ModelManifestError(
                f"models[{index}].dimensions must be a positive integer"
            )
        if dimensions <= 0:
            raise ModelManifestError(
                f"models[{index}].dimensions must be a positive integer"
            )
        if values["modality"] not in _MODALITIES:
            raise ModelManifestError(
                f"models[{index}].modality must be text, image, or image_text"
            )
        if not _SHA256_PATTERN.fullmatch(values["sha256"]):
            raise ModelManifestError(
                f"models[{index}].sha256 must be a lowercase SHA-256 digest"
            )

        relative_path = Path(values["relative_path"])
        if relative_path.is_absolute():
            raise ModelManifestError(
                f"models[{index}].relative_path must be relative"
            )
        artifact_path = (model_root / relative_path).resolve(strict=False)
        if not artifact_path.is_relative_to(model_root):
            raise ModelManifestError(
                f"models[{index}].relative_path resolves outside model_root"
            )

        return ModelEntry(
            model_id=values["model_id"],
            space_id=values["space_id"],
            modality=values["modality"],
            dimensions=dimensions,
            path=artifact_path,
            sha256=values["sha256"],
            license_name=values["license_name"],
            runtime=values["runtime"],
        )

    def require(self, model_id: str) -> ModelEntry:
        for entry in self.entries:
            if entry.model_id == model_id:
                return entry
        raise ModelManifestError(f"unknown model_id: {model_id}")
