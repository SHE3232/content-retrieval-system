import 'dart:async';

import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_controller.dart';
import 'package:content_retrieval_app/features/library/presentation/widgets/index_job_panel.dart';
import 'package:content_retrieval_app/features/library/presentation/widgets/indexed_file_tile.dart';
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
  @override
  void initState() {
    super.initState();
    if (widget.controller.state == LibraryViewState.initial) {
      unawaited(widget.controller.load());
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final controller = widget.controller;
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '索引库',
                          style: Theme.of(context).textTheme.headlineMedium,
                        ),
                        Text('共 ${controller.total} 个文件'),
                        if (!controller.directoryPicker.isSupported)
                          const Text('当前验证平台不支持桌面路径，请使用桌面版管理索引。'),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      IconButton(
                        tooltip: '刷新索引库',
                        onPressed: controller.isRefreshing
                            ? null
                            : controller.refresh,
                        icon: const Icon(Icons.refresh),
                      ),
                      FilledButton.icon(
                        onPressed:
                            controller.directoryPicker.isSupported &&
                                !controller.isMutationInProgress
                            ? controller.selectDirectoryAndStart
                            : null,
                        icon: const Icon(Icons.create_new_folder_outlined),
                        label: const Text('添加文件夹'),
                      ),
                    ],
                  ),
                ],
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
                child: MaterialBanner(
                  content: Text(controller.errorMessage!),
                  actions: [
                    TextButton(
                      onPressed: controller.refresh,
                      child: const Text('刷新重试'),
                    ),
                    TextButton(
                      onPressed: controller.clearError,
                      child: const Text('关闭'),
                    ),
                  ],
                ),
              ),
            if (controller.successMessage != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
                child: Semantics(
                  liveRegion: true,
                  child: MaterialBanner(
                    content: Text(controller.successMessage!),
                    actions: [
                      TextButton(
                        onPressed: controller.clearSuccess,
                        child: const Text('关闭'),
                      ),
                    ],
                  ),
                ),
              ),
            Expanded(child: _body(controller)),
            if (controller.totalPages > 1)
              Padding(
                padding: const EdgeInsets.all(12),
                child: Wrap(
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 12,
                  children: [
                    IconButton(
                      tooltip: '上一页',
                      onPressed: controller.page > 1
                          ? controller.previousPage
                          : null,
                      icon: const Icon(Icons.chevron_left),
                    ),
                    Text('${controller.page} / ${controller.totalPages}'),
                    IconButton(
                      tooltip: '下一页',
                      onPressed: controller.page < controller.totalPages
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

  Widget _body(IndexLibraryController controller) {
    if (controller.state == LibraryViewState.loading &&
        controller.files.isEmpty) {
      return ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        itemCount: 3,
        separatorBuilder: (_, _) => const SizedBox(height: 8),
        itemBuilder: (_, _) => const Card(child: SizedBox(height: 112)),
      );
    }
    if (controller.state == LibraryViewState.failure &&
        controller.files.isEmpty) {
      return const Center(child: Text('无法加载索引库，请刷新重试。'));
    }
    if (controller.files.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.folder_off_outlined, size: 48),
            SizedBox(height: 8),
            Text('索引库为空'),
            Text('在桌面版添加文件夹后，文件会显示在这里。'),
          ],
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
      itemCount: controller.files.length,
      separatorBuilder: (_, _) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final file = controller.files[index];
        return IndexedFileTile(
          key: ValueKey(file.sourceKey),
          file: file,
          fileLauncher: widget.fileLauncher,
          pathClipboard: widget.pathClipboard,
          fileOpenSupported: widget.fileOpenSupported,
          actionsEnabled: !controller.isMutationInProgress,
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
            child: const Text('重新索引'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await widget.controller.reindex(file.sourceKey);
    if (mounted && widget.controller.errorMessage == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('重新索引任务已完成')));
    }
  }

  Future<void> _confirmRemove(IndexedFile file) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('从索引移除 ${file.name}？'),
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
            child: const Text('从索引移除'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final deleted = await widget.controller.remove(file.sourceKey);
    if (mounted && deleted != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已从索引移除 ${deleted.deletedRecords} 条记录')),
      );
    }
  }

  Future<void> _showFailures(IndexFailureDetails details) {
    return showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('索引失败详情'),
        content: SizedBox(
          width: 560,
          child: ListView(
            shrinkWrap: true,
            children: [
              for (final failure in details.failures)
                ListTile(
                  title: Text(failure.path),
                  subtitle: Text('${failure.code} · ${failure.stage}'),
                ),
              if (details.error != null)
                ListTile(
                  title: Text(details.error!.code),
                  subtitle: const Text('任务异常结束，请重试或检查后端日志。'),
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
