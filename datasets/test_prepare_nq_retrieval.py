from __future__ import annotations

import csv
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "datasets" / "prepare_nq_retrieval.py"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


class PrepareNqRetrievalTest(unittest.TestCase):
    def test_cli_builds_leak_free_retrieval_splits(self) -> None:
        rows = [
            {
                "question": "question one",
                "title": "Doc One",
                "candidates": ["one zero", "one relevant"],
                "passage_types": ["Text", "Text"],
                "long_answers": [1],
                "document_url": "https://example.test/doc-one",
            },
            {
                "question": "question two",
                "title": "Doc Two",
                "candidates": ["two relevant"],
                "passage_types": ["Text"],
                "long_answers": [0],
                "document_url": "https://example.test/doc-two",
            },
            {
                "question": "question three",
                "title": "Doc Three",
                "candidates": ["three zero", "three relevant"],
                "passage_types": ["Text", "Text"],
                "long_answers": [1],
                "document_url": "https://example.test/doc-three",
            },
            {
                "question": "no answer",
                "title": "Doc Four",
                "candidates": ["irrelevant"],
                "passage_types": ["Text"],
                "long_answers": [],
                "document_url": "https://example.test/doc-four",
            },
            {
                "question": "duplicate document",
                "title": "Doc One",
                "candidates": ["duplicate relevant"],
                "passage_types": ["Text"],
                "long_answers": [0],
                "document_url": "https://example.test/doc-one",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "source.jsonl.gz"
            output_dir = temp / "processed"
            split_manifest = temp / "split.csv"
            with gzip.open(source_path, "wt", encoding="utf-8") as target:
                for row in rows:
                    target.write(json.dumps(row) + "\n")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(source_path),
                    "--output-dir",
                    str(output_dir),
                    "--split-manifest",
                    str(split_manifest),
                    "--validation-size",
                    "2",
                    "--benchmark-size",
                    "1",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            validation_queries = read_jsonl(output_dir / "validation" / "queries.jsonl")
            benchmark_queries = read_jsonl(output_dir / "benchmark" / "queries.jsonl")
            self.assertEqual(len(validation_queries), 2)
            self.assertEqual(len(benchmark_queries), 1)

            with split_manifest.open(encoding="utf-8", newline="") as source:
                manifest_rows = list(csv.DictReader(source))
            self.assertEqual(len(manifest_rows), 3)
            self.assertEqual(len({row["document_url"] for row in manifest_rows}), 3)

            for split in ("validation", "benchmark"):
                corpus = read_jsonl(output_dir / split / "corpus.jsonl")
                corpus_ids = {str(row["doc_id"]) for row in corpus}
                with (output_dir / split / "qrels.tsv").open(
                    encoding="utf-8", newline=""
                ) as source:
                    qrels = list(csv.DictReader(source, delimiter="\t"))
                self.assertTrue(qrels)
                self.assertTrue(all(row["doc_id"] in corpus_ids for row in qrels))

            metadata_path = output_dir / "metadata.json"
            self.assertTrue(metadata_path.is_file())
            with metadata_path.open(encoding="utf-8") as source:
                metadata = json.load(source)
            self.assertEqual(metadata["validation_queries"], 2)
            self.assertEqual(metadata["benchmark_queries"], 1)
            self.assertEqual(len(metadata["source_sha256"]), 64)
            for relative_path, details in metadata["artifacts"].items():
                artifact_path = output_dir / relative_path
                digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
                self.assertEqual(details["sha256"], digest)
                self.assertEqual(details["bytes"], artifact_path.stat().st_size)

    def test_cli_rejects_insufficient_eligible_examples(self) -> None:
        row = {
            "question": "only question",
            "title": "Only Doc",
            "candidates": ["only relevant"],
            "passage_types": ["Text"],
            "long_answers": [0],
            "document_url": "https://example.test/only",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "source.jsonl.gz"
            with gzip.open(source_path, "wt", encoding="utf-8") as target:
                target.write(json.dumps(row) + "\n")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(source_path),
                    "--output-dir",
                    str(temp / "processed"),
                    "--split-manifest",
                    str(temp / "split.csv"),
                    "--validation-size",
                    "2",
                    "--benchmark-size",
                    "1",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("eligible", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
