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
                  minExtendedWidth: 214,
                  selectedIndex: _selectedIndex,
                  onDestinationSelected: (index) {
                    setState(() => _selectedIndex = index);
                  },
                  destinations: const [
                    NavigationRailDestination(
                      icon: Icon(Icons.search_outlined),
                      selectedIcon: Icon(Icons.search),
                      label: Text('搜索'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.library_books_outlined),
                      selectedIcon: Icon(Icons.library_books),
                      label: Text('索引库'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.settings_outlined),
                      selectedIcon: Icon(Icons.settings),
                      label: Text('设置'),
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
}
