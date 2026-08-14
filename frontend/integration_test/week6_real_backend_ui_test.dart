import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:content_retrieval_app/core/api/http_json_transport.dart';
import 'package:content_retrieval_app/core/platform/directory_picker.dart';
import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/features/library/data/index_library_api_client.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_controller.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_page.dart';
import 'package:content_retrieval_app/features/search/data/search_api_client.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:content_retrieval_app/features/search/presentation/search_controller.dart';
import 'package:content_retrieval_app/features/search/presentation/search_page.dart';
import 'package:content_retrieval_app/features/status/backend_status_client.dart';
import 'package:content_retrieval_app/features/status/backend_status_controller.dart';
import 'package:content_retrieval_app/features/status/backend_status_models.dart';
import 'package:flutter/material.dart' hide SearchController;
import 'package:integration_test/integration_test.dart';
import 'package:flutter_test/flutter_test.dart';

const _baseUrl = String.fromEnvironment('WEEK6_BASE_URL');
const _fixtureRoot = String.fromEnvironment('WEEK6_FIXTURE_ROOT');
const _output = String.fromEnvironment('WEEK6_OUTPUT');

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'Flutter UI completes the Week 6 workflow against a real backend',
    (tester) async {
      expect(_baseUrl, isNotEmpty, reason: 'WEEK6_BASE_URL is required');
      expect(
        _fixtureRoot,
        isNotEmpty,
        reason: 'WEEK6_FIXTURE_ROOT is required',
      );
      expect(_output, isNotEmpty, reason: 'WEEK6_OUTPUT is required');
      await tester.binding.setSurfaceSize(const Size(1280, 900));

      final operations = <String, bool>{};
      final transport = HttpJsonTransport(
        baseUri: Uri.parse(_baseUrl),
        timeout: const Duration(minutes: 3),
      );
      final libraryService = IndexLibraryApiClient(transport);
      final picker = _FixturePicker(_fixtureRoot);
      final launcher = _RecordingLauncher();
      final clipboard = _RecordingClipboard();
      final library = IndexLibraryController(
        service: libraryService,
        directoryPicker: picker,
        pollInterval: const Duration(milliseconds: 100),
      );
      final search = SearchController(SearchApiClient(transport));
      final status = BackendStatusController(
        BackendStatusClient(transport),
        pollInterval: const Duration(minutes: 5),
      );

      try {
        await status.start();
        expect(status.state, BackendConnectionState.online);
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: IndexLibraryPage(
                controller: library,
                fileLauncher: launcher,
                pathClipboard: clipboard,
              ),
            ),
          ),
        );
        await _pumpUntil(
          tester,
          () => library.state != LibraryViewState.loading,
        );
        await tester.tap(find.widgetWithText(FilledButton, '添加文件夹'));
        operations['add_directory'] = picker.calls == 1;
        await _pumpUntil(
          tester,
          () => !library.isMutationInProgress && library.files.length == 5,
          timeout: const Duration(minutes: 8),
        );
        operations['poll_indexing'] = library.files.length == 5;

        final indexedTarget = library.files.first;
        await tester.ensureVisible(find.text(indexedTarget.name));
        await tester.tap(find.byTooltip('打开 ${indexedTarget.name}'));
        await tester.pump();
        await tester.tap(find.byTooltip('复制 ${indexedTarget.name} 的路径'));
        await tester.pump();
        operations['open_file'] = launcher.paths.contains(indexedTarget.path);
        operations['copy_path'] = clipboard.paths.contains(indexedTarget.path);

        await tester.tap(find.byTooltip('重新索引 ${indexedTarget.name}'));
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(FilledButton, '重新索引'));
        await _pumpUntil(
          tester,
          () => !library.isMutationInProgress,
          timeout: const Duration(minutes: 8),
        );
        operations['reindex'] = library.errorMessage == null;

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: SearchPage(
                controller: search,
                statusController: status,
                fileLauncher: launcher,
                pathClipboard: clipboard,
              ),
            ),
          ),
        );
        await tester.enterText(
          find.byKey(const Key('search-query-field')),
          'controlled fixture',
        );
        search.setMode(RetrievalMode.exact);
        await tester.tap(find.byKey(const Key('search-submit-button')));
        await _pumpUntil(tester, () => search.state == SearchViewState.success);
        operations['keyword_search'] = search.response!.hits.isNotEmpty;

        _setOnlyChannel(search, SearchChannel.textSemantic);
        search.setQuery('controlled local fixture notes');
        await search.submit();
        await tester.pump();
        operations['text_semantic_search'] = search.response!.hits.isNotEmpty;

        _setOnlyChannel(search, SearchChannel.imageSemantic);
        search.setQuery('a simple red apple on a white background');
        await search.submit();
        await tester.pump();
        operations['image_semantic_search'] = search.response!.hits.isNotEmpty;

        search.setMode(RetrievalMode.hybrid);
        search.setQuery('controlled fixture');
        await search.submit();
        await tester.pump();
        operations['hybrid_search'] = search.response!.hits.isNotEmpty;

        for (final type in SearchContentType.values) {
          if (type != SearchContentType.textFiles &&
              search.contentTypes.contains(type)) {
            search.toggleContentType(type);
          }
        }
        search.setMode(RetrievalMode.exact);
        await search.submit();
        await tester.pump();
        operations['filter_results'] =
            search.response!.hits.isNotEmpty &&
            search.response!.hits.every((hit) => hit.mimeType == 'text/plain');

        final hit = search.response!.hits.first;
        await tester.ensureVisible(find.byKey(Key('open-${hit.fileId}')));
        await tester.tap(find.byKey(Key('open-${hit.fileId}')));
        await tester.pump();
        await tester.tap(find.byKey(Key('copy-path-${hit.fileId}')));
        await tester.pump();
        operations['open_file'] =
            operations['open_file']! && launcher.paths.contains(hit.path);
        operations['copy_path'] =
            operations['copy_path']! && clipboard.paths.contains(hit.path);

        final unreachable = HttpJsonTransport(
          baseUri: Uri.parse('http://127.0.0.1:1'),
          timeout: const Duration(seconds: 1),
        );
        final offlineStatus = BackendStatusController(
          BackendStatusClient(unreachable),
        );
        await offlineStatus.start();
        await status.refresh();
        operations['disconnect_recovery'] =
            offlineStatus.state == BackendConnectionState.offline &&
            status.state == BackendConnectionState.online;
        offlineStatus.dispose();
        unreachable.close();

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: IndexLibraryPage(
                controller: library,
                fileLauncher: launcher,
                pathClipboard: clipboard,
              ),
            ),
          ),
        );
        await library.load();
        await tester.pump();
        final removeTarget = library.files.first;
        await tester.ensureVisible(find.text(removeTarget.name));
        await tester.tap(find.byTooltip('从索引移除 ${removeTarget.name}'));
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(FilledButton, '从索引移除'));
        await _pumpUntil(tester, () => !library.isMutationInProgress);
        operations['delete_index'] = library.total == 4;

        const required = <String>{
          'add_directory',
          'poll_indexing',
          'keyword_search',
          'text_semantic_search',
          'image_semantic_search',
          'hybrid_search',
          'filter_results',
          'copy_path',
          'open_file',
          'delete_index',
          'reindex',
          'disconnect_recovery',
        };
        expect(operations.keys.toSet(), containsAll(required));
        expect(operations.values, everyElement(isTrue));
        final evidence = <String, Object>{
          'status': 'PASS',
          'real_backend': true,
          'base_url': _baseUrl,
          'fixture_root': _fixtureRoot,
          'operations': operations,
          'indexed_file_count': 5,
          'generated_at': DateTime.now().toUtc().toIso8601String(),
        };
        final output = File(_output);
        await output.parent.create(recursive: true);
        await output.writeAsString(
          const JsonEncoder.withIndent('  ').convert(evidence),
          flush: true,
        );
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        library.dispose();
        search.dispose();
        status.dispose();
        transport.close();
      }
    },
    timeout: const Timeout(Duration(minutes: 15)),
  );
}

