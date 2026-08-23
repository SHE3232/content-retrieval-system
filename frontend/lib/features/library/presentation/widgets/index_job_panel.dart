import 'package:content_retrieval_app/core/accessibility/live_region_message.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:flutter/material.dart';

final class IndexJobPanel extends StatelessWidget {
  const IndexJobPanel({
    super.key,
    required this.job,
    required this.failureDetails,
    required this.onShowFailures,
  });

  final IndexJob job;
  final IndexFailureDetails? failureDetails;
  final VoidCallback onShowFailures;

  @override
  Widget build(BuildContext context) {
    final result = job.result;
    final label = switch (job.status) {
      IndexJobStatus.queued => '资料正在等待处理',
      IndexJobStatus.running => '正在添加资料',
      IndexJobStatus.completed => '资料已可搜索',
      IndexJobStatus.completedWithErrors => '部分文件未能加入索引库',
      IndexJobStatus.failed => '未能添加资料',
    };
    final announcement = result == null
        ? label
        : '$label。已添加 ${result.indexedFiles} 个文件，'
              '${result.failedFiles} 个文件需要处理。';
    return LiveRegionMessage(
      message: announcement,
      excludeChildSemantics: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
        child: DecoratedBox(
          key: const Key('index-job-panel'),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerLow,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      job.status == IndexJobStatus.failed
                          ? Icons.error_outline
                          : Icons.sync,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        label,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                  ],
                ),
                if (job.status == IndexJobStatus.queued ||
                    job.status == IndexJobStatus.running) ...[
                  const SizedBox(height: 12),
                  const LinearProgressIndicator(),
                ],
                if (result != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    '已添加 ${result.indexedFiles} 个文件，'
                    '${result.failedFiles} 个文件需要处理',
                  ),
                ],
                if (failureDetails != null) ...[
                  const SizedBox(height: 8),
                  TextButton.icon(
                    onPressed: onShowFailures,
                    icon: const Icon(Icons.rule_folder_outlined),
                    label: const Text('查看失败详情'),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
