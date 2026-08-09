# Flutter Search Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Material 3 Flutter desktop search workbench that monitors the local FastAPI backend, performs real filtered searches, renders complete result states, and safely opens or copies local result paths.

**Architecture:** Keep transport, backend status, search domain, search state, platform integration, and widgets behind small interfaces so each unit can be tested without a running backend. Compose them only in the application root, use `ChangeNotifier` for the two feature controllers, and keep the current FastAPI contracts unchanged.

**Tech Stack:** Flutter 3.44.6, Dart 3.12.2, Material 3, `dart:io` `HttpClient`, Flutter `Clipboard`, `flutter_test`, Windows desktop runner

---

## File map

- Modify: `frontend/lib/main.dart` - minimal application entry point.
- Create: `frontend/lib/app/content_retrieval_app.dart` - dependency composition and lifecycle.
- Create: `frontend/lib/app/app_theme.dart` - Material 3 light and dark themes.
- Create: `frontend/lib/core/api/api_exception.dart` - stable client-side API failures.
- Create: `frontend/lib/core/api/json_transport.dart` - injectable JSON transport contract.
- Create: `frontend/lib/core/api/io_json_transport.dart` - `HttpClient` transport implementation.
- Create: `frontend/lib/core/platform/file_launcher.dart` - safe platform file opening.
- Create: `frontend/lib/core/platform/path_clipboard.dart` - injectable path clipboard.
- Create: `frontend/lib/features/status/backend_status_models.dart` - readiness and index stats models.
- Create: `frontend/lib/features/status/backend_status_client.dart` - health and stats API adapter.
- Create: `frontend/lib/features/status/backend_status_controller.dart` - polling and retry state.
- Create: `frontend/lib/features/search/domain/search_models.dart` - query, filter, response, and result models.
- Create: `frontend/lib/features/search/data/search_api_client.dart` - `/v1/search` request and response mapping.
- Create: `frontend/lib/features/search/presentation/search_controller.dart` - query, filter, request, stale-response, and error state.
- Create: `frontend/lib/features/search/presentation/search_page.dart` - responsive search page composition.
- Create: `frontend/lib/features/search/presentation/widgets/search_filter_panel.dart` - mode, channel, and type filters.
- Create: `frontend/lib/features/search/presentation/widgets/search_result_tile.dart` - one actionable result.
- Create: `frontend/lib/features/search/presentation/widgets/search_state_view.dart` - initial, loading, empty, and error states.
- Create: `frontend/lib/features/shell/app_shell.dart` - adaptive Material 3 navigation and placeholders.
- Create: `frontend/lib/features/placeholders/index_library_page.dart` - index library placeholder.
- Create: `frontend/lib/features/placeholders/settings_page.dart` - settings placeholder.
- Replace: `frontend/test/widget_test.dart` - application-level smoke and navigation tests.
- Create: `frontend/test/core/api/io_json_transport_test.dart` - real loopback transport tests.
- Create: `frontend/test/core/platform/file_launcher_test.dart` - safe command selection and missing-file tests.
- Create: `frontend/test/features/status/backend_status_controller_test.dart` - readiness and polling tests.
- Create: `frontend/test/features/search/search_api_client_test.dart` - JSON contract tests.
- Create: `frontend/test/features/search/search_controller_test.dart` - state and stale-response tests.
- Create: `frontend/test/features/search/search_page_test.dart` - complete UI state and interaction tests.
- Create: `frontend/test/support/fakes.dart` - shared deterministic test doubles.

## Execution precondition

Run implementation in a dedicated worktree based on the plan commit:

```powershell
Set-Location -LiteralPath 'F:\contentretrivalsystem'
git worktree add -b codex/flutter-search-workbench '.worktrees/flutter-search-workbench' master
Set-Location -LiteralPath 'F:\contentretrivalsystem\.worktrees\flutter-search-workbench\frontend'
git status --short --branch
```

Expected: branch `codex/flutter-search-workbench`, no tracked changes, and no root PDF or output artifacts copied into the worktree.

### Task 1: Add the injectable JSON transport

**Files:**
- Create: `frontend/lib/core/api/api_exception.dart`
- Create: `frontend/lib/core/api/json_transport.dart`
- Create: `frontend/lib/core/api/io_json_transport.dart`
- Create: `frontend/test/core/api/io_json_transport_test.dart`

- [ ] **Step 1: Write loopback transport tests**

Create tests that start a loopback `HttpServer`, echo one GET and one POST body, and return malformed JSON from a third route:

