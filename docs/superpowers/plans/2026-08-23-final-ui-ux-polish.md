# 最终 UI/UX 打磨 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Flutter 客户端重整为统一的任务工作台，统一三页的文案、状态、布局和交互，同时保持现有后端契约与无障碍基线。

**Architecture:** 业务数据继续由现有 controller 和 API client 管理；页面只重组展示层，并新增一个无业务逻辑的共用反馈组件。搜索在更新期间复用 controller 已保留的上次响应，索引库从既有分页和任务结果派生摘要，设置页从 `draft != settings` 派生未保存状态。

**Tech Stack:** Flutter、Dart、Material 3、`flutter_test`、现有 ChangeNotifier controller。

---

## 实施边界与文件职责

实施应在本计划提交后的 `master` HEAD 上创建独立工作树，分支名为 `codex/final-ui-ux-polish`；该 HEAD 的历史必须包含设计提交 `20434e9`。不要带入主工作树未跟踪文件或其他未提交修改。

### 新增文件

- `frontend/lib/core/presentation/workspace_notice.dart`：统一持久信息、警告和错误反馈的视觉与语义，不持有业务状态。
- `frontend/lib/features/library/presentation/widgets/library_summary.dart`：仅展示索引文件总数和当前任务失败数量。
- `frontend/test/core/presentation/workspace_notice_test.dart`：验证共用页头与反馈组件的语义、动作和大字号布局。

### 重点修改文件

- `frontend/lib/app/app_theme.dart`：补齐文本按钮、SnackBar 和弹出菜单的交互尺寸与视觉规则。
- `frontend/lib/core/presentation/workspace_header.dart`：统一页头层级、间距和大字号换行。
- `frontend/lib/features/search/presentation/search_page.dart`：任务工作台布局、筛选焦点返回和上下文面板。
- `frontend/lib/features/search/presentation/widgets/search_stage.dart`：单一搜索任务，不再重复标题。
- `frontend/lib/features/search/presentation/widgets/search_filter_panel.dart`：统一“筛选结果”、模式文案和重置入口。
- `frontend/lib/features/search/presentation/widgets/search_state_view.dart`：统一搜索状态，更新时保留旧结果。
- `frontend/lib/features/search/presentation/widgets/backend_status_indicator.dart`：改用“本地检索服务”用户语言。
- `frontend/lib/features/search/presentation/widgets/search_result_tile.dart`：统一动作标签与结果阅读顺序。
- `frontend/lib/features/library/presentation/index_library_page.dart`：统一页头、摘要、错误、成功反馈和焦点返回。
- `frontend/lib/features/library/presentation/widgets/index_job_panel.dart`：统一任务进度和失败文案。
- `frontend/lib/features/library/presentation/widgets/indexed_file_tile.dart`：保留“打开文件”，把重新索引和移除收入“更多操作”。
- `frontend/lib/features/settings/presentation/settings_controller.dart`：新增纯派生的未保存状态。
- `frontend/lib/features/settings/presentation/settings_page.dart`：分隔式表单、保存状态、重置确认和统一反馈。
- `frontend/test/widget_test.dart`：更新应用壳、主题和布局断言。
- `frontend/test/accessibility/*.dart`：保持快捷键、语义、对比度和触控目标回归。
- `frontend/test/features/*/*_page_test.dart`：覆盖三页新结构、文案、状态和焦点。

## Task 1: 建立共用页头、反馈和主题基础

**Files:**
- Create: `frontend/lib/core/presentation/workspace_notice.dart`
- Create: `frontend/test/core/presentation/workspace_notice_test.dart`
- Modify: `frontend/lib/core/presentation/workspace_header.dart:1-72`
- Modify: `frontend/lib/app/app_theme.dart:22-155`
- Modify: `frontend/test/widget_test.dart:333-496`

- [ ] **Step 1: 写共用组件的失败测试**

新增 `frontend/test/core/presentation/workspace_notice_test.dart`：

```dart
import 'package:content_retrieval_app/core/presentation/workspace_header.dart';
import 'package:content_retrieval_app/core/presentation/workspace_notice.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('workspace header exposes one heading and stacks at large text', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(560, 420));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const MaterialApp(
        home: MediaQuery(
          data: MediaQueryData(textScaler: TextScaler.linear(2)),
          child: Scaffold(
            body: WorkspaceHeader(
              title: '搜索本地资料',
              description: '描述你记得的内容，找到对应文件和位置',
              actions: [FilledButton(onPressed: null, child: Text('搜索资料'))],
            ),
          ),
        ),
      ),
    );

    expect(
      tester.getSemantics(find.text('搜索本地资料')).flagsCollection.isHeader,
      isTrue,
    );
    expect(
      tester.getSemantics(find.text('描述你记得的内容，找到对应文件和位置'))
          .flagsCollection
          .isHeader,
      isFalse,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('workspace notice announces once and exposes its named action', (
    tester,
  ) async {
    var retried = false;
    final semantics = tester.ensureSemantics();
    addTearDown(semantics.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: WorkspaceNotice(
            tone: WorkspaceNoticeTone.error,
            message: '无法加载索引库。',
            actionLabel: '重新尝试',
            onAction: () => retried = true,
            announce: true,
          ),
        ),
      ),
    );

    final notice = find.byKey(const Key('workspace-notice'));
    expect(tester.widget<Semantics>(notice).properties.liveRegion, isTrue);
    await tester.tap(find.widgetWithText(TextButton, '重新尝试'));
    expect(retried, isTrue);
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
  });
}
```

在 `frontend/test/widget_test.dart` 的主题测试中追加：

```dart
expect(
  light.textButtonTheme.style!.minimumSize!.resolve(<WidgetState>{}),
  const Size(48, 48),
);
expect(light.snackBarTheme.behavior, SnackBarBehavior.floating);
```

- [ ] **Step 2: 运行测试并确认因新组件和主题规则缺失而失败**

Run:

