# Week 5 Deliverables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the verified Flutter UI and generate three evidence-backed DOCX deliverables that exactly match the Week 5 requirements, open cleanly in Microsoft Word, and never claim an unexecuted validation as complete.

**Architecture:** Treat `docs/week5/evidence` as the only result source. A manifest builder first validates evidence and produces normalized report data; a reusable Python DOCX builder renders all reports with consistent styles; Word COM export plus PDF/image inspection verifies the final documents. The software package is built from the validated Git commit rather than copied from a dirty worktree.

**Tech Stack:** Git, Flutter release builds, Python, python-docx, Microsoft Word COM, PDF rendering, SHA-256

---

## Required outputs

```text
output/week5/第五周最终提交_请上传这4项/
  01_跨平台Flutter_UI/
    Flutter_UI_源码.zip
    Windows_Release.zip
    构建与运行说明.pdf
    验证清单.json
  02_无障碍合规验证报告.docx
  03_UI可用性测试报告.docx
  04_无障碍用户指南_草稿.docx
  SHA256SUMS.txt
```

The first directory is one software deliverable. The three DOCX files are the remaining deliverables.
The authoritative report files are first generated and finalized under `docs/week5/reports/`, then copied byte-for-byte into the final output directory and hash-compared.

## Required execution skills

When implementing this plan, read and follow the `documents:documents` skill before generating DOCX files and the `windows-docx-finalize` skill before final acceptance. Use the bundled workspace dependency loader to locate Python/document libraries.

### Task 1: Validate and normalize report data

**Files:**
- Create: `tools/week5/build_report_data.py`
- Create: `tools/week5/tests/test_build_report_data.py`
- Create after execution: `tmp/week5/report-data.json`
- Read: `docs/week5/evidence/`

- [ ] **Step 1: Write failing normalization tests**

Use temporary evidence fixtures to assert:

