from __future__ import annotations

import argparse
import csv
import io
import json
import re
import re
from pathlib import Path
from typing import Sequence


CSV_FIELDS = [
    "ecosystem",
    "environment",
    "name",
    "version",
    "dependency_type",
    "source",
    "license_expression",
    "evidence_url",
    "review_status",
    "redistribution",
    "notes",
]

PYTHON_LOCKS = (
    ("backend", Path("backend/uv.lock"), Path("backend/pyproject.toml")),
    (
        "conversion-tools",
        Path("conversion-tools/uv.lock"),
        Path("conversion-tools/pyproject.toml"),
    ),
    (
        "model-tools",
        Path("model-tools/uv.lock"),
        Path("model-tools/pyproject.toml"),
    ),
    (
        "demo-tools",
        Path("tools/demo/uv.lock"),
        Path("tools/demo/pyproject.toml"),
    ),
)

PYTHON_NAME_PATTERN = re.compile(r"[-_.]+")
PACKAGE_HEADER_PATTERN = re.compile(r'^name = "([^"]+)"$')
PACKAGE_VERSION_PATTERN = re.compile(r'^version = "([^"]+)"$')
UV_SOURCE_PATTERN = re.compile(
    r'^source = \{\s*([a-zA-Z0-9_-]+) = "([^"]+)"\s*\}$'
)
PUB_PACKAGE_PATTERN = re.compile(r"^  ([A-Za-z0-9_+.-]+):$")


def normalize_python_name(name: str) -> str:
    return PYTHON_NAME_PATTERN.sub("-", name).lower()


def _strip_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_uv_lock(path: Path) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "[[package]]":
            if current is not None:
                _append_complete_uv_package(packages, current, path)
            current = {}
            continue
        if current is None:
            continue

        name_match = PACKAGE_HEADER_PATTERN.match(line)
        if name_match:
            current["name"] = normalize_python_name(name_match.group(1))
            continue
        version_match = PACKAGE_VERSION_PATTERN.match(line)
        if version_match:
            current["version"] = version_match.group(1)
            continue
        source_match = UV_SOURCE_PATTERN.match(line)
        if source_match:
            source_type, source_value = source_match.groups()
            current["source"] = (
                source_value
                if source_type == "registry"
                else f"{source_type}:{source_value}"
            )

    if current is not None:
        _append_complete_uv_package(packages, current, path)
    return packages


def _append_complete_uv_package(
    packages: list[dict[str, str]],
    package: dict[str, str],
    path: Path,
) -> None:
    missing = [field for field in ("name", "version") if not package.get(field)]
    if missing:
        raise ValueError(f"{path}: package missing {', '.join(missing)}")
    package.setdefault("source", "unspecified")
    packages.append(package)


def parse_pubspec_lock(path: Path) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        header_match = PUB_PACKAGE_PATTERN.match(raw_line)
        if header_match:
            if current is not None:
                _append_complete_pub_package(packages, current, path)
            current = {"name": header_match.group(1)}
            continue
        if current is None:
            continue

        stripped = raw_line.strip()
        if stripped.startswith("dependency:"):
            dependency = _strip_yaml_scalar(stripped.split(":", 1)[1])
            current["dependency_type"] = dependency.replace(" ", "-")
        elif stripped.startswith("source:"):
            current["pub_source"] = _strip_yaml_scalar(stripped.split(":", 1)[1])
        elif stripped.startswith("version:"):
            current["version"] = _strip_yaml_scalar(stripped.split(":", 1)[1])
        elif stripped.startswith("url:"):
            current["source"] = _strip_yaml_scalar(stripped.split(":", 1)[1])

    if current is not None:
        _append_complete_pub_package(packages, current, path)
    return packages


def _append_complete_pub_package(
    packages: list[dict[str, str]],
    package: dict[str, str],
    path: Path,
) -> None:
    missing = [
        field
        for field in ("name", "version", "dependency_type")
        if not package.get(field)
    ]
    if missing:
        raise ValueError(f"{path}: package missing {', '.join(missing)}")
    pub_source = package.pop("pub_source", "unspecified")
    package.setdefault("source", "flutter-sdk" if pub_source == "sdk" else pub_source)
    packages.append(package)


def parse_direct_python_requirements(path: Path) -> tuple[set[str], set[str]]:
    if not path.is_file():
        return set(), set()

    main: set[str] = set()
    development: set[str] = set()
    section = ""
    active_target: set[str] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line
            active_target = None
            continue
        if section == "[project]" and line.startswith("dependencies") and "[" in line:
            active_target = main
            continue
        if section == "[dependency-groups]" and re.match(r"^[A-Za-z0-9_-]+\s*=\s*\[", line):
            active_target = development
            continue
        if active_target is None:
            continue
        if line.startswith("]"):
            active_target = None
            continue
        requirement_match = re.match(r'^["\']([A-Za-z0-9_.-]+)', line)
        if requirement_match:
            active_target.add(normalize_python_name(requirement_match.group(1)))

    return main, development


