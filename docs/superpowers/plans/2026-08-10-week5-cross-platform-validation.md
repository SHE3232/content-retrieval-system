# Week 5 Cross-Platform Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce reproducible build, assistive-technology, scanner, E2E, persistence, and usability evidence for Windows, macOS, Linux, Android, and Web under the strict Week 5 completion rule.

**Architecture:** First make the Flutter source compile without `dart:io` leakage on Web, then add Android/Web runners. Each platform run writes a small JSON record plus raw attachments under a fixed evidence tree. A standard-library Python validator rejects missing, failed, blocked, stale, or attachment-less gates, so documentation cannot overstate completion.

**Tech Stack:** Flutter/Dart, `package:http` 1.6.0, Python 3, Windows/macOS/Linux, Android SDK and Accessibility Scanner, NVDA, VoiceOver, WAVE browser extension

---

## Evidence tree

```text
docs/week5/evidence/
  manifest.json
  windows/
    build.json
    nvda.json
    keyboard.json
    high-contrast.json
    text-scale-200.json
    reduced-motion.json
  macos/
    build.json
    voiceover.json
  linux/
    build.json
  android/
    build.json
    accessibility-scanner.json
  web/
    build.json
    wave.json
  e2e/
    five-formats.json
    persistence.json
  usability/
    participant-01.json
    participant-02.json
    participant-03.json
    summary.json
  attachments/
```

Every JSON record uses:

```json
{
  "gate_id": "build.windows",
  "status": "PASS",
  "tested_at": "2026-08-10T12:00:00+08:00",
  "tester": "reviewer name",
  "environment": "Windows 11; Flutter 3.44.6",
  "procedure": ["flutter build windows --release"],
  "observations": ["exit code 0"],
  "attachments": ["attachments/windows-release-build.txt"],
  "issues": []
}
```

Allowed statuses are `PASS`, `FAIL`, `BLOCKED`, and `NOT_RUN`. Only `PASS` satisfies the strict gate.

### Task 1: Remove Web-incompatible transport and launcher imports

**Files:**
- Modify: `frontend/pubspec.yaml`
- Create: `frontend/lib/core/api/http_json_transport.dart`
- Delete: `frontend/lib/core/api/io_json_transport.dart`
- Create: `frontend/lib/core/platform/file_launcher_contract.dart`
- Create: `frontend/lib/core/platform/file_launcher_io.dart`
- Create: `frontend/lib/core/platform/file_launcher_stub.dart`
- Modify: `frontend/lib/core/platform/file_launcher.dart`
- Modify: `frontend/lib/app/content_retrieval_app.dart`
- Create: `frontend/test/core/api/http_json_transport_test.dart`
- Modify: `frontend/test/core/platform/file_launcher_test.dart`
- Delete: `frontend/test/core/api/io_json_transport_test.dart`

- [ ] **Step 1: Write cross-platform transport tests**

Add `http: ^1.6.0` and inject an `http.Client`. Use `MockClient` or a small fake client to test GET/POST/DELETE, UTF-8 JSON, non-JSON response, timeout mapping, and client close. The production constructor creates `http.Client()`; no source file imported by Web may import `dart:io`.

- [ ] **Step 2: Verify RED**

```powershell
Set-Location frontend
flutter test test/core/api/http_json_transport_test.dart
```

- [ ] **Step 3: Implement `HttpJsonTransport`**

Keep the existing `JsonTransport` public contract. Resolve paths against `baseUri`, use `jsonEncode`, `utf8.decode(response.bodyBytes)`, and map `TimeoutException`, `http.ClientException`, and `FormatException` to existing `ApiException` kinds. Close the injected client exactly once.

- [ ] **Step 4: Split launcher contract and platform implementations**

`file_launcher_contract.dart` contains only enums, exceptions, and the interface. `file_launcher_io.dart` contains `File`, `Platform`, and `Process.start`. `file_launcher_stub.dart` returns a launcher whose `open` throws `unsupportedPlatform`. `file_launcher.dart` selects with conditional export/import:

```dart
export 'file_launcher_stub.dart'
    if (dart.library.io) 'file_launcher_io.dart';
```

On Android the IO factory returns an unsupported launcher; local backend result paths are desktop paths and must not be opened by the mobile validation build.

- [ ] **Step 5: Verify Web compile boundary**

```powershell
dart format lib test
flutter test
flutter analyze
flutter build web --debug
```

Expected: the Web build reaches runner generation without any `dart:io` or `Process` compile error.

- [ ] **Step 6: Commit compatibility refactor**

```powershell
git add pubspec.yaml pubspec.lock lib/core lib/app test/core
git commit -m "refactor: support cross-platform Flutter adapters"
```

### Task 2: Add Android and Web validation targets

