# Local Content Retrieval UI Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the existing Flutter Material 3 interface into the approved “quiet research desk” experience, with search as the primary task, explainable continuous result lists, progressive filters, and consistent library/settings surfaces.

**Architecture:** Preserve the current controllers, API contracts, persistence, and platform services. Add small presentational widgets for the shared workspace header, backend status indicator, and search stage; keep page widgets responsible for composition and breakpoints while controller-backed widgets retain existing behavior.

**Tech Stack:** Flutter 3.44.6, Dart 3.12.2, Material 3, `ChangeNotifier`/`ListenableBuilder`, `flutter_test` widget and semantics tests.

---

## Scope and file map

The plan changes one subsystem: the existing `frontend/` Flutter application. Backend routes, request models, storage, and settings formats remain unchanged.

**Create:**

- `frontend/lib/core/presentation/workspace_header.dart`: reusable responsive page title, description, and action layout.
- `frontend/lib/features/search/presentation/widgets/backend_status_indicator.dart`: compact checking/online/offline state and retry action.
- `frontend/lib/features/search/presentation/widgets/search_stage.dart`: the approved search-first content, input, shortcut hint, submit action, and compact filter entry.

**Modify:**

- `frontend/lib/app/app_theme.dart`: tonal surface hierarchy, button sizes, card elevation, focus-safe component themes.
- `frontend/lib/features/shell/app_shell.dart`: brand presence and quiet navigation surface.
- `frontend/lib/features/search/presentation/search_page.dart`: compose workspace header, search stage, results, and persistent/progressive filters.
- `frontend/lib/features/search/presentation/widgets/search_filter_panel.dart`: active-filter count and refined filter header.
- `frontend/lib/features/search/presentation/widgets/search_state_view.dart`: task-oriented initial/loading/empty/failure/success states.
- `frontend/lib/features/search/presentation/widgets/search_result_tile.dart`: explainable continuous result-row layout.
- `frontend/lib/features/library/presentation/index_library_page.dart`: shared page header and continuous catalog list.
- `frontend/lib/features/library/presentation/widgets/index_job_panel.dart`: tonal transient job surface.
- `frontend/lib/features/library/presentation/widgets/indexed_file_tile.dart`: flat catalog row with responsive actions.
- `frontend/lib/features/settings/presentation/settings_page.dart`: shared page header and tonal sections without elevated cards.

**Test:**

- `frontend/test/widget_test.dart`
- `frontend/test/features/search/search_page_test.dart`
- `frontend/test/features/library/index_library_page_test.dart`
- `frontend/test/features/settings/settings_page_test.dart`
- `frontend/test/accessibility/semantics_test.dart`

Baseline before implementation: `flutter analyze` passes and `flutter test` reports 178 passing tests.

### Task 1: Establish the quiet tonal theme and branded shell

**Files:**

- Modify: `frontend/lib/app/app_theme.dart:1-181`
- Modify: `frontend/lib/features/shell/app_shell.dart:1-183`
- Test: `frontend/test/widget_test.dart:1-619`

- [ ] **Step 1: Write failing theme and shell tests**

Add these assertions to the existing theme test in `frontend/test/widget_test.dart`:

```dart
final theme = AppTheme.light();
final scheme = theme.colorScheme;

expect(theme.scaffoldBackgroundColor, scheme.surfaceContainerLowest);
expect(theme.navigationRailTheme.backgroundColor, scheme.surfaceContainerLow);
expect(theme.cardTheme.elevation, 0);
expect(
  theme.outlinedButtonTheme.style!.minimumSize!.resolve({}),
  const Size(0, 48),
);
expect(
  theme.iconButtonTheme.style!.minimumSize!.resolve({}),
  const Size.square(48),
);
```

Extend `shows all destinations and the injected search page initially`:

```dart
expect(find.byKey(const Key('app-brand')), findsOneWidget);
expect(find.text('本地内容检索'), findsOneWidget);
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
cd frontend
flutter test test/widget_test.dart --plain-name "builds coordinated light and dark Material 3 themes"
flutter test test/widget_test.dart --plain-name "shows all destinations and the injected search page initially"
```

