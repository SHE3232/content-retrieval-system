#!/usr/bin/env python3
"""Strictly validate the Week 6 evidence manifest and deliverables."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REQUIRED_GATES = tuple(f"G{index}" for index in range(10))
REQUIRED_DELIVERABLES = (
    "stable_build",
    "test_report",
    "performance_report",
    "bug_security_report",
)
ALLOWED_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ACCURACY_KEYS = (
    "nq_recall_at_10",
    "nq_mrr_at_10",
    "nq_ndcg_at_10",
    "coco_recall_at_10",
    "coco_mrr_at_10",
    "coco_ndcg_at_10",
)


@dataclass(frozen=True)
class ValidationResult:
    exit_code: int
    summary_status: str
    passed_gates: int
    errors: tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_commit(value: Any, label: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or COMMIT_PATTERN.fullmatch(value) is None:
        errors.append(f"{label} must be 40 lowercase hexadecimal characters")
        return None
    return value


def _resolve_file(root: Path, relative: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        errors.append(f"{label} path must be a non-empty string")
        return None
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        errors.append(f"{label} path escapes evidence root: {relative!r}")
        return None
    if not resolved.is_file():
        errors.append(f"{label}: evidence file not found: {relative!r}")
        return None
    return resolved


def _validate_file_reference(
    root: Path,
    value: Any,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    path = _resolve_file(root, value.get("path"), label, errors)
    expected_hash = value.get("sha256")
    if not isinstance(expected_hash, str) or SHA256_PATTERN.fullmatch(expected_hash) is None:
        errors.append(f"{label} sha256 must be 64 lowercase hexadecimal characters")
        return
    if path is not None:
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            errors.append(
                f"{label} hash mismatch: expected {expected_hash}, got {actual_hash}"
            )


def _validate_generated_at(value: Any, label: str, errors: list[str]) -> None:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
        if parsed is None or parsed.tzinfo is None:
            raise ValueError("timezone is required")
        if parsed.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ValueError("timestamp is in the future")
    except ValueError as error:
        errors.append(f"{label} generated_at is invalid ({error})")


def _improvement_percent(baseline: float, candidate: float) -> float:
    if baseline <= 0:
        raise ValueError("baseline must be greater than zero")
    return (baseline - candidate) / baseline * 100.0


def _validate_performance(
    metrics: Any,
    label: str,
    errors: list[str],
    manifest_commit: str | None,
) -> None:
    if not isinstance(metrics, dict):
        errors.append(f"{label} performance comparison metrics are required")
        return
    if metrics.get("status") != "PASS":
        errors.append(f"{label} performance comparison status must be PASS")
    if manifest_commit is not None and metrics.get("candidate_commit") != manifest_commit:
        errors.append(f"{label} candidate_commit differs from manifest")

    baseline = metrics.get("baseline_medians")
    candidate = metrics.get("candidate_medians")
    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        errors.append(f"{label} performance metrics require baseline_medians and candidate_medians")
        baseline = baseline if isinstance(baseline, dict) else {}
        candidate = candidate if isinstance(candidate, dict) else {}

    required_metrics = (
        "embedding_combined_p95_ms",
        "vector_query_p95_ms",
        "embedding_hot_p95_ms",
        "vector_query_hot_p95_ms",
        "peak_rss_bytes",
        "full_search_p95_ms",
    )
    improvements: dict[str, float] = {}
    for metric in required_metrics:
        baseline_value = baseline.get(metric)
        candidate_value = candidate.get(metric)
        if not _is_number(baseline_value) or not _is_number(candidate_value):
            errors.append(f"{label} missing numeric performance metric {metric}")
            continue
        try:
            improvement = _improvement_percent(float(baseline_value), float(candidate_value))
        except ValueError as error:
            errors.append(f"{label} {metric}: {error}")
            continue
        improvements[metric] = improvement

    for metric in ("embedding_hot_p95_ms", "vector_query_hot_p95_ms", "peak_rss_bytes"):
        improvement = improvements.get(metric)
        if improvement is not None and improvement < 5.0:
            errors.append(f"{label} {metric} improvement {improvement:.2f}% is below 5.00%")
    for metric in ("embedding_combined_p95_ms", "vector_query_p95_ms", "full_search_p95_ms"):
        improvement = improvements.get(metric)
        if improvement is not None and improvement < -5.0:
            errors.append(f"{label} {metric} regression exceeds 5.00%")

    vector_p95 = candidate.get("vector_query_p95_ms")
    if _is_number(vector_p95) and float(vector_p95) > 2000.0:
        errors.append(f"{label} vector search p95 exceeds 2000 ms")

    workload = metrics.get("workload")
    if not isinstance(workload, dict):
        errors.append(f"{label} comparable workload metadata is required")
    else:
        if workload.get("workload_mode") != "mixed-cold-and-cache-hit":
            errors.append(f"{label} mixed cold and cache-hit workload is required")
        if workload.get("warmup_inputs_disjoint") is not True:
            errors.append(f"{label} workload warmup inputs must be disjoint")
        hit_ratio = workload.get("target_cache_hit_ratio")
        if not _is_number(hit_ratio) or not 0.5 <= float(hit_ratio) <= 0.9:
            errors.append(f"{label} workload target_cache_hit_ratio must be between 0.5 and 0.9")

    accuracy_checks = metrics.get("accuracy_checks")
    if not isinstance(accuracy_checks, dict):
        errors.append(f"{label} accuracy checks are required")
        return
    for key in ACCURACY_KEYS:
        check = accuracy_checks.get(key)
        if not isinstance(check, dict) or check.get("status") != "PASS":
            errors.append(f"{label} missing PASS accuracy check {key}")
            continue
        baseline_value = check.get("baseline")
        candidate_value = check.get("candidate")
        if not _is_number(baseline_value) or not _is_number(candidate_value):
            errors.append(f"{label} missing numeric accuracy values for {key}")
        elif float(baseline_value) - float(candidate_value) > 0.01 + 1e-12:
            errors.append(f"{label} accuracy metric {key} regressed by more than 0.01")


def _validate_security(metrics: Any, label: str, errors: list[str]) -> None:
    if not isinstance(metrics, dict):
        errors.append(f"{label}: security metrics are required")
        return
    isolation = metrics.get("network_isolation")
    if not isinstance(isolation, dict):
        errors.append(f"{label}: network isolation evidence is required")
    else:
        if isolation.get("enforced") is not True:
            errors.append(f"{label}: network isolation was not enforced")
        method = isolation.get("method")
        if method not in {
            "host-network-disabled",
            "firewall-outbound-block",
            "process-network-deny",
        }:
            errors.append(f"{label}: unsupported network isolation method {method!r}")
        sample_seconds = isolation.get("sample_seconds")
        if not _is_number(sample_seconds):
            errors.append(f"{label}: numeric connection sample_seconds is required")
        elif float(sample_seconds) < 1800.0:
            errors.append(
                f"{label}: connection sample {float(sample_seconds):g}s is below 1800s"
            )

    checks = metrics.get("checks")
    required_checks = (
        "offline_e2e",
        "non_loopback_connections",
        "path_traversal",
        "reparse_point_escape",
        "package_audit",
    )
    if not isinstance(checks, dict):
        errors.append(f"{label}: security checks are required")
        return
    for check in required_checks:
        if checks.get(check) != "PASS":
            errors.append(f"{label}: missing PASS security check {check}")


def _validate_gate(
    root: Path,
    gate: dict[str, Any],
    manifest_commit: str | None,
    structural_errors: list[str],
    completeness_errors: list[str],
) -> None:
    gate_id = gate.get("gate_id")
    label = gate_id if isinstance(gate_id, str) else "unknown gate"
    status = gate.get("status")
    if status not in ALLOWED_STATUSES:
        structural_errors.append(f"{label}: invalid status {status!r}")
    elif status != "PASS":
        completeness_errors.append(f"{label}: status is {status}")

    source_commit = _validate_commit(
        gate.get("source_commit"), f"{label} source_commit", structural_errors
    )
    if source_commit is not None and manifest_commit is not None and source_commit != manifest_commit:
        structural_errors.append(f"{label}: source_commit differs from manifest")

    _validate_generated_at(gate.get("generated_at"), label, structural_errors)
    command = gate.get("command")
    if not isinstance(command, str) or not command.strip():
        structural_errors.append(f"{label}: command must be a non-empty string")

    exit_code = gate.get("exit_code")
    if status == "PASS" and exit_code != 0:
        structural_errors.append(f"{label}: PASS requires exit_code 0")
    elif exit_code is not None and not isinstance(exit_code, int):
        structural_errors.append(f"{label}: exit_code must be an integer or null")

    evidence = gate.get("evidence")
    if status == "PASS" and (not isinstance(evidence, list) or not evidence):
        structural_errors.append(f"{label}: PASS requires at least one evidence file")
    elif evidence is not None:
        if not isinstance(evidence, list):
            structural_errors.append(f"{label}: evidence must be a list")
        else:
            for index, reference in enumerate(evidence):
                _validate_file_reference(
                    root, reference, f"{label} evidence[{index}]", structural_errors
                )

    if gate_id == "G3" and status == "PASS":
        metrics = gate.get("metrics")
        coverage = metrics.get("statement_coverage") if isinstance(metrics, dict) else None
        if not _is_number(coverage):
            structural_errors.append(f"{label}: numeric statement_coverage is required")
        elif float(coverage) < 90.0:
            structural_errors.append(
                f"{label}: statement coverage {float(coverage):.2f} is below 90.00"
            )

    if gate_id == "G6" and status == "PASS":
        _validate_performance(gate.get("metrics"), label, structural_errors, manifest_commit)

    if gate_id == "G8" and status == "PASS":
        _validate_security(gate.get("metrics"), label, structural_errors)


def _validate_deliverables(
    root: Path,
    raw_deliverables: Any,
    manifest_commit: str | None,
    structural_errors: list[str],
    completeness_errors: list[str],
) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_deliverables, list):
        structural_errors.append("deliverables must be a list")
        return {}
    records: dict[str, dict[str, Any]] = {}
    for value in raw_deliverables:
        if not isinstance(value, dict) or not isinstance(value.get("deliverable_id"), str):
            structural_errors.append("deliverable is missing deliverable_id")
            continue
        deliverable_id = value["deliverable_id"]
        if deliverable_id in records:
            structural_errors.append(f"{deliverable_id}: duplicate deliverable_id")
            continue
        records[deliverable_id] = value

    for deliverable_id in REQUIRED_DELIVERABLES:
        if deliverable_id not in records:
            completeness_errors.append(f"missing deliverable {deliverable_id}")
    for deliverable_id in sorted(set(records) - set(REQUIRED_DELIVERABLES)):
        structural_errors.append(f"unexpected deliverable {deliverable_id}")

    for deliverable_id, value in records.items():
        source_commit = _validate_commit(
            value.get("source_commit"),
            f"{deliverable_id} source_commit",
            structural_errors,
        )
        if source_commit is not None and manifest_commit is not None and source_commit != manifest_commit:
            structural_errors.append(
                f"{deliverable_id}: deliverable source_commit differs from manifest"
            )
        _validate_file_reference(root, value, deliverable_id, structural_errors)
    return records


def _parse_key_value_file(path: Path, label: str, errors: list[str]) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        errors.append(f"{label} cannot be read ({error})")
        return {}
    values: dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        if "=" not in line:
            errors.append(f"{label} contains invalid line {line!r}")
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _validate_release_metadata(
    root: Path,
    records: dict[str, dict[str, Any]],
    manifest_commit: str | None,
    errors: list[str],
) -> None:
    deliverables_dir = root / "deliverables"
    sums_path = deliverables_dir / "SHA256SUMS.txt"
    version_path = deliverables_dir / "SOURCE_VERSION.txt"

    expected_by_name: dict[str, str] = {}
    for deliverable_id in REQUIRED_DELIVERABLES:
        value = records.get(deliverable_id)
        if not isinstance(value, dict):
            continue
        relative = value.get("path")
        sha256 = value.get("sha256")
        if isinstance(relative, str) and isinstance(sha256, str):
            expected_by_name[Path(relative).name] = sha256

    if not sums_path.is_file():
        errors.append("SHA256SUMS.txt is required in deliverables")
    else:
        actual_by_name: dict[str, str] = {}
        try:
            for line in sums_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                parts = line.split(None, 1)
                if len(parts) != 2:
                    errors.append(f"SHA256SUMS contains invalid line {line!r}")
                    continue
                digest, name = parts[0].strip(), parts[1].strip().lstrip("*")
                actual_by_name[name] = digest
        except (OSError, UnicodeError) as error:
            errors.append(f"SHA256SUMS cannot be read ({error})")
        for name, expected_hash in expected_by_name.items():
            actual_hash = actual_by_name.get(name)
            if actual_hash != expected_hash:
                errors.append(
                    f"SHA256SUMS mismatch for {name}: expected {expected_hash}, got {actual_hash}"
                )

    if not version_path.is_file():
        errors.append("SOURCE_VERSION.txt is required in deliverables")
        return
    values = _parse_key_value_file(version_path, "SOURCE_VERSION", errors)
    if manifest_commit is not None and values.get("source_commit") != manifest_commit:
        errors.append("SOURCE_VERSION source_commit differs from manifest")
    stable = records.get("stable_build")
    stable_hash = stable.get("sha256") if isinstance(stable, dict) else None
    if isinstance(stable_hash, str) and values.get("package_sha256") != stable_hash:
        errors.append("SOURCE_VERSION package_sha256 differs from stable_build")


def _validate_submission(
    submission_root: Path,
    records: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    root = submission_root.resolve()
    if not root.is_dir():
        errors.append(f"submission root not found: {root}")
        return
    for deliverable_id in REQUIRED_DELIVERABLES:
        value = records.get(deliverable_id)
        if not isinstance(value, dict):
            continue
        relative = value.get("path")
        expected_hash = value.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            continue
        artifact = root / Path(relative).name
        if not artifact.is_file():
            errors.append(f"submission {deliverable_id} not found: {artifact.name}")
            continue
        actual_hash = _sha256(artifact)
        if actual_hash != expected_hash:
            errors.append(
                f"submission {deliverable_id} hash mismatch: expected {expected_hash}, got {actual_hash}"
            )


def _summary_status(records: Iterable[dict[str, Any]], has_structural_errors: bool) -> str:
    if has_structural_errors:
        return "FAIL"
    statuses = {record.get("status") for record in records}
    if "FAIL" in statuses:
        return "FAIL"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "NOT_RUN" in statuses or "PASS" not in statuses:
        return "NOT_RUN"
    return "PASS"


def validate_evidence(
    root: Path,
    allow_incomplete: bool = False,
    submission_root: Path | None = None,
) -> ValidationResult:
    root = root.resolve()
    structural_errors: list[str] = []
    completeness_errors: list[str] = []
    manifest_path = root / "manifest.json"
    manifest: dict[str, Any] = {}

    if not root.is_dir():
        return ValidationResult(1, "FAIL", 0, (f"evidence root not found: {root}",))
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("top level must be an object")
        manifest = value
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        return ValidationResult(1, "FAIL", 0, (f"invalid manifest.json ({error})",))

    if manifest.get("schema_version") != 1:
        structural_errors.append("schema_version must equal 1")
    manifest_commit = _validate_commit(
        manifest.get("source_commit"), "manifest source_commit", structural_errors
    )

    raw_gates = manifest.get("gates")
    records: dict[str, dict[str, Any]] = {}
    ordered_records: list[dict[str, Any]] = []
    if not isinstance(raw_gates, list):
        structural_errors.append("gates must be a list")
    else:
        for value in raw_gates:
            if not isinstance(value, dict) or not isinstance(value.get("gate_id"), str):
                structural_errors.append("gate is missing gate_id")
                continue
            gate_id = value["gate_id"]
            if gate_id in records:
                structural_errors.append(f"{gate_id}: duplicate gate_id")
                continue
            records[gate_id] = value
            ordered_records.append(value)
            _validate_gate(
                root,
                value,
                manifest_commit,
                structural_errors,
                completeness_errors,
            )

    for gate_id in REQUIRED_GATES:
        if gate_id not in records:
            structural_errors.append(f"missing gate {gate_id}")
    for gate_id in sorted(set(records) - set(REQUIRED_GATES)):
        structural_errors.append(f"unexpected gate {gate_id}")

    deliverable_records = _validate_deliverables(
        root,
        manifest.get("deliverables"),
        manifest_commit,
        structural_errors,
        completeness_errors,
    )
    _validate_release_metadata(
        root,
        deliverable_records,
        manifest_commit,
        structural_errors,
    )
    if submission_root is not None:
        _validate_submission(submission_root, deliverable_records, structural_errors)

    summary = _summary_status(ordered_records, bool(structural_errors))
    passed = sum(record.get("status") == "PASS" for record in ordered_records)
    errors = tuple(structural_errors + completeness_errors)
    exit_code = 1 if structural_errors or (completeness_errors and not allow_incomplete) else 0
    return ValidationResult(exit_code, summary, passed, errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--submission-dir", type=Path)
    args = parser.parse_args()
    result = validate_evidence(
        args.evidence_root,
        args.allow_incomplete,
        submission_root=args.submission_dir,
    )
    for gate_id in REQUIRED_GATES:
        print(f"{gate_id}: checked")
    print(
        f"Week 6 evidence: {result.passed_gates}/{len(REQUIRED_GATES)} gates PASS; "
        f"summary={result.summary_status}"
    )
    for error in result.errors:
        print(f"ERROR {error}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
