from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

RESEARCH_LICENSE = "Apple Machine Learning Research Model License"
REQUIRED_FILES = (
    "app/LICENSE",
    "app/NOTICE",
    "app/THIRD_PARTY_NOTICES.md",
    "app/PACKAGE_MANIFEST.json",
    "app/models/model-manifest.json",
    "app/frontend/content_retrieval_app",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_member(archive: tarfile.TarFile, name: str) -> dict[str, Any]:
    member = archive.getmember(name)
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"archive member is not a regular file: {name}")
    try:
        value = json.loads(stream.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"archive member is not valid UTF-8 JSON: {name}") from error
    if not isinstance(value, dict):
        raise TypeError(f"archive JSON member must be an object: {name}")
    return value


def validate_linux_archive(
    archive_path: Path | str,
    *,
    expected_commit: str,
    size_limit_bytes: int,
) -> dict[str, Any]:
    path = Path(archive_path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"Linux archive is not a file: {path}")
    if len(expected_commit) != 40 or any(
        character not in "0123456789abcdef" for character in expected_commit
    ):
        raise ValueError("expected commit must be a full lowercase SHA-1 hash")
    if size_limit_bytes <= 0:
        raise ValueError("size limit must be positive")
    size_bytes = path.stat().st_size
    if size_bytes >= size_limit_bytes:
        raise ValueError(
            "archive must remain below the strict size limit: "
            f"{size_bytes} >= {size_limit_bytes}"
        )

    try:
        with tarfile.open(path, "r:*") as archive:
            members = archive.getmembers()
            names = [member.name.removeprefix("./") for member in members]
            if len(names) != len(set(names)):
                raise ValueError("archive contains duplicate member paths")
            for member, name in zip(members, names, strict=True):
                candidate = PurePosixPath(name)
                if candidate.is_absolute() or ".." in candidate.parts:
                    raise ValueError(f"archive member path is unsafe: {name}")
                if member.issym() or member.islnk() or member.isdev():
                    raise ValueError(
                        f"archive contains a link or device member: {name}"
                    )
            for required in REQUIRED_FILES:
                if required not in names:
                    raise ValueError(f"required release file is missing: {required}")
            frontend = archive.getmember("app/frontend/content_retrieval_app")
            if not frontend.isfile() or frontend.mode & 0o111 == 0:
                raise ValueError("Linux release frontend is not executable")

            package_manifest = _json_member(
                archive,
                "app/PACKAGE_MANIFEST.json",
            )
            actual_commit = package_manifest.get("source_commit")
            if actual_commit != expected_commit:
                raise ValueError(
                    "source commit mismatch: "
                    f"expected {expected_commit}, got {actual_commit}"
                )
            if package_manifest.get("distribution_class") != "general":
                raise ValueError("Linux public package must use general distribution")
            model_manifest = _json_member(
                archive,
                "app/models/model-manifest.json",
            )
            models = model_manifest.get("models")
            if not isinstance(models, list):
                raise TypeError("model manifest does not contain a models array")
            if any(
                isinstance(model, dict)
                and model.get("license_name") == RESEARCH_LICENSE
                for model in models
            ) or any(
                name.startswith("app/models/mobileclip/")
                or (name.startswith("app/models/") and name.endswith(".pt"))
                for name in names
            ):
                raise ValueError("Linux public package contains a research-only model")
            if any(".cache" in PurePosixPath(name).parts for name in names):
                raise ValueError("Linux public package contains a download cache")
    except (tarfile.TarError, KeyError) as error:
        raise ValueError(f"Linux archive is invalid: {path}") from error

    return {
        "schema_version": 1,
        "path": str(path),
        "source_commit": expected_commit,
        "distribution": "default-public",
        "bytes": size_bytes,
        "sha256": _sha256_file(path),
        "member_count": len(names),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Week 8 Linux release archive."
    )
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--size-limit-bytes", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_linux_archive(
        args.archive,
        expected_commit=args.expected_commit,
        size_limit_bytes=args.size_limit_bytes,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
