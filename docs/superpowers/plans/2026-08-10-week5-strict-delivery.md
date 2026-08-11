# Week 5 Strict Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在严格验收口径下完成第五周 Flutter 跨平台界面、无障碍实现、指定工具验证、可用性测试和四项正式交付物。

**Architecture:** 以现有 FastAPI MVP 为本地后端，以 Flutter 为统一 UI。Windows 是完整 E2E 主平台；macOS、Linux 是桌面构建与无障碍验证平台；Android 和 Web 分别承担 Accessibility Scanner 与 WAVE 指定工具验证。总计划只管理依赖、顺序、状态与完成门槛，具体实现由五个专题计划执行。

**Tech Stack:** Python 3.10, FastAPI, Flutter/Dart, Material 3, pytest, flutter_test, NVDA, VoiceOver, Google Accessibility Scanner, WAVE, Microsoft Word

---

## 1. 严格完成定义

第五周只有在下列项目全部有可复核证据时才标记为完成：

- [ ] Flutter 搜索、文件库、设置和结果展示功能全部实现。
- [ ] Windows release 构建通过，并完成真实后端 E2E。
- [ ] macOS build 通过，并完成 VoiceOver 核心流程验证。
- [ ] Linux build 通过，并完成启动 smoke test。
- [ ] Android build 通过，并完成 Google Accessibility Scanner 验证。
- [ ] Web build 通过，并完成 WAVE 验证。
- [ ] NVDA、纯键盘、高对比度、200% 字体缩放、减少动画和状态播报均通过。
- [ ] 至少 3 名参与者完成核心流程可用性测试。
- [ ] 四项交付物和全部证据清单通过完整性校验。

任一平台或工具因环境缺失未执行时，总状态必须为 `BLOCKED`，不能写成 `COMPLETE`。

## 2. 当前基线审计（2026-08-10）

### 已验证完成

- [x] `tools/start-mvp.ps1 -CheckOnly -Port 8001` 输出 `MVP preflight passed`。
- [x] Week 5 前置后端接口及聚焦自动化测试通过：89 tests passed。
- [x] Flutter Windows/macOS/Linux 工程骨架已纳入 Git。
- [x] `flutter analyze`、`flutter test` 和 Windows debug build 通过。
- [x] 搜索工作台设计与详细实施计划已完成。

### 尚未完成

- [ ] 当前 `frontend/lib/main.dart` 仍为 Flutter 默认计数器页面。
- [ ] 搜索工作台计划尚未实施。
- [ ] 文件库、设置和无障碍功能尚未实施。
- [ ] Android/Web target 尚未加入工程。
- [ ] 五个平台与四种无障碍工具尚无实测证据。
- [ ] 可用性测试与四项正式交付物尚未完成。

**审计结论：** 工程前置条件约完成 90%，第五周实际功能与交付约完成 25%–30%；严格口径下第五周当前状态为 `IN PROGRESS`。

## 3. 计划索引与执行顺序

| 顺序 | 专题计划 | 主要输出 | 当前状态 |
|---|---|---|---|
| 1 | `2026-08-10-flutter-search-workbench.md` | 搜索、过滤、结果、后端状态、错误/空状态 | 未实施 |
| 2 | `2026-08-10-flutter-library-settings.md` | 文件库、索引任务、设置与持久化 | 未实施 |
| 3 | `2026-08-10-flutter-accessibility.md` | Semantics、焦点、键盘、高对比度、200% 字体 | 未实施 |
| 4 | `2026-08-10-week5-cross-platform-validation.md` | 五平台构建、四工具验证、E2E 和可用性证据 | 未实施 |
| 5 | `2026-08-10-week5-deliverables.md` | UI、合规报告、可用性报告、用户指南 | 未实施 |

依赖关系：`搜索 → 文件库/设置 → 无障碍实现 → 跨平台验证 → 文档交付`。验证期间发现的缺陷返回对应实现计划修复，再重新生成证据。

## 4. Gate 0：落实外部验收资源

- [ ] **Step 1: 确认 Mac 资源**

Record the Mac owner, available date, macOS version, Flutter readiness, and VoiceOver test slot.

- [ ] **Step 2: 确认 Linux 资源**

Record the host/VM owner, distribution, graphical desktop availability, Flutter readiness, and smoke-test slot.

- [ ] **Step 3: 确认 Android 与 Scanner 资源**

Record Android SDK status, device/emulator ID, Android API level, Google Play access, Accessibility Scanner availability, and test slot.

- [ ] **Step 4: 确认 Web/WAVE 资源**

Record Chrome/Edge/Firefox version, WAVE extension availability, local-page permission, and test slot.

- [ ] **Step 5: 确认可用性参与者**

Schedule at least three participants and designate at least one complete keyboard-only session. Record only anonymized participant IDs.

If any resource is unavailable, set the affected gate to `BLOCKED` immediately while continuing all executable implementation work.

## 5. Day 1：锁定已完成前置条件

**Files:**
- Verify: `tools/start-mvp.ps1`
- Verify: `models/model-manifest.json`
- Verify: `backend/tests/`
- Verify: `frontend/windows/`
- Verify: `frontend/macos/`
- Verify: `frontend/linux/`

- [ ] **Step 1: 重跑模型与后端预检**

Run:

```powershell
pwsh -NoProfile -File tools/start-mvp.ps1 -CheckOnly -Port 8001
```

Expected: exit code 0 and `MVP preflight passed`.

- [ ] **Step 2: 重跑 Week 5 前置后端测试**

Run the exact focused test list recorded in `docs/superpowers/plans/2026-08-09-ui-backend-index-contracts.md`.

