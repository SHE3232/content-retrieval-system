import 'dart:async';

import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/core/presentation/workspace_header.dart';
import 'package:content_retrieval_app/core/presentation/workspace_notice.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_controller.dart';
import 'package:content_retrieval_app/features/library/presentation/widgets/index_job_panel.dart';
import 'package:content_retrieval_app/features/library/presentation/widgets/indexed_file_tile.dart';
import 'package:content_retrieval_app/features/library/presentation/widgets/library_summary.dart';
import 'package:flutter/material.dart';

final class IndexLibraryPage extends StatefulWidget {
  const IndexLibraryPage({
    super.key,
    required this.controller,
    required this.fileLauncher,
    required this.pathClipboard,
    this.fileOpenSupported = true,
  });

  final IndexLibraryController controller;
  final FileLauncher fileLauncher;
  final PathClipboard pathClipboard;
  final bool fileOpenSupported;

  @override
  State<IndexLibraryPage> createState() => _IndexLibraryPageState();
}

final class _IndexLibraryPageState extends State<IndexLibraryPage> {
  String? _scheduledSuccessMessage;
  String? _pendingReindexFocusSourceKey;
  bool _isPageActive = true;
  late final FocusNode _refreshFocusNode;

  @override
  void initState() {
    super.initState();
    _refreshFocusNode = FocusNode(debugLabel: 'library-refresh-action');
    if (widget.controller.state == LibraryViewState.initial) {
      unawaited(widget.controller.load());
    }
  }

