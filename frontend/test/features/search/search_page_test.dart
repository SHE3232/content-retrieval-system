import 'dart:async';
import 'dart:ui' show SemanticsAction, Tristate;

import 'package:content_retrieval_app/app/app_theme.dart';
import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/core/presentation/workspace_header.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:content_retrieval_app/features/search/presentation/search_controller.dart';
import 'package:content_retrieval_app/features/search/presentation/search_page.dart';
import 'package:content_retrieval_app/features/status/backend_status_controller.dart';
import 'package:content_retrieval_app/features/status/backend_status_models.dart';
import 'package:flutter/material.dart' hide SearchController;
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fakes.dart';

void main() {
  testWidgets('workspace heading excludes its supporting description', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    await _SearchHarness.create(tester);

    final workspaceHeader = find.byType(WorkspaceHeader);
    final heading = find.descendant(
      of: workspaceHeader,
      matching: find.byWidgetPredicate(
        (widget) => widget is Semantics && widget.properties.header == true,
      ),
    );
    expect(heading, findsOneWidget);
    final headingData = tester.getSemantics(heading).getSemanticsData();
    expect(headingData.label, '搜索');
    expect(headingData.flagsCollection.isHeader, isTrue);

    final description = find.semantics.byLabel(RegExp('在本地资料中找回你记得的内容'));
    expect(description, findsOneWidget);
    expect(
      description.evaluate().single.getSemanticsData().flagsCollection.isHeader,
      isFalse,
    );
    semantics.dispose();
  });

  testWidgets('compact filter exposes one interactive restriction label', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    final harness = await _SearchHarness.create(
      tester,
      surfaceSize: const Size(900, 720),
    );
    harness.searchController.toggleContentType(SearchContentType.images);
    await tester.pump();

    final filter = find.semantics.byLabel('筛选，1 个限制');
    expect(filter, findsOneWidget);
    final data = filter.evaluate().single.getSemanticsData();
    expect(data.hasAction(SemanticsAction.tap), isTrue);
    expect(data.flagsCollection.isButton, isTrue);
    semantics.dispose();
  });

  testWidgets('search stage leads with the approved task language', (
    tester,
  ) async {
    await _SearchHarness.create(tester);

    expect(find.byKey(const Key('search-stage')), findsOneWidget);
    expect(find.text('找回你记得的内容'), findsOneWidget);
    expect(find.text('描述一个概念、一段话，或图片中的内容。'), findsOneWidget);
    expect(find.text('Ctrl K'), findsOneWidget);
  });

  testWidgets('initial state teaches content-first searching', (tester) async {
    await _SearchHarness.create(tester);

    expect(find.text('说出你还记得的内容'), findsOneWidget);
    expect(find.textContaining('哪个 PDF 讲过键盘导航'), findsOneWidget);
  });

  testWidgets('success uses a continuous explainable result list', (
    tester,
  ) async {
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
    expect(
      find.byKey(const Key('search-result-row-research-pdf')),
      findsOneWidget,
    );
    expect(find.text('PDF'), findsOneWidget);
    expect(find.text('找到 1 条相关资料'), findsOneWidget);
    expect(find.textContaining('候选'), findsNothing);
    expect(find.textContaining('ms'), findsNothing);
  });

  testWidgets('compact filter entry reports active restrictions', (
    tester,
  ) async {
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

  testWidgets('online initial state exposes a labeled search control', (
    tester,
  ) async {
    await _SearchHarness.create(tester);

    expect(find.text('后端在线'), findsOneWidget);
    expect(find.text('搜索内容'), findsOneWidget);
    expect(find.byKey(const Key('search-query-field')), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('search-submit-button')))
          .onPressed,
      isNotNull,
    );
  });

  for (final themeMode in [ThemeMode.light, ThemeMode.dark]) {
    testWidgets('online status meets contrast in ${themeMode.name} mode', (
      tester,
    ) async {
      await _SearchHarness.create(tester, themeMode: themeMode);
      final statusText = find.text('后端在线');
      final textColor = tester.widget<Text>(statusText).style!.color!;
      final iconColor = tester
          .widget<Icon>(find.byIcon(Icons.check_circle_outline))
          .color!;
      final background = tester
          .widget<ColoredBox>(
            find
                .ancestor(of: statusText, matching: find.byType(ColoredBox))
                .first,
          )
          .color;

      expect(iconColor, textColor);
      expect(_contrastRatio(textColor, background), greaterThanOrEqualTo(4.5));
    });
  }

  testWidgets('checking and offline states are explicit and block search', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(
      tester,
      backendState: BackendConnectionState.checking,
    );

    expect(find.text('正在检测后端'), findsOneWidget);
    expect(harness.submitButton.onPressed, isNull);

    harness.statusController.state = BackendConnectionState.offline;
    harness.statusController.notifyListeners();
    await tester.pump();

    expect(find.text('后端离线'), findsOneWidget);
    expect(find.text('重新检测'), findsOneWidget);
    expect(harness.submitButton.onPressed, isNull);
  });

  testWidgets('offline status retains the last successful result', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.add(_response(names: const ['notes.txt']));
    await harness.search('notes');

    harness.statusController.state = BackendConnectionState.offline;
    harness.statusController.notifyListeners();
    await tester.pump();

    expect(find.text('后端离线'), findsOneWidget);
    expect(find.text('notes.txt'), findsOneWidget);
    expect(harness.submitButton.onPressed, isNull);

    harness.backendApi.readyResults.add(false);
    await tester.tap(find.byKey(const Key('backend-refresh-button')));
    await tester.pumpAndSettle();
    expect(harness.backendApi.readyCalls, 1);
    expect(find.text('notes.txt'), findsOneWidget);
  });

  testWidgets('enter and click each submit exactly one request', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.addAll([
        _response(query: 'alpha'),
        _response(query: 'beta'),
      ]);

    await tester.enterText(
      find.byKey(const Key('search-query-field')),
      ' alpha ',
    );
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();
    expect(harness.searchService.calls, hasLength(1));
    expect(harness.searchService.calls.single.query, 'alpha');

    await tester.enterText(
      find.byKey(const Key('search-query-field')),
      ' beta ',
    );
    await tester.tap(find.byKey(const Key('search-submit-button')));
    await tester.pumpAndSettle();
    expect(harness.searchService.calls, hasLength(2));
    expect(harness.searchService.calls.last.query, 'beta');
  });

  testWidgets('blank search stays local and shows Chinese inline validation', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester);
    await tester.enterText(
      find.byKey(const Key('search-query-field')),
      '   \t ',
    );

    await tester.tap(find.byKey(const Key('search-submit-button')));
    await tester.pump();

    expect(harness.searchService.calls, isEmpty);
    expect(find.text('请输入搜索内容'), findsOneWidget);
    expect(find.text('Enter a search query'), findsNothing);
  });

  testWidgets('loading uses three structural skeletons and blocks repeats', (
    tester,
  ) async {
    final pending = Completer<SearchResponse>();
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.add(pending.future);

    await tester.enterText(
      find.byKey(const Key('search-query-field')),
      'pending',
    );
    await tester.tap(find.byKey(const Key('search-submit-button')));
    await tester.pump();

    expect(
      find.byKey(const Key('search-loading-skeleton'), skipOffstage: false),
      findsNWidgets(3),
    );
    final loadingSemantics = find.byWidgetPredicate(
      (widget) =>
          widget is Semantics && widget.properties.label == '正在搜索“pending”。',
    );
    expect(loadingSemantics, findsOneWidget);
    expect(
      tester.widget<Semantics>(loadingSemantics).properties.liveRegion,
      isTrue,
    );
    expect(
      find.descendant(
        of: loadingSemantics,
        matching: find.byType(ExcludeSemantics),
      ),
      findsOneWidget,
    );
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(harness.submitButton.onPressed, isNull);
    await tester.tap(
      find.byKey(const Key('search-submit-button')),
      warnIfMissed: false,
    );
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();
    expect(harness.searchService.calls, hasLength(1));

    pending.complete(_response(query: 'pending'));
    await tester.pumpAndSettle();
  });

  testWidgets('loading locks persistent filters until the response completes', (
    tester,
  ) async {
    final pending = Completer<SearchResponse>();
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.add(pending.future);
    await tester.enterText(
      find.byKey(const Key('search-query-field')),
      'locked criteria',
    );
    await tester.tap(find.byKey(const Key('search-submit-button')));
    await tester.pump();

    _expectFilterControlsEnabled(tester, false);
    await tester.tap(find.text('语义'), warnIfMissed: false);
    await tester.tap(
      find.byKey(const Key('search-content-images')),
      warnIfMissed: false,
    );
    await tester.tap(
      find.byKey(const Key('search-channel-keyword')),
      warnIfMissed: false,
    );
    await tester.pump();

    expect(harness.searchController.mode, RetrievalMode.hybrid);
    expect(harness.searchController.channels, SearchChannel.values.toSet());
    expect(
      harness.searchController.contentTypes,
      SearchContentType.values.toSet(),
    );
    expect(harness.searchService.calls, hasLength(1));

    pending.complete(
      _response(query: 'locked criteria', names: const ['locked.txt']),
    );
    await tester.pumpAndSettle();

    expect(find.text('locked.txt'), findsOneWidget);
    _expectFilterControlsEnabled(tester, true);
  });

  testWidgets(
    'loading filter lock stays synchronized inside the bottom sheet',
    (tester) async {
      final pending = Completer<SearchResponse>();
      final harness =
          await _SearchHarness.create(tester, surfaceSize: const Size(900, 720))
            ..searchService.results.add(pending.future);
      await tester.enterText(
        find.byKey(const Key('search-query-field')),
        'modal lock',
      );
      await tester.tap(find.byKey(const Key('search-submit-button')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('search-filter-button')));
      await tester.pumpAndSettle();

      _expectFilterControlsEnabled(tester, false);
      pending.complete(_response(query: 'modal lock'));
      await tester.pumpAndSettle();

      _expectFilterControlsEnabled(tester, true);
      expect(harness.searchService.calls, hasLength(1));
    },
  );

  testWidgets('empty state clears filters and exposes the follow-up request', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester)
      ..searchController.setMode(RetrievalMode.semantic)
      ..searchController.toggleContentType(SearchContentType.images)
      ..searchService.results.addAll([
        _response(hits: const <SearchHit>[]),
        _response(query: 'missing', names: const ['found.txt']),
      ]);
    await harness.search('missing');

    expect(find.text('未找到匹配内容'), findsOneWidget);
    await tester.tap(find.byKey(const Key('clear-search-filters-button')));
    await tester.pumpAndSettle();

    expect(harness.searchController.mode, RetrievalMode.hybrid);
    expect(
      harness.searchController.contentTypes,
      SearchContentType.values.toSet(),
    );
    expect(harness.searchService.calls, hasLength(2));
    expect(find.text('found.txt'), findsOneWidget);
  });

  testWidgets('422 rejection maps to stable Chinese validation only', (
    tester,
  ) async {
    final privateCause = StateError('private stack marker');
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.add(
        ApiException(
          ApiErrorKind.rejected,
          'backend private validation',
          statusCode: 422,
          cause: privateCause,
        ),
      );

    await harness.search('bad');

    expect(find.text('搜索条件有误，请调整后重试'), findsOneWidget);
    expect(find.textContaining('backend private'), findsNothing);
    expect(find.textContaining('private stack'), findsNothing);
    expect(find.textContaining('StateError'), findsNothing);
  });

  testWidgets('503 maps to service unavailable with retry', (tester) async {
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.addAll([
        const ApiException(
          ApiErrorKind.rejected,
          'nginx secret',
          statusCode: 503,
        ),
        _response(query: 'retry', names: const ['recovered.txt']),
      ]);
    await harness.search('retry');

    expect(find.text('搜索服务暂时不可用，请稍后重试'), findsOneWidget);
    expect(find.text('重试'), findsOneWidget);
    expect(find.text('搜索条件有误，请调整后重试'), findsNothing);
    expect(find.text('请调整搜索条件'), findsNothing);
    expect(find.textContaining('nginx secret'), findsNothing);

    await tester.tap(find.byKey(const Key('search-retry-button')));
    await tester.pumpAndSettle();
    expect(harness.searchService.calls, hasLength(2));
    expect(find.text('recovered.txt'), findsOneWidget);
  });

  testWidgets('retry follows backend availability and submits once online', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.add(
        const ApiException(
          ApiErrorKind.rejected,
          'hidden outage detail',
          statusCode: 503,
        ),
      );
    await harness.search('retry gating');

    harness.statusController.state = BackendConnectionState.offline;
    harness.statusController.notifyListeners();
    await tester.pump();
    final retry = find.byKey(const Key('search-retry-button'));
    expect(tester.widget<FilledButton>(retry).onPressed, isNull);
    await tester.tap(retry, warnIfMissed: false);
    await tester.pump();
    expect(harness.searchService.calls, hasLength(1));

    harness.searchService.results.add(
      _response(query: 'retry gating', names: const ['online.txt']),
    );
    harness.statusController.state = BackendConnectionState.online;
    harness.statusController.notifyListeners();
    await tester.pump();
    expect(tester.widget<FilledButton>(retry).onPressed, isNotNull);
    await tester.tap(retry);
    await tester.pumpAndSettle();

    expect(harness.searchService.calls, hasLength(2));
    expect(find.text('online.txt'), findsOneWidget);
  });

  testWidgets('other API failures use a generic safe message', (tester) async {
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.add(
        const ApiException(
          ApiErrorKind.rejected,
          'server body must stay hidden',
          statusCode: 500,
        ),
      );

    await harness.search('broken');

    expect(find.text('搜索失败，请稍后重试'), findsOneWidget);
    expect(find.text('搜索条件有误，请调整后重试'), findsNothing);
    expect(find.text('请调整搜索条件'), findsNothing);
    expect(find.textContaining('server body'), findsNothing);
  });

  testWidgets('success rows show real metadata and active response summary', (
    tester,
  ) async {
    final hit = _hit(
      fileId: 'one',
      name: 'report.pdf',
      path: r'C:\资料\report.pdf',
      snippet: 'alpha appears in this paragraph',
      pageNumber: 7,
      paragraphNumber: null,
      matchReasons: const [SearchChannel.keyword, SearchChannel.textSemantic],
    );
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.add(
        _response(
          query: 'alpha',
          hits: [hit],
          totalCandidates: 31,
          elapsedMs: 12.75,
        ),
      );
    await harness.search('alpha');

    expect(find.text('report.pdf'), findsOneWidget);
    expect(find.text('alpha appears in this paragraph'), findsOneWidget);
    expect(find.text('第 7 页'), findsOneWidget);
    expect(find.text(r'C:\资料\report.pdf'), findsOneWidget);
    expect(find.text('找到 1 条相关资料'), findsOneWidget);
    expect(find.text('命中：关键词'), findsOneWidget);
    expect(find.text('命中：文本语义'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '打开'), findsOneWidget);
    expect(find.byTooltip('复制完整路径'), findsOneWidget);
    expect(find.bySemanticsLabel('打开 report.pdf'), findsOneWidget);
    expect(find.bySemanticsLabel('复制 report.pdf 的完整路径'), findsOneWidget);
    expect(find.bySemanticsLabel(r'完整路径 C:\资料\report.pdf'), findsOneWidget);
    final pathSemantics = find.byWidgetPredicate(
      (widget) =>
          widget is Semantics &&
          widget.properties.label == r'完整路径 C:\资料\report.pdf',
    );
    expect(pathSemantics, findsOneWidget);
    expect(tester.widget<Semantics>(pathSemantics).excludeSemantics, isTrue);
  });

  testWidgets('paragraph metadata is shown when page is absent', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.add(
        _response(
          hits: [
            _hit(fileId: 'paragraph', name: 'notes.txt', paragraphNumber: 4),
          ],
        ),
      );
    await harness.search('notes');

    expect(find.text('第 4 段'), findsOneWidget);
  });

  testWidgets('file launch errors stay inline and isolated to their row', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester)
      ..fileLauncher.results.addAll([
        const FileLaunchException(
          FileLaunchErrorKind.notFound,
          'private missing detail',
        ),
        const FileLaunchException(
          FileLaunchErrorKind.launchFailed,
          'private launch detail',
        ),
      ])
      ..searchService.results.add(
        _response(names: const ['one.txt', 'two.txt']),
      );
    await harness.search('files');

    await tester.tap(find.byKey(const Key('open-file-id-0')));
    await tester.pump();
    expect(find.text('文件不存在或已被移动'), findsOneWidget);
    expect(find.text('无法打开文件，请检查系统关联设置'), findsNothing);

    await tester.tap(find.byKey(const Key('open-file-id-1')));
    await tester.pump();
    expect(find.text('文件不存在或已被移动'), findsOneWidget);
    expect(find.text('无法打开文件，请检查系统关联设置'), findsOneWidget);
    expect(find.textContaining('private missing'), findsNothing);
    expect(find.textContaining('private launch'), findsNothing);
  });

  testWidgets('copy records the path and confirms with a snack bar', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.add(
        _response(
          hits: [
            _hit(
              fileId: 'copy-me',
              name: 'copy.txt',
              path: r'C:\notes\copy.txt',
            ),
          ],
        ),
      );
    await harness.search('copy');

    await tester.tap(find.byKey(const Key('copy-path-copy-me')));
    await tester.pump();

    expect(harness.pathClipboard.paths, [r'C:\notes\copy.txt']);
    expect(find.text('路径已复制'), findsOneWidget);
  });

  testWidgets('open semantics invokes once and reflects pending state', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    final pending = Completer<void>();
    final harness = await _SearchHarness.create(tester)
      ..fileLauncher.results.add(pending.future)
      ..searchService.results.add(_response(names: const ['report.pdf']));
    await harness.search('semantic open');
    final open = find.semantics.byLabel('打开 report.pdf');

    expect(open.evaluate(), hasLength(1));
    var data = open.evaluate().single.getSemanticsData();
    expect(data.hasAction(SemanticsAction.tap), isTrue);
    expect(data.flagsCollection.isEnabled, Tristate.isTrue);

    tester.semantics.tap(open);
    await tester.pump();

    expect(harness.fileLauncher.calls, 1);
    data = open.evaluate().single.getSemanticsData();
    expect(data.hasAction(SemanticsAction.tap), isFalse);
    expect(data.flagsCollection.isEnabled, Tristate.isFalse);

    pending.complete();
    await tester.pump();

    data = open.evaluate().single.getSemanticsData();
    expect(data.hasAction(SemanticsAction.tap), isTrue);
    expect(data.flagsCollection.isEnabled, Tristate.isTrue);
    expect(harness.fileLauncher.calls, 1);
    semantics.dispose();
  });

  testWidgets('copy semantics invokes once and reflects pending state', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    final pending = Completer<void>();
    final harness = await _SearchHarness.create(tester)
      ..pathClipboard.results.add(pending.future)
      ..searchService.results.add(_response(names: const ['report.pdf']));
    await harness.search('semantic copy');
    final copy = find.semantics.byLabel('复制 report.pdf 的完整路径');

    expect(copy.evaluate(), hasLength(1));
    var data = copy.evaluate().single.getSemanticsData();
    expect(data.hasAction(SemanticsAction.tap), isTrue);
    expect(data.flagsCollection.isEnabled, Tristate.isTrue);

    tester.semantics.tap(copy);
    await tester.pump();

    expect(harness.pathClipboard.calls, 1);
    data = copy.evaluate().single.getSemanticsData();
    expect(data.hasAction(SemanticsAction.tap), isFalse);
    expect(data.flagsCollection.isEnabled, Tristate.isFalse);

    pending.complete();
    await tester.pump();

    data = copy.evaluate().single.getSemanticsData();
    expect(data.hasAction(SemanticsAction.tap), isTrue);
    expect(data.flagsCollection.isEnabled, Tristate.isTrue);
    expect(harness.pathClipboard.calls, 1);
    semantics.dispose();
  });

  testWidgets(
    'result tile open disables while pending and ignores double tap',
    (tester) async {
      final pending = Completer<void>();
      final harness = await _SearchHarness.create(tester)
        ..fileLauncher.results.add(pending.future)
        ..searchService.results.add(_response(names: const ['pending.txt']));
      await harness.search('open pending');
      final open = find.byKey(const Key('open-file-id-0'));

      await tester.tap(open);
      await tester.pump();
      expect(tester.widget<FilledButton>(open).onPressed, isNull);
      await tester.tap(open, warnIfMissed: false);
      await tester.pump();
      expect(harness.fileLauncher.calls, 1);

      pending.complete();
      await tester.pump();
      expect(tester.widget<FilledButton>(open).onPressed, isNotNull);
    },
  );

  testWidgets(
    'result tile copy disables while pending and ignores double tap',
    (tester) async {
      final pending = Completer<void>();
      final harness = await _SearchHarness.create(tester)
        ..pathClipboard.results.add(pending.future)
        ..searchService.results.add(_response(names: const ['pending.txt']));
      await harness.search('copy pending');
      final copy = find.byKey(const Key('copy-path-file-id-0'));

      await tester.tap(copy);
      await tester.pump();
      expect(tester.widget<IconButton>(copy).onPressed, isNull);
      await tester.tap(copy, warnIfMissed: false);
      await tester.pump();
      expect(harness.pathClipboard.calls, 1);

      pending.complete();
      await tester.pump();
      expect(tester.widget<IconButton>(copy).onPressed, isNotNull);
      expect(find.text('路径已复制'), findsOneWidget);
    },
  );

  testWidgets('result tile pending operations tolerate unmount', (
    tester,
  ) async {
    final pendingOpen = Completer<void>();
    final pendingCopy = Completer<void>();
    final harness = await _SearchHarness.create(tester)
      ..fileLauncher.results.add(pendingOpen.future)
      ..pathClipboard.results.add(pendingCopy.future)
      ..searchService.results.add(_response(names: const ['pending.txt']));
    await harness.search('unmount pending');
    final dynamic openCallback = tester
        .widget<FilledButton>(find.byKey(const Key('open-file-id-0')))
        .onPressed!;
    final dynamic copyCallback = tester
        .widget<IconButton>(find.byKey(const Key('copy-path-file-id-0')))
        .onPressed!;

    final Future<void> openOperation = openCallback() as Future<void>;
    final Future<void> copyOperation = copyCallback() as Future<void>;
    await tester.pumpWidget(const SizedBox.shrink());
    pendingOpen.complete();
    pendingCopy.complete();
    await Future.wait([openOperation, copyOperation]);
    await tester.pump();

    expect(tester.takeException(), isNull);
  });

  testWidgets('result tile shows safe expected copy failure without success', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester)
      ..pathClipboard.results.add(const PathClipboardException())
      ..searchService.results.add(_response(names: const ['copy-error.txt']));
    await harness.search('copy failure');

    await tester.tap(find.byKey(const Key('copy-path-file-id-0')));
    await tester.pump();

    expect(find.text('无法复制路径，请稍后重试'), findsOneWidget);
    expect(find.text('路径已复制'), findsNothing);
  });

  testWidgets('result tile preserves unexpected operation errors', (
    tester,
  ) async {
    final openError = StateError('unexpected open');
    final copyError = StateError('unexpected copy');
    final harness = await _SearchHarness.create(tester)
      ..fileLauncher.results.add(openError)
      ..pathClipboard.results.add(copyError)
      ..searchService.results.add(_response(names: const ['errors.txt']));
    await harness.search('unexpected errors');
    final dynamic openCallback = tester
        .widget<FilledButton>(find.byKey(const Key('open-file-id-0')))
        .onPressed!;
    final dynamic copyCallback = tester
        .widget<IconButton>(find.byKey(const Key('copy-path-file-id-0')))
        .onPressed!;

    await expectLater(openCallback(), throwsA(same(openError)));
    await expectLater(copyCallback(), throwsA(same(copyError)));
  });

  testWidgets(
    'same file in a new response clears errors and ignores stale completion',
    (tester) async {
      final pendingOpen = Completer<void>();
      final harness = await _SearchHarness.create(tester)
        ..fileLauncher.results.add(pendingOpen.future)
        ..pathClipboard.results.add(const PathClipboardException())
        ..searchService.results.addAll([
          _response(
            hits: [
              _hit(
                fileId: 'same-file',
                name: 'old.txt',
                path: r'C:\results\old.txt',
              ),
            ],
          ),
          _response(
            hits: [
              _hit(
                fileId: 'same-file',
                name: 'new.txt',
                path: r'C:\results\new.txt',
              ),
            ],
          ),
        ]);
      await harness.search('old response');

      await tester.tap(find.byKey(const Key('copy-path-same-file')));
      await tester.pump();
      expect(find.text('无法复制路径，请稍后重试'), findsOneWidget);
      final dynamic openCallback = tester
          .widget<FilledButton>(find.byKey(const Key('open-same-file')))
          .onPressed!;
      final Future<void> oldOpen = openCallback() as Future<void>;
      await tester.pump();

      await harness.search('new response');
      expect(find.text('new.txt'), findsOneWidget);
      expect(find.text(r'C:\results\new.txt'), findsOneWidget);
      expect(find.text('无法复制路径，请稍后重试'), findsNothing);

      pendingOpen.completeError(
        const FileLaunchException(
          FileLaunchErrorKind.launchFailed,
          'private stale failure',
        ),
      );
      await oldOpen;
      await tester.pump();

      expect(find.text('无法打开文件，请检查系统关联设置'), findsNothing);
      expect(find.textContaining('private stale failure'), findsNothing);
    },
  );

  testWidgets('desktop keeps a 292 pixel persistent filter panel', (
    tester,
  ) async {
    await _SearchHarness.create(tester, surfaceSize: const Size(1280, 720));

    expect(find.byKey(const Key('search-filter-button')), findsNothing);
    expect(
      tester.getSize(find.byKey(const Key('search-filter-panel'))).width,
      292,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'compact layout opens the shared filter panel in a bottom sheet',
    (tester) async {
      await _SearchHarness.create(tester, surfaceSize: const Size(900, 720));

      expect(find.byKey(const Key('search-filter-panel')), findsNothing);
      await tester.tap(find.byKey(const Key('search-filter-button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('search-filter-panel')), findsOneWidget);
      expect(find.text('检索模式'), findsOneWidget);
      expect(find.text('内容类型'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('bottom sheet filter selection stays visually synchronized', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(
      tester,
      surfaceSize: const Size(900, 720),
    );
    await tester.tap(find.byKey(const Key('search-filter-button')));
    await tester.pumpAndSettle();
    final imagesChip = find.byKey(const Key('search-content-images'));
    expect(tester.widget<FilterChip>(imagesChip).selected, isTrue);

    await tester.tap(imagesChip);
    await tester.pump();

    expect(tester.widget<FilterChip>(imagesChip).selected, isFalse);
    expect(
      harness.searchController.contentTypes,
      isNot(contains(SearchContentType.images)),
    );
    expect(harness.searchService.calls, isEmpty);
  });

  testWidgets('mode and content mutations submit once with updated criteria', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester)
      ..searchService.results.addAll([
        _response(query: 'filters'),
        _response(query: 'filters'),
        _response(query: 'filters'),
      ]);
    await harness.search('  filters  ');

    await tester.tap(find.text('语义'));
    await tester.pumpAndSettle();
    expect(harness.searchController.mode, RetrievalMode.semantic);
    expect(harness.searchController.channels, RetrievalMode.semantic.channels);
    expect(harness.searchService.calls, hasLength(2));
    expect(
      harness.searchService.calls.last.channels,
      RetrievalMode.semantic.channels,
    );

    await tester.tap(find.byKey(const Key('search-content-images')));
    await tester.pumpAndSettle();
    expect(
      harness.searchController.contentTypes,
      isNot(contains(SearchContentType.images)),
    );
    expect(harness.searchService.calls, hasLength(3));
    expect(harness.searchService.calls.last.query, 'filters');
  });

  testWidgets('the final retrieval channel cannot be deselected', (
    tester,
  ) async {
    final harness = await _SearchHarness.create(tester)
      ..searchController.setMode(RetrievalMode.exact);
    await tester.pump();

    await tester.tap(find.byKey(const Key('search-channel-keyword')));
    await tester.pump();

    expect(harness.searchController.channels, {SearchChannel.keyword});
    expect(find.text('至少保留一个检索通道'), findsOneWidget);
    expect(harness.searchService.calls, isEmpty);
  });

  testWidgets('Ctrl+K focuses search and Escape only removes focus', (
    tester,
  ) async {
    await _SearchHarness.create(tester);
    final field = find.byKey(const Key('search-query-field'));

    await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await tester.sendKeyEvent(LogicalKeyboardKey.keyK);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await tester.pump();
    expect(
      tester.widget<EditableText>(find.byType(EditableText)).focusNode.hasFocus,
      isTrue,
    );

    await tester.enterText(field, 'keep this text');
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pump();
    expect(
      tester.widget<EditableText>(find.byType(EditableText)).focusNode.hasFocus,
      isFalse,
    );
    expect(find.text('keep this text'), findsOneWidget);
  });

  for (final state in [
    BackendConnectionState.checking,
    BackendConnectionState.offline,
  ]) {
    testWidgets('filter mutation does not submit while ${state.name}', (
      tester,
    ) async {
      final harness = await _SearchHarness.create(tester, backendState: state);
      harness.searchController.setQuery('not submitted');
      await tester.pump();

      await tester.tap(find.text('语义'));
      await tester.pump();

      expect(harness.searchController.mode, RetrievalMode.semantic);
      expect(harness.searchService.calls, isEmpty);
    });
  }

  for (final size in [
    const Size(1280, 720),
    const Size(1440, 900),
    const Size(640, 720),
  ]) {
    testWidgets(
      'success workbench has no overflow at ${size.width}x${size.height}',
      (tester) async {
        final harness = await _SearchHarness.create(tester, surfaceSize: size)
          ..searchService.results.add(
            _response(names: const ['one.txt', 'two.txt', 'three.txt']),
          );
        await harness.search('responsive');

        expect(find.text('one.txt'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }

  test(
    'platform fakes queue success and typed failure without swallowing it',
    () async {
      final launcherPending = Completer<void>();
      final clipboardPending = Completer<void>();
      const launcherError = FileLaunchException(
        FileLaunchErrorKind.launchFailed,
        'queued failure',
      );
      const clipboardError = PathClipboardException();
      final launcher = FakeFileLauncher()
        ..results.addAll([null, launcherError, launcherPending.future]);
      final clipboard = FakePathClipboard()
        ..results.addAll([null, clipboardError, clipboardPending.future]);

      await launcher.open('first.txt');
      await expectLater(
        launcher.open('second.txt'),
        throwsA(same(launcherError)),
      );
      await clipboard.copy('first.txt');
      await expectLater(
        clipboard.copy('second.txt'),
        throwsA(same(clipboardError)),
      );

      final pendingOpen = launcher.open('third.txt');
      final pendingCopy = clipboard.copy('third.txt');
      launcherPending.complete();
      clipboardPending.complete();
      await Future.wait([pendingOpen, pendingCopy]);

      expect(launcher.paths, ['first.txt', 'second.txt', 'third.txt']);
      expect(clipboard.paths, ['first.txt', 'second.txt', 'third.txt']);
    },
  );
}

void _expectFilterControlsEnabled(WidgetTester tester, bool enabled) {
  expect(
    tester
        .widget<SegmentedButton<RetrievalMode>>(
          find.byType(SegmentedButton<RetrievalMode>),
        )
        .onSelectionChanged,
    enabled ? isNotNull : isNull,
  );
  for (final chip in tester.widgetList<FilterChip>(find.byType(FilterChip))) {
    expect(chip.onSelected, enabled ? isNotNull : isNull);
  }
}

final class _SearchHarness {
  _SearchHarness._({
    required this.tester,
    required this.searchService,
    required this.searchController,
    required this.backendApi,
    required this.statusController,
    required this.fileLauncher,
    required this.pathClipboard,
  });

  final WidgetTester tester;
  final FakeSearchService searchService;
  final SearchController searchController;
  final FakeBackendStatusClient backendApi;
  final BackendStatusController statusController;
  final FakeFileLauncher fileLauncher;
  final FakePathClipboard pathClipboard;

  static Future<_SearchHarness> create(
    WidgetTester tester, {
    BackendConnectionState backendState = BackendConnectionState.online,
    Size surfaceSize = const Size(1280, 720),
    ThemeMode themeMode = ThemeMode.light,
  }) async {
    await tester.binding.setSurfaceSize(surfaceSize);
    final searchService = FakeSearchService();
    final searchController = SearchController(searchService);
    final backendApi = FakeBackendStatusClient();
    final statusController = BackendStatusController(backendApi)
      ..state = backendState;
    final fileLauncher = FakeFileLauncher();
    final pathClipboard = FakePathClipboard();
    final harness = _SearchHarness._(
      tester: tester,
      searchService: searchService,
      searchController: searchController,
      backendApi: backendApi,
      statusController: statusController,
      fileLauncher: fileLauncher,
      pathClipboard: pathClipboard,
    );
    addTearDown(() async {
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.binding.setSurfaceSize(null);
      searchController.dispose();
      statusController.dispose();
    });

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(),
        darkTheme: AppTheme.dark(),
        themeMode: themeMode,
        home: Scaffold(
          body: SearchPage(
            controller: searchController,
            statusController: statusController,
            fileLauncher: fileLauncher,
            pathClipboard: pathClipboard,
          ),
        ),
      ),
    );
    await tester.pump();
    return harness;
  }

  FilledButton get submitButton => tester.widget<FilledButton>(
    find.byKey(const Key('search-submit-button')),
  );

  Future<void> search(String query) async {
    await tester.enterText(find.byKey(const Key('search-query-field')), query);
    await tester.tap(find.byKey(const Key('search-submit-button')));
    await tester.pumpAndSettle();
  }
}

double _contrastRatio(Color foreground, Color background) {
  final foregroundLuminance = foreground.computeLuminance();
  final backgroundLuminance = background.computeLuminance();
  final lighter = foregroundLuminance > backgroundLuminance
      ? foregroundLuminance
      : backgroundLuminance;
  final darker = foregroundLuminance > backgroundLuminance
      ? backgroundLuminance
      : foregroundLuminance;
  return (lighter + 0.05) / (darker + 0.05);
}

SearchResponse _response({
  String query = 'query',
  List<String> names = const ['result.txt'],
  List<SearchHit>? hits,
  int totalCandidates = 9,
  double elapsedMs = 8.5,
}) {
  return SearchResponse(
    query: query,
    hits:
        hits ??
        [
          for (var index = 0; index < names.length; index += 1)
            _hit(
              fileId: 'file-id-$index',
              name: names[index],
              path: 'C:\\results\\${names[index]}',
            ),
        ],
    totalCandidates: totalCandidates,
    elapsedMs: elapsedMs,
    weights: const {'keyword': 1},
  );
}

SearchHit _hit({
  required String fileId,
  required String name,
  String path = r'C:\results\result.txt',
  String? snippet = 'matching snippet',
  int? pageNumber,
  int? paragraphNumber,
  List<SearchChannel> matchReasons = const [SearchChannel.keyword],
}) {
  return SearchHit(
    fileId: fileId,
    sourceId: 'source-$fileId',
    path: path,
    name: name,
    mimeType: 'text/plain',
    modality: 'text',
    score: 0.91,
    matchReasons: matchReasons,
    snippet: snippet,
    pageNumber: pageNumber,
    paragraphNumber: paragraphNumber,
  );
}
