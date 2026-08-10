import 'package:content_retrieval_app/app/app_theme.dart';
import 'package:content_retrieval_app/features/placeholders/index_library_page.dart';
import 'package:content_retrieval_app/features/placeholders/settings_page.dart';
import 'package:content_retrieval_app/features/shell/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows all destinations and the injected search page initially', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));

    expect(find.text('搜索'), findsOneWidget);
    expect(find.text('索引库'), findsOneWidget);
    expect(find.text('设置'), findsOneWidget);
    expect(find.text('SEARCH_PAGE'), findsOneWidget);

    final rail = tester.widget<NavigationRail>(find.byType(NavigationRail));
    expect(rail.selectedIndex, 0);
  });

  testWidgets('opens the index library placeholder', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));
    await tester.tap(find.text('索引库'));
    await tester.pump();

    final page = find.byType(IndexLibraryPage);
    expect(
      find.descendant(of: page, matching: find.text('索引库')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: page, matching: find.text('索引库功能将在后续版本提供')),
      findsOneWidget,
    );
    expect(
      tester.widget<NavigationRail>(find.byType(NavigationRail)).selectedIndex,
      1,
    );
  });

  testWidgets('opens the settings placeholder', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));
    await tester.tap(find.text('设置'));
    await tester.pump();

    final page = find.byType(SettingsPage);
    expect(
      find.descendant(of: page, matching: find.text('设置')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: page, matching: find.text('设置功能将在后续版本提供')),
      findsOneWidget,
    );
    expect(
      tester.widget<NavigationRail>(find.byType(NavigationRail)).selectedIndex,
      2,
    );
  });

  testWidgets('extends the navigation rail at desktop width', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));

    final rail = tester.widget<NavigationRail>(find.byType(NavigationRail));
    expect(rail.extended, isTrue);
    expect(rail.minExtendedWidth, 214);
    expect(tester.takeException(), isNull);
  });

  testWidgets('collapses the navigation rail below desktop width', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(900, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));

    final rail = tester.widget<NavigationRail>(find.byType(NavigationRail));
    expect(rail.extended, isFalse);
    expect(rail.minExtendedWidth, 214);
    expect(tester.takeException(), isNull);
  });

  testWidgets('preserves the search child state across destination switches', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    var initializationCount = 0;

    await tester.pumpWidget(
      _buildApp(
        _StatefulSearchProbe(onInitialized: () => initializationCount += 1),
      ),
    );
    await tester.tap(find.text('INCREMENT_SEARCH'));
    await tester.pump();
    expect(find.text('SEARCH_COUNT:1'), findsOneWidget);

    await tester.tap(find.text('索引库'));
    await tester.pump();
    await tester.tap(find.text('搜索'));
    await tester.pump();

    expect(find.text('SEARCH_COUNT:1'), findsOneWidget);
    expect(initializationCount, 1);
  });

  testWidgets('uses matching destination icons and switches without overflow', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));

    var rail = tester.widget<NavigationRail>(find.byType(NavigationRail));
    expect(rail.destinations, hasLength(3));
    expect((rail.destinations[0].icon as Icon).icon, Icons.search_outlined);
    expect((rail.destinations[0].selectedIcon as Icon).icon, Icons.search);
    expect(
      (rail.destinations[1].icon as Icon).icon,
      Icons.library_books_outlined,
    );
    expect(
      (rail.destinations[1].selectedIcon as Icon).icon,
      Icons.library_books,
    );
    expect((rail.destinations[2].icon as Icon).icon, Icons.settings_outlined);
    expect((rail.destinations[2].selectedIcon as Icon).icon, Icons.settings);

    await tester.tap(find.text('索引库'));
    await tester.pump();
    rail = tester.widget<NavigationRail>(find.byType(NavigationRail));
    expect(rail.selectedIndex, 1);
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('设置'));
    await tester.pump();
    rail = tester.widget<NavigationRail>(find.byType(NavigationRail));
    expect(rail.selectedIndex, 2);
    expect(tester.takeException(), isNull);
  });

  test('builds coordinated light and dark Material 3 themes', () {
    final light = AppTheme.light();
    final dark = AppTheme.dark();
    final expectedLightScheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFF3659AD),
    );
    final expectedDarkScheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFF3659AD),
      brightness: Brightness.dark,
    );

    expect(light.useMaterial3, isTrue);
    expect(dark.useMaterial3, isTrue);
    expect(light.brightness, Brightness.light);
    expect(dark.brightness, Brightness.dark);
    expect(light.colorScheme.primary, expectedLightScheme.primary);
    expect(dark.colorScheme.primary, expectedDarkScheme.primary);
    expect(light.colorScheme.primary, isNot(dark.colorScheme.primary));

    for (final theme in [light, dark]) {
      final scheme = theme.colorScheme;
      expect(theme.inputDecorationTheme.filled, isTrue);
      expect(
        theme.inputDecorationTheme.fillColor,
        scheme.surfaceContainerHighest,
      );
      expect(theme.inputDecorationTheme.border, isA<OutlineInputBorder>());
      expect(
        (theme.inputDecorationTheme.border! as OutlineInputBorder).borderRadius,
        BorderRadius.circular(12),
      );
      expect(theme.chipTheme.shape, isA<RoundedRectangleBorder>());
      expect(theme.chipTheme.backgroundColor, scheme.surfaceContainerLow);
      expect(theme.chipTheme.selectedColor, scheme.secondaryContainer);
      expect(theme.navigationRailTheme.backgroundColor, scheme.surface);
      expect(
        theme.navigationRailTheme.indicatorColor,
        scheme.secondaryContainer,
      );
      expect(theme.navigationRailTheme.minWidth, 72);
      expect(theme.filledButtonTheme.style, isNotNull);
      expect(
        theme.filledButtonTheme.style!.minimumSize!.resolve({}),
        const Size(0, 48),
      );
      expect(
        theme.filledButtonTheme.style!.backgroundColor!.resolve({}),
        scheme.primary,
      );
      expect(theme.tooltipTheme.decoration, isA<BoxDecoration>());
      expect(
        (theme.tooltipTheme.decoration! as BoxDecoration).color,
        scheme.inverseSurface,
      );
      expect(theme.tooltipTheme.textStyle!.color, scheme.onInverseSurface);
      expect(
        theme.tooltipTheme.waitDuration,
        const Duration(milliseconds: 500),
      );
    }
  });

  for (final placeholder
      in <
        ({
          Widget page,
          Type pageType,
          String semanticsLabel,
          String title,
          String sentence,
        })
      >[
        (
          page: const IndexLibraryPage(),
          pageType: IndexLibraryPage,
          semanticsLabel: '索引库空状态',
          title: '索引库',
          sentence: '索引库功能将在后续版本提供',
        ),
        (
          page: const SettingsPage(),
          pageType: SettingsPage,
          semanticsLabel: '设置空状态',
          title: '设置',
          sentence: '设置功能将在后续版本提供',
        ),
      ]) {
    testWidgets(
      '${placeholder.pageType} is a semantic control-free empty state',
      (tester) async {
        await tester.binding.setSurfaceSize(const Size(1280, 720));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        final semantics = tester.ensureSemantics();

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            home: Scaffold(body: placeholder.page),
          ),
        );

        final page = find.byWidgetPredicate(
          (widget) => widget.runtimeType == placeholder.pageType,
        );
        expect(
          find.bySemanticsLabel(placeholder.semanticsLabel),
          findsOneWidget,
        );
        expect(
          find.descendant(of: page, matching: find.byType(Icon)),
          findsOneWidget,
        );
        expect(
          find.descendant(of: page, matching: find.text(placeholder.title)),
          findsOneWidget,
        );
        expect(
          find.descendant(of: page, matching: find.text(placeholder.sentence)),
          findsOneWidget,
        );
        expect(
          find.descendant(of: page, matching: find.byType(FilledButton)),
          findsNothing,
        );
        expect(
          find.descendant(of: page, matching: find.byType(OutlinedButton)),
          findsNothing,
        );
        expect(
          find.descendant(of: page, matching: find.byType(TextButton)),
          findsNothing,
        );
        expect(
          find.descendant(of: page, matching: find.byType(ElevatedButton)),
          findsNothing,
        );
        expect(
          find.descendant(of: page, matching: find.byType(IconButton)),
          findsNothing,
        );
        expect(
          find.descendant(of: page, matching: find.byType(TextField)),
          findsNothing,
        );
        expect(tester.takeException(), isNull);
        semantics.dispose();
      },
    );
  }
}

Widget _buildApp(Widget searchPage) {
  return MaterialApp(
    theme: AppTheme.light(),
    darkTheme: AppTheme.dark(),
    home: AppShell(searchPage: searchPage),
  );
}

final class _StatefulSearchProbe extends StatefulWidget {
  const _StatefulSearchProbe({required this.onInitialized});

  final VoidCallback onInitialized;

  @override
  State<_StatefulSearchProbe> createState() => _StatefulSearchProbeState();
}

final class _StatefulSearchProbeState extends State<_StatefulSearchProbe> {
  var _count = 0;

  @override
  void initState() {
    super.initState();
    widget.onInitialized();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text('SEARCH_COUNT:$_count'),
        TextButton(
          onPressed: () => setState(() => _count += 1),
          child: const Text('INCREMENT_SEARCH'),
        ),
      ],
    );
  }
}
