from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest


POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CAPTURE_SCRIPT = REPOSITORY_ROOT / "tools" / "week6" / "capture_candidate.ps1"
PACKAGE_SCRIPT = REPOSITORY_ROOT / "tools" / "week6" / "package_stable_build.ps1"
INTEGRATED_SCRIPT = REPOSITORY_ROOT / "tools" / "week6" / "start-integrated.ps1"


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _git(repo: Path, *args: str) -> str:
    result = _run(["git", *args], repo)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _init_repo(root: Path) -> str:
    _git(root, "init")
    _git(root, "config", "user.email", "week6@example.invalid")
    _git(root, "config", "user.name", "Week 6 Test")
    (root / ".gitignore").write_text("output/\n", encoding="utf-8")
    (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    return _git(root, "rev-parse", "HEAD")


def _write_cmd(path: Path, output: str, *, stderr: bool = False) -> None:
    redirect = " 1>&2" if stderr else ""
    path.write_text(
        f"@echo off\r\necho {output}{redirect}\r\n", encoding="utf-8"
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_capture_candidate_records_clean_commit_and_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit = _init_repo(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    flutter = bin_dir / "flutter.cmd"
    dart = bin_dir / "dart.cmd"
    java = bin_dir / "java.cmd"
    _write_cmd(flutter, "Flutter 3.44.6")
    _write_cmd(dart, "Dart SDK version: 3.12.2")
    _write_cmd(java, 'openjdk version "21"', stderr=True)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    preflight = tmp_path / "preflight.ps1"
    preflight.write_text(
        "param($PythonExecutable,$JavaExecutable,$ModelRoot,$ManifestPath,"
        "$TikaJar,$TikaChecksumFile,$DataDir,[switch]$CheckOnly)\n"
        "if (-not [IO.Path]::IsPathRooted($JavaExecutable) -or "
        "-not (Test-Path -LiteralPath $JavaExecutable -PathType Leaf)) "
        "{ throw 'Java executable must be absolute' }\n"
        "Write-Output 'MVP preflight passed'\n",
        encoding="utf-8",
    )
    model_root = tmp_path / "models"
    model_root.mkdir()
    model_manifest = model_root / "manifest.json"
    model_manifest.write_text('{"models": []}\n', encoding="utf-8")
    tika = tmp_path / "tika.jar"
    tika.write_bytes(b"tika")
    tika_hash = tmp_path / "tika.sha512"
    tika_hash.write_text("hash\n", encoding="utf-8")
    data_dir = tmp_path / "runtime-data"
    data_dir.mkdir()
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "fixtures")
    commit = _git(tmp_path, "rev-parse", "HEAD")
    output = tmp_path / "candidate.json"

    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(CAPTURE_SCRIPT),
            "-RepositoryRoot",
            str(tmp_path),
            "-OutputPath",
            str(output),
            "-PythonExecutable",
            sys.executable,
            "-FlutterExecutable",
            str(flutter),
            "-DartExecutable",
            str(dart),
            "-JavaExecutable",
            "java",
            "-PreflightScript",
            str(preflight),
            "-ModelRoot",
            str(model_root),
            "-ManifestPath",
            str(model_manifest),
            "-TikaJar",
            str(tika),
            "-TikaChecksumFile",
            str(tika_hash),
            "-DataDir",
            str(data_dir),
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["source_commit"] == commit
    assert record["worktree_clean"] is True
    assert record["preflight"]["status"] == "PASS"
    assert record["versions"]["python"].startswith("Python 3.10")


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_capture_candidate_rejects_dirty_worktree(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(CAPTURE_SCRIPT),
            "-RepositoryRoot",
            str(tmp_path),
            "-OutputPath",
            str(tmp_path / "candidate.json"),
        ],
        tmp_path,
    )

    assert result.returncode != 0
    assert "worktree is not clean" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_package_stable_build_uses_whitelist_and_records_commit(tmp_path: Path) -> None:
    release = tmp_path / "frontend-release"
    release.mkdir()
    (release / "content_retrieval_app.exe").write_bytes(b"app")
    backend = tmp_path / "backend"
    (backend / "src").mkdir(parents=True)
    (backend / "src" / "app.py").write_text("print('backend')\n", encoding="utf-8")
    (backend / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    (backend / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    runtime = tmp_path / "python-runtime"
    runtime.mkdir()
    (runtime / "python.exe").write_bytes(b"python")
    models = tmp_path / "models"
    models.mkdir()
    (models / "weights.bin").write_bytes(b"weights")
    manifest = models / "model-manifest.json"
    manifest.write_text('{"models": []}\n', encoding="utf-8")
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "start-mvp.ps1").write_text("Write-Output ready\n", encoding="utf-8")
    integrated = tools / "start-integrated.ps1"
    integrated.write_text("Write-Output integrated\n", encoding="utf-8")
    tika = tmp_path / "tika.jar"
    tika.write_bytes(b"tika")
    tika_hash = tmp_path / "tika.sha512"
    tika_hash.write_text("hash\n", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "private-index.bin").write_bytes(b"private")
    (tmp_path / "user.log").write_text("secret log\n", encoding="utf-8")
    commit = _init_repo(tmp_path)
    output = tmp_path / "output" / "week6" / "stable.zip"

    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PACKAGE_SCRIPT),
            "-RepositoryRoot",
            str(tmp_path),
            "-SourceCommit",
            commit,
            "-FrontendReleaseDir",
            str(release),
            "-PythonRuntimeDir",
            str(runtime),
            "-ModelRoot",
            str(models),
            "-ModelManifestPath",
            str(manifest),
            "-TikaJar",
            str(tika),
            "-TikaChecksumFile",
            str(tika_hash),
            "-MvpLauncher",
            str(tools / "start-mvp.ps1"),
            "-IntegratedLauncher",
            str(integrated),
            "-OutputZip",
            str(output),
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    with ZipFile(output) as archive:
        names = {name.replace("\\", "/") for name in archive.namelist()}
        assert "app/frontend/content_retrieval_app.exe" in names
        assert "app/backend/src/app.py" in names
        assert "app/runtime/python/python.exe" in names
        assert "app/models/weights.bin" in names
        assert "app/PACKAGE_MANIFEST.json" in names
        assert not any("private-index" in name for name in names)
        assert not any(name.endswith("user.log") for name in names)
        package_manifest = json.loads(archive.read("app/PACKAGE_MANIFEST.json"))
        assert package_manifest["source_commit"] == commit


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_package_stable_build_rejects_output_outside_week6(tmp_path: Path) -> None:
    commit = _init_repo(tmp_path)

    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PACKAGE_SCRIPT),
            "-RepositoryRoot",
            str(tmp_path),
            "-SourceCommit",
            commit,
            "-OutputZip",
            str(tmp_path / "outside.zip"),
        ],
        tmp_path,
    )

    assert result.returncode != 0
    assert "output/week6" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_integrated_launcher_check_only_validates_packaged_resources(tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "content_retrieval_app.exe").write_bytes(b"app")
    runtime = tmp_path / "runtime" / "python" / "Scripts"
    runtime.mkdir(parents=True)
    (runtime / "python.exe").write_bytes(b"python")
    models = tmp_path / "models"
    models.mkdir()
    (models / "model-manifest.json").write_text('{"models": []}\n', encoding="utf-8")
    tika = tmp_path / "tools" / "tika"
    tika.mkdir(parents=True)
    (tika / "tika-server-standard-3.3.1.jar").write_bytes(b"tika")
    (tika / "tika-server-standard-3.3.1.jar.sha512").write_text(
        "hash\n", encoding="utf-8"
    )
    (tmp_path / "tools" / "start-mvp.ps1").write_text(
        "Write-Output ready\n", encoding="utf-8"
    )

    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INTEGRATED_SCRIPT),
            "-PackageRoot",
            str(tmp_path),
            "-CheckOnly",
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "integrated package preflight passed" in result.stdout.lower()
