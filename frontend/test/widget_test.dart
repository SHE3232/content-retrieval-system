import 'dart:async';
import 'dart:io';

import 'package:content_retrieval_app/app/content_retrieval_app.dart';
import 'package:content_retrieval_app/app/app_theme.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:content_retrieval_app/features/library/presentation/index_library_page.dart';
import 'package:content_retrieval_app/features/search/presentation/search_page.dart';
import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_page.dart';
import 'package:content_retrieval_app/features/shell/app_shell.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fakes.dart';

void main() {
  testWidgets('connects the production application shell and themes', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final transport = FakeJsonTransport()
      ..getResponses.addAll(const <JsonResponse>[
        JsonResponse(statusCode: 200, body: null),
        JsonResponse(
          statusCode: 200,
          body: {
            'record_count': 3,
            'file_count': 2,
            'text_record_count': 2,
            'image_record_count': 1,
          },
        ),
        JsonResponse(
          statusCode: 200,
          body: {
            'items': <Object?>[],
            'page': 1,
            'page_size': 20,
            'total': 0,
            'total_pages': 0,
          },
        ),
      ]);

    await tester.pumpWidget(
      ContentRetrievalApp(
        transport: transport,
        fileLauncher: FakeFileLauncher(),
        pathClipboard: FakePathClipboard(),
        settingsStore: _WidgetSettingsStore(),
      ),
    );
    await tester.pumpAndSettle();

    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    final expectedLight = AppTheme.light();
    final expectedDark = AppTheme.dark();
    expect(app.title, '本地内容检索');
    expect(app.debugShowCheckedModeBanner, isFalse);
    expect(app.themeMode, ThemeMode.system);
    expect(app.theme!.brightness, expectedLight.brightness);
    expect(app.theme!.colorScheme, expectedLight.colorScheme);
    expect(app.darkTheme!.brightness, expectedDark.brightness);
    expect(app.darkTheme!.colorScheme, expectedDark.colorScheme);
    expect(find.byType(AppShell), findsOneWidget);
    expect(find.byType(SearchPage), findsOneWidget);
    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.text('搜索内容'), findsOneWidget);
    expect(
      find.text('You have pushed the button this many times:'),
      findsNothing,
    );
    expect(find.byIcon(Icons.add), findsNothing);
    expect(find.byType(FloatingActionButton), findsNothing);
    expect(transport.gets.map((request) => request.path), [
      '/health/ready',
      '/v1/index/stats',
    ]);
    await tester.tap(find.text('索引库'));
    await tester.pumpAndSettle();
    expect(find.byType(IndexLibraryPage), findsOneWidget);
    expect(transport.gets.last.path, '/v1/index/files?page=1&page_size=20');
    await tester.tap(find.text('设置'));
    await tester.pump();
    expect(find.byType(SettingsPage), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    expect(transport.isClosed, isTrue);
  });

  testWidgets('closes its transport once while status startup is pending', (
    tester,
  ) async {
    final transport = _TrackingJsonTransport();

    await tester.pumpWidget(
      ContentRetrievalApp(
        transport: transport,
        fileLauncher: FakeFileLauncher(),
        pathClipboard: FakePathClipboard(),
        settingsStore: _WidgetSettingsStore(),
      ),
    );
    await tester.pump();
    expect(transport.getPaths, ['/health/ready']);

    await tester.pumpWidget(const SizedBox.shrink());
    expect(transport.closeCalls, 1);

    transport.readiness.complete(
      const JsonResponse(statusCode: 200, body: null),
    );
    await tester.pump();
    await tester.pumpAndSettle();
    await tester.pump();

    expect(transport.closeCalls, 1);
    expect(transport.getPaths, ['/health/ready']);
    expect(tester.takeException(), isNull);
  });

  test('main entry boots only ContentRetrievalApp', () {
    final source = File('lib/main.dart').readAsStringSync();

    expect(source, contains('WidgetsFlutterBinding.ensureInitialized();'));
    expect(source, contains('runApp(const ContentRetrievalApp());'));
    for (final forbidden in <String>[
      'MyApp',
      'MyHomePage',
      '_counter',
      'You have pushed the button',
      'FloatingActionButton',
      'Icons.add',
    ]) {
      expect(source, isNot(contains(forbidden)), reason: forbidden);
    }
  });

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
    expect(find.byKey(const Key('app-brand')), findsOneWidget);
    expect(find.text('本地内容检索'), findsOneWidget);

    final rail = tester.widget<NavigationRail>(find.byType(NavigationRail));
    expect(rail.selectedIndex, 0);
  });

  testWidgets('announces the extended brand label exactly once', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    try {
      await tester.binding.setSurfaceSize(const Size(1280, 720));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));

      final brand = tester.getSemantics(find.byKey(const Key('app-brand')));
      expect(brand.label, '本地内容检索');
    } finally {
      semantics.dispose();
    }
  });

  testWidgets('opens the injected index library page', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));
    await tester.tap(find.text('索引库'));
    await tester.pump();

    expect(find.text('INDEX_PAGE'), findsOneWidget);
    expect(
      tester.widget<NavigationRail>(find.byType(NavigationRail)).selectedIndex,
      1,
    );
  });

  testWidgets('opens the injected settings page', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));
    await tester.tap(find.text('设置'));
    await tester.pump();

    expect(find.text('SETTINGS_PAGE'), findsOneWidget);
    expect(
      tester.widget<NavigationRail>(find.byType(NavigationRail)).selectedIndex,
      2,
    );
  });

  testWidgets('extends the navigation rail at desktop width', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1000, 720));
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
    await tester.binding.setSurfaceSize(const Size(999, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));

    final rail = tester.widget<NavigationRail>(find.byType(NavigationRail));
    expect(rail.extended, isFalse);
    expect(rail.minExtendedWidth, 214);
    expect(tester.takeException(), isNull);
  });

  testWidgets('shows a tooltip when hovering a collapsed destination', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(900, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));
    final label = find.text('索引库');
    final labelsBeforeHover = tester.widgetList<Text>(label).length;
    final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
    addTearDown(mouse.removePointer);
    await mouse.addPointer(location: Offset.zero);

    await mouse.moveTo(
      tester.getCenter(find.byIcon(Icons.library_books_outlined)),
    );
    await tester.pump(
      AppTheme.light().tooltipTheme.waitDuration! +
          const Duration(milliseconds: 100),
    );

    expect(label, findsNWidgets(labelsBeforeHover + 1));
    expect(tester.takeException(), isNull);
  });

  testWidgets('scrolls destinations instead of overflowing at short heights', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 120));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(const Text('SEARCH_PAGE')));

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

    final theme = AppTheme.light();
    final scheme = theme.colorScheme;

    expect(theme.scaffoldBackgroundColor, scheme.surfaceContainerLowest);
    expect(
      theme.navigationRailTheme.backgroundColor,
      scheme.surfaceContainerLow,
    );
    expect(theme.cardTheme.elevation, 0);
    expect(
      theme.outlinedButtonTheme.style!.minimumSize!.resolve({}),
      const Size(0, 48),
    );
    expect(
      theme.iconButtonTheme.style!.minimumSize!.resolve({}),
      const Size.square(48),
    );
    expect(
      light.textButtonTheme.style!.minimumSize!.resolve(<WidgetState>{}),
      const Size(48, 48),
    );
    expect(light.snackBarTheme.behavior, SnackBarBehavior.floating);
    expect(light.snackBarTheme.shape, isA<RoundedRectangleBorder>());
    expect(
      (light.snackBarTheme.shape! as RoundedRectangleBorder).borderRadius,
      BorderRadius.circular(12),
    );
    expect(light.popupMenuTheme.shape, isA<RoundedRectangleBorder>());
    expect(
      (light.popupMenuTheme.shape! as RoundedRectangleBorder).borderRadius,
      BorderRadius.circular(12),
    );

    for (final theme in [light, dark]) {
      final scheme = theme.colorScheme;
      expect(theme.inputDecorationTheme.filled, isTrue);
      expect(theme.inputDecorationTheme.fillColor, isA<WidgetStateColor>());
      final inputFill =
          theme.inputDecorationTheme.fillColor! as WidgetStateColor;
      expect(
        inputFill.resolve(const <WidgetState>{}),
        scheme.surfaceContainerHighest,
      );
      expect(
        inputFill.resolve(const {WidgetState.disabled}),
        scheme.onSurface.withValues(alpha: 0.04),
      );

      expect(
        theme.inputDecorationTheme.labelStyle,
        isA<WidgetStateTextStyle>(),
      );
      final inputLabel =
          theme.inputDecorationTheme.labelStyle! as WidgetStateTextStyle;
      expect(inputLabel.resolve(const {WidgetState.error}).color, scheme.error);
      expect(
        inputLabel.resolve(const {WidgetState.disabled}).color,
        scheme.onSurface.withValues(alpha: 0.38),
      );
      expect(
        inputLabel.resolve(const {WidgetState.focused}).color,
        scheme.primary,
      );
      expect(
        inputLabel.resolve(const <WidgetState>{}).color,
        scheme.onSurfaceVariant,
      );

      expect(
        theme.inputDecorationTheme.floatingLabelStyle,
        isA<WidgetStateTextStyle>(),
      );
      final floatingLabel =
          theme.inputDecorationTheme.floatingLabelStyle!
              as WidgetStateTextStyle;
      expect(
        floatingLabel.resolve(const {WidgetState.error}).color,
        scheme.error,
      );
      expect(
        floatingLabel.resolve(const {WidgetState.disabled}).color,
        scheme.onSurface.withValues(alpha: 0.38),
      );
      expect(
        floatingLabel.resolve(const {WidgetState.focused}).color,
        scheme.primary,
      );

      expect(theme.inputDecorationTheme.border, isA<OutlineInputBorder>());
      expect(
        (theme.inputDecorationTheme.border! as OutlineInputBorder).borderRadius,
        BorderRadius.circular(12),
      );
      expect(theme.chipTheme.shape, isA<RoundedRectangleBorder>());
      expect(theme.chipTheme.backgroundColor, scheme.surfaceContainerLow);
      expect(theme.chipTheme.selectedColor, scheme.secondaryContainer);
      expect(theme.chipTheme.labelStyle, isA<WidgetStateTextStyle>());
      final chipLabel = theme.chipTheme.labelStyle! as WidgetStateTextStyle;
      expect(
        chipLabel.resolve(const {WidgetState.selected}).color,
        scheme.onSecondaryContainer,
      );
      expect(
        chipLabel.resolve(const {WidgetState.disabled}).color,
        scheme.onSurface,
      );
      expect(
        chipLabel.resolve(const <WidgetState>{}).color,
        scheme.onSurfaceVariant,
      );
      expect(theme.chipTheme.secondaryLabelStyle, isNull);
      expect(theme.chipTheme.side, isA<WidgetStateBorderSide>());
      final chipSide = theme.chipTheme.side! as WidgetStateBorderSide;
      expect(
        chipSide.resolve(const {WidgetState.selected})!.color,
        scheme.secondary,
      );
      expect(
        chipSide.resolve(const {WidgetState.disabled})!.color,
        scheme.onSurface.withValues(alpha: 0.12),
      );
      expect(
        chipSide.resolve(const <WidgetState>{})!.color,
        scheme.outlineVariant,
      );
      expect(
        theme.navigationRailTheme.backgroundColor,
        scheme.surfaceContainerLow,
      );
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

  for (final themeCase in <({ThemeMode mode, Brightness brightness})>[
    (mode: ThemeMode.light, brightness: Brightness.light),
    (mode: ThemeMode.dark, brightness: Brightness.dark),
  ]) {
    testWidgets(
      'renders ${themeCase.mode.name} state themed controls without overflow',
      (tester) async {
        await tester.binding.setSurfaceSize(const Size(1280, 720));
        addTearDown(() => tester.binding.setSurfaceSize(null));

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            darkTheme: AppTheme.dark(),
            themeMode: themeCase.mode,
            home: const Scaffold(body: _ThemeStateProbe()),
          ),
        );

        final probeContext = tester.element(
          find.byKey(const Key('THEME_STATE_PROBE')),
        );
        expect(Theme.of(probeContext).brightness, themeCase.brightness);
        expect(find.byType(TextField), findsNWidgets(2));
        expect(find.byType(FilterChip), findsNWidgets(3));
        expect(tester.takeException(), isNull);
      },
    );
  }
}