```dart
test('sends JSON requests and decodes JSON responses', () async {
  final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
  addTearDown(() => server.close(force: true));
  server.listen((request) async {
    if (request.uri.path == '/get') {
      request.response
        ..statusCode = 200
        ..headers.contentType = ContentType.json
        ..write(jsonEncode({'status': 'ok'}));
    } else {
      final body = await utf8.decoder.bind(request).join();
      request.response
        ..statusCode = 202
        ..headers.contentType = ContentType.json
        ..write(body);
    }
    await request.response.close();
  });
  final transport = IoJsonTransport(
    baseUri: Uri.parse('http://127.0.0.1:${server.port}'),
    timeout: const Duration(seconds: 2),
  );
  addTearDown(transport.close);

  expect((await transport.get('/get')).body, {'status': 'ok'});
  final posted = await transport.post('/post', body: {'query': 'notes'});
  expect(posted.statusCode, 202);
  expect(posted.body, {'query': 'notes'});
});

test('maps malformed JSON to invalidResponse', () async {
  final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
  addTearDown(() => server.close(force: true));
  server.listen((request) async {
    request.response
      ..statusCode = 200
      ..write('not-json');
    await request.response.close();
  });
  final transport = IoJsonTransport(
    baseUri: Uri.parse('http://127.0.0.1:${server.port}'),
    timeout: const Duration(seconds: 2),
  );
  addTearDown(transport.close);

  await expectLater(
    transport.get('/broken'),
    throwsA(isA<ApiException>().having(
      (error) => error.kind,
      'kind',
      ApiErrorKind.invalidResponse,
    )),
  );
});
```

- [ ] **Step 2: Run the tests and verify RED**

```powershell
flutter test test/core/api/io_json_transport_test.dart
```

Expected: compilation fails because `IoJsonTransport`, `ApiException`, and the transport contract do not exist.

- [ ] **Step 3: Implement the transport contracts**

Use these public types:

```dart
enum ApiErrorKind { offline, timeout, invalidResponse, rejected }

final class ApiException implements Exception {
  const ApiException(this.kind, this.message, {this.code, this.statusCode});

  final ApiErrorKind kind;
  final String message;
  final String? code;
  final int? statusCode;

  @override
  String toString() => 'ApiException($kind, $message)';
}

final class JsonResponse {
  const JsonResponse({required this.statusCode, required this.body});

  final int statusCode;
  final Object? body;
}

abstract interface class JsonTransport {
  Future<JsonResponse> get(String path);
  Future<JsonResponse> post(
    String path, {
    required Map<String, Object?> body,
  });
  void close();
}
```

Implement `IoJsonTransport` with `HttpClient`, `Uri.resolve`, explicit JSON headers, UTF-8 decoding, and these exact exception mappings:

```dart
Future<JsonResponse> _send(
  String method,
  String path, {
  Map<String, Object?>? body,
}) async {
  try {
    final request = await _client.openUrl(method, baseUri.resolve(path));
    request.headers.accept.add(ContentType.json.mimeType);
    if (body != null) {
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode(body));
    }
    final response = await request.close().timeout(timeout);
    final text = await utf8.decoder.bind(response).join();
    final decoded = text.trim().isEmpty ? null : jsonDecode(text);
    return JsonResponse(statusCode: response.statusCode, body: decoded);
  } on TimeoutException catch (error) {
    throw ApiException(ApiErrorKind.timeout, 'Request timed out') from error;
  } on SocketException catch (error) {
    throw ApiException(ApiErrorKind.offline, 'Backend is unreachable')
        from error;
  } on FormatException catch (error) {
    throw ApiException(
      ApiErrorKind.invalidResponse,
      'Backend returned invalid JSON',
    ) from error;
  }
}
```

Set the production base URI later to `http://127.0.0.1:8000` and the timeout to 15 seconds.

- [ ] **Step 4: Run focused and formatting checks**

```powershell
dart format lib/core/api test/core/api
flutter test test/core/api/io_json_transport_test.dart
flutter analyze
```

Expected: both transport tests pass and analysis reports no issues.

- [ ] **Step 5: Commit the transport boundary**

```powershell
git add lib/core/api test/core/api
git commit -m "feat: add Flutter JSON transport"
```

### Task 2: Model and serialize search contracts

**Files:**
- Create: `frontend/lib/features/search/domain/search_models.dart`
- Create: `frontend/lib/features/search/data/search_api_client.dart`
- Create: `frontend/test/features/search/search_api_client_test.dart`
- Create: `frontend/test/support/fakes.dart`

- [ ] **Step 1: Create the fake transport and failing contract tests**

Define `FakeJsonTransport` in `test/support/fakes.dart` with queued GET and POST responses plus captured calls. Test the exact request mapping:

```dart
test('serializes query channels formats and topK', () async {
  final transport = FakeJsonTransport()
    ..postResponses.add(const JsonResponse(
      statusCode: 200,
      body: {
        'query': 'local notes',
        'hits': <Object?>[],
        'total_candidates': 0,
        'elapsed_ms': 4.5,
        'weights': {'keyword': 1.0},
      },
    ));
  final client = SearchApiClient(transport);

  await client.search(const SearchCriteria(
    query: 'local notes',
    channels: {SearchChannel.keyword, SearchChannel.textSemantic},
    contentTypes: {SearchContentType.documents},
  ));

  expect(transport.posts.single.path, '/v1/search');
  expect(transport.posts.single.body, {
    'query': 'local notes',
    'top_k': 20,
    'channels': ['keyword', 'text_semantic'],
    'filters': {
      'mime_types': [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      ],
      'modalities': ['text'],
    },
    'weights': null,
  });
});
```

Add a response test with one complete hit and assert every field, including `match_reasons`, optional page and paragraph numbers, and the real floating-point score. Add `422` and `503` tests asserting backend `detail.code` and `detail.message` become `ApiException` fields.

- [ ] **Step 2: Run the search API tests and verify RED**

```powershell
flutter test test/features/search/search_api_client_test.dart
```

Expected: compilation fails because the search models and client do not exist.

- [ ] **Step 3: Implement domain enums and immutable models**

Define these wire values and mappings exactly:

```dart
enum SearchChannel {
  keyword('keyword'),
  textSemantic('text_semantic'),
  imageSemantic('image_semantic');

  const SearchChannel(this.wireName);
  final String wireName;
}

enum RetrievalMode {
  exact({SearchChannel.keyword}),
  hybrid({
    SearchChannel.keyword,
    SearchChannel.textSemantic,
    SearchChannel.imageSemantic,
  }),
  semantic({SearchChannel.textSemantic, SearchChannel.imageSemantic});

  const RetrievalMode(this.channels);
  final Set<SearchChannel> channels;
}

enum SearchContentType { documents, textFiles, images }

const contentTypeMimeTypes = <SearchContentType, List<String>>{
  SearchContentType.documents: [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  ],
  SearchContentType.textFiles: ['text/plain'],
  SearchContentType.images: ['image/png', 'image/jpeg', 'image/webp'],
};

const contentTypeModalities = <SearchContentType, String>{
  SearchContentType.documents: 'text',
  SearchContentType.textFiles: 'text',
  SearchContentType.images: 'image',
};

final class SearchCriteria {
  const SearchCriteria({
    required this.query,
    required this.channels,
    required this.contentTypes,
    this.topK = 20,
  });

  final String query;
  final Set<SearchChannel> channels;
  final Set<SearchContentType> contentTypes;
  final int topK;
}

final class SearchHit {
  const SearchHit({
    required this.fileId,
    required this.sourceId,
    required this.path,
    required this.name,
    required this.mimeType,
    required this.modality,
    required this.score,
    required this.matchReasons,
    required this.snippet,
    required this.pageNumber,
    required this.paragraphNumber,
  });

  final String fileId;
  final String sourceId;
  final String path;
  final String name;
  final String mimeType;
  final String modality;
  final double score;
  final List<SearchChannel> matchReasons;
  final String? snippet;
  final int? pageNumber;
  final int? paragraphNumber;
}

final class SearchResponse {
  const SearchResponse({
    required this.query,
    required this.hits,
    required this.totalCandidates,
    required this.elapsedMs,
    required this.weights,
  });

  final String query;
  final List<SearchHit> hits;
  final int totalCandidates;
  final double elapsedMs;
  final Map<String, double> weights;
}

abstract interface class SearchService {
  Future<SearchResponse> search(SearchCriteria criteria);
}
```

Parse `score` as `double`; do not convert it to a percentage. Convert every `match_reasons` wire value through `SearchChannel.wireName` and reject unknown values as an invalid response.

- [ ] **Step 4: Implement `SearchApiClient`**

`SearchApiClient` implements `SearchService`. Serialize deterministic channel, MIME, and deduplicated modality lists in enum declaration order. An empty content type set produces empty `mime_types` and `modalities`, which the backend interprets as no content restriction. Reject a response unless its body is `Map<String, Object?>`. For non-2xx responses, parse this shape:

```dart
ApiException _rejected(JsonResponse response) {
  final root = response.body;
  final detail = root is Map<String, Object?> ? root['detail'] : null;
  final values = detail is Map<String, Object?> ? detail : const {};
  return ApiException(
    ApiErrorKind.rejected,
    values['message'] as String? ?? 'Search request failed',
    code: values['code'] as String?,
    statusCode: response.statusCode,
  );
}
```

Parse numeric fields through `(value as num).toDouble()` and optional integers through `(value as num?)?.toInt()`.

- [ ] **Step 5: Run focused tests and analysis**

```powershell
dart format lib/features/search/domain lib/features/search/data test/features/search test/support
flutter test test/features/search/search_api_client_test.dart
flutter analyze
```

