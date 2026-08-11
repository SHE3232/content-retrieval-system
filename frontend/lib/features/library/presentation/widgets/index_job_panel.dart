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
      IndexJobStatus.queued => '索引任务已排队',
      IndexJobStatus.running => '正在建立索引',
      IndexJobStatus.completed => '索引完成',
      IndexJobStatus.completedWithErrors => '索引完成，但有部分失败',
      IndexJobStatus.failed => '索引任务失败',
    };
    final announcement = result == null
        ? label
        : '索引完成，成功 ${result.indexedFiles}，失败 ${result.failedFiles}。';
    return LiveRegionMessage(
      message: announcement,
      excludeChildSemantics: false,
      child: Card(
        margin: const EdgeInsets.fromLTRB(20, 0, 20, 12),
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
                  '成功 ${result.indexedFiles}，失败 ${result.failedFiles}，'
                  '生成 ${result.indexedRecords} 条记录',
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
    );
  }
}
