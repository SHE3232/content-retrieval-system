import 'package:content_retrieval_app/features/settings/domain/app_settings.dart';

abstract final class SettingsKeys {
  static const backendBaseUrl = 'week5.backendBaseUrl';
  static const themeMode = 'week5.themeMode';
  static const highContrast = 'week5.highContrast';
  static const textScale = 'week5.textScale';
  static const reduceMotion = 'week5.reduceMotion';

  static const all = <String>[
    backendBaseUrl,
    themeMode,
    highContrast,
    textScale,
    reduceMotion,
  ];
}

final class SettingsStoreSnapshot {
  const SettingsStoreSnapshot({
    required this.values,
    required this.storageRecovered,
  });

  final Map<String, Object?> values;
  final bool storageRecovered;
}

abstract interface class SettingsStore {
  Future<SettingsStoreSnapshot> load();
  Future<void> save(Map<String, Object?> values);
}

final class SettingsLoadResult {
  const SettingsLoadResult({
    required this.settings,
    required this.recoveredKeys,
  });

  final AppSettings settings;
  final Set<String> recoveredKeys;
}

final class SettingsRepository {
  const SettingsRepository(this._store);

  final SettingsStore _store;

  Future<SettingsLoadResult> load() async {
    final snapshot = await _store.load();
    if (snapshot.storageRecovered) {
      return SettingsLoadResult(
        settings: defaultSettings,
        recoveredKeys: SettingsKeys.all.toSet(),
      );
    }

    final values = snapshot.values;
    final recovered = <String>{};

    final backendBaseUrl = _read<String>(
      values,
      SettingsKeys.backendBaseUrl,
      defaultSettings.backendBaseUrl,
      (value) => value is String ? normalizeBackendBaseUrl(value) : null,
      recovered,
    );
    final themeMode = _read<AppThemePreference>(
      values,
      SettingsKeys.themeMode,
      defaultSettings.themeMode,
      _parseTheme,
      recovered,
    );
    final highContrast = _read<bool>(
      values,
      SettingsKeys.highContrast,
      defaultSettings.highContrast,
      (value) => value is bool ? value : null,
      recovered,
    );
    final textScale = _read<double>(
      values,
      SettingsKeys.textScale,
      defaultSettings.textScale,
      _parseTextScale,
      recovered,
    );
    final reduceMotion = _read<bool>(
      values,
      SettingsKeys.reduceMotion,
      defaultSettings.reduceMotion,
      (value) => value is bool ? value : null,
      recovered,
    );

    return SettingsLoadResult(
      settings: AppSettings(
        backendBaseUrl: backendBaseUrl,
        themeMode: themeMode,
        highContrast: highContrast,
        textScale: textScale,
        reduceMotion: reduceMotion,
      ),
      recoveredKeys: Set<String>.unmodifiable(recovered),
    );
  }

  Future<void> save(AppSettings settings) {
    return _store.save(<String, Object?>{
      SettingsKeys.backendBaseUrl: settings.backendBaseUrl,
      SettingsKeys.themeMode: settings.themeMode.name,
      SettingsKeys.highContrast: settings.highContrast,
      SettingsKeys.textScale: settings.textScale,
      SettingsKeys.reduceMotion: settings.reduceMotion,
    });
  }

  T _read<T>(
    Map<String, Object?> values,
    String key,
    T fallback,
    T? Function(Object? value) parse,
    Set<String> recovered,
  ) {
    if (!values.containsKey(key)) return fallback;
    final parsed = parse(values[key]);
    if (parsed != null) return parsed;
    recovered.add(key);
    return fallback;
  }

  static AppThemePreference? _parseTheme(Object? value) {
    if (value is! String) return null;
    for (final preference in AppThemePreference.values) {
      if (preference.name == value) return preference;
    }
    return null;
  }

  static double? _parseTextScale(Object? value) {
    if (value is! num) return null;
    final parsed = value.toDouble();
    return supportedTextScales.contains(parsed) ? parsed : null;
  }
}