Expected: FAIL because the scaffold and navigation still use `surface`, the outlined/icon button minimum sizes are unset, and the shell has no `app-brand` widget.

- [ ] **Step 3: Implement the tonal theme and shell brand**

In `AppTheme._build`, change the scaffold and navigation colors and add the following card, outlined-button, and icon-button themes. Leave the existing input, chip, filled-button, tooltip, and divider theme objects unchanged.

```dart
return ThemeData(
  useMaterial3: true,
  brightness: brightness,
  colorScheme: scheme,
  scaffoldBackgroundColor: scheme.surfaceContainerLowest,
  cardTheme: CardThemeData(
    elevation: 0,
    color: scheme.surfaceContainerLow,
    margin: EdgeInsets.zero,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(12),
    ),
  ),
  outlinedButtonTheme: OutlinedButtonThemeData(
    style: OutlinedButton.styleFrom(
      minimumSize: const Size(0, 48),
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
      shape: controlShape,
    ),
  ),
  iconButtonTheme: IconButtonThemeData(
    style: IconButton.styleFrom(
      minimumSize: const Size.square(48),
      shape: controlShape,
    ),
  ),
  navigationRailTheme: NavigationRailThemeData(
    backgroundColor: scheme.surfaceContainerLow,
    indicatorColor: scheme.secondaryContainer,
    indicatorShape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(14),
    ),
    minWidth: 72,
    selectedIconTheme: IconThemeData(color: scheme.onSecondaryContainer),
    unselectedIconTheme: IconThemeData(color: scheme.onSurfaceVariant),
    selectedLabelTextStyle: TextStyle(
      color: scheme.onSurface,
      fontWeight: FontWeight.w600,
    ),
    unselectedLabelTextStyle: TextStyle(color: scheme.onSurfaceVariant),
  ),
);
```

Pass a brand widget to `NavigationRail.leading`:

```dart
NavigationRail(
  extended: extended,
  leading: _AppBrand(extended: extended),
)
```

Add the private widget at the end of `app_shell.dart`:

```dart
final class _AppBrand extends StatelessWidget {
  const _AppBrand({required this.extended});

  final bool extended;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      key: const Key('app-brand'),
      container: true,
      label: '本地内容检索',
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 20),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            DecoratedBox(
              decoration: BoxDecoration(
                color: scheme.primary,
                borderRadius: BorderRadius.circular(10),
              ),
              child: SizedBox.square(
                dimension: 36,
                child: Icon(Icons.manage_search, color: scheme.onPrimary),
              ),
            ),
            if (extended) ...[
              const SizedBox(width: 10),
              Text(
                '本地内容检索',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Run shell, theme, and accessibility tests**

Run:

```powershell
cd frontend
flutter test test/widget_test.dart test/accessibility/high_contrast_test.dart test/accessibility/keyboard_navigation_test.dart
```

Expected: PASS; navigation still changes destinations, high-contrast ratios remain valid, and the new brand is visible only once in extended mode.

- [ ] **Step 5: Commit the theme and shell change**

```powershell
git add frontend/lib/app/app_theme.dart frontend/lib/features/shell/app_shell.dart frontend/test/widget_test.dart
git commit -m "feat: establish quiet research desk shell"
```

### Task 2: Build the shared workspace header and search-first stage

**Files:**

- Create: `frontend/lib/core/presentation/workspace_header.dart`
- Create: `frontend/lib/features/search/presentation/widgets/backend_status_indicator.dart`
- Create: `frontend/lib/features/search/presentation/widgets/search_stage.dart`
- Modify: `frontend/lib/features/search/presentation/search_page.dart:1-334`
- Modify: `frontend/lib/features/search/presentation/widgets/search_filter_panel.dart:1-158`
- Test: `frontend/test/features/search/search_page_test.dart:1-1090`

- [ ] **Step 1: Write failing search-stage and progressive-filter tests**

Add to `search_page_test.dart`:

```dart
testWidgets('search stage leads with the approved task language', (tester) async {
  await _SearchHarness.create(tester);

  expect(find.byKey(const Key('search-stage')), findsOneWidget);
  expect(find.text('找回你记得的内容'), findsOneWidget);
  expect(find.text('描述一个概念、一段话，或图片中的内容。'), findsOneWidget);
  expect(find.text('Ctrl K'), findsOneWidget);
});

