from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_nq import (
    load_corpus,
    load_qrels,
    load_queries,
    rank_by_dot_product,
    retrieval_metrics,
)


def test_retrieval_metrics_compute_recall_mrr_and_ndcg() -> None:
    rankings = {
        "q1": ["d1", "d9", "d8"],
        "q2": ["d8", "d2", "d7"],
    }
    qrels = {"q1": {"d1"}, "q2": {"d2"}}

    metrics = retrieval_metrics(rankings, qrels, cutoffs=(1, 5, 10))

    assert metrics["recall@1"] == pytest.approx(0.5)
    assert metrics["recall@5"] == pytest.approx(1.0)
    assert metrics["recall@10"] == pytest.approx(1.0)
    assert metrics["mrr@10"] == pytest.approx(0.75)
    expected_ndcg = (1.0 + 1.0 / np.log2(3.0)) / 2.0
    assert metrics["ndcg@10"] == pytest.approx(expected_ndcg)


def test_retrieval_metrics_average_multi_relevant_recall() -> None:
    rankings = {"q1": ["d1", "d3", "d9"]}
    qrels = {"q1": {"d1", "d2", "d3"}}

    metrics = retrieval_metrics(rankings, qrels, cutoffs=(1, 2, 3))

    assert metrics["recall@1"] == pytest.approx(1 / 3)
    assert metrics["recall@2"] == pytest.approx(2 / 3)
    assert metrics["recall@3"] == pytest.approx(2 / 3)


def test_retrieval_metrics_require_rankings_for_all_qrels() -> None:
    with pytest.raises(ValueError, match="missing rankings"):
        retrieval_metrics({}, {"q1": {"d1"}})

    with pytest.raises(ValueError, match="relevant document"):
        retrieval_metrics({"q1": ["d1"]}, {"q1": set()})


def test_rank_by_dot_product_is_deterministic() -> None:
    queries = np.asarray([[1.0, 0.0], [0.0, 1.0]])
    corpus = np.asarray([[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]])

    rankings = rank_by_dot_product(
        query_ids=["q1", "q2"],
        query_embeddings=queries,
        doc_ids=["d1", "d2", "d3"],
        corpus_embeddings=corpus,
        limit=2,
    )

    assert rankings == {"q1": ["d1", "d2"], "q2": ["d3", "d2"]}


def test_loaders_validate_the_frozen_file_shapes(tmp_path: Path) -> None:
    queries_path = tmp_path / "queries.jsonl"
    corpus_path = tmp_path / "corpus.jsonl"
    qrels_path = tmp_path / "qrels.tsv"
    queries_path.write_text(
        json.dumps({"query_id": "q1", "text": "question"}) + "\n",
        encoding="utf-8",
    )
    corpus_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"doc_id": "d1", "title": "T", "text": "answer"}
                ),
                json.dumps({"doc_id": "d2", "title": "J", "text": ""}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    qrels_path.write_text(
        "query_id\tdoc_id\trelevance\nq1\td1\t1\n",
        encoding="utf-8",
    )

    assert load_queries(queries_path) == [("q1", "question")]
    assert load_corpus(corpus_path) == [
        ("d1", "T\nanswer"),
        ("d2", "J"),
    ]
    assert load_qrels(qrels_path) == {"q1": {"d1"}}
