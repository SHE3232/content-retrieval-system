# Flutter Library and Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the index-library and settings placeholders with a tested file catalog, indexing controls, safe mutations, configurable backend connection, theme/accessibility preferences, and restart persistence.

**Architecture:** Extend the search workbench's injectable transport instead of creating a second HTTP stack. Keep library API mapping, polling/mutation state, directory selection, settings persistence, and application dependency rebuilding behind interfaces. The UI consumes `ChangeNotifier` controllers and never reaches platform APIs or shared preferences directly.

**Tech Stack:** Flutter 3.44.6, Dart 3.12.2, Material 3, `file_selector` 1.1.0, `shared_preferences` 2.5.5, flutter_test

---

## File map

- Modify: `frontend/pubspec.yaml`
- Modify: `frontend/lib/core/api/json_transport.dart`
- Modify: `frontend/lib/core/api/io_json_transport.dart`
- Modify: `frontend/test/core/api/io_json_transport_test.dart`
- Create: `frontend/lib/core/platform/directory_picker.dart`
- Create: `frontend/lib/features/library/domain/index_library_models.dart`
- Create: `frontend/lib/features/library/data/index_library_api_client.dart`
- Create: `frontend/lib/features/library/presentation/index_library_controller.dart`
- Create: `frontend/lib/features/library/presentation/index_library_page.dart`
- Create: `frontend/lib/features/library/presentation/widgets/index_job_panel.dart`
- Create: `frontend/lib/features/library/presentation/widgets/indexed_file_tile.dart`
- Create: `frontend/lib/features/settings/domain/app_settings.dart`
- Create: `frontend/lib/features/settings/data/settings_repository.dart`
- Create: `frontend/lib/features/settings/presentation/settings_controller.dart`
- Create: `frontend/lib/features/settings/presentation/settings_page.dart`
- Modify: `frontend/lib/features/shell/app_shell.dart`
- Modify: `frontend/lib/app/content_retrieval_app.dart`
- Delete: `frontend/lib/features/placeholders/index_library_page.dart`
- Delete: `frontend/lib/features/placeholders/settings_page.dart`
- Create: `frontend/test/features/library/index_library_api_client_test.dart`
- Create: `frontend/test/features/library/index_library_controller_test.dart`
- Create: `frontend/test/features/library/index_library_page_test.dart`
- Create: `frontend/test/features/settings/settings_repository_test.dart`
- Create: `frontend/test/features/settings/settings_controller_test.dart`
- Create: `frontend/test/features/settings/settings_page_test.dart`
- Modify: `frontend/test/support/fakes.dart`
- Modify: `frontend/test/widget_test.dart`

## Execution precondition

Start from the committed completion of `2026-08-10-flutter-search-workbench.md`. Run:

```powershell
Set-Location frontend
flutter test
flutter analyze
```

Expected: all search-workbench tests pass and placeholders are the only library/settings implementation.

### Task 1: Add platform dependencies and complete the transport contract

**Files:**
- Modify: `frontend/pubspec.yaml`
- Modify: `frontend/lib/core/api/json_transport.dart`
- Modify: `frontend/lib/core/api/io_json_transport.dart`
- Modify: `frontend/test/core/api/io_json_transport_test.dart`
- Modify: `frontend/test/support/fakes.dart`

- [ ] **Step 1: Add a failing DELETE transport test**

Extend the loopback server test to capture a DELETE request with no body:

```dart
final deleted = await transport.delete('/v1/index/files/abc');
expect(deleted.statusCode, 204);
expect(capturedMethod, 'DELETE');
expect(capturedPath, '/v1/index/files/abc');
```

Add captured DELETE calls to `FakeJsonTransport`.

- [ ] **Step 2: Verify RED**

```powershell
flutter test test/core/api/io_json_transport_test.dart
```

Expected: compilation fails because `JsonTransport.delete` does not exist.

- [ ] **Step 3: Extend the interface and implementation**

Add:

```dart
abstract interface class JsonTransport {
  Future<JsonResponse> get(String path);
  Future<JsonResponse> post(
    String path, {
    required Map<String, Object?> body,
  });
  Future<JsonResponse> delete(String path);
  void close();
}
```

Make `_send` accept a nullable body and implement `delete` through `_send('DELETE', path)`. Do not put `source_key` into a shell command or concatenate it outside URI resolution.

- [ ] **Step 4: Add pinned packages**

In `pubspec.yaml` add:

```yaml
dependencies:
  file_selector: ^1.1.0
  flutter:
    sdk: flutter
  shared_preferences: ^2.5.5
```

Run:

```powershell
flutter pub get
dart format lib/core/api test/core/api test/support
flutter test test/core/api/io_json_transport_test.dart
flutter analyze
```

Expected: DELETE test passes and package resolution succeeds.

- [ ] **Step 5: Commit transport and dependencies**

```powershell
git add pubspec.yaml pubspec.lock lib/core/api test/core/api test/support
git commit -m "feat: extend Flutter library transport"
```

### Task 2: Model and map the index-management API

**Files:**
- Create: `frontend/lib/features/library/domain/index_library_models.dart`
- Create: `frontend/lib/features/library/data/index_library_api_client.dart`
- Create: `frontend/test/features/library/index_library_api_client_test.dart`
- Modify: `frontend/test/support/fakes.dart`

- [ ] **Step 1: Write failing API contract tests**

Use `FakeJsonTransport` to cover:

1. `GET /v1/index/files?page=2&page_size=25` parses all file and pagination fields.
2. `POST /v1/indexing/jobs` sends `{'directory': r'C:\docs'}` and parses the job.
3. `GET /v1/indexing/jobs/{job_id}` parses status and counters.
4. `GET /v1/indexing/jobs/{job_id}/failures` parses structured failures.
5. `POST /v1/index/files/{source_key}/reindex` uses an empty JSON body.
6. `DELETE /v1/index/files/{source_key}` handles `204`.
7. `409`, `404`, and `503` preserve backend `detail.code`, `detail.message`, and status.

Use one full file fixture:

```dart
const fileJson = <String, Object?>{
  'source_key': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  'file_id': 'file-1',
  'path': r'C:\docs\guide.pdf',
  'name': 'guide.pdf',
  'mime_type': 'application/pdf',
  'modality': 'text',
  'size_bytes': 4096,
  'modified_at': '2026-08-10T10:00:00Z',
  'record_count': 4,
};
```

- [ ] **Step 2: Verify RED**

```powershell
flutter test test/features/library/index_library_api_client_test.dart
```

Expected: missing model/client compilation failures.

- [ ] **Step 3: Implement immutable domain contracts**

Define:

```dart
enum IndexJobStatus { queued, running, completed, failed }

final class IndexedFile {
  const IndexedFile({
    required this.sourceKey,
    required this.fileId,
    required this.path,
    required this.name,
    required this.mimeType,
    required this.modality,
    required this.sizeBytes,
    required this.modifiedAt,
    required this.recordCount,
  });
  final String sourceKey;
  final String fileId;
  final String path;
  final String name;
  final String mimeType;
  final String modality;
  final int sizeBytes;
  final DateTime modifiedAt;
  final int recordCount;
}

final class IndexedFilePage {
  const IndexedFilePage({
    required this.items,
    required this.page,
    required this.pageSize,
    required this.total,
  });
  final List<IndexedFile> items;
  final int page;
  final int pageSize;
  final int total;
}

abstract interface class IndexLibraryService {
  Future<IndexedFilePage> fetchFiles({required int page, required int pageSize});
  Future<IndexJob> startIndexing(String directory);
  Future<IndexJob> fetchJob(String jobId);
  Future<List<IndexFailure>> fetchFailures(String jobId);
  Future<IndexJob> reindex(String sourceKey);
  Future<void> remove(String sourceKey);
}
```

The `IndexJob` fields must mirror the backend response exactly. Parse numeric values through `num`, timestamps through `DateTime.parse`, and reject missing/unknown required fields as `ApiErrorKind.invalidResponse`.

- [ ] **Step 4: Implement `IndexLibraryApiClient`**

Validate `sourceKey` before building paths:

```dart
final sourceKeyPattern = RegExp(r'^[0-9a-f]{64}$');
if (!sourceKeyPattern.hasMatch(sourceKey)) {
  throw const ApiException(
    ApiErrorKind.invalidResponse,
    'Invalid source key',
  );
}
```

Use `Uri.encodeComponent(jobId)` for job routes. Treat only 2xx as success and use the existing backend error mapper for failures.

- [ ] **Step 5: Verify and commit**

```powershell
dart format lib/features/library/domain lib/features/library/data test/features/library test/support
flutter test test/features/library/index_library_api_client_test.dart
flutter analyze
git add lib/features/library/domain lib/features/library/data test/features/library test/support
git commit -m "feat: add Flutter index library contracts"
```

### Task 3: Implement directory selection and library state

**Files:**
- Create: `frontend/lib/core/platform/directory_picker.dart`
- Create: `frontend/lib/features/library/presentation/index_library_controller.dart`
- Create: `frontend/test/features/library/index_library_controller_test.dart`
- Modify: `frontend/test/support/fakes.dart`

