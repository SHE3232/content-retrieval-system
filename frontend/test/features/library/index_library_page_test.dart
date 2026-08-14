import 'package:content_retrieval_app/core/platform/directory_picker.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_controller.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fakes.dart';

const _sourceKey =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

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
    expect(find.text('共 1 个文件'), findsOneWidget);
    expect(find.text('guide.pdf'), findsOneWidget);
    expect(find.text('application/pdf'), findsOneWidget);
    expect(find.textContaining('4 条记录'), findsOneWidget);

    await tester.tap(find.byTooltip('打开 guide.pdf'));
    await tester.pump();
    expect(launcher.paths, [r'C:\docs\guide.pdf']);

    await tester.tap(find.byTooltip('复制 guide.pdf 的路径'));
    await tester.pump();
    expect(clipboard.paths, [r'C:\docs\guide.pdf']);
    expect(find.text('路径已复制'), findsOneWidget);
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

    await tester.tap(find.byTooltip('重新索引 guide.pdf'));
    await tester.pumpAndSettle();
    expect(find.text('重新索引 guide.pdf？'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, '重新索引'));
    await tester.pumpAndSettle();
    expect(service.reindexCalls, [_sourceKey]);

    await tester.tap(find.byTooltip('从索引移除 guide.pdf'));
    await tester.pumpAndSettle();
    expect(find.text('不会删除磁盘上的原文件。'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, '从索引移除'));
    for (var attempt = 0; attempt < 10; attempt += 1) {
      await tester.pump(const Duration(milliseconds: 20));
      if (find.textContaining('已从索引移除').evaluate().isNotEmpty) break;
    }

    expect(service.removeCalls, [_sourceKey]);
    expect(find.textContaining('已从索引移除'), findsOneWidget);
    expect(find.text('索引库为空'), findsOneWidget);
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
      find.widgetWithText(FilledButton, '添加文件夹'),
    );
    expect(addButton.onPressed, isNull);
    expect(find.textContaining('请使用桌面版管理索引'), findsOneWidget);
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

    expect(find.textContaining('成功 1'), findsOneWidget);
    expect(find.textContaining('失败 1'), findsOneWidget);
    await tester.tap(find.text('查看失败详情'));
    await tester.pumpAndSettle();
    expect(find.textContaining('broken.pdf'), findsOneWidget);
    expect(find.textContaining('PARSE_FAILED'), findsOneWidget);
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
  });
}

Widget _app(
  IndexLibraryController controller, {
  FakeFileLauncher? fileLauncher,
  FakePathClipboard? pathClipboard,
}) {
  return MaterialApp(
    home: Scaffold(
      body: IndexLibraryPage(
        controller: controller,
        fileLauncher: fileLauncher ?? FakeFileLauncher(),
        pathClipboard: pathClipboard ?? FakePathClipboard(),
      ),
    ),
  );
}

IndexedFilePage _page() {
  return IndexedFilePage(
    items: [
      IndexedFile(
        sourceKey: _sourceKey,
        fileId: 'file-1',
        path: r'C:\docs\guide.pdf',
        name: 'guide.pdf',
        mimeType: 'application/pdf',
        modality: 'text',
        sizeBytes: 4096,
        modifiedAt: DateTime.utc(2026, 8, 10),
        recordCount: 4,
      ),
    ],
    page: 1,
    pageSize: 20,
    total: 1,
    totalPages: 1,
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

final class _PagePicker implements DirectoryPicker {
  @override
  bool isSupported = true;

  @override
  Future<String?> pickDirectory() async => null;
}

final class _PageService implements IndexLibraryService {
  final List<IndexedFilePage> pages = [];
  final List<IndexJob> reindexJobs = [];
  final List<DeletedIndexedFile> removeResults = [];
  final List<String> reindexCalls = [];
  final List<String> removeCalls = [];

  @override
  Future<IndexedFilePage> fetchFiles({
    required int page,
    required int pageSize,
  }) async => pages.removeAt(0);

  @override
  Future<IndexJob> startIndexing(String directory) =>
      throw UnimplementedError();

  @override
  Future<IndexJob> fetchJob(String jobId) => throw UnimplementedError();

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
