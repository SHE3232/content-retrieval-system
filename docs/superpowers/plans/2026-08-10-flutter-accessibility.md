# Flutter Accessibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Week 5 Flutter workflow perceivable and operable with screen readers, keyboard-only input, high contrast, dynamic text up to 200%, visible focus, reduced motion, and status announcements.

**Architecture:** Accessibility behavior is implemented in shared widgets and app composition, then enforced by semantic-tree, focus, shortcut, layout, contrast, and animation tests. Platform screen-reader and scanner runs remain separate evidence gates in the cross-platform validation plan; automated tests prove implementation behavior but do not substitute for those tools.

**Tech Stack:** Flutter/Dart, Material 3, Semantics, FocusTraversalGroup, Shortcuts/Actions, flutter_test, WCAG contrast calculations

---

## File map

- Create: `frontend/lib/core/accessibility/live_region_message.dart`
- Create: `frontend/lib/core/accessibility/accessibility_shortcuts.dart`
- Create: `frontend/lib/core/accessibility/effective_media_query.dart`
- Modify: `frontend/lib/app/app_theme.dart`
- Modify: `frontend/lib/app/content_retrieval_app.dart`
- Modify: `frontend/lib/features/shell/app_shell.dart`
- Modify: `frontend/lib/features/search/presentation/search_page.dart`
- Modify: `frontend/lib/features/search/presentation/widgets/search_filter_panel.dart`
- Modify: `frontend/lib/features/search/presentation/widgets/search_result_tile.dart`
- Modify: `frontend/lib/features/search/presentation/widgets/search_state_view.dart`
- Modify: `frontend/lib/features/library/presentation/index_library_page.dart`
- Modify: `frontend/lib/features/library/presentation/widgets/index_job_panel.dart`
- Modify: `frontend/lib/features/library/presentation/widgets/indexed_file_tile.dart`
- Modify: `frontend/lib/features/settings/presentation/settings_page.dart`
- Create: `frontend/test/accessibility/semantics_test.dart`
- Create: `frontend/test/accessibility/keyboard_navigation_test.dart`
- Create: `frontend/test/accessibility/text_scaling_test.dart`
- Create: `frontend/test/accessibility/high_contrast_test.dart`
- Create: `frontend/test/accessibility/reduced_motion_test.dart`
- Create: `frontend/test/accessibility/support/accessibility_harness.dart`

## Acceptance matrix

| Area | Automated gate | Manual gate |
|---|---|---|
| Screen reader | semantic labels, roles, live regions | NVDA and VoiceOver |
| Keyboard | focus order, shortcuts, activation | Windows/macOS/Linux keyboard walkthrough |
| High contrast | theme tokens and ratio tests | visual review on light/dark modes |
| Dynamic text | 100/150/200% layout tests | OS scaling walkthrough |
| Reduced motion | zero-duration behavior | system reduce-motion walkthrough |
| Scanner rules | semantic/tap-target checks | Accessibility Scanner and WAVE |

### Task 1: Establish the accessibility test harness

**Files:**
- Create: `frontend/test/accessibility/support/accessibility_harness.dart`
- Create: `frontend/test/accessibility/semantics_test.dart`

- [ ] **Step 1: Build deterministic test helpers**

Create a harness that pumps the complete app with fake online status, search results, indexed files, saved settings, picker, launcher, clipboard, and a 1280×800 surface. Expose helpers for 600×900 and 200% text scale.

The harness must enable semantics and dispose the handle:

```dart
final semantics = tester.ensureSemantics();
addTearDown(semantics.dispose);
```

- [ ] **Step 2: Write failing landmark and control tests**

Assert the semantic tree contains:

- app title and current destination;
- labeled search field and search button;
- retrieval mode group, content-type group, and channel group;
- result name, match summary, open action, and copy action;
- index-library refresh/add/pagination/reindex/remove actions;
- settings groups and current values.

Assert icon-only buttons have non-empty semantic labels and tooltips. Assert decorative icons do not create duplicate spoken nodes.

