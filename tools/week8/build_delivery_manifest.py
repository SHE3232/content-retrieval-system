#!/usr/bin/env python3
"""Build and validate the unified Week 8 delivery manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GATE_STATUSES = frozenset({"PASS", "FAIL", "BLOCKED"})
PLATFORMS = ("windows", "linux", "macos")
DISTRIBUTION_CLASSES = frozenset(
    {"public-source", "default-public", "research-only"}
)


def validate_manifest_data(data: dict[str, Any]) -> list[str]:
    """Return all structural and semantic manifest errors."""

    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    commit = data.get("source_commit")
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        errors.append("source_commit must be a full lowercase Git commit")

    tests = data.get("tests")
    if not isinstance(tests, dict) or not tests:
        errors.append("tests must be a non-empty object")
    else:
        for name, gate in tests.items():
            prefix = f"tests.{name}"
            if not isinstance(gate, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if gate.get("status") not in GATE_STATUSES:
                errors.append(f"{prefix}.status must be PASS, FAIL, or BLOCKED")
            for count_name in ("passed", "skipped"):
                count = gate.get(count_name)
                if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                    errors.append(
                        f"{prefix}.{count_name} must be a non-negative integer"
                    )
            if not isinstance(gate.get("evidence_path"), str) or not gate["evidence_path"].strip():
                errors.append(f"{prefix}.evidence_path is required")

    platforms = data.get("platforms")
    if not isinstance(platforms, dict):
        errors.append("platforms must be an object")
    else:
        for platform in PLATFORMS:
            gate = platforms.get(platform)
            prefix = f"platforms.{platform}"
            if not isinstance(gate, dict):
                errors.append(f"{prefix} is required")
                continue
            status = gate.get("status")
            if status not in GATE_STATUSES:
                errors.append(f"{prefix}.status must be PASS, FAIL, or BLOCKED")
            evidence_paths = gate.get("evidence_paths")
            if not isinstance(evidence_paths, list) or not all(
                isinstance(path, str) and path.strip() for path in evidence_paths
            ):
                errors.append(f"{prefix}.evidence_paths must be a non-empty string list")
            if status == "PASS" and not evidence_paths:
                errors.append(f"{prefix} PASS requires evidence_paths")
            if status in {"FAIL", "BLOCKED"} and not (
                isinstance(gate.get("reason"), str) and gate["reason"].strip()
            ):
                errors.append(f"{prefix}.{status} requires reason")

    distributions = data.get("distributions")
    if not isinstance(distributions, dict) or not distributions:
        errors.append("distributions must be a non-empty object")
    else:
        for name, distribution in distributions.items():
            prefix = f"distributions.{name}"
            if not isinstance(distribution, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if distribution.get("distribution_class") not in DISTRIBUTION_CLASSES:
                errors.append(f"{prefix}.distribution_class is invalid")
            if not isinstance(distribution.get("model_policy"), str) or not distribution[
                "model_policy"
            ].strip():
                errors.append(f"{prefix}.model_policy is required")

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("artifacts must be a list")
    else:
        for index, artifact in enumerate(artifacts):
            prefix = f"artifacts[{index}]"
            if not isinstance(artifact, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if not isinstance(artifact.get("path"), str) or not artifact["path"].strip():
                errors.append(f"{prefix}.path is required")
            size = artifact.get("bytes")
            if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
                errors.append(f"{prefix}.bytes must be a positive integer")
            digest = artifact.get("sha256")
            if not isinstance(digest, str) or not SHA256.fullmatch(digest):
                errors.append(
                    f"{prefix}.sha256 must be 64 lowercase hexadecimal characters"
                )
            if artifact.get("distribution_class") not in DISTRIBUTION_CLASSES:
                errors.append(f"{prefix}.distribution_class is invalid")
            if not isinstance(artifact.get("provenance"), str) or not artifact[
                "provenance"
            ].strip():
                errors.append(f"{prefix}.provenance is required")
    return errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_file(delivery_root: Path, relative_path: str) -> Path:
    pure_path = PurePosixPath(relative_path)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        raise ValueError(f"artifact path must stay below delivery root: {relative_path}")
    candidate = delivery_root.joinpath(*pure_path.parts)
    if candidate.is_symlink():
        raise ValueError(f"artifact path must not be a symbolic link: {relative_path}")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(delivery_root.resolve()) or not resolved.is_file():
        raise ValueError(f"artifact file is missing or escapes delivery root: {relative_path}")
    return resolved


def build_manifest(
    repository: Path, evidence_path: Path, delivery_root: Path
) -> dict[str, Any]:
    """Build a validated manifest by hashing every evidence-declared artifact."""

    repository = repository.resolve()
    delivery_root = delivery_root.resolve()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict):
        raise TypeError("delivery evidence must be a JSON object")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    if evidence.get("source_commit") != head:
        raise ValueError("delivery evidence source_commit does not match repository HEAD")
    manifest = deepcopy(evidence)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    artifacts: list[dict[str, Any]] = []
    for declaration in evidence.get("artifacts", []):
        if not isinstance(declaration, dict):
            raise TypeError("artifact declaration must be an object")
        relative_path = declaration.get("path")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("artifact declaration path is required")
        artifact = _artifact_file(delivery_root, relative_path)
        artifacts.append(
            {
                "path": relative_path,
                "bytes": artifact.stat().st_size,
                "sha256": _sha256(artifact),
                "distribution_class": declaration.get("distribution_class"),
                "provenance": declaration.get("provenance"),
            }
        )
    manifest["artifacts"] = artifacts
    errors = validate_manifest_data(manifest)
    if errors:
        raise ValueError("invalid delivery manifest: " + "; ".join(errors))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--delivery-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    delivery_root = args.delivery_root.resolve()
    if not output.is_relative_to(delivery_root):
        raise ValueError("manifest output must stay below delivery root")
    manifest = build_manifest(args.repository, args.evidence, delivery_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "artifact_count": len(manifest["artifacts"]),
                "output": str(output),
                "source_commit": manifest["source_commit"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
