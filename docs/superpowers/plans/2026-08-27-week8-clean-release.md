# Week 8 Clean Engineering and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one independently runnable, auditable Week 8 engineering tree and reproducible Windows/Linux/macOS release candidates from a single frozen source commit, while removing only code and files proven unused.

**Architecture:** Keep the original working tree untouched. Make source-level deletions only on `codex/week8-finalization`, validate each deletion, then export a clean public tree with an explicit Git-path allowlist. Build artifacts into an untracked F-drive staging area, copy only final archives/evidence into `output/week8/第八周最终交付`, and make `DELIVERY_MANIFEST.json` the source of truth for commit, distribution class, tests, hashes, and platform status.

**Tech Stack:** Python 3.10, pytest, Vulture 2.16, PowerShell 5.1, Flutter 3.44.6/Dart 3.12.2, WSL Ubuntu 24.04, Git, SHA-256, existing Week 5/6 validation and packaging tools.

---

### Task 1: Lock source-cleanliness rules and delete only proven dead imports

**Files:**
- Create: `tools/week8/pyproject.toml`
- Create: `tools/week8/source_audit.py`
- Create: `tools/week8/tests/test_source_audit.py`
- Modify: `tools/week5/build_draft_reports.py:12`
- Modify: `tools/week6/build_reports.py:112`
- Create: `docs/week8/evidence/source-audit/README.md`

- [x] **Step 1: Add failing tests for the two current findings and framework exemptions**

Implement tests that run `audit_paths()` over `backend/src`, `tools`, `model-tools`, and `conversion-tools`; assert that `WD_SECTION` in both report builders is reported, while decorated FastAPI routes and Pydantic validators in small fixtures are not treated as deletion candidates.

