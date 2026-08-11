import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_controller.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('edits and persists every Week 5 preference', (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final store = _PageSettingsStore();
    final controller = SettingsController(SettingsRepository(store));
    addTearDown(controller.dispose);
    await controller.load();
    var saveNotifications = 0;

    await tester.pumpWidget(
      _app(controller, onSettingsSaved: () => saveNotifications += 1),
    );

    expect(find.text('设置'), findsOneWidget);
    expect(find.text('外观与无障碍'), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('backend-base-url')),
      'https://localhost:9443/',
    );
    await tester.tap(find.text('深色'));
    await tester.tap(find.text('高对比度'));
    await tester.tap(find.text('减少动态效果'));
    await tester.tap(find.text('200%'));
    await tester.tap(find.widgetWithText(FilledButton, '保存设置'));
    await tester.pumpAndSettle();

    expect(controller.settings.backendBaseUrl, 'https://localhost:9443');
    expect(controller.settings.themeMode.name, 'dark');
    expect(controller.settings.highContrast, isTrue);
    expect(controller.settings.reduceMotion, isTrue);
    expect(controller.settings.textScale, 2);
    expect(saveNotifications, 1);
    expect(find.text('设置已保存'), findsOneWidget);
  });

  testWidgets('shows a dismissible recovery warning', (tester) async {
    final store = _PageSettingsStore(
      snapshot: const SettingsStoreSnapshot(
        values: {SettingsKeys.themeMode: 'ultraviolet'},
        storageRecovered: false,
      ),
    );
    final controller = SettingsController(SettingsRepository(store));
    addTearDown(controller.dispose);
    await controller.load();

    await tester.pumpWidget(_app(controller));

    expect(find.textContaining('已恢复安全默认值'), findsOneWidget);
    await tester.tap(find.widgetWithText(TextButton, '知道了'));
    await tester.pump();
    expect(find.textContaining('已恢复安全默认值'), findsNothing);
  });

  testWidgets('invalid backend URL blocks saving and explains the format', (
    tester,
  ) async {
    final controller = SettingsController(
      SettingsRepository(_PageSettingsStore()),
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller));

    await tester.enterText(
      find.byKey(const Key('backend-base-url')),
      'ftp://localhost:8000',
    );
    await tester.pump();

    expect(find.textContaining('HTTP(S)'), findsOneWidget);
    final saveButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '保存设置'),
    );
    expect(saveButton.onPressed, isNull);
  });

  testWidgets('settings page has no overflow at 200 percent text scale', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller = SettingsController(
      SettingsRepository(_PageSettingsStore()),
    );
    addTearDown(controller.dispose);
    await controller.load();

    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(2)),
        child: _app(controller),
      ),
    );
    await tester.pump();

    expect(tester.takeException(), isNull);
    expect(find.text('外观与无障碍'), findsOneWidget);
  });
}

Widget _app(SettingsController controller, {VoidCallback? onSettingsSaved}) {
  return MaterialApp(
    home: Scaffold(
      body: SettingsPage(
        controller: controller,
        onSettingsSaved: onSettingsSaved,
      ),
    ),
  );
}

final class _PageSettingsStore implements SettingsStore {
  _PageSettingsStore({
    this.snapshot = const SettingsStoreSnapshot(
      values: <String, Object?>{},
      storageRecovered: false,
    ),
  });

  final SettingsStoreSnapshot snapshot;
  Map<String, Object?>? saved;

  @override
  Future<SettingsStoreSnapshot> load() async => snapshot;

  @override
  Future<void> save(Map<String, Object?> values) async {
    saved = Map<String, Object?>.from(values);
  }
}