```powershell
cd frontend
flutter test test/core/presentation/workspace_notice_test.dart test/widget_test.dart
```

Expected: FAIL，首先报告 `workspace_notice.dart` 或 `WorkspaceNotice` 不存在；补入 import 后的主题断言也应在实现前失败。

- [ ] **Step 3: 实现无业务状态的共用反馈组件**

新增 `frontend/lib/core/presentation/workspace_notice.dart`：

```dart
import 'package:flutter/material.dart';

enum WorkspaceNoticeTone { info, warning, error }

final class WorkspaceNotice extends StatelessWidget {
  const WorkspaceNotice({
    super.key,
    required this.tone,
    required this.message,
    this.actionLabel,
    this.onAction,
    this.onDismiss,
    this.announce = false,
  });

  final WorkspaceNoticeTone tone;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;
  final VoidCallback? onDismiss;
  final bool announce;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (icon, background, foreground) = switch (tone) {
      WorkspaceNoticeTone.info => (
        Icons.info_outline,
        scheme.surfaceContainerHigh,
        scheme.onSurface,
      ),
      WorkspaceNoticeTone.warning => (
        Icons.warning_amber_outlined,
        scheme.tertiaryContainer,
        scheme.onTertiaryContainer,
      ),
      WorkspaceNoticeTone.error => (
        Icons.error_outline,
        scheme.errorContainer,
        scheme.onErrorContainer,
      ),
    };

    return Semantics(
      key: const Key('workspace-notice'),
      container: true,
      liveRegion: announce,
      child: Material(
        color: background,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Icon(icon, color: foreground),
              const SizedBox(width: 10),
              Expanded(child: Text(message, style: TextStyle(color: foreground))),
              if (actionLabel != null && onAction != null)
                TextButton(onPressed: onAction, child: Text(actionLabel!)),
              if (onDismiss != null)
                IconButton(
                  tooltip: '关闭提示',
                  onPressed: onDismiss,
                  icon: const Icon(Icons.close),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: 统一页头和主题交互尺寸**

在 `AppTheme._build` 返回的 `ThemeData` 中加入：

```dart
textButtonTheme: TextButtonThemeData(
  style: TextButton.styleFrom(
    minimumSize: const Size(48, 48),
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
    shape: controlShape,
  ),
),
snackBarTheme: SnackBarThemeData(
  behavior: SnackBarBehavior.floating,
  shape: RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(_controlRadius),
  ),
),
popupMenuTheme: PopupMenuThemeData(
  shape: RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(_controlRadius),
  ),
),
```

保持 `WorkspaceHeader` 的现有公开构造函数；将外层 Key 固定为 `workspace-header`，并让动作区在堆叠与非堆叠模式都使用 `Wrap`：

```dart
final actionGroup = Wrap(
  alignment: WrapAlignment.end,
  spacing: 8,
  runSpacing: 8,
  children: actions,
);

return Padding(
  key: const Key('workspace-header'),
  padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
  child: stacked
      ? Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            text,
            if (actions.isNotEmpty) ...[
              const SizedBox(height: 12),
              actionGroup,
            ],
          ],
        )
      : Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: text),
            if (actions.isNotEmpty) ...[
              const SizedBox(width: 16),
              Flexible(child: actionGroup),
            ],
          ],
        ),
);
```

- [ ] **Step 5: 运行共用组件和主题测试**

Run:

```powershell
cd frontend
dart format lib/core/presentation/workspace_notice.dart lib/core/presentation/workspace_header.dart lib/app/app_theme.dart test/core/presentation/workspace_notice_test.dart test/widget_test.dart
flutter test test/core/presentation/workspace_notice_test.dart test/widget_test.dart
```

Expected: PASS，且无 overflow 或触控目标告警。

- [ ] **Step 6: 提交基础组件**

```powershell
git add frontend/lib/app/app_theme.dart frontend/lib/core/presentation/workspace_header.dart frontend/lib/core/presentation/workspace_notice.dart frontend/test/core/presentation/workspace_notice_test.dart frontend/test/widget_test.dart
git commit -m "feat: unify workspace presentation primitives"
```

## Task 2: 重构搜索任务工作台

**Files:**
- Modify: `frontend/lib/features/search/presentation/search_page.dart:30-252`
- Modify: `frontend/lib/features/search/presentation/widgets/search_stage.dart:1-129`
- Modify: `frontend/lib/features/search/presentation/widgets/search_filter_panel.dart:1-160`
- Modify: `frontend/lib/features/search/presentation/widgets/search_state_view.dart:9-209`
- Modify: `frontend/lib/features/search/presentation/widgets/backend_status_indicator.dart:8-74`
- Modify: `frontend/lib/features/search/presentation/widgets/search_result_tile.dart:84-273`
- Test: `frontend/test/features/search/search_page_test.dart`

- [ ] **Step 1: 更新页头、主要动作和用户语言的失败测试**

将搜索页测试中的页头断言改为：

```dart
expect(headingData.label, '搜索本地资料');
expect(
  find.semantics.byLabel(RegExp('描述你记得的内容，找到对应文件和位置')),
  findsOneWidget,
);
```

将原“search stage leads”测试替换为：

```dart
testWidgets('search workbench exposes one task title and one primary action', (
  tester,
) async {
  await _SearchHarness.create(tester);

  expect(find.text('搜索本地资料'), findsOneWidget);
  expect(find.text('找回你记得的内容'), findsNothing);
  expect(find.text('搜索资料'), findsOneWidget);
  expect(find.text('Ctrl K'), findsOneWidget);
});
```

把连接状态断言改为“正在连接本地检索服务”“本地检索服务已就绪”“本地检索服务不可用”，把空状态动作改为“重置筛选”，把重试动作改为“重新尝试”。

- [ ] **Step 2: 增加更新结果时保留旧列表的失败测试**

在 `search_page_test.dart` 加入：

```dart
testWidgets('filter updates retain results and announce one update state', (
  tester,
) async {
  final pending = Completer<SearchResponse>();
  final harness = await _SearchHarness.create(tester)
    ..searchService.results.addAll([
      _response(query: 'notes', names: const ['notes.txt']),
      pending.future,
    ]);
  await harness.search('notes');

  await tester.tap(find.text('语义'));
  await tester.pump();

  expect(find.text('notes.txt'), findsOneWidget);
  expect(find.text('正在更新结果'), findsOneWidget);
  expect(
    find.byKey(const Key('search-loading-skeleton'), skipOffstage: false),
    findsNothing,
  );
  pending.complete(_response(query: 'notes', names: const ['updated.txt']));
  await tester.pumpAndSettle();
  expect(find.text('updated.txt'), findsOneWidget);
});