- [ ] **Step 1: Write controller tests**

Add fakes for `DirectoryPicker`, `IndexLibraryService`, and scheduled polling. Cover:

- initial load and page navigation;
- selecting a directory then starting a job;
- picker cancellation performs no API call;
- queued/running job polling reaches completed and refreshes page 1;
- failed job loads failure details;
- overlapping refreshes and mutations are ignored;
- `INDEX_MUTATION_CONFLICT` becomes a visible stable error without clearing files;
- reindex and remove require explicit controller calls;
- successful removal refreshes the current valid page;
- dispose cancels all timers and ignores late completions.

Example state assertion:

```dart
expect(controller.job?.status, IndexJobStatus.running);
expect(controller.isMutationInProgress, isTrue);
expect(controller.files, isNotEmpty);
```

- [ ] **Step 2: Verify RED**

```powershell
flutter test test/features/library/index_library_controller_test.dart
```

- [ ] **Step 3: Implement the picker boundary**

```dart
abstract interface class DirectoryPicker {
  bool get isSupported;
  Future<String?> pickDirectory();
}

final class FileSelectorDirectoryPicker implements DirectoryPicker {
  const FileSelectorDirectoryPicker({required this.isSupported});

  @override
  final bool isSupported;

  @override
  Future<String?> pickDirectory() async {
    if (!isSupported) return null;
    return getDirectoryPath(confirmButtonText: '选择此文件夹');
  }
}
```

Production composition sets `isSupported` true only on Windows, macOS, and Linux. It is false on Android and Web because the desktop backend cannot consume a mobile or browser filesystem path. The UI must explain that these are validation targets and direct users to the desktop build for index management.

- [ ] **Step 4: Implement `IndexLibraryController`**

Use one enum for the page state (`initial`, `loading`, `ready`, `empty`, `failure`) and separate booleans for refresh/mutation. Keep the last successful list on transient failures. Poll active jobs every second in tests and every two seconds in production; stop polling on completed/failed/dispose.

Never optimistically remove or reindex a row. After backend success, refetch the page. Map these backend codes exactly:

| Code | UI message |
|---|---|
| `INDEX_MUTATION_CONFLICT` | 另一项索引操作正在进行，请稍后重试。 |
| `FILE_NOT_INDEXED` | 此文件已不在索引中，列表将刷新。 |
| `SOURCE_FILE_NOT_FOUND` | 源文件不存在，无法重新索引。 |
| `STORAGE_UNAVAILABLE` | 索引存储暂时不可用。 |
| `SERVICE_UNAVAILABLE` | 后端服务暂时不可用。 |

- [ ] **Step 5: Verify and commit**

```powershell
dart format lib/core/platform/directory_picker.dart lib/features/library/presentation/index_library_controller.dart test/features/library test/support
flutter test test/features/library/index_library_controller_test.dart
flutter analyze
git add lib/core/platform/directory_picker.dart lib/features/library/presentation/index_library_controller.dart test/features/library test/support
git commit -m "feat: manage Flutter index library state"
```

### Task 4: Build the file-library page

**Files:**
- Create: `frontend/lib/features/library/presentation/index_library_page.dart`
- Create: `frontend/lib/features/library/presentation/widgets/index_job_panel.dart`
- Create: `frontend/lib/features/library/presentation/widgets/indexed_file_tile.dart`
- Create: `frontend/test/features/library/index_library_page_test.dart`

- [ ] **Step 1: Write failing widget tests**

Test a 1280×720 surface and a 600×900 surface. Cover:

- page title, file count, refresh, add-directory action;
- Web-disabled add action and explanatory text;
- loading skeleton, empty state, retained-list error banner;
- pagination previous/next enablement;
- file name, full path tooltip, MIME, size, modified time, and record count;
- open and copy-path actions on supported desktop builds;
- indexing progress and processed/succeeded/failed counters;
- failure-detail expansion;
- reindex confirmation dialog;
- remove confirmation dialog names the exact file and warns that only index records are removed;
- destructive action is disabled while another mutation is running;
- no overflow at 200% text scale.

- [ ] **Step 2: Verify RED**

```powershell
flutter test test/features/library/index_library_page_test.dart
```

- [ ] **Step 3: Implement page composition**

Use this structure:

```text
Column
  Header(title, total count, refresh, add directory)
  IndexJobPanel when a job exists
  Inline error banner when a recoverable error exists
  Expanded list / empty / loading / failure state
  Pagination controls when total > pageSize
```