testWidgets('compact filter entry reports active restrictions', (tester) async {
  final harness = await _SearchHarness.create(
    tester,
    surfaceSize: const Size(900, 720),
  );
  harness.searchController.toggleContentType(SearchContentType.images);
  await tester.pump();

  expect(find.byKey(const Key('search-filter-button')), findsOneWidget);
  expect(find.byKey(const Key('search-filter-count')), findsOneWidget);
  expect(find.text('1'), findsOneWidget);
});
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
cd frontend
flutter test test/features/search/search_page_test.dart --plain-name "search stage leads with the approved task language"
flutter test test/features/search/search_page_test.dart --plain-name "compact filter entry reports active restrictions"
```

Expected: FAIL because the approved content and filter-count badge do not exist.

- [ ] **Step 3: Add the focused presentational widgets**

Create `workspace_header.dart`:

```dart
import 'package:flutter/material.dart';

final class WorkspaceHeader extends StatelessWidget {
  const WorkspaceHeader({
    super.key,
    required this.title,
    required this.description,
    this.actions = const [],
  });

  final String title;
  final String description;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final text = Semantics(
      header: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 4),
          Text(
            description,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
    return LayoutBuilder(
      builder: (context, constraints) {
        final stacked = constraints.maxWidth < 620 ||
            MediaQuery.textScalerOf(context).scale(14) >= 21;
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
          child: stacked
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    text,
                    if (actions.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Wrap(spacing: 8, runSpacing: 8, children: actions),
                    ],
                  ],
                )
              : Row(
                  children: [
                    Expanded(child: text),
                    if (actions.isNotEmpty) ...actions,
                  ],
                ),
        );
      },
    );
  }
}
```

Create `backend_status_indicator.dart` with the complete state mapping:

```dart
import 'dart:async';

import 'package:content_retrieval_app/core/accessibility/live_region_message.dart';
import 'package:content_retrieval_app/features/status/backend_status_controller.dart';
import 'package:content_retrieval_app/features/status/backend_status_models.dart';
import 'package:flutter/material.dart';

final class BackendStatusIndicator extends StatelessWidget {
  const BackendStatusIndicator({super.key, required this.controller});

