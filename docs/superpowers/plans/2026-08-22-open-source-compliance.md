# Open Source Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** License project-owned code under Apache-2.0, account for every locked dependency and material third-party asset, and make incomplete or restricted release inventories fail verification.

**Architecture:** A standard root license layer is separated from third-party notices and a machine-readable approval baseline. A standard-library Python tool parses the three uv locks and the Flutter lock, renders an auditable CSV, and compares every discovered component with the approved baseline. The Week 6 packager copies the legal files and their supporting inventory into both complete and lightweight archives.

**Tech Stack:** Python 3.10 standard library, pytest, PowerShell 7, Markdown, CSV, JSON, uv lockfiles, Flutter pub lockfile.

---

### Task 1: Lockfile inventory parser and coverage gate

**Files:**
- Create: `tools/compliance/tests/test_generate_license_inventory.py`
- Create: `tools/compliance/generate_license_inventory.py`
- Create: `tools/compliance/__init__.py`

- [ ] **Step 1: Write failing parser and missing-approval tests**

```python
from pathlib import Path

import pytest

from tools.compliance.generate_license_inventory import (
    build_inventory,
    parse_pubspec_lock,
    parse_uv_lock,
)


def test_parse_uv_lock_keeps_name_version_and_registry(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text(
        'version = 1\n\n[[package]]\nname = "demo"\nversion = "1.2.3"\n'
        'source = { registry = "https://pypi.org/simple" }\n',
        encoding="utf-8",
    )
    assert parse_uv_lock(lock) == [
        {
            "name": "demo",
            "version": "1.2.3",
            "source": "https://pypi.org/simple",
        }
    ]


def test_parse_pubspec_lock_keeps_dependency_kind(tmp_path: Path) -> None:
    lock = tmp_path / "pubspec.lock"
    lock.write_text(
        "packages:\n  http:\n    dependency: \"direct main\"\n"
        "    description:\n      name: http\n      url: \"https://pub.dev\"\n"
        "    source: hosted\n    version: \"1.6.0\"\n",
        encoding="utf-8",
    )
    assert parse_pubspec_lock(lock) == [
        {
            "name": "http",
            "version": "1.6.0",
            "source": "https://pub.dev",
            "dependency_type": "direct-main",
        }
    ]


def test_build_inventory_rejects_unapproved_locked_component(tmp_path: Path) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "uv.lock").write_text(
        '[[package]]\nname = "demo"\nversion = "1.2.3"\n'
        'source = { registry = "https://pypi.org/simple" }\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unreviewed component: python:demo@1.2.3"):
        build_inventory(tmp_path, {"components": []})
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/compliance/tests/test_generate_license_inventory.py -q
```

Expected: collection fails because `tools.compliance.generate_license_inventory` does not exist.

- [ ] **Step 3: Implement line-oriented parsers and inventory matching**

Implement these public functions in `generate_license_inventory.py`: `parse_uv_lock(path: Path) -> list[dict[str, str]]`, `parse_pubspec_lock(path: Path) -> list[dict[str, str]]`, `build_inventory(repository: Path, approvals: dict[str, object]) -> list[dict[str, str]]`, `write_csv(rows: list[dict[str, str]], destination: Path) -> None`, and `main(argv: Sequence[str] | None = None) -> int`.

The parser must normalize Python names with PEP 503 rules, preserve each environment as a separate CSV row, recognize project-owned packages, and raise one deterministic error listing every missing approval key.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: `3 passed`.

- [ ] **Step 5: Commit parser behavior**

```powershell
git add -- tools/compliance/__init__.py tools/compliance/generate_license_inventory.py tools/compliance/tests/test_generate_license_inventory.py
git commit -m "feat(compliance): add lockfile inventory gate"
```

### Task 2: Complete reviewed dependency baseline and generated CSV

**Files:**
- Create: `tools/compliance/approved-licenses.json`
- Create: `docs/dependency-licenses.csv`
- Modify: `tools/compliance/tests/test_generate_license_inventory.py`

- [ ] **Step 1: Add a failing repository-completeness test**

