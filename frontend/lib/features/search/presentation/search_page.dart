import 'dart:async';

import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/core/presentation/workspace_header.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:content_retrieval_app/features/search/presentation/search_controller.dart';
import 'package:content_retrieval_app/features/search/presentation/widgets/backend_status_indicator.dart';
import 'package:content_retrieval_app/features/search/presentation/widgets/search_filter_panel.dart';
import 'package:content_retrieval_app/features/search/presentation/widgets/search_stage.dart';
import 'package:content_retrieval_app/features/search/presentation/widgets/search_state_view.dart';
import 'package:content_retrieval_app/features/status/backend_status_controller.dart';
import 'package:content_retrieval_app/features/status/backend_status_models.dart';
import 'package:flutter/material.dart' hide SearchController;
import 'package:flutter/services.dart';

final class SearchPage extends StatefulWidget {
  const SearchPage({
    super.key,
    required this.controller,
    required this.statusController,
    required this.fileLauncher,
    required this.pathClipboard,
  });

  final SearchController controller;
  final BackendStatusController statusController;
  final FileLauncher fileLauncher;
  final PathClipboard pathClipboard;

  @override
  State<SearchPage> createState() => _SearchPageState();
}

final class _SearchPageState extends State<SearchPage> {
  static const _filterBreakpoint = 1100.0;

  late final TextEditingController _queryController;
  late final FocusNode _queryFocusNode;
  late final FocusNode _filterButtonFocusNode;
  final GlobalKey _filterSheetKey = GlobalKey(
    debugLabel: 'search filter sheet',
  );
  bool _retainResultsForCurrentRequest = false;
  bool _filtersOpen = false;

  @override
  void initState() {
    super.initState();
    _queryController = TextEditingController(text: widget.controller.query);
    _queryFocusNode = FocusNode(debugLabel: 'search query');
    _filterButtonFocusNode = FocusNode(debugLabel: 'search filters');
  }

  @override
  void dispose() {
    _queryController.dispose();
    _queryFocusNode.dispose();
    _filterButtonFocusNode.dispose();
    super.dispose();
  }

  bool get _isOnline =>
      widget.statusController.state == BackendConnectionState.online;

  bool get _canSubmit =>
      _isOnline && widget.controller.state != SearchViewState.loading;

  Future<void> _submit() async {
    if (!_canSubmit) {
      return;
    }
    _retainResultsForCurrentRequest = false;
    widget.controller.setQuery(_queryController.text);
    await widget.controller.submit();
  }

  Future<void> _retry() async {
    if (!_canSubmit) {
      return;
    }
    final response = widget.controller.response;
    final normalizedQuery = widget.controller.query.trim().replaceAll(
      RegExp(r'\s+'),
      ' ',
    );
    final normalizedResponseQuery = response?.query.trim().replaceAll(
      RegExp(r'\s+'),
      ' ',
    );
    final canRetainResults =
        _retainResultsForCurrentRequest &&
        response != null &&
        response.hits.isNotEmpty &&
        normalizedResponseQuery == normalizedQuery;
    if (!canRetainResults) {
      await _submit();
      return;
    }
    await widget.controller.submit();
  }

  void _filtersChanged() {
    final normalizedQuery = widget.controller.query.trim().replaceAll(
      RegExp(r'\s+'),
      ' ',
    );
    if (normalizedQuery.isEmpty || !_canSubmit) {
      return;
    }
    final response = widget.controller.response;
    final normalizedResponseQuery = response?.query.trim().replaceAll(
      RegExp(r'\s+'),
      ' ',
    );
    _retainResultsForCurrentRequest =
        response != null &&
        response.hits.isNotEmpty &&
        normalizedResponseQuery == normalizedQuery;
    unawaited(widget.controller.submit());
  }

  void _clearFilters() {
    widget.controller.setMode(RetrievalMode.hybrid);
    for (final contentType in SearchContentType.values) {
      if (!widget.controller.contentTypes.contains(contentType)) {
        widget.controller.toggleContentType(contentType);
      }
    }
    _filtersChanged();
  }