def _approval_map(approvals: dict[str, object]) -> dict[str, dict[str, str]]:
    raw_components = approvals.get("components")
    if not isinstance(raw_components, list):
        raise ValueError("approvals.components must be a list")

    mapped: dict[str, dict[str, str]] = {}
    for raw_component in raw_components:
        if not isinstance(raw_component, dict):
            raise ValueError("each approval component must be an object")
        component = {str(key): str(value) for key, value in raw_component.items()}
        key = component.get("key", "")
        if not key:
            raise ValueError("approval component is missing key")
        if key in mapped:
            raise ValueError(f"duplicate approval component: {key}")
        mapped[key] = component
    return mapped


def _reviewed_row(
    *,
    ecosystem: str,
    environment: str,
    package: dict[str, str],
    dependency_type: str,
    approval: dict[str, str],
) -> dict[str, str]:
    return {
        "ecosystem": ecosystem,
        "environment": environment,
        "name": package["name"],
        "version": package["version"],
        "dependency_type": dependency_type,
        "source": package["source"],
        "license_expression": approval.get("license_expression", ""),
        "evidence_url": approval.get("evidence_url", ""),
        "review_status": approval.get("review_status", ""),
        "redistribution": approval.get("redistribution", ""),
        "notes": approval.get("notes", ""),
    }


def build_inventory(
    repository: Path,
    approvals: dict[str, object],
) -> list[dict[str, str]]:
    approved = _approval_map(approvals)
    rows: list[dict[str, str]] = []
    missing_keys: set[str] = set()

    for environment, relative_lock, relative_project in PYTHON_LOCKS:
        lock = repository / relative_lock
        if not lock.is_file():
            continue
        direct_main, direct_dev = parse_direct_python_requirements(
            repository / relative_project
        )
        for package in parse_uv_lock(lock):
            key = f"python:{package['name']}@{package['version']}"
            approval = approved.get(key)
            if approval is None:
                missing_keys.add(key)
                continue
            if approval.get("review_status") == "project-owned":
                dependency_type = "project"
            elif package["name"] in direct_main:
                dependency_type = "direct-main"
            elif package["name"] in direct_dev:
                dependency_type = "direct-dev"
            else:
                dependency_type = "transitive"
            rows.append(
                _reviewed_row(
                    ecosystem="python",
                    environment=environment,
                    package=package,
                    dependency_type=dependency_type,
                    approval=approval,
                )
            )

    pub_lock = repository / "frontend/pubspec.lock"
    if pub_lock.is_file():
        for package in parse_pubspec_lock(pub_lock):
            key = f"dart:{package['name']}@{package['version']}"
            approval = approved.get(key)
            if approval is None:
                missing_keys.add(key)
                continue
            rows.append(
                _reviewed_row(
                    ecosystem="dart",
                    environment="frontend",
                    package=package,
                    dependency_type=package["dependency_type"],
                    approval=approval,
                )
            )

    if missing_keys:
        details = "; ".join(
            f"unreviewed component: {key}" for key in sorted(missing_keys)
        )
        raise ValueError(details)

    rows.sort(
        key=lambda row: (
            row["ecosystem"],
            row["environment"],
            row["name"],
            row["version"],
        )
    )
    return rows


def render_csv(rows: list[dict[str, str]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def write_csv(rows: list[dict[str, str]], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_csv(rows), encoding="utf-8", newline="")


def render_third_party_summary(repository: Path, rows: list[dict[str, str]]) -> str:
    project = repository / "tools/demo/pyproject.toml"
    dependencies = []
    for line in project.read_text(encoding="utf-8").splitlines():
        match = re.match(r'\s*"([A-Za-z0-9_.-]+)(?:[<>=!~;]|$)', line)
        if match and match.group(1).lower() in {"python-docx", "reportlab", "pillow", "pypdfium2"}:
            dependencies.append(match.group(1))
    return ("<!-- GENERATED-DEMO-TOOLS-START -->\n"
            "## 演示工具环境（自动生成）\n\n"
            f"四套 Python `uv.lock` 共 {len(rows)} 条环境记录。\n\n"
            "演示工具直接依赖：" + ", ".join(dependencies) + "。\n"
            "<!-- GENERATED-DEMO-TOOLS-END -->")


def sync_third_party_notices(repository: Path, rows: list[dict[str, str]]) -> None:
    path = repository / "THIRD_PARTY_NOTICES.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    start, end = "<!-- GENERATED-DEMO-TOOLS-START -->", "<!-- GENERATED-DEMO-TOOLS-END -->"
    block = render_third_party_summary(repository, rows)
    if start in text and end in text:
        text = re.sub(re.escape(start) + r".*?" + re.escape(end), block, text, flags=re.S)
    else:
        text += "\n\n" + block + "\n"
    path.write_text(text, encoding="utf-8")


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the reviewed license inventory.")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument(
        "--approvals",
        type=Path,
        default=Path("tools/compliance/approved-licenses.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/dependency-licenses.csv"),
    )
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    repository = args.repository.resolve()
    approvals_path = args.approvals
    if not approvals_path.is_absolute():
        approvals_path = repository / approvals_path
    output_path = args.output
    if not output_path.is_absolute():
        output_path = repository / output_path

    approvals = json.loads(approvals_path.read_text(encoding="utf-8"))
    rows = build_inventory(repository, approvals)
    rendered = render_csv(rows)
    if args.check:
        if not output_path.is_file() or output_path.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"license inventory is stale: {output_path}")
        print(f"{len(rows)} inventory rows verified")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8", newline="")
    sync_third_party_notices(repository, rows)
    print(f"wrote {len(rows)} inventory rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
