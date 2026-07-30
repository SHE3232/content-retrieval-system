from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Iterable, Sequence

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SOURCE = REPOSITORY_ROOT / "backend" / "src"
if str(BACKEND_SOURCE) not in sys.path:
    sys.path.insert(0, str(BACKEND_SOURCE))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from content_retrieval.domain.models import EmbeddingVector
from content_retrieval.domain.retrieval import IndexRecord
from content_retrieval.retrieval.service import RetrievalService
from content_retrieval.runtime import LocalRuntime, build_local_runtime
from content_retrieval.storage.chroma import ChromaVectorRepository


FIXED_TIME = datetime(2026, 7, 30, tzinfo=timezone.utc)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path.name}:{line_number} is not an object")
            rows.append(row)
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def source_hashes(paths: Iterable[Path]) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for path in paths:
        resolved = Path(path).resolve(strict=True)
        results[resolved.name] = {
            "bytes": resolved.stat().st_size,
            "sha256": _sha256_file(resolved),
        }
    return results


def normalize_rows(values: Sequence[Sequence[float]]) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError("vectors must be two-dimensional")
    if not np.isfinite(array).all():
        raise ValueError("vectors must contain only finite values")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if np.any(norms == 0.0):
        raise ValueError("cannot normalize a zero vector")
    return array / norms


def retrieval_metrics(
    rankings: dict[str, list[str]],
    qrels: dict[str, set[str]],
    *,
    cutoffs: tuple[int, ...] = (1, 5, 10),
) -> dict[str, float]:
    if not qrels:
        raise ValueError("qrels must not be empty")
    totals = {cutoff: 0.0 for cutoff in cutoffs}
    reciprocal_rank = 0.0
    ndcg = 0.0
    first_ranks: list[int] = []
    for query_id, relevant in qrels.items():
        if not relevant:
            raise ValueError(f"query {query_id} has no relevant item")
        ranked = rankings.get(query_id)
        if ranked is None:
            raise ValueError(f"missing ranking for query {query_id}")
        relevant_ranks = [
            rank
            for rank, item_id in enumerate(ranked, start=1)
            if item_id in relevant
        ]
        first_rank = relevant_ranks[0] if relevant_ranks else len(ranked) + 1
        first_ranks.append(first_rank)
        for cutoff in cutoffs:
            totals[cutoff] += (
                len(relevant.intersection(ranked[:cutoff]))
                / len(relevant)
            )
        top_ten = [rank for rank in relevant_ranks if rank <= 10]
        if top_ten:
            reciprocal_rank += 1.0 / top_ten[0]
        dcg = sum(1.0 / math.log2(rank + 1) for rank in top_ten)
        ideal_hits = min(len(relevant), 10)
        ideal_dcg = sum(
            1.0 / math.log2(rank + 1)
            for rank in range(1, ideal_hits + 1)
        )
        ndcg += dcg / ideal_dcg

    count = len(qrels)
    result = {
        f"recall@{cutoff}": totals[cutoff] / count
        for cutoff in cutoffs
    }
    result["mrr@10"] = reciprocal_rank / count
    result["ndcg@10"] = ndcg / count
    result["median_rank"] = float(statistics.median(first_ranks))
    return result


def _linear_percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (
        ordered[upper] - ordered[lower]
    ) * fraction


def latency_summary(values: Sequence[float]) -> dict[str, float | int]:
    latencies = [float(value) for value in values]
    if not latencies:
        raise ValueError("latencies must not be empty")
    if any(not math.isfinite(value) or value < 0 for value in latencies):
        raise ValueError("latencies must be finite and non-negative")
    return {
        "query_count": len(latencies),
        "p50_ms": _linear_percentile(latencies, 0.50),
        "p95_ms": _linear_percentile(latencies, 0.95),
        "max_ms": max(latencies),
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)


def _stable_digest(namespace: str, identity: str) -> str:
    return hashlib.sha256(
        f"{namespace}\0{identity}".encode("utf-8")
    ).hexdigest()