At widths below 760, stack metadata and actions vertically. At wider sizes, use a row with a flexible path column. File paths must wrap or ellipsize; never force horizontal scrolling.

`IndexedFileTile` accepts one `IndexedFile`, `FileLauncher`, and `PathClipboard`. Use the existing safe launcher/clipboard boundaries from the search workbench. Desktop builds expose open and copy; Android/Web disable open with an explanatory tooltip while preserving copy. A missing or denied file produces a row-local, actionable error and never removes the catalog entry.

- [ ] **Step 4: Implement guarded dialogs**

Reindex dialog primary action label is `重新索引`. Remove dialog primary action label is `从索引移除`, uses the error color, and includes: `不会删除磁盘上的原文件。`

After a successful mutation, show a `SnackBar`; after failure, keep the row and show an error banner containing what happened, the likely reason when known, and a retry/refresh action. Never expose a stack trace or raw exception object.

- [ ] **Step 5: Verify and commit**

```powershell
dart format lib/features/library/presentation test/features/library/index_library_page_test.dart
flutter test test/features/library/index_library_page_test.dart
flutter analyze
git add lib/features/library/presentation test/features/library/index_library_page_test.dart
git commit -m "feat: build Flutter index library page"
```

### Task 5: Persist application settings

**Files:**
- Create: `frontend/lib/features/settings/domain/app_settings.dart`
- Create: `frontend/lib/features/settings/data/settings_repository.dart`
- Create: `frontend/lib/features/settings/presentation/settings_controller.dart`
- Create: `frontend/test/features/settings/settings_repository_test.dart`
- Create: `frontend/test/features/settings/settings_controller_test.dart`

- [ ] **Step 1: Write failing repository and controller tests**

Cover defaults, round-trip persistence, malformed stored values falling back independently, recovery-key reporting, URL validation, save failure, and reset. Use an in-memory store fake; do not touch process preferences in unit tests.

Required defaults:

```dart
const defaultSettings = AppSettings(
  backendBaseUrl: 'http://127.0.0.1:8000',
  themeMode: AppThemePreference.system,
  highContrast: false,
  textScale: 1.0,
  reduceMotion: false,
);
```

Allowed text scales are exactly `1.0`, `1.25`, `1.5`, and `2.0`.

- [ ] **Step 2: Verify RED**

```powershell
flutter test test/features/settings/settings_repository_test.dart test/features/settings/settings_controller_test.dart
```

- [ ] **Step 3: Implement settings models and store boundary**

Define `SettingsStore` with typed async getters/setters and implement it with `SharedPreferencesAsync`. Persist under these keys:

```text
week5.backendBaseUrl
week5.themeMode
week5.highContrast
week5.textScale
week5.reduceMotion
```

`AppSettings.copyWith` returns an immutable value. `SettingsRepository.load` returns `SettingsLoadResult(settings, recoveredKeys)`, validates each field independently, and always returns a usable object. A malformed value is replaced only for that key and its key is included in `recoveredKeys`.

- [ ] **Step 4: Implement URL normalization and controller lifecycle**

Accept only an absolute `http` or `https` URI with a non-empty host and no query/fragment. Remove a trailing slash. Reject credentials. `SettingsController` exposes draft URL text, saved settings, validation error, busy state, `load`, `save`, and `reset`.

Save all fields before publishing new settings. If persistence fails, retain the previously saved settings and expose `无法保存设置，请重试。`. After loading recovered keys, expose a dismissible warning: `部分设置数据无效，已恢复安全默认值。` with a `查看已恢复项目` action.

- [ ] **Step 5: Verify and commit**

```powershell
dart format lib/features/settings/domain lib/features/settings/data lib/features/settings/presentation/settings_controller.dart test/features/settings
flutter test test/features/settings/settings_repository_test.dart test/features/settings/settings_controller_test.dart
flutter analyze
git add lib/features/settings test/features/settings
git commit -m "feat: persist Flutter application settings"
```

### Task 6: Build the settings page

**Files:**
- Create: `frontend/lib/features/settings/presentation/settings_page.dart`
- Create: `frontend/test/features/settings/settings_page_test.dart`

- [ ] **Step 1: Write failing widget tests**

Cover:

- backend URL label and inline validation;
- system/light/dark selection;
- high-contrast switch;
- text scale segmented selection including 200%;
- reduce-motion switch;
- save success and failure feedback;
- corrupted-setting recovery warning and recovered-key details;
- reset confirmation;
- keyboard activation;
- 200% text scale at 600×900 without overflow.

- [ ] **Step 2: Verify RED**

```powershell
flutter test test/features/settings/settings_page_test.dart
```

