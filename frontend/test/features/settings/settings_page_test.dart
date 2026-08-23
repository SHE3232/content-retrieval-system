import 'dart:async';

import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_controller.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('settings separates connection appearance and accessibility', (
    tester,
  ) async {
    final controller = SettingsController(
      SettingsRepository(_PageSettingsStore()),
    );
    addTearDown(controller.dispose);
    await controller.load();

    await tester.pumpWidget(_app(controller));

    expect(find.text('这些偏好只保存在当前设备上'), findsOneWidget);
    expect(
      find.byKey(const Key('settings-connection-section')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('settings-appearance-section')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('settings-accessibility-section')),
      findsOneWidget,
    );
    expect(find.text('已保存'), findsOneWidget);
    expect(find.byType(Card), findsNothing);
  });

  testWidgets('settings reports unsaved changes and confirms reset', (
    tester,
  ) async {
    final controller = SettingsController(
      SettingsRepository(_PageSettingsStore()),
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller));

    await tester.tap(find.text('150%'));
    await tester.pump();
    expect(find.text('尚未保存更改'), findsOneWidget);

    final resetButton = find.widgetWithText(OutlinedButton, '恢复默认设置');
    await tester.drag(find.byType(ListView), const Offset(0, -400));
    await tester.pumpAndSettle();
    await tester.tap(resetButton);
    await tester.pumpAndSettle();
    expect(find.text('恢复默认设置？'), findsOneWidget);
    expect(find.text('当前未保存的更改将被替换。'), findsOneWidget);
    await tester.tap(find.widgetWithText(TextButton, '取消'));
    await tester.pumpAndSettle();
    expect(controller.draft.textScale, 1.5);
  });

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
    expect(find.text('外观'), findsOneWidget);
    expect(find.text('无障碍'), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('backend-base-url')),
      'https://localhost:9443/',
    );
    await tester.tap(find.text('深色'));
    await tester.tap(find.text('高对比度'));
    await tester.tap(find.text('减少动态效果'));
    await tester.tap(find.text('200%'));
    await tester.pump();
    final saveButton = find.widgetWithText(FilledButton, '保存设置');
    await tester.drag(find.byType(ListView), const Offset(0, -400));
    await tester.pumpAndSettle();
    await tester.tap(saveButton);
    await tester.pumpAndSettle();

    expect(controller.settings.backendBaseUrl, 'https://localhost:9443');
    expect(controller.settings.themeMode.name, 'dark');
    expect(controller.settings.highContrast, isTrue);
    expect(controller.settings.reduceMotion, isTrue);
    expect(controller.settings.textScale, 2);
    expect(saveNotifications, 1);
    expect(find.byType(SnackBar), findsOneWidget);
    expect(find.text('设置已保存'), findsOneWidget);
    expect(_liveRegions(), findsOneWidget);
    expect(find.text('已保存'), findsOneWidget);
  });

  testWidgets('unchanged settings cannot be saved', (tester) async {
    final controller = SettingsController(
      SettingsRepository(_PageSettingsStore()),
    );
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller));

    final saveButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '保存设置'),
    );
    expect(saveButton.onPressed, isNull);
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
    expect(find.byKey(const Key('workspace-notice')), findsOneWidget);
    expect(_liveRegions(), findsOneWidget);
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
    expect(find.text('尚未保存更改'), findsOneWidget);
    final saveButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '保存设置'),
    );
    expect(saveButton.onPressed, isNull);
  });

  testWidgets('save failure keeps the draft and uses a persistent notice', (
    tester,
  ) async {
    final store = _PageSettingsStore()..saveError = StateError('disk full');
    final controller = SettingsController(SettingsRepository(store));
    addTearDown(controller.dispose);
    await controller.load();
    await tester.pumpWidget(_app(controller));

    await tester.enterText(
      find.byKey(const Key('backend-base-url')),
      'https://localhost:9443/',
    );
    await tester.pump();
    final saveButton = find.widgetWithText(FilledButton, '保存设置');
    await tester.drag(find.byType(ListView), const Offset(0, -400));
    await tester.pumpAndSettle();
    await tester.tap(saveButton);
    await tester.pumpAndSettle();

    expect(controller.draft.backendBaseUrl, 'https://localhost:9443/');
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('backend-base-url')))
          .controller!
          .text,
      'https://localhost:9443/',
    );
    expect(find.text('尚未保存更改'), findsOneWidget);
    expect(find.text('无法保存设置，请重试。'), findsOneWidget);
    final notice = find.byKey(const Key('workspace-notice'));
    expect(notice, findsOneWidget);
    expect(tester.widget<Semantics>(notice).properties.liveRegion, isTrue);
    expect(find.text('设置已保存'), findsNothing);
  });

  testWidgets('delayed save failure restores focus to the save button', (
    tester,
  ) async {
    final saveWait = Completer<void>();
    final store = _PageSettingsStore()
      ..saveWait = saveWait
      ..saveError = StateError('disk full');
    final controller = SettingsController(SettingsRepository(store));
    addTearDown(controller.dispose);
    await controller.load();
    controller.setTextScale(1.5);
    await tester.pumpWidget(_app(controller));

    final saveFinder = find.widgetWithText(FilledButton, '保存设置');
    await tester.drag(find.byType(ListView), const Offset(0, -400));
    await tester.pumpAndSettle();
    final saveButton = tester.widget<FilledButton>(saveFinder);
    expect(saveButton.focusNode, isNotNull);
    saveButton.focusNode!.requestFocus();
    await tester.pump();
    expect(saveButton.focusNode!.hasFocus, isTrue);

    await tester.tap(saveFinder);
    await tester.pump();
    expect(controller.isBusy, isTrue);
    expect(
      tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
      isNull,
    );

    saveWait.complete();
    await tester.pumpAndSettle();
    expect(saveButton.focusNode!.hasFocus, isTrue);
  });

  testWidgets('delayed reset failure restores focus to the reset button', (
    tester,
  ) async {
    final saveWait = Completer<void>();
    final store = _PageSettingsStore()
      ..saveWait = saveWait
      ..saveError = StateError('disk full');
    final controller = SettingsController(SettingsRepository(store));
    addTearDown(controller.dispose);
    await controller.load();
    controller.setTextScale(1.5);
    await tester.pumpWidget(_app(controller));

    final resetFinder = find.widgetWithText(OutlinedButton, '恢复默认设置');
    await tester.drag(find.byType(ListView), const Offset(0, -400));
    await tester.pumpAndSettle();
    final resetButton = tester.widget<OutlinedButton>(resetFinder);
    expect(resetButton.focusNode, isNotNull);
    resetButton.focusNode!.requestFocus();
    await tester.pump();
    expect(resetButton.focusNode!.hasFocus, isTrue);

    await tester.tap(resetFinder);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '恢复默认设置'));
    await tester.pump();
    expect(controller.isBusy, isTrue);
    expect(tester.widget<OutlinedButton>(resetFinder).onPressed, isNull);

    saveWait.complete();
    await tester.pumpAndSettle();
    expect(resetButton.focusNode!.hasFocus, isTrue);
  });

  testWidgets('hidden settings never reclaim focus after a delayed save', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final saveWait = Completer<void>();
    final store = _PageSettingsStore()
      ..saveWait = saveWait
      ..saveError = StateError('disk full');
    final controller = SettingsController(SettingsRepository(store));
    final settingsVisible = ValueNotifier<bool>(true);
    final outsideFocus = FocusNode(debugLabel: 'outside-settings');
    addTearDown(controller.dispose);
    addTearDown(settingsVisible.dispose);
    addTearDown(outsideFocus.dispose);
    await controller.load();
    controller.setTextScale(1.5);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              Expanded(
                child: ValueListenableBuilder<bool>(
                  valueListenable: settingsVisible,
                  builder: (context, visible, _) => Visibility(
                    visible: visible,
                    maintainState: true,
                    maintainAnimation: true,
                    maintainSize: true,
                    maintainSemantics: true,
                    maintainInteractivity: true,
                    maintainFocusability: true,
                    child: SettingsPage(controller: controller),
                  ),
                ),
              ),
              FilledButton(
                focusNode: outsideFocus,
                onPressed: () {},
                child: const Text('设置页外操作'),
              ),
            ],
          ),
        ),
      ),
    );

    final saveFinder = find.widgetWithText(FilledButton, '保存设置');
    await tester.drag(find.byType(ListView), const Offset(0, -400));
    await tester.pumpAndSettle();
    final saveFocus = tester.widget<FilledButton>(saveFinder).focusNode!;
    saveFocus.requestFocus();
    await tester.pump();
    await tester.tap(saveFinder);
    await tester.pump();
    expect(controller.isBusy, isTrue);

    settingsVisible.value = false;
    await tester.pump();
    outsideFocus.requestFocus();
    await tester.pump();
    expect(outsideFocus.hasFocus, isTrue);

    saveWait.complete();
    await tester.pumpAndSettle();
    expect(outsideFocus.hasFocus, isTrue);
    expect(saveFocus.hasFocus, isFalse);
  });

  testWidgets('confirmed reset persists defaults and uses a SnackBar', (
    tester,
  ) async {
    final controller = SettingsController(
      SettingsRepository(_PageSettingsStore()),
    );
    addTearDown(controller.dispose);
    await controller.load();
    controller.setTextScale(1.5);
    await tester.pumpWidget(_app(controller));

    final resetButton = find.widgetWithText(OutlinedButton, '恢复默认设置');
    await tester.drag(find.byType(ListView), const Offset(0, -400));
    await tester.pumpAndSettle();
    await tester.tap(resetButton);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '恢复默认设置'));
    await tester.pumpAndSettle();

    expect(controller.settings.textScale, 1);
    expect(controller.hasUnsavedChanges, isFalse);
    expect(find.byType(SnackBar), findsOneWidget);
    expect(find.text('已恢复默认设置'), findsOneWidget);
    expect(_liveRegions(), findsOneWidget);
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
    expect(find.text('外观'), findsOneWidget);
    expect(find.text('无障碍'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '保存设置'), findsOneWidget);
    expect(find.text('已保存'), findsOneWidget);
  });
}

Finder _liveRegions() => find.byWidgetPredicate(
  (widget) => widget is Semantics && widget.properties.liveRegion == true,
);

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
  Object? saveError;
  Completer<void>? saveWait;

  @override
  Future<SettingsStoreSnapshot> load() async => snapshot;

  @override
  Future<void> save(Map<String, Object?> values) async {
    await saveWait?.future;
    if (saveError != null) throw saveError!;
    saved = Map<String, Object?>.from(values);
  }
}
