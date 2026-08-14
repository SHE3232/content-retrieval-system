#!/usr/bin/env python3
"""Run a deterministic 10k-record Chroma stress and soak acceptance gate."""

from __future__ import annotations

import argparse
import csv
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import tempfile
import time
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SOURCE = REPOSITORY_ROOT / "backend" / "src"
if str(BACKEND_SOURCE) not in sys.path:
    sys.path.insert(0, str(BACKEND_SOURCE))


def current_process_rss() -> int:
    """Return this process's resident working set without third-party packages."""
    if os.name == "nt":
        from ctypes import wintypes

        size_t = ctypes.c_size_t

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", size_t),
                ("WorkingSetSize", size_t),
                ("QuotaPeakPagedPoolUsage", size_t),
                ("QuotaPagedPoolUsage", size_t),
                ("QuotaPeakNonPagedPoolUsage", size_t),
                ("QuotaNonPagedPoolUsage", size_t),
                ("PagefileUsage", size_t),
                ("PeakPagefileUsage", size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.restype = wintypes.HANDLE
        get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        get_memory_info.restype = wintypes.BOOL
        handle = get_current_process()
        succeeded = get_memory_info(
            handle,
            ctypes.byref(counters),
            counters.cb,
        )
        if not succeeded:
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        return int(counters.WorkingSetSize)

    import resource

    maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return maximum if os.uname().sysname == "Darwin" else maximum * 1024


def percentile(values: Iterable[float], percent: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    position = (len(ordered) - 1) * percent / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def dataset_manifest_hash(*, seed: int, records: int, dimensions: int) -> str:
    payload = json.dumps(
        {
            "algorithm": "python-random-v1",
            "dimensions": dimensions,
            "records": records,
            "seed": seed,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _check(identifier: str, passed: bool, actual: Any, expected: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "status": "PASS" if passed else "FAIL",
        "actual": actual,
        "expected": expected,
    }


def assess_stress(
    *,
    record_count: int,
    requested_queries: int,
    completed_queries: int,
    soak_seconds: float,
    query_p95_ms: float,
    first_window_rss_median: float,
    last_window_rss_median: float,
    crashes: int,
    deadlocks: int,
    unhandled_exceptions: int,
    malformed_responses: int,
) -> dict[str, Any]:
    rss_limit = first_window_rss_median * 1.10
    checks = [
        _check("record_count", record_count >= 10_000, record_count, ">= 10000"),
        _check(
            "query_count",
            requested_queries >= 500 and completed_queries == requested_queries,
            {"requested": requested_queries, "completed": completed_queries},
            "requested >= 500 and completed == requested",
        ),
        _check("soak_duration", soak_seconds >= 1800, soak_seconds, ">= 1800 seconds"),
        _check("query_p95", query_p95_ms <= 2000, query_p95_ms, "<= 2000 ms"),
        _check(
            "rss_growth",
            last_window_rss_median <= rss_limit,
            {
                "first_window_median": first_window_rss_median,
                "last_window_median": last_window_rss_median,
                "limit": rss_limit,
            },
            "last five-minute median <= 110% of first stable five-minute median",
        ),
        _check(
            "process_stability",
            crashes == 0 and deadlocks == 0,
            {"crashes": crashes, "deadlocks": deadlocks},
            "0 crashes and 0 deadlocks",
        ),
        _check("exception_count", unhandled_exceptions == 0, unhandled_exceptions, "0"),
        _check("response_shape", malformed_responses == 0, malformed_responses, "0"),
    ]
    return {
        "status": "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL",
        "checks": checks,
    }


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _normalized_vector(seed: int, index: int, dimensions: int) -> list[float]:
    generator = random.Random((seed << 32) ^ index)
    values = [generator.uniform(-1.0, 1.0) for _ in range(dimensions)]
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values]


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _records(seed: int, count: int, dimensions: int):
    from content_retrieval.domain.models import EmbeddingVector
    from content_retrieval.domain.retrieval import IndexRecord

    modified_at = datetime(2026, 8, 14, tzinfo=timezone.utc)
    root = Path.cwd().resolve() / "week6-stress-fixtures"
    for index in range(count):
        source_id = _sha(f"week6-stress-record:{seed}:{index}")
        file_id = _sha(f"week6-stress-file:{seed}:{index // 4}")
        source_key = _sha(f"week6-stress-source:{seed}:{index // 4}")
        vector = EmbeddingVector(
            source_id=source_id,
            file_id=file_id,
            model_id="week6-deterministic-stress-v1",
            space_id=f"week6-stress-{dimensions}",
            modality="text",
            values=_normalized_vector(seed, index, dimensions),
            dimensions=dimensions,
            normalized=True,
        )
        yield IndexRecord(
            record_id=source_id,
            source_id=source_id,
            file_id=file_id,
            source_key=source_key,
            path=root / f"fixture-{index // 4:05d}.txt",
            name=f"fixture-{index // 4:05d}.txt",
            mime_type="text/plain" if index % 2 == 0 else "application/pdf",
            modality="text",
            document=f"deterministic local stress record {index}",
            vector=vector,
            modified_at=modified_at,
            size_bytes=128,
            paragraph_number=(index % 4) + 1,
            sequence_number=index % 4,
        )


def _batches(values: Iterable[Any], size: int) -> Iterable[list[Any]]:
    batch: list[Any] = []
    for value in values:
        batch.append(value)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(args: argparse.Namespace) -> dict[str, Any]:
    from content_retrieval.domain.models import EmbeddingVector
    from content_retrieval.domain.retrieval import SearchFilters
    from content_retrieval.storage.chroma import ChromaVectorRepository

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    query_csv = output / "query-samples.csv"
    resource_csv = output / "resource-samples.csv"
    started_at = datetime.now(timezone.utc)
    errors: list[str] = []
    malformed = 0
    deadlocks = 0
    crashes = 0
    latencies: list[float] = []
    resources: list[tuple[float, float, float]] = []
    last_cpu_time = time.process_time()
    last_cpu_sample = time.monotonic()

    def sample_process() -> tuple[float, float]:
        nonlocal last_cpu_time, last_cpu_sample
        now = time.monotonic()
        cpu_time = time.process_time()
        elapsed = max(now - last_cpu_sample, 1e-9)
        cpu_percent = max(0.0, (cpu_time - last_cpu_time) / elapsed * 100.0)
        last_cpu_time = cpu_time
        last_cpu_sample = now
        return float(current_process_rss()), cpu_percent

    with ChromaVectorRepository(args.database) as repository:
        repository.clear()
        for batch in _batches(_records(args.seed, args.records, args.dimensions), args.batch_size):
            repository.upsert(batch)
        actual_records = repository.count()

        with query_csv.open("w", encoding="utf-8", newline="") as query_stream, resource_csv.open(
            "w", encoding="utf-8", newline=""
        ) as resource_stream:
            query_writer = csv.DictWriter(
                query_stream,
                fieldnames=["query_index", "elapsed_seconds", "latency_ms", "result_count", "filter"],
            )
            resource_writer = csv.DictWriter(
                resource_stream,
                fieldnames=["elapsed_seconds", "rss_bytes", "cpu_percent", "queue_length", "errors"],
            )
            query_writer.writeheader()
            resource_writer.writeheader()
            start = time.monotonic()
            next_sample = start
            interval = args.soak_seconds / max(args.queries, 1)
            for index in range(args.queries):
                target = start + index * interval
                while time.monotonic() < target:
                    now = time.monotonic()
                    if now >= next_sample:
                        elapsed = now - start
                        rss, cpu = sample_process()
                        resources.append((elapsed, rss, cpu))
                        resource_writer.writerow(
                            {
                                "elapsed_seconds": f"{elapsed:.6f}",
                                "rss_bytes": int(rss),
                                "cpu_percent": f"{cpu:.3f}",
                                "queue_length": 0,
                                "errors": len(errors),
                            }
                        )
                        next_sample += args.sample_interval
                    time.sleep(min(0.05, max(0.0, target - time.monotonic())))

                values = _normalized_vector(args.seed, index % actual_records, args.dimensions)
                vector = EmbeddingVector(
                    source_id=_sha(f"week6-stress-query:{args.seed}:{index}"),
                    file_id=_sha(f"week6-stress-query-file:{args.seed}:{index}"),
                    model_id="week6-deterministic-stress-v1",
                    space_id=f"week6-stress-{args.dimensions}",
                    modality="text",
                    values=values,
                    dimensions=args.dimensions,
                    normalized=True,
                )
                filter_name = ("none", "text/plain", "application/pdf")[index % 3]
                filters = (
                    SearchFilters()
                    if filter_name == "none"
                    else SearchFilters(mime_types=(filter_name,))
                )
                query_started = time.perf_counter()
                try:
                    hits = repository.query(vector, limit=10, filters=filters)
                    latency_ms = (time.perf_counter() - query_started) * 1000
                    if latency_ms > args.deadlock_seconds * 1000:
                        deadlocks += 1
                    if not isinstance(hits, list) or any(not hasattr(hit, "score") for hit in hits):
                        malformed += 1
                    latencies.append(latency_ms)
                    query_writer.writerow(
                        {
                            "query_index": index,
                            "elapsed_seconds": f"{time.monotonic() - start:.6f}",
                            "latency_ms": f"{latency_ms:.6f}",
                            "result_count": len(hits),
                            "filter": filter_name,
                        }
                    )
                except Exception as error:  # evidence captures the full failed session
                    errors.append(f"query {index}: {type(error).__name__}: {error}")

            while time.monotonic() - start < args.soak_seconds:
                now = time.monotonic()
                if now >= next_sample:
                    elapsed = now - start
                    rss, cpu = sample_process()
                    resources.append((elapsed, rss, cpu))
                    resource_writer.writerow(
                        {
                            "elapsed_seconds": f"{elapsed:.6f}",
                            "rss_bytes": int(rss),
                            "cpu_percent": f"{cpu:.3f}",
                            "queue_length": 0,
                            "errors": len(errors),
                        }
                    )
                    next_sample += args.sample_interval
                time.sleep(0.05)
            actual_soak = time.monotonic() - start

    if not resources:
        rss = float(current_process_rss())
        resources.append((0.0, rss, 0.0))
    first_window = [rss for elapsed, rss, _ in resources if elapsed <= min(300.0, actual_soak)]
    last_start = max(0.0, actual_soak - 300.0)
    last_window = [rss for elapsed, rss, _ in resources if elapsed >= last_start]
    p95 = percentile(latencies, 95) if latencies else float("inf")
    assessment = assess_stress(
        record_count=actual_records,
        requested_queries=args.queries,
        completed_queries=len(latencies),
        soak_seconds=actual_soak,
        query_p95_ms=p95,
        first_window_rss_median=statistics.median(first_window),
        last_window_rss_median=statistics.median(last_window),
        crashes=crashes,
        deadlocks=deadlocks,
        unhandled_exceptions=len(errors),
        malformed_responses=malformed,
    )
    finished_at = datetime.now(timezone.utc)
    return {
        **assessment,
        "generated_at": finished_at.isoformat(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "configuration": {
            "seed": args.seed,
            "records": args.records,
            "queries": args.queries,
            "soak_seconds": args.soak_seconds,
            "dimensions": args.dimensions,
            "batch_size": args.batch_size,
            "sample_interval": args.sample_interval,
        },
        "dataset_manifest_sha256": dataset_manifest_hash(
            seed=args.seed, records=args.records, dimensions=args.dimensions
        ),
        "metrics": {
            "record_count": actual_records,
            "completed_queries": len(latencies),
            "query_p50_ms": percentile(latencies, 50) if latencies else None,
            "query_p95_ms": p95 if latencies else None,
            "query_max_ms": max(latencies) if latencies else None,
            "soak_seconds": actual_soak,
            "first_window_rss_median_bytes": statistics.median(first_window),
            "last_window_rss_median_bytes": statistics.median(last_window),
            "peak_rss_bytes": max(rss for _, rss, _ in resources),
            "unhandled_exceptions": len(errors),
            "malformed_responses": malformed,
            "deadlocks": deadlocks,
            "crashes": crashes,
        },
        "errors": errors,
        "evidence": {
            "query_samples": {"path": query_csv.name, "sha256": _sha256_file(query_csv)},
            "resource_samples": {"path": resource_csv.name, "sha256": _sha256_file(resource_csv)},
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--records", type=int, default=10_000)
    parser.add_argument("--queries", type=int, default=500)
    parser.add_argument("--soak-seconds", type=float, default=1800)
    parser.add_argument("--dimensions", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--deadlock-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run(args)
    except BaseException as error:
        result = {
            "status": "FAIL",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": f"{type(error).__name__}: {error}",
        }
        write_json_atomic(args.output / "summary.json", result)
        raise
    write_json_atomic(args.output / "summary.json", result)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