Run:

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/week8/tests/test_source_audit.py -q
```

Expected: FAIL because `tools/week8/source_audit.py` does not exist.

- [x] **Step 2: Implement the audit wrapper and pin Vulture 2.16**

`source_audit.py` must invoke Vulture with `--min-confidence 80 --sort-by-size`, normalize paths, maintain a documented decorator exemption list, and write JSON containing command, tool version, findings, reviewed exemptions, and source commit. It must return non-zero while unexplained findings remain.

- [x] **Step 3: Confirm red state against the repository**

```powershell
$env:TEMP='F:\contentretrivalsystem\.tmp'
$env:TMP='F:\contentretrivalsystem\.tmp'
$env:UV_CACHE_DIR='F:\contentretrivalsystem\.tmp\uv-cache'
uv run --project tools/week8 --locked python tools/week8/source_audit.py --output docs/week8/evidence/source-audit/report.json
```

Expected: non-zero with exactly the two `WD_SECTION` imports as unresolved findings.

- [x] **Step 4: Remove exactly those two imports**

Delete `from docx.enum.section import WD_SECTION` in Week 5 and the local import in `_style_document()` in Week 6. Do not remove any route, validator, serializer hook, test helper, or public API based only on reference count.

- [x] **Step 5: Verify green state and report generation**

```powershell
uv run --project tools/week8 --locked python tools/week8/source_audit.py --output docs/week8/evidence/source-audit/report.json
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/week5/tests/test_build_draft_reports.py tools/week6/tests/test_build_reports.py tools/week8/tests/test_source_audit.py -q
```

Expected: audit exit 0; all targeted tests pass.

- [x] **Step 6: Commit the isolated cleanup**

```powershell
git add -- tools/week8 tools/week5/build_draft_reports.py tools/week6/build_reports.py docs/week8/evidence/source-audit
git commit -m "refactor: remove verified dead report imports"
```

### Task 2: Remove broken temporary code and relocate reproducible assets

**Files:**
- Delete: `tmp/docx/build_week2_reports.py`
- Delete: `tmp/docx/build_week3_reports.py`
- Delete: `tmp/docx/test_week2_sequence_diagram.py`
- Move: `tmp/week2-deliverables/assets/current-ingestion-sequence.png` → `docs/week2/assets/current-ingestion-sequence.png`
- Modify: `.gitignore`

- [x] **Step 1: Prove each tracked temporary file is either maintained or archival**

`git grep -n` found only historical-plan references. Direct execution proved the Week 2 builder and its regression test depend on an untracked, absent `build_architecture_docx.py`. The Week 3 builder hard-codes a missing, ignored `output/week3/embedding-coverage.json`. None of the three scripts is reproducible in a clean checkout; the Week 2 PNG remains useful documentary evidence.

- [x] **Step 2: Delete broken code and move maintained evidence with history**

Delete the exact broken Week 2 builder/test pair and Week 3 builder. Move the Week 2 PNG after resolving its destination under the isolated worktree. Keep historical-plan references unchanged because they record the paths that existed when those plans were executed.

- [x] **Step 3: Extend `.gitignore`**

Ignore `/.tmp*/`, `/output/`, Flutter build directories, coverage outputs, generated report renders, recording scratch files, and platform packaging staging directories. Preserve existing exceptions for `.gitkeep`, example manifests, checksums, and tracked evidence.

- [x] **Step 4: Run the repository-layout test**

```powershell
uv run --project tools/week8 --locked python -m pytest tools/week8/tests/test_repository_layout.py -q
git ls-files tmp
```

Expected: repository-layout test passes; `git ls-files tmp` is empty.

- [x] **Step 5: Commit the relocation**

```powershell
git add -A -- tmp docs/week2/assets .gitignore docs/superpowers/plans tools/week8/tests/test_repository_layout.py
git commit -m "refactor: remove tracked temporary implementation files"
```

### Task 3: Define and test the clean public-source whitelist

**Files:**
- Create: `tools/week8/delivery_profile.json`
- Create: `tools/week8/build_clean_source.py`
- Create: `tools/week8/tests/test_build_clean_source.py`
- Create: `docs/week8/CLEAN_ENGINEERING_AUDIT.md`

- [ ] **Step 1: Write failing path-policy tests**

Tests must build a miniature Git tree and assert:

- included roots are `backend`, `frontend`, `model-tools`, `conversion-tools`, `datasets`, `demo-data`, curated `tools`, public `docs`, root legal/community files, product/design docs, and lock files;
- rejected paths include `.git`, `.worktrees`, `.venv`, caches, `tmp`, `output`, generated builds, user databases, logs, credentials, history ZIP/DOCX submissions, real model weights, `mobileclip-src`, and recording scratch files;
- symlinks/reparse points escaping the source root fail closed;
- the public tree contains `models/model-manifest.example.json` but no model binary;
- every copied file is Git tracked and has a SHA-256 entry.

- [ ] **Step 2: Implement an allowlist-only exporter**

`build_clean_source.py` must read paths from `git ls-files -z`, apply `delivery_profile.json`, copy without following links, reject a non-empty destination unless its owned manifest matches, and generate `CLEAN_SOURCE_MANIFEST.json` with source commit, inclusion policy version, file count, bytes, hashes, exclusions by rule, and required-file assertions.

- [ ] **Step 3: Run tests and export to an untracked directory**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/week8/tests/test_build_clean_source.py -q
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' tools/week8/build_clean_source.py --repository . --destination 'F:\contentretrivalsystem\.tmp\week8\clean-source'
```

- [ ] **Step 4: Perform read-only archive audit**

From the exported directory, run the Python test suite, `flutter analyze --no-pub`, `flutter test --no-pub`, the compliance verifier, and a forbidden-path scan. Record exact commands/results in `docs/week8/CLEAN_ENGINEERING_AUDIT.md`.

- [ ] **Step 5: Commit the exporter and audit method**

```powershell
git add -- tools/week8/delivery_profile.json tools/week8/build_clean_source.py tools/week8/tests/test_build_clean_source.py docs/week8/CLEAN_ENGINEERING_AUDIT.md
git commit -m "build: add clean source export policy"
```

### Task 4: Add the Week 8 evidence and delivery-manifest pipeline

**Files:**
- Create: `tools/week8/evidence_schema.json`
- Create: `tools/week8/collect_evidence.py`
- Create: `tools/week8/build_delivery_manifest.py`
- Create: `tools/week8/verify_delivery.py`
- Create: `tools/week8/tests/test_delivery_manifest.py`
- Create: `docs/week8/README.md`
- Create: `docs/week8/evidence/manifest.json`
- Create: `docs/week8/evidence/platform/README.md`

- [ ] **Step 1: Specify failing manifest invariants**

