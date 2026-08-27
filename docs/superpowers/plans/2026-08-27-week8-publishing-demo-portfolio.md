# Week 8 Publishing, Demo Video, and Portfolio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the frozen Week 8 candidate into a publishable open-source project, a validated exact-five-minute demonstration, and a concise evidence-linked portfolio without confusing public and research-only distributions.

**Architecture:** Repository-facing materials live at the root and in `docs/week8`; machine-checkable publication rules live in `tools/week8`. The existing nine-segment demo script remains authoritative. Rehearsal, recording, encoding, and portfolio assets reference the same delivery manifest and commit as the platform/source artifacts.

**Tech Stack:** GitHub Actions YAML, Markdown, Python/pytest, Flutter CI, FFmpeg/ffprobe, Windows screen recording, existing `tools/demo` fixture generator and tests, SHA-256.

---

### Task 1: Complete open-source community and security files

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `SECURITY.md`
- Modify: `README.md`
- Modify: `THIRD_PARTY_NOTICES.md`
- Modify: `docs/OPEN_SOURCE_COMPLIANCE.md`
- Create: `tools/week8/tests/test_public_repository.py`

- [ ] **Step 1: Add failing repository-content tests**

Require project purpose, five supported formats, local-only privacy boundary, WebP limitation, model-license boundary, Windows/Linux/macOS status table, quick start, architecture image, UI screenshots, test commands/count source, release links, contribution workflow, conduct policy, private vulnerability reporting process, Apache-2.0 license, NOTICE, and third-party notices.

- [ ] **Step 2: Write the three community files and revise README**

Use `offline-accessible-multimodal-retrieval` as the public repository name. Clearly state that the public/default package excludes MobileCLIP weights and that the course research package is not a general commercial/open-source binary distribution.

- [ ] **Step 3: Re-run compliance and repository tests**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/compliance/tests tools/week8/tests/test_public_repository.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add -- README.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md THIRD_PARTY_NOTICES.md docs/OPEN_SOURCE_COMPLIANCE.md tools/week8/tests/test_public_repository.py
git commit -m "docs: prepare public project governance"
```

### Task 2: Add CI that matches local release gates

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`
- Create: `tools/week8/tests/test_ci_workflows.py`

- [ ] **Step 1: Add failing YAML assertions**

Require pinned major action versions, least-privilege permissions, Python 3.10, `uv sync --locked`, backend/tooling/compliance/demo tests, Flutter stable setup, `flutter analyze --no-pub`, `flutter test --no-pub`, Windows and Ubuntu runners, artifact hashes, and release workflow execution only for `v*` tags. Never add secrets to repository files.

- [ ] **Step 2: Implement CI and release workflows**

The normal CI must not download research-only models. Release workflow builds only public/default artifacts; the course research package remains outside public GitHub Release assets.

