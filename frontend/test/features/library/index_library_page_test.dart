import 'dart:async';

import 'package:content_retrieval_app/core/platform/directory_picker.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_controller.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_page.dart';
import 'package:content_retrieval_app/core/presentation/workspace_notice.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fakes.dart';

const _sourceKey =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _otherSourceKey =
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';

void main() {
  testWidgets('library uses a workspace header and continuous catalog', (
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

    expect(find.text('管理可搜索的本地资料'), findsOneWidget);
    expect(find.byKey(const Key('library-file-list')), findsOneWidget);
    final row = find.byKey(const Key('indexed-file-row-file-1'));
    expect(row, findsOneWidget);
    expect(find.descendant(of: row, matching: find.byType(Card)), findsNothing);
  });

  testWidgets('renders catalog metadata and opens or copies a file', (
    tester,
  ) async {
    final service = _PageService()..pages.add(_page());
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _PagePicker(),
    );
    final launcher = FakeFileLauncher();
    final clipboard = FakePathClipboard();
    addTearDown(controller.dispose);

    await controller.load();
    await tester.pumpWidget(
      _app(controller, fileLauncher: launcher, pathClipboard: clipboard),
    );

    expect(find.text('索引库'), findsOneWidget);
    expect(find.byKey(const Key('library-total-files')), findsOneWidget);
    expect(find.text('1 个可搜索文件'), findsOneWidget);
    expect(find.textContaining('后端'), findsNothing);
    expect(find.text('guide.pdf'), findsOneWidget);
    expect(find.text('application/pdf'), findsOneWidget);
    expect(find.textContaining('4 条记录'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, '打开文件'));
    await tester.pump();
    expect(launcher.paths, [r'C:\docs\guide.pdf']);

    await tester.tap(find.byTooltip('复制 guide.pdf 的路径'));
    await tester.pump();
    expect(clipboard.paths, [r'C:\docs\guide.pdf']);
    expect(find.text('路径已复制'), findsOneWidget);
  });

  testWidgets('header has one primary add action', (tester) async {
    final controller = IndexLibraryController(
      service: _PageService()..pages.add(_page()),
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();

    await tester.pumpWidget(_app(controller));

    expect(find.widgetWithText(FilledButton, '添加资料文件夹'), findsOneWidget);
    expect(find.byTooltip('刷新索引库'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '添加文件夹'), findsNothing);
  });

  testWidgets('secondary file mutations live in the more menu', (tester) async {
    final controller = IndexLibraryController(
      service: _PageService()..pages.add(_page()),
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller));

    expect(find.text('打开文件'), findsOneWidget);
    expect(find.byTooltip('重新索引 guide.pdf'), findsNothing);
    expect(find.byTooltip('从索引移除 guide.pdf'), findsNothing);

    await tester.tap(find.byKey(const Key('more-actions-file-1')));
    await tester.pumpAndSettle();

    expect(find.text('重新索引文件'), findsOneWidget);
    expect(find.text('从索引库移除'), findsOneWidget);
  });

  testWidgets('reindex and remove require named confirmations', (tester) async {
    final service = _PageService()
      ..pages.add(_page())
      ..reindexJobs.add(_completedJob())
      ..pages.add(_page())
      ..removeResults.add(
        const DeletedIndexedFile(sourceKey: _sourceKey, deletedRecords: 4),
      )
      ..pages.add(_emptyPage);
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller));

    await tester.tap(find.byKey(const Key('more-actions-file-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('重新索引文件'));
    await tester.pumpAndSettle();
    expect(find.text('重新索引 guide.pdf？'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, '重新索引文件'));
    await tester.pumpAndSettle();
    expect(service.reindexCalls, [_sourceKey]);

    await tester.tap(find.byKey(const Key('more-actions-file-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('从索引库移除'));
    await tester.pumpAndSettle();
    expect(find.text('从索引库移除 guide.pdf？'), findsOneWidget);
    expect(find.text('不会删除磁盘上的原文件。'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, '从索引库移除'));
    for (var attempt = 0; attempt < 30; attempt += 1) {
      await tester.pump(const Duration(milliseconds: 20));
      if (find.textContaining('资料已从索引库移除').evaluate().isNotEmpty) {
        break;
      }
    }

    expect(service.removeCalls, [_sourceKey]);
    expect(find.text('资料已从索引库移除，共清理 4 条可搜索内容'), findsOneWidget);
    expect(find.byType(MaterialBanner), findsNothing);
    expect(find.text('索引库为空'), findsOneWidget);
  });

  testWidgets('more menu restores focus and reopens with keyboard', (
    tester,
  ) async {
    final controller = IndexLibraryController(
      service: _PageService()..pages.add(_page()),
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller));

    final menuFinder = find.byKey(const Key('more-actions-file-1'));
    await tester.tap(menuFinder);
    await tester.pumpAndSettle();
    await tester.tap(find.text('重新索引文件'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('取消'));
    await tester.pumpAndSettle();

    expect(
      FocusManager.instance.primaryFocus?.debugLabel,
      'more-actions-file-1',
    );

    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(find.text('重新索引文件'), findsOneWidget);

    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(
      FocusManager.instance.primaryFocus?.debugLabel,
      'more-actions-file-1',
    );

    await tester.sendKeyEvent(LogicalKeyboardKey.space);
    await tester.pumpAndSettle();
    expect(find.text('从索引库移除'), findsOneWidget);
  });

  testWidgets(
    'queued reindex waits for terminal state before restoring focus',
    (tester) async {
      final waits = <Completer<void>>[];
      final service = _PageService()
        ..pages.add(_page())
        ..reindexJobs.add(_job(IndexJobStatus.queued))
        ..fetchedJobs.add(_completedJob())
        ..pages.add(_page());
      final controller = IndexLibraryController(
        service: service,
        directoryPicker: _PagePicker(),
        wait: (_) {
          final wait = Completer<void>();
          waits.add(wait);
          return wait.future;
        },
      );
      addTearDown(controller.dispose);
      await controller.load();
      await tester.pumpWidget(_app(controller));
      final triggerFocusNode = tester
          .widget<FocusableActionDetector>(
            find.byKey(const Key('more-actions-file-1')),
          )
          .focusNode!;

      await tester.tap(find.byKey(const Key('more-actions-file-1')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('重新索引文件'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, '重新索引文件'));
      await tester.pump();
      await tester.pump();

      expect(controller.activeJob?.status, IndexJobStatus.queued);
      expect(find.text('重新索引任务已完成'), findsNothing);
      expect(
        tester
            .widget<FocusableActionDetector>(
              find.byKey(const Key('more-actions-file-1')),
            )
            .enabled,
        isFalse,
      );

      waits.single.complete();
      for (var attempt = 0; attempt < 10; attempt += 1) {
        await tester.pump();
      }
      await tester.pumpAndSettle();

      expect(controller.activeJob?.status, IndexJobStatus.completed);
      expect(
        tester
            .widget<FocusableActionDetector>(
              find.byKey(const Key('more-actions-file-1')),
            )
            .focusNode,
        same(triggerFocusNode),
      );
      expect(triggerFocusNode.canRequestFocus, isTrue);
      expect(
        FocusManager.instance.primaryFocus?.debugLabel,
        'more-actions-file-1',
      );
    },
  );

  testWidgets('successful removal focuses the stable refresh action', (
    tester,
  ) async {
    final service = _PageService()
      ..pages.add(_page())
      ..removeResults.add(
        const DeletedIndexedFile(sourceKey: _sourceKey, deletedRecords: 4),
      )
      ..pages.add(_emptyPage);
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller));

    await tester.tap(find.byKey(const Key('more-actions-file-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('从索引库移除'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '从索引库移除'));
    for (var attempt = 0; attempt < 20; attempt += 1) {
      await tester.pump(const Duration(milliseconds: 20));
    }

    expect(find.byKey(const Key('indexed-file-row-file-1')), findsNothing);
    expect(
      FocusManager.instance.primaryFocus?.debugLabel,
      'library-refresh-action',
    );
  });

  testWidgets(
    'page two reindex falls back to refresh and clears pending focus',
    (tester) async {
      final pageTwo = _page(
        page: 2,
        total: 21,
        totalPages: 2,
        fileId: 'file-2',
        name: 'page-two.pdf',
      );
      final service = _PageService()
        ..pages.add(pageTwo)
        ..reindexJobs.add(_completedJob())
        ..pages.add(
          _page(
            total: 21,
            totalPages: 2,
            sourceKey: _otherSourceKey,
            name: 'page-one.pdf',
          ),
        )
        ..pages.add(pageTwo);
      final controller = IndexLibraryController(
        service: service,
        directoryPicker: _PagePicker(),
      );
      addTearDown(controller.dispose);
      await controller.load(page: 2);
      await tester.pumpWidget(_app(controller));

      await tester.tap(find.byKey(const Key('more-actions-file-2')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('重新索引文件'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, '重新索引文件'));
      await tester.pumpAndSettle();

      expect(controller.page, 1);
      expect(
        FocusManager.instance.primaryFocus?.debugLabel,
        'library-refresh-action',
      );

      await controller.nextPage();
      await tester.pumpAndSettle();

      expect(controller.page, 2);
      expect(find.text('page-two.pdf'), findsOneWidget);
      expect(
        FocusManager.instance.primaryFocus?.debugLabel,
        'library-refresh-action',
      );
    },
  );

  testWidgets('disabled more menu cannot receive focus or open', (
    tester,
  ) async {
    final controller = IndexLibraryController(
      service: _PageService()..pages.add(_page()),
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    controller.isMutationInProgress = true;
    await tester.pumpWidget(_app(controller));

    final menuFinder = find.byKey(const Key('more-actions-file-1'));
    final trigger = tester.widget<FocusableActionDetector>(menuFinder);
    expect(trigger.enabled, isFalse);

    trigger.focusNode!.requestFocus();
    await tester.pump();
    expect(trigger.focusNode!.hasFocus, isFalse);

    await tester.tap(menuFinder);
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(find.text('重新索引文件'), findsNothing);
  });

  testWidgets('reduced motion uses a static more-action focus ring', (
    tester,
  ) async {
    final controller = IndexLibraryController(
      service: _PageService()..pages.add(_page()),
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller, disableAnimations: true));

    final trigger = find.byKey(const Key('more-actions-file-1'));
    expect(
      find.descendant(of: trigger, matching: find.byType(AnimatedContainer)),
      findsNothing,
    );
  });

  testWidgets('refresh and mutation busy states disable page actions', (
    tester,
  ) async {
    final delayedRefresh = Completer<IndexedFilePage>();
    final service = _PageService()
      ..pages.add(_page(total: 41, totalPages: 3))
      ..pages.add(delayedRefresh.future);
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _PagePicker(),
      wait: (_) => Completer<void>().future,
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller));

    final refresh = controller.refresh();
    await tester.pump();

    expect(
      tester
          .widget<IconButton>(find.widgetWithIcon(IconButton, Icons.refresh))
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '添加资料文件夹'))
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<FocusableActionDetector>(
            find.byKey(const Key('more-actions-file-1')),
          )
          .enabled,
      isFalse,
    );
    expect(
      tester
          .widget<IconButton>(
            find.widgetWithIcon(IconButton, Icons.chevron_right),
          )
          .onPressed,
      isNull,
    );

    delayedRefresh.complete(_page(total: 41, totalPages: 3));
    await refresh;
    await tester.pump();

    service.reindexJobs.add(_job(IndexJobStatus.queued));
    await controller.reindex(_sourceKey);
    await tester.pump();

    expect(
      tester
          .widget<IconButton>(find.widgetWithIcon(IconButton, Icons.refresh))
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '添加资料文件夹'))
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<FocusableActionDetector>(
            find.byKey(const Key('more-actions-file-1')),
          )
          .enabled,
      isFalse,
    );
    expect(
      tester
          .widget<IconButton>(
            find.widgetWithIcon(IconButton, Icons.chevron_right),
          )
          .onPressed,
      isNull,
    );
  });

  testWidgets('pagination follows the twenty pixel page rhythm', (
    tester,
  ) async {
    final controller = IndexLibraryController(
      service: _PageService()..pages.add(_page(total: 41, totalPages: 3)),
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller));

    final pagination = tester.widget<Padding>(
      find
          .ancestor(of: find.text('1 / 3'), matching: find.byType(Padding))
          .first,
    );
    expect(
      pagination.padding,
      const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
    );
  });

  testWidgets('unsupported directory selection is disabled with explanation', (
    tester,
  ) async {
    final service = _PageService()..pages.add(_emptyPage);
    final picker = _PagePicker()..isSupported = false;
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: picker,
    );
    addTearDown(controller.dispose);
    await controller.load();

    await tester.pumpWidget(_app(controller));

    final addButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '添加资料文件夹'),
    );
    expect(addButton.onPressed, isNull);
    expect(find.textContaining('Windows、macOS 或 Linux 桌面版'), findsOneWidget);
    expect(find.textContaining('后端'), findsNothing);
  });

  testWidgets('job progress and failure details remain textual', (
    tester,
  ) async {
    final service = _PageService()..pages.add(_page());
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    controller
      ..activeJob = _completedJob(status: IndexJobStatus.completedWithErrors)
      ..failureDetails = const IndexFailureDetails(
        jobId: 'job-1',
        status: IndexJobStatus.completedWithErrors,
        total: 1,
        failures: [
          IndexFailure(
            path: r'C:\docs\broken.pdf',
            code: 'PARSE_FAILED',
            message: 'Could not parse file',
            stage: 'parse',
            retryable: false,
            fileId: null,
            sourceId: null,
          ),
        ],
        error: null,
      );

    await tester.pumpWidget(_app(controller));

    expect(find.text('部分文件未能加入索引库'), findsOneWidget);
    expect(find.textContaining('已添加 1 个文件，1 个文件需要处理'), findsOneWidget);
    expect(find.text('本次任务有 1 个文件需要处理'), findsOneWidget);
    await tester.tap(find.text('查看失败详情'));
    await tester.pumpAndSettle();
    expect(find.textContaining('broken.pdf'), findsOneWidget);
    expect(find.text('解析文件时失败'), findsOneWidget);
    expect(find.textContaining('PARSE_FAILED'), findsNothing);
    expect(find.textContaining('Could not parse file'), findsNothing);
  });

  testWidgets('persistent errors use one dismissible workspace notice', (
    tester,
  ) async {
    final controller = IndexLibraryController(
      service: _PageService()..pages.add(_page()),
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    controller.errorMessage = '无法加载索引库。';

    await tester.pumpWidget(_app(controller));

    expect(find.byType(WorkspaceNotice), findsOneWidget);
    expect(find.text('重新尝试'), findsOneWidget);
    expect(find.byTooltip('关闭提示'), findsOneWidget);
    expect(find.byType(MaterialBanner), findsNothing);
  });

  testWidgets('controller success is shown once as a snackbar', (tester) async {
    final controller = IndexLibraryController(
      service: _PageService()..pages.add(_page()),
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    controller.successMessage = '资料已从索引库移除';

    await tester.pumpWidget(_app(controller));
    await tester.pump();

    expect(find.byType(SnackBar), findsOneWidget);
    expect(find.text('资料已从索引库移除'), findsOneWidget);
    expect(find.byType(MaterialBanner), findsNothing);
    expect(controller.successMessage, isNull);

    await tester.pump();
    expect(find.byType(SnackBar), findsOneWidget);
  });

  testWidgets('catalog has no overflow at 200 percent text scale', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final service = _PageService()..pages.add(_page());
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _PagePicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();

    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(2)),
        child: _app(controller),
      ),
    );
    await tester.pump();

    expect(tester.takeException(), isNull);
    expect(find.text('guide.pdf'), findsOneWidget);
    expect(find.byKey(const Key('library-total-files')), findsOneWidget);
    expect(
      tester.getSize(find.widgetWithText(FilledButton, '打开文件')).height,
      greaterThanOrEqualTo(48),
    );
    expect(
      tester.getSize(find.byKey(const Key('more-actions-file-1'))).height,
      greaterThanOrEqualTo(48),
    );
    expect(
      tester.getSize(find.widgetWithText(FilledButton, '添加资料文件夹')).height,
      greaterThanOrEqualTo(48),
    );
    expect(
      tester.getSize(find.byTooltip('复制 guide.pdf 的路径')).height,
      greaterThanOrEqualTo(48),
    );
  });
}