Expected: request, response, `422`, and `503` tests pass.

- [ ] **Step 6: Commit search contracts**

```powershell
git add lib/features/search test/features/search test/support
git commit -m "feat: add Flutter search contracts"
```

### Task 3: Monitor backend readiness and index statistics

**Files:**
- Create: `frontend/lib/features/status/backend_status_models.dart`
- Create: `frontend/lib/features/status/backend_status_client.dart`
- Create: `frontend/lib/features/status/backend_status_controller.dart`
- Create: `frontend/test/features/status/backend_status_controller_test.dart`
- Modify: `frontend/test/support/fakes.dart`

- [ ] **Step 1: Write failing status controller tests**

Use a `FakeBackendStatusClient` with queued readiness and stats results. Cover these transitions:

```dart
test('start checks immediately and publishes online stats', () async {
  final client = FakeBackendStatusClient()
    ..readyResults.add(true)
    ..statsResults.add(const IndexStats(
      recordCount: 3,
      fileCount: 2,
      textRecordCount: 2,
      imageRecordCount: 1,
    ));
  final controller = BackendStatusController(
    client,
    pollInterval: const Duration(hours: 1),
  );
  addTearDown(controller.dispose);

  await controller.start();

  expect(controller.state, BackendConnectionState.online);
  expect(controller.stats?.fileCount, 2);
  expect(client.readyCalls, 1);
});

test('offline refresh keeps last successful stats', () async {
  final client = FakeBackendStatusClient()
    ..readyResults.addAll([true, false])
    ..statsResults.add(const IndexStats(
      recordCount: 3,
      fileCount: 2,
      textRecordCount: 2,
      imageRecordCount: 1,
    ));
  final controller = BackendStatusController(
    client,
    pollInterval: const Duration(hours: 1),
  );
  addTearDown(controller.dispose);

  await controller.start();
  await controller.refresh();

  expect(controller.state, BackendConnectionState.offline);
  expect(controller.stats?.fileCount, 2);
});
```

Add a widget test with a 1-second poll interval, `tester.pump(const Duration(seconds: 1))`, and assert a second readiness call. After `dispose`, pump again and assert the count does not change.

- [ ] **Step 2: Run status tests and verify RED**

```powershell
flutter test test/features/status/backend_status_controller_test.dart
```

Expected: compilation fails because the status types do not exist.

- [ ] **Step 3: Implement the status client**

Define:

```dart
enum BackendConnectionState { checking, online, offline }

final class IndexStats {
  const IndexStats({
    required this.recordCount,
    required this.fileCount,
    required this.textRecordCount,
    required this.imageRecordCount,
  });

  final int recordCount;
  final int fileCount;
  final int textRecordCount;
  final int imageRecordCount;
}

abstract interface class BackendStatusApi {
  Future<bool> isReady();
  Future<IndexStats> fetchStats();
}
```

`BackendStatusClient.isReady` calls `GET /health/ready` and returns true only for `200`. `fetchStats` calls `GET /v1/index/stats`, requires a map body, and parses the four integer fields.

- [ ] **Step 4: Implement polling lifecycle**

`BackendStatusController` extends `ChangeNotifier`, ignores overlapping refreshes, starts one `Timer.periodic`, retains successful stats after failures, and prevents notifications after disposal:

```dart
Future<void> refresh() async {
  if (_refreshing || _disposed) return;
  _refreshing = true;
  try {
    final ready = await api.isReady();
    if (_disposed) return;
    state = ready
        ? BackendConnectionState.online
        : BackendConnectionState.offline;
    if (ready) {
      try {
        stats = await api.fetchStats();
      } on ApiException {
        // Search remains available when stats alone fail.
      }
    }
  } on ApiException {
    if (!_disposed) state = BackendConnectionState.offline;
  } finally {
    _refreshing = false;
    if (!_disposed) notifyListeners();
  }
}
```

`start` immediately sets `checking`, awaits `refresh`, then creates a periodic 10-second timer. `dispose` cancels the timer before calling `super.dispose()`.

- [ ] **Step 5: Run tests and commit**

```powershell
dart format lib/features/status test/features/status test/support
flutter test test/features/status/backend_status_controller_test.dart
flutter analyze
git add lib/features/status test/features/status test/support
git commit -m "feat: monitor Flutter backend status"
```

Expected: all status tests pass and the commit contains only status files plus shared fakes.

### Task 4: Implement deterministic search state

**Files:**
- Create: `frontend/lib/features/search/presentation/search_controller.dart`
- Create: `frontend/test/features/search/search_controller_test.dart`
- Modify: `frontend/test/support/fakes.dart`

- [ ] **Step 1: Write failing controller tests**

Cover blank validation, loading to success, loading to empty, structured failure, at least one channel, mode mapping, and stale responses. Use two `Completer<SearchResponse>` values for the stale-response test:

```dart
test('late response cannot replace a newer search', () async {
  final first = Completer<SearchResponse>();
  final second = Completer<SearchResponse>();
  final client = FakeSearchService()
    ..results.addAll([first.future, second.future]);
  final controller = SearchController(client);

  controller.setQuery('first');
  final firstCall = controller.submit();
  controller.setQuery('second');
  final secondCall = controller.submit();

  second.complete(searchResponse('second', ['new.txt']));
  await secondCall;
  first.complete(searchResponse('first', ['old.txt']));
  await firstCall;

  expect(controller.response?.query, 'second');
  expect(controller.response?.hits.single.name, 'new.txt');
});
```

Assert `setMode(RetrievalMode.semantic)` produces only semantic channels. Assert removing the final channel returns false and preserves it.

- [ ] **Step 2: Run controller tests and verify RED**

```powershell
flutter test test/features/search/search_controller_test.dart
```

Expected: compilation fails because `SearchController` and `SearchViewState` do not exist.

- [ ] **Step 3: Implement controller state and request versioning**

Use:

```dart
enum SearchViewState { initial, loading, success, empty, failure }

final class SearchController extends ChangeNotifier {
  SearchController(this.service);

  final SearchService service;
  String query = '';
  RetrievalMode mode = RetrievalMode.hybrid;
  Set<SearchChannel> channels = SearchChannel.values.toSet();
  Set<SearchContentType> contentTypes = SearchContentType.values.toSet();
  SearchViewState state = SearchViewState.initial;
  SearchResponse? response;
  ApiException? error;
  String? queryError;
  int _requestVersion = 0;
  bool _disposed = false;
}
```

`submit` normalizes whitespace, rejects blanks without calling the service, increments `_requestVersion`, preserves existing results while setting loading, and applies a response only when its version remains current. Map zero hits to `empty`; map `ApiException` to `failure`. `dispose` increments the version and marks disposed.

`setMode` copies the mode channels. `toggleChannel` returns false when removal would leave an empty set. `toggleContentType` permits an empty set and serializes that as no MIME or modality restriction.

- [ ] **Step 4: Run controller suite and commit**

```powershell
dart format lib/features/search/presentation/search_controller.dart test/features/search/search_controller_test.dart test/support
flutter test test/features/search/search_controller_test.dart
flutter analyze
git add lib/features/search/presentation/search_controller.dart test/features/search/search_controller_test.dart test/support
git commit -m "feat: manage Flutter search state"
```

### Task 5: Open and copy result paths safely

**Files:**
- Create: `frontend/lib/core/platform/file_launcher.dart`
- Create: `frontend/lib/core/platform/path_clipboard.dart`
- Create: `frontend/test/core/platform/file_launcher_test.dart`

- [ ] **Step 1: Write failing platform tests**

Inject filesystem existence and process start functions instead of launching applications during tests:

```dart
test('uses explorer arguments without a shell on Windows', () async {
  String? executable;
  List<String>? arguments;
  final launcher = IoFileLauncher(
    platform: DesktopPlatform.windows,
    fileExists: (_) async => true,
    startProcess: (program, args) async {
      executable = program;
      arguments = args;
    },
  );

  await launcher.open(r'C:\notes\project plan.pdf');

  expect(executable, 'explorer.exe');
  expect(arguments, [r'C:\notes\project plan.pdf']);
});

test('rejects a missing result path before starting a process', () async {
  final launcher = IoFileLauncher(
    platform: DesktopPlatform.windows,
    fileExists: (_) async => false,
    startProcess: (_, _) async => fail('must not start'),
  );

  await expectLater(
    launcher.open(r'C:\missing.pdf'),
    throwsA(isA<FileLaunchException>().having(
      (error) => error.kind,
      'kind',
      FileLaunchErrorKind.notFound,
    )),
  );
});
```

Add command tests for macOS `open` and Linux `xdg-open`.

- [ ] **Step 2: Run platform tests and verify RED**

```powershell
flutter test test/core/platform/file_launcher_test.dart
```

Expected: compilation fails because the launcher types do not exist.

- [ ] **Step 3: Implement safe platform adapters**

Define `FileLauncher`, `FileLaunchException`, `DesktopPlatform`, and `IoFileLauncher`. Production process start must use argument arrays and `runInShell: false`:

```dart
Future<void> _defaultStart(String executable, List<String> arguments) async {
  await Process.start(
    executable,
    arguments,
    mode: ProcessStartMode.detached,
    runInShell: false,
  );
}
```

Select `explorer.exe`, `open`, or `xdg-open` from the injected platform. Throw `unsupportedPlatform`, `notFound`, or `launchFailed` with stable Chinese UI messages.

Define:

```dart
abstract interface class PathClipboard {
  Future<void> copy(String path);
}

final class SystemPathClipboard implements PathClipboard {
  @override
  Future<void> copy(String path) =>
      Clipboard.setData(ClipboardData(text: path));
}
```

- [ ] **Step 4: Verify and commit platform integration**

```powershell
dart format lib/core/platform test/core/platform
flutter test test/core/platform/file_launcher_test.dart
flutter analyze
git add lib/core/platform test/core/platform
git commit -m "feat: open Flutter search result files"
```

### Task 6: Build the Material 3 application shell

**Files:**
- Create: `frontend/lib/app/app_theme.dart`
- Create: `frontend/lib/features/shell/app_shell.dart`
- Create: `frontend/lib/features/placeholders/index_library_page.dart`
- Create: `frontend/lib/features/placeholders/settings_page.dart`
- Replace: `frontend/test/widget_test.dart`

- [ ] **Step 1: Replace the counter test with failing shell tests**

Pump `MaterialApp(theme: AppTheme.light(), home: AppShell(searchPage: const Text('SEARCH_PAGE')))`. Assert “搜索”“索引库”“设置”, initial search content, and destination switching. Set a desktop surface size before pumping:

```dart
await tester.binding.setSurfaceSize(const Size(1280, 720));
addTearDown(() => tester.binding.setSurfaceSize(null));
```

Tap “索引库” and expect “索引库功能将在后续版本提供”. Tap “设置” and expect “设置功能将在后续版本提供”.

- [ ] **Step 2: Run shell tests and verify RED**

```powershell
flutter test test/widget_test.dart
```

Expected: compilation fails because the theme and shell do not exist.

- [ ] **Step 3: Implement light and dark Material 3 themes**

Build both themes from `ColorScheme.fromSeed(seedColor: const Color(0xFF3659AD))`, set `useMaterial3: true`, define `inputDecorationTheme`, `chipTheme`, `navigationRailTheme`, `filledButtonTheme`, and `tooltipTheme`. Use system fonts only. Do not add network fonts or a second icon package.

- [ ] **Step 4: Implement adaptive navigation**

`AppShell` owns only the selected destination index and accepts the real search page as a constructor argument:

```dart
final class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.searchPage});
  final Widget searchPage;
}
```

At widths at least 1000, render an extended `NavigationRail` with `minExtendedWidth: 214`; below 1000 render the non-extended rail. Use three `NavigationRailDestination` values with Material icons. The body is an `IndexedStack` so search results survive destination switches.

Placeholder pages must be real centered Material 3 empty states with one icon, one title, and one sentence. They must not expose controls that do nothing.

- [ ] **Step 5: Run shell tests and commit**

```powershell
dart format lib/app/app_theme.dart lib/features/shell lib/features/placeholders test/widget_test.dart
flutter test test/widget_test.dart
flutter analyze
git add lib/app/app_theme.dart lib/features/shell lib/features/placeholders test/widget_test.dart
git commit -m "feat: add Material 3 Flutter shell"
```

### Task 7: Render the complete search workbench

**Files:**
- Create: `frontend/lib/features/search/presentation/search_page.dart`
- Create: `frontend/lib/features/search/presentation/widgets/search_filter_panel.dart`
- Create: `frontend/lib/features/search/presentation/widgets/search_result_tile.dart`
- Create: `frontend/lib/features/search/presentation/widgets/search_state_view.dart`
- Create: `frontend/test/features/search/search_page_test.dart`
- Modify: `frontend/test/support/fakes.dart`

- [ ] **Step 1: Write failing search page state tests**

Create a `buildSearchPage` helper that injects `SearchController`, `BackendStatusController`, `FakeFileLauncher`, and `FakePathClipboard`. Cover these exact states:

```dart
testWidgets('offline keeps existing results and disables search', (tester) async {
  final service = FakeSearchService()
    ..results.add(Future.value(searchResponse('notes', ['notes.txt'])));
  final search = SearchController(service)..setQuery('notes');
  await search.submit();
  final status = offlineStatusController();

  await tester.pumpWidget(buildSearchPage(search: search, status: status));

  expect(find.text('后端离线'), findsOneWidget);
  expect(find.text('notes.txt'), findsOneWidget);
  expect(tester.widget<FilledButton>(find.text('搜索').last).onPressed, isNull);
  expect(find.text('重新检测'), findsOneWidget);
});
```

Also test:

- initial online page has visible “搜索内容” label;
- Enter and the filled search button invoke one request each;
- loading renders three skeleton rows and no circular spinner;
- empty renders “未找到匹配内容” plus “清除过滤”;
- `422` renders request validation text;
- `503` renders service unavailable text plus retry;
- a result shows file name, snippet, page or paragraph, path, reasons, open, and copy buttons;
- opening a missing file creates an inline row error;
- copy invokes `PathClipboard` and shows a `SnackBar`;
- a width below 1100 hides the persistent filter panel and exposes a “筛选” button;
- selecting a retrieval mode changes the checked channels;
- the final selected channel cannot be removed.

