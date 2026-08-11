import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

final class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.searchPage,
    required this.indexLibraryPage,
    required this.settingsPage,
    this.onRefreshSearch,
    this.onRefreshLibrary,
  });

  final Widget searchPage;
  final Widget indexLibraryPage;
  final Widget settingsPage;
  final VoidCallback? onRefreshSearch;
  final VoidCallback? onRefreshLibrary;

  @override
  State<AppShell> createState() => _AppShellState();
}

final class _AppShellState extends State<AppShell> {
  static const _desktopBreakpoint = 1000.0;

  int _selectedIndex = 0;
  final Set<int> _visited = <int>{0};

  @override
  Widget build(BuildContext context) {
    return CallbackShortcuts(
      bindings: <ShortcutActivator, VoidCallback>{
        const SingleActivator(LogicalKeyboardKey.digit1, control: true): () =>
            _selectDestination(0),
        const SingleActivator(LogicalKeyboardKey.digit2, control: true): () =>
            _selectDestination(1),
        const SingleActivator(LogicalKeyboardKey.digit3, control: true): () =>
            _selectDestination(2),
        const SingleActivator(LogicalKeyboardKey.digit1, meta: true): () =>
            _selectDestination(0),
        const SingleActivator(LogicalKeyboardKey.digit2, meta: true): () =>
            _selectDestination(1),
        const SingleActivator(LogicalKeyboardKey.digit3, meta: true): () =>
            _selectDestination(2),
        const SingleActivator(LogicalKeyboardKey.f5): _refreshCurrent,
      },
      child: Focus(
        autofocus: true,
        child: Scaffold(
          body: SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final extended = constraints.maxWidth >= _desktopBreakpoint;

                return Row(
                  children: [
                    NavigationRail(
                      extended: extended,
                      scrollable: true,
                      minExtendedWidth: 214,
                      selectedIndex: _selectedIndex,
                      onDestinationSelected: _selectDestination,
                      destinations: [
                        NavigationRailDestination(
                          icon: _destinationIcon(
                            extended: extended,
                            label: '搜索',
                            icon: Icons.search_outlined,
                          ),
                          selectedIcon: _destinationIcon(
                            extended: extended,
                            label: '搜索',
                            icon: Icons.search,
                          ),
                          label: const Text('搜索'),
                        ),
                        NavigationRailDestination(
                          icon: _destinationIcon(
                            extended: extended,
                            label: '索引库',
                            icon: Icons.library_books_outlined,
                          ),
                          selectedIcon: _destinationIcon(
                            extended: extended,
                            label: '索引库',
                            icon: Icons.library_books,
                          ),
                          label: const Text('索引库'),
                        ),
                        NavigationRailDestination(
                          icon: _destinationIcon(
                            extended: extended,
                            label: '设置',
                            icon: Icons.settings_outlined,
                          ),
                          selectedIcon: _destinationIcon(
                            extended: extended,
                            label: '设置',
                            icon: Icons.settings,
                          ),
                          label: const Text('设置'),
                        ),
                      ],
                    ),
                    const VerticalDivider(),
                    Expanded(
                      child: FocusTraversalGroup(
                        policy: OrderedTraversalPolicy(),
                        child: Semantics(
                          container: true,
                          label: '当前页面：${_destinationLabel(_selectedIndex)}',
                          child: IndexedStack(
                            index: _selectedIndex,
                            children: [
                              widget.searchPage,
                              _visited.contains(1)
                                  ? widget.indexLibraryPage
                                  : const SizedBox.shrink(),
                              _visited.contains(2)
                                  ? widget.settingsPage
                                  : const SizedBox.shrink(),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }

  void _selectDestination(int index) {
    if (index == _selectedIndex && _visited.contains(index)) return;
    setState(() {
      _selectedIndex = index;
      _visited.add(index);
    });
  }

  void _refreshCurrent() {
    switch (_selectedIndex) {
      case 0:
        widget.onRefreshSearch?.call();
      case 1:
        widget.onRefreshLibrary?.call();
      case 2:
        break;
    }
  }

  String _destinationLabel(int index) {
    return switch (index) {
      0 => '搜索',
      1 => '索引库',
      _ => '设置',
    };
  }

  Widget _destinationIcon({
    required bool extended,
    required String label,
    required IconData icon,
  }) {
    final destinationIcon = Icon(icon);
    if (extended) {
      return destinationIcon;
    }
    return Tooltip(
      message: label,
      excludeFromSemantics: true,
      child: destinationIcon,
    );
  }
}