Widget _app(
  IndexLibraryController controller, {
  FakeFileLauncher? fileLauncher,
  FakePathClipboard? pathClipboard,
  bool disableAnimations = false,
}) {
  return MaterialApp(
    builder: disableAnimations
        ? (context, child) => MediaQuery(
            data: MediaQuery.of(context).copyWith(disableAnimations: true),
            child: child!,
          )
        : null,
    home: Scaffold(
      body: IndexLibraryPage(
        controller: controller,
        fileLauncher: fileLauncher ?? FakeFileLauncher(),
        pathClipboard: pathClipboard ?? FakePathClipboard(),
      ),
    ),
  );
}

IndexedFilePage _page({
  int page = 1,
  int total = 1,
  int totalPages = 1,
  String sourceKey = _sourceKey,
  String fileId = 'file-1',
  String name = 'guide.pdf',
}) {
  return IndexedFilePage(
    items: [
      IndexedFile(
        sourceKey: sourceKey,
        fileId: fileId,
        path: 'C:\\docs\\$name',
        name: name,
        mimeType: 'application/pdf',
        modality: 'text',
        sizeBytes: 4096,
        modifiedAt: DateTime.utc(2026, 8, 10),
        recordCount: 4,
      ),
    ],
    page: page,
    pageSize: 20,
    total: total,
    totalPages: totalPages,
  );
}

