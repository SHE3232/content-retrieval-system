#!/usr/bin/env python3
"""Validate direct evidence for the public GitHub v1.0.0 release."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

EXPECTED_REPOSITORY = "offline-accessible-multimodal-retrieval"
REQUIRED_ANONYMOUS_CHECKS = (
    "readme",
    "license",
    "tag",
    "release",
    "assets_downloadable",
)


def _manifest_hashes(manifest: dict[str, Any]) -> dict[str, str]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise TypeError("delivery manifest artifacts are missing")
    result: dict[str, str] = {}
    for artifact in artifacts:
        if isinstance(artifact, dict):
            path = str(artifact.get("path", ""))
            sha = str(artifact.get("sha256", ""))
            if path and re.fullmatch(r"[0-9a-f]{64}", sha):
                result[Path(path).name] = sha
    return result


def validate_github_evidence(
    evidence: dict[str, Any], manifest: dict[str, Any], *, source_commit: str
) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source_commit must be a full lowercase Git commit")
    if evidence.get("source_commit") != source_commit:
        raise ValueError("GitHub evidence is not bound to the frozen commit")
    if manifest.get("source_commit") != source_commit:
        raise ValueError("delivery manifest is not bound to the frozen commit")
    repository_url = str(evidence.get("repository_url", ""))
    if not re.fullmatch(
        rf"https://github\.com/[^/]+/{EXPECTED_REPOSITORY}", repository_url
    ):
        raise ValueError("unexpected or missing public repository URL")
    if evidence.get("tag") != "v1.0.0" or evidence.get("tag_commit") != source_commit:
        raise ValueError("v1.0.0 tag must point to the frozen commit")
    ci = evidence.get("ci")
    if not isinstance(ci, dict) or ci.get("commit") != source_commit:
        raise ValueError("CI evidence must identify the frozen commit")
    jobs = ci.get("jobs")
    if not isinstance(jobs, dict) or not jobs or any(value != "PASS" for value in jobs.values()):
        raise ValueError("every recorded CI job must pass")
    anonymous = evidence.get("anonymous_access")
    if not isinstance(anonymous, dict) or any(
        anonymous.get(name) is not True for name in REQUIRED_ANONYMOUS_CHECKS
    ):
        raise ValueError("anonymous repository and release checks are incomplete")

    expected_hashes = _manifest_hashes(manifest)
    assets = evidence.get("release_assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("release assets are missing")
    checked = 0
    for asset in assets:
        if not isinstance(asset, dict):
            raise TypeError("release asset evidence must be an object")
        name = str(asset.get("name", ""))
        sha = str(asset.get("sha256", ""))
        if "research" in name.casefold() or asset.get("distribution_class") != "public":
            raise ValueError("GitHub Release must not contain research-only assets")
        if expected_hashes.get(name) != sha:
            raise ValueError(f"release asset hash differs from delivery manifest: {name}")
        if asset.get("anonymous_download") is not True:
            raise ValueError(f"release asset lacks anonymous download evidence: {name}")
        checked += 1
    return {
        "schema_version": 1,
        "status": "PASS",
        "source_commit": source_commit,
        "repository_url": repository_url,
        "tag": "v1.0.0",
        "asset_count": checked,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--delivery-manifest", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    manifest = json.loads(args.delivery_manifest.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict) or not isinstance(manifest, dict):
        raise TypeError("GitHub evidence and delivery manifest must be JSON objects")
    result = validate_github_evidence(evidence, manifest, source_commit=args.source_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
