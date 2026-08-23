import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

final class IndexedFileTile extends StatefulWidget {
  const IndexedFileTile({
    super.key,
    required this.file,
    required this.fileLauncher,
    required this.pathClipboard,
    required this.onReindex,
    required this.onRemove,
    required this.actionsEnabled,
    required this.restoreMoreActionsFocus,
    required this.onMoreActionsFocusRestored,
    this.fileOpenSupported = true,
  });

  final IndexedFile file;
  final FileLauncher fileLauncher;
  final PathClipboard pathClipboard;
  final Future<void> Function() onReindex;
  final Future<void> Function() onRemove;
  final bool actionsEnabled;
  final bool restoreMoreActionsFocus;
  final VoidCallback onMoreActionsFocusRestored;
  final bool fileOpenSupported;

  @override
  State<IndexedFileTile> createState() => _IndexedFileTileState();
}

final class _IndexedFileTileState extends State<IndexedFileTile> {
  bool _opening = false;
  bool _copying = false;
  bool _showMoreActionsFocus = false;
  bool _restoreMoreActionsWhenEnabled = false;
  bool _pageFocusRestoreScheduled = false;
  String? _error;
  final GlobalKey<PopupMenuButtonState<_IndexedFileAction>>
  _moreActionsMenuKey = GlobalKey<PopupMenuButtonState<_IndexedFileAction>>();
  late final FocusNode _moreActionsFocusNode;

  @override
  void initState() {
    super.initState();
    _moreActionsFocusNode = FocusNode(
      debugLabel: 'more-actions-${widget.file.fileId}',
    );
  }

