#!/usr/bin/env python3
"""Build a compact, source-bound evidence snapshot for the final reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE_PATHS = {
    "retrieval": Path("docs/week4/evidence/retrieval-benchmark-summary.json"),
    "performance": Path("docs/week4/evidence/performance-summary.json"),
    "text_performance": Path("docs/week3/evidence/text-performance-summary.json"),
    "five_formats": Path("docs/week5/evidence/attachments/five-format-e2e.json"),
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"evidence source must be a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _measurement(data: dict[str, Any], batch_size: int) -> dict[str, Any]:
    measurements = data.get("measurements")
    if not isinstance(measurements, list):
        raise TypeError("text performance evidence requires measurements")
    for item in measurements:
        if isinstance(item, dict) and item.get("batch_size") == batch_size:
            return item
    raise ValueError(f"text performance evidence has no batch_size={batch_size}")


def build_report_evidence(
    *,
    repository: Path,
    manifest_path: Path,
    output_path: Path,
    github_status: str,
    video_status: str,
) -> dict[str, Any]:
    repository = repository.resolve()
    manifest_path = manifest_path.resolve()
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("repository HEAD must be a full lowercase commit")
    manifest = _load_json(manifest_path)
    if manifest.get("source_commit") != head:
        raise ValueError("delivery manifest source_commit does not match repository HEAD")

    loaded: dict[str, dict[str, Any]] = {}
    source_records = [
        {
            "name": "delivery_manifest",
            "path": str(manifest_path),
            "sha256": _sha256(manifest_path),
        }
    ]
    for name, relative_path in SOURCE_PATHS.items():
        path = repository / relative_path
        loaded[name] = _load_json(path)
        source_records.append(
            {
                "name": name,
                "path": relative_path.as_posix(),
                "sha256": _sha256(path),
            }
        )

    retrieval = loaded["retrieval"]
    performance = loaded["performance"]
    text_performance = loaded["text_performance"]
    batch1 = _measurement(text_performance, 1)
    batch16 = _measurement(text_performance, 16)
    five_formats = loaded["five_formats"]
    indexing = five_formats.get("indexing", {})
    indexing_result = indexing.get("result", {}) if isinstance(indexing, dict) else {}
    if not isinstance(indexing_result, dict):
        raise TypeError("five-format evidence requires indexing.result")

    try:
        search_p95 = float(retrieval["nq"]["query_latency"]["p95_ms"])
        target_p95 = float(performance["target"]["maximum_ms"])
        text_p50 = float(batch1["p50_latency_ms"])
        text_throughput = float(batch16["throughput_items_per_second"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("benchmark evidence is incomplete or non-numeric") from error

    evidence: dict[str, Any] = {
        "schema_version": 1,
        "source_commit": head,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tests": manifest.get("tests", {}),
        "platforms": manifest.get("platforms", {}),
        "external_gates": {
            "github": github_status,
            "video": video_status,
        },
        "benchmarks": {
            "search_p95_ms": search_p95,
            "target_p95_ms": target_p95,
            "text_batch1_p50_ms": text_p50,
            "text_batch16_throughput": text_throughput,
        },
        "five_formats": {
            "status": str(five_formats.get("status", "BLOCKED")),
            "parsed_files": int(indexing_result.get("parsed_files", 0)),
            "indexed_files": int(indexing_result.get("indexed_files", 0)),
        },
        "sources": source_records,
    }
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-status", default="BLOCKED：未配置可认证远程仓库")
    parser.add_argument("--video-status", default="BLOCKED：未完成真实五分钟录屏")
    args = parser.parse_args(argv)
    evidence = build_report_evidence(
        repository=args.repository,
        manifest_path=args.manifest,
        output_path=args.output,
        github_status=args.github_status,
        video_status=args.video_status,
    )
    print(
        json.dumps(
            {"output": str(args.output.resolve()), "source_commit": evidence["source_commit"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