- [ ] **Step 3: Validate workflow syntax and policy locally**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/week8/tests/test_ci_workflows.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add -- .github/workflows tools/week8/tests/test_ci_workflows.py
git commit -m "ci: add public validation and release workflows"
```

### Task 3: Finalize release notes and GitHub publication metadata

**Files:**
- Create: `docs/week8/RELEASE_NOTES_v1.0.0.md`
- Create: `docs/week8/GITHUB_PUBLICATION_CHECKLIST.md`
- Create: `tools/week8/validate_publication.py`
- Create: `tools/week8/tests/test_validate_publication.py`
- Copy after execution: `output/week8/第八周最终交付/RELEASE_NOTES.md`

- [ ] **Step 1: Test release-note facts and artifact separation**

Require supported formats/features, exact frozen commit, validation summary sourced from the delivery manifest, known limitations, privacy boundary, license boundary, install/start instructions, public artifact hashes, and no research package in public Release asset entries.

- [ ] **Step 2: Implement publication validator**

Validate remote URL, anonymous HTTP accessibility, default branch, CI conclusion, signed/annotated `v1.0.0` tag target, Release asset names/hashes, and exact commit. Local dry-run mode validates all files without network credentials and reports remote checks as `BLOCKED`.

- [ ] **Step 3: Commit publication materials before tagging**

```powershell
git add -- docs/week8/RELEASE_NOTES_v1.0.0.md docs/week8/GITHUB_PUBLICATION_CHECKLIST.md tools/week8/validate_publication.py tools/week8/tests/test_validate_publication.py
git commit -m "docs: finalize v1.0.0 release materials"
```

- [ ] **Step 4: Publish only when GitHub authority exists**

When an authenticated remote is supplied, push the exact clean branch, wait for CI, create annotated tag `v1.0.0` at the frozen commit, push it, create the GitHub Release, upload public source/platform artifacts and hashes, then verify anonymous access. Without credentials/remote, preserve validator output as `BLOCKED`; do not fabricate a URL.

### Task 4: Add rehearsal logging and exact content gates

**Files:**
- Modify: `docs/demo/五分钟演示脚本.md`
- Create: `tools/week8/record_rehearsal.py`
- Create: `tools/week8/validate_rehearsal.py`
- Create: `tools/week8/tests/test_rehearsal.py`
- Create after execution: `docs/week8/evidence/demo/rehearsal-01.json`
- Create after execution: `docs/week8/evidence/demo/rehearsal-02.json`

- [ ] **Step 1: Preserve the existing nine-segment contract**

Keep all existing `tools/demo/tests/test_demo_materials.py` assertions green. Add no unsupported WebP, accuracy/probability, cloud, or fixed-image-ranking claims.

- [ ] **Step 2: Add failing rehearsal-schema tests**

Each rehearsal must record source commit, clean data directory, preflight, readiness, five fixtures, five expected queries validated twice, nine segment actual durations, accessibility interactions, offline failure/recovery, operator name, start/end timestamps, raw recording path/hash, and PASS/FAIL per checkpoint.

- [ ] **Step 3: Implement logger and validator**

The validator requires two distinct rehearsal IDs and data directories, rejects self-declared PASS without referenced command/screenshot/video evidence, and checks total rehearsal duration between 4:55 and 5:05.

- [ ] **Step 4: Execute rehearsal 01 and 02 against the frozen candidate**

Use `F:\week8-demo\rehearsal-01` and `F:\week8-demo\rehearsal-02`, separate TEMP/TMP/UV caches, run preflight, start backend and Flutter Windows app, execute the script, and preserve raw logs/screenshots/video hashes.

- [ ] **Step 5: Commit script changes and compact evidence**

```powershell
git add -- docs/demo/五分钟演示脚本.md tools/week8/record_rehearsal.py tools/week8/validate_rehearsal.py tools/week8/tests/test_rehearsal.py docs/week8/evidence/demo
git commit -m "test: validate two Week 8 demo rehearsals"
```

### Task 5: Record, encode, and validate the exact five-minute video

**Files:**
- Create: `tools/week8/validate_video.py`
- Create: `tools/week8/tests/test_validate_video.py`
- Create: `docs/week8/evidence/demo/final-video.json`
- Create after execution: `output/week8/第八周最终交付/04_项目演示视频/离线可访问多模态检索系统_5分钟演示.mp4`

- [ ] **Step 1: Add ffprobe-metadata tests**

Accept only H.264/AAC MP4, 1920×1080, 30/1 fps, duration from 299.5 through 300.5 seconds, at least one video and one audio stream, non-zero audio, no rotation metadata, and SHA-256 matching the evidence file. Unit tests use mocked ffprobe JSON plus one generated two-second fixture.

- [ ] **Step 2: Implement the validator**

Call `ffprobe -v error -show_streams -show_format -of json`; validate codec/dimensions/rate/duration/audio and write normalized metadata plus source commit and file hash.

- [ ] **Step 3: Capture the real GUI recording**

Record the actual frozen Windows application at 1920×1080/30 fps using the validated script and `recording-01` data directory. Show the five fixtures, exact/text-semantic/image-semantic/hybrid search, filters, copy/open operations, high contrast, 150% text, reduced motion, keyboard navigation, and real offline failure/recovery. Hide notifications and private paths.

- [ ] **Step 4: Trim only dead air and encode to exactly 5:00**

Use FFmpeg with explicit 1920×1080 scaling/padding, 30 fps, H.264 yuv420p, AAC audio, and `-t 300`. Do not synthesize fake result screens or splice a different commit/application state.

- [ ] **Step 5: Inspect at segment boundaries**

Extract stills at 00:00, 00:20, 00:55, 01:25, 02:00, 02:45, 03:25, 03:55, 04:25, and 04:59; visually inspect legibility, private-data masking, result correctness, and absence of blank/error frames. Run the validator and record its PASS.

- [ ] **Step 6: Add only metadata and final deliverable reference to Git**

Keep large raw recordings out of Git. Commit `validate_video.py`, tests, final-video JSON, and any small reviewed contact sheet; put the MP4 only in the Week 8 delivery directory/GitHub release as permitted.

### Task 6: Build the evidence-linked project portfolio

**Files:**
- Create: `docs/week8/portfolio/README.md`
- Create: `docs/week8/portfolio/assets/architecture.png`
- Create: `docs/week8/portfolio/assets/release-model.png`
- Create: `docs/week8/portfolio/assets/test-summary.png`
- Create: `tools/week8/validate_portfolio.py`
- Create: `tools/week8/tests/test_validate_portfolio.py`
- Copy after execution: `output/week8/第八周最终交付/05_项目作品集/`

- [ ] **Step 1: Add failing content/source tests**

Require project background, role, architecture, ingestion/search flow, key UI, technical challenges, test/performance results, accessibility, privacy/compliance, video, GitHub, downloads, documentation, known limitations, reflection, full commit, image alt text, and evidence-linked numeric claims.

- [ ] **Step 2: Create three white-background black-line figures**

Generate architecture, public-vs-research release relationship, and test-summary diagrams from final manifest values. Reuse verified UI screenshots from `docs/week5/evidence/attachments`; never upscale low-resolution images without marking them as screenshots.

- [ ] **Step 3: Write and validate the portfolio**

Use relative links that also work in the public source ZIP. The validator cross-checks every test count, artifact hash/link, platform status, and commit against `DELIVERY_MANIFEST.json`.

- [ ] **Step 4: Commit**

```powershell
git add -- docs/week8/portfolio tools/week8/validate_portfolio.py tools/week8/tests/test_validate_portfolio.py
git commit -m "docs: add Week 8 project portfolio"
```

### Task 7: Final publication audit and tag

**Files:**
- Modify after execution: `output/week8/第八周最终交付/DELIVERY_MANIFEST.json`
- Modify after execution: `output/week8/第八周最终交付/SHA256SUMS.txt`

- [ ] **Step 1: Re-run all public, CI, rehearsal, video, portfolio, and delivery validators**

No validator may consume handwritten counts where a machine-readable source exists.

- [ ] **Step 2: Re-freeze if any tracked file changed**

If report, README, workflow, validator, or portfolio work changes the commit after artifacts were built, create a new frozen commit and rebuild all artifacts; do not patch commit strings inside old archives.

- [ ] **Step 3: Create `v1.0.0` only at the final immutable commit**

Require a clean tree and verify `git rev-list -n 1 v1.0.0` equals `SOURCE_VERSION.txt`. Keep local tag creation reversible until remote publication is authorized.

- [ ] **Step 4: Record honest completion status**

Windows/Linux/local documentation work may pass independently. macOS, GitHub, or real-video gates remain `BLOCKED` until their direct evidence exists; their absence prevents the overall Week 8 goal from being marked complete.