  @override
  void dispose() {
    _moreActionsFocusNode.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(IndexedFileTile oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!oldWidget.actionsEnabled &&
        widget.actionsEnabled &&
        _restoreMoreActionsWhenEnabled) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _restoreMoreActionsFocus();
      });
    }
    _schedulePageFocusRestore();
  }

  @override
  Widget build(BuildContext context) {
    _schedulePageFocusRestore();
    final file = widget.file;
    return Material(
      key: Key('indexed-file-row-${file.fileId}'),
      color: Colors.transparent,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(file.name, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            Semantics(
              label: file.path,
              child: Tooltip(
                message: file.path,
                child: ExcludeSemantics(
                  child: Text(
                    file.path,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                Text(file.mimeType),
                Text(_formatBytes(file.sizeBytes)),
                Text('${file.recordCount} 条记录'),
                Text(_formatDate(file.modifiedAt)),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                Tooltip(
                  message: widget.fileOpenSupported
                      ? '打开 ${file.name}'
                      : '当前平台不支持打开桌面文件',
                  child: FilledButton.tonalIcon(
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(48, 48),
                    ),
                    onPressed:
                        widget.actionsEnabled &&
                            widget.fileOpenSupported &&
                            !_opening
                        ? _open
                        : null,
                    icon: const Icon(Icons.open_in_new),
                    label: const Text('打开文件'),
                  ),
                ),
                Tooltip(
                  message: '复制 ${file.name} 的路径',
                  child: IconButton(
                    constraints: const BoxConstraints(
                      minWidth: 48,
                      minHeight: 48,
                    ),
                    onPressed: widget.actionsEnabled && !_copying
                        ? _copy
                        : null,
                    icon: const Icon(Icons.content_copy),
                  ),
                ),
                Semantics(
                  label: '${file.name} 的更多操作',
                  button: true,
                  enabled: widget.actionsEnabled,
                  onTap: widget.actionsEnabled ? _showMoreActionsMenu : null,
                  child: FocusableActionDetector(
                    key: Key('more-actions-${file.fileId}'),
                    enabled: widget.actionsEnabled,
                    focusNode: _moreActionsFocusNode,
                    descendantsAreFocusable: false,
                    descendantsAreTraversable: false,
                    includeFocusSemantics: false,
                    shortcuts: const <ShortcutActivator, Intent>{
                      SingleActivator(LogicalKeyboardKey.enter):
                          ActivateIntent(),
                      SingleActivator(LogicalKeyboardKey.space):
                          ActivateIntent(),
                    },
                    actions: <Type, Action<Intent>>{
                      ActivateIntent: CallbackAction<ActivateIntent>(
                        onInvoke: (_) {
                          _showMoreActionsMenu();
                          return null;
                        },
                      ),
                    },
                    onShowFocusHighlight: (show) {
                      if (mounted) {
                        setState(() => _showMoreActionsFocus = show);
                      }
                    },
                    child: ExcludeSemantics(
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(24),
                          border: Border.all(
                            color: _showMoreActionsFocus
                                ? Theme.of(context).colorScheme.primary
                                : Colors.transparent,
                            width: 2,
                          ),
                        ),
                        child: PopupMenuButton<_IndexedFileAction>(
                          key: _moreActionsMenuKey,
                          enabled: widget.actionsEnabled,
                          tooltip: '${file.name} 的更多操作',
                          padding: const EdgeInsets.all(12),
                          icon: const Icon(Icons.more_vert),
                          itemBuilder: (context) => const [
                            PopupMenuItem(
                              value: _IndexedFileAction.reindex,
                              child: ListTile(
                                leading: Icon(Icons.refresh),
                                title: Text('重新索引文件'),
                              ),
                            ),
                            PopupMenuItem(
                              value: _IndexedFileAction.remove,
                              child: ListTile(
                                leading: Icon(Icons.delete_outline),
                                title: Text('从索引库移除'),
                              ),
                            ),
                          ],
                          onCanceled: _restoreMoreActionsFocus,
                          onSelected: _performAction,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _schedulePageFocusRestore() {
    if (_pageFocusRestoreScheduled ||
        !widget.restoreMoreActionsFocus ||
        !widget.actionsEnabled) {
      return;
    }
    _pageFocusRestoreScheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _pageFocusRestoreScheduled = false;
      if (!mounted ||
          !widget.restoreMoreActionsFocus ||
          !widget.actionsEnabled) {
        return;
      }
      _moreActionsFocusNode.requestFocus();
      widget.onMoreActionsFocusRestored();
    });
  }

  void _showMoreActionsMenu() {
    if (!widget.actionsEnabled) return;
    _moreActionsMenuKey.currentState?.showButtonMenu();
  }

  void _restoreMoreActionsFocus() {
    if (!mounted) return;
    if (widget.actionsEnabled) {
      _restoreMoreActionsWhenEnabled = false;
      _moreActionsFocusNode.requestFocus();
    } else {
      _restoreMoreActionsWhenEnabled = true;
    }
  }

  Future<void> _performAction(_IndexedFileAction action) async {
    _restoreMoreActionsWhenEnabled = true;
    final callback = switch (action) {
      _IndexedFileAction.reindex => widget.onReindex,
      _IndexedFileAction.remove => widget.onRemove,
    };
    await callback();
    _restoreMoreActionsFocus();
  }

  Future<void> _open() async {
    setState(() {
      _opening = true;
      _error = null;
    });
    try {
      await widget.fileLauncher.open(widget.file.path);
    } on FileLaunchException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _opening = false);
    }
  }

  Future<void> _copy() async {
    setState(() {
      _copying = true;
      _error = null;
    });
    try {
      await widget.pathClipboard.copy(widget.file.path);
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('路径已复制')));
      }
    } on PathClipboardException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _copying = false);
    }
  }

  String _formatBytes(int value) {
    if (value < 1024) return '$value B';
    if (value < 1024 * 1024) return '${(value / 1024).toStringAsFixed(1)} KB';
    return '${(value / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  String _formatDate(DateTime value) {
    final local = value.toLocal();
    String two(int number) => number.toString().padLeft(2, '0');
    return '${local.year}-${two(local.month)}-${two(local.day)} '
        '${two(local.hour)}:${two(local.minute)}';
  }
}

enum _IndexedFileAction { reindex, remove }
