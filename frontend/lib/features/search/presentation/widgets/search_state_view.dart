import 'package:content_retrieval_app/core/accessibility/live_region_message.dart';
import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/core/presentation/workspace_notice.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:content_retrieval_app/features/search/presentation/search_controller.dart';
import 'package:content_retrieval_app/features/search/presentation/widgets/search_result_tile.dart';
import 'package:flutter/material.dart' hide SearchController;

final class SearchStateView extends StatelessWidget {
  const SearchStateView({
    super.key,
    required this.controller,
    required this.fileLauncher,
    required this.pathClipboard,
    required this.retainResultsForCurrentRequest,
    required this.onRetry,
    required this.onClearFilters,
  });

  final SearchController controller;
  final FileLauncher fileLauncher;
  final PathClipboard pathClipboard;
  final bool retainResultsForCurrentRequest;
  final VoidCallback? onRetry;
  final VoidCallback onClearFilters;

  @override
  Widget build(BuildContext context) => switch (controller.state) {
    SearchViewState.initial => _message(
      context,
      icon: Icons.manage_search,
      title: '说出你还记得的内容',
      body: '例如：“哪个 PDF 讲过键盘导航？”\n支持文档、文本文件和图片。',
    ),
    SearchViewState.loading =>
      retainResultsForCurrentRequest &&
              controller.response != null &&
              controller.response!.hits.isNotEmpty
          ? _retainedLoading(context, controller.response!)
          : _initialLoading(context),
    SearchViewState.success => _success(context, controller.response!),
    SearchViewState.empty => _empty(context),
    SearchViewState.failure => _failure(context),
  };

  Widget _initialLoading(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return LiveRegionMessage(
      message: '正在搜索“${controller.query.trim()}”。',
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: Material(
          color: scheme.surface,
          child: ListView.separated(
            padding: const EdgeInsets.only(bottom: 20),
            itemCount: 3,
            separatorBuilder: (_, _) => const Divider(),
            itemBuilder: (_, _) => Container(
              key: const Key('search-loading-skeleton'),
              height: 132,
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  FractionallySizedBox(
                    widthFactor: 0.35,
                    child: Container(
                      height: 14,
                      color: scheme.surfaceContainerHigh,
                    ),
                  ),
                  const SizedBox(height: 18),
                  FractionallySizedBox(
                    widthFactor: 0.82,
                    child: Container(
                      height: 10,
                      color: scheme.surfaceContainerHigh,
                    ),
                  ),
                  const SizedBox(height: 10),
                  FractionallySizedBox(
                    widthFactor: 0.58,
                    child: Container(
                      height: 10,
                      color: scheme.surfaceContainerHigh,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _retainedLoading(BuildContext context, SearchResponse response) {
    final theme = Theme.of(context);
    return _resultList(
      context,
      response,
      header: [
        LiveRegionMessage(
          key: const Key('search-updating-live-region'),
          message: '正在更新结果。',
          excludeChildSemantics: false,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '正在更新结果',
                key: const Key('search-summary'),
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              const LinearProgressIndicator(minHeight: 2),
            ],
          ),
        ),
        const SizedBox(height: 10),
      ],
    );
  }

  Widget _success(BuildContext context, SearchResponse response) {
    final theme = Theme.of(context);
    return _resultList(
      context,
      response,
      header: [
        LiveRegionMessage(
          message: '搜索完成，找到 ${response.hits.length} 条结果。',
          child: Text(
            '找到 ${response.hits.length} 条相关资料',
            key: const Key('search-summary'),
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        const SizedBox(height: 10),
      ],
    );
  }

  Widget _empty(BuildContext context) => _message(
    context,
    icon: Icons.search_off,
    title: '没有找到相关资料',
    body: '尝试调整搜索内容，或重置筛选条件',
    liveMessage: '搜索完成，没有找到相关资料。',
    action: FilledButton.tonal(
      key: const Key('clear-search-filters-button'),
      onPressed: onClearFilters,
      child: const Text('重置筛选'),
    ),
  );

  Widget _failure(BuildContext context) {
    final error = controller.error;
    final (title, body) = _safeErrorCopy(error);
    final retainedResponse = controller.response;
    if (retainResultsForCurrentRequest &&
        retainedResponse != null &&
        retainedResponse.hits.isNotEmpty) {
      final theme = Theme.of(context);
      return _resultList(
        context,
        retainedResponse,
        header: [
          WorkspaceNotice(
            tone: WorkspaceNoticeTone.error,
            message: '$title\n$body',
            actionLabel: '重新尝试',
            onAction: onRetry,
            announce: true,
          ),
          const SizedBox(height: 10),
          Text(
            '保留上次的 ${retainedResponse.hits.length} 条结果',
            key: const Key('search-summary'),
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 10),
        ],
      );
    }

    return _message(
      context,
      icon: _isValidationError(error) ? Icons.tune : Icons.error_outline,
      title: title,
      body: body,
      liveMessage: '$title。$body',
      action: FilledButton.tonal(
        key: const Key('search-retry-button'),
        onPressed: onRetry,
        child: const Text('重新尝试'),
      ),
    );
  }

  (String, String) _safeErrorCopy(ApiException? error) {
    if (_isValidationError(error)) {
      return ('请调整搜索条件', '搜索条件有误，请调整后重新尝试。');
    }
    if (error?.statusCode == 503) {
      return ('本地检索服务暂时不可用', '请稍后重新尝试。');
    }
    return switch (error?.kind) {
      ApiErrorKind.offline => ('无法连接本地检索服务', '请检查服务地址和运行状态。'),
      ApiErrorKind.timeout => ('搜索用时过长', '请重新尝试。'),
      ApiErrorKind.invalidResponse => ('无法读取搜索结果', '本地检索服务返回了无法读取的内容。'),
      ApiErrorKind.rejected || null => ('搜索失败', '当前结果未更新，请重新尝试。'),
    };
  }

  Widget _resultList(
    BuildContext context,
    SearchResponse response, {
    required List<Widget> header,
  }) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ...header,
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Material(
              key: const Key('search-result-list'),
              color: theme.colorScheme.surface,
              child: ListView.separated(
                padding: const EdgeInsets.only(bottom: 20),
                itemCount: response.hits.length,
                separatorBuilder: (_, _) => const Divider(),
                itemBuilder: (_, index) => SearchResultTile(
                  key: ValueKey((response, response.hits[index].fileId)),
                  rowKey: Key(
                    'search-result-row-${response.hits[index].fileId}',
                  ),
                  hit: response.hits[index],
                  fileLauncher: fileLauncher,
                  pathClipboard: pathClipboard,
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _message(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String body,
    Widget? action,
    String? liveMessage,
  }) {
    final theme = Theme.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: LiveRegionMessage(
          message: liveMessage ?? '$title。$body。',
          excludeChildSemantics: false,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 34, color: theme.colorScheme.onSurfaceVariant),
              const SizedBox(height: 12),
              Text(title, style: theme.textTheme.titleMedium),
              const SizedBox(height: 6),
              Text(
                body,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              if (action != null) ...[const SizedBox(height: 16), action],
            ],
          ),
        ),
      ),
    );
  }
}

bool isSearchValidationError(ApiException? error) => _isValidationError(error);

bool _isValidationError(ApiException? error) => error?.statusCode == 422;
