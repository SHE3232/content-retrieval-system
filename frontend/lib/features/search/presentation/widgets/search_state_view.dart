import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/features/search/presentation/search_controller.dart';
import 'package:content_retrieval_app/features/search/presentation/widgets/search_result_tile.dart';
import 'package:flutter/material.dart' hide SearchController;

final class SearchStateView extends StatelessWidget {
  const SearchStateView({
    super.key,
    required this.controller,
    required this.fileLauncher,
    required this.pathClipboard,
    required this.onRetry,
    required this.onClearFilters,
  });

  final SearchController controller;
  final FileLauncher fileLauncher;
  final PathClipboard pathClipboard;
  final VoidCallback onRetry;
  final VoidCallback onClearFilters;

  @override
  Widget build(BuildContext context) => switch (controller.state) {
    SearchViewState.initial => _message(
      context,
      icon: Icons.manage_search,
      title: '输入关键词开始搜索',
      body: '可按文件类型和检索通道缩小结果范围',
    ),
    SearchViewState.loading => _loading(context),
    SearchViewState.success => _success(context),
    SearchViewState.empty => _empty(context),
    SearchViewState.failure => _failure(context),
  };

  Widget _loading(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return ListView.separated(
      padding: const EdgeInsets.only(bottom: 20),
      itemCount: 3,
      separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (_, _) => Container(
        key: const Key('search-loading-skeleton'),
        height: 132,
        decoration: BoxDecoration(
          color: scheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: scheme.outlineVariant),
        ),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            FractionallySizedBox(
              widthFactor: 0.35,
              child: Container(height: 14, color: scheme.surfaceContainerHigh),
            ),
            const SizedBox(height: 18),
            FractionallySizedBox(
              widthFactor: 0.82,
              child: Container(height: 10, color: scheme.surfaceContainerHigh),
            ),
            const SizedBox(height: 10),
            FractionallySizedBox(
              widthFactor: 0.58,
              child: Container(height: 10, color: scheme.surfaceContainerHigh),
            ),
          ],
        ),
      ),
    );
  }

  Widget _success(BuildContext context) {
    final response = controller.response!;
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '候选 ${response.totalCandidates} 个，用时 ${response.elapsedMs.toStringAsFixed(2)} ms',
          key: const Key('search-summary'),
          style: theme.textTheme.labelLarge?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 12),
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.only(bottom: 20),
            itemCount: response.hits.length,
            separatorBuilder: (_, _) => const SizedBox(height: 12),
            itemBuilder: (_, index) => SearchResultTile(
              key: ValueKey(response.hits[index].fileId),
              hit: response.hits[index],
              fileLauncher: fileLauncher,
              pathClipboard: pathClipboard,
            ),
          ),
        ),
      ],
    );
  }

  Widget _empty(BuildContext context) => _message(
    context,
    icon: Icons.search_off,
    title: '未找到匹配内容',
    body: '尝试更换关键词或恢复完整筛选范围',
    action: FilledButton.tonal(
      key: const Key('clear-search-filters-button'),
      onPressed: onClearFilters,
      child: const Text('清除过滤'),
    ),
  );

  Widget _failure(BuildContext context) {
    final error = controller.error;
    if (_isValidationError(error)) {
      return _message(
        context,
        icon: Icons.tune,
        title: '请调整搜索条件',
        body: '修改查询后可重新搜索',
      );
    }
    final serviceUnavailable = error?.statusCode == 503;
    return _message(
      context,
      icon: Icons.error_outline,
      title: serviceUnavailable ? '搜索服务暂时不可用，请稍后重试' : '搜索失败，请稍后重试',
      body: '当前结果未更新',
      action: FilledButton.tonal(
        key: const Key('search-retry-button'),
        onPressed: onRetry,
        child: const Text('重试'),
      ),
    );
  }

  Widget _message(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String body,
    Widget? action,
  }) {
    final theme = Theme.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Semantics(
          container: true,
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
