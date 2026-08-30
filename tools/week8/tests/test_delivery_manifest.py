from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from tools.week8.build_delivery_manifest import build_manifest, validate_manifest_data
from tools.week8.collect_evidence import run_evidence_command
from tools.week8.verify_delivery import verify_delivery

COMMIT = "1" * 40
REPOSITORY = Path(__file__).resolve().parents[3]
MANIFEST_SCRIPT = REPOSITORY / "tools" / "week8" / "build_delivery_manifest.py"
VERIFY_SCRIPT = REPOSITORY / "tools" / "week8" / "verify_delivery.py"
COLLECT_SCRIPT = REPOSITORY / "tools" / "week8" / "collect_evidence.py"
EVIDENCE_SCHEMA = REPOSITORY / "tools" / "week8" / "evidence_schema.json"


def _blocked_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "source_commit": COMMIT,
        "generated_at": "2026-08-27T12:00:00+00:00",
        "tests": {
            "python-main": {
                "status": "PASS",
                "passed": 464,
                "skipped": 1,
                "evidence_path": "docs/week8/evidence/tests/python-main.log",
            }
        },
        "platforms": {
            "windows": {
                "status": "BLOCKED",
                "evidence_paths": ["docs/week8/evidence/platform/windows/status.json"],
                "reason": "candidate not built",
            },
            "linux": {
                "status": "BLOCKED",
                "evidence_paths": ["docs/week8/evidence/platform/linux/status.json"],
                "reason": "candidate not built",
            },
            "macos": {
                "status": "BLOCKED",
                "evidence_paths": ["docs/week8/evidence/platform/macos/status.json"],
                "reason": "real Mac unavailable",
            },
        },
        "distributions": {
            "public-source": {
                "distribution_class": "public-source",
                "model_policy": "excludes MobileCLIP weights",
            },
            "default-public": {
                "distribution_class": "default-public",
                "model_policy": "excludes MobileCLIP weights",
            },
            "course-research": {
                "distribution_class": "research-only",
                "model_policy": "MobileCLIP allowed only with research license and hashes",
            },
        },
        "artifacts": [],
    }


def test_validate_manifest_accepts_explicit_blocked_platforms() -> None:
    assert validate_manifest_data(_blocked_manifest()) == []


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.update(source_commit="abc123"), "full lowercase Git commit"),
        (
            lambda data: data["platforms"]["windows"].update(
                status="PASS", evidence_paths=[]
            ),
            "PASS requires evidence_paths",
        ),
        (
            lambda data: data["platforms"]["linux"].update(status="UNKNOWN"),
            "status must be PASS, FAIL, or BLOCKED",
        ),
        (
            lambda data: data["tests"]["python-main"].update(passed=-1),
            "passed must be a non-negative integer",
        ),
    ],
)
def test_validate_manifest_rejects_invalid_gate_data(mutation, message: str) -> None:
    data = deepcopy(_blocked_manifest())
    mutation(data)

    errors = validate_manifest_data(data)

    assert any(message in error for error in errors)


def test_validate_manifest_requires_artifact_hash_size_class_and_provenance() -> None:
    data = _blocked_manifest()
    data["artifacts"] = [
        {
            "path": "02_公开源码/source.zip",
            "bytes": 0,
            "sha256": "bad",
            "distribution_class": "public-source",
            "provenance": "",
        }
    ]

    errors = validate_manifest_data(data)

    assert any("bytes must be a positive integer" in error for error in errors)
    assert any(
        "sha256 must be 64 lowercase hexadecimal characters" in error
        for error in errors
    )
    assert any("provenance is required" in error for error in errors)


