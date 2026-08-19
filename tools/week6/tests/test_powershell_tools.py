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
BUILD_PORTABLE_JAVA_SCRIPT = (
    REPOSITORY_ROOT / "tools" / "week6" / "build_portable_java.ps1"
)
INTEGRATED_SCRIPT = REPOSITORY_ROOT / "tools" / "week6" / "start-integrated.ps1"
SECURITY_AUDIT_SCRIPT = REPOSITORY_ROOT / "tools" / "week6" / "audit_offline_security.ps1"
LIGHTWEIGHT_PROFILE_PATH = REPOSITORY_ROOT / "tools" / "week6" / "lightweight_package_profile.json"
LIGHTWEIGHT_PROFILE = json.loads(LIGHTWEIGHT_PROFILE_PATH.read_text(encoding="utf-8"))
LIGHTWEIGHT_LICENSE_FILENAMES = {
    "pyarrow": "LICENSE.txt",
    "coverage": "NOTICE.txt",
}


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
    _git(root, "config", "core.longpaths", "true")
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


def _add_lightweight_runtime_fixture(runtime: Path, java_runtime: Path) -> None:
    profile = LIGHTWEIGHT_PROFILE
    site_packages = runtime / "Lib" / "site-packages"
    sentence_transformers = site_packages / "sentence_transformers"
    sentence_transformers.mkdir(parents=True)
    (sentence_transformers / "__init__.py").write_text("\n", encoding="utf-8")
    for directory_name in profile["python_remove_directory_names"]:
        marker_dir = sentence_transformers / directory_name
        marker_dir.mkdir()
        (marker_dir / f"{directory_name}-marker.txt").write_text(
            "remove directory\n", encoding="utf-8"
        )
    (sentence_transformers / "__pycache__" / "cached.pyc").write_bytes(b"cache")
    (sentence_transformers / "tests" / "test_model.py").write_text(
        "# test\n", encoding="utf-8"
    )

    for extension in profile["python_remove_file_extensions"]:
        (sentence_transformers / f"extension-marker{extension}").write_bytes(
            b"remove extension"
        )

    for relative_tree in profile["python_remove_relative_trees"]:
        marker = runtime / relative_tree / "relative-tree-marker.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("remove tree\n", encoding="utf-8")

    torch = site_packages / "torch"
    (torch / "lib").mkdir(parents=True)
    (torch / "lib" / "torch_cpu.dll").write_bytes(b"torch")
    (torch / "lib" / "torch_cpu.lib").write_bytes(b"symbols")
    (torch / "include").mkdir(exist_ok=True)
    (torch / "include" / "torch.h").write_text("// header\n", encoding="utf-8")

    for package in profile["python_remove_packages"]:
        component = site_packages / package
        component.mkdir()
        (component / "package-marker.txt").write_text("remove package\n", encoding="utf-8")
        license_filename = LIGHTWEIGHT_LICENSE_FILENAMES.get(package, "LICENSE")
        metadata_dir = site_packages / f"{package}-1.0.dist-info"
        metadata_dir.mkdir()
        (metadata_dir / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {package}\nVersion: 1.0\n",
            encoding="utf-8",
        )
        license_file = metadata_dir / "licenses" / license_filename
        license_file.parent.mkdir(parents=True)
        license_file.write_bytes(f"{package} license\n".encode("utf-8"))
        if package == "pyarrow":
            duplicate_license = metadata_dir / "vendor" / license_filename
            duplicate_license.parent.mkdir(parents=True)
            duplicate_license.write_bytes(b"pyarrow nested license\n")

    collision_metadata = site_packages / "pandas_2fa-1.0.dist-info"
    collision_metadata.mkdir()
    (collision_metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: pandas-2fa\nVersion: 1.0\n",
        encoding="utf-8",
    )
    (collision_metadata / "collision-sentinel.txt").write_bytes(b"keep collision")
    (collision_metadata / "LICENSE").write_bytes(b"pandas-2fa license\n")

    expected_module_path = str(java_runtime / "jmods")
    escaped_module_path = expected_module_path.replace("'", "''")
    expected_java_modules = ",".join(profile["java_modules"])
    jlink = java_runtime / "bin" / "jlink.ps1"
    jlink.parent.mkdir(parents=True)
    (jlink.parent / "java.exe").write_bytes(b"source-java")
    jlink.write_text(
        "param(\n"
        "  [Parameter(ValueFromRemainingArguments = $true)]\n"
        "  [string[]]$Arguments\n"
        ")\n"
        "function Require-ArgumentValue([string]$Name) {\n"
        "  $index = [Array]::IndexOf($Arguments, $Name)\n"
        "  if ($index -lt 0 -or $index + 1 -ge $Arguments.Count) {\n"
        "    throw \"jlink $Name argument is required\"\n"
        "  }\n"
        "  return $Arguments[$index + 1]\n"
        "}\n"
        "$modulePath = Require-ArgumentValue '--module-path'\n"
        "$addModules = Require-ArgumentValue '--add-modules'\n"
        "$output = Require-ArgumentValue '--output'\n"
        f"$expectedModulePath = '{escaped_module_path}'\n"
        f"$expectedModules = '{expected_java_modules}'\n"
        "if ([IO.Path]::GetFullPath($modulePath) -ne [IO.Path]::GetFullPath($expectedModulePath)) {\n"
        "  throw 'jlink module path does not match the lightweight JDK jmods directory'\n"
        "}\n"
        "if ($addModules -ne $expectedModules) {\n"
        "  throw 'jlink module list does not match lightweight package policy'\n"
        "}\n"
        "New-Item -ItemType Directory -Force -Path (Join-Path $output 'bin') | Out-Null\n"
        "[IO.File]::WriteAllBytes((Join-Path $output 'bin/java.exe'), [byte[]](106, 97, 118, 97))\n"
        "[IO.File]::WriteAllText((Join-Path $output 'bin/jlink-arguments.txt'), "
        "\"module_path=$modulePath`nadd_modules=$addModules\")\n",
        encoding="utf-8",
    )
    jmods = java_runtime / "jmods"
    jmods.mkdir(parents=True)
    for module in profile["java_modules"]:
        (jmods / f"{module}.jmod").write_bytes(b"jmod")


