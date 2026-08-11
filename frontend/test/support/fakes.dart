import 'dart:async';

import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:content_retrieval_app/features/status/backend_status_models.dart';

final class CapturedGet {
  const CapturedGet(this.path);

  final String path;
}

final class CapturedPost {
  const CapturedPost(this.path, this.body);

  final String path;
  final Map<String, Object?> body;
}

final class FakeJsonTransport implements JsonTransport {
  final List<JsonResponse> getResponses = <JsonResponse>[];
  final List<JsonResponse> postResponses = <JsonResponse>[];
  final List<CapturedGet> gets = <CapturedGet>[];
  final List<CapturedPost> posts = <CapturedPost>[];

  bool isClosed = false;

  @override
  Future<JsonResponse> get(String path) async {
    gets.add(CapturedGet(path));
    if (getResponses.isEmpty) {
      throw StateError('No queued GET response for $path');
    }
    return getResponses.removeAt(0);
  }

  @override
  Future<JsonResponse> post(
    String path, {
    required Map<String, Object?> body,
  }) async {
    posts.add(CapturedPost(path, Map<String, Object?>.unmodifiable(body)));
    if (postResponses.isEmpty) {
      throw StateError('No queued POST response for $path');
    }
    return postResponses.removeAt(0);
  }

  @override
  void close() {
    isClosed = true;
  }
}

final class FakeBackendStatusClient implements BackendStatusApi {
  final List<FutureOr<bool>> readyResults = <FutureOr<bool>>[];
  final List<FutureOr<IndexStats>> statsResults = <FutureOr<IndexStats>>[];
  final List<ApiException> readyErrors = <ApiException>[];
  final List<ApiException> statsErrors = <ApiException>[];

  int readyCalls = 0;
  int statsCalls = 0;

  @override
  Future<bool> isReady() async {
    readyCalls += 1;
    if (readyErrors.isNotEmpty) {
      throw readyErrors.removeAt(0);
    }
    if (readyResults.isEmpty) {
      throw StateError('No queued readiness result');
    }
    return readyResults.removeAt(0);
  }

  @override
  Future<IndexStats> fetchStats() async {
    statsCalls += 1;
    if (statsErrors.isNotEmpty) {
      throw statsErrors.removeAt(0);
    }
    if (statsResults.isEmpty) {
      throw StateError('No queued stats result');
    }
    return statsResults.removeAt(0);
  }
}

final class FakeSearchService implements SearchService {
  final List<Object> results = <Object>[];
  final List<SearchCriteria> calls = <SearchCriteria>[];

  @override
  Future<SearchResponse> search(SearchCriteria criteria) async {
    calls.add(criteria);
    if (results.isEmpty) {
      throw StateError('No queued search result');
    }

    final result = results.removeAt(0);
    if (result is ApiException) {
      throw result;
    }
    if (result is SearchResponse) {
      return result;
    }
    if (result is Future<SearchResponse>) {
      return result;
    }
    throw StateError('Unsupported search result: ${result.runtimeType}');
  }
}

final class FakeFileLauncher implements FileLauncher {
  final List<String> paths = <String>[];
  final List<FileLaunchException?> results = <FileLaunchException?>[];

  int get calls => paths.length;

  @override
  Future<void> open(String path) async {
    paths.add(path);
    if (results.isEmpty) {
      return;
    }
    final result = results.removeAt(0);
    if (result != null) {
      throw result;
    }
  }
}

final class FakePathClipboard implements PathClipboard {
  final List<String> paths = <String>[];
  final List<FileLaunchException?> results = <FileLaunchException?>[];

  int get calls => paths.length;

  @override
  Future<void> copy(String path) async {
    paths.add(path);
    if (results.isEmpty) {
      return;
    }
    final result = results.removeAt(0);
    if (result != null) {
      throw result;
    }
  }
}
