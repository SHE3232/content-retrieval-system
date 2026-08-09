# Flutter Desktop Scaffold Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recreate the default `content_retrieval_app` Flutter desktop project under `frontend/` and commit its source, tests, and Windows/macOS/Linux project files to Git.

**Architecture:** Run the Flutter 3.44.6 official generator from the clean worktree root to create `frontend/` with only the three desktop platforms enabled. Keep the generated counter application and widget test unchanged, rely on Flutter's generated ignore rules for caches and build products, then verify analysis, tests, the Windows build, platform manifests, and the staged Git boundary.

**Tech Stack:** Flutter 3.44.6, Dart 3.12.2, Windows PowerShell, Git

---

## File map

- Create: `frontend/pubspec.yaml` — package identity, Dart constraint, Flutter dependency, and lint/test dependencies.
- Create: `frontend/pubspec.lock` — application dependency lockfile.
- Create: `frontend/lib/main.dart` — Flutter's default counter application.
- Create: `frontend/test/widget_test.dart` — Flutter's default counter increment widget test.
- Create: `frontend/windows/` — CMake configuration, generated plugin bridge sources, Win32 runner, resources, and icon.
- Create: `frontend/macos/` — Flutter configuration, Swift runner, Xcode project/workspace, resources, entitlements, and runner test target.
- Create: `frontend/linux/` — CMake configuration, generated plugin bridge sources, and GTK runner.
- Create: `frontend/.gitignore`, `frontend/.metadata`, `frontend/analysis_options.yaml`, `frontend/README.md` — standard Flutter project metadata and repository rules.
- Preserve: `backend/`, root untracked PDF, `output/`, and `tmp/` — outside this implementation boundary.

### Task 1: Confirm the generation boundary

**Files:**
- Inspect: `frontend/`
- Inspect: `.gitignore`
- Inspect: `.git/info/exclude`

- [ ] **Step 1: Confirm the repository and Flutter toolchain state**

Run from `F:\contentretrivalsystem\.worktrees\flutter-desktop-scaffold`:

```powershell
git status --short --branch
flutter --version
```

Expected: branch `master`; Flutter reports 3.44.6 and Dart 3.12.2. Existing root-level PDF, `output/`, and `tmp/` entries may remain untracked.

- [ ] **Step 2: Prove the required project files are absent and no frontend files are tracked**

Run:

```powershell
$required = @(
  'frontend/pubspec.yaml',
  'frontend/lib/main.dart',
  'frontend/test/widget_test.dart',
  'frontend/windows/CMakeLists.txt',
  'frontend/macos/Runner.xcodeproj/project.pbxproj',
  'frontend/linux/CMakeLists.txt'
)
$present = $required | Where-Object { Test-Path -LiteralPath $_ }
$tracked = @(git ls-files -- frontend)
if ($present.Count -ne 0) { throw "Unexpected existing scaffold files: $($present -join ', ')" }
if ($tracked.Count -ne 0) { throw "Unexpected tracked frontend files: $($tracked -join ', ')" }
Write-Output 'Precondition verified: scaffold absent and frontend untracked.'
```

Expected: `Precondition verified: scaffold absent and frontend untracked.`

### Task 2: Generate the official desktop scaffold

**Files:**
- Create: `frontend/pubspec.yaml`
- Create: `frontend/pubspec.lock`
- Create: `frontend/lib/main.dart`
- Create: `frontend/test/widget_test.dart`
- Create: `frontend/windows/**`
- Create: `frontend/macos/**`
- Create: `frontend/linux/**`
- Create: `frontend/.gitignore`
- Create: `frontend/.metadata`
- Create: `frontend/analysis_options.yaml`
- Create: `frontend/README.md`

- [ ] **Step 1: Run Flutter's generator from the clean worktree root**

Run:

```powershell
Set-Location -LiteralPath 'F:\contentretrivalsystem\.worktrees\flutter-desktop-scaffold'
flutter create --platforms=windows,macos,linux --project-name content_retrieval_app frontend
```

Expected: Flutter reports project creation, dependency resolution, and `All done!` without replacing or editing files outside `frontend/`.

- [ ] **Step 2: Resolve application dependencies explicitly**

Run from `F:\contentretrivalsystem\.worktrees\flutter-desktop-scaffold\frontend`:

```powershell
flutter pub get
```

Expected: `Got dependencies!` and exit code 0.

- [ ] **Step 3: Confirm package identity and the default test import**

Run:

```powershell
Select-String -Path 'pubspec.yaml' -Pattern '^name: content_retrieval_app$'
Select-String -Path 'test\widget_test.dart' -Pattern "package:content_retrieval_app/main.dart"
```

Expected: each command returns exactly one matching line.

### Task 3: Verify Dart source behavior

**Files:**
- Verify: `frontend/lib/main.dart`
- Verify: `frontend/test/widget_test.dart`
- Verify: `frontend/pubspec.yaml`

- [ ] **Step 1: Check formatting without rewriting generated source**

Run from `F:\contentretrivalsystem\.worktrees\flutter-desktop-scaffold\frontend`:

```powershell
dart format --output=none --set-exit-if-changed lib test
```

Expected: two files processed, zero files changed, exit code 0.

- [ ] **Step 2: Run static analysis**

Run:

```powershell
flutter analyze
```

Expected: `No issues found!` and exit code 0.

- [ ] **Step 3: Run the generated widget test**

Run:

```powershell
flutter test
```

Expected: the counter increment smoke test passes and the final output contains `All tests passed!`.