def _record(
    *,
    namespace: str,
    identity: str,
    document: str,
    values: Sequence[float],
    model_id: str,
    space_id: str,
    modality: str,
    virtual_root: Path,
    mime_type: str,
    suffix: str,
) -> IndexRecord:
    file_id = _stable_digest(namespace, identity)
    source_id = _stable_digest(f"{namespace}-source", identity)
    path = (virtual_root / f"{file_id}{suffix}").resolve()
    vector = EmbeddingVector(
        source_id=source_id,
        file_id=file_id,
        model_id=model_id,
        space_id=space_id,
        modality=modality,
        values=[float(value) for value in values],
        dimensions=len(values),
        normalized=True,
        metadata={"benchmark_identity": identity},
    )
    return IndexRecord(
        record_id=source_id,
        source_id=source_id,
        file_id=file_id,
        source_key=_stable_digest("source-key", str(path)),
        path=path,
        name=f"{file_id}{suffix}",
        mime_type=mime_type,
        modality=modality,
        document=document,
        vector=vector,
        modified_at=FIXED_TIME,
        size_bytes=len(document.encode("utf-8")),
        paragraph_number=1 if modality == "text" else None,
    )


def _batched(values: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _encode_texts(
    backend: Any,
    texts: list[str],
    *,
    batch_size: int,
) -> np.ndarray:
    rows: list[list[float]] = []
    for batch in _batched(texts, batch_size):
        rows.extend(backend.encode(list(batch)))
    return normalize_rows(rows)


def _encode_images(
    backend: Any,
    paths: list[Path],
    *,
    batch_size: int,
) -> np.ndarray:
    rows: list[list[float]] = []
    for batch in _batched(paths, batch_size):
        rows.extend(backend.encode_images(list(batch)))
    return normalize_rows(rows)


def _upsert_batched(
    repository: ChromaVectorRepository,
    records: list[IndexRecord],
    *,
    batch_size: int = 500,
) -> int:
    return sum(
        repository.upsert(batch)
        for batch in _batched(records, batch_size)
    )


def _load_qrels(path: Path) -> dict[str, set[str]]:
    qrels: dict[str, set[str]] = {}
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if reader.fieldnames != ["query_id", "doc_id", "relevance"]:
            raise ValueError("invalid NQ qrels header")
        for row in reader:
            if int(row["relevance"]) > 0:
                qrels.setdefault(row["query_id"], set()).add(row["doc_id"])
    return qrels


def _tika_version() -> str | None:
    try:
        import httpx

        with httpx.Client(
            timeout=2.0,
            trust_env=False,
        ) as client:
            response = client.get("http://127.0.0.1:9998/version")
            response.raise_for_status()
            return response.text.strip()
    except Exception:
        return None


def run_smoke(runtime: LocalRuntime) -> dict[str, Any]:
    runtime.repository.clear()
    fixtures = [
        REPOSITORY_ROOT / "datasets" / "smoke" / "text" / "zh_local_search.txt",
        REPOSITORY_ROOT
        / "Software Engineering Project Offline Accessible Multimodal Local Content Retrieval System.pdf",
        REPOSITORY_ROOT / "对项目的总理解和每周任务安排.docx",
        REPOSITORY_ROOT / "datasets" / "smoke" / "image" / "jpg_with_exif.jpg",
        REPOSITORY_ROOT
        / "frontend"
        / "macos"
        / "Runner"
        / "Assets.xcassets"
        / "AppIcon.appiconset"
        / "app_icon_512.png",
    ]
    resolved = [path.resolve(strict=True) for path in fixtures]
    started = time.perf_counter()
    result = runtime.indexing_service.index_paths(
        resolved,
        authorized_roots=[REPOSITORY_ROOT],
    )
    runtime.retrieval_service.refresh()
    searches = [
        (
            "keyword",
            "没有互联网连接",
            ("keyword",),
            "zh_local_search.txt",
        ),
        (
            "text_semantic",
            "offline system for searching private documents",
            ("text_semantic",),
            None,
        ),
        (
            "image_semantic",
            "a blue geometric logo on a white rounded square",
            ("image_semantic",),
            "app_icon_512.png",
        ),
    ]
    outcomes = []
    for name, query, channels, expected_name in searches:
        search_result = runtime.retrieval_service.search(
            query,
            top_k=5,
            channels=channels,
        )
        top_hit = search_result.hits[0] if search_result.hits else None
        passed = top_hit is not None and (
            expected_name is None or top_hit.name == expected_name
        )
        outcomes.append(
            {
                "name": name,
                "query": query,
                "channels": list(channels),
                "top_hit": top_hit.name if top_hit else None,
                "top_score": top_hit.score if top_hit else None,
                "match_reasons": (
                    list(top_hit.match_reasons) if top_hit else []
                ),
                "elapsed_ms": search_result.elapsed_ms,
                "passed": passed,
            }
        )

    restarted_repository = ChromaVectorRepository(
        runtime.repository.database_path
    )
    restarted_retrieval = RetrievalService(
        repository=restarted_repository,
        embedding_service=runtime.embedding_service,
    )
    repeated = restarted_retrieval.search(
        "没有互联网连接",
        top_k=5,
        channels=("keyword",),
    )
    restart_passed = (
        restarted_repository.count() == runtime.repository.count()
        and bool(repeated.hits)
        and repeated.hits[0].name == "zh_local_search.txt"
    )
    passed = (
        result.indexed_files == 5
        and result.failed_files == 0
        and all(item["passed"] for item in outcomes)
        and restart_passed
    )
    return {
        "schema_version": "1",
        "status": "passed" if passed else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline_mode": {
            "HF_HUB_OFFLINE": os.environ["HF_HUB_OFFLINE"],
            "TRANSFORMERS_OFFLINE": os.environ["TRANSFORMERS_OFFLINE"],
            "tika_version": _tika_version(),
        },
        "fixture_count": len(resolved),
        "formats": ["TXT", "PDF", "DOCX", "JPG", "PNG"],
        "fixtures": source_hashes(resolved),
        "indexing": {
            "parsed_files": result.parsed_files,
            "indexed_files": result.indexed_files,
            "indexed_records": result.indexed_records,
            "failed_files": result.failed_files,
            "partial_files": result.partial_files,
            "record_count": runtime.repository.count(),
            "failures": [
                {
                    "name": failure.path.name,
                    "code": failure.code,
                    "stage": failure.stage,
                    "message": failure.message,
                }
                for failure in result.failures
            ],
        },
        "searches": outcomes,
        "persistent_restart": {
            "record_count": restarted_repository.count(),
            "top_hit": repeated.hits[0].name if repeated.hits else None,
            "passed": restart_passed,
        },
        "elapsed_seconds": time.perf_counter() - started,
        "models": [
            {
                "model_id": entry.model_id,
                "space_id": entry.space_id,
                "sha256": entry.sha256,
            }
            for entry in runtime.manifest.entries
        ],
    }


