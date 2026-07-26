from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import time
from typing import Any

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_number} is not an object")
            rows.append(value)
    return rows


def load_queries(path: Path) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in _load_jsonl(path):
        query_id = row.get("query_id")
        text = row.get("text")
        if not isinstance(query_id, str) or not query_id:
            raise ValueError("query_id must be a non-empty string")
        if query_id in seen:
            raise ValueError(f"duplicate query_id: {query_id}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"query {query_id} has empty text")
        seen.add(query_id)
        queries.append((query_id, text.strip()))
    return queries


def load_corpus(path: Path) -> list[tuple[str, str]]:
    corpus: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in _load_jsonl(path):
        doc_id = row.get("doc_id")
        title = row.get("title")
        text = row.get("text")
        if not isinstance(doc_id, str) or not doc_id:
            raise ValueError("doc_id must be a non-empty string")
        if doc_id in seen:
            raise ValueError(f"duplicate doc_id: {doc_id}")
        if not isinstance(text, str):
            raise ValueError(f"document {doc_id} has invalid text")
        title_text = title.strip() if isinstance(title, str) else ""
        body_text = text.strip()
        if not title_text and not body_text:
            raise ValueError(f"document {doc_id} has no title or text")
        parts = []
        if title_text:
            parts.append(title_text)
        if body_text:
            parts.append(body_text)
        seen.add(doc_id)
        corpus.append((doc_id, "\n".join(parts)))
    return corpus


def load_qrels(path: Path) -> dict[str, set[str]]:
    qrels: dict[str, set[str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["query_id", "doc_id", "relevance"]:
            raise ValueError("qrels must contain query_id, doc_id, relevance")
        for row in reader:
            if int(row["relevance"]) > 0:
                qrels.setdefault(row["query_id"], set()).add(row["doc_id"])
    return qrels


def rank_by_dot_product(
    *,
    query_ids: list[str],
    query_embeddings: np.ndarray,
    doc_ids: list[str],
    corpus_embeddings: np.ndarray,
    limit: int,
) -> dict[str, list[str]]:
    queries = np.asarray(query_embeddings, dtype=np.float32)
    corpus = np.asarray(corpus_embeddings, dtype=np.float32)
    if queries.ndim != 2 or corpus.ndim != 2:
        raise ValueError("embeddings must be two-dimensional")
    if queries.shape[0] != len(query_ids):
        raise ValueError("query embedding count does not match query IDs")
    if corpus.shape[0] != len(doc_ids):
        raise ValueError("corpus embedding count does not match document IDs")
    if queries.shape[1] != corpus.shape[1]:
        raise ValueError("query and corpus embedding dimensions differ")
    if limit <= 0:
        raise ValueError("limit must be positive")

    scores = queries @ corpus.T
    ranked_indices = np.argsort(-scores, axis=1, kind="stable")[
        :, : min(limit, len(doc_ids))
    ]
    return {
        query_id: [doc_ids[int(index)] for index in indices]
        for query_id, indices in zip(query_ids, ranked_indices, strict=True)
    }


def retrieval_metrics(
    rankings: dict[str, list[str]],
    qrels: dict[str, set[str]],
    *,
    cutoffs: tuple[int, ...] = (1, 5, 10),
) -> dict[str, float]:
    if not qrels:
        raise ValueError("qrels must not be empty")
    if any(cutoff <= 0 for cutoff in cutoffs):
        raise ValueError("cutoffs must be positive")

    totals = {cutoff: 0.0 for cutoff in cutoffs}
    reciprocal_rank_total = 0.0
    ndcg_total = 0.0
    ndcg_cutoff = 10
    for query_id, relevant in qrels.items():
        if not relevant:
            raise ValueError(f"query {query_id} has no relevant document")
        if query_id not in rankings:
            raise ValueError(f"missing rankings for query {query_id}")
        ranked = rankings[query_id]
        for cutoff in cutoffs:
            hits = len(relevant.intersection(ranked[:cutoff]))
            totals[cutoff] += hits / len(relevant)

        relevant_ranks = [
            rank
            for rank, doc_id in enumerate(ranked[:ndcg_cutoff], start=1)
            if doc_id in relevant
        ]
        if relevant_ranks:
            reciprocal_rank_total += 1.0 / relevant_ranks[0]
        dcg = sum(1.0 / math.log2(rank + 1) for rank in relevant_ranks)
        ideal_hits = min(len(relevant), ndcg_cutoff)
        ideal_dcg = sum(
            1.0 / math.log2(rank + 1)
            for rank in range(1, ideal_hits + 1)
        )
        ndcg_total += dcg / ideal_dcg

    query_count = len(qrels)
    metrics = {
        f"recall@{cutoff}": totals[cutoff] / query_count
        for cutoff in cutoffs
    }
    metrics["mrr@10"] = reciprocal_rank_total / query_count
    metrics["ndcg@10"] = ndcg_total / query_count
    return metrics


def _encode(
    model: Any,
    texts: list[str],
    *,
    batch_size: int,
) -> np.ndarray:
    encoded = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    return np.asarray(encoded, dtype=np.float32)


def _relevant_ranks(
    rankings: dict[str, list[str]],
    qrels: dict[str, set[str]],
) -> dict[str, list[int]]:
    return {
        query_id: [
            rank
            for rank, doc_id in enumerate(
                rankings[query_id],
                start=1,
            )
            if doc_id in relevant
        ]
        for query_id, relevant in qrels.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a local text embedding model on frozen NQ data."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=REPOSITORY_ROOT / "datasets" / "processed" / "nq",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "models"
            / "text"
            / "text-multilingual-v1"
        ),
    )
    parser.add_argument(
        "--model-id",
        default="text-multilingual-v1",
    )
    parser.add_argument(
        "--split",
        choices=["validation", "benchmark"],
        default="benchmark",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "output" / "week3" / "nq-benchmark.json",
    )
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")

    from sentence_transformers import SentenceTransformer

    split_root = args.dataset_root.resolve(strict=True) / args.split
    queries = load_queries(split_root / "queries.jsonl")
    corpus = load_corpus(split_root / "corpus.jsonl")
    qrels = load_qrels(split_root / "qrels.tsv")
    model = SentenceTransformer(
        str(args.model.resolve(strict=True)),
        device="cpu",
        local_files_only=True,
    )

    started = time.perf_counter()
    query_embeddings = _encode(
        model,
        [text for _, text in queries],
        batch_size=args.batch_size,
    )
    corpus_embeddings = _encode(
        model,
        [text for _, text in corpus],
        batch_size=args.batch_size,
    )
    rankings = rank_by_dot_product(
        query_ids=[query_id for query_id, _ in queries],
        query_embeddings=query_embeddings,
        doc_ids=[doc_id for doc_id, _ in corpus],
        corpus_embeddings=corpus_embeddings,
        limit=min(10, len(corpus)),
    )
    elapsed_seconds = time.perf_counter() - started
    metrics = retrieval_metrics(rankings, qrels)
    payload = {
        "schema_version": "1",
        "dataset": "sentence-transformers/NQ-retrieval",
        "split": args.split,
        "frozen_test_split": args.split == "benchmark",
        "model_id": args.model_id,
        "space_id": "text-semantic-v1",
        "query_count": len(queries),
        "corpus_count": len(corpus),
        "dimensions": int(query_embeddings.shape[1]),
        "batch_size": args.batch_size,
        "elapsed_seconds": elapsed_seconds,
        "metrics": metrics,
        "relevant_ranks": _relevant_ranks(rankings, qrels),
    }
    destination = args.output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