def _lightweight_package_fixture(
    tmp_path: Path, archive_size_limit_bytes: int = 128
) -> tuple[list[str], Path, Path]:
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
    java_runtime = tmp_path / "java-runtime"
    _add_lightweight_runtime_fixture(runtime, java_runtime)
    models = tmp_path / "models"
    models.mkdir()
    (models / "weights.bin").write_bytes(b"weights")
    manifest = models / "model-manifest.json"
    manifest.write_text('{"models": []}\n', encoding="utf-8")
    tools = tmp_path / "tools"
    tools.mkdir()
    mvp_launcher = tools / "start-mvp.ps1"
    mvp_launcher.write_text("Write-Output ready\n", encoding="utf-8")
    integrated_launcher = tools / "start-integrated.ps1"
    integrated_launcher.write_text("Write-Output integrated\n", encoding="utf-8")
    tika = tmp_path / "tika.jar"
    tika.write_bytes(b"tika")
    tika_hash = tmp_path / "tika.sha512"
    tika_hash.write_text("hash\n", encoding="utf-8")
    commit = _init_repo(tmp_path)
    output = tmp_path / "output" / "week6" / "lightweight.zip"
    staging = tmp_path / "output" / "week6" / ".staging"
    return (
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
            "-JavaRuntimeDir",
            str(java_runtime),
            "-ModelRoot",
            str(models),
            "-ModelManifestPath",
            str(manifest),
            "-TikaJar",
            str(tika),
            "-TikaChecksumFile",
            str(tika_hash),
            "-MvpLauncher",
            str(mvp_launcher),
            "-IntegratedLauncher",
            str(integrated_launcher),
            "-OutputZip",
            str(output),
            "-StagingRoot",
            str(staging),
            "-PackageProfile",
            "lightweight",
            "-JlinkExecutable",
            str(java_runtime / "bin" / "jlink.ps1"),
            "-ArchiveSizeLimitBytes",
            str(archive_size_limit_bytes),
        ],
        output,
        staging,
    )