### Task 4: Verify the desktop platform projects

**Files:**
- Verify: `frontend/windows/**`
- Verify: `frontend/macos/**`
- Verify: `frontend/linux/**`

- [ ] **Step 1: Assert the cross-platform project manifest**

Run from `F:\contentretrivalsystem\.worktrees\flutter-desktop-scaffold`:

```powershell
$required = @(
  'frontend/windows/CMakeLists.txt',
  'frontend/windows/flutter/CMakeLists.txt',
  'frontend/windows/flutter/generated_plugin_registrant.cc',
  'frontend/windows/flutter/generated_plugin_registrant.h',
  'frontend/windows/flutter/generated_plugins.cmake',
  'frontend/windows/runner/main.cpp',
  'frontend/windows/runner/flutter_window.cpp',
  'frontend/windows/runner/win32_window.cpp',
  'frontend/windows/runner/Runner.rc',
  'frontend/windows/runner/resources/app_icon.ico',
  'frontend/macos/Flutter/Flutter-Debug.xcconfig',
  'frontend/macos/Flutter/Flutter-Release.xcconfig',
  'frontend/macos/Flutter/GeneratedPluginRegistrant.swift',
  'frontend/macos/Runner/AppDelegate.swift',
  'frontend/macos/Runner/MainFlutterWindow.swift',
  'frontend/macos/Runner/Info.plist',
  'frontend/macos/Runner/Configs/AppInfo.xcconfig',
  'frontend/macos/Runner.xcodeproj/project.pbxproj',
  'frontend/macos/Runner.xcodeproj/xcshareddata/xcschemes/Runner.xcscheme',
  'frontend/macos/Runner.xcworkspace/contents.xcworkspacedata',
  'frontend/macos/RunnerTests/RunnerTests.swift',
  'frontend/linux/CMakeLists.txt',
  'frontend/linux/flutter/CMakeLists.txt',
  'frontend/linux/flutter/generated_plugin_registrant.cc',
  'frontend/linux/flutter/generated_plugin_registrant.h',
  'frontend/linux/flutter/generated_plugins.cmake',
  'frontend/linux/runner/CMakeLists.txt',
  'frontend/linux/runner/main.cc',
  'frontend/linux/runner/my_application.cc',
  'frontend/linux/runner/my_application.h'
)
$missing = $required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }
if ($missing.Count -ne 0) { throw "Missing platform files: $($missing -join ', ')" }
Write-Output "Platform manifest verified: $($required.Count)/$($required.Count) files present."
```

Expected: `Platform manifest verified: 30/30 files present.`

- [ ] **Step 2: Build the Windows debug application**

Run from `F:\contentretrivalsystem\.worktrees\flutter-desktop-scaffold\frontend`:

```powershell
flutter build windows --debug
```

Expected: exit code 0 and a debug executable under `build\windows\x64\runner\Debug\`. macOS and Linux are not built on the Windows host.

### Task 5: Stage, audit, and commit the scaffold

**Files:**
- Stage: `frontend/**` except generated and ignored caches/build products.

- [ ] **Step 1: Stage only the frontend project**

Run from `F:\contentretrivalsystem\.worktrees\flutter-desktop-scaffold`:

```powershell
git add -- frontend
```

Expected: Git stages the Flutter project while generated ignore rules exclude `.dart_tool/`, `build/`, `.idea/`, and platform `ephemeral/` paths.

- [ ] **Step 2: Verify the staged boundary and mandatory paths**

Run:

```powershell
$staged = @(git diff --cached --name-only)
$unexpected = $staged | Where-Object { -not $_.StartsWith('frontend/') }
$required = @(
  'frontend/pubspec.yaml',
  'frontend/pubspec.lock',
  'frontend/lib/main.dart',
  'frontend/test/widget_test.dart',
  'frontend/windows/CMakeLists.txt',
  'frontend/macos/Runner.xcodeproj/project.pbxproj',
  'frontend/linux/CMakeLists.txt'
)
$missing = $required | Where-Object { $_ -notin $staged }
$forbidden = $staged | Where-Object {
  $_ -match '(^|/)(\.dart_tool|build|\.idea|ephemeral)(/|$)'
}
if ($unexpected.Count -ne 0) { throw "Staged outside frontend: $($unexpected -join ', ')" }
if ($missing.Count -ne 0) { throw "Required files not staged: $($missing -join ', ')" }
if ($forbidden.Count -ne 0) { throw "Generated files staged: $($forbidden -join ', ')" }
Write-Output "Staged boundary verified: $($staged.Count) frontend files."
```

Expected: a positive staged file count, no paths outside `frontend/`, every mandatory path present, and no generated cache/build path present.

- [ ] **Step 3: Check the staged patch and ignored paths**

Run:

```powershell
git diff --cached --check
git status --short --ignored frontend
```

Expected: `git diff --cached --check` has no output; status shows source/config files staged and caches/build products ignored.

- [ ] **Step 4: Commit the generated project**

Run:

```powershell
git commit -m "feat: restore Flutter desktop scaffold"
```

Expected: one implementation commit containing only `frontend/` paths.

- [ ] **Step 5: Verify the committed result**

Run:

```powershell
git show --stat --oneline --decorate HEAD
git status --short --branch
```

Expected: `HEAD` is `feat: restore Flutter desktop scaffold`; the Flutter files no longer appear as pending changes; the pre-existing root PDF, `output/`, and `tmp/` entries remain untracked and untouched.