- [ ] **Step 3: Verify RED**

```powershell
flutter test test/accessibility/semantics_test.dart
```

Expected: missing labels, landmarks, or semantic grouping cause failures.

- [ ] **Step 4: Commit only the harness and failing tests**

```powershell
git add test/accessibility
git commit -m "test: define Flutter accessibility contract"
```

### Task 2: Add semantic structure and live status regions

**Files:**
- Create: `frontend/lib/core/accessibility/live_region_message.dart`
- Modify: all feature widgets listed in the file map
- Modify: `frontend/test/accessibility/semantics_test.dart`

- [ ] **Step 1: Implement a reusable live region**

Use a semantic live region without relying on a platform-specific announcement API:

```dart
final class LiveRegionMessage extends StatelessWidget {
  const LiveRegionMessage({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      liveRegion: true,
      label: message,
      child: ExcludeSemantics(child: Text(message)),
    );
  }
}
```

Render it only when the message is meaningful. Give changing messages stable widget positions and keys so assistive technologies detect updates.

- [ ] **Step 2: Apply exact status messages**

Use live regions for:

| Event | Message pattern |
|---|---|
| Backend online | 后端已连接，共索引 {fileCount} 个文件。 |
| Backend offline | 后端连接已断开。 |
| Search loading | 正在搜索“{query}”。 |
| Search results | 搜索完成，找到 {hitCount} 条结果。 |
| Search empty | 搜索完成，没有匹配结果。 |
| Search failure | 搜索失败：{stableMessage} |
| Indexing progress | 索引处理中，已处理 {processed} 个文件。 |
| Indexing complete | 索引完成，成功 {succeeded}，失败 {failed}。 |
| Settings saved | 设置已保存。 |

Do not announce progress more often than once every two seconds. Do not include full file paths in automatic announcements.

- [ ] **Step 3: Group and label complex controls**

Wrap result cards and indexed-file rows in `MergeSemantics` only when it does not hide their individual actions. Otherwise use a container semantic node with a concise label and leave buttons as children. Add `header: true` to page and section headings. Add `selected: true` to the active navigation destination and filter state.

Every destructive action's semantic label must contain the file name, such as `从索引移除 guide.pdf`.

- [ ] **Step 4: Run semantics tests**

```powershell
dart format lib/core/accessibility lib/features test/accessibility
flutter test test/accessibility/semantics_test.dart
flutter analyze
```

Expected: all semantic contract tests pass with no duplicate unlabeled action nodes.

- [ ] **Step 5: Commit semantic implementation**

```powershell
git add lib/core/accessibility lib/features test/accessibility/semantics_test.dart
git commit -m "feat: add Flutter semantic structure"
```

### Task 3: Enforce keyboard navigation and visible focus

**Files:**
- Create: `frontend/lib/core/accessibility/accessibility_shortcuts.dart`
- Modify: `frontend/lib/features/shell/app_shell.dart`
- Modify: search/library/settings widgets
- Create: `frontend/test/accessibility/keyboard_navigation_test.dart`

- [ ] **Step 1: Write failing focus-order tests**

Use `tester.sendKeyEvent(LogicalKeyboardKey.tab)` and assert this order on each destination:

```text
Navigation destinations
Page primary action
Page input/filter controls in visual order
Content row actions in row order
Pagination or save/reset actions
```

Also test Shift+Tab reversal, Space/Enter activation, Escape closing dialogs/bottom sheets, and focus restoration to the invoking control.

- [ ] **Step 2: Write failing shortcut tests**

Required shortcuts:

| Shortcut | Action |
|---|---|
| Ctrl/Cmd+K | Focus search field |
| Ctrl/Cmd+1 | Open Search |
| Ctrl/Cmd+2 | Open Index Library |
| Ctrl/Cmd+3 | Open Settings |
| F5 | Refresh current network page |
| Escape | Close transient UI, otherwise unfocus search |

