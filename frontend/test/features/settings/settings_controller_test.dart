import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';
import 'package:content_retrieval_app/features/settings/domain/app_settings.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_controller.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('load publishes settings and a dismissible recovery warning', () async {
    final store = _ControllerStore(
      snapshot: const SettingsStoreSnapshot(
        values: {SettingsKeys.textScale: 7.0},
        storageRecovered: false,
      ),
    );
    final controller = SettingsController(SettingsRepository(store));
    addTearDown(controller.dispose);

    await controller.load();

    expect(controller.settings, defaultSettings);
    expect(controller.recoveredKeys, {SettingsKeys.textScale});
    expect(controller.recoveryWarning, '部分设置数据无效，已恢复安全默认值。');
    controller.dismissRecoveryWarning();
    expect(controller.recoveryWarning, isNull);
  });

  test('backend URL validation normalizes a trailing slash', () async {
    final store = _ControllerStore();
    final controller = SettingsController(SettingsRepository(store));
    addTearDown(controller.dispose);
    await controller.load();

    controller.setBackendBaseUrl('https://localhost:9443/');
    expect(controller.backendUrlError, isNull);
    expect(await controller.save(), isTrue);

    expect(controller.settings.backendBaseUrl, 'https://localhost:9443');
    expect(
      store.savedValues.single[SettingsKeys.backendBaseUrl],
      'https://localhost:9443',
    );
  });

  test('hasUnsavedChanges follows draft and persisted settings', () async {
    final controller = SettingsController(
      SettingsRepository(_ControllerStore()),
    );
    addTearDown(controller.dispose);
    await controller.load();

    expect(controller.hasUnsavedChanges, isFalse);
    controller.setTextScale(1.5);
    expect(controller.hasUnsavedChanges, isTrue);
    expect(await controller.save(), isTrue);
    expect(controller.hasUnsavedChanges, isFalse);
  });

  test('rejects credentials query fragment and unsupported schemes', () async {
    final controller = SettingsController(
      SettingsRepository(_ControllerStore()),
    );
    addTearDown(controller.dispose);
    await controller.load();

    for (final value in [
      'ftp://localhost:8000',
      'http://user:pass@localhost:8000',
      'http://localhost:8000?x=1',
      'http://localhost:8000/#fragment',
    ]) {
      controller.setBackendBaseUrl(value);
      expect(controller.backendUrlError, isNotNull, reason: value);
    }
  });

  test('save failure retains the last saved settings', () async {
    final store = _ControllerStore()..saveError = StateError('disk full');
    final controller = SettingsController(SettingsRepository(store));
    addTearDown(controller.dispose);
    await controller.load();

    controller
      ..setHighContrast(true)
      ..setTextScale(2);
    expect(await controller.save(), isFalse);

    expect(controller.settings, defaultSettings);
    expect(controller.draft.highContrast, isTrue);
    expect(controller.draft.textScale, 2);
    expect(controller.hasUnsavedChanges, isTrue);
    expect(controller.saveError, '无法保存设置，请重试。');
  });

  test('reset persists and publishes defaults', () async {
    final store = _ControllerStore(
      snapshot: const SettingsStoreSnapshot(
        values: {
          SettingsKeys.backendBaseUrl: 'http://localhost:9000',
          SettingsKeys.themeMode: 'dark',
          SettingsKeys.highContrast: true,
          SettingsKeys.textScale: 2.0,
          SettingsKeys.reduceMotion: true,
        },
        storageRecovered: false,
      ),
    );
    final controller = SettingsController(SettingsRepository(store));
    addTearDown(controller.dispose);
    await controller.load();

    expect(await controller.reset(), isTrue);

    expect(controller.settings, defaultSettings);
    expect(controller.draft, defaultSettings);
    expect(store.savedValues.single[SettingsKeys.themeMode], 'system');
  });
}

final class _ControllerStore implements SettingsStore {
  _ControllerStore({
    this.snapshot = const SettingsStoreSnapshot(
      values: {},
      storageRecovered: false,
    ),
  });

  final SettingsStoreSnapshot snapshot;
  final List<Map<String, Object?>> savedValues = [];
  Object? saveError;

  @override
  Future<SettingsStoreSnapshot> load() async => snapshot;

  @override
  Future<void> save(Map<String, Object?> values) async {
    if (saveError != null) throw saveError!;
    savedValues.add(Map<String, Object?>.from(values));
  }
}
