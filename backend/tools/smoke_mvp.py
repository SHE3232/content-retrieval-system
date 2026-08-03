from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any

import httpx


REQUIRED_SUFFIXES = {".txt", ".pdf", ".docx", ".jpg", ".png"}
PENDING_JOB_STATUSES = {"queued", "running"}


@dataclass(frozen=True, slots=True)
class SmokeQueries:
    keyword: str
    text_semantic: str
    image_semantic: str


def _require_formats(input_root: Path) -> list[str]:
    suffixes = {
        path.suffix.lower()
        for path in input_root.rglob("*")
        if path.is_file()
    }
    missing = sorted(REQUIRED_SUFFIXES - suffixes)
    if missing:
        raise ValueError("input root is missing formats: " + ", ".join(missing))
    return sorted(suffix[1:].upper() for suffix in REQUIRED_SUFFIXES)


def _request_json(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as error:
        raise RuntimeError("API returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError("API returned a non-object JSON payload")
    return payload


def _integer_field(payload: dict[str, Any], field: str, context: str) -> int:
    try:
        value = payload[field]
    except KeyError as error:
        raise RuntimeError(f"{context} is missing {field}") from error
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"{context} has invalid {field}")
    return value


def _record_count(payload: dict[str, Any], context: str) -> int:
    count = _integer_field(payload, "record_count", context)
    if count < 0:
        raise RuntimeError(f"{context} has invalid record_count")
    return count


def _require_job_result(job: dict[str, Any]) -> dict[str, Any]:
    result = job.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("indexing job returned no result object")
    failed_files = _integer_field(result, "failed_files", "indexing result")
    partial_files = _integer_field(result, "partial_files", "indexing result")
    if failed_files:
        raise RuntimeError("indexing smoke contains failed files")
    if partial_files:
        raise RuntimeError("indexing smoke contains partial files")
    return result


def _search_checks(queries: SmokeQueries) -> list[tuple[str, str, list[str], dict[str, object] | None, str | None]]:
    return [
        ("keyword", queries.keyword, ["keyword"], None, None),
        (
            "text_semantic",
            queries.text_semantic,
            ["text_semantic"],
            None,
            None,
        ),
        (
            "image_semantic",
            queries.image_semantic,
            ["image_semantic"],
            None,
            None,
        ),
        (
            "hybrid",
            queries.text_semantic,
            ["keyword", "text_semantic", "image_semantic"],
            None,
            None,
        ),
        (
            "filtered_image",
            queries.image_semantic,
            ["image_semantic"],
            {"modalities": ["image"]},
            "image",
        ),
    ]


def _validate_hits(
    payload: dict[str, Any],
    *,
    check_name: str,
    expected_modality: str | None,
) -> list[dict[str, Any]]:
    hits = payload.get("hits")
    if not isinstance(hits, list) or not hits:
        raise RuntimeError(f"{check_name} search returned no hits")
    if any(not isinstance(hit, dict) for hit in hits):
        raise RuntimeError(f"{check_name} search returned malformed hits")
    typed_hits: list[dict[str, Any]] = hits
    if expected_modality is not None and any(
        hit.get("modality") != expected_modality for hit in typed_hits
    ):
        raise RuntimeError(f"{check_name} search violated its modality filter")
    first = typed_hits[0]
    if not isinstance(first.get("name"), str) or not first["name"].strip():
        raise RuntimeError(f"{check_name} search returned a malformed top hit")
    reasons = first.get("match_reasons")
    if not isinstance(reasons, list) or not reasons:
        raise RuntimeError(f"{check_name} search returned malformed match reasons")
    elapsed_ms = payload.get("elapsed_ms")
    if isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, (int, float)):
        raise RuntimeError(f"{check_name} search returned invalid elapsed_ms")
    return typed_hits


def run_smoke(
    client: httpx.Client,
    *,
    input_root: Path,
    queries: SmokeQueries,
    require_existing_index: bool = False,
    timeout_seconds: float = 180.0,
    poll_interval_seconds: float = 0.25,
) -> dict[str, object]:
    if timeout_seconds < 0:
        raise ValueError("timeout_seconds must be non-negative")
    if poll_interval_seconds < 0:
        raise ValueError("poll_interval_seconds must be non-negative")

    root = input_root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("input root must be a directory")
    formats = _require_formats(root)

    before = _request_json(client.get("/v1/index/stats"))
    pre_index_records = _record_count(before, "pre-index stats")
    if require_existing_index and pre_index_records <= 0:
        raise RuntimeError("no records existed before indexing after restart")

    created = _request_json(
        client.post(
            "/v1/indexing/jobs",
            json={
                "paths": [str(root)],
                "authorized_roots": [str(root)],
                "recursive": True,
            },
        )
    )
    job_id = created.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        raise RuntimeError("indexing job creation returned an invalid job_id")

    deadline = time.monotonic() + timeout_seconds
    while True:
        job = _request_json(client.get(f"/v1/indexing/jobs/{job_id}"))
        job_status = job.get("status")
        if not isinstance(job_status, str):
            raise RuntimeError("indexing job returned an invalid status")
        if job_status not in PENDING_JOB_STATUSES:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"indexing job {job_id} did not finish")
        time.sleep(poll_interval_seconds)

    if job_status == "failed":
        raise RuntimeError(f"indexing job ended as {job_status}")
    if job_status not in {"completed", "completed_with_errors"}:
        raise RuntimeError(f"indexing job ended as {job_status}")
    result = _require_job_result(job)
    if job_status != "completed":
        raise RuntimeError(f"indexing job ended as {job_status}")

    searches: list[dict[str, object]] = []
    for name, query, channels, filters, expected_modality in _search_checks(queries):
        request_payload: dict[str, object] = {
            "query": query,
            "top_k": 5,
            "channels": channels,
        }
        if filters is not None:
            request_payload["filters"] = filters
        payload = _request_json(client.post("/v1/search", json=request_payload))
        hits = _validate_hits(
            payload,
            check_name=name,
            expected_modality=expected_modality,
        )
        searches.append(
            {
                "name": name,
                "query": query,
                "channels": channels,
                "top_hit": hits[0]["name"],
                "match_reasons": hits[0]["match_reasons"],
                "elapsed_ms": payload["elapsed_ms"],
                "passed": True,
            }
        )

    after = _request_json(client.get("/v1/index/stats"))
    if _record_count(after, "post-index stats") <= 0:
        raise RuntimeError("post-index stats contained no records")
    return {
        "schema_version": "1",
        "status": "passed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "formats": formats,
        "pre_index_record_count": pre_index_records,
        "indexing": result,
        "stats": after,
        "searches": searches,
        "persistent_restart": {
            "required": require_existing_index,
            "passed": require_existing_index and pre_index_records > 0,
        },
    }


def _write_json_atomically(output: Path, evidence: dict[str, object]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(output)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the running MVP API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--keyword-query", required=True)
    parser.add_argument("--text-query", required=True)
    parser.add_argument("--image-query", required=True)
    parser.add_argument("--require-existing-index", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    with httpx.Client(
        base_url=args.base_url,
        timeout=30.0,
        trust_env=False,
    ) as client:
        evidence = run_smoke(
            client,
            input_root=args.input_root,
            queries=SmokeQueries(
                keyword=args.keyword_query,
                text_semantic=args.text_query,
                image_semantic=args.image_query,
            ),
            require_existing_index=args.require_existing_index,
        )
    _write_json_atomically(args.output, evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