testWidgets('failed result updates retain the previous result list', (
  tester,
) async {
  final harness = await _SearchHarness.create(tester)
    ..searchService.results.addAll([
      _response(query: 'notes', names: const ['notes.txt']),
      const ApiException(ApiErrorKind.timeout, 'private timeout detail'),
    ]);
  await harness.search('notes');

  await tester.tap(find.text('语义'));
  await tester.pumpAndSettle();

  expect(find.text('notes.txt'), findsOneWidget);
  expect(find.text('搜索用时过长'), findsOneWidget);
  expect(find.text('重新尝试'), findsOneWidget);
  expect(find.textContaining('private timeout'), findsNothing);
});
```

增加窄窗口筛选焦点返回测试：

```dart
testWidgets('compact filters close with Escape and return focus', (tester) async {
  await _SearchHarness.create(tester, surfaceSize: const Size(900, 720));
  final button = find.byKey(const Key('search-filter-button'));
  await tester.tap(button);
  await tester.pumpAndSettle();
  expect(find.byKey(const Key('search-filter-panel')), findsOneWidget);

  await tester.sendKeyEvent(LogicalKeyboardKey.escape);
  await tester.pumpAndSettle();

  expect(find.byKey(const Key('search-filter-panel')), findsNothing);
  final filterButton = tester.widget<OutlinedButton>(button);
  expect(filterButton.focusNode!.hasFocus, isTrue);
});
```

- [ ] **Step 3: 运行搜索测试并确认旧文案、骨架更新和焦点行为失败**

Run:

```powershell
cd frontend
flutter test test/features/search/search_page_test.dart
```

Expected: FAIL，失败点包含新页头/按钮文案、保留旧结果和筛选按钮 FocusNode。

- [ ] **Step 4: 重组搜索页和筛选焦点生命周期**

在 `_SearchPageState` 新增并管理 `_filterButtonFocusNode`：

```dart
late final FocusNode _filterButtonFocusNode;

@override
void initState() {
  super.initState();
  _queryController = TextEditingController(text: widget.controller.query);
  _queryFocusNode = FocusNode(debugLabel: 'search query');
  _filterButtonFocusNode = FocusNode(debugLabel: 'search filters');
}

@override
void dispose() {
  _queryController.dispose();
  _queryFocusNode.dispose();
  _filterButtonFocusNode.dispose();
  super.dispose();
}
```

把 `_showFilters` 改为异步并在关闭后恢复焦点；在底部面板内显式处理 Escape：

```dart
Future<void> _showFilters() async {
  await showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (sheetContext) => CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.escape): () =>
            Navigator.pop(sheetContext),
      },
      child: Focus(
        autofocus: true,
        child: SafeArea(
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.sizeOf(sheetContext).height * 0.82,
            ),
            child: ListenableBuilder(
              listenable: widget.controller,
              builder: (context, _) => SearchFilterPanel(
                key: const Key('search-filter-panel'),
                controller: widget.controller,
                enabled: widget.controller.state != SearchViewState.loading,
                onChanged: _filtersChanged,
                onReset: _clearFilters,
              ),
            ),
          ),
        ),
      ),
    ),
  );
  if (mounted) _filterButtonFocusNode.requestFocus();
}
```

给 `SearchStage` 增加必需参数 `filterButtonFocusNode`，传给筛选 `OutlinedButton` 的 `focusNode`。页头和搜索组件使用：

```dart
WorkspaceHeader(
  title: '搜索本地资料',
  description: '描述你记得的内容，找到对应文件和位置',
  actions: [BackendStatusIndicator(controller: widget.statusController)],
)
```

删除 `SearchStage` 内部的重复标题和说明，只保留输入、筛选入口和按钮，并把按钮标签改为“搜索资料”。

- [ ] **Step 5: 统一筛选、连接状态和结果动作文案**

给 `SearchFilterPanel` 增加 `final VoidCallback onReset`，标题行使用以下结构：

```dart
Row(
  children: [
    Expanded(child: Text('筛选结果', style: theme.textTheme.titleMedium)),
    TextButton(onPressed: widget.enabled ? widget.onReset : null, child: const Text('重置')),
  ],
)
```

检索模式标签使用：

```dart
const [
  ButtonSegment(value: RetrievalMode.exact, label: Text('精确')),
  ButtonSegment(value: RetrievalMode.hybrid, label: Text('综合')),
  ButtonSegment(value: RetrievalMode.semantic, label: Text('语义')),
]
```

`BackendStatusIndicator` 的三组文字替换为：

```dart
BackendConnectionState.checking => '正在连接本地检索服务',
BackendConnectionState.online => '本地检索服务已就绪',
BackendConnectionState.offline => '本地检索服务不可用',
```

对应播报使用“正在连接本地检索服务。”“本地检索服务已连接，共有 N 个可搜索文件。”“本地检索服务连接已断开。”，操作标签改为“重新连接”。

在 `SearchResultTile` 中把可见按钮“打开”改为“打开文件”，复制 Tooltip 改为“复制路径”；保持现有完整语义标签和 48dp IconButton。

- [ ] **Step 6: 实现保留结果的更新状态**

在 `SearchStateView` 中把 loading 分成首次搜索和结果更新：

```dart
SearchViewState.loading => controller.response == null
    ? _initialLoading(context)
    : _success(context, updating: true),
