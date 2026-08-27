from __future__ import annotations

from pathlib import Path
import subprocess


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
