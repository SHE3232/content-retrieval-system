"""Build deterministic local retrieval splits from NQ-retrieval JSONL data."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_query_id(row: dict[str, Any]) -> str:
    key = f"{row['document_url']}\n{row['question']}".encode("utf-8")
    return "nq-" + hashlib.sha256(key).hexdigest()[:16]


def load_eligible(path: Path) -> list[dict[str, Any]]:
    selected_by_url: dict[str, dict[str, Any]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for source_row, line in enumerate(source):
            row = json.loads(line)
            candidates = row["candidates"]
            passage_types = row["passage_types"]
            answers = row["long_answers"]
            if not answers or len(candidates) != len(passage_types):
                continue
            if any(not isinstance(index, int) or index < 0 or index >= len(candidates) for index in answers):
                continue
            document_url = row["document_url"]
            if document_url in selected_by_url:
                continue
            row["source_row"] = source_row
            row["query_id"] = stable_query_id(row)
            selected_by_url[document_url] = row
    return sorted(selected_by_url.values(), key=lambda row: row["query_id"])


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_split(output_dir: Path, split: str, rows: list[dict[str, Any]]) -> None:
    split_dir = output_dir / split
    split_dir.mkdir(parents=True, exist_ok=True)

    queries: list[dict[str, Any]] = []
    corpus: list[dict[str, Any]] = []
    qrels: list[dict[str, Any]] = []
    for row in rows:
        query_id = row["query_id"]
        queries.append(
            {
                "query_id": query_id,
                "text": row["question"],
                "language": "en",
                "source": "sentence-transformers/NQ-retrieval",
            }
        )
        for index, (text, passage_type) in enumerate(
            zip(row["candidates"], row["passage_types"], strict=True)
        ):
            doc_id = f"{query_id}-p{index:04d}"
            corpus.append(
                {
                    "doc_id": doc_id,
                    "source_id": query_id,
                    "title": row["title"],
                    "text": text,
                    "passage_type": passage_type,
                    "document_url": row["document_url"],
                }
            )
        for index in sorted(set(row["long_answers"])):
            qrels.append(
                {
                    "query_id": query_id,
                    "doc_id": f"{query_id}-p{index:04d}",
                    "relevance": 1,
                }
            )

    write_jsonl(split_dir / "queries.jsonl", queries)
    write_jsonl(split_dir / "corpus.jsonl", corpus)
    with (split_dir / "qrels.tsv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(
            target, fieldnames=["query_id", "doc_id", "relevance"], delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(qrels)


def prepare(
    input_path: Path,
    output_dir: Path,
    split_manifest: Path,
    validation_size: int,
    benchmark_size: int,
) -> None:
    eligible = load_eligible(input_path)
    required = validation_size + benchmark_size
    if len(eligible) < required:
        raise ValueError(
            f"requested {required} examples but only {len(eligible)} eligible examples exist"
        )
    validation = eligible[:validation_size]
    benchmark = eligible[validation_size : validation_size + benchmark_size]

    write_split(output_dir, "validation", validation)
    write_split(output_dir, "benchmark", benchmark)

    split_manifest.parent.mkdir(parents=True, exist_ok=True)
    with split_manifest.open("w", encoding="utf-8", newline="") as target:
        fieldnames = [
            "query_id",
            "split",
            "source_row",
            "document_url",
            "question",
            "relevant_passages",
            "candidate_count",
        ]
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        for split, rows in (("validation", validation), ("benchmark", benchmark)):
            for row in rows:
                writer.writerow(
                    {
                        "query_id": row["query_id"],
                        "split": split,
                        "source_row": row["source_row"],
                        "document_url": row["document_url"],
                        "question": row["question"],
                        "relevant_passages": ";".join(
                            str(index) for index in sorted(set(row["long_answers"]))
                        ),
                        "candidate_count": len(row["candidates"]),
                    }
                )

    artifacts: dict[str, dict[str, Any]] = {}
    for artifact_path in sorted(output_dir.rglob("*")):
        if not artifact_path.is_file() or artifact_path.name == "metadata.json":
            continue
        relative_path = artifact_path.relative_to(output_dir).as_posix()
        artifacts[relative_path] = {
            "sha256": sha256_file(artifact_path),
            "bytes": artifact_path.stat().st_size,
        }

    metadata = {
        "dataset": "sentence-transformers/NQ-retrieval",
        "source_file": "dev.jsonl.gz",
        "source_url": (
            "https://huggingface.co/datasets/sentence-transformers/"
            "NQ-retrieval/resolve/main/dev.jsonl.gz"
        ),
        "source_sha256": sha256_file(input_path),
        "selection": "eligible unique document URLs sorted by stable SHA-256 query ID",
        "validation_queries": len(validation),
        "benchmark_queries": len(benchmark),
        "validation_passages": sum(len(row["candidates"]) for row in validation),
        "benchmark_passages": sum(len(row["candidates"]) for row in benchmark),
        "split_manifest": {
            "name": split_manifest.name,
            "sha256": sha256_file(split_manifest),
            "bytes": split_manifest.stat().st_size,
        },
        "artifacts": artifacts,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "metadata.json").open(
        "w", encoding="utf-8", newline="\n"
    ) as target:
        json.dump(metadata, target, ensure_ascii=False, indent=2)
        target.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--validation-size", type=int, default=160)
    parser.add_argument("--benchmark-size", type=int, default=40)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prepare(
        args.input,
        args.output_dir,
        args.split_manifest,
        args.validation_size,
        args.benchmark_size,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