const IndexedFilePage _emptyPage = IndexedFilePage(
  items: [],
  page: 1,
  pageSize: 20,
  total: 0,
  totalPages: 0,
);

IndexJob _completedJob({IndexJobStatus status = IndexJobStatus.completed}) {
  return IndexJob(
    jobId: 'job-1',
    status: status,
    result: const IndexingResult(
      parsedFiles: 2,
      indexedFiles: 1,
      indexedRecords: 4,
      skippedFiles: 0,
      failedFiles: 1,
      partialFiles: 0,
      unchangedFiles: 0,
      removedStaleRecords: 0,
      failures: [],
    ),
  );
}

IndexJob _job(IndexJobStatus status) {
  return IndexJob(jobId: 'job-1', status: status, result: null);
}

final class _PagePicker implements DirectoryPicker {
  @override
  bool isSupported = true;

  @override
  Future<String?> pickDirectory() async => null;
}

final class _PageService implements IndexLibraryService {
  final List<Object> pages = [];
  final List<IndexJob> reindexJobs = [];
  final List<IndexJob> fetchedJobs = [];
  final List<DeletedIndexedFile> removeResults = [];
  final List<String> reindexCalls = [];
  final List<String> removeCalls = [];

  @override
  Future<IndexedFilePage> fetchFiles({
    required int page,
    required int pageSize,
  }) async {
    final value = pages.removeAt(0);
    if (value is Future<IndexedFilePage>) return value;
    return value as IndexedFilePage;
  }

  @override
  Future<IndexJob> startIndexing(String directory) =>
      throw UnimplementedError();

  @override
  Future<IndexJob> fetchJob(String jobId) async => fetchedJobs.removeAt(0);

  @override
  Future<IndexFailureDetails> fetchFailures(String jobId) =>
      throw UnimplementedError();

  @override
  Future<IndexJob> reindex(String sourceKey) async {
    reindexCalls.add(sourceKey);
    return reindexJobs.removeAt(0);
  }

  @override
  Future<DeletedIndexedFile> remove(String sourceKey) async {
    removeCalls.add(sourceKey);
    return removeResults.removeAt(0);
  }
}