**Files:**
- Create: `frontend/android/`
- Create: `frontend/web/`
- Modify: `frontend/.metadata`
- Modify: `frontend/lib/core/platform/directory_picker.dart`
- Modify: `frontend/lib/features/library/presentation/index_library_page.dart`
- Modify: `frontend/test/features/library/index_library_page_test.dart`

- [ ] **Step 1: Generate only missing targets**

From `frontend` run:

```powershell
flutter create --platforms=android,web .
```

Review `git status --short`. Restore no existing source blindly; inspect any generated changes to `lib/main.dart`, `pubspec.yaml`, and tests and retain the implemented application versions.

- [ ] **Step 2: Set honest mobile/Web capability flags**

Directory indexing is enabled only on Windows, macOS, and Linux because the backend consumes paths in its own desktop filesystem namespace. Disable it on Android and Web with visible text:

```text
此验证版本不能把移动端或浏览器文件夹路径交给本地桌面后端；请在桌面版管理索引。
```

On Android, search, results, settings, semantic navigation, contrast, and text scaling remain usable when Settings points to a backend reachable from the device. On Web, the UI, settings, semantic navigation, contrast, and text scaling remain usable for visual and accessibility verification. Backend health, search, and results require same-origin hosting or an explicitly scoped allowed-origin or proxy configuration; the current backend provides neither, so this validation must not claim functional Web retrieval. Library local file-open and folder actions are disabled where capability flags mark them unsupported. Search result Open remains visible, but reports an inline unsupported-platform message when the platform launcher cannot open the path; Copy path remains available.

- [ ] **Step 3: Configure Android networking for local validation**

Ensure the generated manifest includes internet permission. For debug-only emulator validation, allow cleartext loopback access in `android/app/src/debug/AndroidManifest.xml`; do not weaken the release manifest. Set backend URL through Settings to `http://10.0.2.2:8000` when testing against a backend on the Android emulator host.

- [ ] **Step 4: Add platform-scope widget tests**

Inject capabilities rather than mocking `Platform`. Assert desktop enables index folder selection; Android/Web disables it; all targets still expose the same search and accessibility semantics.

- [ ] **Step 5: Verify generated targets**

```powershell
flutter analyze
flutter test
flutter build apk --debug
flutter build web --release
```

Expected: both builds exit 0 on the configured Windows Android toolchain.

- [ ] **Step 6: Commit targets**

```powershell
git add android web .metadata lib/core/platform lib/features/library test/features/library
git commit -m "feat: add Flutter accessibility validation targets"
```

### Task 3: Implement the evidence validator before collecting evidence

**Files:**
- Create: `tools/week5/validate_evidence.py`
- Create: `tools/week5/tests/test_validate_evidence.py`
- Create: `docs/week5/evidence/manifest.json`

- [ ] **Step 1: Write failing validator tests**

Test these cases with temporary directories:

