import 'package:flutter/material.dart';

final class WorkspaceHeader extends StatelessWidget {
  const WorkspaceHeader({
    super.key,
    required this.title,
    required this.description,
    this.actions = const [],
  });

  final String title;
  final String description;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final text = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          container: true,
          header: true,
          child: Text(title, style: Theme.of(context).textTheme.headlineMedium),
        ),
        const SizedBox(height: 4),
        Text(
          description,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
    return LayoutBuilder(
      builder: (context, constraints) {
        final stacked =
            constraints.maxWidth < 620 ||
            MediaQuery.textScalerOf(context).scale(14) >= 21;
        return Padding(
          key: const Key('workspace-header'),
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
          child: stacked
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    text,
                    if (actions.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Wrap(spacing: 8, runSpacing: 8, children: actions),
                    ],
                  ],
                )
              : Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: text),
                    if (actions.isNotEmpty) ...[
                      const SizedBox(width: 16),
                      Flexible(
                        child: Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: actions,
                        ),
                      ),
                    ],
                  ],
                ),
        );
      },
    );
  }
}