- [ ] **Step 2: Run the page tests and verify RED**

```powershell
flutter test test/features/search/search_page_test.dart
```

Expected: compilation fails because the page widgets do not exist.

- [ ] **Step 3: Implement reusable result and state widgets**

`SearchResultTile` accepts one `SearchHit`, `FileLauncher`, and `PathClipboard`. Keep row-local `FileLaunchException?` state. Use `SelectableText` or a tooltip for the full path, a Material `FilledButton.tonalIcon` for open, and an `IconButton` for copy.

`SearchStateView` switches on `SearchViewState`:

```dart
return switch (controller.state) {
  SearchViewState.initial => const SearchInitialState(),
  SearchViewState.loading => const SearchSkeletonList(rowCount: 3),
  SearchViewState.empty => SearchEmptyState(onClearFilters: onClearFilters),
  SearchViewState.failure => SearchErrorState(
      message: errorMessage(controller.error),
      onRetry: onRetry,
    ),
  SearchViewState.success => SearchResultList(
      response: controller.response!,
      fileLauncher: fileLauncher,
      pathClipboard: pathClipboard,
    ),
};
```

Skeleton rows must match the final result row structure using neutral `Container` blocks. Do not use an indeterminate spinner for result loading.

- [ ] **Step 4: Implement the filter panel**

Use a Material 3 segmented control for `RetrievalMode`, filter chips for content types, and checkboxes for channels. Display a short inline message when the last channel removal is rejected. The wide panel is 292 pixels; the compact version is the same widget inside `showModalBottomSheet`.

- [ ] **Step 5: Implement `SearchPage` composition**

Use nested `ListenableBuilder` widgets for status and search controllers. The structure is:

```text
Column
  Search top bar with backend status and refresh
  Expanded
    LayoutBuilder
      Row
        Expanded search column
          Search stage
          Expanded SearchStateView
        SearchFilterPanel when width >= 1100
```

The input has a visible label, `FocusNode`, and `Shortcuts` mappings: `Ctrl+K` requests focus and Escape calls `unfocus()` without clearing the controller text. `onSubmitted` calls search only when backend state is online. Filter changes call `submit` only when the normalized query is non-empty and the backend is online. The result summary displays only the real `totalCandidates` and `elapsedMs` returned by the active response.

Preserve existing successful results when the backend transitions offline. Disable only actions that require a new network request.

- [ ] **Step 6: Run page tests and commit**

```powershell
dart format lib/features/search/presentation test/features/search/search_page_test.dart test/support
flutter test test/features/search/search_page_test.dart
flutter analyze
git add lib/features/search/presentation test/features/search/search_page_test.dart test/support
git commit -m "feat: build Flutter search workbench UI"
```

### Task 8: Compose production dependencies and replace the counter app

**Files:**
- Create: `frontend/lib/app/content_retrieval_app.dart`
- Modify: `frontend/lib/main.dart`
- Modify: `frontend/test/widget_test.dart`

- [ ] **Step 1: Add a failing application smoke test**

Pump `ContentRetrievalApp` with injected fake transport, launcher, and clipboard. Assert no counter text or add icon exists, the title is “本地内容检索”, and the search shell appears. Add a dispose test asserting the injected transport `close` method is called once.

- [ ] **Step 2: Run the application test and verify RED**

```powershell
flutter test test/widget_test.dart
```

Expected: compilation fails because `ContentRetrievalApp` does not exist.

- [ ] **Step 3: Compose dependency lifecycle**

`ContentRetrievalApp` is stateful and accepts optional injected adapters for tests. In production, construct:

```dart
final transport = IoJsonTransport(
  baseUri: Uri.parse('http://127.0.0.1:8000'),
  timeout: const Duration(seconds: 15),
);
final statusApi = BackendStatusClient(transport);
final statusController = BackendStatusController(statusApi);
final searchController = SearchController(SearchApiClient(transport));
final fileLauncher = IoFileLauncher.production();
const pathClipboard = SystemPathClipboard();
```

Call `statusController.start()` from `initState` with `unawaited`. Dispose both controllers, then close the transport once. Build `MaterialApp` with `themeMode: ThemeMode.system`, `AppTheme.light()`, `AppTheme.dark()`, and `AppShell(searchPage: SearchPage(...))`.

- [ ] **Step 4: Replace the entry point**

`frontend/lib/main.dart` becomes:

```dart
import 'package:flutter/material.dart';

import 'app/content_retrieval_app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ContentRetrievalApp());
}
```

- [ ] **Step 5: Run all Flutter tests and commit**

