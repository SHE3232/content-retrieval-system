#!/usr/bin/env python3
"""Verify Week 8 delivery hashes, evidence, archives, and distribution boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.week8.build_delivery_manifest import validate_manifest_data

RESTRICTED_PUBLIC_SUFFIXES = (
    ".ckpt",
    ".onnx",
    ".pt",
    ".pth",
    ".safetensors",
    ".tflite",
)
RESEARCH_REQUIRED_SUFFIXES = (
    "LICENSES/MOBILECLIP_MODEL_LICENSE.txt",
    "MODEL_CARD.md",
    "MODEL_MANIFEST.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_file(root: Path, relative_path: str, *, label: str) -> Path:
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"{label} path escapes root: {relative_path}")
    candidate = root.joinpath(*pure.parts)
    if candidate.is_symlink():
        raise ValueError(f"{label} path is a symbolic link: {relative_path}")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError(f"{label} file is missing or escapes root: {relative_path}")
    return resolved


def _embedded_commit(package: ZipFile, names: list[str]) -> str | None:
    candidates = [
        name
        for name in names
        if name.endswith(("CLEAN_SOURCE_MANIFEST.json", "PACKAGE_MANIFEST.json"))
    ]
    for name in candidates:
        try:
            payload = json.loads(package.read(name).decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        commit = payload.get("source_commit") if isinstance(payload, dict) else None
        if isinstance(commit, str):
            return commit
    return None


def _verify_zip(path: Path, artifact: dict[str, Any], source_commit: str) -> None:
    try:
        with ZipFile(path) as package:
            names = [name.replace("\\", "/") for name in package.namelist()]
            for name in names:
                pure = PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts:
                    raise ValueError(f"archive member escapes archive root: {name}")
            embedded_commit = _embedded_commit(package, names)
            if embedded_commit != source_commit:
                raise ValueError(
                    f"archive embedded source_commit mismatch: {path.name}"
                )
            distribution_class = artifact["distribution_class"]
            if distribution_class in {"public-source", "default-public"}:
                for name in names:
                    lowered = name.lower()
                    if lowered.endswith(RESTRICTED_PUBLIC_SUFFIXES) or "third_party/mobileclip-src/" in lowered:
                        raise ValueError(f"restricted public archive member: {name}")
            elif distribution_class == "research-only":
                missing = [
                    suffix
                    for suffix in RESEARCH_REQUIRED_SUFFIXES
                    if not any(name.endswith(suffix) for name in names)
                ]
                if missing:
                    raise ValueError(
                        "research archive missing required files: " + ", ".join(missing)
                    )
    except BadZipFile as error:
        raise ValueError(f"invalid ZIP archive: {path}") from error


def verify_delivery(
    repository: Path,
    delivery_root: Path,
    manifest_path: Path,
    *,
    require_all_platforms: bool = False,
) -> dict[str, object]:
    """Verify a complete or honestly blocked delivery manifest."""

    repository = repository.resolve()
    delivery_root = delivery_root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise TypeError("delivery manifest must be a JSON object")
    errors = validate_manifest_data(manifest)
    if errors:
        raise ValueError("invalid delivery manifest: " + "; ".join(errors))
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    if manifest["source_commit"] != head:
        raise ValueError("delivery manifest source_commit does not match repository HEAD")

    for gate in manifest["tests"].values():
        _safe_file(repository, gate["evidence_path"], label="test evidence")
    for platform, gate in manifest["platforms"].items():
        for evidence_path in gate["evidence_paths"]:
            _safe_file(repository, evidence_path, label=f"{platform} evidence")
    if require_all_platforms:
        incomplete = [
            platform
            for platform, gate in manifest["platforms"].items()
            if gate["status"] != "PASS"
        ]
        if incomplete:
            raise ValueError("platforms are not PASS: " + ", ".join(sorted(incomplete)))

    for artifact in manifest["artifacts"]:
        path = _safe_file(delivery_root, artifact["path"], label="artifact")
        if path.stat().st_size != artifact["bytes"]:
            raise ValueError(f"artifact byte count mismatch: {artifact['path']}")
        if _sha256(path) != artifact["sha256"]:
            raise ValueError(f"artifact SHA-256 mismatch: {artifact['path']}")
        if path.suffix.lower() == ".zip":
            _verify_zip(path, artifact, manifest["source_commit"])

    return {
        "status": "PASS",
        "source_commit": manifest["source_commit"],
        "artifact_count": len(manifest["artifacts"]),
        "platforms": {
            name: gate["status"] for name, gate in manifest["platforms"].items()
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--delivery-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--require-all-platforms", action="store_true")
    args = parser.parse_args(argv)
    report = verify_delivery(
        args.repository,
        args.delivery_root,
        args.manifest,
        require_all_platforms=args.require_all_platforms,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