  Future<void> _showFilters() async {
    if (_filtersOpen) {
      return;
    }
    _filtersOpen = true;
    try {
      await showModalBottomSheet<void>(
        context: context,
        showDragHandle: true,
        isScrollControlled: true,
        builder: (sheetContext) => CallbackShortcuts(
          key: _filterSheetKey,
          bindings: {
            const SingleActivator(LogicalKeyboardKey.escape): () {
              Navigator.of(sheetContext).pop();
            },
          },
          child: Focus(
            autofocus: true,
            child: SafeArea(
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  maxHeight: MediaQuery.sizeOf(sheetContext).height * 0.82,
                ),
                child: ListenableBuilder(
                  listenable: widget.controller,
                  builder: (context, _) => SearchFilterPanel(
                    key: const Key('search-filter-panel'),
                    controller: widget.controller,
                    enabled: widget.controller.state != SearchViewState.loading,
                    onChanged: _filtersChanged,
                    onReset: _clearFilters,
                  ),
                ),
              ),
            ),
          ),
        ),
      );
    } finally {
      _filtersOpen = false;
      _restoreFocusAfterFiltersClose();
    }
  }

  void _restoreFocusAfterFiltersClose() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      if (_filterSheetKey.currentContext != null) {
        _restoreFocusAfterFiltersClose();
        return;
      }
      final filterButtonContext = _filterButtonFocusNode.context;
      if (filterButtonContext != null && filterButtonContext.mounted) {
        _filterButtonFocusNode.requestFocus();
      } else {
        _queryFocusNode.requestFocus();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.keyK, control: true): () {
          _queryFocusNode.requestFocus();
        },
        const SingleActivator(LogicalKeyboardKey.escape): () {
          _queryFocusNode.unfocus();
        },
      },
      child: Focus(
        autofocus: true,
        child: ListenableBuilder(
          listenable: widget.statusController,
          builder: (context, _) => ListenableBuilder(
            listenable: widget.controller,
            builder: (context, _) => Column(
              children: [
                WorkspaceHeader(
                  title: '搜索本地资料',
                  description: '描述你记得的内容，找到对应文件和位置',
                  actions: [
                    BackendStatusIndicator(controller: widget.statusController),
                  ],
                ),
                const Divider(),
                Expanded(
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      final showPersistentFilters =
                          constraints.maxWidth >= _filterBreakpoint;
                      final main = _SearchMainColumn(
                        controller: widget.controller,
                        fileLauncher: widget.fileLauncher,
                        pathClipboard: widget.pathClipboard,
                        queryController: _queryController,
                        queryFocusNode: _queryFocusNode,
                        filterButtonFocusNode: _filterButtonFocusNode,
                        retainResultsForCurrentRequest:
                            _retainResultsForCurrentRequest,
                        canSubmit: _canSubmit,
                        showFilterButton: !showPersistentFilters,
                        onSubmit: _submit,
                        onRetry: _retry,
                        onShowFilters: _showFilters,
                        onClearFilters: _clearFilters,
                      );
                      if (!showPersistentFilters) {
                        return main;
                      }
                      return Row(
                        children: [
                          Expanded(child: main),
                          const VerticalDivider(),
                          SizedBox(
                            width: 292,
                            child: SearchFilterPanel(
                              key: const Key('search-filter-panel'),
                              controller: widget.controller,
                              enabled:
                                  widget.controller.state !=
                                  SearchViewState.loading,
                              onChanged: _filtersChanged,
                              onReset: _clearFilters,
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

final class _SearchMainColumn extends StatelessWidget {
  const _SearchMainColumn({
    required this.controller,
    required this.fileLauncher,
    required this.pathClipboard,
    required this.queryController,
    required this.queryFocusNode,
    required this.filterButtonFocusNode,
    required this.retainResultsForCurrentRequest,
    required this.canSubmit,
    required this.showFilterButton,
    required this.onSubmit,
    required this.onRetry,
    required this.onShowFilters,
    required this.onClearFilters,
  });

  final SearchController controller;
  final FileLauncher fileLauncher;
  final PathClipboard pathClipboard;
  final TextEditingController queryController;
  final FocusNode queryFocusNode;
  final FocusNode filterButtonFocusNode;
  final bool retainResultsForCurrentRequest;
  final bool canSubmit;
  final bool showFilterButton;
  final Future<void> Function() onSubmit;
  final Future<void> Function() onRetry;
  final VoidCallback onShowFilters;
  final VoidCallback onClearFilters;

  @override
  Widget build(BuildContext context) {
    final inlineError = controller.queryError != null
        ? '请输入搜索内容'
        : isSearchValidationError(controller.error)
        ? '搜索条件有误，请调整后重试'
        : null;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SearchStage(
            queryController: queryController,
            queryFocusNode: queryFocusNode,
            filterButtonFocusNode: filterButtonFocusNode,
            canSubmit: canSubmit,
            showFilterButton: showFilterButton,
            activeFilterCount: activeSearchFilterCount(controller),
            inlineError: inlineError,
            onQueryChanged: controller.setQuery,
            onSubmit: onSubmit,
            onShowFilters: onShowFilters,
          ),
          const SizedBox(height: 18),
          Expanded(
            child: SearchStateView(
              controller: controller,
              fileLauncher: fileLauncher,
              pathClipboard: pathClipboard,
              retainResultsForCurrentRequest: retainResultsForCurrentRequest,
              onRetry: canSubmit ? () => unawaited(onRetry()) : null,
              onClearFilters: onClearFilters,
            ),
          ),
        ],
      ),
    );
  }
}
