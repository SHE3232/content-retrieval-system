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

V2_REMOVED_DISTRIBUTIONS = {
    "scipy",
    "scikit-learn",
    "joblib",
    "threadpoolctl",
    "lxml",
    "python-docx",
    "multiprocess",
    "dill",
    "pyreadline3",
}
V2_REMOVED_RELATIVE_TREES = {
    "Lib/site-packages/scipy.libs",
    "Lib/site-packages/sklearn",
    "Lib/site-packages/docx",
    "Lib/site-packages/pyarrow.libs",
    "Lib/site-packages/pandas.libs",
    "Lib/idlelib",
    "Lib/tkinter",
    "Lib/lib2to3",
    "tcl",
    "include",
}
V2_PRESERVED_RELATIVE_TREES = {
    "Lib/site-packages/torch/testing",
    "Lib/site-packages/torch/_numpy/testing",
    "Lib/site-packages/numpy/testing",
    "Lib/site-packages/numpy/_core/tests",
}
V2_REMOVED_RELATIVE_FILES = {
    "DLLs/_tkinter.pyd",
    "DLLs/tcl86t.dll",
    "DLLs/tk86t.dll",
    "Lib/site-packages/threadpoolctl.py",
}
V2_REMOVED_EXTENSIONS = {
    ".a",
    ".c",
    ".cmake",
    ".h",
    ".hpp",
    ".pxd",
    ".pxi",
    ".pyi",
    ".pyx",
}
SIMILARITY_RELATIVE_PATH = (
    "Lib/site-packages/sentence_transformers/util/similarity.py"
)
SIMILARITY_TOP_LEVEL_IMPORT = "from sklearn.metrics import pairwise_distances"
SIMILARITY_CALL_LINE = (
    '        dist = pairwise_distances(a_coo, b_coo, metric="manhattan")'
)
TENSOR_RELATIVE_PATH = "Lib/site-packages/sentence_transformers/util/tensor.py"
TENSOR_TOP_LEVEL_IMPORT = "from scipy.sparse import coo_matrix"
TENSOR_CALL_LINE = (
    "    return coo_matrix((values, (indices[0], indices[1])), shape=x.shape)"
)


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
    similarity = runtime / SIMILARITY_RELATIVE_PATH
    similarity.parent.mkdir(parents=True)
    similarity.write_bytes(
        (
            SIMILARITY_TOP_LEVEL_IMPORT
            + "\r\n\r\ndef manhattan_sim(a_coo, b_coo):\r\n"
            + SIMILARITY_CALL_LINE
            + "\r\n        return dist\r\n"
        ).encode("utf-8")
    )
    tensor = runtime / TENSOR_RELATIVE_PATH
    tensor.write_bytes(
        (
            TENSOR_TOP_LEVEL_IMPORT
            + "\r\n\r\ndef to_scipy_coo(x):\r\n"
            + "    x = x.coalesce()\r\n"
            + TENSOR_CALL_LINE
            + "\r\n"
        ).encode("utf-8")
    )
    (sentence_transformers / "inference.py").write_text(
        "def encode():\n    return 'ok'\n", encoding="utf-8"
    )
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

    for preserve_tree in V2_PRESERVED_RELATIVE_TREES:
        preserve_root = runtime / preserve_tree
        (preserve_root / "nested" / "testing").mkdir(parents=True, exist_ok=True)
        (preserve_root / "runtime.py").write_text(
            "RUNTIME = True\n", encoding="utf-8"
        )
        (preserve_root / "runtime.yaml").write_text(
            "runtime: required\n", encoding="utf-8"
        )
        (preserve_root / "nested" / "testing" / "runtime.py").write_text(
            "NESTED_RUNTIME = True\n", encoding="utf-8"
        )
        (preserve_root / "development.h").write_text(
            "// development only\n", encoding="utf-8"
        )

    for relative_file in profile.get("python_remove_relative_files", []):
        marker = runtime / relative_file
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_bytes(b"remove file")

    scipy = site_packages / "scipy"
    scipy.mkdir(exist_ok=True)
    (scipy / "_inference.py").write_text("# required runtime\n", encoding="utf-8")
    scipy_libs = site_packages / "scipy.libs"
    scipy_libs.mkdir(exist_ok=True)
    (scipy_libs / "libopenblas.dll").write_bytes(b"scipy-runtime")

    torch = site_packages / "torch"
    (torch / "lib").mkdir(parents=True)
    (torch / "lib" / "torch_cpu.dll").write_bytes(b"torch")
    (torch / "lib" / "torch_cpu.lib").write_bytes(b"symbols")
    (torch / "include").mkdir(exist_ok=True)
    (torch / "include" / "torch.h").write_text("// header\n", encoding="utf-8")

    for package in profile["python_remove_packages"]:
        component = site_packages / package
        component.mkdir(exist_ok=True)
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

    torchgen = site_packages / "torchgen"
    torchgen.mkdir(exist_ok=True)
    (torchgen / "__init__.py").write_text("RUNTIME = True\n", encoding="utf-8")
    (torchgen / "schemas.yaml").write_text("runtime: required\n", encoding="utf-8")
    (torchgen / "developer-header.h").write_text(
        "// development only\n", encoding="utf-8"
    )
    torchgen_metadata = site_packages / "torchgen-1.0.dist-info"
    torchgen_metadata.mkdir(exist_ok=True)
    (torchgen_metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: torchgen\nVersion: 1.0\n",
        encoding="utf-8",
    )

    sympy = site_packages / "sympy"
    (sympy / "tests").mkdir(parents=True, exist_ok=True)
    (sympy / "__init__.py").write_text("RUNTIME = True\n", encoding="utf-8")
    (sympy / "definitions.yaml").write_text(
        "runtime: required\n", encoding="utf-8"
    )
    (sympy / "tests" / "test_runtime.py").write_text(
        "# removable tests\n", encoding="utf-8"
    )
    (sympy / "cache.h").write_text("// removable header\n", encoding="utf-8")
    sympy_metadata = site_packages / "sympy-1.0.dist-info"
    sympy_metadata.mkdir(exist_ok=True)
    (sympy_metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: sympy\nVersion: 1.0\n",
        encoding="utf-8",
    )

    torch_metadata = site_packages / "torch-1.0.dist-info"
    (torch_metadata / "licenses" / "vendor" / "testing").mkdir(parents=True)
    (torch_metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: torch\nVersion: 1.0\n",
        encoding="utf-8",
    )
    (torch_metadata / "licenses" / "vendor" / "testing" / "LICENSE").write_bytes(
        b"torch testing license\x00\xff"
    )

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