void _setOnlyChannel(SearchController controller, SearchChannel wanted) {
  controller.setMode(RetrievalMode.hybrid);
  for (final channel in SearchChannel.values) {
    if (channel != wanted && controller.channels.contains(channel)) {
      controller.toggleChannel(channel);
    }
  }
}

Future<void> _pumpUntil(
  WidgetTester tester,
  bool Function() predicate, {
  Duration timeout = const Duration(minutes: 3),
}) async {
  final deadline = DateTime.now().add(timeout);
  while (!predicate()) {
    if (DateTime.now().isAfter(deadline)) {
      throw TimeoutException('condition was not met within $timeout');
    }
    await Future<void>.delayed(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));
  }
  await tester.pump();
}

final class _FixturePicker implements DirectoryPicker {
  _FixturePicker(this.path);

  final String path;
  int calls = 0;

  @override
  bool get isSupported => true;

  @override
  Future<String?> pickDirectory() async {
    calls += 1;
    return path;
  }
}

final class _RecordingLauncher implements FileLauncher {
  final List<String> paths = <String>[];

  @override
  Future<void> open(String path) async => paths.add(path);
}

final class _RecordingClipboard implements PathClipboard {
  final List<String> paths = <String>[];

  @override
  Future<void> copy(String path) async => paths.add(path);
}
