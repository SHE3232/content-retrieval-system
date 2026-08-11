import 'dart:async';

import 'package:content_retrieval_app/core/accessibility/live_region_message.dart';
import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:content_retrieval_app/features/search/presentation/search_controller.dart';
import 'package:content_retrieval_app/features/search/presentation/widgets/search_filter_panel.dart';
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
                _BackendStatusBar(controller: widget.statusController),
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
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: TextField(
                  key: const Key('search-query-field'),
                  controller: queryController,
                  focusNode: queryFocusNode,
                  textInputAction: TextInputAction.search,
                  onChanged: controller.setQuery,
                  onSubmitted: canSubmit ? (_) => onSubmit() : null,
                  decoration: InputDecoration(
                    labelText: '搜索内容',
                    hintText: '输入文件名或内容关键词',
                    errorText: inlineError,
                    prefixIcon: const Icon(Icons.search),
                  ),
                ),
              ),
              if (showFilterButton) ...[
                const SizedBox(width: 10),
                OutlinedButton.icon(
                  key: const Key('search-filter-button'),
                  onPressed: onShowFilters,
                  icon: const Icon(Icons.tune),
                  label: const Text('筛选'),
                ),
              ],
              const SizedBox(width: 10),
              FilledButton.icon(
                key: const Key('search-submit-button'),
                onPressed: canSubmit ? onSubmit : null,
                icon: const Icon(Icons.search),
                label: const Text('搜索'),
              ),
            ],
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

final class _BackendStatusBar extends StatelessWidget {
  const _BackendStatusBar({required this.controller});

  final BackendStatusController controller;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (label, icon, color) = switch (controller.state) {
      BackendConnectionState.checking => (
        '正在检测后端',
        Icons.sync,
        theme.colorScheme.onSurfaceVariant,
      ),
      BackendConnectionState.online => (
        '后端在线',
        Icons.check_circle_outline,
        theme.brightness == Brightness.dark
            ? Colors.green.shade300
            : Colors.green.shade800,
      ),
      BackendConnectionState.offline => (
        '后端离线',
        Icons.error_outline,
        theme.colorScheme.error,
      ),
    };
    final announcement = switch (controller.state) {
      BackendConnectionState.checking => '正在检测后端。',
      BackendConnectionState.online =>
        '后端已连接，共索引 ${controller.stats?.fileCount ?? 0} 个文件。',
      BackendConnectionState.offline => '后端连接已断开。',
    };
    return ColoredBox(
      color: theme.colorScheme.surfaceContainerLow,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        child: LiveRegionMessage(
          message: announcement,
          excludeChildSemantics: false,
          child: Row(
            children: [
              Icon(icon, size: 18, color: color),
              const SizedBox(width: 8),
              Text(
                label,
                style: theme.textTheme.labelLarge?.copyWith(color: color),
              ),
              const Spacer(),
              if (controller.state == BackendConnectionState.offline)
                TextButton.icon(
                  key: const Key('backend-refresh-button'),
                  onPressed: () => unawaited(controller.refresh()),
                  icon: const Icon(Icons.refresh, size: 18),
                  label: const Text('重新检测'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
