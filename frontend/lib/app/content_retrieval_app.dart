import 'dart:async';

import 'package:content_retrieval_app/app/app_theme.dart';
import 'package:content_retrieval_app/core/api/http_json_transport.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:content_retrieval_app/core/platform/directory_picker.dart';
import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/features/library/data/index_library_api_client.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_controller.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_page.dart';
import 'package:content_retrieval_app/features/search/data/search_api_client.dart';
import 'package:content_retrieval_app/features/search/presentation/search_controller.dart';
import 'package:content_retrieval_app/features/search/presentation/search_page.dart';
import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';
import 'package:content_retrieval_app/features/settings/data/settings_store_provider.dart';
import 'package:content_retrieval_app/features/settings/domain/app_settings.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_controller.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_page.dart';
import 'package:content_retrieval_app/features/shell/app_shell.dart';
import 'package:content_retrieval_app/features/status/backend_status_client.dart';
import 'package:content_retrieval_app/features/status/backend_status_controller.dart';
import 'package:flutter/material.dart' hide SearchController;

final class ContentRetrievalApp extends StatefulWidget {
  const ContentRetrievalApp({
    super.key,
    this.transport,
    this.fileLauncher,
    this.pathClipboard,
    this.directoryPicker,
    this.settingsStore,
  });

  final JsonTransport? transport;
  final FileLauncher? fileLauncher;
  final PathClipboard? pathClipboard;
  final DirectoryPicker? directoryPicker;
  final SettingsStore? settingsStore;

  @override
  State<ContentRetrievalApp> createState() => _ContentRetrievalAppState();
}

final class _ContentRetrievalAppState extends State<ContentRetrievalApp> {
  late final SettingsController _settingsController;
  late final FileLauncher _fileLauncher;
  late final PathClipboard _pathClipboard;
  late final DirectoryPicker _directoryPicker;

  JsonTransport? _transport;
  BackendStatusController? _statusController;
  SearchController? _searchController;
  IndexLibraryController? _libraryController;
  String? _activeBackendBaseUrl;
  bool _initialized = false;
  bool _disposed = false;

  @override
  void initState() {
    super.initState();
    _settingsController = SettingsController(
      SettingsRepository(widget.settingsStore ?? createPlatformSettingsStore()),
    );
    _fileLauncher = widget.fileLauncher ?? createPlatformFileLauncher();
    _pathClipboard = widget.pathClipboard ?? SystemPathClipboard();
    _directoryPicker =
        widget.directoryPicker ?? createPlatformDirectoryPicker();
    unawaited(_initialize());
  }

  Future<void> _initialize() async {
    try {
      await _settingsController.load();
    } catch (_) {
      // Defaults remain usable when the settings location cannot be read.
    }
    if (_disposed) return;
    _createServices(_settingsController.settings.backendBaseUrl);
    if (!mounted) return;
    setState(() => _initialized = true);
    unawaited(_statusController!.start());
  }

  void _createServices(String backendBaseUrl) {
    final transport =
        widget.transport ??
        HttpJsonTransport(
          baseUri: Uri.parse(backendBaseUrl),
          timeout: const Duration(seconds: 15),
        );
    _transport = transport;
    _statusController = BackendStatusController(BackendStatusClient(transport));
    _searchController = SearchController(SearchApiClient(transport));
    _libraryController = IndexLibraryController(
      service: IndexLibraryApiClient(transport),
      directoryPicker: _directoryPicker,
    );
    _activeBackendBaseUrl = backendBaseUrl;
  }

  void _applySavedSettings() {
    final nextBackendBaseUrl = _settingsController.settings.backendBaseUrl;
    if (widget.transport == null &&
        nextBackendBaseUrl != _activeBackendBaseUrl) {
      _disposeServices();
      _createServices(nextBackendBaseUrl);
      unawaited(_statusController!.start());
    } else {
      _activeBackendBaseUrl = nextBackendBaseUrl;
    }
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _disposed = true;
    _settingsController.dispose();
    _disposeServices();
    super.dispose();
  }

  void _disposeServices() {
    _statusController?.dispose();
    _searchController?.dispose();
    _libraryController?.dispose();
    _transport?.close();
    _statusController = null;
    _searchController = null;
    _libraryController = null;
    _transport = null;
  }

  @override
  Widget build(BuildContext context) {
    final settings = _settingsController.settings;
    return MaterialApp(
      title: '本地内容检索',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(highContrast: settings.highContrast),
      darkTheme: AppTheme.dark(highContrast: settings.highContrast),
      themeMode: _themeMode(settings.themeMode),
      builder: (context, child) {
        final mediaQuery = MediaQuery.of(context);
        return MediaQuery(
          data: mediaQuery.copyWith(
            textScaler: TextScaler.linear(settings.textScale),
            disableAnimations: settings.reduceMotion,
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
      home: !_initialized
          ? Scaffold(
              body: Center(
                child: Semantics(
                  liveRegion: true,
                  label: '正在加载设置',
                  child: CircularProgressIndicator(),
                ),
              ),
            )
          : AppShell(
              searchPage: SearchPage(
                controller: _searchController!,
                statusController: _statusController!,
                fileLauncher: _fileLauncher,
                pathClipboard: _pathClipboard,
              ),
              indexLibraryPage: IndexLibraryPage(
                controller: _libraryController!,
                fileLauncher: _fileLauncher,
                pathClipboard: _pathClipboard,
                fileOpenSupported:
                    widget.fileLauncher != null || platformFileActionsSupported,
              ),
              settingsPage: SettingsPage(
                controller: _settingsController,
                onSettingsSaved: _applySavedSettings,
              ),
            ),
    );
  }

  ThemeMode _themeMode(AppThemePreference preference) {
    return switch (preference) {
      AppThemePreference.system => ThemeMode.system,
      AppThemePreference.light => ThemeMode.light,
      AppThemePreference.dark => ThemeMode.dark,
    };
  }
}
