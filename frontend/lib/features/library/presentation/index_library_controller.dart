import 'dart:async';

import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/platform/directory_picker.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:flutter/foundation.dart';

enum LibraryViewState { initial, loading, ready, empty, failure }

typedef WaitForPoll = Future<void> Function(Duration duration);

final class IndexLibraryController extends ChangeNotifier {
  IndexLibraryController({
    required this.service,
    required this.directoryPicker,
    this.pageSize = 20,
    this.pollInterval = const Duration(seconds: 2),
    WaitForPoll? wait,
  }) : _wait = wait ?? Future<void>.delayed;

  final IndexLibraryService service;
  final DirectoryPicker directoryPicker;
  final int pageSize;
  final Duration pollInterval;
  final WaitForPoll _wait;

  LibraryViewState state = LibraryViewState.initial;
  List<IndexedFile> files = const <IndexedFile>[];
  int page = 1;
  int total = 0;
  int totalPages = 0;
  bool isRefreshing = false;
  bool isMutationInProgress = false;
  IndexJob? activeJob;
  IndexFailureDetails? failureDetails;
  String? errorMessage;
  String? successMessage;

  bool _disposed = false;
  int _pollGeneration = 0;

  bool get isBusy => isRefreshing || isMutationInProgress;

  Future<void> load({int page = 1, bool preserveError = false}) async {
    if (_disposed || isBusy) return;
    isRefreshing = true;
    if (!preserveError) errorMessage = null;
    if (files.isEmpty) state = LibraryViewState.loading;
    _notify();

    try {
      final result = await service.fetchFiles(page: page, pageSize: pageSize);
      if (_disposed) return;
      files = List<IndexedFile>.unmodifiable(result.items);
      this.page = result.page;
      total = result.total;
      totalPages = result.totalPages;
      state = files.isEmpty ? LibraryViewState.empty : LibraryViewState.ready;
    } on ApiException catch (error) {
      if (_disposed) return;
      errorMessage = _messageFor(error);
      if (files.isEmpty) state = LibraryViewState.failure;
    } finally {
      isRefreshing = false;
      _notify();
    }
  }

  Future<void> refresh() => load(page: page);

  Future<void> nextPage() {
    if (page >= totalPages) return Future<void>.value();
    return load(page: page + 1);
  }

  Future<void> previousPage() {
    if (page <= 1) return Future<void>.value();
    return load(page: page - 1);
  }

  Future<void> selectDirectoryAndStart() async {
    if (_disposed || isBusy) return;
    if (!directoryPicker.isSupported) {
      errorMessage = '当前平台不支持添加本地资料文件夹，请使用 Windows、macOS 或 Linux 桌面版。';
      _notify();
      return;
    }

    if (!_beginMutation()) return;
    String? directory;
    try {
      directory = await directoryPicker.pickDirectory();
    } catch (_) {
      if (!_disposed) {
        isMutationInProgress = false;
        _notify();
      }
      rethrow;
    }
    if (_disposed) return;
    if (directory == null || directory.trim().isEmpty) {
      isMutationInProgress = false;
      _notify();
      return;
    }

    final selectedDirectory = directory;
    await _startMutation(() => service.startIndexing(selectedDirectory));
  }

  Future<void> reindex(String sourceKey) async {
    if (!_beginMutation()) return;
    await _startMutation(() => service.reindex(sourceKey));
  }

  Future<DeletedIndexedFile?> remove(String sourceKey) async {
    if (!_beginMutation()) return null;
    try {
      final deleted = await service.remove(sourceKey);
      if (_disposed) return null;
      successMessage = '已从索引移除 ${deleted.deletedRecords} 条记录';
      final remaining = total > 0 ? total - 1 : 0;
      final previousPageWouldBeEmpty =
          page > 1 && remaining <= (page - 1) * pageSize;
      isMutationInProgress = false;
      await load(page: previousPageWouldBeEmpty ? page - 1 : page);
      return deleted;
    } on ApiException catch (error) {
      if (!_disposed) {
        errorMessage = _messageFor(error);
      }
      return null;
    } finally {
      isMutationInProgress = false;
      _notify();
    }
  }

  Future<void> _startMutation(Future<IndexJob> Function() start) async {
    failureDetails = null;
    _notify();
    try {
      final job = await start();
      if (_disposed) return;
      activeJob = job;
      _notify();
      if (job.status.isTerminal) {
        await _finishJob(job);
      } else {
        final generation = ++_pollGeneration;
        unawaited(_monitorJob(job.jobId, generation));
      }
    } on ApiException catch (error) {
      if (_disposed) return;
      errorMessage = _messageFor(error);
      isMutationInProgress = false;
      _notify();
    }
  }

  bool _beginMutation() {
    if (_disposed || isBusy) return false;
    isMutationInProgress = true;
    errorMessage = null;
    successMessage = null;
    _notify();
    return true;
  }

  Future<void> _monitorJob(String jobId, int generation) async {
    await _wait(pollInterval);
    if (_disposed || generation != _pollGeneration) return;
    try {
      final job = await service.fetchJob(jobId);
      if (_disposed || generation != _pollGeneration) return;
      activeJob = job;
      _notify();
      if (job.status.isTerminal) {
        await _finishJob(job);
      } else {
        unawaited(_monitorJob(jobId, generation));
      }
    } on ApiException catch (error) {
      if (_disposed || generation != _pollGeneration) return;
      errorMessage = _messageFor(error);
      isMutationInProgress = false;
      _notify();
    }
  }

  Future<void> _finishJob(IndexJob job) async {
    if (_disposed) return;
    if (job.status == IndexJobStatus.failed ||
        job.status == IndexJobStatus.completedWithErrors ||
        (job.result?.failures.isNotEmpty ?? false)) {
      try {
        failureDetails = await service.fetchFailures(job.jobId);
      } on ApiException catch (error) {
        errorMessage = _messageFor(error);
      }
    }
    if (job.status == IndexJobStatus.failed) {
      errorMessage = '任务未完成，请重新尝试；若问题持续，请检查本地检索服务。';
    }
    isMutationInProgress = false;
    _notify();
    await load(page: 1, preserveError: errorMessage != null);
  }

  String _messageFor(ApiException error) {
    return switch (error.code) {
      'INDEX_MUTATION_CONFLICT' => '另一项索引操作正在进行，请稍后重试。',
      'FILE_NOT_INDEXED' => '此文件已不在索引中，列表将刷新。',
      'SOURCE_FILE_NOT_FOUND' => '源文件不存在，无法重新索引。',
      'STORAGE_UNAVAILABLE' => '索引存储暂时不可用，请稍后刷新。',
      'RETRIEVAL_UNAVAILABLE' => '索引已更新，但搜索服务刷新失败，请重新启动本地检索服务后重试。',
      'SERVICE_UNAVAILABLE' => '本地检索服务暂时不可用，请检查运行状态后重新尝试。',
      _ when error.kind == ApiErrorKind.offline => '无法连接本地检索服务，请检查服务地址和运行状态。',
      _ when error.kind == ApiErrorKind.timeout => '请求用时过长，请重新尝试。',
      _ => '操作失败，请刷新后重试。',
    };
  }

  void clearError() {
    if (errorMessage == null || _disposed) return;
    errorMessage = null;
    _notify();
  }

  void clearSuccess() {
    if (successMessage == null || _disposed) return;
    successMessage = null;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    _pollGeneration += 1;
    super.dispose();
  }
}
