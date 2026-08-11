import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';
import 'package:content_retrieval_app/features/settings/domain/app_settings.dart';
import 'package:flutter/foundation.dart';

final class SettingsController extends ChangeNotifier {
  SettingsController(this._repository);

  final SettingsRepository _repository;

  AppSettings settings = defaultSettings;
  AppSettings draft = defaultSettings;
  Set<String> recoveredKeys = const <String>{};
  String? recoveryWarning;
  String? backendUrlError;
  String? saveError;
  bool isBusy = false;
  bool _disposed = false;

  Future<void> load() async {
    isBusy = true;
    _notify();
    try {
      final result = await _repository.load();
      if (_disposed) return;
      settings = result.settings;
      draft = result.settings;
      recoveredKeys = result.recoveredKeys;
      recoveryWarning = recoveredKeys.isEmpty ? null : '部分设置数据无效，已恢复安全默认值。';
      backendUrlError = null;
      saveError = null;
    } finally {
      isBusy = false;
      _notify();
    }
  }

  void dismissRecoveryWarning() {
    if (recoveryWarning == null) return;
    recoveryWarning = null;
    _notify();
  }

  void setBackendBaseUrl(String value) {
    draft = draft.copyWith(backendBaseUrl: value);
    backendUrlError = normalizeBackendBaseUrl(value) == null
        ? '请输入不含路径、凭据、查询或片段的 HTTP(S) 地址。'
        : null;
    saveError = null;
    _notify();
  }

  void setThemeMode(AppThemePreference value) {
    draft = draft.copyWith(themeMode: value);
    saveError = null;
    _notify();
  }

  void setHighContrast(bool value) {
    draft = draft.copyWith(highContrast: value);
    saveError = null;
    _notify();
  }

  void setTextScale(double value) {
    if (!supportedTextScales.contains(value)) return;
    draft = draft.copyWith(textScale: value);
    saveError = null;
    _notify();
  }

  void setReduceMotion(bool value) {
    draft = draft.copyWith(reduceMotion: value);
    saveError = null;
    _notify();
  }

  Future<bool> save() async {
    final normalizedUrl = normalizeBackendBaseUrl(draft.backendBaseUrl);
    if (normalizedUrl == null) {
      backendUrlError = '请输入不含路径、凭据、查询或片段的 HTTP(S) 地址。';
      _notify();
      return false;
    }
    final candidate = draft.copyWith(backendBaseUrl: normalizedUrl);
    return _persist(candidate);
  }

  Future<bool> reset() => _persist(defaultSettings);

  Future<bool> _persist(AppSettings candidate) async {
    if (isBusy) return false;
    isBusy = true;
    saveError = null;
    _notify();
    try {
      await _repository.save(candidate);
      if (_disposed) return false;
      settings = candidate;
      draft = candidate;
      backendUrlError = null;
      recoveredKeys = const <String>{};
      recoveryWarning = null;
      return true;
    } catch (_) {
      if (!_disposed) saveError = '无法保存设置，请重试。';
      return false;
    } finally {
      isBusy = false;
      _notify();
    }
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
