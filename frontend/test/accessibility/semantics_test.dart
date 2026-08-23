import 'package:content_retrieval_app/core/platform/directory_picker.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_controller.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_page.dart';
import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_controller.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_page.dart';
import 'package:content_retrieval_app/features/shell/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fakes.dart';

void main() {
  testWidgets('shell announces the current destination after shortcuts', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(
      const MaterialApp(
        home: AppShell(
          searchPage: Text('SEARCH_PAGE'),
          indexLibraryPage: Text('LIBRARY_PAGE'),
          settingsPage: Text('SETTINGS_PAGE'),
        ),
      ),
    );
    await tester.pump();

    expect(find.bySemanticsLabel(RegExp('当前页面：搜索')), findsOneWidget);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await tester.sendKeyEvent(LogicalKeyboardKey.digit2);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await tester.pump();
    expect(find.bySemanticsLabel(RegExp('当前页面：索引库')), findsOneWidget);
    semantics.dispose();
  });

  testWidgets('compact shell destinations meet Android tap target size', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    await tester.binding.setSurfaceSize(const Size(411, 914));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(useMaterial3: true),
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: const TextScaler.linear(2)),
          child: child!,
        ),
        home: const AppShell(
          searchPage: Text('SEARCH_PAGE'),
          indexLibraryPage: Text('LIBRARY_PAGE'),
          settingsPage: Text('SETTINGS_PAGE'),
        ),
      ),
    );
    await tester.pump();

    for (final label in ['搜索', '索引库', '设置']) {
      final node = tester.getSemantics(
        find.bySemanticsLabel(RegExp('^$label')),
      );
      expect(
        node.rect.height,
        greaterThanOrEqualTo(48),
        reason: '$label destination must expose a 48dp semantics target',
      );
    }
    semantics.dispose();
  });

  testWidgets('settings exposes headings, labels, values, and tap targets', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    final controller = SettingsController(
      SettingsRepository(_SemanticsSettingsStore()),
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.binding.setSurfaceSize(const Size(900, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: SettingsPage(controller: controller)),
      ),
    );

    expect(
      tester.getSemantics(find.text('设置')).flagsCollection.isHeader,
      isTrue,
    );
    expect(
      tester.getSemantics(find.text('外观与无障碍')).flagsCollection.isHeader,
      isTrue,
    );
    expect(find.bySemanticsLabel(RegExp('后端地址')), findsOneWidget);
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    semantics.dispose();
  });

  testWidgets('index library exposes a heading and labeled primary actions', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    final controller = IndexLibraryController(
      service: _EmptyLibraryService(),
      directoryPicker: const UnsupportedDirectoryPicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: IndexLibraryPage(
            controller: controller,
            fileLauncher: FakeFileLauncher(),
            pathClipboard: FakePathClipboard(),
            fileOpenSupported: false,
          ),
        ),
      ),
    );

    expect(
      tester.getSemantics(find.text('索引库')).flagsCollection.isHeader,
      isTrue,
    );
    expect(find.bySemanticsLabel('刷新索引库'), findsOneWidget);
    expect(find.bySemanticsLabel('添加资料文件夹'), findsOneWidget);
    semantics.dispose();
  });
}

final class _SemanticsSettingsStore implements SettingsStore {
  @override
  Future<SettingsStoreSnapshot> load() async => const SettingsStoreSnapshot(
    values: <String, Object?>{},
    storageRecovered: false,
  );

  @override
  Future<void> save(Map<String, Object?> values) async {}
}

final class _EmptyLibraryService implements IndexLibraryService {
  @override
  Future<IndexedFilePage> fetchFiles({
    required int page,
    required int pageSize,
  }) async => const IndexedFilePage(
    items: <IndexedFile>[],
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0,
  );

  @override
  Future<IndexFailureDetails> fetchFailures(String jobId) =>
      throw UnimplementedError();

  @override
  Future<IndexJob> fetchJob(String jobId) => throw UnimplementedError();

  @override
  Future<DeletedIndexedFile> remove(String sourceKey) =>
      throw UnimplementedError();

  @override
  Future<IndexJob> reindex(String sourceKey) => throw UnimplementedError();

  @override
  Future<IndexJob> startIndexing(String directory) =>
      throw UnimplementedError();
}
