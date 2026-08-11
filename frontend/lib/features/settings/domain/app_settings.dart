enum AppThemePreference { system, light, dark }

const defaultSettings = AppSettings(
  backendBaseUrl: 'http://127.0.0.1:8000',
  themeMode: AppThemePreference.system,
  highContrast: false,
  textScale: 1,
  reduceMotion: false,
);

const supportedTextScales = <double>[1, 1.25, 1.5, 2];

final class AppSettings {
  const AppSettings({
    required this.backendBaseUrl,
    required this.themeMode,
    required this.highContrast,
    required this.textScale,
    required this.reduceMotion,
  });

  final String backendBaseUrl;
  final AppThemePreference themeMode;
  final bool highContrast;
  final double textScale;
  final bool reduceMotion;

  AppSettings copyWith({
    String? backendBaseUrl,
    AppThemePreference? themeMode,
    bool? highContrast,
    double? textScale,
    bool? reduceMotion,
  }) {
    return AppSettings(
      backendBaseUrl: backendBaseUrl ?? this.backendBaseUrl,
      themeMode: themeMode ?? this.themeMode,
      highContrast: highContrast ?? this.highContrast,
      textScale: textScale ?? this.textScale,
      reduceMotion: reduceMotion ?? this.reduceMotion,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is AppSettings &&
            backendBaseUrl == other.backendBaseUrl &&
            themeMode == other.themeMode &&
            highContrast == other.highContrast &&
            textScale == other.textScale &&
            reduceMotion == other.reduceMotion;
  }

  @override
  int get hashCode => Object.hash(
    backendBaseUrl,
    themeMode,
    highContrast,
    textScale,
    reduceMotion,
  );
}

String? normalizeBackendBaseUrl(String value) {
  final trimmed = value.trim();
  final uri = Uri.tryParse(trimmed);
  if (uri == null ||
      !uri.isAbsolute ||
      (uri.scheme != 'http' && uri.scheme != 'https') ||
      uri.host.isEmpty ||
      uri.userInfo.isNotEmpty ||
      uri.hasQuery ||
      uri.hasFragment ||
      (uri.path.isNotEmpty && uri.path != '/')) {
    return null;
  }
  return trimmed.endsWith('/')
      ? trimmed.substring(0, trimmed.length - 1)
      : trimmed;
}