```

把原 `_loading` 改名为 `_initialLoading`。把 `_success` 签名和摘要区改为：

```dart
Widget _success(BuildContext context, {bool updating = false}) {
  final response = controller.response!;
  final theme = Theme.of(context);
  final summary = updating
      ? '正在更新结果'
      : '找到 ${response.hits.length} 条相关资料';
  final announcement = updating
      ? '正在更新搜索结果。'
      : '搜索完成，找到 ${response.hits.length} 条结果。';

  return Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      LiveRegionMessage(
        message: announcement,
        child: Row(
          children: [
            Expanded(
              child: Text(
                summary,
                key: const Key('search-summary'),
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            if (updating)
              const SizedBox.square(
                dimension: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
          ],
        ),
      ),
      const SizedBox(height: 10),
      Expanded(
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
    ],
  );
}
```

空状态标题改为“没有找到相关资料”，正文改为“尝试调整搜索内容，或重置筛选条件”，动作改为“重置筛选”。失败操作统一为“重新尝试”。

把 `_failure` 拆为安全用户文案，并在 `controller.response` 非空时把 `WorkspaceNotice` 放在旧结果列表上方：

```dart
final (title, body) = switch (controller.error?.kind) {
  ApiErrorKind.offline => (
    '无法连接本地检索服务',
    '请检查服务地址和运行状态。',
  ),
  ApiErrorKind.timeout => ('搜索用时过长', '请重新尝试。'),
  ApiErrorKind.invalidResponse => (
    '无法读取搜索结果',
    '本地检索服务返回了无法读取的内容。',
  ),
  _ when controller.error?.statusCode == 503 => (
    '本地检索服务暂时不可用',
    '请稍后重新尝试。',
  ),
  _ => ('搜索失败', '当前结果未更新，请重新尝试。'),
};
```

保留结果时使用 `_resultList(context, controller.response!)`，反馈组件为：

```dart
WorkspaceNotice(
  tone: WorkspaceNoticeTone.error,
  message: '$title。$body',
  actionLabel: '重新尝试',
  onAction: onRetry,
  announce: true,
)
```

首次失败时继续使用居中的 `_message`，但必须复用同一组 `title`、`body` 和“重新尝试”动作。422 校验错误继续与搜索输入关联，不显示服务错误详情。

- [ ] **Step 7: 运行搜索测试并修正全部旧断言**

Run:

```powershell
cd frontend
dart format lib/features/search test/features/search/search_page_test.dart
flutter test test/features/search/search_page_test.dart
```

Expected: PASS，保留已有请求次数、错误隐私、200% 字号、深色对比度和平台操作测试。

- [ ] **Step 8: 提交搜索工作台**

```powershell
git add frontend/lib/features/search frontend/test/features/search/search_page_test.dart
git commit -m "feat: focus search on one accessible task"
```

## Task 3: 重构索引库清单、任务状态和更多操作

**Files:**
- Create: `frontend/lib/features/library/presentation/widgets/library_summary.dart`
- Modify: `frontend/lib/features/library/presentation/index_library_page.dart:30-308`
- Modify: `frontend/lib/features/library/presentation/widgets/index_job_panel.dart:5-89`
- Modify: `frontend/lib/features/library/presentation/widgets/indexed_file_tile.dart:6-170`
- Modify: `frontend/lib/features/library/presentation/index_library_controller.dart:190-201`
- Test: `frontend/test/features/library/index_library_page_test.dart`

- [ ] **Step 1: 写索引库摘要、文案和更多操作的失败测试**

在 `index_library_page_test.dart` 更新并加入：

```dart
testWidgets('library exposes one primary action and a truthful summary', (
  tester,
) async {
  final service = _PageService()..pages.add(_page());
  final controller = IndexLibraryController(
    service: service,
    directoryPicker: _PagePicker(),
  );
  addTearDown(controller.dispose);
  await controller.load();

  await tester.pumpWidget(_app(controller));

  expect(find.text('添加资料文件夹'), findsOneWidget);
  expect(find.byKey(const Key('library-total-files')), findsOneWidget);
  expect(find.text('1 个可搜索文件'), findsOneWidget);
  expect(find.textContaining('后端'), findsNothing);
});

testWidgets('secondary file mutations live in a focus-restoring menu', (
  tester,
) async {
  final service = _PageService()..pages.add(_page());
  final controller = IndexLibraryController(
    service: service,
    directoryPicker: _PagePicker(),
  );
  addTearDown(controller.dispose);
  await controller.load();
  await tester.pumpWidget(_app(controller));

  final more = find.byKey(const Key('more-actions-file-1'));
  expect(find.widgetWithText(FilledButton, '打开文件'), findsOneWidget);
  expect(find.byTooltip('重新索引 guide.pdf'), findsNothing);
  await tester.tap(more);
  await tester.pumpAndSettle();
  expect(find.text('重新索引文件'), findsOneWidget);
  expect(find.text('从索引库移除'), findsOneWidget);

  await tester.tap(find.text('重新索引文件'));
  await tester.pumpAndSettle();
  await tester.tap(find.widgetWithText(TextButton, '取消'));
  await tester.pumpAndSettle();
  final menu = tester.widget<PopupMenuButton<dynamic>>(more);
  expect(menu.focusNode!.hasFocus, isTrue);
});
```

把失败详情断言从内部代码改为用户语言：

```dart
expect(find.textContaining('解析文件时失败'), findsOneWidget);
expect(find.textContaining('PARSE_FAILED'), findsNothing);
```

- [ ] **Step 2: 运行索引库测试并确认摘要、菜单和用户语言失败**

Run:

```powershell
cd frontend
flutter test test/features/library/index_library_page_test.dart
```

Expected: FAIL，原因包含“添加资料文件夹”、`library-total-files`、更多操作菜单和错误码仍可见。

- [ ] **Step 3: 新增不伪造全局健康数据的摘要组件**

新增 `library_summary.dart`：

```dart
import 'package:flutter/material.dart';

final class LibrarySummary extends StatelessWidget {
  const LibrarySummary({
    super.key,
    required this.totalFiles,
    required this.currentTaskFailures,
  });

  final int totalFiles;
  final int currentTaskFailures;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        Semantics(
          key: const Key('library-total-files'),
          label: '$totalFiles 个可搜索文件',
          child: Chip(
            avatar: const Icon(Icons.library_books_outlined, size: 18),
            label: Text('$totalFiles 个可搜索文件'),
            backgroundColor: scheme.surfaceContainerLow,
          ),
        ),
        if (currentTaskFailures > 0)
          Semantics(
            label: '本次任务有 $currentTaskFailures 个文件需要处理',
            child: Chip(
              avatar: const Icon(Icons.warning_amber_outlined, size: 18),
              label: Text('本次任务 $currentTaskFailures 个需要处理'),
              backgroundColor: scheme.errorContainer,
              labelStyle: TextStyle(color: scheme.onErrorContainer),
            ),
          ),
      ],
    );
  }
}
```

“可搜索文件”直接使用 `controller.total`；“需要处理”只使用 `controller.activeJob?.result?.failedFiles ?? 0`，不把当前页数量冒充全局统计。

- [ ] **Step 4: 重组索引库页头、反馈和任务区域**

页头改为：

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
      label: const Text('添加资料文件夹'),
    ),
  ],
)
```