Tests must require a full 40-character commit; current test counts; explicit `PASS`, `FAIL`, or `BLOCKED` per platform gate; distribution class; model-license boundary; file size and lowercase SHA-256; provenance path; and prohibition of `PASS` without a referenced evidence file.

- [ ] **Step 2: Implement evidence collection**

Capture commands, start/end timestamps, exit code, stdout/stderr log path, host OS, Flutter/Dart/Python/Java versions, WSL distro, and commit. Do not overwrite evidence from a different commit.

- [ ] **Step 3: Implement manifest generation and verification**

`build_delivery_manifest.py` consumes only validated evidence and final files. `verify_delivery.py` recomputes all hashes, opens each archive, checks source markers, rejects forbidden content in public artifacts, requires research-license files in the research package, and enforces the same commit in every item.

- [ ] **Step 4: Validate the empty-platform state honestly**

Generate an initial manifest with Windows/Linux/macOS gates marked `BLOCKED` and explanatory evidence paths. Tests must pass because the state is internally consistent, while `verify_delivery.py --require-all-platforms` must fail.

- [ ] **Step 5: Commit the evidence framework**

```powershell
git add -- tools/week8 docs/week8/README.md docs/week8/evidence
git commit -m "build: add Week 8 delivery evidence gates"
```

### Task 5: Build and validate the Windows candidate

**Files:**
- Create: `tools/week8/build_windows_release.ps1`
- Create: `tools/week8/tests/test_build_windows_release.py`
- Create after execution: `docs/week8/evidence/platform/windows/`
- Create after execution: `output/week8/第八周最终交付/01_平台发布/Windows/`

- [ ] **Step 1: Add structural tests for source commit and distribution mode**

Tests must prove the wrapper refuses a dirty tree, abbreviated commit, source mismatch, public package containing research-only weights, missing legal files, non-release Flutter bundle, or archive at/above its strict size limit.

- [ ] **Step 2: Implement the wrapper around existing Week 6 primitives**

The wrapper builds Flutter Windows release, performs `tools/start-mvp.ps1 -CheckOnly`, invokes `package_stable_build.ps1`, and records evidence. Use two products: a default public CPU package without MobileCLIP weights and a separately named `课程演示研究包` with `-ResearchOnlyDistribution` and exact model-license/hash evidence.

- [ ] **Step 3: Execute the full Windows validation**

Run backend tests, Week 5/6/tooling/compliance tests, demo tests, `flutter analyze --no-pub`, `flutter test --no-pub`, `flutter build windows --release`, launcher preflight, one-click launch, health probes, and `tools/week5/run_real_five_format_e2e.py` against an empty F-drive data directory.

- [ ] **Step 4: Verify offline restart and archive extraction**

Extract each archive into a new empty short path, disable remote model/download resolution through environment controls, start the packaged app, verify readiness and the five-format workflow, stop owned processes, and recompute every file hash. Record raw logs and JSON in `docs/week8/evidence/platform/windows/`.

- [ ] **Step 5: Commit scripts and evidence, not staging directories**

```powershell
git add -- tools/week8/build_windows_release.ps1 tools/week8/tests/test_build_windows_release.py docs/week8/evidence/platform/windows
git commit -m "release: validate Week 8 Windows candidate"
```

### Task 6: Build and validate the Linux candidate in WSL

**Files:**
- Create: `tools/week8/build_linux_release.sh`
- Create: `tools/week8/tests/test_build_linux_release.py`
- Create after execution: `docs/week8/evidence/platform/linux/`
- Create after execution: `output/week8/第八周最终交付/01_平台发布/Linux/`

- [ ] **Step 1: Add shell-policy tests**

Require `set -euo pipefail`, exact commit checks, clean-tree check, release build, legal files, manifest/hash generation, public-model exclusion, and cleanup traps for owned processes.

- [ ] **Step 2: Execute in `Ubuntu-24.04`**

Run the clean export and Linux build from a WSL-native short staging directory on `F:`/`/mnt/f`; capture distro/kernel/tool versions. Build Flutter Linux release where dependencies permit, run backend/tooling tests, start the local backend, perform health and five-format E2E, and validate the archive from a fresh extraction.

- [ ] **Step 3: Handle environment absence without false PASS**