def test_integrated_launcher_allows_cold_model_startup() -> None:
    script = INTEGRATED_SCRIPT.read_text(encoding="utf-8")
    assert "[int]$ReadyTimeoutSeconds = 600" in script


def test_integrated_launcher_cleans_backend_process_tree() -> None:
    script = INTEGRATED_SCRIPT.read_text(encoding="utf-8")
    assert "function Stop-OwnedProcessTree" in script
    assert "Stop-OwnedProcessTree -RootProcess $backendProcess" in script


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
@pytest.mark.parametrize("jlink_exit_code", [23, 0], ids=["nonzero", "missing_java"])
def test_build_portable_java_removes_partial_output_on_failure(
    tmp_path: Path, jlink_exit_code: int
) -> None:
    java_home = tmp_path / "java-home"
    (java_home / "jmods").mkdir(parents=True)
    fake_jlink = java_home / "bin" / "jlink.cmd"
    fake_jlink.parent.mkdir()
    fake_jlink.write_text(
        "@echo off\r\n"
        "set \"output=\"\r\n"
        ":parse\r\n"
        "if \"%~1\"==\"\" exit /b 99\r\n"
        "if /I \"%~1\"==\"--output\" goto create\r\n"
        "shift\r\n"
        "goto parse\r\n"
        ":create\r\n"
        "set \"output=%~2\"\r\n"
        "mkdir \"%output%\\bin\" >nul\r\n"
        "> \"%output%\\partial.txt\" echo partial\r\n"
        f"exit /b {jlink_exit_code}\r\n",
        encoding="utf-8",
    )
    output = tmp_path / "portable-java"
    sibling = tmp_path / "keep-sibling"
    sibling.mkdir()
    sentinel = sibling / "sentinel.txt"
    sentinel.write_bytes(b"keep")

    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_PORTABLE_JAVA_SCRIPT),
            "-OutputDirectory",
            str(output),
            "-JavaHome",
            str(java_home),
            "-JlinkExecutable",
            str(fake_jlink),
        ],
        tmp_path,
    )

    assert result.returncode != 0
    assert not output.exists()
    assert sentinel.read_bytes() == b"keep"


