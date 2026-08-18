from __future__ import annotations

import hashlib
import inspect
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from tools.week6.validate_evidence import (
    REQUIRED_DELIVERABLES,
    REQUIRED_GATES,
    validate_evidence,
)


SOURCE_COMMIT = "a" * 40


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _performance_metrics() -> dict[str, object]:
    baseline_medians = {
        "embedding_combined_p95_ms": 100.0,
        "vector_query_p95_ms": 100.0,
        "embedding_hot_p95_ms": 100.0,
        "vector_query_hot_p95_ms": 100.0,
        "peak_rss_bytes": 1_000_000_000.0,
        "full_search_p95_ms": 200.0,
    }
    candidate_medians = {key: value * 0.94 for key, value in baseline_medians.items()}
    accuracy_checks = {
        key: {
            "status": "PASS",
            "baseline": value,
            "candidate": value,
            "drop": 0.0,
            "maximum_drop": 0.01,
        }
        for key, value in {
            "nq_recall_at_10": 0.60,
            "nq_mrr_at_10": 0.30,
            "nq_ndcg_at_10": 0.36,
            "coco_recall_at_10": 1.0,
            "coco_mrr_at_10": 0.95,
            "coco_ndcg_at_10": 0.96,
        }.items()
    }
    return {
        "status": "PASS",
        "baseline_commit": "b" * 40,
        "candidate_commit": SOURCE_COMMIT,
        "baseline_medians": baseline_medians,
        "candidate_medians": candidate_medians,
        "improvements_percent": {key: 6.0 for key in baseline_medians},
        "workload": {
            "workload_sha256": "c" * 64,
            "workload_mode": "mixed-cold-and-cache-hit",
            "unique_queries": 20,
            "target_cache_hit_ratio": 0.8,
            "warmup_inputs_disjoint": True,
        },
        "accuracy_checks": accuracy_checks,
        "checks": [{"id": "comparison", "status": "PASS"}],
    }


def _write_complete_tree(root: Path) -> Path:
    proof = root / "attachments" / "proof.txt"
    proof.parent.mkdir(parents=True, exist_ok=True)
    proof.write_text("verified\n", encoding="utf-8")
    generated_at = datetime.now(timezone.utc).isoformat()

    gates = []
    for gate_id in REQUIRED_GATES:
        gate: dict[str, object] = {
            "gate_id": gate_id,
            "status": "PASS",
            "source_commit": SOURCE_COMMIT,
            "generated_at": generated_at,
            "command": f"verify {gate_id}",
            "exit_code": 0,
            "evidence": [
                {
                    "path": "attachments/proof.txt",
                    "sha256": _sha256(proof),
                }
            ],
        }
        if gate_id == "G3":
            gate["metrics"] = {"statement_coverage": 90.0}
        if gate_id == "G6":
            gate["metrics"] = _performance_metrics()
        if gate_id == "G8":
            gate["metrics"] = {
                "network_isolation": {
                    "enforced": True,
                    "method": "process-network-deny",
                    "sample_seconds": 1800,
                },
                "checks": {
                    "offline_e2e": "PASS",
                    "non_loopback_connections": "PASS",
                    "path_traversal": "PASS",
                    "reparse_point_escape": "PASS",
                    "package_audit": "PASS",
                },
            }
        gates.append(gate)

    deliverables = []
    for deliverable_id in REQUIRED_DELIVERABLES:
        artifact = root / "deliverables" / f"{deliverable_id}.bin"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(deliverable_id.encode("utf-8"))
        deliverables.append(
            {
                "deliverable_id": deliverable_id,
                "path": artifact.relative_to(root).as_posix(),
                "sha256": _sha256(artifact),
                "source_commit": SOURCE_COMMIT,
            }
        )

    sums = root / "deliverables" / "SHA256SUMS.txt"
    sums.write_text(
        "".join(
            f"{item['sha256']}  {Path(item['path']).name}\n" for item in deliverables
        ),
        encoding="utf-8",
    )
    stable = next(item for item in deliverables if item["deliverable_id"] == "stable_build")
    (root / "deliverables" / "SOURCE_VERSION.txt").write_text(
        f"source_commit={SOURCE_COMMIT}\npackage_sha256={stable['sha256']}\n",
        encoding="utf-8",
    )

    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project": "Local Multimodal Content Retrieval System",
                "source_commit": SOURCE_COMMIT,
                "gates": gates,
                "deliverables": deliverables,
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _gate(manifest: dict[str, object], gate_id: str) -> dict[str, object]:
    gates = manifest["gates"]
    assert isinstance(gates, list)
    return next(gate for gate in gates if gate["gate_id"] == gate_id)


def test_complete_manifest_passes_strict_validation(tmp_path: Path) -> None:
    _write_complete_tree(tmp_path)

    result = validate_evidence(tmp_path)

    assert result.exit_code == 0
    assert result.summary_status == "PASS"
    assert result.passed_gates == len(REQUIRED_GATES)
    assert result.errors == ()


def test_missing_and_duplicate_gates_fail(tmp_path: Path) -> None:
    manifest_path = _write_complete_tree(tmp_path)
    manifest = _load(manifest_path)
    gates = manifest["gates"]
    assert isinstance(gates, list)
    gates.pop()
    gates.append(dict(gates[0]))
    _save(manifest_path, manifest)

    result = validate_evidence(tmp_path)

    assert result.exit_code == 1
    assert any("missing gate" in error for error in result.errors)
    assert any("duplicate gate_id" in error for error in result.errors)