页头下依次放 `LibrarySummary`、`IndexJobPanel` 和 `WorkspaceNotice`。错误反馈使用：

```dart
WorkspaceNotice(
  tone: WorkspaceNoticeTone.error,
  message: controller.errorMessage!,
  actionLabel: '重新尝试',
  onAction: controller.refresh,
  onDismiss: controller.clearError,
  announce: true,
)
```

删除成功 `MaterialBanner`。在 State 中记录 `_shownSuccessMessage`，用 post-frame callback 将新的 `controller.successMessage` 显示一次为 SnackBar，然后调用 `controller.clearSuccess()`：

```dart
void _scheduleSuccess(String? message) {
  if (message == null || message == _shownSuccessMessage) return;
  _shownSuccessMessage = message;
  WidgetsBinding.instance.addPostFrameCallback((_) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
    widget.controller.clearSuccess();
  });
}
```

- [ ] **Step 5: 把危险操作收入可恢复焦点的菜单**

在 `IndexedFileTile` 中把回调改为：

```dart
final Future<void> Function() onReindex;
final Future<void> Function() onRemove;
```

State 新增并释放 FocusNode：

```dart
final FocusNode _moreActionsFocusNode = FocusNode(debugLabel: 'file actions');

@override
void dispose() {
  _moreActionsFocusNode.dispose();
  super.dispose();
}
```

可见操作区保留“打开文件”和复制路径，把两个危险操作替换为：

```dart
PopupMenuButton<_IndexedFileAction>(
  key: Key('more-actions-${file.fileId}'),
  focusNode: _moreActionsFocusNode,
  tooltip: '${file.name} 的更多操作',
  enabled: widget.actionsEnabled,
  onSelected: (action) async {
    switch (action) {
      case _IndexedFileAction.reindex:
        await widget.onReindex();
      case _IndexedFileAction.remove:
        await widget.onRemove();
    }
    if (mounted) _moreActionsFocusNode.requestFocus();
  },
  itemBuilder: (context) => const [
    PopupMenuItem(
      value: _IndexedFileAction.reindex,
      child: ListTile(
        leading: Icon(Icons.refresh),
        title: Text('重新索引文件'),
      ),
    ),
    PopupMenuItem(
      value: _IndexedFileAction.remove,
      child: ListTile(
        leading: Icon(Icons.delete_outline),
        title: Text('从索引库移除'),
      ),
    ),
  ],
)
```

文件顶部定义：

```dart
enum _IndexedFileAction { reindex, remove }
```

把打开按钮标签改为“打开文件”。`IndexLibraryPage` 直接传 `_confirmReindex(file)` 与 `_confirmRemove(file)` 的 Future。

- [ ] **Step 6: 统一任务和失败详情文案**

`IndexJobPanel` 使用“正在添加资料”“资料已可搜索”“部分文件未能加入索引库”等用户语言；进行中显示 LinearProgressIndicator，完成显示“已添加 N 个文件，M 个文件需要处理”。

在 `index_library_page.dart` 新增纯展示映射：

```dart
String _failureStageLabel(String stage) => switch (stage) {
  'discover' => '查找文件时失败',
  'parse' => '解析文件时失败',
  'embed' => '处理文件内容时失败',
  'persist' => '保存索引时失败',
  _ => '处理文件时失败',
};
```

失败详情行使用 `Text(_failureStageLabel(failure.stage))`，不显示 `failure.code`。任务级错误说明改为“任务未完成，请重新尝试；若问题持续，请检查本地检索服务。”。

在 `IndexLibraryController.selectDirectoryAndStart` 中把不支持平台的文案改为“当前平台不支持添加本地资料文件夹，请使用 Windows、macOS 或 Linux 桌面版。”。在 `_messageFor` 中使用以下精确文案：

```dart
'RETRIEVAL_UNAVAILABLE' =>
  '索引已更新，但搜索服务刷新失败，请重新启动本地检索服务后重试。',
'SERVICE_UNAVAILABLE' => '本地检索服务暂时不可用，请检查运行状态后重新尝试。',
_ when error.kind == ApiErrorKind.offline =>
  '无法连接本地检索服务，请检查服务地址和运行状态。',
_ when error.kind == ApiErrorKind.timeout => '请求用时过长，请重新尝试。',
```

- [ ] **Step 7: 运行索引库 controller、页面和 200% 字号测试**

