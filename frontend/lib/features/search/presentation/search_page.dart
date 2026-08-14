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

  @override
  void initState() {
    super.initState();
    _queryController = TextEditingController(text: widget.controller.query);
    _queryFocusNode = FocusNode(debugLabel: 'search query');
  }

  @override
  void dispose() {
    _queryController.dispose();
    _queryFocusNode.dispose();
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
    widget.controller.setQuery(_queryController.text);
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

  void _showFilters() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(context).height * 0.82,
          ),
          child: ListenableBuilder(
            listenable: widget.controller,
            builder: (context, _) => SearchFilterPanel(
              key: const Key('search-filter-panel'),
              controller: widget.controller,
              enabled: widget.controller.state != SearchViewState.loading,
              onChanged: _filtersChanged,
            ),
          ),
        ),
      ),
    );
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
                  title: '搜索',
                  description: '在本地资料中找回你记得的内容',
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
                        canSubmit: _canSubmit,
                        showFilterButton: !showPersistentFilters,
                        onSubmit: _submit,
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
    required this.canSubmit,
    required this.showFilterButton,
    required this.onSubmit,
    required this.onShowFilters,
    required this.onClearFilters,
  });

  final SearchController controller;
  final FileLauncher fileLauncher;
  final PathClipboard pathClipboard;
  final TextEditingController queryController;
  final FocusNode queryFocusNode;
  final bool canSubmit;
  final bool showFilterButton;
  final Future<void> Function() onSubmit;
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
              onRetry: canSubmit ? () => unawaited(onSubmit()) : null,
              onClearFilters: onClearFilters,
            ),
          ),
        ],
      ),
    );
  }
}
