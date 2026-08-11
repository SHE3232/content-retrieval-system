import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';
import 'package:content_retrieval_app/features/settings/domain/app_settings.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'missing settings load safe defaults without recovery warnings',
    () async {
      final store = _MemorySettingsStore();

      final result = await SettingsRepository(store).load();

      expect(result.settings, defaultSettings);
      expect(result.recoveredKeys, isEmpty);
    },
  );

  test(
    'malformed values recover independently and report exact keys',
    () async {
      final store = _MemorySettingsStore(
        values: {
          SettingsKeys.backendBaseUrl: 'not-a-url',
          SettingsKeys.themeMode: 'dark',
          SettingsKeys.highContrast: 'yes',
          SettingsKeys.textScale: 1.5,
          SettingsKeys.reduceMotion: true,
        },
      );

      final result = await SettingsRepository(store).load();

      expect(result.settings.backendBaseUrl, defaultSettings.backendBaseUrl);
      expect(result.settings.themeMode, AppThemePreference.dark);
      expect(result.settings.highContrast, defaultSettings.highContrast);
      expect(result.settings.textScale, 1.5);
      expect(result.settings.reduceMotion, isTrue);
      expect(result.recoveredKeys, {
        SettingsKeys.backendBaseUrl,
        SettingsKeys.highContrast,
      });
    },
  );

  test('corrupted storage recovers every setting key', () async {
    final store = _MemorySettingsStore(storageRecovered: true);

    final result = await SettingsRepository(store).load();

    expect(result.settings, defaultSettings);
    expect(result.recoveredKeys, SettingsKeys.all.toSet());
  });

  test('save persists one complete immutable snapshot', () async {
    final store = _MemorySettingsStore();
    const settings = AppSettings(
      backendBaseUrl: 'https://localhost:9443',
      themeMode: AppThemePreference.light,
      highContrast: true,
      textScale: 2,
      reduceMotion: true,
    );

    await SettingsRepository(store).save(settings);

    expect(store.saveCalls, 1);
    expect(store.values, {
      SettingsKeys.backendBaseUrl: 'https://localhost:9443',
      SettingsKeys.themeMode: 'light',
      SettingsKeys.highContrast: true,
      SettingsKeys.textScale: 2.0,
      SettingsKeys.reduceMotion: true,
    });
  });
}

final class _MemorySettingsStore implements SettingsStore {
  _MemorySettingsStore({
    Map<String, Object?>? values,
    this.storageRecovered = false,
  }) : values = Map<String, Object?>.from(values ?? const {});

  Map<String, Object?> values;
  final bool storageRecovered;
  int saveCalls = 0;

  @override
  Future<SettingsStoreSnapshot> load() async {
    return SettingsStoreSnapshot(
      values: Map<String, Object?>.unmodifiable(values),
      storageRecovered: storageRecovered,
    );
  }

  @override
  Future<void> save(Map<String, Object?> values) async {
    saveCalls += 1;
    this.values = Map<String, Object?>.from(values);
  }
}
