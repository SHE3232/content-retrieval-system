import 'dart:async';

import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/platform/directory_picker.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_controller.dart';
import 'package:flutter_test/flutter_test.dart';

const _sourceKey =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

void main() {
  test('load publishes the catalog and pagination', () async {
    final service = _FakeLibraryService()..pages.add(_page(page: 2));
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _FakeDirectoryPicker(),
      pageSize: 25,
    );
    addTearDown(controller.dispose);

    await controller.load(page: 2);

    expect(controller.state, LibraryViewState.ready);
    expect(controller.files.single.name, 'guide.pdf');
    expect(controller.page, 2);
    expect(controller.totalPages, 3);
    expect(service.pageCalls.single, (page: 2, pageSize: 25));
  });

  test('cancelled directory selection performs no API call', () async {
    final picker = _FakeDirectoryPicker()..results.add(null);
    final controller = IndexLibraryController(
      service: _FakeLibraryService(),
      directoryPicker: picker,
    );
    addTearDown(controller.dispose);

    await controller.selectDirectoryAndStart();

    expect(picker.calls, 1);
    expect(controller.activeJob, isNull);
    expect(controller.isMutationInProgress, isFalse);
  });

  test(
    'unsupported picker message names supported desktop platforms',
    () async {
      final picker = _FakeDirectoryPicker()..isSupported = false;
      final controller = IndexLibraryController(
        service: _FakeLibraryService(),
        directoryPicker: picker,
      );
      addTearDown(controller.dispose);

      await controller.selectDirectoryAndStart();

      expect(
        controller.errorMessage,
        '当前平台不支持添加本地资料文件夹，请使用 Windows、macOS 或 Linux 桌面版。',
      );
      expect(controller.errorMessage, isNot(contains('后端')));
    },
  );

  test('service errors use local retrieval service language', () async {
    final service = _FakeLibraryService()
      ..reindexResults.add(
        const ApiException(
          ApiErrorKind.rejected,
          'raw',
          code: 'SERVICE_UNAVAILABLE',
        ),
      );
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _FakeDirectoryPicker(),
    );
    addTearDown(controller.dispose);

    await controller.reindex(_sourceKey);

    expect(controller.errorMessage, '本地检索服务暂时不可用，请检查运行状态后重新尝试。');
    expect(controller.errorMessage, isNot(contains('后端')));
  });

  test('running job polls to completion and refreshes page one', () async {
    final service = _FakeLibraryService()
      ..startedJobs.add(_job(IndexJobStatus.queued))
      ..fetchedJobs.add(_job(IndexJobStatus.running))
      ..fetchedJobs.add(
        _job(IndexJobStatus.completed, result: _result(indexedFiles: 1)),
      )
      ..pages.add(_page(page: 1));
    final picker = _FakeDirectoryPicker()..results.add(r'C:\docs');
    final waits = <Completer<void>>[];
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: picker,
      wait: (_) {
        final completer = Completer<void>();
        waits.add(completer);
        return completer.future;
      },
    );
    addTearDown(controller.dispose);

    await controller.selectDirectoryAndStart();
    expect(controller.activeJob?.status, IndexJobStatus.queued);
    expect(controller.isMutationInProgress, isTrue);

    waits.removeAt(0).complete();
    await _flush();
    expect(controller.activeJob?.status, IndexJobStatus.running);

    waits.removeAt(0).complete();
    await _flush();
    expect(controller.activeJob?.status, IndexJobStatus.completed);
    expect(controller.isMutationInProgress, isFalse);
    expect(controller.files.single.name, 'guide.pdf');
    expect(service.pageCalls.single.page, 1);
  });

  test('failed job loads structured failure details', () async {
    final service = _FakeLibraryService()
      ..startedJobs.add(_job(IndexJobStatus.queued))
      ..fetchedJobs.add(_job(IndexJobStatus.failed))
      ..failureDetails.add(
        const IndexFailureDetails(
          jobId: 'job-1',
          status: IndexJobStatus.failed,
          total: 0,
          failures: [],
          error: IndexJobError(
            code: 'INDEXING_JOB_FAILED',
            message: 'Indexing job failed unexpectedly',
            retryable: true,
          ),
        ),
      )
      ..pages.add(_page(page: 1));
    final waits = <Completer<void>>[];
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _FakeDirectoryPicker()..results.add(r'C:\docs'),
      wait: (_) {
        final completer = Completer<void>();
        waits.add(completer);
        return completer.future;
      },
    );
    addTearDown(controller.dispose);

    await controller.selectDirectoryAndStart();
    waits.single.complete();
    await _flush();

    expect(controller.failureDetails?.error?.code, 'INDEXING_JOB_FAILED');
    expect(controller.errorMessage, '任务未完成，请重新尝试；若问题持续，请检查本地检索服务。');
    expect(controller.isMutationInProgress, isFalse);
  });

  test(
    'mutation conflict retains files and maps a stable action message',
    () async {
      final service = _FakeLibraryService()
        ..pages.add(_page(page: 1))
        ..reindexResults.add(
          const ApiException(
            ApiErrorKind.rejected,
            'raw backend message',
            code: 'INDEX_MUTATION_CONFLICT',
            statusCode: 409,
          ),
        );
      final controller = IndexLibraryController(
        service: service,
        directoryPicker: _FakeDirectoryPicker(),
      );
      addTearDown(controller.dispose);
      await controller.load();

      await controller.reindex(_sourceKey);

      expect(controller.files.single.name, 'guide.pdf');
      expect(controller.errorMessage, '另一项索引操作正在进行，请稍后重试。');
      expect(controller.isMutationInProgress, isFalse);
    },
  );

  test('successful removal refreshes a valid previous page', () async {
    final service = _FakeLibraryService()
      ..pages.add(_page(page: 2, total: 26, totalPages: 2))
      ..removeResults.add(
        const DeletedIndexedFile(sourceKey: _sourceKey, deletedRecords: 4),
      )
      ..pages.add(_page(page: 1, total: 25, totalPages: 1));
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _FakeDirectoryPicker(),
      pageSize: 25,
    );
    addTearDown(controller.dispose);
    await controller.load(page: 2);

    final deleted = await controller.remove(_sourceKey);

    expect(deleted?.deletedRecords, 4);
    expect(controller.page, 1);
    expect(service.pageCalls.last.page, 1);
  });

  test(
    'refresh blocks every mutation until its delayed response settles',
    () async {
      final delayedPage = Completer<IndexedFilePage>();
      final service = _FakeLibraryService()
        ..pages.add(delayedPage.future)
        ..startedJobs.add(_job(IndexJobStatus.queued));
      final picker = _FakeDirectoryPicker()..results.add(r'C:\docs');
      final controller = IndexLibraryController(
        service: service,
        directoryPicker: picker,
        wait: (_) => Completer<void>().future,
      );
      addTearDown(controller.dispose);

      final refresh = controller.load();
      expect(controller.isRefreshing, isTrue);

      await controller.selectDirectoryAndStart();
      await controller.reindex(_sourceKey);
      final deleted = await controller.remove(_sourceKey);

      expect(picker.calls, 0);
      expect(service.startCalls, 0);
      expect(service.reindexCalls, 0);
      expect(service.removeCalls, 0);
      expect(deleted, isNull);

      delayedPage.complete(_page(page: 1));
      await refresh;
    },
  );

  test('mutation blocks refresh and competing mutations', () async {
    final delayedJob = Completer<IndexJob>();
    final delayedPage = Completer<IndexedFilePage>();
    final service = _FakeLibraryService()
      ..reindexResults.add(delayedJob.future)
      ..pages.add(delayedPage.future);
    final picker = _FakeDirectoryPicker()..results.add(r'C:\docs');
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: picker,
      wait: (_) => Completer<void>().future,
    );
    addTearDown(controller.dispose);

    final mutation = controller.reindex(_sourceKey);
    expect(controller.isMutationInProgress, isTrue);

    final refresh = controller.refresh();
    await controller.selectDirectoryAndStart();
    final deleted = await controller.remove(_sourceKey);

    expect(service.pageCalls, isEmpty);
    expect(service.reindexCalls, 1);
    expect(service.startCalls, 0);
    expect(service.removeCalls, 0);
    expect(picker.calls, 0);
    expect(deleted, isNull);

    delayedPage.complete(_page(page: 1));
    await refresh;
    delayedJob.complete(_job(IndexJobStatus.queued));
    await mutation;
  });

  test('stale refresh cannot restore a file after removal', () async {
    final staleRefresh = Completer<IndexedFilePage>();
    final service = _FakeLibraryService()
      ..pages.add(_page(page: 1, total: 1, totalPages: 1))
      ..pages.add(staleRefresh.future)
      ..removeResults.add(
        const DeletedIndexedFile(sourceKey: _sourceKey, deletedRecords: 4),
      )
      ..pages.add(
        const IndexedFilePage(
          items: [],
          page: 1,
          pageSize: 20,
          total: 0,
          totalPages: 0,
        ),
      );
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _FakeDirectoryPicker(),
    );
    addTearDown(controller.dispose);
    await controller.load();

    final refresh = controller.refresh();
    expect(await controller.remove(_sourceKey), isNull);
    expect(service.removeCalls, 0);

    staleRefresh.complete(_page(page: 1, total: 1, totalPages: 1));
    await refresh;
    expect(controller.files, hasLength(1));

    expect(await controller.remove(_sourceKey), isNotNull);
    expect(controller.files, isEmpty);
    expect(service.removeCalls, 1);
  });

  test('dispose ignores a late page response', () async {
    final page = Completer<IndexedFilePage>();
    final service = _FakeLibraryService()..pages.add(page.future);
    final controller = IndexLibraryController(
      service: service,
      directoryPicker: _FakeDirectoryPicker(),
    );
    var notifications = 0;
    controller.addListener(() => notifications += 1);

    final load = controller.load();
    controller.dispose();
    page.complete(_page(page: 1));
    await load;

    expect(notifications, 1);
  });
}

