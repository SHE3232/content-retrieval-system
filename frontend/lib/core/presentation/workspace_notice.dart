import 'package:flutter/material.dart';

enum WorkspaceNoticeTone { info, warning, error }

final class WorkspaceNotice extends StatelessWidget {
  const WorkspaceNotice({
    super.key,
    required this.tone,
    required this.message,
    this.actionLabel,
    this.onAction,
    this.onDismiss,
    this.announce = false,
  });

  final WorkspaceNoticeTone tone;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;
  final VoidCallback? onDismiss;
  final bool announce;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final style = switch (tone) {
      WorkspaceNoticeTone.info => _WorkspaceNoticeStyle(
        backgroundColor: scheme.surfaceContainerHigh,
        foregroundColor: scheme.onSurface,
        icon: Icons.info_outline,
      ),
      WorkspaceNoticeTone.warning => _WorkspaceNoticeStyle(
        backgroundColor: scheme.tertiaryContainer,
        foregroundColor: scheme.onTertiaryContainer,
        icon: Icons.warning_amber_outlined,
      ),
      WorkspaceNoticeTone.error => _WorkspaceNoticeStyle(
        backgroundColor: scheme.errorContainer,
        foregroundColor: scheme.onErrorContainer,
        icon: Icons.error_outline,
      ),
    };
    final actions = <Widget>[
      if (actionLabel != null)
        TextButton(
          onPressed: onAction,
          style: TextButton.styleFrom(
            minimumSize: const Size(48, 48),
            foregroundColor: style.foregroundColor,
          ),
          child: Text(actionLabel!),
        ),
      if (onDismiss != null)
        IconButton(
          onPressed: onDismiss,
          tooltip: '关闭提示',
          style: IconButton.styleFrom(
            minimumSize: const Size.square(48),
            foregroundColor: style.foregroundColor,
          ),
          icon: const Icon(Icons.close),
        ),
    ];
    final message = Text(
      this.message,
      style: Theme.of(
        context,
      ).textTheme.bodyMedium?.copyWith(color: style.foregroundColor),
    );
    final compact = MediaQuery.textScalerOf(context).scale(14) >= 21;

    return Semantics(
      key: const Key('workspace-notice'),
      container: true,
      liveRegion: announce,
      child: Material(
        color: style.backgroundColor,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final stacked = compact || constraints.maxWidth < 400;
              if (stacked) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(style.icon, color: style.foregroundColor),
                        const SizedBox(width: 12),
                        Expanded(child: message),
                      ],
                    ),
                    if (actions.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Padding(
                        padding: const EdgeInsets.only(left: 36),
                        child: Wrap(
                          spacing: 4,
                          runSpacing: 4,
                          children: actions,
                        ),
                      ),
                    ],
                  ],
                );
              }

              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(style.icon, color: style.foregroundColor),
                  const SizedBox(width: 12),
                  Expanded(child: message),
                  if (actions.isNotEmpty) ...[
                    const SizedBox(width: 8),
                    Flexible(
                      child: Wrap(spacing: 4, runSpacing: 4, children: actions),
                    ),
                  ],
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

final class _WorkspaceNoticeStyle {
  const _WorkspaceNoticeStyle({
    required this.backgroundColor,
    required this.foregroundColor,
    required this.icon,
  });

  final Color backgroundColor;
  final Color foregroundColor;
  final IconData icon;
}