Run:

```powershell
cd frontend
dart format lib/features/library test/features/library/index_library_page_test.dart
flutter test test/features/library/index_library_controller_test.dart test/features/library/index_library_page_test.dart
```

Expected: PASS；现有分页、轮询、删除、打开、复制、确认对话框和 200% 字号测试继续通过。

- [ ] **Step 8: 提交索引库工作台**

```powershell
git add frontend/lib/features/library frontend/test/features/library/index_library_page_test.dart
git commit -m "feat: clarify the indexed library workspace"
```

## Task 4: 重构设置分组、未保存状态和重置确认

**Files:**
- Modify: `frontend/lib/features/settings/presentation/settings_controller.dart:10-111`
- Modify: `frontend/lib/features/settings/presentation/settings_page.dart:21-295`
- Modify: `frontend/test/features/settings/settings_controller_test.dart`
- Modify: `frontend/test/features/settings/settings_page_test.dart`
- Modify: `frontend/test/accessibility/semantics_test.dart:78-108`

- [ ] **Step 1: 写未保存状态的 controller 失败测试**

在 `settings_controller_test.dart` 加入：

```dart
test('hasUnsavedChanges follows draft and persisted settings', () async {
  final controller = SettingsController(
    SettingsRepository(_ControllerStore()),
  );
  addTearDown(controller.dispose);
  await controller.load();

  expect(controller.hasUnsavedChanges, isFalse);
  controller.setTextScale(1.5);
  expect(controller.hasUnsavedChanges, isTrue);
  expect(await controller.save(), isTrue);
  expect(controller.hasUnsavedChanges, isFalse);
});
```

- [ ] **Step 2: 写设置页结构、保存状态和重置确认的失败测试**

在 `settings_page_test.dart` 更新并加入：

```dart
testWidgets('settings separates connection appearance and accessibility', (
  tester,
) async {
  final controller = SettingsController(
    SettingsRepository(_PageSettingsStore()),
  );
  addTearDown(controller.dispose);
  await controller.load();
  await tester.pumpWidget(_app(controller));

  expect(find.text('这些偏好只保存在当前设备上'), findsOneWidget);
  expect(find.byKey(const Key('settings-connection-section')), findsOneWidget);
  expect(find.byKey(const Key('settings-appearance-section')), findsOneWidget);
  expect(find.byKey(const Key('settings-accessibility-section')), findsOneWidget);
  expect(find.text('已保存'), findsOneWidget);
  expect(find.byType(Card), findsNothing);
});

testWidgets('settings reports unsaved changes and confirms reset', (tester) async {
  final controller = SettingsController(
    SettingsRepository(_PageSettingsStore()),
  );
  addTearDown(controller.dispose);
  await controller.load();
  await tester.pumpWidget(_app(controller));

  await tester.tap(find.text('150%'));
  await tester.pump();
  expect(find.text('尚未保存更改'), findsOneWidget);

  await tester.tap(find.widgetWithText(OutlinedButton, '恢复默认设置'));
  await tester.pumpAndSettle();
  expect(find.text('恢复默认设置？'), findsOneWidget);
  expect(find.text('当前未保存的更改将被替换。'), findsOneWidget);
  await tester.tap(find.widgetWithText(TextButton, '取消'));
  await tester.pumpAndSettle();
  expect(controller.draft.textScale, 1.5);
});
```

语义测试把“后端地址”断言改为“服务地址”，并分别验证“连接”“外观”“无障碍”为 header。

- [ ] **Step 3: 运行设置测试并确认派生状态和新结构失败**

Run:

```powershell
cd frontend
flutter test test/features/settings/settings_controller_test.dart test/features/settings/settings_page_test.dart test/accessibility/semantics_test.dart
```

Expected: FAIL，原因包含 `hasUnsavedChanges`、分组 Key、新页头文案和重置确认缺失。

- [ ] **Step 4: 新增纯派生未保存状态**

在 `SettingsController` 中加入：

```dart
bool get hasUnsavedChanges => draft != settings;
```

不增加第二个布尔字段，不在每个 setter 手动同步脏状态。

- [ ] **Step 5: 把设置页改为分隔式单列布局**

页头使用：

```dart
const WorkspaceHeader(
  title: '设置',
  description: '这些偏好只保存在当前设备上',
)
```

把原 `_SettingsSection` 的装饰容器替换为：

```dart
final class _SettingsSection extends StatelessWidget {
  const _SettingsSection({
    required this.sectionKey,
    required this.title,
    required this.children,
  });

  final Key sectionKey;
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: sectionKey,
      padding: const EdgeInsets.symmetric(vertical: 20),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
        ),
      ),
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
    );
  }
}
```

分组时直接移动现有控件，不复制 controller 状态。三个分组的完整 Widget 结构为：

