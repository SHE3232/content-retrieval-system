import 'package:content_retrieval_app/features/placeholders/index_library_page.dart';
import 'package:content_retrieval_app/features/placeholders/settings_page.dart';
import 'package:flutter/material.dart';

final class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.searchPage});

  final Widget searchPage;

  @override
  State<AppShell> createState() => _AppShellState();
}

final class _AppShellState extends State<AppShell> {
  static const _desktopBreakpoint = 1000.0;

  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
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
                  onDestinationSelected: (index) {
                    setState(() => _selectedIndex = index);
                  },
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
                  child: IndexedStack(
                    index: _selectedIndex,
                    children: [
                      widget.searchPage,
                      const IndexLibraryPage(),
                      const SettingsPage(),
                    ],
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
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
