from __future__ import annotations

import subprocess
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility
    import tomli as tomllib


REPOSITORY = Path(__file__).resolve().parents[3]


def test_tracked_temp_tree_is_empty_and_only_reproducible_assets_are_relocated() -> None:
    tracked = set(
        subprocess.check_output(
            ["git", "ls-files"], cwd=REPOSITORY, text=True
        ).splitlines()
    )

    assert not {path for path in tracked if path.startswith("tmp/")}
    assert "docs/week2/assets/current-ingestion-sequence.png" in tracked
    assert {
        "tools/week2/build_reports.py",
        "tools/week2/tests/test_sequence_diagram.py",
        "tools/week3/build_reports.py",
    }.isdisjoint(tracked)


def test_root_gitignore_excludes_week8_generated_and_scratch_trees() -> None:
    rules = set((REPOSITORY / ".gitignore").read_text(encoding="utf-8").splitlines())

    assert {
        "/.tmp*/",
        "/output/",
        "/outputs/",
        "**/build/",
        "**/coverage/",
        "*.lcov",
        "/recordings/",
        "/docs/week8/evidence/report/rendered-*/",
    }.issubset(rules)


def test_cross_platform_shell_scripts_are_forced_to_lf() -> None:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(REPOSITORY),
            "check-attr",
            "eol",
            "--",
            "tools/week8/build_linux_release.sh",
            "tools/week8/start-integrated-linux.sh",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.stdout.splitlines() == [
        "tools/week8/build_linux_release.sh: eol: lf",
        "tools/week8/start-integrated-linux.sh: eol: lf",
    ]


def test_public_python_projects_do_not_require_machine_local_mobileclip_source() -> None:
    for project in ("backend", "model-tools"):
        pyproject = tomllib.loads(
            (REPOSITORY / project / "pyproject.toml").read_text(encoding="utf-8")
        )
        dependencies = pyproject["project"]["dependencies"]
        uv_sources = pyproject.get("tool", {}).get("uv", {}).get("sources", {})
        lockfile = (REPOSITORY / project / "uv.lock").read_text(encoding="utf-8")

        assert not any(
            dependency.partition(";")[0].strip().lower().startswith("mobileclip")
            for dependency in dependencies
        )
        assert "mobileclip" not in uv_sources
        assert "../third_party/mobileclip-src" not in lockfile


def test_backend_locks_torch_to_the_official_cpu_index() -> None:
    pyproject = tomllib.loads(
        (REPOSITORY / "backend/pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = pyproject["project"]["dependencies"]
    uv = pyproject["tool"]["uv"]
    indexes = uv["index"]
    lockfile = (REPOSITORY / "backend/uv.lock").read_text(encoding="utf-8")

    assert any(dependency.startswith("torch") for dependency in dependencies)
    assert uv["sources"]["torch"] == {"index": "pytorch-cpu"}
    assert {
        "name": "pytorch-cpu",
        "url": "https://download.pytorch.org/whl/cpu",
        "explicit": True,
    } in indexes
    assert 'registry = "https://download.pytorch.org/whl/cpu"' in lockfile
    assert 'name = "nvidia-' not in lockfile
    assert 'name = "cuda-' not in lockfile
    assert 'name = "triton"' not in lockfile


def test_public_repository_has_community_health_and_ci_files() -> None:
    required = {
        "CONTRIBUTING.md": ("uv sync --project backend --locked", "flutter test"),
        "CODE_OF_CONDUCT.md": ("行为准则", "举报"),
        "SECURITY.md": ("安全漏洞", "不要"),
        ".github/workflows/ci.yml": (
            "permissions:",
            "uv sync --project backend --locked",
            "flutter analyze --no-pub",
            "flutter test --no-pub",
        ),
    }

    for relative_path, markers in required.items():
        content = (REPOSITORY / relative_path).read_text(encoding="utf-8")
        assert all(marker in content for marker in markers)

    workflow = (REPOSITORY / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "download_models.py" not in workflow
    assert "download_mobileclip.py" not in workflow