```dart
_SettingsSection(
  sectionKey: const Key('settings-connection-section'),
  title: '连接',
  children: [
    TextField(
      key: const Key('backend-base-url'),
      controller: _backendUrlController,
      enabled: !controller.isBusy,
      keyboardType: TextInputType.url,
      autocorrect: false,
      decoration: InputDecoration(
        labelText: '服务地址',
        hintText: 'http://127.0.0.1:8000',
        errorText: controller.backendUrlError,
        helperText: '用于连接这台设备上的本地检索服务。',
      ),
      onChanged: (value) {
        controller.setBackendBaseUrl(value);
      },
    ),
  ],
),
_SettingsSection(
  sectionKey: const Key('settings-appearance-section'),
  title: '外观',
  children: [
    const Text('主题'),
    const SizedBox(height: 8),
    Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        _themeChoice(
          label: '跟随系统',
          value: AppThemePreference.system,
          controller: controller,
        ),
        _themeChoice(
          label: '浅色',
          value: AppThemePreference.light,
          controller: controller,
        ),
        _themeChoice(
          label: '深色',
          value: AppThemePreference.dark,
          controller: controller,
        ),
      ],
    ),
    const SizedBox(height: 16),
    const Text('文字大小'),
    const SizedBox(height: 8),
    Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final scale in supportedTextScales)
          ChoiceChip(
            label: Text('${(scale * 100).round()}%'),
            selected: controller.draft.textScale == scale,
            onSelected: controller.isBusy
                ? null
                : (_) => controller.setTextScale(scale),
          ),
      ],
    ),
  ],
),
_SettingsSection(
  sectionKey: const Key('settings-accessibility-section'),
  title: '无障碍',
  children: [
    SwitchListTile(
      contentPadding: EdgeInsets.zero,
      title: const Text('高对比度'),
      subtitle: const Text('增强文字、边框与背景的区分'),
      value: controller.draft.highContrast,
      onChanged: controller.isBusy ? null : controller.setHighContrast,
    ),
    const Divider(),
    SwitchListTile(
      contentPadding: EdgeInsets.zero,
      title: const Text('减少动态效果'),
      subtitle: const Text('减少非必要的动画和过渡'),
      value: controller.draft.reduceMotion,
      onChanged: controller.isBusy ? null : controller.setReduceMotion,
    ),
  ],
),
```

- [ ] **Step 6: 实现保存状态、SnackBar 和重置确认**

底部操作区使用：

```dart
Wrap(
  alignment: WrapAlignment.spaceBetween,
  crossAxisAlignment: WrapCrossAlignment.center,
  spacing: 12,
  runSpacing: 12,
  children: [
    Text(controller.hasUnsavedChanges ? '尚未保存更改' : '已保存'),
    Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        OutlinedButton(
          onPressed: controller.isBusy ? null : _confirmReset,
          child: const Text('恢复默认设置'),
        ),
        FilledButton(
          onPressed: controller.isBusy ||
                  controller.backendUrlError != null ||
                  !controller.hasUnsavedChanges
              ? null
              : _save,
          child: Text(controller.isBusy ? '正在保存…' : '保存设置'),
        ),
      ],
    ),
  ],
)
```

新增重置确认：

```dart
Future<void> _confirmReset() async {
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('恢复默认设置？'),
      content: const Text('当前未保存的更改将被替换。'),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('恢复默认设置'),
        ),
      ],
    ),
  );
  if (confirmed == true) await _reset();
}
```

把保存成功和重置成功改为浮动 SnackBar：

```dart
void _showConfirmation(String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: LiveRegionMessage(
          message: '$message。',
          child: Text(message),
        ),
      ),
    );
}

Future<void> _save() async {
  final saved = await widget.controller.save();
  if (!mounted || !saved) return;
  _backendUrlController.text = widget.controller.settings.backendBaseUrl;
  _showConfirmation('设置已保存');
  widget.onSettingsSaved?.call();
}

Future<void> _reset() async {
  final reset = await widget.controller.reset();
  if (!mounted || !reset) return;
  _backendUrlController.text = widget.controller.settings.backendBaseUrl;
  _showConfirmation('已恢复默认设置');
  widget.onSettingsSaved?.call();
}
```

恢复警告使用 `WorkspaceNoticeTone.warning`、动作“知道了”；保存错误使用 `WorkspaceNoticeTone.error`、`announce: true`，不提供会重复保存的第二个按钮。保存失败不改 `_backendUrlController`，因此草稿继续保留。

- [ ] **Step 7: 运行设置和语义测试**

Run:

```powershell
cd frontend
dart format lib/features/settings test/features/settings/settings_controller_test.dart test/features/settings/settings_page_test.dart test/accessibility/semantics_test.dart
flutter test test/features/settings/settings_controller_test.dart test/features/settings/settings_page_test.dart test/accessibility/semantics_test.dart
```

Expected: PASS；保存持久化、损坏设置恢复、URL 校验和 200% 字号测试继续通过。

- [ ] **Step 8: 提交设置工作台**

```powershell
git add frontend/lib/features/settings frontend/test/features/settings frontend/test/accessibility/semantics_test.dart
git commit -m "feat: make settings state explicit"
```

## Task 5: 锁定跨页面无障碍、响应式和文案一致性

**Files:**
- Modify: `frontend/test/accessibility/keyboard_navigation_test.dart`
- Modify: `frontend/test/accessibility/semantics_test.dart`
- Modify: `frontend/test/accessibility/high_contrast_test.dart`
- Modify: `frontend/test/widget_test.dart`
- Modify: `frontend/test/features/search/search_page_test.dart`
- Modify: `frontend/test/features/library/index_library_page_test.dart`
- Modify: `frontend/test/features/settings/settings_page_test.dart`
- Modify only if a test exposes a defect: the corresponding file under `frontend/lib/`

- [ ] **Step 1: 增加全局文案和单标题回归测试**

在 `widget_test.dart` 的生产应用测试中加入：

```dart
for (final forbidden in ['后端在线', '后端离线', '正在检测后端', '添加文件夹']) {
  expect(find.text(forbidden), findsNothing, reason: forbidden);
}
expect(find.text('搜索本地资料'), findsOneWidget);
expect(find.text('本地检索服务已就绪'), findsOneWidget);
```

在 `semantics_test.dart` 对每页标题使用相同 helper：

```dart
void expectSingleHeader(WidgetTester tester, String label) {
  final headers = tester
      .widgetList<Semantics>(
        find.byWidgetPredicate(
          (widget) => widget is Semantics && widget.properties.header == true,
        ),
      )
      .where((widget) => widget.properties.label == null);
  expect(find.text(label), findsOneWidget);
  expect(tester.getSemantics(find.text(label)).flagsCollection.isHeader, isTrue);
  expect(headers.length, greaterThanOrEqualTo(1));
}
```

分别调用 `expectSingleHeader(tester, '搜索本地资料')`、`expectSingleHeader(tester, '索引库')`、`expectSingleHeader(tester, '设置')`，并验证说明文字不是 header。