Tests must use `SingleActivator` and assert one action per key press.

- [ ] **Step 3: Verify RED**

```powershell
flutter test test/accessibility/keyboard_navigation_test.dart
```

- [ ] **Step 4: Implement focus scopes and actions**

Wrap the shell in `Shortcuts` + `Actions`. Use `FocusTraversalGroup(policy: OrderedTraversalPolicy())` per destination and `NumericFocusOrder` only where natural widget order does not match visual order. Do not assign focus to static text.

All custom clickable surfaces must use Material controls or `FocusableActionDetector` with Enter/Space activation. Add a visible focus style at least 2 logical pixels thick and never use color alone to signal focus.

- [ ] **Step 5: Verify and commit**

```powershell
dart format lib/core/accessibility/accessibility_shortcuts.dart lib/features test/accessibility/keyboard_navigation_test.dart
flutter test test/accessibility/keyboard_navigation_test.dart
flutter analyze
git add lib/core/accessibility/accessibility_shortcuts.dart lib/features test/accessibility/keyboard_navigation_test.dart
git commit -m "feat: add Flutter keyboard accessibility"
```

### Task 4: Make text scaling and responsive layout robust

**Files:**
- Create: `frontend/lib/core/accessibility/effective_media_query.dart`
- Modify: `frontend/lib/app/content_retrieval_app.dart`
- Modify: feature pages/widgets
- Create: `frontend/test/accessibility/text_scaling_test.dart`

- [ ] **Step 1: Write failing scale tests**

Pump search, library, settings, error dialogs, result cards, and indexing progress at `1.0`, `1.5`, and `2.0` on both surfaces. For every case assert:

```dart
expect(tester.takeException(), isNull);
expect(find.byType(OverflowBar), findsWidgets);
```

Additionally assert all primary actions remain reachable by scrolling and no horizontal scrollbar is required.

- [ ] **Step 2: Verify RED**

```powershell
flutter test test/accessibility/text_scaling_test.dart
```

- [ ] **Step 3: Compose system and user scale safely**

Implement:

```dart
double effectiveTextScale(MediaQueryData media, double preference) {
  final system = media.textScaler.scale(1.0);
  return (system * preference).clamp(1.0, 2.0).toDouble();
}
```

Preserve all other `MediaQueryData` fields. Combine reduced motion with the OS value using logical OR.

- [ ] **Step 4: Remove fixed-height text containers**

Replace fixed heights around text with minimum constraints, flexible layout, `Wrap`, and `OverflowBar`. Keep minimum touch target dimensions at 48×48 logical pixels. Use ellipsis only for secondary path text with a tooltip exposing the full value.

- [ ] **Step 5: Verify and commit**

```powershell
dart format lib/core/accessibility/effective_media_query.dart lib/app lib/features test/accessibility/text_scaling_test.dart
flutter test test/accessibility/text_scaling_test.dart
flutter analyze
git add lib/core/accessibility/effective_media_query.dart lib/app lib/features test/accessibility/text_scaling_test.dart
git commit -m "feat: support Flutter dynamic text scaling"
```

### Task 5: Implement verified high-contrast themes

**Files:**
- Modify: `frontend/lib/app/app_theme.dart`
- Modify: relevant feature widgets
- Create: `frontend/test/accessibility/high_contrast_test.dart`

- [ ] **Step 1: Add a contrast-ratio helper in the test**

Use relative luminance and this exact assertion helper:

```dart
double contrastRatio(Color foreground, Color background) {
  final lighter = math.max(foreground.computeLuminance(), background.computeLuminance());
  final darker = math.min(foreground.computeLuminance(), background.computeLuminance());
  return (lighter + 0.05) / (darker + 0.05);
}
```

Assert normal text pairs are at least 4.5:1 and large text/non-text focus or control boundaries are at least 3:1.

- [ ] **Step 2: Write failing theme tests**

Test light and dark high-contrast schemes for surface/onSurface, primary/onPrimary, error/onError, outline/surface, focused input border/surface, selected chip text/background, and disabled text/background.