If Flutter Linux system libraries or display services are missing, preserve the exact command/output and keep the affected gate `BLOCKED`; install only project-scoped dependencies allowed by the existing environment, never weaken tests.

- [ ] **Step 4: Commit scripts and verified evidence**

```powershell
git add -- tools/week8/build_linux_release.sh tools/week8/tests/test_build_linux_release.py docs/week8/evidence/platform/linux
git commit -m "release: validate Week 8 Linux candidate"
```

### Task 7: Prepare and enforce the real-macOS handoff gate

**Files:**
- Create: `tools/week8/build_macos_release.sh`
- Create: `tools/week8/validate_macos_evidence.py`
- Create: `tools/week8/tests/test_validate_macos_evidence.py`
- Create: `docs/week8/MACOS_RELEASE_RUNBOOK.md`
- Create: `docs/week8/evidence/platform/macos/status.json`

- [ ] **Step 1: Test the evidence validator**

It must reject non-Darwin evidence, simulator-only evidence, missing `flutter build macos --release` log, missing app hash, absent launch/health/five-format results, missing VoiceOver checklist, mismatched commit, and screenshots without hashes.

- [ ] **Step 2: Write the deterministic macOS script and runbook**

The script checks out the frozen tag, validates a clean tree, runs tests/analyze/build, packages the `.app`, runs local health/five-format smoke tests, captures `sw_vers`, `uname`, Flutter/Dart versions, and generates SHA-256. The runbook gives exact VoiceOver steps for navigation, labels, search results, high contrast, 150% text, reduced motion, copied path, and opened file.

- [ ] **Step 3: Record the current honest state**

Set `status.json` to `BLOCKED` with reason `real macOS host unavailable`, source commit, required command list, and validator output. Do not create a macOS ZIP on Windows and do not mark VoiceOver passed.

- [ ] **Step 4: Commit the handoff gate**

```powershell
git add -- tools/week8/build_macos_release.sh tools/week8/validate_macos_evidence.py tools/week8/tests/test_validate_macos_evidence.py docs/week8/MACOS_RELEASE_RUNBOOK.md docs/week8/evidence/platform/macos/status.json
git commit -m "release: add real macOS acceptance gate"
```

### Task 8: Freeze the candidate and assemble the final clean engineering directory

**Files:**
- Create after execution: `output/week8/第八周最终交付/02_公开源码/offline-accessible-multimodal-retrieval-v1.0.0.zip`
- Create after execution: `output/week8/第八周最终交付/03_课程演示研究包/`
- Create after execution: `output/week8/第八周最终交付/SOURCE_VERSION.txt`
- Create after execution: `output/week8/第八周最终交付/DELIVERY_MANIFEST.json`
- Create after execution: `output/week8/第八周最终交付/SHA256SUMS.txt`

- [ ] **Step 1: Run the complete pre-freeze suite**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest backend/tests -q
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/week5/tests tools/week6/tests tools/compliance/tests tools/week8/tests -q
uv run --project tools/demo --locked python -m unittest discover -s tools/demo/tests -v
Set-Location frontend
flutter analyze --no-pub
flutter test --no-pub
```

Expected minimums: Python main 464 passed/1 skipped; Week 5/6/compliance remains at or above 124 passed plus new Week 8 tests; demo 33 passed; Flutter 249 passed; analyze 0 issues.

- [ ] **Step 2: Commit the final source state and record the exact commit**

Commit any remaining tracked source/evidence changes, require `git status --porcelain` empty, then write the full `git rev-parse HEAD` value into every builder invocation. Do not amend after artifacts are built.

- [ ] **Step 3: Export, archive, and verify from the exact commit**

Use a new detached clean worktree at the frozen commit, generate the clean source, platform candidates, research package, manifest, and SHA sums. Extract every archive into separate empty directories and run only read-only validation there.

- [ ] **Step 4: Keep all three deliverable families commit-identical**

Verify that source ZIP, platform package manifests, research package, report evidence, video metadata, portfolio metadata, `SOURCE_VERSION.txt`, and `DELIVERY_MANIFEST.json` contain the same full commit.

- [ ] **Step 5: Do not tag until publication documents and CI are committed**

Leave the candidate commit untagged until the publishing plan completes; any source change after this point requires rebuilding all artifacts.