def _security_audit_fixtures(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    package = tmp_path / "stable.zip"
    with ZipFile(package, "w") as archive:
        archive.writestr("app/PACKAGE_MANIFEST.json", '{"source_commit":"' + "a" * 40 + '"}\n')
        archive.writestr("app/frontend/data/flutter_assets/AssetManifest.bin", b"asset")
        archive.writestr(
            "app/runtime/python/Lib/site-packages/timm/data/config.py",
            b"runtime library data",
        )
        archive.writestr(
            "app/runtime/python/Lib/site-packages/certifi/cacert.pem",
            b"-----BEGIN CERTIFICATE-----\npublic trust anchor\n",
        )
        archive.writestr(
            "app/runtime/python/Lib/site-packages/opentelemetry/proto/logs/v1/logs_pb2.py",
            b"generated protocol source",
        )
        archive.writestr(
            "app/runtime/python/Lib/site-packages/huggingface_hub/constants.py",
            b'HUGGINGFACE_HEADER_X_XET_ACCESS_TOKEN = "X-Xet-Access-Token"\n',
        )
        archive.writestr(
            "app/runtime/python/Lib/site-packages/chromadb/test/test_client.py",
            b'api_key="incorrect_api_key"\n',
        )
    offline = tmp_path / "offline.json"
    offline.write_text('{"status":"PASS"}\n', encoding="utf-8")
    security_tests = tmp_path / "security-tests.json"
    security_tests.write_text(
        json.dumps(
            {
                "status": "PASS",
                "checks": {
                    "path_traversal": "PASS",
                    "reparse_point_escape": "PASS",
                },
            }
        ),
        encoding="utf-8",
    )
    network_probe = tmp_path / "network-probe.json"
    network_probe.write_text(
        json.dumps(
            {
                "status": "PASS",
                "blocked": True,
                "target": "https://example.invalid/week6-egress-probe",
            }
        ),
        encoding="utf-8",
    )
    return package, offline, security_tests, network_probe


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_security_audit_rejects_unenforced_network_isolation(tmp_path: Path) -> None:
    package, offline, security_tests, network_probe = _security_audit_fixtures(tmp_path)
    output = tmp_path / "security.json"
    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SECURITY_AUDIT_SCRIPT),
            "-ProcessIds",
            "999999",
            "-PackagePath",
            str(package),
            "-OfflineE2EJson",
            str(offline),
            "-SecurityTestJson",
            str(security_tests),
            "-NetworkProbeJson",
            str(network_probe),
            "-OutputPath",
            str(output),
            "-SampleSeconds",
            "1",
            "-MinimumSampleSeconds",
            "1",
        ],
        tmp_path,
    )

    assert result.returncode != 0
    record = json.loads(output.read_text(encoding="utf-8-sig"))
    assert record["network_isolation"]["enforced"] is False
    assert record["checks"]["network_isolation"] == "FAIL"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_security_audit_emits_gate_ready_full_security_evidence(tmp_path: Path) -> None:
    package, offline, security_tests, network_probe = _security_audit_fixtures(tmp_path)
    output = tmp_path / "security.json"
    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SECURITY_AUDIT_SCRIPT),
            "-ProcessIds",
            "999999",
            "-PackagePath",
            str(package),
            "-OfflineE2EJson",
            str(offline),
            "-SecurityTestJson",
            str(security_tests),
            "-NetworkProbeJson",
            str(network_probe),
            "-OutputPath",
            str(output),
            "-IsolationMethod",
            "process-network-deny",
            "-NetworkIsolationEnforced",
            "-SampleSeconds",
            "1",
            "-MinimumSampleSeconds",
            "1",
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(output.read_text(encoding="utf-8-sig"))
    assert record["status"] == "PASS"
    assert record["network_isolation"] == {
        "enforced": True,
        "method": "process-network-deny",
        "sample_seconds": 1,
        "probe_blocked": True,
    }
    assert record["checks"]["offline_e2e"] == "PASS"
    assert record["checks"]["non_loopback_connections"] == "PASS"
    assert record["checks"]["path_traversal"] == "PASS"
    assert record["checks"]["reparse_point_escape"] == "PASS"
    assert record["checks"]["package_audit"] == "PASS"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_security_audit_rejects_packaged_user_state(tmp_path: Path) -> None:
    package, offline, security_tests, network_probe = _security_audit_fixtures(tmp_path)
    with ZipFile(package, "a") as archive:
        archive.writestr(
            "app/third_party/example.xcodeproj/xcuserdata/user.xcuserdatad/"
            "UserInterfaceState.xcuserstate",
            b"user state",
        )
        archive.writestr("app/data/index.sqlite", b"user index")
        archive.writestr(
            "app/backend/src/content_retrieval/settings.py",
            b'api_key = "sk-live-week6-secret-value"\n',
        )
    output = tmp_path / "security.json"
    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SECURITY_AUDIT_SCRIPT),
            "-ProcessIds",
            "999999",
            "-PackagePath",
            str(package),
            "-OfflineE2EJson",
            str(offline),
            "-SecurityTestJson",
            str(security_tests),
            "-NetworkProbeJson",
            str(network_probe),
            "-OutputPath",
            str(output),
            "-IsolationMethod",
            "process-network-deny",
            "-NetworkIsolationEnforced",
            "-SampleSeconds",
            "1",
            "-MinimumSampleSeconds",
            "1",
        ],
        tmp_path,
    )

    assert result.returncode != 0
    record = json.loads(output.read_text(encoding="utf-8-sig"))
    assert record["checks"]["package_audit"] == "FAIL"
    forbidden = next(
        item for item in record["check_details"] if item["id"] == "forbidden_package_entries"
    )
    assert any("xcuserdata" in item for item in forbidden["actual"])
    assert "app/data/index.sqlite" in forbidden["actual"]
    sensitive = next(
        item for item in record["check_details"] if item["id"] == "package_sensitive_content"
    )
    assert "app/backend/src/content_retrieval/settings.py" in sensitive["actual"]


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
@pytest.mark.parametrize(
    "package_profile",
    ["complete", "lightweight"],
    ids=["complete_profile", "lightweight_profile"],
)
def test_package_stable_build_uses_whitelist_and_records_commit(
    tmp_path: Path, package_profile: str
) -> None:
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
    java_runtime = tmp_path / "java-runtime"
    if package_profile == "complete":
        (java_runtime / "bin").mkdir(parents=True)
        (java_runtime / "bin" / "java.exe").write_bytes(b"java")
    else:
        _add_lightweight_runtime_fixture(runtime, java_runtime)
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
    third_party = tmp_path / "third-party-source"
    (third_party / "safe").mkdir(parents=True)
    (third_party / "safe" / "LICENSE").write_text("license\n", encoding="utf-8")
    user_state = (
        third_party
        / "ios_app"
        / "Example.xcodeproj"
        / "xcuserdata"
        / "developer.xcuserdatad"
    )
    user_state.mkdir(parents=True)
    (user_state / "UserInterfaceState.xcuserstate").write_bytes(b"private UI state")
    commit = _init_repo(tmp_path)
    output = tmp_path / "output" / "week6" / "stable.zip"

    profile_arguments: list[str] = []
    if package_profile == "lightweight":
        profile_arguments = [
            "-PackageProfile",
            "lightweight",
            "-JlinkExecutable",
            str(java_runtime / "bin" / "jlink.ps1"),
        ]

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
            "-JavaRuntimeDir",
            str(java_runtime),
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
            "-ThirdPartySourceDir",
            str(third_party),
            "-OutputZip",
            str(output),
            *profile_arguments,
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Archive bytes: {output.stat().st_size}" in result.stdout
    with ZipFile(output) as archive:
        names = {name.replace("\\", "/") for name in archive.namelist()}
        assert "app/frontend/content_retrieval_app.exe" in names
        assert "app/backend/src/app.py" in names
        assert "app/runtime/python/python.exe" in names
        assert "app/runtime/java/bin/java.exe" in names
        assert "app/内容检索系统.exe" in names
        assert "app/models/weights.bin" in names
        assert "app/PACKAGE_MANIFEST.json" in names
        assert not any("private-index" in name for name in names)
        assert not any(name.endswith("user.log") for name in names)
        package_manifest = json.loads(archive.read("app/PACKAGE_MANIFEST.json"))
        assert package_manifest["source_commit"] == commit
        assert package_manifest["one_click_launcher"] == "内容检索系统.exe"
        if package_profile == "complete":
            assert package_manifest["java_runtime_mode"] == "bundled"
            assert "app/third_party/mobileclip-src/safe/LICENSE" in names
            assert not any("xcuserdata" in name.lower() for name in names)
            assert not any(name.lower().endswith(".xcuserstate") for name in names)
        else:
            profile = LIGHTWEIGHT_PROFILE
            assert (
                "app/runtime/python/Lib/site-packages/"
                "sentence_transformers/__init__.py"
            ) in names
            assert "app/runtime/python/Lib/site-packages/torch/lib/torch_cpu.dll" in names
            assert "app/runtime/java/bin/java.exe" in names
            for package in profile["python_remove_packages"]:
                license_filename = LIGHTWEIGHT_LICENSE_FILENAMES.get(package, "LICENSE")
                assert not any(f"/site-packages/{package}/" in name for name in names)
                assert (
                    f"app/runtime/python/Lib/site-packages/{package}-1.0.dist-info/"
                    f"licenses/{license_filename}"
                ) not in names
                excluded_license = (
                    "app/licenses/excluded-python-components/"
                    f"{package}/{package}-1.0.dist-info/licenses/{license_filename}"
                )
                assert excluded_license in names
                assert archive.read(excluded_license) == f"{package} license\n".encode()
            duplicate_license = (
                "app/licenses/excluded-python-components/pyarrow/"
                "pyarrow-1.0.dist-info/vendor/LICENSE.txt"
            )
            assert duplicate_license in names
            assert archive.read(duplicate_license) == b"pyarrow nested license\n"
            collision_root = (
                "app/runtime/python/Lib/site-packages/pandas_2fa-1.0.dist-info/"
            )
            assert collision_root + "collision-sentinel.txt" in names
            assert (
                archive.read(collision_root + "collision-sentinel.txt")
                == b"keep collision"
            )
            assert collision_root + "LICENSE" in names
            assert archive.read(collision_root + "LICENSE") == b"pandas-2fa license\n"
            for directory_name in profile["python_remove_directory_names"]:
                assert (
                    "app/runtime/python/Lib/site-packages/sentence_transformers/"
                    f"{directory_name}/{directory_name}-marker.txt"
                ) not in names
            for extension in profile["python_remove_file_extensions"]:
                assert (
                    "app/runtime/python/Lib/site-packages/sentence_transformers/"
                    f"extension-marker{extension}"
                ) not in names
            for relative_tree in profile["python_remove_relative_trees"]:
                assert f"app/runtime/python/{relative_tree}/relative-tree-marker.txt" not in names
            assert "app/runtime/python/Lib/site-packages/torch/lib/torch_cpu.lib" not in names
            assert "app/runtime/python/Lib/site-packages/torch/include/torch.h" not in names
            assert "app/runtime/java/bin/jlink-arguments.txt" in names
            assert archive.read("app/runtime/java/bin/jlink-arguments.txt").decode(
                "utf-8"
            ) == (
                f"module_path={java_runtime / 'jmods'}\n"
                f"add_modules={','.join(profile['java_modules'])}"
            )
            assert package_manifest["package_profile"] == "lightweight"
            assert package_manifest["archive_size_limit_bytes"] == 1000000000
            assert package_manifest["pruning_policy_version"] == "1"
            assert package_manifest["java_runtime_mode"] == "jlink"
            assert package_manifest["excluded_runtime_components"] == profile[
                "python_remove_packages"
            ]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_lightweight_package_rejects_archive_at_or_above_limit(tmp_path: Path) -> None:
    command, output, staging = _lightweight_package_fixture(tmp_path)
    result = _run(command, tmp_path)

    assert result.returncode != 0
    assert "archive size limit" in (result.stdout + result.stderr).lower()
    assert not output.exists()
    assert not staging.exists() or not any(staging.iterdir())
    assert not list(output.parent.glob(".week6-*.zip"))


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_lightweight_package_replacement_preserves_existing_output_on_size_failure(
    tmp_path: Path,
) -> None:
    command, output, staging = _lightweight_package_fixture(tmp_path)
    sentinel = b"existing stable package"
    output.parent.mkdir(parents=True)
    output.write_bytes(sentinel)

    result = _run([*command, "-ReplaceExactTarget"], tmp_path)

    assert result.returncode != 0
    assert "archive size limit" in (result.stdout + result.stderr).lower()
    assert output.read_bytes() == sentinel
    assert not list(output.parent.glob(".week6-*.zip"))
    assert not staging.exists() or not any(staging.iterdir())


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
@pytest.mark.parametrize(
    ("archive_bytes", "expected_success"),
    [(127, True), (128, False), (129, False)],
    ids=["below_limit", "at_limit", "above_limit"],
)
def test_lightweight_archive_size_limit_includes_exact_boundary(
    tmp_path: Path, archive_bytes: int, expected_success: bool
) -> None:
    helper_path = str(REPOSITORY_ROOT / "tools" / "week6" / "lightweight_package.ps1").replace(
        "'", "''"
    )
    result = _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                f"& {{ . '{helper_path}'; Assert-LightweightArchiveSize "
                f"-ArchiveBytes {archive_bytes} -LimitBytes 128 }}"
            ),
        ],
        tmp_path,
    )

    if expected_success:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0
        assert (
            f"Lightweight archive size limit exceeded: {archive_bytes} bytes >= 128 bytes"
            in result.stdout + result.stderr
        )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_package_stable_build_expands_venv_into_portable_runtime(tmp_path: Path) -> None:
    release = tmp_path / "frontend-release"
    release.mkdir()
    (release / "content_retrieval_app.exe").write_bytes(b"app")
    backend = tmp_path / "backend"
    (backend / "src").mkdir(parents=True)
    (backend / "src" / "app.py").write_text("print('backend')\n", encoding="utf-8")
    (backend / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    (backend / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    base_runtime = tmp_path / "base-python"
    (base_runtime / "Lib").mkdir(parents=True)
    (base_runtime / "python.exe").write_bytes(b"portable-python")
    (base_runtime / "python310.dll").write_bytes(b"runtime-dll")
    (base_runtime / "Lib" / "os.py").write_text("# stdlib\n", encoding="utf-8")
    venv = tmp_path / "venv"
    site_packages = venv / "Lib" / "site-packages" / "example_dependency"
    site_packages.mkdir(parents=True)
    (site_packages / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    deep_runtime_file = (
        venv
        / "Lib"
        / "site-packages"
        / ("deep_dependency_" + "a" * 55)
        / ("generated_resources_" + "b" * 55)
        / ("runtime_payload_" + "c" * 55 + ".bin")
    )
    deep_runtime_file_extended = "\\\\?\\" + str(deep_runtime_file)
    os.makedirs(os.path.dirname(deep_runtime_file_extended), exist_ok=True)
    with open(deep_runtime_file_extended, "wb") as stream:
        stream.write(b"deep-runtime")
    (venv / "Scripts").mkdir()
    (venv / "Scripts" / "python.exe").write_bytes(b"venv-redirector")
    (venv / "pyvenv.cfg").write_text(f"home = {base_runtime}\n", encoding="utf-8")
    java_runtime = tmp_path / "java-runtime"
    (java_runtime / "bin").mkdir(parents=True)
    (java_runtime / "bin" / "java.exe").write_bytes(b"java")

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
    commit = _init_repo(tmp_path)
    output = tmp_path / "output" / "week6" / "portable.zip"
    staging = tmp_path / "output" / "week6" / ".staging"

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
            str(venv),
            "-JavaRuntimeDir",
            str(java_runtime),
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
            "-StagingRoot",
            str(staging),
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    with ZipFile(output) as archive:
        names = {name.replace("\\", "/") for name in archive.namelist()}
        assert "app/runtime/python/python.exe" in names
        assert "app/runtime/python/python310.dll" in names
        assert "app/runtime/python/Lib/os.py" in names
        assert "app/runtime/python/Lib/site-packages/example_dependency/__init__.py" in names
        assert any(name.endswith("runtime_payload_" + "c" * 55 + ".bin") for name in names)
        assert "app/runtime/python/pyvenv.cfg" not in names
        assert archive.read("app/runtime/python/python.exe") == b"portable-python"
    assert not staging.exists() or not any(staging.iterdir())


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
    java = tmp_path / "runtime" / "java" / "bin"
    java.mkdir(parents=True)
    (java / "java.exe").write_bytes(b"java")
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
    assert str(java / "java.exe") in result.stdout
