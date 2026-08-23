import 'package:flutter/material.dart';

final class SearchStage extends StatelessWidget {
  const SearchStage({
    super.key,
    required this.queryController,
    required this.queryFocusNode,
    required this.filterButtonFocusNode,
    required this.canSubmit,
    required this.showFilterButton,
    required this.activeFilterCount,
    required this.inlineError,
    required this.onQueryChanged,
    required this.onSubmit,
    required this.onShowFilters,
  });

  final TextEditingController queryController;
  final FocusNode queryFocusNode;
  final FocusNode filterButtonFocusNode;
  final bool canSubmit;
  final bool showFilterButton;
  final int activeFilterCount;
  final String? inlineError;
  final ValueChanged<String> onQueryChanged;
  final Future<void> Function() onSubmit;
  final VoidCallback onShowFilters;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return DecoratedBox(
      key: const Key('search-stage'),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LayoutBuilder(
              builder: (context, constraints) {
                final largeText =
                    MediaQuery.textScalerOf(context).scale(14) >= 21;
                final stacked = constraints.maxWidth < 720 || largeText;
                final field = TextField(
                  key: const Key('search-query-field'),
                  controller: queryController,
                  focusNode: queryFocusNode,
                  textInputAction: TextInputAction.search,
                  onChanged: onQueryChanged,
                  onSubmitted: canSubmit ? (_) => onSubmit() : null,
                  decoration: InputDecoration(
                    labelText: '搜索内容',
                    hintText: '输入关键词，或描述你记得的内容',
                    errorText: inlineError,
                    prefixIcon: const Icon(Icons.search),
                    suffixIconConstraints: const BoxConstraints(minWidth: 62),
                    suffixIcon: const Center(
                      child: Text('Ctrl K', style: TextStyle(fontSize: 11)),
                    ),
                  ),
                );
                final actions = Wrap(
                  alignment: WrapAlignment.end,
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    if (showFilterButton)
                      Semantics(
                        label: activeFilterCount == 0
                            ? '筛选'
                            : '筛选，$activeFilterCount 个限制',
                        button: true,
                        onTap: onShowFilters,
                        excludeSemantics: true,
                        child: Badge(
                          key: const Key('search-filter-count'),
                          isLabelVisible: activeFilterCount > 0,
                          label: Text('$activeFilterCount'),
                          child: OutlinedButton.icon(
                            key: const Key('search-filter-button'),
                            focusNode: filterButtonFocusNode,
                            onPressed: onShowFilters,
                            icon: const Icon(Icons.tune),
                            label: const Text('筛选'),
                          ),
                        ),
                      ),
                    FilledButton.icon(
                      key: const Key('search-submit-button'),
                      onPressed: canSubmit ? onSubmit : null,
                      icon: const Icon(Icons.search),
                      label: const Text('搜索资料'),
                    ),
                  ],
                );
                if (stacked) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [field, const SizedBox(height: 10), actions],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: field),
                    const SizedBox(width: 10),
                    actions,
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