- all required gate files present and `PASS` returns 0;
- missing record returns 1;
- `FAIL`, `BLOCKED`, or `NOT_RUN` returns 1;
- malformed timestamp or future timestamp returns 1;
- missing tester/procedure/observation returns 1;
- referenced attachment outside evidence root or absent returns 1;
- duplicate `gate_id` returns 1.

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest tools/week5/tests/test_validate_evidence.py -q
```

- [ ] **Step 3: Implement a standard-library validator**

Required gate IDs:

```python
REQUIRED_GATES = {
    "build.windows", "build.macos", "build.linux", "build.android", "build.web",
    "a11y.nvda", "a11y.voiceover", "a11y.android_scanner", "a11y.wave",
    "a11y.keyboard", "a11y.high_contrast", "a11y.text_scale_200",
    "a11y.reduced_motion",
    "e2e.five_formats", "e2e.persistence",
    "usability.participant_01", "usability.participant_02",
    "usability.participant_03", "usability.summary",
}
```

Resolve attachment paths and require they remain inside `docs/week5/evidence`. Print a one-line result for each gate and a final count. Add `--allow-incomplete` for progress reporting; it still prints missing gates but returns 0. The strict release command must omit that flag.

- [ ] **Step 4: Create the initial manifest**

The manifest lists schema version `1`, project commit, Flutter version, backend version/commit, and relative paths of all evidence records. It must not declare an unexecuted gate as passed.

- [ ] **Step 5: Verify and commit**

```powershell
python -m pytest tools/week5/tests/test_validate_evidence.py -q
python tools/week5/validate_evidence.py docs/week5/evidence --allow-incomplete
git add tools/week5 docs/week5/evidence/manifest.json
git commit -m "test: validate Week 5 evidence"
```

### Task 4: Validate Windows, NVDA, keyboard, contrast, 200% text, and reduced motion

**Files:**
- Create after execution: `docs/week5/evidence/windows/build.json`
- Create after execution: `docs/week5/evidence/windows/nvda.json`
- Create after execution: `docs/week5/evidence/windows/keyboard.json`
- Create after execution: `docs/week5/evidence/windows/high-contrast.json`
- Create after execution: `docs/week5/evidence/windows/text-scale-200.json`
- Create after execution: `docs/week5/evidence/windows/reduced-motion.json`
- Create after execution: `docs/week5/evidence/attachments/windows-*`

- [ ] **Step 1: Build the committed release snapshot**

```powershell
Set-Location frontend
flutter build windows --release *> ..\docs\week5\evidence\attachments\windows-release-build.txt
```

Record Flutter/Windows/NVDA versions and the tested commit.

- [ ] **Step 2: Run the NVDA workflow**

With NVDA enabled, complete search, filter change, result open/copy, library navigation, indexing progress review, reindex/remove dialogs, settings, and error recovery. For every step record announced label, role, state, focus order, live-status behavior, expected value, and actual result.

- [ ] **Step 3: Run keyboard-only workflow**

Complete the same workflow without pointer input. Verify all shortcuts, forward/reverse traversal, visible focus, dialog focus containment, Escape behavior, and focus restoration.

- [ ] **Step 4: Review high contrast, 200% text, and reduced motion**

Test light/dark high contrast at Windows 100% and 200% text settings. Enable the OS/app reduced-motion preference and verify project-owned transitions stop without hiding progress or moving focus. Capture all three pages, one dialog, loading, empty, error, and populated result states. Record any clipping, overlap, inaccessible scrolling, color-only state, or motion that ignores the preference.

- [ ] **Step 5: Fix, rerun, and write PASS records**

Any issue first produces `FAIL`, is fixed through the owning implementation plan, then the entire affected workflow is rerun. Only the final successful run is `PASS`; retain before/after evidence in observations.

### Task 5: Validate macOS and VoiceOver

**Files:**
- Create after execution: `docs/week5/evidence/macos/build.json`
- Create after execution: `docs/week5/evidence/macos/voiceover.json`
- Create after execution: `docs/week5/evidence/attachments/macos-*`

- [ ] **Step 1: Check out the same commit on a Mac**

Record `git rev-parse HEAD` and require it equals the manifest commit.

- [ ] **Step 2: Build and launch**

```bash
cd frontend
flutter doctor -v
flutter pub get
flutter analyze
flutter test
flutter build macos --release
open build/macos/Build/Products/Release/content_retrieval_app.app
```

- [ ] **Step 3: Run VoiceOver core flows**

Use VoiceOver keyboard navigation to traverse the three destinations, submit a search, inspect results and states, navigate the library, read indexing progress, open confirmations, and change settings. Verify rotor/landmark discoverability where exposed, spoken selection states, no duplicate labels, and focus restoration.

- [ ] **Step 4: Record evidence**

Attach build log, macOS/Flutter/VoiceOver versions, signed checklist, and screenshots or screen recording. If no Mac is available, write `BLOCKED`; strict Week 5 remains incomplete.

### Task 6: Validate Linux build and smoke behavior

**Files:**
- Create after execution: `docs/week5/evidence/linux/build.json`
- Create after execution: `docs/week5/evidence/attachments/linux-*`

- [ ] **Step 1: Check out the manifest commit on Linux**

- [ ] **Step 2: Build and test**

```bash
cd frontend
flutter doctor -v
flutter pub get
flutter analyze
flutter test
flutter build linux --release
./build/linux/x64/release/bundle/content_retrieval_app
```

- [ ] **Step 3: Perform smoke workflow**

Verify launch, backend connection, search offline/online states, file-library list and actions, settings persistence controls, keyboard traversal, visible focus, high contrast, 200% text, and clean exit. If using a remote/headless runner, a virtual display is insufficient for the visual smoke gate unless screenshots and human review are recorded.

- [ ] **Step 4: Record PASS or BLOCKED honestly**

### Task 7: Validate Android with Google Accessibility Scanner

**Files:**
- Create after execution: `docs/week5/evidence/android/build.json`
- Create after execution: `docs/week5/evidence/android/accessibility-scanner.json`
- Create after execution: `docs/week5/evidence/attachments/android-*`

- [ ] **Step 1: Validate Android environment**

```powershell
Set-Location frontend
flutter doctor -v
flutter doctor --android-licenses
flutter devices
flutter build apk --debug
```

Use an Android 9+ device/emulator with Google Play access. Record device model, API level, scanner version, Flutter version, and commit.

- [ ] **Step 2: Launch the validation build**

```powershell
flutter run -d <recorded-device-id>
```

Set `http://10.0.2.2:8000` only when a host backend is running. Otherwise exercise explicit offline, loading fixture, empty, error, and populated demo/test states through the deterministic validation harness; do not claim mobile directory indexing or file opening.

- [ ] **Step 3: Scan a complete recorded workflow**