- strict evidence validator is invoked and failures stop report generation;
- every required gate maps to one report section;
- participant P01–P03 data is anonymized;
- pass/fail counts are computed rather than accepted from narrative fields;
- issue severity accepts only `critical`, `high`, `medium`, `low`, `observation`;
- missing observations never become invented prose;
- source commit, test dates, versions, and attachment paths remain traceable.

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest tools/week5/tests/test_build_report_data.py -q
```

- [ ] **Step 3: Implement normalized output**

Write UTF-8 JSON with these top-level keys:

```json
{
  "project": {},
  "completion": {},
  "builds": [],
  "accessibility": [],
  "e2e": [],
  "usability": {},
  "open_issues": [],
  "evidence_index": []
}
```

Derive all totals from source records. Preserve `BLOCKED`/`FAIL` if the script is run with `--draft`; strict final mode refuses them.

- [ ] **Step 4: Verify and commit**

```powershell
python -m pytest tools/week5/tests/test_build_report_data.py -q
python tools/week5/build_report_data.py docs/week5/evidence tmp/week5/report-data.json
git add tools/week5
git commit -m "feat: normalize Week 5 report data"
```

Expected: final-mode generation succeeds only after all strict gates pass.

### Task 2: Package the functional Flutter UI from the validated commit

**Files:**
- Create: `tools/week5/package_flutter_ui.ps1`
- Create after execution: `output/week5/第五周最终提交_请上传这4项/01_跨平台Flutter_UI/`
- Read: `docs/week5/evidence/manifest.json`

- [ ] **Step 1: Implement exact-target safeguards**

The script accepts `-SourceCommit`, `-OutputRoot`, and `-EvidenceManifest`. It must:

1. require a full 40-character commit hash;
2. require it equals the source commit recorded by all five build records;
3. resolve the output path and require it is inside `output/week5`;
4. refuse an existing non-empty target unless `-ReplaceExactTarget` is supplied;
5. never include `.git`, `.dart_tool`, `build`, models, indexed user content, preferences, or credentials.

- [ ] **Step 2: Build source archive from Git objects**

Use binary-safe archive behavior:

```powershell
git -c core.autocrlf=false archive --format=zip --output=<source-zip> <commit> frontend
```

After extraction to a new temporary directory, compare every archived tracked file's `git hash-object --no-filters` value with the commit's blob OID. Fail on any mismatch.

- [ ] **Step 3: Package the verified Windows release**

Create a detached worktree at the exact source commit, run:

```powershell
Set-Location frontend
flutter pub get
flutter analyze
flutter test
flutter build windows --release
```

Zip only `build/windows/x64/runner/Release`. Record executable SHA-256, Flutter version, build command, and commit in `验证清单.json`.

- [ ] **Step 4: Generate build/run instructions**

Create a concise Markdown source and convert it to PDF. It must state:

- supported validation targets and actual evidence result;
- Windows launch steps;
- backend default URL and Android emulator URL;
- model files are backend runtime prerequisites and are not redownloaded on every launch when already present;
- Android/Web validation limitations for directory indexing and file opening;
- exact source commit and evidence manifest path.

- [ ] **Step 5: Test packaging script**

Run it once against a temporary output root, inspect hashes and exclusions, then run against the final exact output root. Commit the script, not generated temporary directories.

### Task 3: Build a reusable Week 5 DOCX generator

**Files:**
- Create: `tmp/docx/build_week5_reports.py`
- Create: `tmp/docx/test_build_week5_reports.py`
- Read: `tmp/docx/build_week3_reports.py`
- Read: `tmp/docx/build_week2_reports.py`

- [ ] **Step 1: Reuse proven document primitives**

Extract or adapt existing helpers for title pages, headings, tables, page breaks, headers/footers, and field updates. Do not modify prior-week reports or their builders.

- [ ] **Step 2: Write failing structure tests**

Generate into a temporary directory and inspect OOXML with `zipfile`/`lxml` or python-docx. Assert each file has:

- Times New Roman for Latin text and a compatible Chinese font for East Asian text;
- A4 page size and consistent margins;
- title, version, date, source commit, reviewer/status block;
- automatic table of contents field;
- page numbers in the footer;
- table header repeat and non-splitting rows where supported;
- no placeholder markers, raw absolute workstation paths, empty required sections, or external hyperlink sources section;
- evidence IDs and relative attachment references.

- [ ] **Step 3: Verify RED**

```powershell
python -m pytest tmp/docx/test_build_week5_reports.py -q
```

- [ ] **Step 4: Implement the generator**

The script accepts `--data`, `--output`, and `--draft`. Final mode refuses incomplete evidence. Use consistent styles:

| Element | Style |
|---|---|
| Body | Times New Roman 11 pt, 1.15 spacing |
| Title | 24 pt bold |
| Heading 1 | 16 pt bold, dark blue |
| Heading 2 | 13 pt bold |
| Table text | 9–10 pt, black on white |
| Caption | 9 pt italic |
| Header/footer | 9 pt |

Use white table backgrounds, black text, and black or dark-gray borders. Do not use dark or colored table fills that can hide body text.

- [ ] **Step 5: Verify structure tests**

```powershell
python -m pytest tmp/docx/test_build_week5_reports.py -q
```

### Task 4: Populate the Accessibility Compliance Validation Report

**Files:**
- Generate: `docs/week5/reports/无障碍合规验证报告.docx`

- [ ] **Step 1: Generate these exact sections**

1. Executive summary and strict completion result
2. Scope, targets, commit, environment, and limitations
3. Requirement-to-evidence matrix
4. Automated Flutter accessibility tests
5. Windows NVDA and keyboard results
6. macOS VoiceOver results
7. Android Accessibility Scanner results
8. Web WAVE results
9. High contrast, 200% text, and reduced motion
10. Findings, remediation, rerun evidence, and residual risk
11. Evidence index and reviewer sign-off

- [ ] **Step 2: Enforce claim discipline**

Each result row contains requirement, platform/tool, procedure, expected, actual, status, tested date, tester, source commit, and evidence ID. The summary status is computed from the evidence validator; it is never hard-coded. Evidence IDs stay in validation tables and the evidence index; descriptive prose has no internal citation clutter or external references section.

### Task 5: Populate the UI Usability Test Report

**Files:**
- Generate: `docs/week5/reports/UI可用性测试报告.docx`

- [ ] **Step 1: Generate these exact sections**

1. Objectives and evaluated workflows
2. Participant profile and consent/anonymization approach
3. Environment and moderation protocol
4. Task scripts and success criteria
5. Participant-level results P01–P03
6. Aggregated completion, time, errors, and assistance
7. Qualitative observations and quotes limited to participant consent
8. Severity-ranked findings
9. Implemented fixes and retest results
10. Recommendations and acceptance decision
11. Evidence index

- [ ] **Step 2: Guard metrics**

Use median for completion time and show the raw three values. Include System Usability Scale only if all ten standard items and scoring data exist. Label any small-sample percentage with `n=3`.

### Task 6: Populate the Draft Accessibility User Guide

**Files:**
- Generate: `docs/week5/reports/无障碍用户指南（草稿）.docx`

- [ ] **Step 1: Generate task-oriented instructions**

1. Supported platforms and validation scope
2. Starting the backend and Flutter UI
3. Understanding connection status
4. Searching and filtering
5. Reading, opening, and copying results
6. Managing the index library safely
7. Changing theme, high contrast, text size, and reduced motion
8. Complete keyboard shortcut table
9. NVDA quick start
10. VoiceOver quick start
11. Android/Web validation limitations
12. Common errors and recovery
13. Privacy and local-file behavior
14. Draft status and feedback channel

- [ ] **Step 2: Verify every instruction against the built UI**

Perform every documented action on the applicable platform. UI labels in the guide must exactly match the current build. Screenshots, if used, include meaningful captions and do not replace written instructions.

### Task 7: Finalize and visually inspect DOCX files

**Files:**
- Modify final: all three DOCX files
- Create temporary: `tmp/week5/rendered/`

- [ ] **Step 1: Open and update fields in Word**

Use Microsoft Word COM in a visible=false, read-only-safe automation session to open each generated DOCX, update fields/table of contents, repaginate, and save. Fail if Word shows a repair prompt or Protected View prevents validation.

- [ ] **Step 2: Export each DOCX to PDF**

Use Word `ExportAsFixedFormat` with PDF format 17. Verify each PDF has at least one page and non-zero text extraction on every narrative page.

- [ ] **Step 3: Render PDFs to page images**

Use the bundled PDF runtime or `pypdfium2` to rasterize every page. Inspect title pages, TOCs, all wide tables, page breaks, captions, headers/footers, and final sign-off pages.

- [ ] **Step 4: Run automated document checks**

Scan extracted text and OOXML for common English/Chinese deferred-work markers and sample-data labels.

Expected: none appear in final mode. Verify no row is clipped, no text is white on white/dark on dark, no heading is orphaned at page bottom, and no absolute `F:\` or `C:\Users\` path appears.

- [ ] **Step 5: Correct source generator and regenerate**

Do not patch final DOCX binaries manually unless the document skill explicitly requires a surgical fix. Correct the builder/data, regenerate, reopen in Word, export, and inspect again.

### Task 8: Create checksums and final acceptance record

**Files:**
- Create: `output/week5/第五周最终提交_请上传这4项/SHA256SUMS.txt`
- Modify: `docs/week5/README.md`

- [ ] **Step 1: Compute hashes**

Copy the three finalized reports from `docs/week5/reports/` to their numbered final-output names, compare source and destination SHA-256 values, then hash every final file recursively and record relative paths in ordinal order. Exclude temporary renderings and Word lock files.

- [ ] **Step 2: Re-open from the final directory**

Open all three DOCX files and the PDF instructions directly from the final directory. Extract both ZIPs into a new temporary location and verify expected executables/source files and their recorded hashes.

- [ ] **Step 3: Run final evidence and repository gates**

```powershell
python tools/week5/validate_evidence.py docs/week5/evidence
git diff --check
git status --short
```

Expected: evidence validator exits 0; no generated lock file, render cache, or unrelated source is staged.

- [ ] **Step 4: Update acceptance matrix**

Add final artifact paths, sizes, SHA-256 values, document page counts, source commit, evidence commit, generator version, reviewer, and acceptance date to `docs/week5/README.md`.

- [ ] **Step 5: Commit controlled deliverables**

Stage only the approved reports, scripts that are intended to remain in the repository, evidence metadata, and README. If final software ZIPs are too large for repository policy, keep them in `output/week5` and record their hashes without forcing them into Git.

## Plan self-review checklist

- Deliverable mapping: one software package plus three named DOCX reports exactly matches the four Week 5 outputs.
- Source integrity: archives are built from the validated commit and verified against Git blob identities.
- Evidence integrity: report numbers and completion claims are computed from strict evidence records.
- Document quality: Word open/update, PDF export, full-page raster review, OOXML scan, and checksum verification are mandatory.
- Privacy: participant data is anonymized and private test content is excluded from packages.
