import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:content_retrieval_app/features/search/presentation/search_controller.dart';
import 'package:flutter/material.dart' hide SearchController;

int activeSearchFilterCount(SearchController controller) {
  var count = controller.mode == RetrievalMode.hybrid ? 0 : 1;
  count += SearchChannel.values.length - controller.channels.length;
  count += SearchContentType.values.length - controller.contentTypes.length;
  return count;
}

final class SearchFilterPanel extends StatefulWidget {
  const SearchFilterPanel({
    super.key,
    required this.controller,
    required this.enabled,
    required this.onChanged,
    required this.onReset,
  });

  final SearchController controller;
  final bool enabled;
  final VoidCallback onChanged;
  final VoidCallback onReset;

  @override
  State<SearchFilterPanel> createState() => _SearchFilterPanelState();
}

final class _SearchFilterPanelState extends State<SearchFilterPanel> {
  String? _channelError;

  void _setMode(RetrievalMode mode) {
    if (mode == widget.controller.mode) {
      return;
    }
    widget.controller.setMode(mode);
    setState(() => _channelError = null);
    widget.onChanged();
  }

  void _toggleChannel(SearchChannel channel) {
    final changed = widget.controller.toggleChannel(channel);
    if (!changed) {
      setState(() => _channelError = '至少保留一个检索通道');
      return;
    }
    setState(() => _channelError = null);
    widget.onChanged();
  }

  void _toggleContentType(SearchContentType contentType) {
    widget.controller.toggleContentType(contentType);
    widget.onChanged();
  }

  void _reset() {
    setState(() => _channelError = null);
    widget.onReset();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final theme = Theme.of(context);
        return ColoredBox(
          color: theme.colorScheme.surfaceContainerLow,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text('筛选结果', style: theme.textTheme.titleMedium),
                    ),
                    TextButton(
                      onPressed: widget.enabled ? _reset : null,
                      child: const Text('重置'),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                Text('检索模式', style: theme.textTheme.labelLarge),
                const SizedBox(height: 10),
                SizedBox(
                  width: double.infinity,
                  child: SegmentedButton<RetrievalMode>(
                    showSelectedIcon: false,
                    segments: const [
                      ButtonSegment(
                        value: RetrievalMode.exact,
                        label: Text('精确'),
                      ),
                      ButtonSegment(
                        value: RetrievalMode.hybrid,
                        label: Text('综合'),
                      ),
                      ButtonSegment(
                        value: RetrievalMode.semantic,
                        label: Text('语义'),
                      ),
                    ],
                    selected: {widget.controller.mode},
                    onSelectionChanged: widget.enabled
                        ? (selection) => _setMode(selection.single)
                        : null,
                  ),
                ),
                const SizedBox(height: 20),
                Text('检索通道', style: theme.textTheme.labelLarge),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final channel in SearchChannel.values)
                      FilterChip(
                        key: Key('search-channel-${channel.name}'),
                        label: Text(_channelLabel(channel)),
                        selected: widget.controller.channels.contains(channel),
                        onSelected: widget.enabled
                            ? (_) => _toggleChannel(channel)
                            : null,
                      ),
                  ],
                ),
                if (_channelError != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    _channelError!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 20),
                Text('内容类型', style: theme.textTheme.labelLarge),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final contentType in SearchContentType.values)
                      FilterChip(
                        key: Key('search-content-${contentType.name}'),
                        label: Text(_contentTypeLabel(contentType)),
                        selected: widget.controller.contentTypes.contains(
                          contentType,
                        ),
                        onSelected: widget.enabled
                            ? (_) => _toggleContentType(contentType)
                            : null,
                      ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

String searchChannelLabel(SearchChannel channel) => _channelLabel(channel);

String _channelLabel(SearchChannel channel) => switch (channel) {
  SearchChannel.keyword => '关键词',
  SearchChannel.textSemantic => '文本语义',
  SearchChannel.imageSemantic => '图像语义',
};

String _contentTypeLabel(SearchContentType contentType) =>
    switch (contentType) {
      SearchContentType.documents => '文档',
      SearchContentType.textFiles => '文本文件',
      SearchContentType.images => '图片',
    };