Future<void> _flush() async {
  await Future<void>.delayed(Duration.zero);
  await Future<void>.delayed(Duration.zero);
  await Future<void>.delayed(Duration.zero);
}

IndexedFilePage _page({required int page, int total = 51, int totalPages = 3}) {
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
        modifiedAt: DateTime.utc(2026, 8, 10, 10),
        recordCount: 4,
      ),
    ],
    page: page,
    pageSize: 25,
    total: total,
    totalPages: totalPages,
  );
}

IndexJob _job(IndexJobStatus status, {IndexingResult? result}) {
  return IndexJob(jobId: 'job-1', status: status, result: result);
}

IndexingResult _result({required int indexedFiles}) {
  return IndexingResult(
    parsedFiles: indexedFiles,
    indexedFiles: indexedFiles,
    indexedRecords: indexedFiles,
    skippedFiles: 0,
    failedFiles: 0,
    partialFiles: 0,
    unchangedFiles: 0,
    removedStaleRecords: 0,
    failures: const [],
  );
}

final class _FakeDirectoryPicker implements DirectoryPicker {
  final List<String?> results = <String?>[];
  int calls = 0;

  @override
  bool isSupported = true;

  @override
  Future<String?> pickDirectory() async {
    calls += 1;
    return results.isEmpty ? null : results.removeAt(0);
  }
}

