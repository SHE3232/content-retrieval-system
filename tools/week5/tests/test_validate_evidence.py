import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.week5.validate_evidence import REQUIRED_GATES, validate_evidence


def _write_complete_tree(root: Path) -> None:
    attachment = root / "attachments" / "proof.txt"
    attachment.parent.mkdir(parents=True, exist_ok=True)
    attachment.write_text("verified\n", encoding="utf-8")
    records = root / "records"
    records.mkdir(exist_ok=True)
    tested_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    for index, gate_id in enumerate(sorted(REQUIRED_GATES)):
        (records / f"{index:02d}.json").write_text(
            json.dumps(
                {
                    "gate_id": gate_id,
                    "status": "PASS",
                    "tested_at": tested_at,
                    "tester": "Automated test",
                    "environment": "test",
                    "procedure": ["run verification"],
                    "observations": ["exit code 0"],
                    "attachments": ["attachments/proof.txt"],
                    "issues": [],
                }
            ),
            encoding="utf-8",
        )


def test_all_required_pass_returns_success(tmp_path: Path) -> None:
    _write_complete_tree(tmp_path)
    assert validate_evidence(tmp_path) == 0


def test_missing_or_non_pass_gate_fails_strict_mode(tmp_path: Path) -> None:
    _write_complete_tree(tmp_path)
    records = sorted((tmp_path / "records").glob("*.json"))
    records[0].unlink()
    assert validate_evidence(tmp_path) == 1

    _write_complete_tree(tmp_path)
    record = json.loads(records[1].read_text(encoding="utf-8"))
    record["status"] = "BLOCKED"
    records[1].write_text(json.dumps(record), encoding="utf-8")
    assert validate_evidence(tmp_path) == 1
    assert validate_evidence(tmp_path, allow_incomplete=True) == 0


def test_invalid_time_required_fields_and_attachments_fail(tmp_path: Path) -> None:
    _write_complete_tree(tmp_path)
    record_path = sorted((tmp_path / "records").glob("*.json"))[0]
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["tested_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    record["tester"] = ""
    record["procedure"] = []
    record["attachments"] = ["../outside.txt"]
    record_path.write_text(json.dumps(record), encoding="utf-8")
    assert validate_evidence(tmp_path) == 1


def test_duplicate_gate_id_fails(tmp_path: Path) -> None:
    _write_complete_tree(tmp_path)
    first = sorted((tmp_path / "records").glob("*.json"))[0]
    duplicate = tmp_path / "records" / "duplicate.json"
    duplicate.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
    assert validate_evidence(tmp_path) == 1