def _invoke_lightweight_pruning(
    tmp_path: Path, app_root: Path, policy: dict[str, object]
) -> subprocess.CompletedProcess[str]:
    policy_path = tmp_path / "lightweight-policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    helper_path = str(
        REPOSITORY_ROOT / "tools" / "week6" / "lightweight_package.ps1"
    ).replace("'", "''")
    escaped_app_root = str(app_root).replace("'", "''")
    escaped_policy = str(policy_path).replace("'", "''")
    return _run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                f"& {{ . '{helper_path}'; "
                f"$policy = Get-Content -LiteralPath '{escaped_policy}' -Raw | ConvertFrom-Json; "
                f"Invoke-LightweightPythonPruning -AppRoot '{escaped_app_root}' -Policy $policy }}"
            ),
        ],
        tmp_path,
    )


def _minimal_v2_policy() -> dict[str, object]:
    return {
        "pruning_policy_version": "2",
        "python_remove_packages": [],
        "python_remove_directory_names": [],
        "python_remove_file_extensions": [],
        "python_remove_relative_trees": [],
        "python_preserve_relative_trees": [],
        "python_remove_relative_files": [],
        "python_lazy_import_patches": [
            {
                "relative_path": SIMILARITY_RELATIVE_PATH,
                "top_level_import": SIMILARITY_TOP_LEVEL_IMPORT,
                "call_line": SIMILARITY_CALL_LINE,
            },
            {
                "relative_path": TENSOR_RELATIVE_PATH,
                "top_level_import": TENSOR_TOP_LEVEL_IMPORT,
                "call_line": TENSOR_CALL_LINE,
            },
        ],
    }


