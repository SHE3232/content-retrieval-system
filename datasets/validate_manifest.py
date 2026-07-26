"""Validate the Week 1 local dataset manifest using only Python stdlib."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "datasets" / "manifest.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    with MANIFEST.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))

    missing: list[str] = []
    mismatches: list[str] = []
    hashes: dict[str, str] = {}

    for row in rows:
        item_id = row["id"]
        path = ROOT / Path(row["path"])
        if not path.is_file():
            missing.append(item_id)
            continue

        actual_hash = sha256(path)
        hashes[item_id] = actual_hash
        if actual_hash.lower() != row["sha256"].lower():
            mismatches.append(item_id)

    duplicate_pair_ok = (
        hashes.get("D004") is not None
        and hashes.get("D004") == hashes.get("D005")
    )

    print(f"FILES={len(rows)}")
    print(f"MISSING={len(missing)}")
    print(f"HASH_MISMATCH={len(mismatches)}")
    print(f"DUPLICATE_PAIR_OK={duplicate_pair_ok}")

    if missing:
        print("MISSING_IDS=" + ",".join(missing))
    if mismatches:
        print("HASH_MISMATCH_IDS=" + ",".join(mismatches))

    return 0 if not missing and not mismatches and duplicate_pair_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