```powershell
dart format lib test
flutter analyze
flutter test
git add lib/main.dart lib/app/content_retrieval_app.dart test/widget_test.dart
git commit -m "feat: connect Flutter search application"
```

Expected: analysis succeeds and every transport, status, search, platform, page, shell, and application test passes.

### Task 9: Verify desktop behavior and committed boundaries

**Files:**
- Verify: all `frontend/lib/**`, `frontend/test/**`, and unchanged platform projects.

- [ ] **Step 1: Run formatting without rewriting**

```powershell
dart format --output=none --set-exit-if-changed lib test
```

Expected: all Dart files are unchanged and the command exits 0.

- [ ] **Step 2: Run static analysis and the complete Flutter suite**

```powershell
flutter analyze
flutter test
```

Expected: `No issues found!` and `All tests passed!`.

- [ ] **Step 3: Build the Windows debug application**

```powershell
flutter build windows --debug
```

Expected: build succeeds and produces `build\windows\x64\runner\Debug\content_retrieval_app.exe`.

- [ ] **Step 4: Run a real backend smoke test**

Start the existing backend in a separate terminal from the repository worktree root:

```powershell
.\tools\start-mvp.ps1
```

Then launch the app:

```powershell
Set-Location -LiteralPath 'frontend'
flutter run -d windows
```

Verify manually:

1. Status changes from checking to online.
2. Index stats show only values returned by the backend.
3. A real query returns results from `/v1/search`.
4. Mode, channel, and format changes alter the next request.
5. Open launches an existing result with the system default application.
6. Copy places the full path on the clipboard.
7. Stopping the backend changes status to offline without clearing results.
8. Restarting the backend and clicking “重新检测” returns to online.

Stop the Flutter app and the backend with Ctrl+C in their owning terminals.

- [ ] **Step 5: Audit diff and generated file noise**

```powershell
git diff master...HEAD --check
git status --short
git diff master...HEAD --name-status
```

Expected: only planned source and test files differ. If Flutter marks generated plugin registrants as modified, compare filtered blob hashes before refreshing only those exact index entries; do not reset unrelated user files.

- [ ] **Step 6: Verify the exact commit in a clean detached worktree**

From `F:\contentretrivalsystem` create a temporary detached worktree at the final feature commit, run all Flutter verification there, then remove only that verified temporary worktree:

```powershell
$verifyPath = 'F:\contentretrivalsystem\.worktrees\verify-flutter-search'
$resolvedParent = (Resolve-Path -LiteralPath 'F:\contentretrivalsystem\.worktrees').Path
if (Test-Path -LiteralPath $verifyPath) {
  throw "Verification path already exists: $verifyPath"
}
git worktree add --detach $verifyPath codex/flutter-search-workbench
Push-Location -LiteralPath (Join-Path $verifyPath 'frontend')
try {
  dart format --output=none --set-exit-if-changed lib test
  if ($LASTEXITCODE -ne 0) { throw 'Clean format verification failed' }
  flutter analyze
  if ($LASTEXITCODE -ne 0) { throw 'Clean analysis failed' }
  flutter test
  if ($LASTEXITCODE -ne 0) { throw 'Clean tests failed' }
  flutter build windows --debug
  if ($LASTEXITCODE -ne 0) { throw 'Clean Windows build failed' }
} finally {
  Pop-Location
}
$resolvedVerify = (Resolve-Path -LiteralPath $verifyPath).Path
if (-not $resolvedVerify.StartsWith($resolvedParent + '\')) {
  throw "Refusing to remove worktree outside expected parent: $resolvedVerify"
}
git worktree remove $resolvedVerify
```

Expected: every command passes from the committed snapshot, and the temporary worktree path no longer exists afterward. This confirms the branch does not depend on untracked source or caches in the development worktree.

- [ ] **Step 7: Commit any verification-only fixes**

If verification required source or test corrections, stage only those exact paths and commit:

```powershell
git add frontend/lib frontend/test
git commit -m "fix: finalize Flutter search workbench"
```

If no tracked corrections were required, do not create an empty commit.

## Plan self-review checklist

- Spec coverage: Tasks 1-9 cover backend readiness, index stats, real search, channel and format filters, result opening, path copy, adaptive Material 3 navigation, placeholders, loading, empty, error, offline, light, dark, reduced motion, tests, and Windows build.
- Placeholder scan: the plan contains no deferred code markers or unspecified “handle errors” steps.
- Type consistency: `JsonTransport`, `BackendStatusApi`, `SearchService`, `SearchCriteria`, `SearchResponse`, `SearchController`, `FileLauncher`, and `PathClipboard` keep the same signatures from their first definition through application composition.
- Scope check: index management, editable settings, history, favorites, weight sliders, advanced path or date filters, previews, and process control remain excluded.