def _write_similarity_fixture(app_root: Path, content: str) -> Path:
    similarity = app_root / "runtime" / "python" / SIMILARITY_RELATIVE_PATH
    similarity.parent.mkdir(parents=True)
    similarity.write_bytes(content.encode("utf-8"))
    return similarity


def _write_tensor_fixture(app_root: Path, content: str) -> Path:
    tensor = app_root / "runtime" / "python" / TENSOR_RELATIVE_PATH
    tensor.parent.mkdir(parents=True, exist_ok=True)
    tensor.write_bytes(content.encode("utf-8"))
    return tensor


def _write_valid_lazy_patch_fixtures(app_root: Path) -> tuple[Path, Path]:
    similarity = _write_similarity_fixture(
        app_root,
        SIMILARITY_TOP_LEVEL_IMPORT + "\n" + SIMILARITY_CALL_LINE + "\n",
    )
    tensor = _write_tensor_fixture(
        app_root,
        TENSOR_TOP_LEVEL_IMPORT + "\n" + TENSOR_CALL_LINE + "\n",
    )
    return similarity, tensor


def test_lightweight_profile_v2_declares_exact_inference_pruning() -> None:
    profile = LIGHTWEIGHT_PROFILE

    assert profile["pruning_policy_version"] == "2"
    assert V2_REMOVED_DISTRIBUTIONS <= set(profile["python_remove_packages"])
    assert V2_REMOVED_RELATIVE_TREES <= set(profile["python_remove_relative_trees"])
    assert set(profile["python_preserve_relative_trees"]) == V2_PRESERVED_RELATIVE_TREES
    assert V2_REMOVED_RELATIVE_FILES == set(profile["python_remove_relative_files"])
    assert V2_REMOVED_EXTENSIONS <= set(profile["python_remove_file_extensions"])
    assert profile["python_lazy_import_patches"] == [
        {
            "relative_path": SIMILARITY_RELATIVE_PATH,
            "top_level_import": SIMILARITY_TOP_LEVEL_IMPORT,
            "call_line": SIMILARITY_CALL_LINE,
        },
        {
            "relative_path": TENSOR_RELATIVE_PATH,
            "top_level_import": TENSOR_TOP_LEVEL_IMPORT,
            "call_line": TENSOR_CALL_LINE,
        },
    ]
    serialized_removals = json.dumps(
        {
            "packages": profile["python_remove_packages"],
            "trees": profile["python_remove_relative_trees"],
            "files": profile["python_remove_relative_files"],
        }
    ).lower()
    assert "scipy" in profile["python_remove_packages"]
    assert "Lib/site-packages/scipy.libs" in profile["python_remove_relative_trees"]
    assert "sympy" not in serialized_removals
    assert "torchgen" not in serialized_removals