final class _FakeLibraryService implements IndexLibraryService {
  final List<Object> pages = <Object>[];
  final List<IndexJob> startedJobs = <IndexJob>[];
  final List<IndexJob> fetchedJobs = <IndexJob>[];
  final List<IndexFailureDetails> failureDetails = <IndexFailureDetails>[];
  final List<Object> reindexResults = <Object>[];
  final List<Object> removeResults = <Object>[];
  final List<({int page, int pageSize})> pageCalls = [];
  int startCalls = 0;
  int reindexCalls = 0;
  int removeCalls = 0;

  @override
  Future<IndexedFilePage> fetchFiles({
    required int page,
    required int pageSize,
  }) async {
    pageCalls.add((page: page, pageSize: pageSize));
    final value = pages.removeAt(0);
    if (value is Future<IndexedFilePage>) return value;
    return value as IndexedFilePage;
  }

  @override
  Future<IndexJob> startIndexing(String directory) async {
    startCalls += 1;
    return startedJobs.removeAt(0);
  }

  @override
  Future<IndexJob> fetchJob(String jobId) async {
    return fetchedJobs.removeAt(0);
  }

  @override
  Future<IndexFailureDetails> fetchFailures(String jobId) async {
    return failureDetails.removeAt(0);
  }

  @override
  Future<IndexJob> reindex(String sourceKey) async {
    reindexCalls += 1;
    final value = reindexResults.removeAt(0);
    if (value is ApiException) throw value;
    if (value is Future<IndexJob>) return value;
    return value as IndexJob;
  }

  @override
  Future<DeletedIndexedFile> remove(String sourceKey) async {
    removeCalls += 1;
    final value = removeResults.removeAt(0);
    if (value is ApiException) throw value;
    return value as DeletedIndexedFile;
  }
}
