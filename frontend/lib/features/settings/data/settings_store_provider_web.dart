// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:convert';
import 'dart:html' as html;

import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';

SettingsStore createPlatformSettingsStore() => const _WebSettingsStore();

final class _WebSettingsStore implements SettingsStore {
  const _WebSettingsStore();

  static const _key = 'content-retrieval.week5.settings';

  @override
  Future<SettingsStoreSnapshot> load() async {
    final raw = html.window.localStorage[_key];
    if (raw == null) {
      return const SettingsStoreSnapshot(
        values: <String, Object?>{},
        storageRecovered: false,
      );
    }
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) return _recovered;
      return SettingsStoreSnapshot(
        values: Map<String, Object?>.unmodifiable(decoded),
        storageRecovered: false,
      );
    } on FormatException {
      return _recovered;
    }
  }

  @override
  Future<void> save(Map<String, Object?> values) async {
    html.window.localStorage[_key] = jsonEncode(values);
  }

  static const _recovered = SettingsStoreSnapshot(
    values: <String, Object?>{},
    storageRecovered: true,
  );
}