def _git_repository(root: Path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "week8@example.invalid"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Week 8 Test"], cwd=root, check=True)
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


def test_run_evidence_command_writes_logs_and_machine_metadata(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    commit = _git_repository(repository)
    evidence_dir = tmp_path / "evidence"

    record = run_evidence_command(
        evidence_id="sample-pass",
        command=[sys.executable, "-c", "print('hello evidence')"],
        repository=repository,
        evidence_dir=evidence_dir,
    )

    assert record["status"] == "PASS"
    assert record["exit_code"] == 0
    assert record["source_commit"] == commit
    assert record["command"] == [sys.executable, "-c", "print('hello evidence')"]
    assert record["host"]["os"]
    assert record["host"]["python"]
    assert (evidence_dir / record["stdout_path"]).read_text(
        encoding="utf-8"
    ) == "hello evidence\n"
    assert (evidence_dir / record["stderr_path"]).read_text(encoding="utf-8") == ""
    persisted = json.loads(
        (evidence_dir / "sample-pass.json").read_text(encoding="utf-8")
    )
    assert persisted == record


def test_run_evidence_command_records_nonzero_exit_without_claiming_pass(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git_repository(repository)

    record = run_evidence_command(
        evidence_id="sample-fail",
        command=[
            sys.executable,
            "-c",
            "import sys; print('bad', file=sys.stderr); sys.exit(3)",
        ],
        repository=repository,
        evidence_dir=tmp_path / "evidence",
    )

    assert record["status"] == "FAIL"
    assert record["exit_code"] == 3
    assert record["error"] == "command exited with status 3"


def test_build_manifest_hashes_declared_artifacts_and_uses_exact_head(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    commit = _git_repository(repository)
    delivery_root = tmp_path / "delivery"
    artifact = delivery_root / "02_public_source" / "source.zip"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"week8 artifact")
    evidence = _blocked_manifest()
    evidence["source_commit"] = commit
    evidence["artifacts"] = [
        {
            "path": "02_public_source/source.zip",
            "distribution_class": "public-source",
            "provenance": "clean source exporter",
        }
    ]
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    manifest = build_manifest(repository, evidence_path, delivery_root)

    assert manifest["source_commit"] == commit
    assert manifest["artifacts"] == [
        {
            "path": "02_public_source/source.zip",
            "bytes": len(b"week8 artifact"),
            "sha256": __import__("hashlib").sha256(b"week8 artifact").hexdigest(),
            "distribution_class": "public-source",
            "provenance": "clean source exporter",
        }
    ]
    assert validate_manifest_data(manifest) == []


def test_build_manifest_cli_writes_output(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    commit = _git_repository(repository)
    delivery_root = tmp_path / "delivery"
    delivery_root.mkdir()
    evidence = _blocked_manifest()
    evidence["source_commit"] = commit
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    output = delivery_root / "DELIVERY_MANIFEST.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(MANIFEST_SCRIPT),
            "--repository",
            str(repository),
            "--evidence",
            str(evidence_path),
            "--delivery-root",
            str(delivery_root),
            "--output",
            str(output),
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["source_commit"] == commit
    assert json.loads(completed.stdout) == {
        "artifact_count": 0,
        "output": str(output.resolve()),
        "source_commit": commit,
    }


def _write_gate_evidence(repository: Path, manifest: dict[str, object]) -> None:
    for gate in manifest["tests"].values():
        path = repository / gate["evidence_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test evidence\n", encoding="utf-8")
    for gate in manifest["platforms"].values():
        for raw_path in gate["evidence_paths"]:
            path = repository / raw_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("platform evidence\n", encoding="utf-8")


def test_verify_delivery_accepts_consistent_blocked_state_but_all_platform_gate_fails(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    commit = _git_repository(repository)
    delivery_root = tmp_path / "delivery"
    delivery_root.mkdir()
    manifest = _blocked_manifest()
    manifest["source_commit"] = commit
    _write_gate_evidence(repository, manifest)
    manifest_path = delivery_root / "DELIVERY_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_delivery(repository, delivery_root, manifest_path)

    assert report["status"] == "PASS"
    assert report["artifact_count"] == 0
    with pytest.raises(ValueError, match="platforms are not PASS"):
        verify_delivery(
            repository, delivery_root, manifest_path, require_all_platforms=True
        )


def test_verify_delivery_rejects_restricted_weight_in_public_zip(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    commit = _git_repository(repository)
    delivery_root = tmp_path / "delivery"
    delivery_root.mkdir()
    archive = delivery_root / "public.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as package:
        package.writestr(
            "CLEAN_SOURCE_MANIFEST.json", json.dumps({"source_commit": commit})
        )
        package.writestr("models/mobileclip/model.safetensors", b"restricted")
    manifest = _blocked_manifest()
    manifest["source_commit"] = commit
    manifest["artifacts"] = [
        {
            "path": "public.zip",
            "bytes": archive.stat().st_size,
            "sha256": __import__("hashlib").sha256(archive.read_bytes()).hexdigest(),
            "distribution_class": "public-source",
            "provenance": "test",
        }
    ]
    _write_gate_evidence(repository, manifest)
    manifest_path = delivery_root / "DELIVERY_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="restricted public archive member"):
        verify_delivery(repository, delivery_root, manifest_path)


def test_verify_delivery_allows_frozen_text_model_in_default_public_zip(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    commit = _git_repository(repository)
    delivery_root = tmp_path / "delivery"
    delivery_root.mkdir()
    archive = delivery_root / "default-public.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as package:
        package.writestr("PACKAGE_MANIFEST.json", json.dumps({"source_commit": commit}))
        package.writestr(
            "app/models/text/text-multilingual-v1/model.safetensors", b"text"
        )
        package.writestr(
            "app/runtime/python/site-packages/distutils-precedence.pth", b"runtime"
        )
    manifest = _blocked_manifest()
    manifest["source_commit"] = commit
    manifest["artifacts"] = [
        {
            "path": "default-public.zip",
            "bytes": archive.stat().st_size,
            "sha256": __import__("hashlib").sha256(archive.read_bytes()).hexdigest(),
            "distribution_class": "default-public",
            "provenance": "test",
        }
    ]
    _write_gate_evidence(repository, manifest)
    manifest_path = delivery_root / "DELIVERY_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_delivery(repository, delivery_root, manifest_path)

    assert report["status"] == "PASS"


def test_verify_delivery_rejects_mobileclip_in_default_public_zip(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    commit = _git_repository(repository)
    delivery_root = tmp_path / "delivery"
    delivery_root.mkdir()
    archive = delivery_root / "default-public.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as package:
        package.writestr("PACKAGE_MANIFEST.json", json.dumps({"source_commit": commit}))
        package.writestr("app/models/mobileclip/mobileclip_s0.pt", b"restricted")
    manifest = _blocked_manifest()
    manifest["source_commit"] = commit
    manifest["artifacts"] = [
        {
            "path": "default-public.zip",
            "bytes": archive.stat().st_size,
            "sha256": __import__("hashlib").sha256(archive.read_bytes()).hexdigest(),
            "distribution_class": "default-public",
            "provenance": "test",
        }
    ]
    _write_gate_evidence(repository, manifest)
    manifest_path = delivery_root / "DELIVERY_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="restricted public archive member"):
        verify_delivery(repository, delivery_root, manifest_path)


def test_verify_delivery_requires_license_and_model_manifest_in_research_zip(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    commit = _git_repository(repository)
    delivery_root = tmp_path / "delivery"
    delivery_root.mkdir()
    archive = delivery_root / "research.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as package:
        package.writestr("PACKAGE_MANIFEST.json", json.dumps({"source_commit": commit}))
        package.writestr("models/mobileclip/model.safetensors", b"research")
    manifest = _blocked_manifest()
    manifest["source_commit"] = commit
    manifest["artifacts"] = [
        {
            "path": "research.zip",
            "bytes": archive.stat().st_size,
            "sha256": __import__("hashlib").sha256(archive.read_bytes()).hexdigest(),
            "distribution_class": "research-only",
            "provenance": "test",
        }
    ]
    _write_gate_evidence(repository, manifest)
    manifest_path = delivery_root / "DELIVERY_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="research archive missing"):
        verify_delivery(repository, delivery_root, manifest_path)


def test_evidence_schema_declares_required_fact_domains() -> None:
    schema = json.loads(EVIDENCE_SCHEMA.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert set(schema["required"]) == {
        "schema_version",
        "source_commit",
        "generated_at",
        "tests",
        "platforms",
        "distributions",
        "artifacts",
    }
    assert set(schema["properties"]["platforms"]["required"]) == {
        "windows",
        "linux",
        "macos",
    }


def test_verify_delivery_cli_prints_machine_readable_result(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    commit = _git_repository(repository)
    delivery_root = tmp_path / "delivery"
    delivery_root.mkdir()
    manifest = _blocked_manifest()
    manifest["source_commit"] = commit
    _write_gate_evidence(repository, manifest)
    manifest_path = delivery_root / "DELIVERY_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--repository",
            str(repository),
            "--delivery-root",
            str(delivery_root),
            "--manifest",
            str(manifest_path),
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "artifact_count": 0,
        "platforms": {"linux": "BLOCKED", "macos": "BLOCKED", "windows": "BLOCKED"},
        "source_commit": commit,
        "status": "PASS",
    }


def test_collect_evidence_cli_runs_command_after_separator(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    commit = _git_repository(repository)
    evidence_dir = tmp_path / "evidence"

    completed = subprocess.run(
        [
            sys.executable,
            str(COLLECT_SCRIPT),
            "--repository",
            str(repository),
            "--evidence-dir",
            str(evidence_dir),
            "--evidence-id",
            "cli-pass",
            "--",
            sys.executable,
            "-c",
            "print('cli evidence')",
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    record = json.loads(completed.stdout)
    assert record["status"] == "PASS"
    assert record["source_commit"] == commit
    assert (evidence_dir / "cli-pass.json").is_file()
