from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from zipfile import BadZipFile, ZipFile

Distribution = Literal["default-public", "research-only"]
RESEARCH_LICENSE = "Apple Machine Learning Research Model License"
RESEARCH_LICENSE_TEXT_MARKER = "Apple Machine Learning Research Model"
REQUIRED_LEGAL_FILES = (
    "app/LICENSE",
    "app/NOTICE",
    "app/THIRD_PARTY_NOTICES.md",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_member(archive: ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(archive.read(name).decode("utf-8"))
    except KeyError as error:
        raise ValueError(f"archive member is missing: {name}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"archive member is not valid UTF-8 JSON: {name}") from error
    if not isinstance(value, dict):
        raise TypeError(f"archive JSON member must be an object: {name}")
    return value


def validate_windows_archive(
    archive_path: Path | str,
    *,
    expected_commit: str,
    distribution: Distribution,
    size_limit_bytes: int,
) -> dict[str, Any]:
    path = Path(archive_path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"Windows archive is not a file: {path}")
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
        with ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename.replace("\\", "/") for info in infos]
            if len(names) != len(set(names)):
                raise ValueError("archive contains duplicate member paths")
            for name in names:
                member = PurePosixPath(name)
                if member.is_absolute() or ".." in member.parts:
                    raise ValueError(f"archive member path is unsafe: {name}")
            for legal_name in REQUIRED_LEGAL_FILES:
                if legal_name not in names:
                    raise ValueError(f"required legal file is missing: {legal_name}")
            if "app/frontend/content_retrieval_app.exe" not in names:
                raise ValueError("release frontend executable is missing")

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
            model_manifest = _json_member(
                archive,
                "app/models/model-manifest.json",
            )
            model_entries = model_manifest.get("models")
            if not isinstance(model_entries, list):
                raise TypeError("model manifest does not contain a models array")
            research_entries = [
                entry
                for entry in model_entries
                if isinstance(entry, dict)
                and entry.get("license_name") == RESEARCH_LICENSE
            ]

            if distribution == "default-public":
                if package_manifest.get("distribution_class") != "general":
                    raise ValueError(
                        "public package distribution class must be general"
                    )
                if research_entries or any(
                    name.startswith("app/models/mobileclip/")
                    or (
                        name.startswith("app/models/")
                        and name.endswith(".pt")
                    )
                    for name in names
                ):
                    raise ValueError(
                        "public package contains a research-only model"
                    )
            else:
                if package_manifest.get("distribution_class") != "research-only":
                    raise ValueError(
                        "research package distribution class must be research-only"
                    )
                if not research_entries:
                    raise ValueError(
                        "research package manifest lacks the restricted model"
                    )
                license_members = [
                    name
                    for name in names
                    if PurePosixPath(name).name.upper() in {
                        "LICENSE",
                        "LICENSE_MODELS",
                    }
                    and name.startswith("app/models/")
                ]
                if not any(
                    RESEARCH_LICENSE_TEXT_MARKER in archive.read(name).decode(
                        "utf-8",
                        errors="replace",
                    )
                    for name in license_members
                ):
                    raise ValueError(
                        "research package is missing the model license text"
                    )
    except BadZipFile as error:
        raise ValueError(f"Windows archive is not a valid ZIP: {path}") from error

    return {
        "schema_version": 1,
        "path": str(path),
        "source_commit": expected_commit,
        "distribution": distribution,
        "bytes": size_bytes,
        "sha256": _sha256_file(path),
        "member_count": len(names),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Week 8 Windows release archive."
    )
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument(
        "--distribution",
        required=True,
        choices=("default-public", "research-only"),
    )
    parser.add_argument("--size-limit-bytes", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_windows_archive(
        args.archive,
        expected_commit=args.expected_commit,
        distribution=args.distribution,
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