def _nq_benchmark(
    runtime: LocalRuntime,
    repository: ChromaVectorRepository,
    *,
    batch_size: int,
) -> dict[str, Any]:
    root = REPOSITORY_ROOT / "datasets" / "processed" / "nq" / "benchmark"
    corpus_path = root / "corpus.jsonl"
    queries_path = root / "queries.jsonl"
    qrels_path = root / "qrels.tsv"
    corpus = _load_jsonl(corpus_path)
    queries = _load_jsonl(queries_path)
    qrels = _load_qrels(qrels_path)
    texts = [
        "\n".join(
            part
            for part in (
                str(row.get("title", "")).strip(),
                str(row.get("text", "")).strip(),
            )
            if part
        )
        for row in corpus
    ]
    started = time.perf_counter()
    embeddings = _encode_texts(
        runtime.text_engine.backend,
        texts,
        batch_size=batch_size,
    )
    virtual_root = repository.database_path.parent / "virtual-nq"
    records = [
        _record(
            namespace="nq",
            identity=str(row["doc_id"]),
            document=text,
            values=vector,
            model_id=runtime.text_engine.backend.model_id,
            space_id=runtime.text_engine.backend.space_id,
            modality="text",
            virtual_root=virtual_root,
            mime_type="text/plain",
            suffix=".txt",
        )
        for row, text, vector in zip(
            corpus,
            texts,
            embeddings,
            strict=True,
        )
    ]
    _upsert_batched(repository, records)
    retrieval = RetrievalService(
        repository=repository,
        embedding_service=runtime.embedding_service,
    )
    identity_by_file_id = {
        record.file_id: str(row["doc_id"])
        for record, row in zip(records, corpus, strict=True)
    }
    rankings: dict[str, list[str]] = {}
    latencies = []
    ranking_depth = min(100, len(records))
    for query in queries:
        result = retrieval.search(
            str(query["text"]),
            top_k=ranking_depth,
            channels=("text_semantic",),
        )
        rankings[str(query["query_id"])] = [
            identity_by_file_id[hit.file_id] for hit in result.hits
        ]
        latencies.append(result.elapsed_ms)
    return {
        "dataset": "sentence-transformers/NQ-retrieval",
        "split": "benchmark",
        "frozen_test_split": True,
        "query_count": len(queries),
        "collection_size": len(records),
        "ranking_depth": ranking_depth,
        "unretrieved_rank": ranking_depth + 1,
        "model_id": runtime.text_engine.backend.model_id,
        "space_id": runtime.text_engine.backend.space_id,
        "dimensions": runtime.text_engine.backend.dimensions,
        "source_hashes": source_hashes(
            [corpus_path, queries_path, qrels_path]
        ),
        "metrics": retrieval_metrics(rankings, qrels),
        "query_latency": latency_summary(latencies),
        "elapsed_seconds": time.perf_counter() - started,
    }


