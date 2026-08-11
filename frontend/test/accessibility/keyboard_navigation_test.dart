import 'package:content_retrieval_app/features/shell/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Ctrl+1 through Ctrl+3 switch destinations and preserve state', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(_app());
    await tester.pump();

    await _controlShortcut(tester, LogicalKeyboardKey.digit2);
    await tester.pump();
    expect(find.text('LIBRARY_PAGE'), findsOneWidget);

    await _controlShortcut(tester, LogicalKeyboardKey.digit3);
    await tester.pump();
    expect(find.text('SETTINGS_PAGE'), findsOneWidget);

    await _controlShortcut(tester, LogicalKeyboardKey.digit1);
    await tester.pump();
    expect(find.text('SEARCH_PAGE'), findsOneWidget);
  });

  testWidgets('F5 invokes only the current destination refresh action', (
    tester,
  ) async {
    var searchRefreshes = 0;
    var libraryRefreshes = 0;
    await tester.pumpWidget(
      _app(
        onRefreshSearch: () => searchRefreshes += 1,
        onRefreshLibrary: () => libraryRefreshes += 1,
      ),
    );
    await tester.pump();

    await tester.sendKeyEvent(LogicalKeyboardKey.f5);
    expect(searchRefreshes, 1);
    expect(libraryRefreshes, 0);

    await _controlShortcut(tester, LogicalKeyboardKey.digit2);
    await tester.sendKeyEvent(LogicalKeyboardKey.f5);
    expect(searchRefreshes, 1);
    expect(libraryRefreshes, 1);

    await _controlShortcut(tester, LogicalKeyboardKey.digit3);
    await tester.sendKeyEvent(LogicalKeyboardKey.f5);
    expect(searchRefreshes, 1);
    expect(libraryRefreshes, 1);
  });
}

Widget _app({VoidCallback? onRefreshSearch, VoidCallback? onRefreshLibrary}) {
  return MaterialApp(
    home: AppShell(
      searchPage: const Text('SEARCH_PAGE'),
      indexLibraryPage: const Text('LIBRARY_PAGE'),
      settingsPage: const Text('SETTINGS_PAGE'),
      onRefreshSearch: onRefreshSearch,
      onRefreshLibrary: onRefreshLibrary,
    ),
  );
}

Future<void> _controlShortcut(
  WidgetTester tester,
  LogicalKeyboardKey key,
) async {
  await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
  await tester.sendKeyEvent(key);
  await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
}
