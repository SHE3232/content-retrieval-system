#!/usr/bin/env python3
"""Produce deterministic high-confidence unused-code findings for Week 8 cleanup."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

import vulture
from vulture.core import Vulture

HTTP_ROUTE_DECORATORS = frozenset({"delete", "get", "patch", "post", "put"})
PYDANTIC_VALIDATOR_DECORATORS = frozenset(
    {"field_validator", "model_validator", "root_validator", "validator"}
)
EXCLUDED_DIRECTORY_NAMES = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__"}
)


def _iter_python_files(paths: Iterable[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.add(path)
        elif path.is_dir():
            files.update(
                candidate
                for candidate in path.rglob("*.py")
                if candidate.is_file()
                and not EXCLUDED_DIRECTORY_NAMES.intersection(candidate.parts)
            )
    return sorted(files)


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _decorator_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _review_framework_callbacks(paths: Iterable[Path]) -> list[dict[str, object]]:
    exemptions: list[dict[str, object]] = []
    for path in _iter_python_files(paths):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                decorator_name = _decorator_name(decorator)
                terminal_name = decorator_name.rsplit(".", 1)[-1]
                is_route = "." in decorator_name and terminal_name in HTTP_ROUTE_DECORATORS
                is_validator = terminal_name in PYDANTIC_VALIDATOR_DECORATORS
                if not is_route and not is_validator:
                    continue
                exemptions.append(
                    {
                        "decorator": decorator_name,
                        "kind": "function",
                        "line": node.lineno,
                        "path": str(path),
                        "symbol": node.name,
                    }
                )
                break
    exemptions.sort(key=lambda item: (str(item["path"]), int(item["line"])))
    return exemptions


def audit_paths(paths: Iterable[Path], *, minimum_confidence: int = 80) -> dict[str, object]:
    """Return normalized Vulture findings for the supplied source paths."""

    resolved_paths = [Path(path).resolve() for path in paths]
    reviewed_exemptions = _review_framework_callbacks(resolved_paths)
    exempt_symbols = {
        (item["path"], item["line"], item["symbol"])
        for item in reviewed_exemptions
    }
    analyzer = Vulture()
    analyzer.scavenge(_iter_python_files(resolved_paths))
    findings = [
        {
            "confidence": item.confidence,
            "kind": item.typ,
            "line": item.first_lineno,
            "message": item.message,
            "path": str(Path(item.filename).resolve()),
            "symbol": item.name,
        }
        for item in analyzer.get_unused_code(min_confidence=minimum_confidence)
        if (
            str(Path(item.filename).resolve()),
            item.first_lineno,
            item.name,
        )
        not in exempt_symbols
    ]
    findings.sort(key=lambda finding: (str(finding["path"]), int(finding["line"])))
    return {"findings": findings, "reviewed_exemptions": reviewed_exemptions}


def _source_commit(repository: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()


def main(argv: list[str] | None = None) -> int:
    repository = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[
            repository / "backend" / "src",
            repository / "tools",
            repository / "model-tools",
            repository / "conversion-tools",
        ],
    )
    parser.add_argument("--minimum-confidence", type=int, default=80)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    resolved_paths = [path.resolve() for path in args.paths]
    report = audit_paths(resolved_paths, minimum_confidence=args.minimum_confidence)
    report.update(
        {
            "command": [str(Path(sys.executable).resolve()), *sys.argv[1:]],
            "minimum_confidence": args.minimum_confidence,
            "paths": [str(path) for path in resolved_paths],
            "source_commit": _source_commit(repository),
            "tool": {"name": "vulture", "version": vulture.__version__},
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
