import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:content_retrieval_app/features/search/presentation/widgets/search_filter_panel.dart';
import 'package:flutter/material.dart';

final class SearchResultTile extends StatefulWidget {
  const SearchResultTile({
    super.key,
    required this.hit,
    required this.fileLauncher,
    required this.pathClipboard,
  });

  final SearchHit hit;
  final FileLauncher fileLauncher;
  final PathClipboard pathClipboard;

  @override
  State<SearchResultTile> createState() => _SearchResultTileState();
}

final class _SearchResultTileState extends State<SearchResultTile> {
  String? _launchError;

  Future<void> _open() async {
    try {
      await widget.fileLauncher.open(widget.hit.path);
      if (mounted) {
        setState(() => _launchError = null);
      }
    } on FileLaunchException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _launchError = switch (error.kind) {
          FileLaunchErrorKind.notFound => '文件不存在或已被移动',
          FileLaunchErrorKind.launchFailed => '无法打开文件，请检查系统关联设置',
          FileLaunchErrorKind.unsupportedPlatform => '当前系统不支持打开文件',
        };
      });
    }
  }

  Future<void> _copyPath() async {
    await widget.pathClipboard.copy(widget.hit.path);
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('路径已复制')));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final location = widget.hit.pageNumber != null
        ? '第 ${widget.hit.pageNumber} 页'
        : widget.hit.paragraphNumber != null
        ? '第 ${widget.hit.paragraphNumber} 段'
        : null;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    widget.hit.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                FilledButton.tonalIcon(
                  key: Key('open-${widget.hit.fileId}'),
                  onPressed: _open,
                  icon: const Icon(Icons.open_in_new, size: 18),
                  label: const Text('打开'),
                ),
                const SizedBox(width: 4),
                Semantics(
                  container: true,
                  button: true,
                  label: '复制 ${widget.hit.name} 的完整路径',
                  excludeSemantics: true,
                  child: Tooltip(
                    message: '复制完整路径',
                    child: IconButton(
                      key: Key('copy-path-${widget.hit.fileId}'),
                      onPressed: _copyPath,
                      icon: const Icon(Icons.copy_outlined),
                    ),
                  ),
                ),
              ],
            ),
            if (widget.hit.snippet case final snippet?) ...[
              const SizedBox(height: 8),
              Text(snippet, style: theme.textTheme.bodyMedium),
            ],
            if (location != null) ...[
              const SizedBox(height: 8),
              Text(
                location,
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
            const SizedBox(height: 8),
            Semantics(
              label: '完整路径 ${widget.hit.path}',
              child: Tooltip(
                message: widget.hit.path,
                child: Text(
                  widget.hit.path,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                for (final reason in widget.hit.matchReasons)
                  Text(
                    searchChannelLabel(reason),
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.primary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
              ],
            ),
            if (_launchError != null) ...[
              const SizedBox(height: 8),
              Text(
                _launchError!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