```python
import csv
import json


REPOSITORY = Path(__file__).resolve().parents[3]


def test_repository_inventory_covers_every_locked_component() -> None:
    approvals = json.loads(
        (REPOSITORY / "tools/compliance/approved-licenses.json").read_text(
            encoding="utf-8"
        )
    )
    rows = build_inventory(REPOSITORY, approvals)
    rendered = list(
        csv.DictReader(
            (REPOSITORY / "docs/dependency-licenses.csv").open(
                encoding="utf-8", newline=""
            )
        )
    )
    assert rendered == rows
    assert len(rows) == 374
    assert not [row for row in rows if row["review_status"] == "review-required"]
```

- [ ] **Step 2: Run the focused test and verify RED**

Expected: failure because the approved baseline and CSV do not exist.

- [ ] **Step 3: Populate exact-version approvals from official release evidence**

Use the exact version/revision license file shipped in the distribution as primary evidence. Each JSON component must contain:

```json
{
  "key": "python:fastapi@0.139.0",
  "license_expression": "MIT",
  "evidence_url": "https://pypi.org/project/fastapi/0.139.0/",
  "review_status": "approved",
  "redistribution": "retain license and copyright notices",
  "notes": "runtime dependency"
}
```

For proprietary NVIDIA packages use `restricted`; for project packages use `project-owned`; for SDK packages use the pinned Flutter BSD-3-Clause evidence. Do not convert unknown metadata into an approval without an upstream license file.

- [ ] **Step 4: Generate the canonical CSV**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' tools/compliance/generate_license_inventory.py --repository . --approvals tools/compliance/approved-licenses.json --output docs/dependency-licenses.csv
```

Expected: `wrote 374 inventory rows` and exit code 0.

- [ ] **Step 5: Run focused tests and verify GREEN**

Expected: all compliance inventory tests pass and no `review-required` row remains.

- [ ] **Step 6: Commit reviewed inventory**

```powershell
git add -- tools/compliance/approved-licenses.json docs/dependency-licenses.csv tools/compliance/tests/test_generate_license_inventory.py
git commit -m "docs(compliance): audit locked dependency licenses"
```

### Task 3: Apache license, third-party notices, and compliance report

**Files:**
- Create: `LICENSE`
- Create: `NOTICE`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `docs/OPEN_SOURCE_COMPLIANCE.md`
- Create: `README.md`

- [ ] **Step 1: Add the unmodified Apache License 2.0 text**

Download or compare against `https://www.apache.org/licenses/LICENSE-2.0.txt`. The file begins with `Apache License` and ends with `limitations under the License.`; no project-specific wording is inserted into the license body.

- [ ] **Step 2: Add the project notice**

```text
Content Retrieval System
Copyright 2026 Content Retrieval System contributors

This product includes third-party software and other materials governed by
separate terms. See THIRD_PARTY_NOTICES.md. The Apache License 2.0 applies only
to material the project contributors are authorized to license under it.
```

- [ ] **Step 3: Write source and obligation notices**

`THIRD_PARTY_NOTICES.md` must contain separate tables for software/code, models, tools/runtimes, and datasets. Each material component records name, exact version or revision, official source, license, redistribution decision, and required action. It must state that MobileCLIP weights are non-commercial research only and that NQ/COCO assets are excluded from the Apache grant.

- [ ] **Step 4: Write the audit report and release checklist**

`docs/OPEN_SOURCE_COMPLIANCE.md` must report counts from the generated CSV, explain evidence priority, list restricted/not-distributed items, and give commands for regenerating and checking the inventory.

- [ ] **Step 5: Add README discoverability**

Append this exact section to the project README:

```markdown
## 开源许可证与第三方材料

项目自有代码和文档采用 [Apache License 2.0](LICENSE)。第三方软件、模型、工具和数据集不因项目许可证而被重新授权；来源、固定版本、许可证和发行限制见 [第三方声明](THIRD_PARTY_NOTICES.md) 与 [开源合规审查](docs/OPEN_SOURCE_COMPLIANCE.md)。
```

- [ ] **Step 6: Verify text integrity and commit**