  @override
  void dispose() {
    _refreshFocusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    _isPageActive = Visibility.of(context);
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final controller = widget.controller;
        _scheduleSuccessFeedback(controller);
        _reconcilePendingFocus(controller);
        return Column(
          children: [
            WorkspaceHeader(
              title: '索引库',
              description: '管理可搜索的本地资料',
              actions: [
                Semantics(
                  label: '刷新索引库',
                  button: true,
                  enabled: !controller.isBusy,
                  child: ExcludeSemantics(
                    child: IconButton(
                      tooltip: '刷新索引库',
                      focusNode: _refreshFocusNode,
                      onPressed: controller.isBusy ? null : controller.refresh,
                      icon: const Icon(Icons.refresh),
                    ),
                  ),
                ),
                Semantics(
                  label: '添加资料文件夹',
                  button: true,
                  enabled:
                      controller.directoryPicker.isSupported &&
                      !controller.isBusy,
                  child: ExcludeSemantics(
                    child: FilledButton.icon(
                      onPressed:
                          controller.directoryPicker.isSupported &&
                              !controller.isBusy
                          ? controller.selectDirectoryAndStart
                          : null,
                      icon: const Icon(Icons.create_new_folder_outlined),
                      label: const Text('添加资料文件夹'),
                    ),
                  ),
                ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    LibrarySummary(
                      totalFiles: controller.total,
                      currentTaskFailures:
                          controller.activeJob?.result?.failedFiles ?? 0,
                    ),
                    if (!controller.directoryPicker.isSupported) ...[
                      const SizedBox(height: 8),
                      const Text(
                        '当前平台不支持添加本地资料文件夹，请使用 Windows、macOS 或 Linux 桌面版。',
                      ),
                    ],
                  ],
                ),
              ),
            ),
            if (controller.activeJob != null)
              IndexJobPanel(
                job: controller.activeJob!,
                failureDetails: controller.failureDetails,
                onShowFailures: () => _showFailures(controller.failureDetails!),
              ),
            if (controller.errorMessage != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
                child: WorkspaceNotice(
                  tone: WorkspaceNoticeTone.error,
                  message: controller.errorMessage!,
                  actionLabel: '重新尝试',
                  onAction: controller.isBusy
                      ? null
                      : controller.hasDirectoryPickerFailure
                      ? controller.selectDirectoryAndStart
                      : controller.refresh,
                  onDismiss: controller.clearError,
                  announce: true,
                ),
              ),
            Expanded(child: _body(controller)),
            if (controller.totalPages > 1)
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 12,
                ),
                child: Wrap(
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 12,
                  children: [
                    IconButton(
                      tooltip: '上一页',
                      onPressed: !controller.isBusy && controller.page > 1
                          ? controller.previousPage
                          : null,
                      icon: const Icon(Icons.chevron_left),
                    ),
                    Text('${controller.page} / ${controller.totalPages}'),
                    IconButton(
                      tooltip: '下一页',
                      onPressed:
                          !controller.isBusy &&
                              controller.page < controller.totalPages
                          ? controller.nextPage
                          : null,
                      icon: const Icon(Icons.chevron_right),
                    ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }

  void _scheduleSuccessFeedback(IndexLibraryController controller) {
    final message = controller.successMessage;
    if (message == null || message == _scheduledSuccessMessage) return;
    _scheduledSuccessMessage = message;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (controller.successMessage != message) {
        if (_scheduledSuccessMessage == message) {
          _scheduledSuccessMessage = null;
        }
        return;
      }
      final messenger = ScaffoldMessenger.of(context);
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(message)));
      _scheduledSuccessMessage = null;
      controller.clearSuccess();
    });
  }

  Widget _body(IndexLibraryController controller) {
    if (controller.state == LibraryViewState.loading &&
        controller.files.isEmpty) {
      return ListView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        children: [
          DecoratedBox(
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Column(
              children: [
                SizedBox(height: 112),
                Divider(height: 1),
                SizedBox(height: 112),
                Divider(height: 1),
                SizedBox(height: 112),
              ],
            ),
          ),
        ],
      );
    }
    if (controller.state == LibraryViewState.failure &&
        controller.files.isEmpty) {
      return const Center(child: Text('暂时无法显示索引库，请使用上方的“重新尝试”。'));
    }
    if (controller.files.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.folder_off_outlined, size: 48),
            SizedBox(height: 8),
            Text('索引库为空'),
            Text('添加资料文件夹后，可搜索文件会显示在这里。'),
          ],
        ),
      );
    }
    return ListView.separated(
      key: const Key('library-file-list'),
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
      itemCount: controller.files.length,
      separatorBuilder: (_, _) => const Divider(),
      itemBuilder: (context, index) {
        final file = controller.files[index];
        return IndexedFileTile(
          key: ValueKey(file.sourceKey),
          file: file,
          fileLauncher: widget.fileLauncher,
          pathClipboard: widget.pathClipboard,
          fileOpenSupported: widget.fileOpenSupported,
          actionsEnabled: !controller.isBusy,
          restoreMoreActionsFocus:
              _isPageActive && _pendingReindexFocusSourceKey == file.sourceKey,
          onMoreActionsFocusRestored: () {
            if (!mounted || _pendingReindexFocusSourceKey != file.sourceKey) {
              return;
            }
            setState(() => _pendingReindexFocusSourceKey = null);
          },
          onReindex: () => _confirmReindex(file),
          onRemove: () => _confirmRemove(file),
        );
      },
    );
  }

  Future<void> _confirmReindex(IndexedFile file) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('重新索引 ${file.name}？'),
        content: const Text('将重新解析源文件并更新搜索索引。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('重新索引文件'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    _pendingReindexFocusSourceKey = file.sourceKey;
    await widget.controller.reindex(file.sourceKey);
  }

  Future<void> _confirmRemove(IndexedFile file) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('从索引库移除 ${file.name}？'),
        content: const Text('不会删除磁盘上的原文件。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
              foregroundColor: Theme.of(context).colorScheme.onError,
            ),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('从索引库移除'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final deleted = await widget.controller.remove(file.sourceKey);
    if (deleted != null) _focusRefreshAction();
  }

  void _focusRefreshAction() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted &&
          _isPageActive &&
          !widget.controller.isBusy &&
          _refreshFocusNode.canRequestFocus) {
        _refreshFocusNode.requestFocus();
      }
    });
  }

  void _reconcilePendingFocus(IndexLibraryController controller) {
    final pendingSourceKey = _pendingReindexFocusSourceKey;
    if (pendingSourceKey == null || controller.isBusy) return;
    if (controller.files.any((file) => file.sourceKey == pendingSourceKey)) {
      return;
    }
    _pendingReindexFocusSourceKey = null;
    _focusRefreshAction();
  }

  Future<void> _showFailures(IndexFailureDetails details) {
    return showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('未处理文件详情'),
        content: SizedBox(
          width: 560,
          child: ListView(
            shrinkWrap: true,
            children: [
              for (final failure in details.failures)
                ListTile(
                  title: Text(failure.path),
                  subtitle: Text(_failureStageLabel(failure.stage)),
                ),
              if (details.error != null)
                const ListTile(
                  title: Text('任务未完成'),
                  subtitle: Text('任务未完成，请重新尝试；若问题持续，请检查本地检索服务。'),
                ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('关闭'),
          ),
        ],
      ),
    );
  }
}

String _failureStageLabel(String stage) {
  return switch (stage) {
    'discover' => '查找文件时失败',
    'parse' => '解析文件时失败',
    'embed' => '处理文件内容时失败',
    'persist' => '保存索引时失败',
    _ => '处理文件时失败',
  };
}