def test_lightweight_profile_preserves_torchgen_runtime_dependency() -> None:
    profile = LIGHTWEIGHT_PROFILE

    assert "torchgen" not in profile["python_remove_packages"]
    assert "sympy" not in profile["python_remove_packages"]
    assert all(
        "torchgen" not in relative_tree.lower()
        for relative_tree in profile["python_remove_relative_trees"]
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_lightweight_pruning_v2_is_exact_and_preserves_runtime_boundaries(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    python_root = app_root / "runtime" / "python"
    site_packages = python_root / "Lib" / "site-packages"
    original_similarity = (
        SIMILARITY_TOP_LEVEL_IMPORT
        + "\r\n\r\ndef manhattan_sim(a_coo, b_coo):\r\n"
        + SIMILARITY_CALL_LINE
        + "\r\n        return dist\r\n"
    )
    similarity = _write_similarity_fixture(app_root, original_similarity)
    original_tensor = (
        TENSOR_TOP_LEVEL_IMPORT
        + "\r\n\r\ndef to_scipy_coo(x):\r\n"
        + TENSOR_CALL_LINE
        + "\r\n"
    )
    tensor = _write_tensor_fixture(app_root, original_tensor)

    import_names = {
        "scipy": "scipy",
        "scikit-learn": "sklearn",
        "joblib": "joblib",
        "threadpoolctl": None,
        "lxml": "lxml",
        "python-docx": "docx",
        "multiprocess": "multiprocess",
        "dill": "dill",
        "pyreadline3": "pyreadline3",
    }
    license_payloads: dict[str, bytes] = {}
    for distribution, import_name in import_names.items():
        if import_name is not None:
            package_dir = site_packages / import_name
            package_dir.mkdir(parents=True, exist_ok=True)
            (package_dir / "runtime-marker.py").write_text(
                "# removed distribution\n", encoding="utf-8"
            )
        metadata = site_packages / f"{distribution}-9.9.dist-info"
        metadata.mkdir(parents=True)
        (metadata / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: 9.9\n",
            encoding="utf-8",
        )
        payload = b"\x00exact-" + distribution.encode("ascii") + b"-license\xff"
        license_payloads[distribution] = payload
        (metadata / "licenses").mkdir()
        (metadata / "licenses" / "LICENSE.bin").write_bytes(payload)

    for relative_tree in V2_REMOVED_RELATIVE_TREES:
        marker = python_root / relative_tree / "remove-me.dat"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_bytes(b"remove tree")
    for relative_file in V2_REMOVED_RELATIVE_FILES:
        marker = python_root / relative_file
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_bytes(b"remove file")
    for extension in V2_REMOVED_EXTENSIONS:
        marker = site_packages / "sentence_transformers" / f"dev-only{extension}"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_bytes(b"remove extension")

    preserved_files = {
        site_packages / "sentence_transformers" / "inference.py": b"required code",
        site_packages / "torch" / "lib" / "torch_cpu.dll": b"required torch dll",
        app_root / "models" / "weights.bin": b"required model",
        app_root / "tools" / "tika" / "tika.jar": b"required tika",
    }
    for path, payload in preserved_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    policy = _minimal_v2_policy()
    policy["python_remove_packages"] = sorted(V2_REMOVED_DISTRIBUTIONS)
    policy["python_remove_relative_trees"] = sorted(V2_REMOVED_RELATIVE_TREES)
    policy["python_remove_relative_files"] = sorted(V2_REMOVED_RELATIVE_FILES)
    policy["python_remove_file_extensions"] = sorted(V2_REMOVED_EXTENSIONS)
    result = _invoke_lightweight_pruning(tmp_path, app_root, policy)

    assert result.returncode == 0, result.stdout + result.stderr
    patched = similarity.read_bytes()
    similarity_lines = patched.decode("utf-8").splitlines()
    assert similarity_lines.count(SIMILARITY_TOP_LEVEL_IMPORT) == 0
    assert similarity_lines.count("        " + SIMILARITY_TOP_LEVEL_IMPORT) == 1
    assert not patched.startswith(b"\xef\xbb\xbf")
    assert b"\n" not in patched.replace(b"\r\n", b"")
    patched_tensor = tensor.read_bytes()
    tensor_lines = patched_tensor.decode("utf-8").splitlines()
    assert tensor_lines.count(TENSOR_TOP_LEVEL_IMPORT) == 0
    assert tensor_lines.count("    " + TENSOR_TOP_LEVEL_IMPORT) == 1

    for distribution, import_name in import_names.items():
        if import_name is not None:
            assert not (site_packages / import_name).exists()
        assert not (site_packages / f"{distribution}-9.9.dist-info").exists()
        preserved_license = (
            app_root
            / "licenses"
            / "excluded-python-components"
            / distribution
            / f"{distribution}-9.9.dist-info"
            / "licenses"
            / "LICENSE.bin"
        )
        assert preserved_license.read_bytes() == license_payloads[distribution]
    for relative_tree in V2_REMOVED_RELATIVE_TREES:
        assert not (python_root / relative_tree).exists()
    for relative_file in V2_REMOVED_RELATIVE_FILES:
        assert not (python_root / relative_file).exists()
    for extension in V2_REMOVED_EXTENSIONS:
        assert not (
            site_packages / "sentence_transformers" / f"dev-only{extension}"
        ).exists()
    for path, payload in preserved_files.items():
        assert path.read_bytes() == payload


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
@pytest.mark.parametrize(
    "similarity_content",
    [
        None,
        SIMILARITY_CALL_LINE + "\n",
        SIMILARITY_TOP_LEVEL_IMPORT + "\n" + SIMILARITY_TOP_LEVEL_IMPORT + "\n" + SIMILARITY_CALL_LINE + "\n",
        SIMILARITY_TOP_LEVEL_IMPORT + "\n",
        SIMILARITY_TOP_LEVEL_IMPORT + "\n" + SIMILARITY_CALL_LINE + "\n" + SIMILARITY_CALL_LINE + "\n",
    ],
    ids=["missing_target", "missing_import", "duplicate_import", "missing_call", "duplicate_call"],
)
def test_lightweight_lazy_import_patch_fails_closed_before_pruning(
    tmp_path: Path, similarity_content: str | None
) -> None:
    app_root = tmp_path / "app"
    sklearn = app_root / "runtime" / "python" / "Lib" / "site-packages" / "sklearn"
    sklearn.mkdir(parents=True)
    sentinel = sklearn / "keep-on-failure.py"
    sentinel.write_bytes(b"not pruned")
    similarity = None
    if similarity_content is not None:
        similarity = _write_similarity_fixture(app_root, similarity_content)
        original = similarity.read_bytes()
    _write_tensor_fixture(
        app_root, TENSOR_TOP_LEVEL_IMPORT + "\n" + TENSOR_CALL_LINE + "\n"
    )
    policy = _minimal_v2_policy()
    policy["python_remove_packages"] = ["scikit-learn"]
    policy["python_remove_relative_trees"] = ["Lib/site-packages/sklearn"]

    result = _invoke_lightweight_pruning(tmp_path, app_root, policy)

    assert result.returncode != 0
    assert "lazy import patch" in (result.stdout + result.stderr).lower()
    assert sentinel.read_bytes() == b"not pruned"
    if similarity is not None:
        assert similarity.read_bytes() == original


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_tensor_lazy_import_patch_fails_closed_before_any_patch_or_pruning(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    similarity = _write_similarity_fixture(
        app_root,
        SIMILARITY_TOP_LEVEL_IMPORT + "\n" + SIMILARITY_CALL_LINE + "\n",
    )
    tensor = _write_tensor_fixture(app_root, TENSOR_TOP_LEVEL_IMPORT + "\n")
    similarity_before = similarity.read_bytes()
    tensor_before = tensor.read_bytes()
    scipy = app_root / "runtime" / "python" / "Lib" / "site-packages" / "scipy"
    scipy.mkdir(parents=True)
    sentinel = scipy / "keep-on-failure.py"
    sentinel.write_bytes(b"not pruned")
    policy = _minimal_v2_policy()
    policy["python_remove_packages"] = ["scipy"]

    result = _invoke_lightweight_pruning(tmp_path, app_root, policy)

    assert result.returncode != 0
    assert "lazy import patch" in (result.stdout + result.stderr).lower()
    assert similarity.read_bytes() == similarity_before
    assert tensor.read_bytes() == tensor_before
    assert sentinel.read_bytes() == b"not pruned"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_directory_name_pruning_preserves_runtime_trees_case_insensitively(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    _write_valid_lazy_patch_fixtures(app_root)
    python_root = app_root / "runtime" / "python"
    preserved_runtime_files: list[Path] = []
    preserved_headers: list[Path] = []
    for relative_tree in V2_PRESERVED_RELATIVE_TREES:
        preserve_root = python_root / relative_tree
        nested_testing = preserve_root / "nested" / "testing"
        nested_testing.mkdir(parents=True)
        runtime_file = nested_testing / "runtime.py"
        runtime_file.write_bytes(b"required runtime")
        header = nested_testing / "development.h"
        header.write_bytes(b"remove extension")
        preserved_runtime_files.append(runtime_file)
        preserved_headers.append(header)
    ordinary_tests = (
        python_root / "Lib" / "site-packages" / "ordinary" / "tests"
    )
    ordinary_tests.mkdir(parents=True)
    (ordinary_tests / "remove.py").write_bytes(b"remove ordinary tests")
    policy = _minimal_v2_policy()
    policy["python_remove_directory_names"] = ["tests", "testing"]
    policy["python_remove_file_extensions"] = [".h"]
    policy["python_preserve_relative_trees"] = [
        relative_tree.upper() for relative_tree in V2_PRESERVED_RELATIVE_TREES
    ]

    result = _invoke_lightweight_pruning(tmp_path, app_root, policy)

    assert result.returncode == 0, result.stdout + result.stderr
    assert all(path.read_bytes() == b"required runtime" for path in preserved_runtime_files)
    assert all(not path.exists() for path in preserved_headers)
    assert not ordinary_tests.exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_directory_name_pruning_does_not_enter_package_metadata_trees(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    _write_valid_lazy_patch_fixtures(app_root)
    site_packages = (
        app_root / "runtime" / "python" / "Lib" / "site-packages"
    )
    metadata_licenses = [
        site_packages
        / "torch-1.0.dist-info"
        / "licenses"
        / "vendor"
        / "testing"
        / "LICENSE",
        site_packages / "torch_legacy.egg-info" / "licenses" / "tests" / "LICENSE",
    ]
    for index, license_path in enumerate(metadata_licenses):
        license_path.parent.mkdir(parents=True)
        license_path.write_bytes(b"exact metadata license " + bytes([index]))
    escape_directory = site_packages / "torch.dist-info-escape" / "testing"
    escape_directory.mkdir(parents=True)
    (escape_directory / "remove.py").write_bytes(b"not metadata")
    policy = _minimal_v2_policy()
    policy["python_remove_directory_names"] = ["tests", "testing"]

    result = _invoke_lightweight_pruning(tmp_path, app_root, policy)

    assert result.returncode == 0, result.stdout + result.stderr
    for index, license_path in enumerate(metadata_licenses):
        assert license_path.read_bytes() == b"exact metadata license " + bytes([index])
    assert not escape_directory.exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_preserve_tree_policy_rejects_path_traversal_before_patching(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    similarity, tensor = _write_valid_lazy_patch_fixtures(app_root)
    similarity_before = similarity.read_bytes()
    tensor_before = tensor.read_bytes()
    outside = app_root / "outside"
    outside.mkdir(parents=True)
    (outside / "keep.py").write_bytes(b"keep outside")
    policy = _minimal_v2_policy()
    policy["python_preserve_relative_trees"] = ["../../outside"]

    result = _invoke_lightweight_pruning(tmp_path, app_root, policy)

    assert result.returncode != 0
    assert "escapes staging root" in (result.stdout + result.stderr).lower()
    assert similarity.read_bytes() == similarity_before
    assert tensor.read_bytes() == tensor_before
    assert (outside / "keep.py").read_bytes() == b"keep outside"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
@pytest.mark.parametrize("unsafe_kind", ["traversal", "directory_as_file"])
def test_lightweight_relative_file_removal_rejects_unsafe_targets(
    tmp_path: Path, unsafe_kind: str
) -> None:
    app_root = tmp_path / "app"
    _write_valid_lazy_patch_fixtures(app_root)
    policy = _minimal_v2_policy()
    if unsafe_kind == "traversal":
        outside = app_root / "outside.txt"
        outside.write_bytes(b"keep outside")
        policy["python_remove_relative_files"] = ["../../outside.txt"]
    else:
        outside = (
            app_root
            / "runtime"
            / "python"
            / "DLLs"
            / "_tkinter.pyd"
        )
        outside.mkdir(parents=True)
        (outside / "keep.txt").write_bytes(b"keep directory")
        policy["python_remove_relative_files"] = ["DLLs/_tkinter.pyd"]

    result = _invoke_lightweight_pruning(tmp_path, app_root, policy)

    assert result.returncode != 0
    assert outside.exists()


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
        complete_sentinel = runtime / "Lib" / "site-packages" / "sklearn" / "keep.py"
        complete_sentinel.parent.mkdir(parents=True)
        complete_sentinel.write_text("# complete profile keeps runtime\n", encoding="utf-8")
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
            assert "app/runtime/python/Lib/site-packages/sklearn/keep.py" in names
            assert "app/third_party/mobileclip-src/safe/LICENSE" in names
            assert not any("xcuserdata" in name.lower() for name in names)
            assert not any(name.lower().endswith(".xcuserstate") for name in names)
        else:
            profile = LIGHTWEIGHT_PROFILE
            assert (
                "app/runtime/python/Lib/site-packages/"
                "sentence_transformers/__init__.py"
            ) in names
            similarity_name = (
                "app/runtime/python/Lib/site-packages/"
                "sentence_transformers/util/similarity.py"
            )
            patched_similarity = archive.read(similarity_name)
            similarity_lines = patched_similarity.decode("utf-8").splitlines()
            assert similarity_lines.count(SIMILARITY_TOP_LEVEL_IMPORT) == 0
            assert (
                similarity_lines.count("        " + SIMILARITY_TOP_LEVEL_IMPORT)
                == 1
            )
            tensor_name = (
                "app/runtime/python/Lib/site-packages/"
                "sentence_transformers/util/tensor.py"
            )
            patched_tensor = archive.read(tensor_name)
            tensor_lines = patched_tensor.decode("utf-8").splitlines()
            assert tensor_lines.count(TENSOR_TOP_LEVEL_IMPORT) == 0
            assert tensor_lines.count("    " + TENSOR_TOP_LEVEL_IMPORT) == 1
            assert (
                "app/runtime/python/Lib/site-packages/"
                "sentence_transformers/inference.py"
            ) in names
            assert not any(
                name.startswith("app/runtime/python/Lib/site-packages/scipy/")
                for name in names
            )
            assert not any(
                name.startswith("app/runtime/python/Lib/site-packages/scipy.libs/")
                for name in names
            )
            assert "app/runtime/python/Lib/site-packages/torch/lib/torch_cpu.dll" in names
            assert "app/runtime/python/Lib/site-packages/torchgen/__init__.py" in names
            assert "app/runtime/python/Lib/site-packages/torchgen/schemas.yaml" in names
            assert (
                "app/runtime/python/Lib/site-packages/torchgen/developer-header.h"
                not in names
            )
            torchgen_metadata = (
                "app/runtime/python/Lib/site-packages/torchgen-1.0.dist-info/METADATA"
            )
            assert torchgen_metadata in names
            assert "Name: torchgen" in archive.read(torchgen_metadata).decode(
                "utf-8"
            ).splitlines()
            assert "app/runtime/python/Lib/site-packages/sympy/__init__.py" in names
            assert "app/runtime/python/Lib/site-packages/sympy/definitions.yaml" in names
            assert "app/runtime/python/Lib/site-packages/sympy/cache.h" not in names
            assert not any(
                name.startswith("app/runtime/python/Lib/site-packages/sympy/tests/")
                for name in names
            )
            sympy_metadata = (
                "app/runtime/python/Lib/site-packages/sympy-1.0.dist-info/METADATA"
            )
            assert sympy_metadata in names
            assert "Name: sympy" in archive.read(sympy_metadata).decode(
                "utf-8"
            ).splitlines()
            for preserve_tree in profile["python_preserve_relative_trees"]:
                preserve_root = f"app/runtime/python/{preserve_tree}"
                assert f"{preserve_root}/runtime.py" in names
                assert f"{preserve_root}/runtime.yaml" in names
                assert f"{preserve_root}/nested/testing/runtime.py" in names
                assert f"{preserve_root}/development.h" not in names
            torch_testing_license = (
                "app/runtime/python/Lib/site-packages/torch-1.0.dist-info/"
                "licenses/vendor/testing/LICENSE"
            )
            assert torch_testing_license in names
            assert archive.read(torch_testing_license) == b"torch testing license\x00\xff"
            assert archive.read("app/models/weights.bin") == b"weights"
            assert (
                archive.read("app/tools/tika/tika-server-standard-3.3.1.jar")
                == b"tika"
            )
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
            for relative_file in profile["python_remove_relative_files"]:
                assert f"app/runtime/python/{relative_file}" not in names
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
            assert package_manifest["pruning_policy_version"] == "2"
            assert package_manifest["java_runtime_mode"] == "jlink"
            assert package_manifest["excluded_runtime_components"] == profile[
                "python_remove_packages"
            ]
            assert "torchgen" not in package_manifest["excluded_runtime_components"]
            assert "sympy" not in package_manifest["excluded_runtime_components"]
            assert "scipy" in package_manifest["excluded_runtime_components"]


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
def test_lightweight_package_replacement_promotes_valid_archive(tmp_path: Path) -> None:
    command, output, staging = _lightweight_package_fixture(
        tmp_path, archive_size_limit_bytes=1_000_000
    )
    sentinel = b"existing stable package"
    output.parent.mkdir(parents=True)
    output.write_bytes(sentinel)

    result = _run([*command, "-ReplaceExactTarget"], tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert output.read_bytes() != sentinel
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert "app/PACKAGE_MANIFEST.json" in archive.namelist()
    assert not list(output.parent.glob(".week6-*.zip"))
    assert not staging.exists() or not any(staging.iterdir())


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_lightweight_package_jlink_failure_preserves_existing_output(
    tmp_path: Path,
) -> None:
    command, output, staging = _lightweight_package_fixture(tmp_path)
    jlink = Path(command[command.index("-JlinkExecutable") + 1])
    jlink.write_text("throw 'simulated jlink failure'\n", encoding="utf-8")
    _git(tmp_path, "add", "java-runtime/bin/jlink.ps1")
    _git(tmp_path, "commit", "-m", "simulate jlink failure")
    command[command.index("-SourceCommit") + 1] = _git(tmp_path, "rev-parse", "HEAD")
    sentinel = b"existing stable package"
    output.parent.mkdir(parents=True)
    output.write_bytes(sentinel)

    result = _run([*command, "-ReplaceExactTarget"], tmp_path)

    assert result.returncode != 0
    assert "simulated jlink failure" in (result.stdout + result.stderr).lower()
    assert output.read_bytes() == sentinel
    assert not list(output.parent.glob(".week6-*.zip"))
    assert not staging.exists() or not any(staging.iterdir())


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_package_stable_build_rejects_output_zip_directory(tmp_path: Path) -> None:
    command, output, staging = _lightweight_package_fixture(tmp_path)
    output.mkdir(parents=True)
    sentinel = output / "keep.txt"
    sentinel.write_bytes(b"keep")

    result = _run([*command, "-ReplaceExactTarget"], tmp_path)

    assert result.returncode != 0
    assert "output zip path is a directory" in (result.stdout + result.stderr).lower()
    assert sentinel.read_bytes() == b"keep"
    assert not staging.exists() or not any(staging.iterdir())


def test_package_stable_build_freezes_replacement_authorization() -> None:
    script = PACKAGE_SCRIPT.read_text(encoding="utf-8")

    assert "$targetExists = [System.IO.File]::Exists($absoluteOutput)" in script
    assert "$targetIsDirectory = [System.IO.Directory]::Exists($absoluteOutput)" in script
    assert "$replaceExistingTarget = $targetExists -and $ReplaceExactTarget.IsPresent" in script
    assert "if ($replaceExistingTarget)" in script
    assert "[System.IO.File]::Move($temporaryZip, $absoluteOutput)" in script


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
