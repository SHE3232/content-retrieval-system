import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:content_retrieval_app/features/search/presentation/widgets/search_filter_panel.dart';
import 'package:flutter/material.dart';

final class SearchResultTile extends StatefulWidget {
  const SearchResultTile({
    super.key,
    required this.rowKey,
    required this.hit,
    required this.fileLauncher,
    required this.pathClipboard,
  });

  final Key rowKey;
  final SearchHit hit;
  final FileLauncher fileLauncher;
  final PathClipboard pathClipboard;

  @override
  State<SearchResultTile> createState() => _SearchResultTileState();
}

final class _SearchResultTileState extends State<SearchResultTile> {
  bool _opening = false;
  bool _copying = false;
  String? _launchError;
  String? _copyError;

  Future<void> _open() async {
    if (_opening) {
      return;
    }
    setState(() => _opening = true);
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
    } finally {
      if (mounted) {
        setState(() => _opening = false);
      }
    }
  }

  Future<void> _copyPath() async {
    if (_copying) {
      return;
    }
    setState(() => _copying = true);
    try {
      await widget.pathClipboard.copy(widget.hit.path);
      if (!mounted) {
        return;
      }
      setState(() => _copyError = null);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('路径已复制')));
    } on PathClipboardException catch (error) {
      if (mounted) {
        setState(() => _copyError = error.message);
      }
    } finally {
      if (mounted) {
        setState(() => _copying = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textScaler = MediaQuery.textScalerOf(context);
    final location = widget.hit.pageNumber != null
        ? '第 ${widget.hit.pageNumber} 页'
        : widget.hit.paragraphNumber != null
        ? '第 ${widget.hit.paragraphNumber} 段'
        : null;

    return Material(
      key: widget.rowKey,
      color: Colors.transparent,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final badge = Container(
              width: 44,
              height: 44,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: theme.colorScheme.secondaryContainer,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                _fileTypeLabel(widget.hit.name),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onSecondaryContainer,
                  fontWeight: FontWeight.w700,
                ),
              ),
            );
            final metadata = _metadata(theme, location);
            final actions = _actions();
            final stackActions =
                constraints.maxWidth < 560 || textScaler.scale(1) > 1.15;

            if (stackActions) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      badge,
                      const SizedBox(width: 12),
                      Expanded(child: metadata),
                    ],
                  ),
                  const SizedBox(height: 12),
                  SizedBox(width: double.infinity, child: actions),
                ],
              );
            }

            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                badge,
                const SizedBox(width: 12),
                Expanded(child: metadata),
                const SizedBox(width: 12),
                actions,
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _metadata(ThemeData theme, String? location) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        widget.hit.name,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: theme.textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.w600,
        ),
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
        container: true,
        label: '完整路径 ${widget.hit.path}',
        excludeSemantics: true,
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
              '命中：${searchChannelLabel(reason)}',
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
      if (_copyError != null) ...[
        const SizedBox(height: 8),
        Text(
          _copyError!,
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.error,
          ),
        ),
      ],
    ],
  );

  Widget _actions() => Wrap(
    alignment: WrapAlignment.end,
    spacing: 4,
    runSpacing: 4,
    children: [
      Semantics(
        container: true,
        button: true,
        enabled: !_opening,
        label: '打开 ${widget.hit.name}',
        onTap: _opening ? null : _open,
        excludeSemantics: true,
        child: FilledButton.tonalIcon(
          key: Key('open-${widget.hit.fileId}'),
          onPressed: _opening ? null : _open,
          icon: const Icon(Icons.open_in_new, size: 18),
          label: const Text('打开'),
        ),
      ),
      Semantics(
        container: true,
        button: true,
        enabled: !_copying,
        label: '复制 ${widget.hit.name} 的完整路径',
        onTap: _copying ? null : _copyPath,
        excludeSemantics: true,
        child: Tooltip(
          message: '复制完整路径',
          child: IconButton(
            key: Key('copy-path-${widget.hit.fileId}'),
            onPressed: _copying ? null : _copyPath,
            icon: const Icon(Icons.copy_outlined),
          ),
        ),
      ),
    ],
  );
}

String _fileTypeLabel(String name) {
  final dot = name.lastIndexOf('.');
  if (dot < 0 || dot == name.length - 1) return 'FILE';
  final extension = name.substring(dot + 1).toUpperCase();
  return extension.length <= 5 ? extension : 'FILE';
}