  final BackendStatusController controller;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (label, icon, color) = switch (controller.state) {
      BackendConnectionState.checking => (
        '正在检测后端',
        Icons.sync,
        theme.colorScheme.onSurfaceVariant,
      ),
      BackendConnectionState.online => (
        '后端在线',
        Icons.check_circle_outline,
        theme.brightness == Brightness.dark
            ? Colors.green.shade300
            : Colors.green.shade800,
      ),
      BackendConnectionState.offline => (
        '后端离线',
        Icons.error_outline,
        theme.colorScheme.error,
      ),
    };
    final announcement = switch (controller.state) {
      BackendConnectionState.checking => '正在检测后端。',
      BackendConnectionState.online =>
        '后端已连接，共索引 ${controller.stats?.fileCount ?? 0} 个文件。',
      BackendConnectionState.offline => '后端连接已断开。',
    };
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: ColoredBox(
        color: theme.colorScheme.surfaceContainerLow,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          child: LiveRegionMessage(
            message: announcement,
            excludeChildSemantics: false,
            child: Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 4,
              runSpacing: 4,
              children: [
                Icon(icon, size: 18, color: color),
                Text(
                  label,
                  style: theme.textTheme.labelLarge?.copyWith(color: color),
                ),
                if (controller.state == BackendConnectionState.offline)
                  TextButton.icon(
                    key: const Key('backend-refresh-button'),
                    onPressed: () => unawaited(controller.refresh()),
                    icon: const Icon(Icons.refresh, size: 18),
                    label: const Text('重新检测'),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

Create `search_stage.dart`:

```dart
import 'package:flutter/material.dart';

final class SearchStage extends StatelessWidget {
  const SearchStage({
    super.key,
    required this.queryController,
    required this.queryFocusNode,
    required this.canSubmit,
    required this.showFilterButton,
    required this.activeFilterCount,
    required this.inlineError,
    required this.onQueryChanged,
    required this.onSubmit,
    required this.onShowFilters,
  });

  final TextEditingController queryController;
  final FocusNode queryFocusNode;
  final bool canSubmit;
  final bool showFilterButton;
  final int activeFilterCount;
  final String? inlineError;
  final ValueChanged<String> onQueryChanged;
  final Future<void> Function() onSubmit;
  final VoidCallback onShowFilters;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return DecoratedBox(
      key: const Key('search-stage'),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '找回你记得的内容',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '描述一个概念、一段话，或图片中的内容。',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            LayoutBuilder(
              builder: (context, constraints) {
                final largeText =
                    MediaQuery.textScalerOf(context).scale(14) >= 21;
                final stacked = constraints.maxWidth < 720 || largeText;
                final field = TextField(
                  key: const Key('search-query-field'),
                  controller: queryController,
                  focusNode: queryFocusNode,
                  textInputAction: TextInputAction.search,
                  onChanged: onQueryChanged,
                  onSubmitted: canSubmit ? (_) => onSubmit() : null,
                  decoration: InputDecoration(
                    labelText: '搜索内容',
                    hintText: '输入关键词，或描述你记得的内容',
                    errorText: inlineError,
                    prefixIcon: const Icon(Icons.search),
                    suffixIconConstraints: const BoxConstraints(minWidth: 62),
                    suffixIcon: const Center(
                      child: Text(
                        'Ctrl K',
                        style: TextStyle(fontSize: 11),
                      ),
                    ),
                  ),
                );
                final actions = Wrap(
                  alignment: WrapAlignment.end,
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    if (showFilterButton)
                      Badge(
                        key: const Key('search-filter-count'),
                        isLabelVisible: activeFilterCount > 0,
                        label: Text('$activeFilterCount'),
                        child: OutlinedButton.icon(
                          key: const Key('search-filter-button'),
                          onPressed: onShowFilters,
                          icon: const Icon(Icons.tune),
                          label: const Text('筛选'),
                        ),
                      ),
                    FilledButton.icon(
                      key: const Key('search-submit-button'),
                      onPressed: canSubmit ? onSubmit : null,
                      icon: const Icon(Icons.search),
                      label: const Text('搜索'),
                    ),
                  ],
                );
                if (stacked) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      field,
                      const SizedBox(height: 10),
                      actions,
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: field),
                    const SizedBox(width: 10),
                    actions,
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
```

Export a deterministic restriction count from `search_filter_panel.dart`:

```dart
int activeSearchFilterCount(SearchController controller) {
  var count = controller.mode == RetrievalMode.hybrid ? 0 : 1;
  count += SearchChannel.values.length - controller.channels.length;
  count += SearchContentType.values.length - controller.contentTypes.length;
  return count;
}
```

Compose `WorkspaceHeader`, `BackendStatusIndicator`, and `SearchStage` in `SearchPage`; preserve `_submit`, `_filtersChanged`, `_clearFilters`, modal behavior, breakpoints, keys, and controller wiring.

- [ ] **Step 4: Run all search-page tests**

Run:

```powershell
cd frontend
flutter test test/features/search/search_page_test.dart
```

Expected: PASS, including the two new tests and all existing submit, filter, offline, keyboard, and responsive behavior tests.

- [ ] **Step 5: Commit the search-stage composition**

```powershell
git add frontend/lib/core/presentation/workspace_header.dart frontend/lib/features/search/presentation/search_page.dart frontend/lib/features/search/presentation/widgets/backend_status_indicator.dart frontend/lib/features/search/presentation/widgets/search_stage.dart frontend/lib/features/search/presentation/widgets/search_filter_panel.dart frontend/test/features/search/search_page_test.dart
git commit -m "feat: focus the workspace on search"
```

### Task 3: Convert search states and results into a trusted continuous list

**Files:**

- Modify: `frontend/lib/features/search/presentation/widgets/search_state_view.dart:1-202`
- Modify: `frontend/lib/features/search/presentation/widgets/search_result_tile.dart:1-216`
- Test: `frontend/test/features/search/search_page_test.dart:1-1090`

- [ ] **Step 1: Write failing state and result-list tests**

Add or update assertions:

```dart
testWidgets('initial state teaches content-first searching', (tester) async {
  await _SearchHarness.create(tester);

  expect(find.text('说出你还记得的内容'), findsOneWidget);
  expect(find.textContaining('哪个 PDF 讲过键盘导航'), findsOneWidget);
});

testWidgets('success uses a continuous explainable result list', (tester) async {
  final harness = await _SearchHarness.create(tester)
    ..searchService.results.add(
      _response(
        hits: [
          _hit(
            fileId: 'research-pdf',
            name: 'research.pdf',
            matchReasons: const [SearchChannel.textSemantic],
          ),
        ],
      ),
    );
  await harness.search('research');

  expect(find.byKey(const Key('search-result-list')), findsOneWidget);
  expect(find.byKey(const Key('search-result-row-research-pdf')), findsOneWidget);
  expect(find.text('PDF'), findsOneWidget);
  expect(find.text('找到 1 条相关资料'), findsOneWidget);
  expect(find.textContaining('候选'), findsNothing);
  expect(find.textContaining('ms'), findsNothing);
});
```

In the existing metadata test, replace:

```dart
expect(find.text('候选 31 个，用时 12.75 ms'), findsOneWidget);
```

with:

```dart
expect(find.text('找到 1 条相关资料'), findsOneWidget);
expect(find.text('命中：关键词'), findsOneWidget);
expect(find.text('命中：文本语义'), findsOneWidget);
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
cd frontend
flutter test test/features/search/search_page_test.dart --plain-name "initial state teaches content-first searching"
flutter test test/features/search/search_page_test.dart --plain-name "success uses a continuous explainable result list"
```

Expected: FAIL because the current copy, metrics summary, file badge, and continuous-list keys are absent.

- [ ] **Step 3: Implement the continuous list and explainable row**

Update the initial state in `SearchStateView`:

```dart
SearchViewState.initial => _message(
  context,
  icon: Icons.manage_search,
  title: '说出你还记得的内容',
  body: '例如：“哪个 PDF 讲过键盘导航？”\n支持文档、文本文件和图片。',
),
```

Replace the success summary and spaced cards with one clipped list:

```dart
Text(
  '找到 ${response.hits.length} 条相关资料',
  key: const Key('search-summary'),
  style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
),
const SizedBox(height: 10),
Expanded(
  child: ClipRRect(
    borderRadius: BorderRadius.circular(12),
    child: Material(
      key: const Key('search-result-list'),
      color: theme.colorScheme.surface,
      child: ListView.separated(
        padding: const EdgeInsets.only(bottom: 20),
        itemCount: response.hits.length,
        separatorBuilder: (_, _) => const Divider(),
        itemBuilder: (_, index) => SearchResultTile(
          key: ValueKey((response, response.hits[index].fileId)),
          rowKey: Key('search-result-row-${response.hits[index].fileId}'),
          hit: response.hits[index],
          fileLauncher: fileLauncher,
          pathClipboard: pathClipboard,
        ),
      ),
    ),
  ),
),
```

Add `rowKey` to `SearchResultTile`. Replace its bordered `DecoratedBox` with a responsive row rooted at `Material(key: rowKey, color: Colors.transparent)`. Use a 44px tonal file badge derived from the filename extension:

```dart
String _fileTypeLabel(String name) {
  final dot = name.lastIndexOf('.');
  if (dot < 0 || dot == name.length - 1) return 'FILE';
  final extension = name.substring(dot + 1).toUpperCase();
  return extension.length <= 5 ? extension : 'FILE';
}
```

Render every reason as `Text('命中：${searchChannelLabel(reason)}')`. Preserve the existing open/copy semantics, keys, pending states, inline errors, path tooltip, location selection, and exception handling. Use `LayoutBuilder` or `Wrap` so the action group moves below metadata when the row is narrow or text is enlarged.

Change loading separators from 12px gaps to `Divider`, and use one list surface instead of three bordered cards. Keep three `search-loading-skeleton` keys and the existing live-region message.

- [ ] **Step 4: Run search behavior, semantics, and overflow tests**

Run:

```powershell
cd frontend
flutter test test/features/search/search_page_test.dart test/accessibility/semantics_test.dart
```

Expected: PASS. Existing open/copy, pending, error-isolation, live-region, 1280×720, 1440×900, and 640×720 tests remain green.

- [ ] **Step 5: Commit trusted search results**

```powershell
git add frontend/lib/features/search/presentation/widgets/search_state_view.dart frontend/lib/features/search/presentation/widgets/search_result_tile.dart frontend/test/features/search/search_page_test.dart
git commit -m "feat: explain search results in a continuous list"
```

### Task 4: Align the index library with the same workspace language

**Files:**

- Modify: `frontend/lib/features/library/presentation/index_library_page.dart:1-318`
- Modify: `frontend/lib/features/library/presentation/widgets/index_job_panel.dart:1-82`
- Modify: `frontend/lib/features/library/presentation/widgets/indexed_file_tile.dart:1-168`
- Test: `frontend/test/features/library/index_library_page_test.dart:1-279`

- [ ] **Step 1: Write failing library hierarchy tests**

Add to `index_library_page_test.dart`:

```dart
testWidgets('library uses a workspace header and continuous catalog', (tester) async {
  final service = _PageService()..pages.add(_page());
  final controller = IndexLibraryController(
    service: service,
    directoryPicker: _PagePicker(),
  );
  addTearDown(controller.dispose);
  await controller.load();

  await tester.pumpWidget(_app(controller));

  expect(find.text('管理可搜索的本地资料'), findsOneWidget);
  expect(find.byKey(const Key('library-file-list')), findsOneWidget);
  final row = find.byKey(const Key('indexed-file-row-file-1'));
  expect(row, findsOneWidget);
  expect(find.descendant(of: row, matching: find.byType(Card)), findsNothing);
});
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
cd frontend
flutter test test/features/library/index_library_page_test.dart --plain-name "library uses a workspace header and continuous catalog"
```

Expected: FAIL because the approved subtitle/list/row keys do not exist and `IndexedFileTile` is still a `Card`.

- [ ] **Step 3: Implement the header, transient job surface, and flat rows**

Import and use `WorkspaceHeader` at the top of `IndexLibraryPage`:

```dart
WorkspaceHeader(
  title: '索引库',
  description: '管理可搜索的本地资料',
  actions: [
    IconButton(
      tooltip: '刷新索引库',
      onPressed: controller.isRefreshing ? null : controller.refresh,
      icon: const Icon(Icons.refresh),
    ),
    FilledButton.icon(
      onPressed: controller.directoryPicker.isSupported &&
              !controller.isMutationInProgress
          ? controller.selectDirectoryAndStart
          : null,
      icon: const Icon(Icons.create_new_folder_outlined),
      label: const Text('添加文件夹'),
    ),
  ],
),
```

Give the catalog list `key: const Key('library-file-list')`, change separators to `Divider`, and remove per-row 8px gaps.

Add `rowKey` or derive `Key('indexed-file-row-${file.fileId}')` inside `IndexedFileTile`. Replace `Card` with:

```dart
Material(
  key: Key('indexed-file-row-${file.fileId}'),
  color: Colors.transparent,
  child: Padding(
    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
    child: /* existing metadata and responsive action Wrap */,
  ),
)
```

Replace the `IndexJobPanel` card/elevation with a `DecoratedBox` using `surfaceContainerLow`, 12px radius, 16px padding, and `key: const Key('index-job-panel')`. Preserve progress, failure counts, failure-details action, and textual semantics.

- [ ] **Step 4: Run library and semantics tests**

Run:

```powershell
cd frontend
flutter test test/features/library/index_library_page_test.dart test/accessibility/semantics_test.dart
```

Expected: PASS, including confirmation dialogs, job text, file operations, empty state, and 200% text-scale overflow coverage.

- [ ] **Step 5: Commit the library refinement**

```powershell
git add frontend/lib/features/library/presentation/index_library_page.dart frontend/lib/features/library/presentation/widgets/index_job_panel.dart frontend/lib/features/library/presentation/widgets/indexed_file_tile.dart frontend/test/features/library/index_library_page_test.dart
git commit -m "feat: refine the searchable library workspace"
```

### Task 5: Replace settings cards with quiet tonal sections

**Files:**

- Modify: `frontend/lib/features/settings/presentation/settings_page.dart:1-284`
- Test: `frontend/test/features/settings/settings_page_test.dart:1-138`

- [ ] **Step 1: Write failing settings-surface tests**

Add to `settings_page_test.dart`:

```dart
testWidgets('settings uses tonal sections instead of elevated cards', (tester) async {
  final controller = SettingsController(
    SettingsRepository(_PageSettingsStore()),
  );
  addTearDown(controller.dispose);
  await controller.load();

  await tester.pumpWidget(_app(controller));

  expect(find.text('偏好设置只保存在这台设备上'), findsOneWidget);
  expect(find.byKey(const Key('settings-connection-section')), findsOneWidget);
  expect(find.byKey(const Key('settings-accessibility-section')), findsOneWidget);
  expect(find.byType(Card), findsNothing);
});
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
cd frontend
flutter test test/features/settings/settings_page_test.dart --plain-name "settings uses tonal sections instead of elevated cards"
```

Expected: FAIL because `_SettingsSection` returns `Card` and the approved subtitle/keys are absent.

- [ ] **Step 3: Implement the shared header and tonal sections**

Use:

```dart
const WorkspaceHeader(
  title: '设置',
  description: '偏好设置只保存在这台设备上',
),
```

Change `_SettingsSection` to accept a `Key sectionKey` and return:

```dart
DecoratedBox(
  key: sectionKey,
  decoration: BoxDecoration(
    color: Theme.of(context).colorScheme.surfaceContainerLow,
    borderRadius: BorderRadius.circular(12),
  ),
  child: Padding(
    padding: const EdgeInsets.all(20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          header: true,
          child: Text(title, style: Theme.of(context).textTheme.titleLarge),
        ),
        const SizedBox(height: 16),
        ...children,
      ],
    ),
  ),
)
```

Pass `Key('settings-connection-section')` and `Key('settings-accessibility-section')`. Preserve controller draft updates, validation, recovery warning, live-region messages, save/reset callbacks, and the wrapping action row.

- [ ] **Step 4: Run settings and high-contrast tests**

Run:

```powershell
cd frontend
flutter test test/features/settings/settings_page_test.dart test/accessibility/high_contrast_test.dart
```

Expected: PASS, including persistence, invalid URL blocking, recovery warning dismissal, and 200% text scale.

- [ ] **Step 5: Commit the settings refinement**

```powershell
git add frontend/lib/features/settings/presentation/settings_page.dart frontend/test/features/settings/settings_page_test.dart
git commit -m "feat: simplify settings into tonal sections"
```

### Task 6: Harden responsive and accessibility behavior across the redesign

**Files:**

- Modify: `frontend/test/features/search/search_page_test.dart:1-1090`
- Modify: `frontend/lib/features/search/presentation/widgets/search_stage.dart`

- [ ] **Step 1: Add 200% search coverage and a failing compact-filter semantics test**

Extend `_SearchHarness.create` with:

```dart
TextScaler textScaler = TextScaler.noScaling,
```

Wrap the harness home:

```dart
home: MediaQuery(
  data: MediaQueryData(textScaler: textScaler),
  child: Scaffold(
    body: SearchPage(
      controller: searchController,
      statusController: statusController,
      fileLauncher: fileLauncher,
      pathClipboard: pathClipboard,
    ),
  ),
),
```

Add:

```dart
testWidgets('search workbench has no overflow at 200 percent text scale', (tester) async {
  final harness = await _SearchHarness.create(
    tester,
    surfaceSize: const Size(900, 900),
    textScaler: const TextScaler.linear(2),
  )..searchService.results.add(_response(names: const ['large-text.pdf']));
  await harness.search('large text');

  expect(find.text('large-text.pdf'), findsOneWidget);
  expect(tester.takeException(), isNull);
});
```

Add a compact filter semantics test in `search_page_test.dart`:

```dart
testWidgets('compact filter count is announced as one control', (tester) async {
  final semantics = tester.ensureSemantics();
  final harness = await _SearchHarness.create(
    tester,
    surfaceSize: const Size(900, 720),
  );
  harness.searchController.toggleContentType(SearchContentType.images);
  await tester.pump();

  expect(find.bySemanticsLabel('筛选，1 个限制'), findsOneWidget);
  semantics.dispose();
});
```

- [ ] **Step 2: Run the new accessibility tests and verify any real failures**

Run:

```powershell
cd frontend
flutter test test/features/search/search_page_test.dart --plain-name "search workbench has no overflow at 200 percent text scale"
flutter test test/features/search/search_page_test.dart --plain-name "compact filter count is announced as one control"
```

Expected: the 200% test establishes the responsive baseline; the compact-filter semantics test FAILS because Task 2 adds a visual badge but not one combined accessible label.

- [ ] **Step 3: Give the progressive filter one complete accessible label**

Wrap the compact filter badge and button in one semantic node in `SearchStage`:

```dart
Semantics(
  label: activeFilterCount == 0
      ? '筛选'
      : '筛选，$activeFilterCount 个限制',
  button: true,
  onTap: onShowFilters,
  excludeSemantics: true,
  child: Badge(
    key: const Key('search-filter-count'),
    isLabelVisible: activeFilterCount > 0,
    label: Text('$activeFilterCount'),
    child: OutlinedButton.icon(
      key: const Key('search-filter-button'),
      onPressed: onShowFilters,
      icon: const Icon(Icons.tune),
      label: const Text('筛选'),
    ),
  ),
)
```

Task 2 already stacks search actions at 200% text and Task 3 makes result actions responsive. If the 200% regression does not pass, stop and compare the implementation with those exact snippets instead of reducing 48px controls, removing labels, or suppressing metadata.

- [ ] **Step 4: Run the entire Flutter quality gate**

Run:

```powershell
cd frontend
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

Expected: formatter exits 0, analyzer reports `No issues found!`, and all tests pass with a count greater than the 178-test baseline.

- [ ] **Step 5: Commit accessibility hardening**

```powershell
git add frontend/lib/features/search/presentation/widgets/search_stage.dart frontend/test/features/search/search_page_test.dart
git commit -m "test: harden redesigned UI accessibility"
```

### Task 7: Build and visually verify the approved interface

**Files:**

- Verify: all files changed in Tasks 1-6
- Do not commit generated `build/`, `.dart_tool/`, screenshots, or local runtime data

- [ ] **Step 1: Produce release-capable desktop and web builds**

Run:

```powershell
cd frontend
flutter build windows --debug
flutter build web --release
```

Expected: both commands exit 0 and produce the standard ignored build outputs.

- [ ] **Step 2: Launch the real Windows application**

Run the existing backend according to `docs/week4/MVP_RUNBOOK.md`, then:

```powershell
cd frontend
flutter run -d windows
```

Expected: the app opens on Search, reports the actual backend state, and preserves real search/index/settings behavior.

- [ ] **Step 3: Inspect the required visual states**

At 1440×900 and 1280×720, verify:

- Search is the first visual and keyboard focus target.
- The navigation brand is quiet and does not compete with search.
- Persistent filters appear only at or above 1100px; compact mode shows the progressive filter entry and preserves selections.
- Initial, loading, success, empty, failure, and offline states do not jump or overflow.
- Results read in the order file → snippet → source/reason → actions.
- Library rows and settings sections use tonal layering without elevated-card stacking.

Repeat with light, dark, high contrast, 200% text, and reduced motion.

- [ ] **Step 4: Apply and verify any evidence-based polish fixes**

For each visual defect, add or tighten a widget test first, reproduce the failure, make the smallest presentation change, and rerun the focused test. Do not add unplanned features or change backend contracts.

- [ ] **Step 5: Run final verification and confirm branch cleanliness**

Run:

```powershell
cd frontend
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
cd ..
git status --short
git log --oneline --decorate -7
```

Expected: all quality gates pass; `git status --short` is empty except for explicitly retained local visual evidence; the log shows the small task commits from this plan.
