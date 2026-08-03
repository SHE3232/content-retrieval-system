import hashlib
import json
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    platform.system() != "Windows",
    reason="PowerShell MVP launcher is Windows-only",
)


def _available_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _run_preflight(tmp_path: Path, checksum: str) -> subprocess.CompletedProcess[str]:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is not available")

    repository_root = Path(__file__).resolve().parents[2]
    launcher = repository_root / "tools" / "start-mvp.ps1"
    fixture_root = tmp_path / "MVP fixture with spaces"
    fixture_root.mkdir()
    model_root = fixture_root / "models"
    model_root.mkdir()
    manifest = model_root / "model-manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": "1", "models": []}),
        encoding="utf-8",
    )
    tika_jar = fixture_root / "tika.jar"
    tika_jar.write_bytes(b"tika-fixture")
    checksum_file = fixture_root / "tika.jar.sha512"
    checksum_file.write_text(checksum, encoding="ascii")
    data_dir = fixture_root / "data"

    return subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(launcher),
            "-CheckOnly",
            "-PythonExecutable",
            sys.executable,
            "-JavaExecutable",
            sys.executable,
            "-ModelRoot",
            str(model_root),
            "-ManifestPath",
            str(manifest),
            "-DataDir",
            str(data_dir),
            "-TikaJar",
            str(tika_jar),
            "-TikaChecksumFile",
            str(checksum_file),
            "-Port",
            str(_available_tcp_port()),
        ],
        cwd=fixture_root,
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_only_passes_with_matching_tika_checksum(tmp_path: Path) -> None:
    result = _run_preflight(
        tmp_path,
        hashlib.sha512(b"tika-fixture").hexdigest(),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MVP preflight passed" in result.stdout


def test_check_only_rejects_mismatched_tika_checksum(tmp_path: Path) -> None:
    result = _run_preflight(tmp_path, "0" * 128)

    assert result.returncode != 0
    assert "Tika server JAR SHA-512 mismatch" in result.stdout + result.stderr
