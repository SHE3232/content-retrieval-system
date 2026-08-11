import 'dart:io';

import 'package:content_retrieval_app/features/settings/data/json_file_settings_store.dart';
import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late Directory directory;
  late File settingsFile;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('week5-settings-');
    settingsFile = File(
      '${directory.path}${Platform.pathSeparator}settings.json',
    );
  });

  tearDown(() async {
    if (await directory.exists()) await directory.delete(recursive: true);
  });

  test('missing file loads an empty healthy snapshot', () async {
    final snapshot = await JsonFileSettingsStore(settingsFile).load();

    expect(snapshot.values, isEmpty);
    expect(snapshot.storageRecovered, isFalse);
  });

  test('save and load round-trip one complete JSON object', () async {
    final store = JsonFileSettingsStore(settingsFile);
    final values = <String, Object?>{
      SettingsKeys.backendBaseUrl: 'http://localhost:9000',
      SettingsKeys.themeMode: 'dark',
      SettingsKeys.highContrast: true,
      SettingsKeys.textScale: 2.0,
      SettingsKeys.reduceMotion: true,
    };

    await store.save(values);
    final snapshot = await store.load();

    expect(snapshot.values, values);
    expect(snapshot.storageRecovered, isFalse);
    expect(directory.listSync().whereType<File>().map((file) => file.path), [
      settingsFile.path,
    ]);
  });

  test('invalid JSON is reported as recovered storage', () async {
    await settingsFile.writeAsString('{not-json');

    final snapshot = await JsonFileSettingsStore(settingsFile).load();

    expect(snapshot.values, isEmpty);
    expect(snapshot.storageRecovered, isTrue);
  });

  test('non-object JSON is reported as recovered storage', () async {
    await settingsFile.writeAsString('[1, 2, 3]');

    final snapshot = await JsonFileSettingsStore(settingsFile).load();

    expect(snapshot.values, isEmpty);
    expect(snapshot.storageRecovered, isTrue);
  });
}