```powershell
git diff --check
Select-String -Path LICENSE -Pattern '^Apache License$','^   END OF TERMS AND CONDITIONS$'
git add -- LICENSE NOTICE THIRD_PARTY_NOTICES.md docs/OPEN_SOURCE_COMPLIANCE.md README.md
git commit -m "docs: license project under Apache 2.0"
```

### Task 4: Include legal files and enforce restricted-model release mode

**Files:**
- Modify: `tools/week6/tests/test_powershell_tools.py`
- Modify: `tools/week6/package_stable_build.ps1`

- [ ] **Step 1: Extend the package integration test**

Before `_init_repo(tmp_path)`, create `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md` with distinct payloads. In the ZIP assertions add:

```python
    for legal_name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
    archived_name = f"app/{legal_name}"
    assert archived_name in names
    assert archive.read(archived_name) == (tmp_path / legal_name).read_bytes()
```

Also assert that `docs/dependency-licenses.csv`, `docs/OPEN_SOURCE_COMPLIANCE.md`,
`tools/compliance/approved-licenses.json`, and `datasets/licenses/NOTICE.md` are
copied byte-for-byte so that links inside the notices remain valid in the archive.

- [ ] **Step 2: Run both parameterized package cases and verify RED**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/week6/tests/test_powershell_tools.py::test_package_stable_build_uses_whitelist_and_records_commit -q
```

Expected: both complete and lightweight cases fail because the three root legal files are absent from the ZIP.

- [ ] **Step 3: Copy required legal files before the package manifest is generated**

Add to `package_stable_build.ps1` immediately after `$appRoot` is created:

```powershell
foreach ($legalName in @('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md')) {
    $legalSource = Resolve-RequiredFile `
        -Path (Join-Path $repository $legalName) `
        -Label "Legal file $legalName"
    Copy-Item -LiteralPath $legalSource -Destination (Join-Path $appRoot $legalName)
}
```

- [ ] **Step 4: Run the focused package test and verify GREEN**

Expected: `2 passed`.

- [ ] **Step 5: Add a failing restricted-model release test**

Create a model manifest containing `Apple Machine Learning Research Model License`.
Verify that packaging fails by default, succeeds only with an explicit
`-ResearchOnlyDistribution` switch, preserves the model license, and writes
`distribution_class: research-only` to `PACKAGE_MANIFEST.json`.

- [ ] **Step 6: Implement and verify the research-only gate**

Parse the model manifest before staging. Reject Apple research-licensed weights
unless the switch is present and an applicable license file exists below the model
root. General packages must record `distribution_class: general`.

- [ ] **Step 7: Commit packaging enforcement**

```powershell
git add -- tools/week6/package_stable_build.ps1 tools/week6/tests/test_powershell_tools.py
git commit -m "build: include legal notices in release archives"
```

### Task 5: Final compliance, links, and regression verification

**Files:**
- Modify only if verification reveals an error in files created by Tasks 1-4.

- [ ] **Step 1: Check inventory determinism**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' tools/compliance/generate_license_inventory.py --repository . --approvals tools/compliance/approved-licenses.json --output docs/dependency-licenses.csv --check
```

Expected: `374 inventory rows verified`.

- [ ] **Step 2: Run compliance tests**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/compliance/tests tools/week6/tests/test_powershell_tools.py::test_package_stable_build_uses_whitelist_and_records_commit -q
```

Expected: all tests pass.

- [ ] **Step 3: Run the existing backend regression**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest backend/tests -m 'not requires_models and not requires_tika and not stress' -q
```

Expected: 437 tests pass, one stress test is deselected.

- [ ] **Step 4: Verify legal files and links**

Run a standard-library link checker over `README.md`, `THIRD_PARTY_NOTICES.md`, and `docs/OPEN_SOURCE_COMPLIANCE.md`; verify every relative Markdown target exists and every new text file passes `git diff --check`.

- [ ] **Step 5: Verify change scope**

```powershell
git status --short
git diff --stat master...HEAD
git log --oneline master..HEAD
```

Expected: only the plan, compliance tooling/data/docs, README, and the Week 6 packaging test/script are changed.
