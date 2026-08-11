import 'dart:async';

import 'package:content_retrieval_app/app/app_theme.dart';
import 'package:content_retrieval_app/core/api/http_json_transport.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/features/search/data/search_api_client.dart';
import 'package:content_retrieval_app/features/search/presentation/search_controller.dart';
import 'package:content_retrieval_app/features/search/presentation/search_page.dart';
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
  });

  final JsonTransport? transport;
  final FileLauncher? fileLauncher;
  final PathClipboard? pathClipboard;

  @override
  State<ContentRetrievalApp> createState() => _ContentRetrievalAppState();
}

final class _ContentRetrievalAppState extends State<ContentRetrievalApp> {
  late final JsonTransport _transport;
  late final BackendStatusController _statusController;
  late final SearchController _searchController;
  late final FileLauncher _fileLauncher;
  late final PathClipboard _pathClipboard;

  @override
  void initState() {
    super.initState();
    _transport =
        widget.transport ??
        HttpJsonTransport(
          baseUri: Uri.parse('http://127.0.0.1:8000'),
          timeout: const Duration(seconds: 15),
        );
    _statusController = BackendStatusController(
      BackendStatusClient(_transport),
    );
    _searchController = SearchController(SearchApiClient(_transport));
    _fileLauncher =
        widget.fileLauncher ??
        IoFileLauncher(platform: currentDesktopPlatform());
    _pathClipboard = widget.pathClipboard ?? SystemPathClipboard();
    unawaited(_statusController.start());
  }

  @override
  void dispose() {
    _statusController.dispose();
    _searchController.dispose();
    _transport.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '本地内容检索',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.system,
      home: AppShell(
        searchPage: SearchPage(
          controller: _searchController,
          statusController: _statusController,
          fileLauncher: _fileLauncher,
          pathClipboard: _pathClipboard,
        ),
      ),
    );
  }
}
