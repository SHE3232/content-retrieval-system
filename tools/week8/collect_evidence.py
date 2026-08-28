#!/usr/bin/env python3
"""Run one command and persist auditable Week 8 evidence."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_evidence_command(
    *,
    evidence_id: str,
    command: Sequence[str],
    repository: Path,
    evidence_dir: Path,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Run a command without raising for its exit code and persist logs plus metadata."""

    if not EVIDENCE_ID.fullmatch(evidence_id):
        raise ValueError("evidence_id must contain only lowercase letters, digits, dot, dash, underscore")
    if not command or not all(isinstance(argument, str) and argument for argument in command):
        raise ValueError("command must be a non-empty string sequence")
    repository = repository.resolve()
    evidence_dir = evidence_dir.resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    stdout_name = f"{evidence_id}.stdout.log"
    stderr_name = f"{evidence_id}.stderr.log"
    started_at = _now()
    process_environment = os.environ.copy()
    if environment:
        process_environment.update(environment)
    completed = subprocess.run(
        list(command),
        cwd=repository,
        env=process_environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    finished_at = _now()
    (evidence_dir / stdout_name).write_text(completed.stdout, encoding="utf-8")
    (evidence_dir / stderr_name).write_text(completed.stderr, encoding="utf-8")
    record: dict[str, object] = {
        "schema_version": 1,
        "evidence_id": evidence_id,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "source_commit": source_commit,
        "command": list(command),
        "working_directory": str(repository),
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": completed.returncode,
        "stdout_path": stdout_name,
        "stderr_path": stderr_name,
        "host": {
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "wsl_distro": os.environ.get("WSL_DISTRO_NAME", ""),
        },
    }
    if completed.returncode != 0:
        record["error"] = f"command exited with status {completed.returncode}"
    (evidence_dir / f"{evidence_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--evidence-id", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    record = run_evidence_command(
        evidence_id=args.evidence_id,
        command=command,
        repository=args.repository,
        evidence_dir=args.evidence_dir,
    )
    print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return int(record["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