def test_short_source_commit_fails(tmp_path: Path) -> None:
    manifest_path = _write_complete_tree(tmp_path)
    manifest = _load(manifest_path)
    manifest["source_commit"] = "abc123"
    _save(manifest_path, manifest)

    result = validate_evidence(tmp_path)

    assert result.exit_code == 1
    assert any("40 lowercase hexadecimal" in error for error in result.errors)


def test_missing_evidence_and_hash_mismatch_fail(tmp_path: Path) -> None:
    manifest_path = _write_complete_tree(tmp_path)
    manifest = _load(manifest_path)
    gate = _gate(manifest, "G0")
    evidence = gate["evidence"]
    assert isinstance(evidence, list)
    evidence[0]["sha256"] = "0" * 64
    _gate(manifest, "G1")["evidence"] = [
        {"path": "attachments/missing.txt", "sha256": "0" * 64}
    ]
    _save(manifest_path, manifest)

    result = validate_evidence(tmp_path)

    assert result.exit_code == 1
    assert any("hash mismatch" in error for error in result.errors)
    assert any("evidence file not found" in error for error in result.errors)


def test_deliverable_commit_must_match_manifest(tmp_path: Path) -> None:
    manifest_path = _write_complete_tree(tmp_path)
    manifest = _load(manifest_path)
    deliverables = manifest["deliverables"]
    assert isinstance(deliverables, list)
    deliverables[0]["source_commit"] = "b" * 40
    _save(manifest_path, manifest)

    result = validate_evidence(tmp_path)

    assert result.exit_code == 1
    assert any("deliverable source_commit differs" in error for error in result.errors)


def test_blocked_gate_never_summarizes_as_pass(tmp_path: Path) -> None:
    manifest_path = _write_complete_tree(tmp_path)
    manifest = _load(manifest_path)
    _gate(manifest, "G2")["status"] = "BLOCKED"
    _gate(manifest, "G2")["exit_code"] = None
    _save(manifest_path, manifest)

    strict = validate_evidence(tmp_path)
    development = validate_evidence(tmp_path, allow_incomplete=True)

    assert strict.exit_code == 1
    assert strict.summary_status == "BLOCKED"
    assert development.exit_code == 0
    assert development.summary_status == "BLOCKED"


def test_coverage_uses_unrounded_value(tmp_path: Path) -> None:
    manifest_path = _write_complete_tree(tmp_path)
    manifest = _load(manifest_path)
    _gate(manifest, "G3")["metrics"] = {"statement_coverage": 89.99}
    _save(manifest_path, manifest)

    result = validate_evidence(tmp_path)

    assert result.exit_code == 1
    assert any("statement coverage 89.99 is below 90.00" in error for error in result.errors)


def test_performance_requires_comparison_output_and_mixed_workload(tmp_path: Path) -> None:
    manifest_path = _write_complete_tree(tmp_path)
    manifest = _load(manifest_path)
    metrics = _performance_metrics()
    metrics.pop("candidate_medians")
    workload = metrics["workload"]
    assert isinstance(workload, dict)
    workload["workload_mode"] = "single-query-cache-hit"
    _gate(manifest, "G6")["metrics"] = metrics
    _save(manifest_path, manifest)

    result = validate_evidence(tmp_path)

    assert result.exit_code == 1
    assert any("baseline_medians and candidate_medians" in error for error in result.errors)
    assert any("mixed cold and cache-hit workload" in error for error in result.errors)


def test_stale_sha256sums_and_source_version_fail(tmp_path: Path) -> None:
    _write_complete_tree(tmp_path)
    (tmp_path / "deliverables" / "SHA256SUMS.txt").write_text(
        f"{'0' * 64}  stable_build.bin\n",
        encoding="utf-8",
    )
    (tmp_path / "deliverables" / "SOURCE_VERSION.txt").write_text(
        f"source_commit={'b' * 40}\npackage_sha256={'0' * 64}\n",
        encoding="utf-8",
    )

    result = validate_evidence(tmp_path)

    assert result.exit_code == 1
    assert any("SHA256SUMS" in error for error in result.errors)
    assert any("SOURCE_VERSION source_commit differs" in error for error in result.errors)
    assert any("SOURCE_VERSION package_sha256 differs" in error for error in result.errors)


def test_submission_directory_must_match_manifest_deliverables(tmp_path: Path) -> None:
    _write_complete_tree(tmp_path)
    submission = tmp_path / "submission"
    submission.mkdir()
    for artifact in (tmp_path / "deliverables").iterdir():
        if artifact.suffix == ".bin":
            shutil.copy2(artifact, submission / artifact.name)
    (submission / "stable_build.bin").write_bytes(b"newer package from another commit")

    assert "submission_root" in inspect.signature(validate_evidence).parameters
    result = validate_evidence(tmp_path, submission_root=submission)

    assert result.exit_code == 1
    assert any("submission stable_build hash mismatch" in error for error in result.errors)


def test_g8_requires_enforced_isolation_full_sample_and_security_checks(
    tmp_path: Path,
) -> None:
    manifest_path = _write_complete_tree(tmp_path)
    manifest = _load(manifest_path)
    metrics = _gate(manifest, "G8")["metrics"]
    assert isinstance(metrics, dict)
    isolation = metrics["network_isolation"]
    assert isinstance(isolation, dict)
    isolation["enforced"] = False
    isolation["sample_seconds"] = 60
    checks = metrics["checks"]
    assert isinstance(checks, dict)
    checks.pop("reparse_point_escape")
    _save(manifest_path, manifest)

    result = validate_evidence(tmp_path)

    assert result.exit_code == 1
    assert any("G8: network isolation was not enforced" in error for error in result.errors)
    assert any("G8: connection sample 60s is below 1800s" in error for error in result.errors)
    assert any("G8: missing PASS security check reparse_point_escape" in error for error in result.errors)
