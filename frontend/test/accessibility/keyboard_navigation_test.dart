import 'dart:async';

import 'package:content_retrieval_app/core/platform/directory_picker.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_controller.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_page.dart';
import 'package:content_retrieval_app/features/shell/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

const _sourceKey =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

void main() {
  testWidgets('Ctrl+1 through Ctrl+3 switch destinations and preserve state', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(_app());
    await tester.pump();

    await _controlShortcut(tester, LogicalKeyboardKey.digit2);
    await tester.pump();
    expect(find.text('LIBRARY_PAGE'), findsOneWidget);

    await _controlShortcut(tester, LogicalKeyboardKey.digit3);
    await tester.pump();
    expect(find.text('SETTINGS_PAGE'), findsOneWidget);

    await _controlShortcut(tester, LogicalKeyboardKey.digit1);
    await tester.pump();
    expect(find.text('SEARCH_PAGE'), findsOneWidget);
  });

  testWidgets('F5 invokes only the current destination refresh action', (
    tester,
  ) async {
    var searchRefreshes = 0;
    var libraryRefreshes = 0;
    await tester.pumpWidget(
      _app(
        onRefreshSearch: () => searchRefreshes += 1,
        onRefreshLibrary: () => libraryRefreshes += 1,
      ),
    );
    await tester.pump();

    await tester.sendKeyEvent(LogicalKeyboardKey.f5);
    expect(searchRefreshes, 1);
    expect(libraryRefreshes, 0);

    await _controlShortcut(tester, LogicalKeyboardKey.digit2);
    await tester.sendKeyEvent(LogicalKeyboardKey.f5);
    expect(searchRefreshes, 1);
    expect(libraryRefreshes, 1);

    await _controlShortcut(tester, LogicalKeyboardKey.digit3);
    await tester.sendKeyEvent(LogicalKeyboardKey.f5);
    expect(searchRefreshes, 1);
    expect(libraryRefreshes, 1);
  });

  testWidgets('hidden library cannot reclaim focus after a delayed job', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final waits = <Completer<void>>[];
    final service = _ShellLibraryService()
      ..pages.add(_libraryPage)
      ..reindexJobs.add(_job(IndexJobStatus.queued))
      ..fetchedJobs.add(_job(IndexJobStatus.completed))
      ..pages.add(_libraryPage);
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: const UnsupportedDirectoryPicker(),
      wait: (_) {
        final wait = Completer<void>();
        waits.add(wait);
        return wait.future;
      },
    );
    final searchFocus = FocusNode(debugLabel: 'visible-search-action');
    addTearDown(controller.dispose);
    addTearDown(searchFocus.dispose);
    await controller.load();

    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(
          searchPage: Center(
            child: FilledButton(
              focusNode: searchFocus,
              onPressed: () {},
              child: const Text('搜索页操作'),
            ),
          ),
          indexLibraryPage: IndexLibraryPage(
            controller: controller,
            fileLauncher: FakeFileLauncher(),
            pathClipboard: FakePathClipboard(),
          ),
          settingsPage: const Text('SETTINGS_PAGE'),
        ),
      ),
    );
    await _controlShortcut(tester, LogicalKeyboardKey.digit2);
    await tester.pump();

    await tester.tap(find.byKey(const Key('more-actions-file-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('重新索引文件'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '重新索引文件'));
    await tester.pump();
    expect(controller.activeJob?.status, IndexJobStatus.queued);

    await _controlShortcut(tester, LogicalKeyboardKey.digit1);
    await tester.pump();
    searchFocus.requestFocus();
    await tester.pump();
    expect(searchFocus.hasFocus, isTrue);

    waits.single.complete();
    await tester.pumpAndSettle();

    expect(searchFocus.hasFocus, isTrue);
    final hiddenTrigger = tester.widget<FocusableActionDetector>(
      find.byKey(const Key('more-actions-file-1'), skipOffstage: false),
    );
    expect(hiddenTrigger.focusNode!.hasFocus, isFalse);
    expect(hiddenTrigger.focusNode!.canRequestFocus, isFalse);

    await _controlShortcut(tester, LogicalKeyboardKey.digit2);
    await tester.pumpAndSettle();
    expect(
      FocusManager.instance.primaryFocus?.debugLabel,
      'more-actions-file-1',
    );
  });
}

Widget _app({VoidCallback? onRefreshSearch, VoidCallback? onRefreshLibrary}) {
  return MaterialApp(
    home: AppShell(
      searchPage: const Text('SEARCH_PAGE'),
      indexLibraryPage: const Text('LIBRARY_PAGE'),
      settingsPage: const Text('SETTINGS_PAGE'),
      onRefreshSearch: onRefreshSearch,
      onRefreshLibrary: onRefreshLibrary,
    ),
  );
}

Future<void> _controlShortcut(
  WidgetTester tester,
  LogicalKeyboardKey key,
) async {
  await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
  await tester.sendKeyEvent(key);
  await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
}

IndexJob _job(IndexJobStatus status) {
  return IndexJob(jobId: 'job-1', status: status, result: null);
}

final _libraryPage = IndexedFilePage(
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

final class _ShellLibraryService implements IndexLibraryService {
  final List<IndexedFilePage> pages = [];
  final List<IndexJob> reindexJobs = [];
  final List<IndexJob> fetchedJobs = [];

  @override
  Future<IndexedFilePage> fetchFiles({
    required int page,
    required int pageSize,
  }) async => pages.removeAt(0);

  @override
  Future<IndexJob> reindex(String sourceKey) async => reindexJobs.removeAt(0);

  @override
  Future<IndexJob> fetchJob(String jobId) async => fetchedJobs.removeAt(0);

  @override
  Future<IndexJob> startIndexing(String directory) =>
      throw UnimplementedError();

  @override
  Future<IndexFailureDetails> fetchFailures(String jobId) =>
      throw UnimplementedError();

  @override
  Future<DeletedIndexedFile> remove(String sourceKey) =>
      throw UnimplementedError();
}