def _coco_benchmark(
    runtime: LocalRuntime,
    repository: ChromaVectorRepository,
    *,
    batch_size: int,
) -> dict[str, Any]:
    items_path = (
        REPOSITORY_ROOT
        / "datasets"
        / "processed"
        / "coco"
        / "benchmark"
        / "items.jsonl"
    )
    image_root = (
        REPOSITORY_ROOT / "datasets" / "raw" / "coco" / "val2017"
    )
    items = _load_jsonl(items_path)
    paths = [
        (image_root / str(item["file_name"])).resolve(strict=True)
        for item in items
    ]
    started = time.perf_counter()
    embeddings = _encode_images(
        runtime.image_engine.backend,
        paths,
        batch_size=batch_size,
    )
    records = [
        _record(
            namespace="coco",
            identity=str(item["image_id"]),
            document=str(item["file_name"]),
            values=vector,
            model_id=runtime.image_engine.backend.model_id,
            space_id=runtime.image_engine.backend.space_id,
            modality="image",
            virtual_root=image_root,
            mime_type="image/jpeg",
            suffix=".jpg",
        )
        for item, vector in zip(items, embeddings, strict=True)
    ]
    _upsert_batched(repository, records)
    retrieval = RetrievalService(
        repository=repository,
        embedding_service=runtime.embedding_service,
    )
    identity_by_file_id = {
        record.file_id: str(item["image_id"])
        for record, item in zip(records, items, strict=True)
    }
    rankings: dict[str, list[str]] = {}
    qrels: dict[str, set[str]] = {}
    latencies = []
    caption_index = 0
    ranking_depth = min(100, len(records))
    for item in items:
        for caption in item["captions"]:
            query_id = f"caption-{caption_index:04d}"
            result = retrieval.search(
                str(caption),
                top_k=ranking_depth,
                channels=("image_semantic",),
            )
            rankings[query_id] = [
                identity_by_file_id[hit.file_id] for hit in result.hits
            ]
            qrels[query_id] = {str(item["image_id"])}
            latencies.append(result.elapsed_ms)
            caption_index += 1
    return {
        "dataset": "COCO 2017 validation",
        "split": "benchmark",
        "frozen_test_split": True,
        "query_count": caption_index,
        "collection_size": len(records),
        "ranking_depth": ranking_depth,
        "unretrieved_rank": ranking_depth + 1,
        "model_id": runtime.image_engine.backend.model_id,
        "space_id": runtime.image_engine.backend.space_id,
        "dimensions": runtime.image_engine.backend.dimensions,
        "source_hashes": {
            **source_hashes([items_path]),
            "images": {
                "count": len(paths),
                "total_bytes": sum(path.stat().st_size for path in paths),
                "manifest_sha256": hashlib.sha256(
                    "".join(
                        f"{path.name}:{_sha256_file(path)}\n"
                        for path in paths
                    ).encode("utf-8")
                ).hexdigest(),
            },
        },
        "metrics": retrieval_metrics(rankings, qrels),
        "query_latency": latency_summary(latencies),
        "elapsed_seconds": time.perf_counter() - started,
    }


def run_retrieval_benchmarks(
    runtime: LocalRuntime,
    database_path: Path,
    *,
    text_batch_size: int,
    image_batch_size: int,
) -> dict[str, Any]:
    repository = ChromaVectorRepository(database_path)
    repository.clear()
    nq = _nq_benchmark(
        runtime,
        repository,
        batch_size=text_batch_size,
    )
    coco = _coco_benchmark(
        runtime,
        repository,
        batch_size=image_batch_size,
    )
    return {
        "schema_version": "1",
        "status": "passed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "storage": "ChromaDB persistent cosine collections",
        "retrieval_path": "RetrievalService",
        "total_collection_size": repository.count(),
        "nq": nq,
        "coco": coco,
    }


def _dependency_versions() -> dict[str, str]:
    packages = (
        "chromadb",
        "mobileclip",
        "numpy",
        "sentence-transformers",
        "torch",
        "torchvision",
        "transformers",
    )
    return {
        package: importlib.metadata.version(package)
        for package in packages
    }


