import 'package:flutter/material.dart';

final class LibrarySummary extends StatelessWidget {
  const LibrarySummary({
    super.key,
    required this.totalFiles,
    required this.currentTaskFailures,
  });

  final int totalFiles;
  final int currentTaskFailures;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        Semantics(
          key: const Key('library-total-files'),
          label: '$totalFiles 个可搜索文件',
          child: ExcludeSemantics(
            child: Chip(
              avatar: const Icon(Icons.library_books_outlined),
              label: Text('$totalFiles 个可搜索文件'),
              backgroundColor: scheme.surfaceContainerLow,
            ),
          ),
        ),
        if (currentTaskFailures > 0)
          Semantics(
            label: '本次任务有 $currentTaskFailures 个文件需要处理',
            child: ExcludeSemantics(
              child: Chip(
                avatar: Icon(
                  Icons.warning_amber_outlined,
                  color: scheme.onErrorContainer,
                ),
                label: Text('本次任务有 $currentTaskFailures 个文件需要处理'),
                labelStyle: TextStyle(color: scheme.onErrorContainer),
                backgroundColor: scheme.errorContainer,
              ),
            ),
          ),
      ],
    );
  }
}