Use Accessibility Scanner recording across search, filters, results, navigation, library, settings, dialogs, 200% text, and high contrast. Export/share scanner results and capture its lists by screen/category.

- [ ] **Step 4: Resolve every scanner finding**

Classify each item as fixed or false positive with exact screen, control, rationale, reviewer, and screenshot. Rerun the same recording after fixes. `PASS` requires zero unresolved findings; the scanner result alone does not replace manual keyboard/screen-reader checks.

### Task 8: Validate Web with WAVE

**Files:**
- Create after execution: `docs/week5/evidence/web/build.json`
- Create after execution: `docs/week5/evidence/web/wave.json`
- Create after execution: `docs/week5/evidence/attachments/web-*`

- [ ] **Step 1: Build and serve the committed Web output**

```powershell
Set-Location frontend
flutter build web --release *> ..\docs\week5\evidence\attachments\web-release-build.txt
python -m http.server 8080 --directory build\web
```

Open `http://127.0.0.1:8080` in a browser with the WAVE extension. Record browser and extension versions.

- [ ] **Step 2: Evaluate every reachable state**

Run WAVE on search initial/loading/populated/empty/error, library, settings, confirmation dialogs, high contrast, and 200% text. Because WAVE inspects the rendered Web accessibility tree, explicitly record the Web target's limited directory/file-open scope.

- [ ] **Step 3: Resolve findings and rerun**

Record errors, contrast errors, alerts, features, structure, and ARIA counts per state. `PASS` requires zero unresolved WAVE errors and contrast errors; every remaining alert needs a documented manual review and disposition.

### Task 9: Validate E2E, persistence, and usability

**Files:**
- Create after execution: `docs/week5/evidence/e2e/five-formats.json`
- Create after execution: `docs/week5/evidence/e2e/persistence.json`
- Create after execution: `docs/week5/evidence/usability/*.json`
- Create after execution: `docs/week5/evidence/attachments/e2e-*`

- [ ] **Step 1: Prepare a controlled five-format fixture**

Create one TXT, PDF, DOCX, JPG, and PNG with unique searchable identifiers. Record SHA-256, size, and expected modality outside the source tree. Do not commit private test content.

- [ ] **Step 2: Run Windows E2E**

Index the fixture directory, confirm successful counts, search each unique identifier, exercise keyword/text-semantic/image-semantic/hybrid retrieval plus format and modality filters, inspect result metadata, open/copy supported results, reindex one file, remove one file from the index, and confirm the disk file remains. Capture request/response identifiers without including sensitive document content.

- [ ] **Step 3: Run restart persistence**

Save theme, high contrast, 200% text, reduce motion, and backend URL; close the Flutter process; restart; verify all values and indexed catalog state persist.

- [ ] **Step 4: Conduct three moderated usability sessions**

Recruit three participants who did not implement the tested flow. Each completes: connect/check status, search/filter/open, add directory/check progress, reindex/remove, and enable accessibility settings. At least one participant completes the entire script with keyboard only. Record task success, completion time, errors, assistance, comments, consent, input method, and severity-rated observations. Anonymize them as P01–P03.

- [ ] **Step 5: Produce usability summary**

Aggregate task completion, median time, error count, assistance rate, System Usability Scale only if the full standard questionnaire was administered, and prioritized findings. Do not invent missing participant data.

### Task 10: Enforce the strict release gate

**Files:**
- Verify: `docs/week5/evidence/`
- Modify: `docs/week5/README.md`

- [ ] **Step 1: Validate every record**

```powershell
python tools/week5/validate_evidence.py docs/week5/evidence
```

Expected: 19/19 required gates pass and exit code is 0.

- [ ] **Step 2: Check evidence commit identity**

Every platform build record must reference the same source commit. If validation fixes changed the commit, rebuild and rerun affected platform/tool gates; do not reuse stale results.

- [ ] **Step 3: Set overall status**

Set `docs/week5/README.md` to `COMPLETE` only after the strict command passes. Otherwise set `BLOCKED` and list each failing gate, its owner, and the next executable action.

- [ ] **Step 4: Commit source-independent evidence**

```powershell
git add docs/week5/evidence docs/week5/README.md
git diff --cached --check
git commit -m "test: record Week 5 cross-platform validation"
```

Do not amend the validated source commit. The evidence commit may follow it and must record the source commit hash separately.

## Plan self-review checklist

- Five targets: Windows, macOS, Linux, Android, and Web each have a real build gate.
- Named tools: NVDA, VoiceOver, Accessibility Scanner, and WAVE each require actual-run evidence.
- Scope honesty: Android/Web are accessibility validation targets; unsupported local-path operations are visibly disabled.
- Reproducibility: commands, versions, commit identities, outcomes, and attachments are mandatory.
- Strictness: missing environments and unresolved findings produce `BLOCKED`/`FAIL`, never an inferred pass.