- [ ] **Step 3: Implement the page**

Use a scrollable `ListView` with four named sections: `后端连接`, `外观`, `无障碍`, `重置`. Every switch has a visible label and description. The save button is disabled while busy or URL-invalid. Display `Android 模拟器通常使用 http://10.0.2.2:8000` as supporting guidance, not as an automatic rewrite.

- [ ] **Step 4: Verify and commit**

```powershell
dart format lib/features/settings/presentation/settings_page.dart test/features/settings/settings_page_test.dart
flutter test test/features/settings/settings_page_test.dart
flutter analyze
git add lib/features/settings/presentation/settings_page.dart test/features/settings/settings_page_test.dart
git commit -m "feat: build Flutter settings page"
```

### Task 7: Compose runtime services and replace placeholders

**Files:**
- Modify: `frontend/lib/app/content_retrieval_app.dart`
- Modify: `frontend/lib/features/shell/app_shell.dart`
- Delete: `frontend/lib/features/placeholders/index_library_page.dart`
- Delete: `frontend/lib/features/placeholders/settings_page.dart`
- Modify: `frontend/test/widget_test.dart`

- [ ] **Step 1: Write failing application integration tests**

Inject fake settings repository, transport factory, picker, launcher, and clipboard. Assert:

- settings load before runtime services are created;
- saving a different base URL disposes the old status/search/library controllers and closes the old transport exactly once;
- search, library, and status then use the new transport;
- changing only theme/text scale does not rebuild the transport;
- restart loads persisted settings before the first visible application frame;
- recovered settings publish a visible warning without blocking startup;
- real pages replace both placeholder sentences.

- [ ] **Step 2: Verify RED**

```powershell
flutter test test/widget_test.dart
```

- [ ] **Step 3: Introduce one runtime owner**

Inside `content_retrieval_app.dart`, define a private `_AppServices` that owns transport and all API/controller instances. Its `dispose` order is library/status/search controllers, then transport. Recreate it only when normalized `backendBaseUrl` changes.

The `MaterialApp` uses saved settings:

```dart
themeMode: settings.themeMode.flutterValue,
theme: AppTheme.light(highContrast: settings.highContrast),
darkTheme: AppTheme.dark(highContrast: settings.highContrast),
builder: (context, child) => MediaQuery(
  data: MediaQuery.of(context).copyWith(
    textScaler: TextScaler.linear(settings.textScale),
    disableAnimations: settings.reduceMotion,
  ),
  child: child!,
),
```

The accessibility plan will refine system-scale composition; this task establishes persistence and visible behavior.

- [ ] **Step 4: Replace shell placeholders**

Change `AppShell` to accept `searchPage`, `indexLibraryPage`, and `settingsPage`; keep the `IndexedStack`. Delete placeholder source files only after imports and tests use real pages.

- [ ] **Step 5: Verify and commit**

```powershell
dart format lib/app lib/features/shell test/widget_test.dart
flutter test
flutter analyze
git add lib/app lib/features/shell lib/features/placeholders test/widget_test.dart
git commit -m "feat: connect Flutter library and settings"
```

### Task 8: Run feature and Windows integration verification

**Files:**
- Verify: `frontend/lib/`
- Verify: `frontend/test/`

- [ ] **Step 1: Run deterministic checks**

```powershell
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build windows --debug
```

Expected: all commands exit 0.

- [ ] **Step 2: Run real backend workflow**

With `tools/start-mvp.ps1` running, verify:

1. Add a folder containing TXT/PDF/DOCX/JPG/PNG.
2. Observe queued/running/completed state and counters.
3. Open the file catalog and page through it.
4. Reindex one existing source.
5. Remove one source from the index and confirm the original file remains on disk.
6. Enter an unreachable backend URL and verify offline state.
7. Restore the valid URL and verify reconnection.
8. Change theme, high contrast, 200% text, and reduce motion; restart and verify persistence.

- [ ] **Step 3: Audit and commit verification fixes**

```powershell
git diff --check
git status --short
```

Commit only source/test fixes. Do not add build directories, local preferences, indexed content, or model files.

## Plan self-review checklist

- Contract coverage: every required backend library endpoint and stable error code has a client test.
- Mutation safety: no destructive file deletion exists; remove affects index records only and requires confirmation.
- Persistence coverage: every setting has a default, validation, storage key, failure path, and restart test.
- Platform scope: Android/Web explicitly disable desktop-path indexing; Android emulator backend guidance remains visible for search and settings validation.
- Accessibility handoff: semantic refinement and system text-scale composition are owned by `2026-08-10-flutter-accessibility.md`.
