import 'dart:async';

import 'package:content_retrieval_app/core/accessibility/live_region_message.dart';
import 'package:content_retrieval_app/features/status/backend_status_controller.dart';
import 'package:content_retrieval_app/features/status/backend_status_models.dart';
import 'package:flutter/material.dart';

final class BackendStatusIndicator extends StatelessWidget {
  const BackendStatusIndicator({super.key, required this.controller});

  final BackendStatusController controller;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (label, icon, color) = switch (controller.state) {
      BackendConnectionState.checking => (
        '正在检测后端',
        Icons.sync,
        theme.colorScheme.onSurfaceVariant,
      ),
      BackendConnectionState.online => (
        '后端在线',
        Icons.check_circle_outline,
        theme.brightness == Brightness.dark
            ? Colors.green.shade300
            : Colors.green.shade800,
      ),
      BackendConnectionState.offline => (
        '后端离线',
        Icons.error_outline,
        theme.colorScheme.error,
      ),
    };
    final announcement = switch (controller.state) {
      BackendConnectionState.checking => '正在检测后端。',
      BackendConnectionState.online =>
        '后端已连接，共索引 ${controller.stats?.fileCount ?? 0} 个文件。',
      BackendConnectionState.offline => '后端连接已断开。',
    };
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: ColoredBox(
        color: theme.colorScheme.surfaceContainerLow,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          child: LiveRegionMessage(
            message: announcement,
            excludeChildSemantics: false,
            child: Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 4,
              runSpacing: 4,
              children: [
                Icon(icon, size: 18, color: color),
                Text(
                  label,
                  style: theme.textTheme.labelLarge?.copyWith(color: color),
                ),
                if (controller.state == BackendConnectionState.offline)
                  TextButton.icon(
                    key: const Key('backend-refresh-button'),
                    onPressed: () => unawaited(controller.refresh()),
                    icon: const Icon(Icons.refresh, size: 18),
                    label: const Text('重新检测'),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