- [ ] **Step 3: Verify RED**

```powershell
flutter test test/accessibility/high_contrast_test.dart
```

- [ ] **Step 4: Implement explicit high-contrast tokens**

Change theme factories to `AppTheme.light({required bool highContrast})` and `AppTheme.dark({required bool highContrast})`. For high-contrast variants use explicit color values selected by the ratio tests; do not rely only on `ColorScheme.fromSeed` defaults. Increase divider, outline, selected, and focus differentiation. Add icons/text to status states so meaning never depends on color alone.

- [ ] **Step 5: Verify and commit**

```powershell
dart format lib/app/app_theme.dart lib/features test/accessibility/high_contrast_test.dart
flutter test test/accessibility/high_contrast_test.dart
flutter analyze
git add lib/app/app_theme.dart lib/features test/accessibility/high_contrast_test.dart
git commit -m "feat: add verified high contrast themes"
```

### Task 6: Respect reduced motion

**Files:**
- Modify: application and widgets containing animations
- Create: `frontend/test/accessibility/reduced_motion_test.dart`

- [ ] **Step 1: Write failing reduced-motion tests**

With `MediaQueryData(disableAnimations: true)`, trigger navigation, filter expansion, loading skeleton, and state changes. Assert page transitions and explicit animation durations are zero, the loading state remains understandable as static content, and focus is not moved by animation completion callbacks.

- [ ] **Step 2: Implement one duration resolver**

```dart
Duration accessibleDuration(BuildContext context, Duration normal) {
  return MediaQuery.disableAnimationsOf(context) ? Duration.zero : normal;
}
```

Use it for project-owned animations. Do not replace useful progress text with animation. Avoid flashing, pulsing, or repeated opacity below 50%.

- [ ] **Step 3: Verify and commit**

```powershell
dart format lib test/accessibility/reduced_motion_test.dart
flutter test test/accessibility/reduced_motion_test.dart
flutter analyze
git add lib test/accessibility/reduced_motion_test.dart
git commit -m "feat: respect Flutter reduced motion"
```

### Task 7: Run the automated accessibility gate

**Files:**
- Verify: `frontend/lib/`
- Verify: `frontend/test/accessibility/`

- [ ] **Step 1: Run all accessibility tests together**

```powershell
dart format --output=none --set-exit-if-changed lib test
flutter test test/accessibility
flutter test
flutter analyze
flutter build windows --debug
```

Expected: all commands exit 0.

- [ ] **Step 2: Inspect Flutter guideline findings**

Add targeted `meetsGuideline` assertions where the current Flutter SDK supports them, including labeled tap targets and minimum target sizes. Record SDK-specific guideline names in test descriptions so future upgrades fail visibly rather than silently skipping checks.

- [ ] **Step 3: Perform keyboard-only smoke test**

On Windows, unplug or avoid the mouse and complete: connect backend, search, change filters, open/copy a result, add directory, inspect job, reindex, remove, change settings, and reset. Record observed focus defects for immediate correction.

- [ ] **Step 4: Audit implementation versus manual gates**

Confirm this plan does not mark NVDA, VoiceOver, Accessibility Scanner, or WAVE as passed. Those statuses are updated only by evidence produced through `2026-08-10-week5-cross-platform-validation.md`.

- [ ] **Step 5: Commit verification fixes**

```powershell
git diff --check
git status --short
```

Commit only verified source and test corrections.

## Plan self-review checklist

- Perceivable: headings, groups, status changes, results, progress, and errors have semantic representations.
- Operable: every action is reachable, focus-visible, keyboard-activatable, and ordered.
- Adaptable: layouts pass 200% text scale on desktop and narrow validation surfaces.
- Distinguishable: normal text meets 4.5:1; boundaries and large text meet 3:1; status does not depend only on color.
- Honest validation: automated tests are implementation gates, not substitutes for named assistive-technology runs.