def run_performance(
    runtime: LocalRuntime,
    database_path: Path,
    *,
    record_count: int,
    query_count: int,
) -> dict[str, Any]:
    if record_count < 10_000:
        raise ValueError("record_count must be at least 10,000")
    if query_count < 50:
        raise ValueError("query_count must be at least 50")
    repository = ChromaVectorRepository(database_path)
    repository.clear()
    dimensions = runtime.text_engine.backend.dimensions
    random = np.random.default_rng(20260730)
    vectors = normalize_rows(
        random.standard_normal(
            (record_count, dimensions),
            dtype=np.float32,
        )
    )
    virtual_root = repository.database_path.parent / "virtual-performance"
    started = time.perf_counter()
    records = [
        _record(
            namespace="performance",
            identity=f"record-{index:05d}",
            document=f"Synthetic performance record {index:05d}",
            values=vector,
            model_id=runtime.text_engine.backend.model_id,
            space_id=runtime.text_engine.backend.space_id,
            modality="text",
            virtual_root=virtual_root,
            mime_type="text/plain",
            suffix=".txt",
        )
        for index, vector in enumerate(vectors)
    ]
    _upsert_batched(repository, records)
    indexing_seconds = time.perf_counter() - started
    retrieval = RetrievalService(
        repository=repository,
        embedding_service=runtime.embedding_service,
    )
    for index in range(5):
        retrieval.search(
            f"warm local query {index}",
            top_k=10,
            channels=("text_semantic",),
        )
    latencies = [
        retrieval.search(
            f"offline performance query {index}",
            top_k=10,
            channels=("text_semantic",),
        ).elapsed_ms
        for index in range(query_count)
    ]
    summary = latency_summary(latencies)
    passed = summary["p95_ms"] <= 2000.0
    import torch

    return {
        "schema_version": "1",
        "status": "passed" if passed else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": repository.count(),
        "query_count": query_count,
        "warmup_query_count": 5,
        "seed": 20260730,
        "dimensions": dimensions,
        "model_id": runtime.text_engine.backend.model_id,
        "space_id": runtime.text_engine.backend.space_id,
        "indexing_seconds": indexing_seconds,
        "latency": summary,
        "target": {
            "metric": "p95_ms",
            "maximum_ms": 2000.0,
            "passed": passed,
        },
        "device": {
            "type": "cpu",
            "processor": platform.processor(),
            "platform": platform.platform(),
            "torch_cuda_available": torch.cuda.is_available(),
            "torch_version": torch.__version__,
        },
        "dependencies": _dependency_versions(),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the complete offline Week 4 retrieval verification."
    )
    parser.add_argument(
        "--mode",
        choices=["all", "smoke", "benchmark", "performance"],
        default="all",
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=REPOSITORY_ROOT / "models",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPOSITORY_ROOT / "models" / "model-manifest.json",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=REPOSITORY_ROOT / "output" / "week4" / "runtime-data",
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=REPOSITORY_ROOT / "docs" / "week4" / "evidence",
    )
    parser.add_argument("--text-batch-size", type=int, default=32)
    parser.add_argument("--image-batch-size", type=int, default=8)
    parser.add_argument("--synthetic-record-count", type=int, default=10_000)
    parser.add_argument("--performance-query-count", type=int, default=50)
    return parser


def main() -> int:
    args = _parser().parse_args()
    runtime = build_local_runtime(
        model_root=args.model_root,
        manifest_path=args.manifest,
        data_dir=args.data_root / "smoke",
        text_batch_size=args.text_batch_size,
        image_batch_size=args.image_batch_size,
    )
    statuses = []
    if args.mode in {"all", "smoke"}:
        smoke = run_smoke(runtime)
        _atomic_json(args.evidence_root / "e2e-summary.json", smoke)
        statuses.append(smoke["status"])
    if args.mode in {"all", "benchmark"}:
        benchmark = run_retrieval_benchmarks(
            runtime,
            args.data_root / "benchmark",
            text_batch_size=args.text_batch_size,
            image_batch_size=args.image_batch_size,
        )
        _atomic_json(
            args.evidence_root / "retrieval-benchmark-summary.json",
            benchmark,
        )
        statuses.append(benchmark["status"])
    if args.mode in {"all", "performance"}:
        performance = run_performance(
            runtime,
            args.data_root / "performance",
            record_count=args.synthetic_record_count,
            query_count=args.performance_query_count,
        )
        _atomic_json(
            args.evidence_root / "performance-summary.json",
            performance,
        )
        statuses.append(performance["status"])
    print(
        json.dumps(
            {
                "mode": args.mode,
                "statuses": statuses,
                "evidence_root": str(args.evidence_root.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(status == "passed" for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
