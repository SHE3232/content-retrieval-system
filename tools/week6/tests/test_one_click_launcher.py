from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUILD_SCRIPT = REPOSITORY_ROOT / "tools" / "week6" / "build_one_click_launcher.ps1"
BUILD_JAVA_SCRIPT = REPOSITORY_ROOT / "tools" / "week6" / "build_portable_java.ps1"


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


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_one_click_launcher_builds_and_checks_complete_package(tmp_path: Path) -> None:
    launcher = tmp_path / "内容检索系统.exe"
    build = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_SCRIPT),
            "-OutputPath",
            str(launcher),
        ],
        REPOSITORY_ROOT,
    )

    assert build.returncode == 0, build.stdout + build.stderr
    assert launcher.read_bytes().startswith(b"MZ")

    package = tmp_path / "app"
    (package / "frontend").mkdir(parents=True)
    (package / "frontend" / "content_retrieval_app.exe").write_bytes(b"app")
    (package / "runtime" / "python").mkdir(parents=True)
    (package / "runtime" / "python" / "python.exe").write_bytes(b"python")
    (package / "runtime" / "java" / "bin").mkdir(parents=True)
    (package / "runtime" / "java" / "bin" / "java.exe").write_bytes(b"java")
    (package / "models").mkdir()
    (package / "models" / "model-manifest.json").write_text("{}\n", encoding="utf-8")
    (package / "tools" / "tika").mkdir(parents=True)
    (package / "tools" / "tika" / "tika-server-standard-3.3.1.jar").write_bytes(b"tika")
    (package / "tools" / "tika" / "tika-server-standard-3.3.1.jar.sha512").write_text("hash\n", encoding="utf-8")
    (package / "tools" / "start-mvp.ps1").write_text("Write-Output ready\n", encoding="utf-8")
    (package / "启动应用.ps1").write_text("Write-Output integrated\n", encoding="utf-8")

    check = _run(
        [str(launcher), "--check-only", "--package-root", str(package)],
        package,
    )

    assert check.returncode == 0, check.stdout + check.stderr

    (package / "runtime" / "java" / "bin" / "java.exe").unlink()
    missing_java = _run(
        [str(launcher), "--check-only", "--package-root", str(package)],
        package,
    )
    assert missing_java.returncode != 0


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_one_click_launcher_invokes_integrated_script_headlessly(tmp_path: Path) -> None:
    launcher = tmp_path / "内容检索系统.exe"
    build = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_SCRIPT),
            "-OutputPath",
            str(launcher),
        ],
        REPOSITORY_ROOT,
    )
    assert build.returncode == 0, build.stdout + build.stderr

    package = tmp_path / "package with spaces"
    (package / "frontend").mkdir(parents=True)
    (package / "frontend" / "content_retrieval_app.exe").write_bytes(b"app")
    (package / "runtime" / "python").mkdir(parents=True)
    (package / "runtime" / "python" / "python.exe").write_bytes(b"python")
    (package / "runtime" / "java" / "bin").mkdir(parents=True)
    (package / "runtime" / "java" / "bin" / "java.exe").write_bytes(b"java")
    (package / "models").mkdir()
    (package / "models" / "model-manifest.json").write_text("{}\n", encoding="utf-8")
    (package / "tools" / "tika").mkdir(parents=True)
    (package / "tools" / "tika" / "tika-server-standard-3.3.1.jar").write_bytes(b"tika")
    (package / "tools" / "tika" / "tika-server-standard-3.3.1.jar.sha512").write_text("hash\n", encoding="utf-8")
    (package / "tools" / "start-mvp.ps1").write_text("Write-Output ready\n", encoding="utf-8")
    (package / "启动应用.ps1").write_text(
        "param([string]$PackageRoot)\n"
        "[IO.File]::WriteAllText((Join-Path $PackageRoot 'launcher-invoked.txt'), $PackageRoot)\n"
        "exit 0\n",
        encoding="utf-8",
    )

    launched = _run(
        [str(launcher), "--headless", "--package-root", str(package)],
        package,
    )

    assert launched.returncode == 0, launched.stdout + launched.stderr
    assert (package / "launcher-invoked.txt").read_text(encoding="utf-8") == str(package)

    (package / "launcher-invoked.txt").unlink()
    launched_by_double_click_path = _run(
        [str(launcher), "--package-root", str(package)],
        package,
    )
    assert launched_by_double_click_path.returncode == 0
    assert (package / "launcher-invoked.txt").is_file()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_portable_java_builder_uses_jlink_and_verifies_java(tmp_path: Path) -> None:
    fake_jlink = tmp_path / "fake-jlink.ps1"
    fake_jlink.write_text(
        "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Remaining)\n"
        "$outputIndex = [Array]::IndexOf($Remaining, '--output')\n"
        "if ($outputIndex -lt 0) { throw 'missing --output' }\n"
        "$output = $Remaining[$outputIndex + 1]\n"
        "New-Item -ItemType Directory -Force -Path (Join-Path $output 'bin') | Out-Null\n"
        "[IO.File]::WriteAllBytes((Join-Path $output 'bin/java.exe'), [byte[]](77,90))\n"
        "[IO.File]::WriteAllText((Join-Path $output 'jlink-arguments.txt'), ($Remaining -join \"`n\"))\n",
        encoding="utf-8",
    )
    java_home = tmp_path / "jdk"
    (java_home / "jmods").mkdir(parents=True)
    output = tmp_path / "portable-java"

    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_JAVA_SCRIPT),
            "-JavaHome",
            str(java_home),
            "-JlinkExecutable",
            str(fake_jlink),
            "-OutputDirectory",
            str(output),
        ],
        REPOSITORY_ROOT,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output / "bin" / "java.exe").read_bytes().startswith(b"MZ")
    arguments = (output / "jlink-arguments.txt").read_text(encoding="utf-8")
    assert "ALL-MODULE-PATH" in arguments
    assert "--strip-debug" in arguments