Expected: 89 tests pass, 0 fail.

- [ ] **Step 3: 验证桌面骨架**

Run:

```powershell
Set-Location frontend
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build windows --debug
```

Expected: all commands exit 0.

- [ ] **Step 4: 建立状态记录**

Create `docs/week5/README.md` with the baseline audit table from Section 2 and mark every unexecuted strict gate as `NOT RUN`.

## 6. Day 2：实施搜索工作台

**Files:**
- Execute: `docs/superpowers/plans/2026-08-10-flutter-search-workbench.md`
- Test: `frontend/test/features/search/`

- [ ] **Step 1: 执行搜索专题计划全部任务**

Follow the referenced plan in order, preserving its test-first sequence.

- [ ] **Step 2: 运行搜索验收测试**

Run:

```powershell
Set-Location frontend
flutter test test/features/search test/features/shell test/app
flutter analyze
```

Expected: exit code 0; no counter-app assertions remain.

- [ ] **Step 3: 提交搜索工作台**

Commit only the files listed by the search plan after reviewing `git diff --check`.

## 7. Day 3：实施文件库与设置

**Files:**
- Execute: `docs/superpowers/plans/2026-08-10-flutter-library-settings.md`
- Test: `frontend/test/features/library/`
- Test: `frontend/test/features/settings/`

- [ ] **Step 1: 执行文件库与设置专题计划全部任务**

- [ ] **Step 2: 运行专题验收测试**

Run:

```powershell
Set-Location frontend
flutter test test/features/library test/features/settings test/app
flutter analyze
```

Expected: exit code 0;设置重启持久化测试通过。

- [ ] **Step 3: Windows 真实后端 smoke test**

Start the backend, launch Flutter Windows, add a directory, observe job completion, list files, reindex one file, remove one file, change the backend URL, restore it, restart the app, and verify settings persistence.

- [ ] **Step 4: 提前执行 Linux 首轮构建**

On the reserved Linux environment, check out the current source commit and run `flutter build linux --release`. Record failures immediately so platform fixes do not accumulate until Day 5.

- [ ] **Step 5: 提交文件库与设置**

Commit only the files listed in the topical plan.

## 8. Day 4：实施无障碍能力与指定工具早测

**Files:**
- Execute: `docs/superpowers/plans/2026-08-10-flutter-accessibility.md`
- Test: `frontend/test/accessibility/`

- [ ] **Step 1: 执行无障碍专题计划全部任务**

- [ ] **Step 2: 运行自动化无障碍门禁**

Run:

```powershell
Set-Location frontend
flutter test test/accessibility
flutter test
flutter analyze
```

Expected: exit code 0; semantics、键盘、200% 字体、高对比度和减少动效测试通过。

- [ ] **Step 3: 完成跨平台编译适配和证据校验器**

Execute Tasks 1–3 of `2026-08-10-week5-cross-platform-validation.md`.

- [ ] **Step 4: 执行 Android Accessibility Scanner 和 Web WAVE 首轮验证**

Execute the Android and Web validation tasks, fix all actionable findings in the owning implementation plan, and rerun affected states.

- [ ] **Step 5: 提交无障碍实现**

Commit only after all existing feature tests remain green.

## 9. Day 5：跨平台验证与证据采集

**Files:**
- Execute: `docs/superpowers/plans/2026-08-10-week5-cross-platform-validation.md`
- Output: `docs/week5/evidence/`

- [ ] **Step 1: 完成 Windows + NVDA + 键盘验证**
- [ ] **Step 2: 完成 macOS + VoiceOver 验证**
- [ ] **Step 3: 完成 Linux build + smoke test**
- [ ] **Step 4: 完成 Android + Accessibility Scanner 验证**
- [ ] **Step 5: 完成 Web + WAVE 验证**
- [ ] **Step 6: 完成五类文件 E2E 与重启持久化验证**
- [ ] **Step 7: 完成至少 3 名参与者的可用性测试**
- [ ] **Step 8: 运行证据完整性校验**

Expected: evidence validator returns exit code 0 and no strict gate remains `NOT RUN`, `FAIL`, or `BLOCKED`.

## 10. Day 5：生成正式交付物

**Files:**
- Execute: `docs/superpowers/plans/2026-08-10-week5-deliverables.md`
- Output: `output/week5/`

- [ ] **Step 1: 生成四项交付物**

Required outputs:

1. Functional Cross-Platform Flutter UI package
2. Accessibility Compliance Validation Report
3. UI Usability Test Report
4. Draft Accessibility User Guide

- [ ] **Step 2: 校验 DOCX 与发布包**

Expected: documents open in Word without repair prompts, evidence links resolve, tables render correctly, and the package contains no temporary files.

- [ ] **Step 3: 更新总状态**

Set `docs/week5/README.md` to `COMPLETE` only if every gate in Section 1 is supported by evidence. Otherwise set it to `BLOCKED` and list the exact missing environment or failed check.

## 11. 最终仓库门禁

- [ ] **Step 1: 运行全量测试**

```powershell
Set-Location backend
python -m pytest -q
Set-Location ../frontend
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build windows --release
```

Expected: all commands exit 0.

- [ ] **Step 2: 检查差异和大文件**

```powershell
Set-Location ..
git diff --check
git status --short
git ls-files | ForEach-Object { Get-Item -LiteralPath $_ -ErrorAction SilentlyContinue } | Where-Object Length -GT 50MB
```

Expected: no whitespace errors; only intended tracked changes; no accidental model or build artifact added.

- [ ] **Step 3: 对照严格完成定义逐项签字**

Record reviewer, date, result, and evidence path for every checkbox in Section 1.