Widget _buildApp(Widget searchPage) {
  return MaterialApp(
    theme: AppTheme.light(),
    darkTheme: AppTheme.dark(),
    home: AppShell(
      searchPage: searchPage,
      indexLibraryPage: const Text('INDEX_PAGE'),
      settingsPage: const Text('SETTINGS_PAGE'),
    ),
  );
}

final class _WidgetSettingsStore implements SettingsStore {
  @override
  Future<SettingsStoreSnapshot> load() async {
    return const SettingsStoreSnapshot(
      values: <String, Object?>{},
      storageRecovered: false,
    );
  }

  @override
  Future<void> save(Map<String, Object?> values) async {}
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

final class _ThemeStateProbe extends StatelessWidget {
  const _ThemeStateProbe();

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      key: const Key('THEME_STATE_PROBE'),
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const TextField(decoration: InputDecoration(labelText: '可用输入框')),
          const SizedBox(height: 16),
          const TextField(
            enabled: false,
            decoration: InputDecoration(labelText: '禁用输入框'),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            children: [
              FilterChip(
                label: const Text('未选择'),
                selected: false,
                onSelected: (_) {},
              ),
              FilterChip(
                label: const Text('已选择'),
                selected: true,
                onSelected: (_) {},
              ),
              const FilterChip(
                label: Text('已禁用'),
                selected: false,
                onSelected: null,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

final class _TrackingJsonTransport implements JsonTransport {
  final readiness = Completer<JsonResponse>();
  final getPaths = <String>[];
  final posts = <({String path, Map<String, Object?> body})>[];

  int closeCalls = 0;

  @override
  Future<JsonResponse> get(String path) async {
    getPaths.add(path);
    if (path == '/health/ready') {
      return readiness.future;
    }
    throw StateError('Unexpected GET $path');
  }

  @override
  Future<JsonResponse> post(
    String path, {
    required Map<String, Object?> body,
  }) async {
    posts.add((path: path, body: Map<String, Object?>.unmodifiable(body)));
    throw StateError('Unexpected POST $path');
  }

  @override
  Future<JsonResponse> delete(String path) async {
    throw StateError('Unexpected DELETE $path');
  }

  @override
  void close() {
    closeCalls += 1;
  }
}