- [ ] **Step 2: 增加 48dp、200% 字号和高对比度回归矩阵**

保留现有 `androidTapTargetGuideline` 与主题对比度测试。扩充三个已经存在的响应式测试，不新增第二套 harness：

- 在 `search_page_test.dart` 的 `success workbench has no overflow` 循环中保留 `1280×720`、`1440×900`、`640×720`，并追加：

```dart
expect(find.widgetWithText(FilledButton, '搜索资料'), findsOneWidget);
```

- 在 `index_library_page_test.dart` 的 `catalog has no overflow at 200 percent text scale` 中追加：

```dart
expect(find.widgetWithText(FilledButton, '添加资料文件夹'), findsOneWidget);
expect(find.byKey(const Key('library-total-files')), findsOneWidget);
```

- 在 `settings_page_test.dart` 的 `settings page has no overflow at 200 percent text scale` 中追加：

```dart
expect(find.widgetWithText(FilledButton, '保存设置'), findsOneWidget);
expect(find.text('已保存'), findsOneWidget);
```

保存设置在无更改时允许禁用，但必须可见且语义标签完整。

- [ ] **Step 3: 运行定向无障碍测试并修复精确失败点**

Run:

```powershell
cd frontend
flutter test test/accessibility test/widget_test.dart test/features/search/search_page_test.dart test/features/library/index_library_page_test.dart test/features/settings/settings_page_test.dart
```

Expected: PASS。

如果出现失败，只允许以下对应修复：

- 触控目标不足：在 `AppTheme` 对应 ButtonTheme 增加 `minimumSize: Size(48, 48)`。
- 重复朗读：对装饰图标使用 `ExcludeSemantics`，对自定义动作使用单一 `Semantics(..., excludeSemantics: true)`。
- 大字号 overflow：把失败位置的 `Row` 改为 `Wrap`，或沿用现有 `LayoutBuilder` 在 `textScaler.scale(14) >= 21` 时切换 Column。
- 焦点未返回：请求该任务已经创建的 `_filterButtonFocusNode` 或 `_moreActionsFocusNode`，不得创建全局 FocusScope。
- 对比度不足：只调整现有 ColorScheme 语义色，不能引入硬编码浅灰文字。

- [ ] **Step 4: 扫描实现术语和旧文案**

Run:

```powershell
Get-ChildItem -LiteralPath frontend\lib -Recurse -File -Filter *.dart | Select-String -Pattern '后端在线|后端离线|正在检测后端|后端地址|添加文件夹|清除过滤|\bChroma\b|embedding' -CaseSensitive:$false
```

Expected: 无用户可见旧文案。允许 README、类型名和 API 层代码出现技术术语；本命令只扫描 `frontend/lib`，命中注释或内部标识时确认其不进入 Widget 文本。

- [ ] **Step 5: 提交无障碍与一致性回归**

```powershell
git add frontend/lib frontend/test
git commit -m "test: lock final UI accessibility and copy"
```

## Task 6: 完整验证和 Windows 桌面验收

**Files:**
- Modify only when verification exposes a scoped UI defect: files already listed in Tasks 1-5
- Do not modify: backend API, data model, generated platform files, build output

- [ ] **Step 1: 在 F 盘准备 Flutter 临时目录**

```powershell
$flutterTemp = 'F:\contentretrivalsystem\.tmp\final-ui-ux-polish'
New-Item -ItemType Directory -Force -Path $flutterTemp | Out-Null
$env:TEMP = $flutterTemp
$env:TMP = $flutterTemp
```

Expected: `$env:TEMP` 与 `$env:TMP` 都指向 F 盘项目临时目录。

- [ ] **Step 2: 格式化并检查静态分析**

Run:

```powershell
cd frontend
dart format --output=none --set-exit-if-changed lib test
flutter analyze
```

Expected: 两条命令 exit code 0；`flutter analyze` 输出 `No issues found!`。

- [ ] **Step 3: 运行完整 Flutter 测试**

Run:

```powershell
cd frontend
flutter test
```

Expected: exit code 0，全部测试通过，无 overflow、pending timer 或未处理异常。

- [ ] **Step 4: 构建 Windows Debug 客户端**

Run:

```powershell
cd frontend
flutter build windows --debug
```

Expected: exit code 0，并生成 `frontend/build/windows/x64/runner/Debug/content_retrieval_app.exe`。

- [ ] **Step 5: 做实际桌面界面检查**

运行：

```powershell
cd frontend
flutter run -d windows
```

逐项检查：

1. 搜索页只有“搜索本地资料”一个一级标题，按钮为“搜索资料”。
2. 连接状态使用“本地检索服务”，离线状态同时有图标、文字和“重新连接”。
3. 宽屏显示筛选侧栏；窄窗口显示筛选按钮，Escape 关闭后焦点返回。
4. 搜索更新时旧结果仍可见，完成后列表稳定替换。
5. 索引库只有“添加资料文件夹”为主要按钮，文件危险操作位于更多菜单。
6. 设置页分为连接、外观、无障碍，修改后显示“尚未保存更改”。
7. 浅色、深色、高对比度、200% 字号和仅键盘路径均无截断、重复朗读或失焦。

Expected: 所有检查项通过；关闭应用后终端正常返回。

- [ ] **Step 6: 审计最终提交内容**

Run:

```powershell
git status --short
git diff --check 20434e9..HEAD
git diff --stat 20434e9..HEAD
git log --oneline 20434e9..HEAD
```

Expected: 工作树只允许存在用户原有的无关改动；本分支的提交只修改本计划列出的前端源码、测试和计划文档，`git diff --check` 无输出。

- [ ] **Step 7: 如验证阶段产生修复则提交，否则记录验证完成**

只有在 Steps 2-5 暴露并修复了范围内缺陷时执行：

```powershell
git add frontend/lib frontend/test
git commit -m "fix: close final UI polish regressions"
```

Expected: 提交成功；若没有代码修复，不创建空提交。
