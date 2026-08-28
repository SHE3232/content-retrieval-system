#!/usr/bin/env python3
"""Export an allowlisted, Git-tracked public source tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path


def _matches(path: str, patterns: Sequence[str]) -> str | None:
    return next((pattern for pattern in patterns if fnmatchcase(path, pattern)), None)


def select_tracked_paths(
    tracked_paths: Iterable[str], profile: Mapping[str, Sequence[str]]
) -> tuple[list[str], dict[str, str]]:
    """Apply a root allowlist, explicit exclusions, and narrow allow overrides."""

    root_files = set(profile["include_root_files"])
    root_directories = set(profile["include_root_directories"])
    exclude_globs = profile["exclude_globs"]
    allow_globs = profile.get("allow_globs", [])
    selected: list[str] = []
    excluded: dict[str, str] = {}

    for raw_path in sorted(set(tracked_paths)):
        path = raw_path.replace("\\", "/")
        root = path.split("/", 1)[0]
        if path not in root_files and root not in root_directories:
            excluded[path] = "not-allowlisted"
            continue
        if _matches(path, allow_globs):
            selected.append(path)
            continue
        exclusion = _matches(path, exclude_globs)
        if exclusion:
            excluded[path] = f"excluded:{exclusion}"
            continue
        selected.append(path)

    return selected, excluded


def load_profile(path: Path) -> dict[str, object]:
    """Load and minimally validate the versioned clean-source policy."""

    profile = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or profile.get("schema_version") != 1:
        raise ValueError("delivery profile must use schema_version 1")
    for key in (
        "include_root_files",
        "include_root_directories",
        "exclude_globs",
        "allow_globs",
        "required_files",
    ):
        value = profile.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"delivery profile {key} must be a string list")
    return profile


def read_tracked_paths(repository: Path) -> list[str]:
    """Read exact unquoted tracked paths, including non-ASCII names, from Git."""

    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repository,
        capture_output=True,
        check=True,
    )
    return [
        raw.decode("utf-8").replace("\\", "/")
        for raw in completed.stdout.split(b"\0")
        if raw
    ]


def _git_output(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=repository, text=True
    ).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_source_file(repository: Path, relative_path: str) -> Path:
    repository = repository.resolve()
    candidate = repository / relative_path
    if candidate.is_symlink():
        raise ValueError(f"tracked source path is a symbolic link: {relative_path}")
    attributes = getattr(candidate.lstat(), "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if reparse_flag and attributes & reparse_flag:
        raise ValueError(f"tracked source path is a reparse point: {relative_path}")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(repository):
        raise ValueError(f"tracked source path escapes repository: {relative_path}")
    if not resolved.is_file():
        raise ValueError(f"tracked source file is missing: {relative_path}")
    return resolved


def _prepare_destination(destination: Path, *, repository: Path, policy_name: str) -> None:
    destination = destination.resolve()
    if destination == destination.anchor or destination.parent == destination:
        raise ValueError(f"unsafe clean-source destination: {destination}")
    if not destination.exists():
        destination.mkdir(parents=True)
        return
    if not destination.is_dir():
        raise ValueError(f"clean-source destination is not a directory: {destination}")
    children = list(destination.iterdir())
    if not children:
        return
    manifest_path = destination / "CLEAN_SOURCE_MANIFEST.json"
    try:
        owner = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(
            f"destination is not an owned clean-source directory: {destination}"
        ) from error
    if (
        owner.get("owned_by") != "week8-clean-source-exporter"
        or owner.get("source_repository") != str(repository.resolve())
        or owner.get("policy_name") != policy_name
    ):
        raise ValueError(f"destination is not an owned clean-source directory: {destination}")
    for child in children:
        resolved_child = child.resolve()
        if not resolved_child.is_relative_to(destination):
            raise ValueError(f"destination child escapes clean-source root: {child}")
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def export_clean_source(
    repository: Path, destination: Path, profile_path: Path
) -> dict[str, object]:
    """Export selected tracked files and persist a complete hash manifest."""

    repository = repository.resolve()
    destination = destination.resolve()
    profile_path = profile_path.resolve()
    profile = load_profile(profile_path)
    status = _git_output(repository, "status", "--porcelain", "--untracked-files=no")
    if status:
        raise ValueError("repository has tracked changes; clean-source export requires a clean tree")

    tracked = read_tracked_paths(repository)
    selected, excluded = select_tracked_paths(tracked, profile)
    required = set(profile["required_files"])
    missing = sorted(required.difference(selected))
    if missing:
        raise ValueError(f"clean-source required files are missing: {', '.join(missing)}")

    _prepare_destination(
        destination, repository=repository, policy_name=str(profile["name"])
    )
    files: list[dict[str, object]] = []
    for relative_path in selected:
        source = _safe_source_file(repository, relative_path)
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
        files.append(
            {
                "bytes": target.stat().st_size,
                "path": relative_path,
                "sha256": _sha256(target),
            }
        )

    exclusions_by_rule = dict(sorted(Counter(excluded.values()).items()))
    manifest: dict[str, object] = {
        "schema_version": 1,
        "owned_by": "week8-clean-source-exporter",
        "policy_name": profile["name"],
        "policy_sha256": _sha256(profile_path),
        "source_commit": _git_output(repository, "rev-parse", "HEAD"),
        "source_repository": str(repository),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "total_bytes": sum(int(item["bytes"]) for item in files),
        "required_files": sorted(required),
        "exclusions_by_rule": exclusions_by_rule,
        "excluded_files": [
            {"path": path, "reason": reason} for path, reason in sorted(excluded.items())
        ],
        "files": files,
    }
    (destination / "CLEAN_SOURCE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path(__file__).resolve().with_name("delivery_profile.json"),
    )
    args = parser.parse_args(argv)
    manifest = export_clean_source(args.repository, args.destination, args.profile)
    print(
        json.dumps(
            {
                "destination": str(args.destination.resolve()),
                "file_count": manifest["file_count"],
                "source_commit": manifest["source_commit"],
                "total_bytes": manifest["total_bytes"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
